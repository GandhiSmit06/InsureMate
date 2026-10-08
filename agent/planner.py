"""agent/planner.py
Planning stage for InsureMate Agent.
Generates structured, step-by-step workflow plans based on goal, uploaded files, and claim state.
Supports both deterministic rule-grounded planning and optional LLM-assisted plan generation.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import json

from agent.state import ClaimState
from services.missing_document.ollama_client import OllamaClient
from utils.logger import logger


@dataclass
class PlanStep:
    step: int
    action: str
    reason: str
    status: str = "pending"  # "pending", "in_progress", "completed", "skipped", "failed"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ClaimPlan:
    goal: str
    steps: List[PlanStep] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "steps": [s.to_dict() for s in self.steps]
        }

    def get_step(self, action: str) -> Optional[PlanStep]:
        for s in self.steps:
            if s.action == action:
                return s
        return None

    def get_next_pending_step(self) -> Optional[PlanStep]:
        for s in self.steps:
            if s.status == "pending":
                return s
        return None

    def mark_status(self, action: str, status: str) -> None:
        step = self.get_step(action)
        if step:
            step.status = status


class InsureMatePlanner:
    """
    Agent Planning Engine:
    Converts claim goals and session context into an executable structured plan.
    """

    def __init__(self, llm_client: Optional[OllamaClient] = None):
        self.llm_client = llm_client

    def create_initial_plan(
        self,
        goal: str,
        documents: List[str],
        state: Optional[ClaimState] = None
    ) -> ClaimPlan:
        """
        Generate structured execution plan for claim analysis.
        """
        logger.info(f"Generating initial plan for goal: '{goal}' ({len(documents)} document(s))")

        # Try LLM plan creation if client is available and online
        if self.llm_client and self.llm_client.is_available():
            try:
                llm_plan = self._generate_plan_via_llm(goal, documents)
                if llm_plan and len(llm_plan.steps) >= 3:
                    return self._synchronize_with_state(llm_plan, state)
            except Exception as e:
                logger.warning(f"LLM planner failed: {e}. Falling back to deterministic plan.")

        # Deterministic grounded planning
        plan = self._generate_grounded_plan(goal, documents)
        return self._synchronize_with_state(plan, state)

    def update_plan(self, plan: ClaimPlan, state: ClaimState) -> ClaimPlan:
        """
        Dynamically update plan status and steps based on intermediate state.
        """
        # Step 1: document_extraction
        step_ext = plan.get_step("document_extraction")
        if step_ext:
            if state.extracted_data:
                step_ext.status = "completed"
            elif any("document_extraction" in err for err in state.errors):
                step_ext.status = "failed"

        # Step 2: document_validation
        step_val = plan.get_step("document_validation")
        if step_val:
            if state.validation_result:
                step_val.status = "completed"
            elif any("document_validation" in err for err in state.errors):
                step_val.status = "failed"

        # Step 3: validity_checker
        step_chk = plan.get_step("validity_checker")
        if step_chk:
            if state.validity_result:
                step_chk.status = "completed"
            elif any("validity_checker" in err for err in state.errors):
                step_chk.status = "failed"

        # Step 4: missing_document_detector
        step_mis = plan.get_step("missing_document_detector")
        if step_mis:
            if state.missing_documents:
                step_mis.status = "completed"
            elif any("missing_document_detector" in err for err in state.errors):
                step_mis.status = "failed"

        # Step 5: claim_preparation
        step_prep = plan.get_step("claim_preparation")
        if step_prep:
            if state.final_status:
                step_prep.status = "completed"

        return plan

    def _generate_grounded_plan(self, goal: str, documents: List[str]) -> ClaimPlan:
        """Create deterministic, rule-grounded step-by-step workflow plan."""
        steps = [
            PlanStep(
                step=1,
                action="document_extraction",
                reason="Extract structured claim entities, classifications, and policy clauses from uploaded PDF documents using Qwen-VL.",
                status="pending"
            ),
            PlanStep(
                step=2,
                action="document_validation",
                reason="Deterministically validate extracted records against required fields for each document category.",
                status="pending"
            ),
            PlanStep(
                step=3,
                action="validity_checker",
                reason="Deterministically check invoice and incident dates against policy coverage duration and verify patient identity.",
                status="pending"
            ),
            PlanStep(
                step=4,
                action="missing_document_detector",
                reason="Dynamically extract policy document requirements using pretrained LLM and cross-reference submitted evidence to detect missing documents.",
                status="pending"
            ),
            PlanStep(
                step=5,
                action="claim_preparation",
                reason="Synthesize intermediate findings into final claim readiness package, checklist, and decision.",
                status="pending"
            ),
        ]
        return ClaimPlan(goal=goal, steps=steps)

    def _generate_plan_via_llm(self, goal: str, documents: List[str]) -> Optional[ClaimPlan]:
        """Prompt pretrained LLM (Gemma 3) to generate plan."""
        doc_names = [d.split("/")[-1] for d in documents] if documents else ["pre-loaded claim files"]
        prompt = (
            f"You are the InsureMate Planning Agent. Create a plan for the following goal:\n"
            f"Goal: {goal}\n"
            f"Documents: {doc_names}\n\n"
            f"Available actions: document_extraction, document_validation, validity_checker, "
            f"missing_document_detector, claim_preparation.\n"
            f"Output strictly valid JSON with this format:\n"
            f"{{\n"
            f'  "goal": "{goal}",\n'
            f'  "steps": [\n'
            f'    {{"step": 1, "action": "document_extraction", "reason": "...", "status": "pending"}}\n'
            f"  ]\n"
            f"}}"
        )

        response_text = self.llm_client.chat(
            messages=[
                {"role": "system", "content": "You are a professional insurance claim workflow planner. Respond only with JSON."},
                {"role": "user", "content": prompt}
            ],
            format_type="json"
        )

        data = json.loads(response_text)
        steps: List[PlanStep] = []
        for idx, item in enumerate(data.get("steps", []), start=1):
            steps.append(PlanStep(
                step=item.get("step", idx),
                action=item.get("action", f"step_{idx}"),
                reason=item.get("reason", "Execute step"),
                status=item.get("status", "pending")
            ))
        return ClaimPlan(goal=data.get("goal", goal), steps=steps)

    def _synchronize_with_state(self, plan: ClaimPlan, state: Optional[ClaimState]) -> ClaimPlan:
        """Mark steps that are already satisfied if state is provided."""
        if not state:
            return plan
        return self.update_plan(plan, state)
