"""agent/decision.py
Dynamic Decision-Making Engine for the InsureMate Agent.
The LLM acts as the decision-making controller, dynamically choosing tools,
evaluating observations, and deciding next steps or termination without any
hardcoded universal sequence of execution.
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
    """Represents a dynamic runtime decision made by the InsureMate Agent."""
    action: str  # Registered tool name or "complete", "request_user_info", "abort"
    reason: str  # Concise human-readable explanation
    decision_type: str = "TOOL_CALL"  # "TOOL_CALL", "REQUEST_INFO", "TERMINATE"
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
    Evaluates intermediate state, user goal, available tools, and observations
    to dynamically determine the next action using the LLM.
    Strictly prohibits hardcoded universal execution sequences.
    """

    MAX_RECOVERY_ATTEMPTS: int = 2

    def __init__(self, llm_client: Optional[OllamaClient] = None, offline_mode: bool = False):
        self.llm_client = llm_client
        self.offline_mode = offline_mode

    def decide_next_action(
        self,
        state: ClaimState,
        tool_registry: Optional[Any] = None
    ) -> AgentDecision:
        """
        Main decision-making entry point.
        The LLM autonomously determines the next action based on accumulated evidence.
        When offline_mode is explicitly enabled without an active LLM, evaluates goal-directed actions.
        """
        # Terminal state check
        if state.final_status is not None:
            return AgentDecision(
                action="complete",
                reason="Task already reached terminal status.",
                decision_type="TERMINATE"
            )

        # If offline_mode is set or LLM client is unavailable or local daemon offline, use grounded decision engine
        if self.offline_mode or not self.llm_client or not self.llm_client.is_available():
            return self._evaluate_grounded_decision(state, tool_registry)

        # LLM-driven decision with bounded recovery
        last_error = ""
        for attempt in range(self.MAX_RECOVERY_ATTEMPTS + 1):
            try:
                feedback = f"Previous response error: {last_error}" if last_error else None
                llm_decision = self._decide_via_llm(state, tool_registry, error_feedback=feedback)
                
                is_valid, validation_err = self._validate_decision(llm_decision, state, tool_registry)
                if is_valid:
                    logger.info(f"[LLM DECISION] Action='{llm_decision.action}' | Reason='{llm_decision.reason}'")
                    return llm_decision
                
                last_error = validation_err
                logger.warning(f"[DECISION RECOVERY {attempt+1}/{self.MAX_RECOVERY_ATTEMPTS}] {validation_err}")

            except Exception as e:
                last_error = f"Model execution error: {e}"
                logger.warning(f"[DECISION ERROR {attempt+1}/{self.MAX_RECOVERY_ATTEMPTS}] {e}")

        # Recovery exhausted: abort gracefully
        logger.warning(f"[DECISION RECOVERY] LLM retries exhausted ({last_error}). Aborting safely.")
        return AgentDecision(
            action="abort",
            reason=f"LLM decision recovery exhausted: {last_error}",
            decision_type="TERMINATE"
        )

    def _build_tools_manifest(self, tool_registry: Optional[Any] = None) -> List[Dict[str, Any]]:
        return [
            {
                "name": "document_extraction",
                "description": "Extracts text, entities, and classifications from documents.",
                "parameters": {},
                "expected_output": "Extracted list of document pages with entities.",
                "prerequisites": []
            },
            {
                "name": "document_validation",
                "description": "Validates mandatory claim fields for extracted document records. Runs autonomously on extracted documents.",
                "parameters": {},
                "expected_output": "Validation pass/fail summary and missing fields.",
                "prerequisites": ["document_extraction"]
            },
            {
                "name": "validity_checker",
                "description": "Audits incident and bill dates against policy coverage duration. Runs autonomously on extracted documents.",
                "parameters": {},
                "expected_output": "Coverage duration validity check.",
                "prerequisites": ["document_extraction"]
            },
            {
                "name": "missing_document_detector",
                "description": "Infers required documents from policy clauses and detects missing claim evidence. Runs autonomously on extracted documents.",
                "parameters": {},
                "expected_output": "Checklist of missing evidence.",
                "prerequisites": ["document_extraction"]
            },
            {
                "name": "policy_clause_search",
                "description": "Searches policy clauses, exclusions, waiting periods, room rent, and benefits.",
                "parameters": {"query": {"type": "string"}},
                "expected_output": "Matching policy clauses and relevant excerpts.",
                "prerequisites": ["document_extraction"]
            },
            {
                "name": "cross_document_consistency_check",
                "description": "Cross-checks patient names, hospital providers, amounts, and dates across documents. Runs autonomously on extracted documents.",
                "parameters": {},
                "expected_output": "Consistency assessment and discrepancy report.",
                "prerequisites": ["document_extraction"]
            },
            {
                "name": "claim_preparation",
                "description": "Synthesizes final claim readiness determination, action checklist, and verdict. Prerequisite: document_validation, validity_checker, missing_document_detector, and cross_document_consistency_check must be completed first.",
                "parameters": {},
                "expected_output": "Comprehensive readiness report.",
                "prerequisites": ["document_validation", "validity_checker", "missing_document_detector", "cross_document_consistency_check"]
            }
        ]

    def _build_system_prompt(self) -> str:
        return (
            "You are InsureMate's autonomous AI Agent Orchestrator. "
            "You independently determine the NEXT action to satisfy the user's goal based on actual evidence. "
            "CRITICAL RULES:\n"
            "1. Choose the NEXT analytical tool to progress towards claim readiness.\n"
            "2. All analysis tools (document_validation, validity_checker, missing_document_detector, cross_document_consistency_check, claim_preparation) operate automatically on the extracted claim documents. Always leave 'action_input' empty ({}).\n"
            "3. DO NOT call 'request_user_info' while analysis tools are pending. You MUST execute all relevant analysis tools to audit the documents.\n"
            "4. PREREQUISITES: 'claim_preparation' CANNOT be called until 'document_validation', 'validity_checker', 'missing_document_detector', AND 'cross_document_consistency_check' have all completed. Call 'document_validation', 'validity_checker', 'missing_document_detector', and 'cross_document_consistency_check' first before preparing the claim.\n"
            "5. If all analysis steps are completed, choose action 'claim_preparation'.\n"
            "6. Never limit or truncate document extraction with artificial max_pages.\n\n"
            "Output strictly valid JSON with this format:\n"
            "{\n"
            '  "thought": "Analysis of current observations, what has been established, and why this action is needed next",\n'
            '  "action": "<tool_name or complete or claim_preparation>",\n'
            '  "action_input": {},\n'
            '  "reason": "Clear explanation of this step",\n'
            '  "decision_type": "TOOL_CALL" or "PREPARE_CLAIM" or "TERMINATE"\n'
            "}"
        )

    def _build_user_prompt(
        self,
        state: ClaimState,
        tool_registry: Optional[Any] = None,
        error_feedback: Optional[str] = None
    ) -> str:
        tools_manifest = self._build_tools_manifest(tool_registry)

        recent_observations = []
        for entry in state.tool_history[-4:]:
            recent_observations.append({
                "tool": entry.get("tool_name"),
                "status": entry.get("status"),
                "summary": entry.get("summary"),
                "inputs": entry.get("inputs_summary"),
                "error": entry.get("error")
            })

        extracted_summary = []
        for doc in state.extracted_data:
            extracted_summary.append({
                "page": doc.get("page_number"),
                "type": doc.get("document_type"),
                "title": doc.get("document_title"),
                "insurer": doc.get("insurer_name") or doc.get("insurer"),
                "policy_number": doc.get("policy_number"),
                "dates": f"{doc.get('policy_start_date')}-{doc.get('policy_end_date')}" if doc.get("policy_start_date") else doc.get("document_date"),
                "patient": doc.get("patient_name") or doc.get("policy_holder_name"),
                "hospital": doc.get("hospital_name"),
                "amount": doc.get("bill_amount")
            })

        context_payload = {
            "user_goal": state.goal,
            "uploaded_documents": state.documents,
            "total_extracted_pages": len(state.extracted_data),
            "extracted_pages_summary": extracted_summary,
            "verified_facts": state.verified_facts,
            "unresolved_questions": state.unresolved_questions,
            "recent_tool_observations": recent_observations,
            "completed_steps": state.completed_steps,
            "validation_status": "COMPLETED" if state.validation_result is not None else "PENDING",
            "validity_status": "COMPLETED" if state.validity_result is not None else "PENDING",
            "missing_evidence_status": "COMPLETED" if state.missing_documents is not None else "PENDING",
            "consistency_status": "COMPLETED" if state.consistency_results is not None else "PENDING",
            "pending_mandatory_checks": [
                c for c, done in [
                    ("document_validation", state.validation_result is not None),
                    ("validity_checker", state.validity_result is not None),
                    ("missing_document_detector", state.missing_documents is not None),
                    ("cross_document_consistency_check", state.consistency_results is not None)
                ] if not done
            ],
            "remaining_budget": state.remaining_budget,
            "iteration_count": state.iteration_count
        }

        user_content = (
            f"GOAL:\n{state.goal}\n\n"
            f"AVAILABLE TOOLS MANIFEST:\n{json.dumps(tools_manifest, indent=2)}\n\n"
            f"CURRENT CONTEXT & EVIDENCE:\n{json.dumps(context_payload, indent=2)}\n\n"
        )
        if error_feedback:
            user_content += (
                f"CORRECTION REQUIRED: Your previous decision failed validation: {error_feedback}\n"
                f"DO NOT select 'claim_preparation' while any prerequisite check is PENDING. "
                f"You MUST select one of the pending checks: {context_payload['pending_mandatory_checks']}.\n\n"
            )
        user_content += "Decide the next action:"
        return user_content

    def _decide_via_llm(
        self,
        state: ClaimState,
        tool_registry: Optional[Any] = None,
        error_feedback: Optional[str] = None
    ) -> AgentDecision:
        """Query LLM with goal, tool manifests, verified evidence, and recent observations."""
        system_prompt = self._build_system_prompt()
        user_content = self._build_user_prompt(state, tool_registry, error_feedback)

        resp = self.llm_client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            format_type="json"
        )

        # Parse JSON with robust stripping and regex repair
        cleaned = resp.strip()
        if "```" in cleaned:
            m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
            if m:
                cleaned = m.group(1).strip()

        data: Optional[Dict[str, Any]] = None
        try:
            data = json.loads(cleaned)
        except Exception:
            m = re.search(r"\{[\s\S]*\}", resp)
            if m:
                try:
                    data = json.loads(m.group(0))
                except Exception:
                    data = None

        if not isinstance(data, dict):
            # Run lightweight regex-based key-value extraction
            act_m = re.search(r'["\']action["\']\s*:\s*["\']([^"\']+)["\']', resp, re.I)
            rsn_m = re.search(r'["\']reason["\']\s*:\s*["\']([^"\']+)["\']', resp, re.I)
            tht_m = re.search(r'["\']thought["\']\s*:\s*["\']([^"\']+)["\']', resp, re.I)
            inp_m = re.search(r'["\']action_input["\']\s*:\s*(\{[\s\S]*?\})', resp, re.I)

            act_val = act_m.group(1).strip() if act_m else ""
            rsn_val = rsn_m.group(1).strip() if rsn_m else "Autonomous decision."
            tht_val = tht_m.group(1).strip() if tht_m else ""
            inp_val = {}
            if inp_m:
                try:
                    inp_val = json.loads(inp_m.group(1))
                except Exception:
                    inp_val = {}
            if act_val:
                data = {
                    "action": act_val,
                    "reason": rsn_val,
                    "thought": tht_val,
                    "action_input": inp_val
                }
            else:
                raise ValueError(f"Could not parse valid JSON from response: {resp[:200]}")

        action = str(data.get("action", "")).strip()
        reason = str(data.get("reason", "Autonomous decision.")).strip()
        thought = str(data.get("thought", "")).strip()
        action_input = data.get("action_input") if isinstance(data.get("action_input"), dict) else {}
        decision_type = str(data.get("decision_type", "")).strip()
        if not decision_type:
            decision_type = "TERMINATE" if action in ("complete", "finish", "abort", "request_user_info") else "TOOL_CALL"

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
    ) -> (bool, str):
        """Validate decision format and detect infinite repetition loops."""
        if not decision.action:
            return False, "Decision action is empty."

        # Ensure documents have been extracted before claim_preparation
        if decision.action == "claim_preparation":
            if not state.extracted_data and not state.errors:
                return False, "Document extraction must be executed before 'claim_preparation'."
            has_val_failure = state.validation_result and state.validation_result.get("valid") is False and state.validation_result.get("valid_documents", 0) == 0
            has_date_failure = state.validity_result and state.validity_result.get("valid") is False
            if not has_val_failure and not has_date_failure:
                if state.validation_result is None:
                    return False, "Prerequisite 'document_validation' must be executed before 'claim_preparation' to audit document completeness and mandatory fields."
                if state.validity_result is None:
                    return False, "Prerequisite 'validity_checker' must be executed before 'claim_preparation' to verify policy coverage dates."
                if state.missing_documents is None:
                    return False, "Prerequisite 'missing_document_detector' must be executed before 'claim_preparation' to audit required policy evidence."
                if state.consistency_results is None and len(state.extracted_data) > 1:
                    return False, "Prerequisite 'cross_document_consistency_check' must be executed before 'claim_preparation' to cross-audit entity consistency."

        # Block premature request_user_info when documents exist and audits are pending,
        # unless an actual failure/contradiction was already discovered and requires clarification.
        if decision.action in ("request_user_info", "ask_user"):
            if state.extracted_data:
                has_val_failure = state.validation_result and (
                    state.validation_result.get("valid") is False or state.validation_result.get("valid_documents", 1) == 0
                )
                has_date_failure = state.validity_result and state.validity_result.get("valid") is False
                has_consistency_issue = state.consistency_results and (
                    state.consistency_results.get("consistent") is False
                    or len(state.consistency_results.get("discrepancies", [])) > 0
                )
                if not (has_val_failure or has_date_failure or has_consistency_issue):
                    pending_audits = []
                    if state.validation_result is None:
                        pending_audits.append("document_validation")
                    if state.validity_result is None:
                        pending_audits.append("validity_checker")
                    if state.missing_documents is None:
                        pending_audits.append("missing_document_detector")
                    if state.consistency_results is None and len(state.extracted_data) > 1:
                        pending_audits.append("cross_document_consistency_check")
                    if pending_audits:
                        return False, f"All uploaded documents must be analyzed before requesting user info. Next mandatory tool: '{pending_audits[0]}'."

        # Prevent infinite repetitions: same tool called 3 or more times consecutively
        history_actions = [h.get("tool_name") for h in state.tool_history[-3:]]
        if len(history_actions) >= 3 and all(a == decision.action for a in history_actions):
            return False, f"Loop detected: Tool '{decision.action}' called 3 times consecutively without progress."

        return True, ""

    def _evaluate_grounded_decision(
        self,
        state: ClaimState,
        tool_registry: Optional[Any] = None
    ) -> AgentDecision:
        """
        Dynamically determine the next action grounded in the specific goal and state observations.
        Active during offline mode when an LLM server is not configured or in local evaluation mode.
        """
        if state.final_status is not None:
            return AgentDecision(
                action="complete",
                reason="Required analysis is complete.",
                decision_type="TERMINATE"
            )

        goal_lower = (state.goal or "").lower()

        # 1. Document Extraction Check
        if not state.extracted_data:
            if any("document_extraction" in err for err in state.errors) or state.retry_counts.get("document_extraction", 0) > 0:
                return AgentDecision(
                    action="abort",
                    reason="Document extraction failed or document is unreadable. Halting workflow due to insufficient information.",
                    decision_type="TERMINATE"
                )
            if state.documents:
                return AgentDecision(
                    action="document_extraction",
                    reason="Extracting document entities and pages using vision/OCR pipeline.",
                    decision_type="TOOL_CALL"
                )
            return AgentDecision(
                action="abort",
                reason="No documents available to extract.",
                decision_type="TERMINATE"
            )

        # 2. Targeted clause goal check
        is_clause_goal = any(kw in goal_lower for kw in [
            "clause", "exclusion", "exclude", "cataract", "waiting period",
            "room rent", "copay", "limit", "benefit", "coverage condition"
        ])
        if is_clause_goal and not any(kw in goal_lower for kw in ["readiness", "full audit", "prepare claim", "validate medical"]):
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

        # 3. Targeted validity check goal
        is_validity_goal = any(kw in goal_lower for kw in [
            "date validity", "validity check", "is policy valid", "coverage period", "active period", "dates valid"
        ])
        if is_validity_goal and not any(kw in goal_lower for kw in ["readiness", "full audit", "prepare claim"]):
            if "validity_checker" not in state.completed_steps:
                return AgentDecision(
                    action="validity_checker",
                    reason=f"Auditing policy validity period against document dates for goal: '{state.goal}'.",
                    decision_type="TOOL_CALL"
                )
            return AgentDecision(
                action="complete",
                reason="Validity check inquiry satisfied.",
                decision_type="TERMINATE"
            )

        # 4. Targeted missing document checklist goal
        is_missing_doc_goal = any(kw in goal_lower for kw in [
            "missing document", "document checklist", "missing evidence", "what documents are missing", "detect missing"
        ])
        if is_missing_doc_goal and not any(kw in goal_lower for kw in ["readiness", "full audit", "prepare claim"]):
            if "missing_document_detector" not in state.completed_steps:
                return AgentDecision(
                    action="missing_document_detector",
                    reason=f"Auditing submitted documents against required policy evidence for goal: '{state.goal}'.",
                    decision_type="TOOL_CALL"
                )
            return AgentDecision(
                action="complete",
                reason="Missing document inquiry satisfied.",
                decision_type="TERMINATE"
            )

        # 5. Targeted document validation goal
        is_field_val_goal = any(kw in goal_lower for kw in [
            "validate field", "field validation", "mandatory field", "document completeness", "field completeness"
        ])
        if is_field_val_goal and not any(kw in goal_lower for kw in ["readiness", "full audit", "prepare claim"]):
            if "document_validation" not in state.completed_steps:
                return AgentDecision(
                    action="document_validation",
                    reason=f"Validating mandatory document fields for goal: '{state.goal}'.",
                    decision_type="TOOL_CALL"
                )
            return AgentDecision(
                action="complete",
                reason="Document validation inquiry satisfied.",
                decision_type="TERMINATE"
            )

        # 6. Targeted cross-document consistency goal
        is_consistency_goal = any(kw in goal_lower for kw in [
            "consistency check", "discrepancy", "cross check", "cross-document"
        ])
        if is_consistency_goal and not any(kw in goal_lower for kw in ["readiness", "full audit", "prepare claim"]):
            if "cross_document_consistency_check" not in state.completed_steps:
                return AgentDecision(
                    action="cross_document_consistency_check",
                    reason=f"Cross-checking records across submitted documents for goal: '{state.goal}'.",
                    decision_type="TOOL_CALL"
                )
            return AgentDecision(
                action="complete",
                reason="Cross-document consistency inquiry satisfied.",
                decision_type="TERMINATE"
            )

        # 7. Adaptive Comprehensive Evaluation (Goal: readiness / full assessment)
        if state.validation_result is None:
            return AgentDecision(
                action="document_validation",
                reason="Validating document completeness and mandatory field integrity.",
                decision_type="TOOL_CALL"
            )

        # Observation branch: if all documents failed validation, synthesize rejection report directly
        if state.validation_result.get("total_documents", 0) > 0 and state.validation_result.get("valid_documents", 0) == 0:
            if "claim_preparation" not in state.completed_steps:
                return AgentDecision(
                    action="claim_preparation",
                    reason="All submitted documents failed mandatory validation checks. Synthesizing deficiency findings.",
                    decision_type="PREPARE_CLAIM"
                )
            return AgentDecision(
                action="complete",
                reason="All submitted documents failed validation checks. Deficiency report generated.",
                decision_type="TERMINATE"
            )

        # Coverage Validity Check
        if state.validity_result is None:
            return AgentDecision(
                action="validity_checker",
                reason="Checking policy coverage period against incident and treatment dates.",
                decision_type="TOOL_CALL"
            )

        # Missing Document Detection
        if state.missing_documents is None:
            return AgentDecision(
                action="missing_document_detector",
                reason="Auditing submitted documents against required policy evidence clauses.",
                decision_type="TOOL_CALL"
            )

        # Cross-Document Consistency Check
        if state.consistency_results is None and "cross_document_consistency_check" not in state.completed_steps:
            return AgentDecision(
                action="cross_document_consistency_check",
                reason="Cross-checking insurer identities, policy numbers, patient names, and facilities across all submitted documents.",
                decision_type="TOOL_CALL"
            )

        # Final Claim Preparation
        if "claim_preparation" not in state.completed_steps:
            return AgentDecision(
                action="claim_preparation",
                reason="Synthesizing final claim readiness package and actionable assessment checklist.",
                decision_type="PREPARE_CLAIM"
            )

        return AgentDecision(
            action="complete",
            reason="Autonomous analysis completed. Readiness assessment synthesized.",
            decision_type="TERMINATE"
        )
