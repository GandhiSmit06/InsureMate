"""agent/insuremate_agent.py
Central Agent Orchestrator for InsureMate.
Coordinates planning, autonomous tool selection, execution trace logging,
context tracking, and claim readiness package synthesis.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

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
        max_iterations: int = 10
    ):
        if offline_mode is True and llm_client is None:
            self.llm_client = None
        elif llm_client is not None:
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

        self.planner = InsureMatePlanner(llm_client=self.llm_client)
        self.decision_engine = InsureMateDecisionEngine(llm_client=self.llm_client)
        self.max_iterations = max_iterations


    def run(
        self,
        documents: Optional[Union[List[str], str]] = None,
        goal: Optional[str] = None,
        state: Optional[ClaimState] = None,
        max_pages: Optional[int] = None
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
        plan = self.planner.create_initial_plan(
            goal=state.goal,
            documents=state.documents,
            state=state
        )
        state.current_plan = plan.to_dict()

        # 3. Autonomous Execution Loop
        while not state.is_finished() and state.iteration_count < state.max_iterations:
            state.iteration_count += 1

            # Update plan based on current state
            plan = self.planner.update_plan(plan, state)
            state.current_plan = plan.to_dict()

            # Dynamic Decision-Making based on intermediate results
            decision = self.decision_engine.decide_next_action(state)
            state.current_step = decision.action

            logger.info(
                f"[AGENT ITERATION {state.iteration_count}] "
                f"Action={decision.action} | Reason='{decision.reason}'"
            )

            # Case A: Terminal - Terminate normally
            if decision.action == "complete":
                state.record_trace(decision=decision.reason, tool=None, tool_result=None)
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
                    "action_items": ["Provide legible and complete claim documents."]
                }
                break

            # Case C: Claim Preparation tool
            if decision.action == "claim_preparation":
                prep_result = self.tool_registry.execute_tool("claim_preparation", state)
                state.record_tool_execution(
                    tool_name="claim_preparation",
                    status=prep_result.status,
                    summary=prep_result.summary
                )
                state.record_trace(
                    decision=decision.reason,
                    tool="claim_preparation",
                    tool_result=prep_result.summary
                )
                state.mark_step_completed("claim_preparation")
                # Immediately record terminal decision
                state.record_trace(
                    decision="Claim analysis and preparation are complete.",
                    tool=None,
                    tool_result=None
                )
                break

            # Case D: Standard Tool Invocations
            tool_name = decision.action
            tool_res = self.tool_registry.execute_tool(
                tool_name=tool_name,
                state=state,
                max_pages=max_pages
            )

            # Failure Handling & Single Retry policy
            if tool_res.status == "error" and state.can_retry(tool_name):
                logger.warning(f"[AGENT RETRY] Retrying {tool_name} once following error: {tool_res.error}")
                state.increment_retry(tool_name)
                tool_res = self.tool_registry.execute_tool(
                    tool_name=tool_name,
                    state=state,
                    max_pages=max_pages
                )

            # Record tool result in state history
            state.record_tool_execution(
                tool_name=tool_name,
                status=tool_res.status,
                summary=tool_res.summary,
                error=tool_res.error
            )

            # Record human-readable trace
            state.record_trace(
                decision=decision.reason,
                tool=tool_name,
                tool_result=tool_res.summary
            )

            if tool_res.status == "success":
                state.mark_step_completed(tool_name)
            else:
                state.mark_step_failed(tool_name, tool_res.error or "Unknown error")
                # If extraction fails completely, abort gracefully on next turn
                if tool_name == "document_extraction":
                    state.final_status = ClaimStatus.INSUFFICIENT_INFORMATION.value
                    state.final_report = {
                        "claim_id": state.claim_id,
                        "status": state.final_status,
                        "is_ready": False,
                        "decision_summary": f"Document extraction failed: {tool_res.error}",
                        "action_items": ["Please upload valid, uncorrupted PDF documents."]
                    }
                    break

        # Infinite loop guard check
        if state.iteration_count >= state.max_iterations and not state.is_finished():
            state.final_status = ClaimStatus.FAILED.value
            state.errors.append("Execution exceeded safe iteration limit (loop prevention).")
            state.final_report = {
                "claim_id": state.claim_id,
                "status": state.final_status,
                "is_ready": False,
                "decision_summary": "Agent reached maximum iteration limit without converging.",
                "action_items": ["Review document formatting and retry."]
            }

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
