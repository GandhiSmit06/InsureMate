"""services/agent_service.py
Service layer connecting InsureMateAgent, ToolExecutor, and ClaimDatabase.
Manages file uploads, session lifecycles, autonomous agent execution,
and persistent claim memory.
"""

import os
import shutil
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from agent.insuremate_agent import InsureMateAgent
from agent.state import ClaimState, ClaimStatus
from services.database.db import ClaimDatabase
from utils.logger import logger

ROOT_DIR = Path(__file__).resolve().parent.parent
UPLOADS_DIR = ROOT_DIR / "uploads"


class AgentService:
    """Coordinates claim session creation, agent orchestration, and memory persistence."""

    def __init__(
        self,
        db: Optional[ClaimDatabase] = None,
        db_path: Optional[Union[str, Path]] = None,
        upload_dir: Optional[Union[str, Path]] = None
    ):
        if db is not None:
            self.db = db
        elif db_path is not None:
            self.db = ClaimDatabase(db_path=db_path)
        else:
            self.db = ClaimDatabase()

        self.upload_dir = Path(upload_dir) if upload_dir else UPLOADS_DIR
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self._running_claims: set = set()
        self._lock = threading.Lock()

    def is_claim_running(self, claim_id: str) -> bool:
        """Check whether the agent is currently running for the claim."""
        with self._lock:
            return claim_id in self._running_claims

    def acquire_claim_lock(self, claim_id: str) -> bool:
        """Attempt to acquire execution lock for claim_id. Returns True if acquired."""
        with self._lock:
            if claim_id in self._running_claims:
                return False
            self._running_claims.add(claim_id)
            return True

    def release_claim_lock(self, claim_id: str) -> None:
        """Release execution lock for claim_id."""
        with self._lock:
            self._running_claims.discard(claim_id)

    def create_session(
        self,
        goal: str = "Determine claim readiness and identify missing evidence.",
        session_name: Optional[str] = None,
        claim_type: str = "general",
        policy_file_path: Optional[str] = None,
        claim_file_path: Optional[str] = None,
        policy_filename: Optional[str] = None,
        claim_filename: Optional[str] = None,
        offline_mode: bool = False
    ) -> Dict[str, Any]:
        """Initialize a new claim session with uploaded or referenced documents."""
        claim_id = f"CLM-{uuid.uuid4().hex[:8].upper()}"
        name = session_name or f"Claim Session {claim_id}"

        claim = self.db.create_claim(
            claim_id=claim_id,
            goal=goal,
            session_name=name,
            claim_type=claim_type,
            policy_path=policy_file_path,
            claim_path=claim_file_path,
            policy_filename=policy_filename or (Path(policy_file_path).name if policy_file_path else None),
            claim_filename=claim_filename or (Path(claim_file_path).name if claim_file_path else None),
            offline_mode=offline_mode
        )
        logger.info(f"[SERVICE] Created new claim session {claim_id} ({name})")
        return claim

    def save_uploaded_file(
        self,
        claim_id: str,
        filename: str,
        file_bytes: bytes
    ) -> str:
        """Store uploaded file into isolated claim directory and return absolute path."""
        claim_dir = self.upload_dir / claim_id
        claim_dir.mkdir(parents=True, exist_ok=True)
        dest_path = claim_dir / filename
        dest_path.write_bytes(file_bytes)
        return str(dest_path)

    def create_demo_session(
        self,
        demo_type: Optional[str] = None,
        preset: Optional[str] = None,
        offline_mode: bool = True,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Create a preconfigured demonstration session using repository documents."""
        selected_type = (demo_type or preset or "health").lower()
        claim_id = f"DEMO-{uuid.uuid4().hex[:6].upper()}"

        if selected_type in ("travel", "flight", "baggage"):
            p_src = ROOT_DIR / "policy_B.pdf"
            c_src = ROOT_DIR / "claim_B.pdf"
            session_name = "Demo: Travel Incident Claim (Policy B)"
            goal = "Analyze travel insurance policy and detect missing baggage claim documents."
            claim_type = "travel"
        elif selected_type in ("health", "hospital", "medical"):
            p_src = ROOT_DIR / "policy_A.pdf"
            c_src = ROOT_DIR / "claim_A.pdf"
            session_name = "Demo: Health Hospitalization Claim (Policy A)"
            goal = "Determine claim readiness, validate medical bills, and detect missing discharge summary."
            claim_type = "health"
        else:
            raise ValueError(f"Invalid preset or demo_type: '{selected_type}'. Supported: 'health', 'travel'.")

        # Fallback to sample files if A/B not found
        if not p_src.exists():
            p_src = ROOT_DIR / "sample_policy.pdf"
        if not c_src.exists():
            c_src = ROOT_DIR / "sample_claim.pdf"

        # Copy to claim directory
        claim_dir = self.upload_dir / claim_id
        claim_dir.mkdir(parents=True, exist_ok=True)

        p_dest = claim_dir / p_src.name
        c_dest = claim_dir / c_src.name

        if p_src.exists():
            shutil.copyfile(p_src, p_dest)
        else:
            p_dest.write_text("Dummy Policy Content")

        if c_src.exists():
            shutil.copyfile(c_src, c_dest)
        else:
            c_dest.write_text("Dummy Claim Content")

        return self.create_session(
            goal=goal,
            session_name=session_name,
            claim_type=claim_type,
            policy_file_path=str(p_dest),
            claim_file_path=str(c_dest),
            policy_filename=p_src.name,
            claim_filename=c_src.name,
            offline_mode=offline_mode
        )

    create_demo_claim = create_demo_session


    def run_agent(
        self,
        claim_id: str,
        max_pages: Optional[int] = None,
        offline_mode: Optional[bool] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Execute the InsureMate Agent autonomously on the specified claim session,
        recording all intermediate steps, tool executions, and the final verdict in the database.
        """
        claim = self.db.get_claim(claim_id)
        if not claim:
            raise ValueError(f"Claim session '{claim_id}' not found.")

        if not self.acquire_claim_lock(claim_id):
            logger.warning(f"[SERVICE] Duplicate execution blocked: Claim {claim_id} is already in progress.")
            history = self.db.get_claim_full_history(claim_id) or {}
            history["status"] = "in_progress"
            history["is_running"] = True
            history["message"] = f"Claim {claim_id} is already running."
            return history

        self.db.update_claim_status(claim_id, ClaimStatus.IN_PROGRESS.value)
        logger.info(f"[SERVICE] Launching InsureMate Agent for claim {claim_id}")

        # Assemble documents list including all files in claim upload folder
        docs: List[str] = []
        if claim.get("policy_path") and Path(claim["policy_path"]).exists():
            docs.append(claim["policy_path"])
        if claim.get("claim_path") and Path(claim["claim_path"]).exists():
            docs.append(claim["claim_path"])

        # Gather any additional uploaded claim documents
        claim_dir = self.upload_dir / claim_id
        if claim_dir.exists():
            for f in sorted(claim_dir.iterdir()):
                if f.is_file() and f.suffix.lower() == ".pdf":
                    f_str = str(f)
                    if f_str not in docs:
                        docs.append(f_str)

        effective_offline = offline_mode if offline_mode is not None else claim.get("offline_mode", False)

        # Instantiate agent
        agent = InsureMateAgent(offline_mode=effective_offline)

        # Initial ClaimState with claim_id preserved
        init_state = ClaimState(
            claim_id=claim_id,
            goal=claim.get("goal") or "Determine claim readiness.",
            documents=docs
        )

        try:
            # Autonomous execution
            final_state = agent.run(
                documents=docs,
                goal=claim.get("goal"),
                state=init_state,
                max_pages=max_pages
            )

            # Record all tool history into DB
            for idx, entry in enumerate(final_state.tool_history):
                self.db.record_tool_execution(
                    claim_id=claim_id,
                    tool_name=entry.get("tool_name", "unknown_tool"),
                    step_index=idx + 1,
                    success=(entry.get("status") in ("success", "PASS", "ok")),
                    duration_ms=0.0,
                    input_data=entry.get("inputs_summary"),
                    output_data=entry.get("summary"),
                    error_data=entry.get("error")
                )

            # Record final state snapshot
            self.db.record_state_snapshot(
                claim_id=claim_id,
                step_name="completed",
                status=final_state.final_status or "UNKNOWN",
                state_dict=final_state.to_dict()
            )

            # Save synthesized report
            report = final_state.final_report or {
                "claim_id": claim_id,
                "status": final_state.final_status or "UNKNOWN",
                "verdict": final_state.final_status or "UNKNOWN",
                "decision_summary": "Agent workflow finished.",
                "is_ready": (final_state.final_status == ClaimStatus.CLAIM_READY_FOR_SUBMISSION.value)
            }
            if "verdict" not in report:
                report["verdict"] = final_state.final_status or "UNKNOWN"

            self.db.save_final_report(claim_id, report)
            self.db.update_claim_status(claim_id, "completed")

            logger.info(f"[SERVICE] Agent finished claim {claim_id} with verdict: {final_state.final_status}")
            history = self.db.get_claim_full_history(claim_id) or {}
            history["success"] = True
            history["status"] = "completed"
            history["final_report"] = report
            return history

        except Exception as e:
            logger.error(f"[SERVICE] Error executing agent for claim {claim_id}: {e}")
            self.db.update_claim_status(claim_id, ClaimStatus.FAILED.value)
            self.db.record_state_snapshot(
                claim_id=claim_id,
                step_name="failed",
                status=ClaimStatus.FAILED.value,
                state_dict={"error": str(e)}
            )
            raise e
        finally:
            self.release_claim_lock(claim_id)

    run_claim = run_agent

    def get_claim(self, claim_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve full claim history, trace, and final report."""
        return self.db.get_claim_full_history(claim_id)

    def list_claims(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """List past claim sessions from database memory."""
        return self.db.list_claims(limit=limit, offset=offset)

    def delete_claim(self, claim_id: str) -> bool:
        """Delete claim record and associated files."""
        # Cleanup files
        claim_dir = self.upload_dir / claim_id
        if claim_dir.exists():
            shutil.rmtree(claim_dir, ignore_errors=True)
        return self.db.delete_claim(claim_id)

