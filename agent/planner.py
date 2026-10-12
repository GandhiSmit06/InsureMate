"""agent/planner.py
Advisory Planning Engine for the InsureMate Agent.
Provides goal decomposition, task analysis, and adaptive replanning.
The plan serves as advisory context for the LLM decision controller and does NOT
prescribe a mandatory or universal sequence of execution.
"""

from dataclasses import dataclass, field, asdict
import json
from typing import Any, Dict, List, Optional

from agent.state import ClaimState
from services.missing_document.ollama_client import OllamaClient
from utils.logger import logger


@dataclass
class PlanStep:
    step: int
    action: str
    reason: str
    status: str = "pending"  # "pending", "in_progress", "completed", "skipped", "abandoned", "failed"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ClaimPlan:
    """
    Advisory goal decomposition.
    Contains hypotheses, suggested candidate actions, and working steps.
    Non-binding: Agent runtime adapts dynamically at each turn.
    """
    goal: str
    hypotheses: List[str] = field(default_factory=list)
    suggested_actions: List[str] = field(default_factory=list)
    steps: List[PlanStep] = field(default_factory=list)
    status: str = "active"  # "active", "completed", "abandoned"
    abandoned: bool = False
    reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "hypotheses": self.hypotheses,
            "suggested_actions": self.suggested_actions,
            "steps": [s.to_dict() for s in self.steps],
            "status": self.status,
            "abandoned": self.abandoned,
            "reasoning": self.reasoning,
        }

    def get_step(self, action: str) -> Optional[PlanStep]:
        for s in self.steps:
            if s.action == action:
                return s
        return None

    def mark_status(self, action: str, status: str) -> None:
        step = self.get_step(action)
        if step:
            step.status = status

    def abandon_plan(self, reason: str) -> None:
        self.abandoned = True
        self.status = "abandoned"
        self.reasoning = reason
        for s in self.steps:
            if s.status == "pending":
                s.status = "abandoned"


class InsureMatePlanner:
    """
    Agent Planning Engine:
    Decomposes user objectives into open questions and advisory suggested actions.
    Supports dynamic adaptation and abandonment when new observations arrive.
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
        Generate advisory plan for the claim goal.
        """
        logger.info(f"[PLANNER] Generating advisory plan for goal: '{goal}' ({len(documents)} document(s))")

        # Try LLM plan creation if client is available
        if self.llm_client and self.llm_client.is_available():
            try:
                llm_plan = self._generate_plan_via_llm(goal, documents)
                if llm_plan and len(llm_plan.steps) >= 1:
                    return self._synchronize_with_state(llm_plan, state)
            except Exception as e:
                logger.warning(f"[PLANNER] LLM planner failed: {e}. Using goal decomposition.")

        # Advisory open plan without universal hardcoded pipeline
        plan = self._create_advisory_decomposition(goal, documents)
        return self._synchronize_with_state(plan, state)

    def update_plan(self, plan: ClaimPlan, state: ClaimState) -> ClaimPlan:
        """
        Dynamically update plan steps, hypotheses, and status based on latest observations.
        Can mark steps as completed, skipped, or abandoned.
        """
        # Synchronize step statuses from state
        for step in plan.steps:
            if step.action in state.completed_steps:
                step.status = "completed"
            elif any(step.action in err for err in state.errors):
                step.status = "failed"

        # Adaptive replanning: If critical failure observed, abandon obsolete steps
        if state.errors and not state.extracted_data and state.documents:
            plan.abandon_plan("Document extraction failed. Downstream analysis abandoned.")
            return plan

        if state.validation_result and state.validation_result.get("valid_documents", 0) == 0 and state.validation_result.get("total_documents", 0) > 0:
            for step in plan.steps:
                if step.action in ("validity_checker", "missing_document_detector") and step.status == "pending":
                    step.status = "skipped"

        return plan

    def _create_advisory_decomposition(self, goal: str, documents: List[str]) -> ClaimPlan:
        """
        Create non-binding advisory decomposition stating key questions for this goal.
        Does NOT prescribe any fixed sequence of tools.
        """
        doc_names = [d.split("/")[-1] for d in documents] if documents else ["pre-loaded data"]
        
        # Advisory steps: purely illustrative starting hypothesis
        steps = [
            PlanStep(
                step=1,
                action="document_extraction",
                reason="Extract structured document entities and text if unextracted files exist.",
                status="pending"
            )
        ]

        return ClaimPlan(
            goal=goal,
            hypotheses=[
                f"Verify submitted documents against goal: '{goal}'",
                f"Documents available for inspection: {doc_names}"
            ],
            suggested_actions=["document_extraction"],
            steps=steps,
            status="active"
        )

    def _generate_plan_via_llm(self, goal: str, documents: List[str]) -> Optional[ClaimPlan]:
        """Prompt LLM to analyze the goal and suggest advisory steps."""
        doc_names = [d.split("/")[-1] for d in documents] if documents else ["pre-loaded claim files"]
        prompt = (
            f"You are the InsureMate Planning Agent. Create an advisory plan tailored specifically to the goal:\n"
            f"Goal: {goal}\n"
            f"Documents: {doc_names}\n\n"
            f"Available tool capabilities: document_extraction, document_validation, validity_checker, "
            f"missing_document_detector, policy_clause_search, cross_document_consistency_check, claim_preparation.\n"
            f"Only suggest tools necessary to achieve this specific goal.\n"
            f"Output strictly valid JSON with this format:\n"
            f"{{\n"
            f'  "goal": "{goal}",\n'
            f'  "hypotheses": ["Key question 1", "Key question 2"],\n'
            f'  "steps": [\n'
            f'    {{"step": 1, "action": "...", "reason": "...", "status": "pending"}}\n'
            f"  ]\n"
            f"}}"
        )

        response_text = self.llm_client.chat(
            messages=[
                {"role": "system", "content": "You are a professional insurance workflow planner. Respond only with JSON."},
                {"role": "user", "content": prompt}
            ],
            format_type="json"
        )

        cleaned = response_text.strip()
        if "```" in cleaned:
            import re
            m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
            if m:
                cleaned = m.group(1).strip()

        data = json.loads(cleaned)
        steps: List[PlanStep] = []
        for idx, item in enumerate(data.get("steps", []), start=1):
            steps.append(PlanStep(
                step=item.get("step", idx),
                action=item.get("action", f"step_{idx}"),
                reason=item.get("reason", "Execute step"),
                status=item.get("status", "pending")
            ))

        return ClaimPlan(
            goal=data.get("goal", goal),
            hypotheses=data.get("hypotheses", []),
            steps=steps,
            status="active"
        )

    def _synchronize_with_state(self, plan: ClaimPlan, state: Optional[ClaimState]) -> ClaimPlan:
        """Mark steps that are already satisfied if state is provided."""
        if not state:
            return plan
        return self.update_plan(plan, state)
