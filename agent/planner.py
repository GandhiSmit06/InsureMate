"""agent/planner.py
Planning stage for InsureMate Agent.
Generates structured, goal-aware workflow plans based on task objective, uploaded files, and claim state.
Supports both deterministic goal-directed planning and dynamic LLM plan generation with adaptive replanning.
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
    Supports dynamic adaptation when intermediate tool observations arrive.
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
        Generate structured execution plan for claim analysis based on specific goal.
        """
        logger.info(f"Generating initial plan for goal: '{goal}' ({len(documents)} document(s))")

        # Try LLM plan creation if client is available and online
        if self.llm_client and self.llm_client.is_available():
            try:
                llm_plan = self._generate_plan_via_llm(goal, documents)
                if llm_plan and len(llm_plan.steps) >= 1:
                    return self._synchronize_with_state(llm_plan, state)
            except Exception as e:
                logger.warning(f"LLM planner failed: {e}. Falling back to goal-directed plan.")

        # Goal-directed planning
        plan = self._generate_grounded_plan(goal, documents)
        return self._synchronize_with_state(plan, state)

    def update_plan(self, plan: ClaimPlan, state: ClaimState) -> ClaimPlan:
        """
        Dynamically update plan status and steps based on intermediate state and new observations.
        """
        # Step: document_extraction
        step_ext = plan.get_step("document_extraction")
        if step_ext:
            if state.extracted_data:
                step_ext.status = "completed"
            elif any("document_extraction" in err for err in state.errors):
                step_ext.status = "failed"

        # Step: policy_clause_search
        step_clause = plan.get_step("policy_clause_search")
        if step_clause:
            if "policy_clause_search" in state.completed_steps:
                step_clause.status = "completed"

        # Step: cross_document_consistency_check
        step_const = plan.get_step("cross_document_consistency_check")
        if step_const:
            if "cross_document_consistency_check" in state.completed_steps:
                step_const.status = "completed"

        # Step: document_validation
        step_val = plan.get_step("document_validation")
        if step_val:
            if state.validation_result:
                step_val.status = "completed"
                # If validation failed with 0 valid documents, dynamically skip downstream validity checker
                if state.validation_result.get("valid_documents", 0) == 0 and state.validation_result.get("total_documents", 0) > 0:
                    step_chk = plan.get_step("validity_checker")
                    if step_chk and step_chk.status == "pending":
                        step_chk.status = "skipped"
            elif any("document_validation" in err for err in state.errors):
                step_val.status = "failed"

        # Step: validity_checker
        step_chk = plan.get_step("validity_checker")
        if step_chk:
            if state.validity_result:
                step_chk.status = "completed"
            elif any("validity_checker" in err for err in state.errors):
                step_chk.status = "failed"

        # Step: missing_document_detector
        step_mis = plan.get_step("missing_document_detector")
        if step_mis:
            if state.missing_documents:
                step_mis.status = "completed"
            elif any("missing_document_detector" in err for err in state.errors):
                step_mis.status = "failed"

        # Step: claim_preparation
        step_prep = plan.get_step("claim_preparation")
        if step_prep:
            if state.final_status:
                step_prep.status = "completed"

        return plan

    def _generate_grounded_plan(self, goal: str, documents: List[str]) -> ClaimPlan:
        """Create goal-aware step-by-step workflow plan tailored to user intent."""
        goal_lower = goal.lower()

        # Goal A: Clause / Exclusion inquiry
        is_clause_goal = any(kw in goal_lower for kw in [
            "clause", "exclusion", "exclude", "cataract", "waiting period",
            "room rent", "copay", "limit", "benefit", "coverage condition", "is covered"
        ])
        if is_clause_goal and not any(kw in goal_lower for kw in ["readiness", "full audit", "prepare claim"]):
            steps = [
                PlanStep(
                    step=1,
                    action="document_extraction",
                    reason="Extract policy documents and clauses using vision document understanding.",
                    status="pending"
                ),
                PlanStep(
                    step=2,
                    action="policy_clause_search",
                    reason=f"Search policy clauses and terms specifically for: '{goal}'.",
                    status="pending"
                ),
            ]
            return ClaimPlan(goal=goal, steps=steps)

        # Goal B: Date validity inquiry
        is_date_goal = any(kw in goal_lower for kw in ["date validity", "coverage window", "check date", "expired", "active duration"])
        if is_date_goal and not any(kw in goal_lower for kw in ["readiness", "full audit", "prepare claim"]):
            steps = [
                PlanStep(
                    step=1,
                    action="document_extraction",
                    reason="Extract policy duration and document invoice/incident dates.",
                    status="pending"
                ),
                PlanStep(
                    step=2,
                    action="validity_checker",
                    reason="Deterministically verify document dates against policy coverage duration.",
                    status="pending"
                ),
            ]
            return ClaimPlan(goal=goal, steps=steps)

        # Goal C: Cross-document consistency inquiry
        is_consistency_goal = any(kw in goal_lower for kw in ["consistent", "consistency", "contradiction", "discrepancy", "match"])
        if is_consistency_goal and not any(kw in goal_lower for kw in ["readiness", "full audit", "prepare claim"]):
            steps = [
                PlanStep(
                    step=1,
                    action="document_extraction",
                    reason="Extract document entities, patient names, and hospital facilities.",
                    status="pending"
                ),
                PlanStep(
                    step=2,
                    action="cross_document_consistency_check",
                    reason="Cross-check patient identity, facility names, and dates across all documents.",
                    status="pending"
                ),
            ]
            return ClaimPlan(goal=goal, steps=steps)

        # Goal D: Missing document detection only
        is_missing_doc_goal = any(kw in goal_lower for kw in ["missing document", "missing evidence", "checklist", "what is missing"])
        if is_missing_doc_goal and not any(kw in goal_lower for kw in ["readiness", "full audit", "prepare claim"]):
            steps = [
                PlanStep(
                    step=1,
                    action="document_extraction",
                    reason="Extract document classifications and records from uploaded files.",
                    status="pending"
                ),
                PlanStep(
                    step=2,
                    action="missing_document_detector",
                    reason="Dynamically infer required policy documents and audit submitted evidence.",
                    status="pending"
                ),
            ]
            return ClaimPlan(goal=goal, steps=steps)

        # Default Goal E: Full Claim Readiness Assessment
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
        """Prompt pretrained LLM to generate goal-specific plan."""
        doc_names = [d.split("/")[-1] for d in documents] if documents else ["pre-loaded claim files"]
        prompt = (
            f"You are the InsureMate Planning Agent. Create an actionable plan tailored specifically to the goal:\n"
            f"Goal: {goal}\n"
            f"Documents: {doc_names}\n\n"
            f"Available actions: document_extraction, document_validation, validity_checker, "
            f"missing_document_detector, policy_clause_search, cross_document_consistency_check, claim_preparation.\n"
            f"Only include tools necessary to achieve this specific goal.\n"
            f"Output strictly valid JSON with this format:\n"
            f"{{\n"
            f'  "goal": "{goal}",\n'
            f'  "steps": [\n'
            f'    {{"step": 1, "action": "...", "reason": "...", "status": "pending"}}\n'
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
