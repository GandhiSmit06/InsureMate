"""agent/insuremate_agent.py
Central Agent Orchestrator for InsureMate.
Coordinates planning, autonomous tool selection, execution trace logging,
context tracking, and claim readiness package synthesis.
"""

from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Optional, Union

from agent.decision import InsureMateDecisionEngine, AgentDecision
from agent.planner import InsureMatePlanner, ClaimPlan
from agent.state import ClaimState, ClaimStatus
from agent.tools import InsureMateToolRegistry, ToolExecutionResult
from services.missing_document.ollama_client import OllamaClient
from tools.tool_registry import ToolRegistry
from tools.tool_executor import ToolExecutor
from utils.logger import logger


class InsureMateAgent:
    """
    Central InsureMate Agent Orchestrator.
    Fulfills Track B Agentic AI application requirements:
    - Multi-step workflow planning
    - Autonomous tool calling loop
    - Context & memory maintenance across intermediate steps
    - Dynamic decision-making conditioned on intermediate observations
    - Robust failure handling and loop guardrails
    - Seamless Phase 6 ToolRegistry & ToolExecutor integration
    """

    DEFAULT_GOAL = "Determine claim readiness."

    def __init__(
        self,
        llm_client: Optional[OllamaClient] = None,
        tool_registry: Optional[Union[InsureMateToolRegistry, ToolRegistry]] = None,
        executor: Optional[ToolExecutor] = None,
        offline_mode: Optional[bool] = None,
        max_iterations: int = 10,
        planner: Optional[InsureMatePlanner] = None,
        decision_engine: Optional[InsureMateDecisionEngine] = None
    ):
        # Local Ollama LLM is the default reasoning controller; no external API key needed
        if llm_client is not None:
            self.llm_client = llm_client
        else:
            self.llm_client = OllamaClient()

        if executor is not None and tool_registry is None:
            self.tool_registry = InsureMateToolRegistry(offline_mode=offline_mode, phase6_registry=executor.registry)
            self.executor = executor
        elif isinstance(tool_registry, ToolRegistry):
            self.tool_registry = InsureMateToolRegistry(offline_mode=offline_mode, phase6_registry=tool_registry)
            self.executor = ToolExecutor(registry=tool_registry)
        else:
            self.tool_registry = tool_registry or InsureMateToolRegistry(offline_mode=offline_mode)
            self.executor = executor or ToolExecutor()

        self.planner = planner or InsureMatePlanner(llm_client=self.llm_client)
        self.decision_engine = decision_engine or InsureMateDecisionEngine(
            llm_client=self.llm_client,
            offline_mode=bool(offline_mode)
        )
        self.max_iterations = max_iterations

    @staticmethod
    def get_tool_antigravity_metadata(tool_name: str) -> tuple:
        """Returns Antigravity-style (toolAction, toolSummary) pair."""
        metadata = {
            "document_extraction": ("Extracting document entities", "Multimodal vision extraction"),
            "document_extraction_tool": ("Extracting document entities", "Multimodal vision extraction"),
            "qwen_vl_extraction_tool": ("Extracting document entities", "Multimodal vision extraction"),
            "document_validation": ("Validating field completeness", "Document validation & integrity audit"),
            "document_validation_tool": ("Validating field completeness", "Document validation & integrity audit"),
            "validity_checker": ("Auditing policy coverage window", "Coverage period & date check"),
            "validity_checker_tool": ("Auditing policy coverage window", "Coverage period & date check"),
            "missing_document_detector": ("Auditing evidence requirements", "Missing document detection"),
            "missing_document_tool": ("Auditing evidence requirements", "Missing document detection"),
            "policy_clause_search": ("Searching policy clauses & limits", "Policy clause search"),
            "policy_clause_search_tool": ("Searching policy clauses & limits", "Policy clause search"),
            "cross_document_consistency_check": ("Auditing cross-document consistency", "Discrepancy & contradiction check"),
            "cross_document_consistency_tool": ("Auditing cross-document consistency", "Discrepancy & contradiction check"),
            "claim_preparation": ("Synthesizing claim readiness package", "Readiness verdict & checklist synthesis"),
        }
        clean_name = (tool_name or "").lower().replace("_tool", "")
        for k, v in metadata.items():
            if k.lower().replace("_tool", "") == clean_name:
                return v
        title = (tool_name or "Tool").replace("_", " ").title()
        return (f"Executing {title}", f"{title} execution")

    def run(
        self,
        documents: Optional[Union[List[str], str]] = None,
        goal: Optional[str] = None,
        state: Optional[ClaimState] = None,
        max_pages: Optional[int] = None,
        on_event: Optional[Any] = None
    ) -> ClaimState:
        """
        Execute autonomous agentic workflow.

        Args:
            documents: List of filesystem paths to policy and claim documents.
            goal: Natural language goal for the agent.
            state: Optional existing ClaimState to continue session.
            max_pages: Optional limit on pages to process per PDF.

        Returns:
            Completed ClaimState containing tool history, trace, and final status.
        """
        # 1. Initialize or normalize working state
        if isinstance(documents, ClaimState) and state is None:
            state = documents
            documents = None

        if state is None:
            doc_list: List[str] = []
            if documents:
                if isinstance(documents, (str, Path)):
                    doc_list = [str(documents)]
                else:
                    doc_list = [str(d) for d in documents]

            state = ClaimState(
                goal=goal or self.DEFAULT_GOAL,
                documents=doc_list,
                max_iterations=self.max_iterations
            )
        elif goal and state.goal == self.DEFAULT_GOAL:
            state.goal = goal

        logger.info(f"[AGENT] Starting InsureMate Agent for Claim ID: {state.claim_id}")

        # 2. Planning Stage
        def _emit(evt: Dict[str, Any]) -> None:
            if on_event:
                try:
                    on_event(evt)
                except Exception as ex:
                    logger.warning(f"[AGENT EVENT ERROR] {ex}")

        # 2. Planning Stage
        plan = self.planner.create_initial_plan(
            goal=state.goal,
            documents=state.documents,
            state=state
        )
        state.current_plan = plan.to_dict()
        _emit({
            "type": "plan",
            "claim_id": state.claim_id,
            "plan": state.current_plan,
            "iteration": 0
        })

        # 3. Autonomous Execution Loop
        while not state.is_finished() and state.iteration_count < state.max_iterations:
            state.iteration_count += 1

            # Update plan based on current state observations
            plan = self.planner.update_plan(plan, state)
            state.current_plan = plan.to_dict()
            _emit({
                "type": "plan",
                "claim_id": state.claim_id,
                "plan": state.current_plan,
                "iteration": state.iteration_count
            })

            # Dynamic Decision-Making based on intermediate results and available tools
            decision = self.decision_engine.decide_next_action(state, tool_registry=self.tool_registry)
            state.current_step = decision.action

            logger.info(
                f"[AGENT ITERATION {state.iteration_count}] "
                f"Action={decision.action} | Reason='{decision.reason}'"
            )

            _emit({
                "type": "decision",
                "claim_id": state.claim_id,
                "action": decision.action,
                "reason": decision.reason,
                "thought": getattr(decision, "thought", "") or decision.reason,
                "decision_type": getattr(decision, "decision_type", "TOOL_CALL"),
                "iteration": state.iteration_count
            })

            # Case A: Terminal - Complete
            if decision.action in ("complete", "finish"):
                state.record_trace(decision=decision.reason, tool=None, tool_result=None)
                if not state.final_status:
                    # Ground final status in accumulated evidence rather than blindly defaulting to ready
                    validation_valid = state.validation_result.get("valid") if state.validation_result else None
                    is_valid_dates = state.validity_result.get("valid") if state.validity_result else None
                    
                    missing_list: list = []
                    if state.missing_documents:
                        raw_missing = (
                            state.missing_documents.get("missing_documents", [])
                            if isinstance(state.missing_documents, dict)
                            else (state.missing_documents if isinstance(state.missing_documents, list) else [])
                        )
                        for item in raw_missing:
                            if isinstance(item, str):
                                missing_list.append(item)
                            elif isinstance(item, dict) and item.get("missing") is True:
                                missing_list.append(item.get("document_title", "Unknown document"))

                    if state.errors and not state.extracted_data:
                        state.final_status = ClaimStatus.INSUFFICIENT_INFORMATION.value
                    elif not state.extracted_data and not state.documents:
                        state.final_status = ClaimStatus.CLAIM_READY_FOR_SUBMISSION.value
                    elif validation_valid is False:
                        state.final_status = ClaimStatus.ACTION_REQUIRED_INVALID_DOCUMENTS.value
                    elif is_valid_dates is False:
                        state.final_status = ClaimStatus.INVALID_CLAIM_DATES.value
                    elif missing_list:
                        state.final_status = ClaimStatus.ACTION_REQUIRED_MISSING_EVIDENCE.value
                    elif validation_valid is True and is_valid_dates is True and not missing_list:
                        state.final_status = ClaimStatus.CLAIM_READY_FOR_SUBMISSION.value
                    elif validation_valid is None or is_valid_dates is None:
                        state.final_status = ClaimStatus.INSUFFICIENT_INFORMATION.value
                    else:
                        state.final_status = ClaimStatus.INSUFFICIENT_INFORMATION.value

                if not state.final_report:
                    is_ready = state.final_status == ClaimStatus.CLAIM_READY_FOR_SUBMISSION.value
                    action_items = []
                    if not is_ready:
                        if state.final_status == ClaimStatus.INVALID_CLAIM_DATES.value:
                            reasons = state.validity_result.get("reasons", []) if state.validity_result else []
                            action_items.extend(reasons or ["Incident or treatment date falls outside the policy coverage period."])
                        elif state.final_status == ClaimStatus.ACTION_REQUIRED_INVALID_DOCUMENTS.value:
                            action_items.append("Provide valid, legible claim documents containing all mandatory fields.")
                        elif state.final_status == ClaimStatus.ACTION_REQUIRED_MISSING_EVIDENCE.value:
                            action_items.append("Upload all missing mandatory claim evidence.")
                        elif state.final_status == ClaimStatus.INSUFFICIENT_INFORMATION.value:
                            action_items.append("Execute complete claim verification before submission.")
                        else:
                            action_items.append(decision.reason or "Review claim deficiencies.")
                    state.final_report = {
                        "claim_id": state.claim_id,
                        "status": state.final_status,
                        "is_ready": is_ready,
                        "decision_summary": decision.reason,
                        "coverage_validity_status": "PASS" if (state.validity_result and state.validity_result.get("valid")) else ("FAIL" if (state.validity_result and state.validity_result.get("valid") is False) else "NOT_CHECKED"),
                        "validation_status": "PASS" if (state.validation_result and state.validation_result.get("valid")) else ("FAIL" if (state.validation_result and state.validation_result.get("valid") is False) else "NOT_CHECKED"),
                        "action_items": action_items,
                        "human_review_required": not is_ready,
                        "notice": "This analysis is an AI-assisted preparation assessment and does not constitute guaranteed insurer approval."
                    }
                _emit({
                    "type": "complete",
                    "claim_id": state.claim_id,
                    "status": state.final_status,
                    "verdict": state.final_status,
                    "report": state.final_report,
                    "iteration": state.iteration_count
                })
                break

            # Case B: Terminal - Abort gracefully due to unreadable/missing input
            if decision.action == "abort":
                state.record_trace(decision=decision.reason, tool=None, tool_result=None)
                state.final_status = ClaimStatus.INSUFFICIENT_INFORMATION.value
                state.final_report = {
                    "claim_id": state.claim_id,
                    "status": state.final_status,
                    "is_ready": False,
                    "decision_summary": decision.reason,
                    "action_items": ["Provide legible and complete claim documents."],
                    "human_review_required": True,
                }
                _emit({
                    "type": "complete",
                    "claim_id": state.claim_id,
                    "status": state.final_status,
                    "verdict": state.final_status,
                    "report": state.final_report,
                    "iteration": state.iteration_count
                })
                break

            # Case C: Terminal / Interaction - Request information from user
            if decision.action in ("request_user_info", "ask_user"):
                state.record_trace(decision=decision.reason, tool=None, tool_result=None)
                if not state.documents and not state.extracted_data:
                    state.final_status = ClaimStatus.INSUFFICIENT_INFORMATION.value
                else:
                    state.final_status = ClaimStatus.ACTION_REQUIRED_MISSING_EVIDENCE.value
                question = decision.reason or "Additional user information or document evidence is required."
                state.record_unresolved_question(question)
                state.final_report = {
                    "claim_id": state.claim_id,
                    "status": state.final_status,
                    "is_ready": False,
                    "decision_summary": decision.reason,
                    "action_items": [question],
                    "human_review_required": True,
                    "unresolved_questions": state.unresolved_questions,
                }
                _emit({
                    "type": "complete",
                    "claim_id": state.claim_id,
                    "status": state.final_status,
                    "verdict": state.final_status,
                    "report": state.final_report,
                    "iteration": state.iteration_count
                })
                break

            # Case D: Dynamic Tool Invocations
            tool_name = decision.action
            tool_args = decision.action_input if isinstance(decision.action_input, dict) else {}

            # Safety & Validation: Reject unknown tools
            if not self.tool_registry.has(tool_name):
                logger.warning(f"[AGENT] Rejected unknown tool '{tool_name}' requested by agent.")
                rejection_error = (
                    f"Tool '{tool_name}' is not recognized or available. "
                    f"Available tools: {self.tool_registry.get_tool_names()}"
                )
                state.record_tool_execution(
                    tool_name=tool_name,
                    status="error",
                    summary=f"Unknown tool '{tool_name}' rejected.",
                    inputs_summary=str(tool_args) if tool_args else None,
                    error=rejection_error
                )
                state.record_trace(
                    decision=decision.reason,
                    tool=tool_name,
                    tool_result=f"REJECTED: {rejection_error}"
                )
                state.mark_step_failed(tool_name, rejection_error)
                continue

            tool_action, tool_summary = self.get_tool_antigravity_metadata(tool_name)
            t_start = time.time()
            _emit({
                "type": "tool_start",
                "claim_id": state.claim_id,
                "tool_name": tool_name,
                "tool_action": tool_action,
                "tool_summary": tool_summary,
                "inputs": tool_args,
                "iteration": state.iteration_count,
                "timestamp": t_start
            })

            exec_kwargs = dict(tool_args) if isinstance(tool_args, dict) else {}
            if max_pages is not None and "max_pages" not in exec_kwargs:
                exec_kwargs["max_pages"] = max_pages

            tool_res = self.tool_registry.execute_tool(
                tool_name=tool_name,
                state=state,
                **exec_kwargs
            )

            # Failure Handling & Controlled Single Retry policy
            if tool_res.status == "error" and state.can_retry(tool_name):
                logger.warning(f"[AGENT RETRY] Retrying {tool_name} once following error: {tool_res.error}")
                state.increment_retry(tool_name)
                state.record_trace(
                    decision=f"Retrying {tool_name} once following error: {tool_res.error}",
                    tool=tool_name,
                    tool_result="Initiating retry attempt"
                )
                tool_res = self.tool_registry.execute_tool(
                    tool_name=tool_name,
                    state=state,
                    **exec_kwargs
                )

            t_duration = round((time.time() - t_start) * 1000, 1)

            # Record tool result in state history
            state.record_tool_execution(
                tool_name=tool_name,
                status=tool_res.status,
                summary=tool_res.summary,
                inputs_summary=str(tool_args) if tool_args else None,
                error=tool_res.error
            )

            _emit({
                "type": "tool_finish",
                "claim_id": state.claim_id,
                "tool_name": tool_name,
                "tool_action": tool_action,
                "tool_summary": tool_summary,
                "status": tool_res.status,
                "summary": tool_res.summary,
                "data": getattr(tool_res, "data", {}) or {},
                "duration_ms": t_duration,
                "error": tool_res.error,
                "iteration": state.iteration_count,
                "timestamp": time.time()
            })

            # Record human-readable trace
            state.record_trace(
                decision=decision.reason,
                tool=tool_name,
                tool_result=tool_res.summary
            )

            if tool_res.status == "success":
                state.mark_step_completed(tool_name)
                # Ground verified facts into state
                if tool_name == "validity_checker" and state.validity_result:
                    state.record_verified_fact(
                        "date_validity",
                        state.validity_result.get("valid", False),
                        provenance="validity_checker"
                    )
                elif tool_name == "document_validation" and state.validation_result:
                    state.record_verified_fact(
                        "document_validation",
                        state.validation_result.get("valid", False),
                        provenance="document_validation"
                    )
                elif tool_name == "policy_clause_search" and state.clause_search_results:
                    matches = state.clause_search_results.get("matched_clauses") or state.clause_search_results.get("matches", [])
                    if matches:
                        state.record_verified_fact(
                            "policy_clauses_found",
                            [m.get("clause_text") or m.get("clause") for m in matches[:3]],
                            provenance="policy_clause_search"
                        )
                elif tool_name == "cross_document_consistency_check" and state.consistency_results:
                    discrepancies = state.consistency_results.get("discrepancies", [])
                    if discrepancies:
                        state.record_verified_fact(
                            "discrepancies_detected",
                            discrepancies,
                            provenance="cross_document_consistency_check"
                        )
                elif tool_name == "missing_document_detector" and state.missing_documents:
                    missing = state.missing_documents.get("missing_documents", [])
                    if missing:
                        for m_doc in missing:
                            state.record_unresolved_question(
                                f"Missing mandatory document: {m_doc.get('document_type', 'unknown')}"
                            )
            else:
                state.mark_step_failed(tool_name, tool_res.error or "Unknown error")

        # Bounded execution limit guard check
        if state.iteration_count >= state.max_iterations and not state.is_finished():
            state.final_status = ClaimStatus.FAILED.value
            state.errors.append(f"Execution reached maximum limit of {state.max_iterations} iterations without converging.")
            state.final_report = {
                "claim_id": state.claim_id,
                "status": state.final_status,
                "is_ready": False,
                "decision_summary": f"Agent reached iteration limit ({state.max_iterations}) to ensure bounded execution.",
                "action_items": ["Review document formatting and retry with clearer instructions."],
                "human_review_required": True,
            }
            _emit({
                "type": "complete",
                "claim_id": state.claim_id,
                "status": state.final_status,
                "verdict": state.final_status,
                "report": state.final_report,
                "iteration": state.iteration_count
            })

        logger.info(f"[AGENT] Workflow concluded. Final Status: {state.final_status}")
        return state

    def format_execution_trace(self, state: ClaimState) -> str:
        """
        Formats safe, human-readable execution trace matching master specification.
        Hides private internal chain-of-thought, showing only plan, tool selections,
        results, and concise decisions.
        """
        lines: List[str] = [
            "=" * 50,
            "INSUREMATE AGENT EXECUTION",
            "=" * 50,
            "",
            "GOAL:",
            state.goal,
            "",
            "PLAN:"
        ]

        # Plan steps
        if state.current_plan and "steps" in state.current_plan:
            for s in state.current_plan["steps"]:
                action_name = s.get("action", "").replace("_", " ").title()
                lines.append(f"{s.get('step')}. {action_name}")
        else:
            lines.extend([
                "1. Extract documents",
                "2. Validate documents",
                "3. Check validity",
                "4. Detect missing evidence",
                "5. Complete claim analysis"
            ])

        lines.append("")

        # Execution trace entries
        for entry in state.execution_trace:
            lines.append("AGENT DECISION:")
            lines.append(entry.get("decision", ""))
            lines.append("")

            if entry.get("tool"):
                lines.append("TOOL:")
                lines.append(entry.get("tool", ""))
                lines.append("")

            if entry.get("tool_result"):
                lines.append("TOOL RESULT:")
                lines.append(entry.get("tool_result", ""))
                lines.append("")

        # Final State
        final_summary = "Claim processing complete."
        if state.final_report:
            final_summary = state.final_report.get("decision_summary", state.final_status or "Complete")
        elif state.final_status:
            final_summary = state.final_status

        lines.append("FINAL STATE:")
        lines.append(final_summary)
        lines.append("")
        lines.append("=" * 50)

        return "\n".join(lines)

    def print_execution_trace(self, state: ClaimState) -> None:
        """Print the execution trace to stdout."""
        print(self.format_execution_trace(state))
