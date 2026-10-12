"""agent/decision.py
Dynamic Decision-Making Engine for the InsureMate Agent.
Evaluates the task goal, current state, tool descriptions, and previous observations
to independently determine the next tool to invoke, with what arguments, or whether to terminate.
"""

from dataclasses import dataclass, field
import json
import re
from typing import Any, Dict, List, Optional

from agent.state import ClaimState, ClaimStatus
from services.missing_document.ollama_client import OllamaClient
from utils.logger import logger


@dataclass
class AgentDecision:
    """Represents a dynamic decision made by the InsureMate Agent."""
    action: str  # Tool name or "claim_preparation", "abort", "complete"
    reason: str  # Concise human-readable explanation
    decision_type: str = "TOOL_CALL"  # "TOOL_CALL", "PREPARE_CLAIM", "TERMINATE"
    action_input: Dict[str, Any] = field(default_factory=dict)
    thought: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "decision_type": self.decision_type,
            "action_input": self.action_input,
            "thought": self.thought,
        }


class InsureMateDecisionEngine:
    """
    Evaluates intermediate state, user goal, and observations to dynamically
    select the most appropriate next action without following any hardcoded sequence.
    """

    def __init__(self, llm_client: Optional[OllamaClient] = None):
        self.llm_client = llm_client

    def decide_next_action(
        self,
        state: ClaimState,
        tool_registry: Optional[Any] = None
    ) -> AgentDecision:
        """
        Main decision-making entry point.
        Evaluates task objective, observed evidence, and available tools.
        """
        # 1. Try LLM decision if available
        if self.llm_client and self.llm_client.is_available():
            try:
                llm_decision = self._decide_via_llm(state, tool_registry)
                if self._validate_decision(llm_decision, state, tool_registry):
                    logger.info(f"LLM Decision selected: {llm_decision.action} ({llm_decision.reason})")
                    return llm_decision
            except Exception as e:
                logger.warning(f"LLM decision engine failed: {e}. Falling back to goal-directed evaluation.")

        # 2. Dynamic goal-directed evaluation (works offline and for deterministic test environments)
        return self._evaluate_grounded_decision(state, tool_registry)

    def _decide_via_llm(
        self,
        state: ClaimState,
        tool_registry: Optional[Any] = None
    ) -> AgentDecision:
        """Query LLM to reason about the goal, context, and previous observations."""
        # Build available tool summaries
        tools_info: List[Dict[str, Any]] = []
        if tool_registry and hasattr(tool_registry, "list_tools"):
            tools_info = tool_registry.list_tools()
        else:
            tools_info = [
                {"name": "document_extraction", "description": "Extracts text, entities, classifications from PDF/image files."},
                {"name": "document_validation", "description": "Validates mandatory fields on extracted records."},
                {"name": "validity_checker", "description": "Checks bill dates against active policy duration."},
                {"name": "missing_document_detector", "description": "Infers required documents from policy and detects missing evidence."},
                {"name": "policy_clause_search", "description": "Searches policy clauses, exclusions, waiting periods, room rent, and limits."},
                {"name": "cross_document_consistency_check", "description": "Cross-checks patient names, hospital facilities, and amounts across documents."},
                {"name": "claim_preparation", "description": "Synthesizes final claim readiness package and actionable checklist."},
            ]

        # Recent tool observations
        recent_history = []
        for entry in state.tool_history[-4:]:
            recent_history.append({
                "tool": entry.get("tool_name"),
                "status": entry.get("status"),
                "summary": entry.get("summary"),
                "inputs": entry.get("inputs_summary"),
            })

        extracted_summary = []
        for doc in state.extracted_data:
            extracted_summary.append({
                "page": doc.get("page_number"),
                "type": doc.get("document_type"),
                "title": doc.get("document_title"),
                "dates": f"{doc.get('policy_start_date')}-{doc.get('policy_end_date')}" if doc.get("policy_start_date") else doc.get("document_date"),
                "patient": doc.get("patient_name") or doc.get("policy_holder_name"),
            })

        context_payload = {
            "user_goal": state.goal,
            "uploaded_documents": state.documents,
            "total_extracted_pages": len(state.extracted_data),
            "extracted_pages_summary": extracted_summary,
            "has_validation": state.validation_result is not None,
            "validation_summary": state.validation_result.get("summary") if state.validation_result else None,
            "has_validity": state.validity_result is not None,
            "validity_summary": state.validity_result.get("summary") if state.validity_result else None,
            "has_missing_docs": state.missing_documents is not None,
            "missing_docs_summary": state.missing_documents.get("summary") if state.missing_documents else None,
            "recent_tool_observations": recent_history,
            "completed_steps": state.completed_steps,
        }

        system_prompt = (
            "You are InsureMate's autonomous AI Agent Orchestrator. "
            "Your objective is to independently decide the NEXT action to satisfy the user's goal. "
            "You are NOT bound to any static pipeline or fixed sequence. "
            "Assess what is known, what is missing, and what action is needed. "
            "When the user's goal has been achieved, select action 'complete'. "
            "If the task cannot progress due to unreadable files or missing inputs, select 'abort'.\n\n"
            "Return strictly valid JSON with:\n"
            "{\n"
            '  "thought": "Reasoning about current state and what is needed next",\n'
            '  "action": "<tool_name or complete or abort>",\n'
            '  "action_input": {"param_name": "param_value"},\n'
            '  "reason": "Concise 1-sentence explanation of why this action was chosen",\n'
            '  "decision_type": "TOOL_CALL" or "TERMINATE"\n'
            "}"
        )

        user_prompt = (
            f"GOAL:\n{state.goal}\n\n"
            f"AVAILABLE TOOLS:\n{json.dumps(tools_info, indent=2)}\n\n"
            f"CURRENT CONTEXT & OBSERVATIONS:\n{json.dumps(context_payload, indent=2)}\n\n"
            "Decide the next action:"
        )

        resp = self.llm_client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            format_type="json"
        )

        # Parse JSON response
        data = {}
        try:
            cleaned = resp.strip()
            if "```" in cleaned:
                m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
                if m:
                    cleaned = m.group(1).strip()
            data = json.loads(cleaned)
        except Exception:
            m = re.search(r"\{[\s\S]*\}", resp)
            if m:
                data = json.loads(m.group(0))

        action = str(data.get("action", "")).strip()
        reason = str(data.get("reason", "Autonomous step selected.")).strip()
        thought = str(data.get("thought", "")).strip()
        action_input = data.get("action_input") if isinstance(data.get("action_input"), dict) else {}
        decision_type = data.get("decision_type", "TERMINATE" if action in ("complete", "abort", "finish") else "TOOL_CALL")

        return AgentDecision(
            action=action,
            reason=reason,
            decision_type=decision_type,
            action_input=action_input,
            thought=thought
        )

    def _validate_decision(
        self,
        decision: AgentDecision,
        state: ClaimState,
        tool_registry: Optional[Any] = None
    ) -> bool:
        """Validate that the LLM's dynamic decision is sensible and avoids infinite loops."""
        if not decision.action:
            return False

        # Termination actions are always valid
        if decision.action in ("complete", "finish", "abort"):
            return True

        # Check tool registration
        if tool_registry and hasattr(tool_registry, "has"):
            if not tool_registry.has(decision.action):
                return False

        # Prevent calling tools requiring documents if no documents exist at all
        if decision.action != "document_extraction" and not state.extracted_data and not state.documents:
            return False

        # Prevent infinite repetitions: same tool called 3 or more times consecutively
        history_actions = [h.get("tool_name") for h in state.tool_history[-3:]]
        if len(history_actions) >= 3 and all(a == decision.action for a in history_actions):
            logger.warning(f"[AGENT LOOP DETECTED] Tool '{decision.action}' called 3 times consecutively without progress.")
            return False

        return True

    def _evaluate_grounded_decision(
        self,
        state: ClaimState,
        tool_registry: Optional[Any] = None
    ) -> AgentDecision:
        """
        Dynamically determine the next action grounded in the specific goal and state observations.
        Does NOT impose a universal sequential chain.
        """
        # 1. Terminal / Completed check
        if state.final_status is not None:
            return AgentDecision(
                action="complete",
                reason="Required analysis is complete.",
                decision_type="TERMINATE"
            )

        goal_lower = state.goal.lower()

        # 2. Check if documents need extraction
        if not state.extracted_data:
            if any("document_extraction" in err for err in state.errors) or state.retry_counts.get("document_extraction", 0) > 0:
                return AgentDecision(
                    action="abort",
                    reason="Document extraction failed or document is unreadable. Halting workflow due to insufficient information.",
                    decision_type="TERMINATE"
                )
            return AgentDecision(
                action="document_extraction",
                reason="Extracting document entities and pages to inspect evidence.",
                decision_type="TOOL_CALL"
            )

        if len(state.extracted_data) == 0:
            return AgentDecision(
                action="abort",
                reason="Extraction returned zero usable document records. Insufficient information to proceed.",
                decision_type="TERMINATE"
            )

        # ----------------------------------------------------------------------
        # DYNAMIC GOAL-DRIVEN BRANCHING (Non-Sequential)
        # ----------------------------------------------------------------------

        # Goal Pattern A: Policy Clause / Exclusion / Benefit Inquiry
        is_clause_goal = any(kw in goal_lower for kw in [
            "clause", "exclusion", "exclude", "cataract", "waiting period",
            "room rent", "copay", "limit", "benefit", "coverage condition", "is covered"
        ])
        if is_clause_goal and not any(kw in goal_lower for kw in ["readiness", "full audit", "prepare claim"]):
            if "policy_clause_search" not in state.completed_steps:
                return AgentDecision(
                    action="policy_clause_search",
                    reason=f"Searching policy clauses specifically addressing: '{state.goal}'.",
                    decision_type="TOOL_CALL",
                    action_input={"query": state.goal}
                )
            return AgentDecision(
                action="complete",
                reason="Policy clause inquiry satisfied from extracted policy documentation.",
                decision_type="TERMINATE"
            )

        # Goal Pattern B: Date Validity / Coverage Window Inquiry
        is_date_goal = any(kw in goal_lower for kw in ["date validity", "coverage window", "check date", "expired", "active duration"])
        if is_date_goal and not any(kw in goal_lower for kw in ["readiness", "full audit", "prepare claim"]):
            if "validity_checker" not in state.completed_steps:
                return AgentDecision(
                    action="validity_checker",
                    reason="Verifying claim document and invoice dates against policy active coverage window.",
                    decision_type="TOOL_CALL"
                )
            return AgentDecision(
                action="complete",
                reason="Coverage window date audit satisfied.",
                decision_type="TERMINATE"
            )

        # Goal Pattern C: Cross-Document Consistency Inquiry
        is_consistency_goal = any(kw in goal_lower for kw in ["consistent", "consistency", "contradiction", "discrepancy", "match"])
        if is_consistency_goal and not any(kw in goal_lower for kw in ["readiness", "full audit", "prepare claim"]):
            if "cross_document_consistency_check" not in state.completed_steps:
                return AgentDecision(
                    action="cross_document_consistency_check",
                    reason="Cross-checking patient identities, facilities, and amounts across submitted documents.",
                    decision_type="TOOL_CALL"
                )
            return AgentDecision(
                action="complete",
                reason="Cross-document consistency assessment completed.",
                decision_type="TERMINATE"
            )

        # Goal Pattern D: Missing Document Audit Only
        is_missing_doc_goal = any(kw in goal_lower for kw in ["missing document", "missing evidence", "checklist", "what is missing"])
        if is_missing_doc_goal and not any(kw in goal_lower for kw in ["readiness", "full audit", "prepare claim"]):
            if "missing_document_detector" not in state.completed_steps:
                return AgentDecision(
                    action="missing_document_detector",
                    reason="Auditing policy requirements against submitted claim evidence.",
                    decision_type="TOOL_CALL"
                )
            return AgentDecision(
                action="complete",
                reason="Missing evidence audit completed.",
                decision_type="TERMINATE"
            )

        # ----------------------------------------------------------------------
        # Goal Pattern E: Full Claim Readiness Assessment (Result-Driven Adaptation)
        # ----------------------------------------------------------------------

        # Step 1: Validate field completeness if not done
        if state.validation_result is None:
            return AgentDecision(
                action="document_validation",
                reason="Validating required field completeness for submitted documents.",
                decision_type="TOOL_CALL"
            )

        val_total = state.validation_result.get("total_documents", 0)
        val_valid_count = state.validation_result.get("valid_documents", 0)

        # Adaptive branch: If ALL documents are invalid / unreadable
        if val_valid_count == 0 and val_total > 0 and state.validity_result is None:
            return AgentDecision(
                action="claim_preparation",
                reason="Submitted documents failed validation with missing mandatory fields. Proceeding directly to claim preparation to record deficiencies.",
                decision_type="PREPARE_CLAIM"
            )

        # Step 2: Check date validity if policy exists and not yet evaluated
        policy_docs = [d for d in state.extracted_data if d.get("document_type") == "insurance_policy"]
        if state.validity_result is None:
            if not policy_docs:
                # If no policy document is attached, check missing evidence first
                if state.missing_documents is None:
                    return AgentDecision(
                        action="missing_document_detector",
                        reason="No policy document found. Detecting missing evidence requirements.",
                        decision_type="TOOL_CALL"
                    )
            return AgentDecision(
                action="validity_checker",
                reason="Auditing policy coverage duration against submitted documentation.",
                decision_type="TOOL_CALL"
            )

        # Step 3: Check missing evidence against policy requirements
        if state.missing_documents is None:
            is_valid_dates = state.validity_result.get("valid", True) if state.validity_result else True
            reason = (
                "Validity check identified date/coverage discrepancies. Evaluating policy requirements against submitted claim documents."
                if not is_valid_dates
                else "Evaluating policy requirements against submitted claim documents."
            )
            return AgentDecision(
                action="missing_document_detector",
                reason=reason,
                decision_type="TOOL_CALL"
            )

        # Step 4: Cross-document consistency check if multiple documents exist and not yet checked
        if len(state.extracted_data) > 1 and "cross_document_consistency_check" not in state.completed_steps:
            return AgentDecision(
                action="cross_document_consistency_check",
                reason="Cross-checking patient identity, facilities, and amounts across all submitted documents.",
                decision_type="TOOL_CALL"
            )

        # Step 5: Synthesize claim readiness package
        if state.final_status is None:
            return AgentDecision(
                action="claim_preparation",
                reason="All required evidence assessed. Synthesizing claim readiness package.",
                decision_type="PREPARE_CLAIM"
            )

        return AgentDecision(
            action="complete",
            reason="All claim processing steps completed.",
            decision_type="TERMINATE"
        )
