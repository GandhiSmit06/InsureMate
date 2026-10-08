"""agent/decision.py
Decision-making engine for the InsureMate Agent.
Evaluates current claim state, intermediate observations, and history
to dynamically determine the next tool or action.
"""

from dataclasses import dataclass
import json
from typing import Any, Dict, List, Optional

from agent.state import ClaimState, ClaimStatus
from services.missing_document.ollama_client import OllamaClient
from utils.logger import logger


@dataclass
class AgentDecision:
    """Represents a decision made by the InsureMate Agent."""
    action: str  # Tool name or "claim_preparation", "abort", "complete"
    reason: str  # Human-readable concise explanation of the decision
    decision_type: str = "TOOL_CALL"  # "TOOL_CALL", "PREPARE_CLAIM", "TERMINATE"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "decision_type": self.decision_type
        }


class InsureMateDecisionEngine:
    """
    Evaluates intermediate state and chooses the appropriate next step.
    Supports both rule-guarded evaluation and optional LLM-assisted tool selection.
    """

    def __init__(self, llm_client: Optional[OllamaClient] = None):
        self.llm_client = llm_client

    def decide_next_action(self, state: ClaimState) -> AgentDecision:
        """
        Main decision-making entry point.
        Evaluates intermediate state and selects next step.
        """
        # Try LLM decision if available
        if self.llm_client and self.llm_client.is_available():
            try:
                llm_decision = self._decide_via_llm(state)
                if self._validate_decision(llm_decision, state):
                    logger.info(f"LLM Decision selected: {llm_decision.action} ({llm_decision.reason})")
                    return llm_decision
            except Exception as e:
                logger.warning(f"LLM decision engine failed: {e}. Falling back to rule-grounded evaluation.")

        # Grounded decision evaluation
        return self._evaluate_grounded_decision(state)

    def _evaluate_grounded_decision(self, state: ClaimState) -> AgentDecision:
        """
        Evaluate intermediate results and choose next action based on state conditions.
        """
        # 1. Terminal / Completed check
        if state.final_status is not None:
            return AgentDecision(
                action="complete",
                reason="Required analysis is complete.",
                decision_type="TERMINATE"
            )

        # 2. Check if extraction is needed
        if not state.extracted_data:
            # Check if extraction was already attempted and errored
            if any("document_extraction" in err for err in state.errors) or state.retry_counts.get("document_extraction", 0) > 0:
                return AgentDecision(
                    action="abort",
                    reason="Document extraction failed or document is unreadable. Halting workflow due to insufficient information.",
                    decision_type="TERMINATE"
                )
            return AgentDecision(
                action="document_extraction",
                reason="Document information is not available.",
                decision_type="TOOL_CALL"
            )

        # 3. Intermediate check on extracted documents
        # If extraction produced 0 usable records
        if len(state.extracted_data) == 0:
            return AgentDecision(
                action="abort",
                reason="Extraction returned zero usable document records. Insufficient information to proceed.",
                decision_type="TERMINATE"
            )

        # Check for unreadable/unsupported documents
        all_unknown = all(d.get("document_type") == "unknown" for d in state.extracted_data)
        if all_unknown and len(state.extracted_data) > 0:
            # Even if unknown, let validation run to produce standard actionable error reasons
            pass

        # 4. Check if validation is needed
        if state.validation_result is None:
            return AgentDecision(
                action="document_validation",
                reason="Documents are available. Validation is required.",
                decision_type="TOOL_CALL"
            )

        # 5. Intermediate evaluation after validation
        val_total = state.validation_result.get("total_documents", 0)
        val_valid_count = state.validation_result.get("valid_documents", 0)

        # If zero documents in validation or completely unreadable
        if val_total == 0:
            return AgentDecision(
                action="abort",
                reason="Validation showed empty document set. Insufficient information.",
                decision_type="TERMINATE"
            )

        # If all documents are completely invalid and no policy or bills could be validated
        if val_valid_count == 0 and val_total > 0 and state.validity_result is None:
            # Documents are severely incomplete/invalid
            return AgentDecision(
                action="claim_preparation",
                reason="Submitted documents failed validation with missing mandatory fields. Proceeding to claim preparation to record deficiencies.",
                decision_type="PREPARE_CLAIM"
            )

        # 6. Check if validity checker is needed
        if state.validity_result is None:
            policy_docs = [d for d in state.extracted_data if d.get("document_type") == "insurance_policy"]
            claim_docs = [
                d for d in state.extracted_data
                if d.get("document_type") in ("medical_bill", "medical_report", "hospital_document", "invoice", "incident_document")
            ]

            if not policy_docs:
                return AgentDecision(
                    action="missing_document_detector",
                    reason="No insurance policy document identified in submission. Skipping validity checking to detect missing evidence.",
                    decision_type="TOOL_CALL"
                )
            elif not claim_docs:
                return AgentDecision(
                    action="missing_document_detector",
                    reason="Only policy document available with no incident/bill documents. Skipping validity checking to detect missing evidence.",
                    decision_type="TOOL_CALL"
                )
            else:
                return AgentDecision(
                    action="validity_checker",
                    reason="Policy and bill dates are available. Validity should be checked.",
                    decision_type="TOOL_CALL"
                )

        # 7. Intermediate evaluation after validity checker
        if state.missing_documents is None:
            is_valid_dates = state.validity_result.get("valid", False)
            if not is_valid_dates:
                return AgentDecision(
                    action="missing_document_detector",
                    reason="Validity check identified date/coverage discrepancies. Required-document comparison is required.",
                    decision_type="TOOL_CALL"
                )
            else:
                return AgentDecision(
                    action="missing_document_detector",
                    reason="Required-document comparison is required.",
                    decision_type="TOOL_CALL"
                )

        # 8. Check claim preparation
        if state.final_status is None:
            return AgentDecision(
                action="claim_preparation",
                reason="Required analysis is complete.",
                decision_type="PREPARE_CLAIM"
            )

        return AgentDecision(
            action="complete",
            reason="All claim processing steps completed.",
            decision_type="TERMINATE"
        )

    def _decide_via_llm(self, state: ClaimState) -> AgentDecision:
        """Query pretrained LLM for next action decision."""
        summary = {
            "has_extracted_data": bool(state.extracted_data),
            "doc_count": len(state.extracted_data),
            "has_validation": state.validation_result is not None,
            "validation_valid": state.validation_result.get("valid") if state.validation_result else None,
            "has_validity": state.validity_result is not None,
            "validity_valid": state.validity_result.get("valid") if state.validity_result else None,
            "has_missing_docs": state.missing_documents is not None,
            "completed_steps": state.completed_steps
        }

        prompt = (
            f"You are the InsureMate Agent Orchestrator. Evaluate the current claim state:\n"
            f"{json.dumps(summary, indent=2)}\n\n"
            f"Select the NEXT action from: ['document_extraction', 'document_validation', 'validity_checker', 'missing_document_detector', 'claim_preparation', 'complete'].\n"
            f"Provide a concise 1-sentence reason.\n"
            f"Output strictly valid JSON:\n"
            f'{{"action": "...", "reason": "...", "decision_type": "TOOL_CALL"}}\n'
        )

        resp = self.llm_client.chat(
            messages=[
                {"role": "system", "content": "You are an agent orchestrator deciding the next workflow step. Reply only with JSON."},
                {"role": "user", "content": prompt}
            ],
            format_type="json"
        )

        data = json.loads(resp)
        action = data.get("action", "")
        reason = data.get("reason", "Next processing step selected.")
        decision_type = data.get("decision_type", "TOOL_CALL")
        return AgentDecision(action=action, reason=reason, decision_type=decision_type)

    def _validate_decision(self, decision: AgentDecision, state: ClaimState) -> bool:
        """Ensure LLM decision doesn't violate prerequisite state dependencies."""
        valid_actions = {
            "document_extraction",
            "document_validation",
            "validity_checker",
            "missing_document_detector",
            "claim_preparation",
            "abort",
            "complete"
        }
        if decision.action not in valid_actions:
            return False

        # Guard against skipping extraction
        if decision.action in ("document_validation", "validity_checker", "missing_document_detector") and not state.extracted_data:
            return False

        # Guard against running validation if already done
        if decision.action == "document_validation" and state.validation_result is not None:
            return False

        # Guard against validity checker if already done or if validation had 0 valid documents
        if decision.action == "validity_checker":
            if state.validity_result is not None:
                return False
            if state.validation_result and state.validation_result.get("valid_documents", 0) == 0:
                return False
            policy_docs = [d for d in state.extracted_data if d.get("document_type") == "insurance_policy"]
            if not policy_docs:
                return False

        # Guard against running missing document detector if already done
        if decision.action == "missing_document_detector" and state.missing_documents is not None:
            return False

        # Guard against skipping missing document detector before claim preparation
        if decision.action == "claim_preparation":
            # If documents are valid and policy exists, missing_document_detector must have run
            if state.validation_result and state.validation_result.get("valid_documents", 0) > 0:
                if state.missing_documents is None:
                    return False

        # Guard against premature complete
        if decision.action == "complete" and state.final_status is None:
            return False

        return True
