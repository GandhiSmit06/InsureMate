"""services/database/db.py
InsureMate Phase 7 Database & Claim Memory Layer.
Provides SQLite-backed persistence for:
- Claim sessions & metadata
- Multi-step tool execution audit history
- Intermediate ClaimState observation snapshots
- Final claim readiness reports & verdicts
"""

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = ROOT_DIR / "insuremate.db"


class ClaimDatabase:
    """Thread-safe SQLite manager for InsureMate Claim Memory & Execution History."""

    _local = threading.local()

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create thread-local SQLite connection with dictionary-like row factory."""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_db(self):
        """Initialize database tables and indices if not already present."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._get_connection()
        try:
            with conn:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS claims (
                        claim_id TEXT PRIMARY KEY,
                        session_name TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        status TEXT NOT NULL,
                        claim_type TEXT,
                        goal TEXT,
                        policy_path TEXT,
                        claim_path TEXT,
                        policy_filename TEXT,
                        claim_filename TEXT,
                        claim_filenames TEXT,
                        offline_mode INTEGER DEFAULT 0
                    );

                    CREATE TABLE IF NOT EXISTS tool_executions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        claim_id TEXT NOT NULL,
                        tool_name TEXT NOT NULL,
                        step_index INTEGER,
                        success INTEGER NOT NULL,
                        duration_ms REAL DEFAULT 0.0,
                        input_data TEXT,
                        output_data TEXT,
                        error_data TEXT,
                        timestamp TEXT NOT NULL,
                        FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS claim_state_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        claim_id TEXT NOT NULL,
                        step_name TEXT NOT NULL,
                        status TEXT NOT NULL,
                        state_json TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS final_reports (
                        claim_id TEXT PRIMARY KEY,
                        verdict TEXT NOT NULL,
                        confidence_score INTEGER,
                        decision_summary TEXT,
                        missing_count INTEGER DEFAULT 0,
                        validity_pass INTEGER DEFAULT 1,
                        report_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS idx_tool_exec_claim ON tool_executions(claim_id);
                    CREATE INDEX IF NOT EXISTS idx_state_snap_claim ON claim_state_snapshots(claim_id);
                    CREATE INDEX IF NOT EXISTS idx_claims_created ON claims(created_at DESC);
                """)

                # Automated column migrations for existing databases
                cur = conn.execute("PRAGMA table_info(claims)")
                claim_cols = {row["name"] for row in cur.fetchall()}
                if "claim_type" not in claim_cols:
                    conn.execute("ALTER TABLE claims ADD COLUMN claim_type TEXT")
                if "claim_filenames" not in claim_cols:
                    conn.execute("ALTER TABLE claims ADD COLUMN claim_filenames TEXT")

                cur = conn.execute("PRAGMA table_info(final_reports)")
                report_cols = {row["name"] for row in cur.fetchall()}
                if "confidence_score" not in report_cols:
                    conn.execute("ALTER TABLE final_reports ADD COLUMN confidence_score INTEGER")
        finally:
            conn.close()


    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_claim(
        self,
        claim_id: str,
        goal: str = "Determine claim readiness.",
        session_name: Optional[str] = None,
        claim_type: Optional[str] = "general",
        policy_path: Optional[str] = None,
        claim_path: Optional[str] = None,
        policy_filename: Optional[str] = None,
        claim_filename: Optional[str] = None,
        claim_filenames: Optional[Union[str, List[str]]] = None,
        offline_mode: bool = False,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Create and store a new claim session record."""
        now = self._now_iso()
        name = session_name or f"Claim Session {claim_id}"
        conn = self._get_connection()

        if isinstance(claim_filenames, list):
            stored_claim_filenames = json.dumps(claim_filenames)
            if not claim_filename and claim_filenames:
                claim_filename = claim_filenames[0]
        elif isinstance(claim_filenames, str):
            stored_claim_filenames = json.dumps([claim_filenames])
            if not claim_filename:
                claim_filename = claim_filenames
        else:
            stored_claim_filenames = json.dumps([claim_filename] if claim_filename else [])

        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO claims (
                        claim_id, session_name, created_at, updated_at,
                        status, claim_type, goal, policy_path, claim_path,
                        policy_filename, claim_filename, claim_filenames, offline_mode
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        claim_id, name, now, now,
                        "pending", claim_type or "general", goal, policy_path, claim_path,
                        policy_filename, claim_filename, stored_claim_filenames, 1 if offline_mode else 0
                    )
                )
            return self.get_claim(claim_id) or {}
        finally:
            conn.close()

    def get_claim(self, claim_id: str) -> Optional[Dict[str, Any]]:
        """Fetch basic claim record by claim_id."""
        conn = self._get_connection()
        try:
            cur = conn.execute("SELECT * FROM claims WHERE claim_id = ?", (claim_id,))
            row = cur.fetchone()
            if not row:
                return None
            res = dict(row)
            res["offline_mode"] = bool(res.get("offline_mode", 0))
            if res.get("claim_filenames"):
                try:
                    res["claim_filenames"] = json.loads(res["claim_filenames"])
                except Exception:
                    res["claim_filenames"] = [res["claim_filenames"]]
            else:
                res["claim_filenames"] = [res["claim_filename"]] if res.get("claim_filename") else []
            return res
        finally:
            conn.close()

    def update_claim_status(self, claim_id: str, status: str) -> bool:
        """Update claim lifecycle status and timestamp."""
        conn = self._get_connection()
        try:
            with conn:
                cur = conn.execute(
                    "UPDATE claims SET status = ?, updated_at = ? WHERE claim_id = ?",
                    (status, self._now_iso(), claim_id)
                )
                return cur.rowcount > 0
        finally:
            conn.close()

    def record_tool_execution(
        self,
        claim_id: str,
        tool_name: Union[str, Dict[str, Any]],
        step_index: Optional[int] = None,
        success: bool = True,
        duration_ms: float = 0.0,
        input_data: Optional[Any] = None,
        output_data: Optional[Any] = None,
        error_data: Optional[Any] = None
    ) -> int:
        """Persist a single tool execution envelope or parameter dictionary in audit history."""
        # Handle dict envelope passed as tool_name
        if isinstance(tool_name, dict):
            env = tool_name
            actual_tool_name = env.get("tool_name", "unknown_tool")
            step_index = env.get("step_index", step_index)
            if "status" in env:
                success = (env.get("status") in ("success", "PASS", "ok"))
            else:
                success = env.get("success", True)
            duration_ms = env.get("execution_time_ms", env.get("duration_ms", 0.0))
            input_data = env.get("parameters", env.get("inputs_summary", env.get("input_data")))
            output_data = env.get("output", env.get("summary", env.get("output_data")))
            error_data = env.get("error_message", env.get("error", env.get("error_data")))
        else:
            actual_tool_name = tool_name

        conn = self._get_connection()
        try:
            with conn:
                cur = conn.execute(
                    """
                    INSERT INTO tool_executions (
                        claim_id, tool_name, step_index, success, duration_ms,
                        input_data, output_data, error_data, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        claim_id,
                        actual_tool_name,
                        step_index,
                        1 if success else 0,
                        duration_ms,
                        json.dumps(input_data) if input_data is not None else None,
                        json.dumps(output_data) if output_data is not None else None,
                        json.dumps(error_data) if error_data is not None else None,
                        self._now_iso()
                    )
                )
                return cur.lastrowid or 0
        finally:
            conn.close()

    def record_state_snapshot(
        self,
        claim_id: str,
        step_name: Optional[Any] = None,
        status: Optional[Any] = "SNAPSHOT",
        state_dict: Optional[Dict[str, Any]] = None,
        step_number: Optional[int] = None,
        state_data: Optional[Dict[str, Any]] = None
    ) -> int:
        """Persist full ClaimState intermediate snapshot."""
        if isinstance(status, dict) and state_dict is None and state_data is None:
            s_data = status
            s_status = "SNAPSHOT"
        else:
            s_data = state_dict if state_dict is not None else (state_data or {})
            s_status = status if isinstance(status, str) else "SNAPSHOT"

        if isinstance(step_name, int):
            s_name = f"step_{step_name}"
        else:
            s_name = str(step_name) if step_name is not None else (f"step_{step_number}" if step_number is not None else "step")

        conn = self._get_connection()
        try:
            with conn:
                cur = conn.execute(
                    """
                    INSERT INTO claim_state_snapshots (
                        claim_id, step_name, status, state_json, timestamp
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (claim_id, s_name, s_status, json.dumps(s_data), self._now_iso())
                )
                return cur.lastrowid or 0
        finally:
            conn.close()


    save_state_snapshot = record_state_snapshot

    def get_state_snapshots(self, claim_id: str) -> List[Dict[str, Any]]:
        """Retrieve all state snapshots for a claim."""
        conn = self._get_connection()
        try:
            cur = conn.execute(
                "SELECT * FROM claim_state_snapshots WHERE claim_id = ? ORDER BY id ASC",
                (claim_id,)
            )
            rows = cur.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                if item.get("state_json"):
                    try:
                        item["state_data"] = json.loads(item["state_json"])
                    except Exception:
                        item["state_data"] = {}
                else:
                    item["state_data"] = {}
                # step_number helper
                item["step_number"] = item.get("id")
                results.append(item)
            return results
        finally:
            conn.close()

    def save_final_report(
        self,
        claim_id: str,
        report_dict: Optional[Dict[str, Any]] = None,
        report_data: Optional[Dict[str, Any]] = None,
        verdict: Optional[str] = None,
        confidence_score: Optional[int] = None
    ) -> int:
        """Store synthesized final claim readiness package."""
        data = report_dict if report_dict is not None else (report_data or {})
        eff_verdict = verdict or data.get("status") or data.get("verdict") or "UNKNOWN"
        summary = data.get("decision_summary") or data.get("reasoning", "")
        eff_conf = confidence_score or data.get("confidence_score")

        missing_count = 0
        if "missing_documents" in data:
            missing_count = len(data.get("missing_documents", []))
        elif "missing_documents_analysis" in data:
            missing_count = len(data["missing_documents_analysis"].get("missing_documents", []))

        validity_pass = True
        if "validity_check" in data:
            validity_pass = data["validity_check"].get("valid", True)

        now = self._now_iso()
        conn = self._get_connection()
        try:
            with conn:
                cur = conn.execute(
                    """
                    INSERT OR REPLACE INTO final_reports (
                        claim_id, verdict, confidence_score, decision_summary, missing_count,
                        validity_pass, report_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        claim_id,
                        eff_verdict,
                        eff_conf,
                        summary,
                        missing_count,
                        1 if validity_pass else 0,
                        json.dumps(data),
                        now
                    )
                )
                conn.execute(
                    "UPDATE claims SET status = ?, updated_at = ? WHERE claim_id = ?",
                    (eff_verdict, now, claim_id)
                )
                return cur.lastrowid or 1
        finally:
            conn.close()

    def get_tool_executions(self, claim_id: str) -> List[Dict[str, Any]]:
        """Retrieve chronological tool execution log for a claim."""
        conn = self._get_connection()
        try:
            cur = conn.execute(
                "SELECT * FROM tool_executions WHERE claim_id = ? ORDER BY id ASC",
                (claim_id,)
            )
            rows = cur.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                item["success"] = bool(item.get("success", 0))
                for key in ("input_data", "output_data", "error_data"):
                    if item.get(key):
                        try:
                            item[key] = json.loads(item[key])
                        except Exception:
                            pass
                # Provide output alias for ease of consumption
                item["output"] = item.get("output_data")
                item["parameters"] = item.get("input_data")
                results.append(item)
            return results
        finally:
            conn.close()

    def get_final_report(self, claim_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve stored final report and metadata."""
        conn = self._get_connection()
        try:
            cur = conn.execute("SELECT * FROM final_reports WHERE claim_id = ?", (claim_id,))
            row = cur.fetchone()
            if not row:
                return None
            res = dict(row)
            res["validity_pass"] = bool(res.get("validity_pass", 1))
            try:
                res["report"] = json.loads(res["report_json"])
            except Exception:
                res["report"] = {}
            res["report_data"] = res["report"]
            return res
        finally:
            conn.close()


    def get_claim_full_history(self, claim_id: str) -> Optional[Dict[str, Any]]:
        """Complete unified memory package for a claim session."""
        claim = self.get_claim(claim_id)
        if not claim:
            return None

        tools = self.get_tool_executions(claim_id)
        report = self.get_final_report(claim_id)

        # Get latest state snapshot if any
        conn = self._get_connection()
        latest_state = None
        try:
            cur = conn.execute(
                "SELECT state_json, timestamp FROM claim_state_snapshots WHERE claim_id = ? ORDER BY id DESC LIMIT 1",
                (claim_id,)
            )
            state_row = cur.fetchone()
            if state_row and state_row["state_json"]:
                try:
                    latest_state = json.loads(state_row["state_json"])
                except Exception:
                    latest_state = None
        finally:
            conn.close()

        return {
            "claim": claim,
            "tool_executions": tools,
            "final_report": report["report"] if report else None,
            "verdict": report["verdict"] if report else claim.get("status"),
            "latest_state": latest_state
        }

    def list_claims(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """List past claim sessions sorted by most recent first."""
        conn = self._get_connection()
        try:
            cur = conn.execute(
                """
                SELECT c.*, r.verdict, r.missing_count, r.validity_pass
                FROM claims c
                LEFT JOIN final_reports r ON c.claim_id = r.claim_id
                ORDER BY c.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset)
            )
            rows = cur.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                item["offline_mode"] = bool(item.get("offline_mode", 0))
                if "validity_pass" in item and item["validity_pass"] is not None:
                    item["validity_pass"] = bool(item["validity_pass"])
                results.append(item)
            return results
        finally:
            conn.close()

    def delete_claim(self, claim_id: str) -> bool:
        """Delete claim and all associated cascade records."""
        conn = self._get_connection()
        try:
            with conn:
                cur = conn.execute("DELETE FROM claims WHERE claim_id = ?", (claim_id,))
                return cur.rowcount > 0
        finally:
            conn.close()
