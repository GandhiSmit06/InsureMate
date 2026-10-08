"""tools/tool_executor.py
Central Tool Executor for the InsureMate Agentic AI Architecture.
Handles safe execution, input validation, controlled retries, operational logging,
structured error handling, and tool execution history for the Phase 5 Agent Orchestrator.
"""

from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional, Union

from tools.base_tool import AgentTool
from tools.claim_state import ClaimState
from tools.tool_registry import ToolRegistry, create_tool_registry
from utils.logger import logger


class ToolErrorDict(dict):
    """
    Structured error dictionary compatible with both string and dict expectations.
    Allows accessing `error['type']` and `error['message']`, while `str(error)` returns
    the human-readable error message.
    """

    def __init__(self, error_type: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__({"type": error_type, "message": message})
        if details:
            self["details"] = details

    def __str__(self) -> str:
        return self.get("message", "")


class ToolExecutor:
    """
    Standardized executor for InsureMate Agent tools.

    Responsibilities:
    1. Look up tool by name in ToolRegistry.
    2. Validate input dictionary.
    3. Execute tool with optional controlled retry capability.
    4. Capture results and record operational history.
    5. Handle and structure all errors without crashing the agent.
    6. Maintain ClaimState compatibility.
    """

    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry: ToolRegistry = registry or create_tool_registry()
        self.execution_history: List[Dict[str, Any]] = []

    def execute(
        self,
        tool_name: str,
        input_data: Optional[Dict[str, Any]] = None,
        retry_count: int = 0,
        state: Optional[ClaimState] = None,
    ) -> Dict[str, Any]:
        """
        Execute a registered tool safely and return a standardized result.

        Args:
            tool_name: Canonical name or alias of the tool to execute.
            input_data: Tool input dictionary. Defaults to empty dict if None.
            retry_count: Number of retries on failure (default 0).
            state: Optional shared ClaimState to record history and update context.

        Returns:
            Standardized result dictionary:
            Success:
            {
                "success": True,
                "tool_name": tool_name,
                "result": {...},
                "error": None
            }
            Failure:
            {
                "success": False,
                "tool_name": tool_name,
                "result": None,
                "error": {
                    "type": "...",
                    "message": "..."
                }
            }
        """
        start_time = time.time()
        input_data = input_data if input_data is not None else {}

        # 1. Operational Log: Tool Call
        logger.info(f"\n[TOOL CALL]\nTool: {tool_name}")

        # 2. Input validation: verify input_data type
        if not isinstance(input_data, dict):
            err_msg = f"Invalid input format for tool '{tool_name}': expected dict, got {type(input_data).__name__}."
            err = ToolErrorDict("ToolValidationError", err_msg)
            return self._finalize_result(
                tool_name=tool_name,
                success=False,
                result=None,
                error=err,
                start_time=start_time,
                retries_attempted=0,
                state=state,
            )

        # 3. Find tool in registry
        tool: Optional[AgentTool] = self.registry.get(tool_name)
        if not tool:
            available = self.registry.get_tool_names()
            err_msg = f"Tool '{tool_name}' not found in registry. Available tools: {available}"
            err = ToolErrorDict("ToolNotFoundError", err_msg)
            return self._finalize_result(
                tool_name=tool_name,
                success=False,
                result=None,
                error=err,
                start_time=start_time,
                retries_attempted=0,
                state=state,
            )

        # 4. Safe Execution with Controlled Retry
        max_attempts = max(1, 1 + retry_count)
        last_error: Optional[Exception] = None
        last_tool_result: Optional[Dict[str, Any]] = None
        attempts_made = 0

        for attempt in range(1, max_attempts + 1):
            attempts_made = attempt
            if attempt > 1:
                logger.info(f"[TOOL RETRY] Retrying '{tool_name}' (attempt {attempt}/{max_attempts})...")

            try:
                # Execute tool method
                if hasattr(tool, "execute"):
                    res = tool.execute(input_data)
                elif hasattr(tool, "run"):
                    res = tool.run(**input_data)
                elif callable(tool):
                    res = tool(input_data)
                else:
                    raise TypeError(f"Tool '{tool_name}' is not callable and does not provide execute().")

                last_tool_result = res

                # Check if tool itself reported a failure that should trigger retry
                if isinstance(res, dict) and res.get("success") is False:
                    tool_err = res.get("error") or (res.get("errors")[0] if res.get("errors") else "Tool reported failure")
                    last_error = RuntimeError(str(tool_err))
                    if attempt < max_attempts:
                        continue
                    else:
                        break

                # Success reached
                return self._finalize_result(
                    tool_name=tool_name,
                    success=True,
                    result=res,
                    error=None,
                    start_time=start_time,
                    retries_attempted=attempts_made - 1,
                    state=state,
                )

            except Exception as e:
                last_error = e
                logger.error(f"[TOOL ERROR] Error executing '{tool_name}' on attempt {attempt}: {e}")
                if attempt < max_attempts:
                    continue

        # If execution loop exhausted with failure
        err_type = type(last_error).__name__ if last_error else "ToolExecutionError"
        err_msg = str(last_error) if last_error else f"Tool '{tool_name}' execution failed."
        err = ToolErrorDict(err_type, err_msg)

        return self._finalize_result(
            tool_name=tool_name,
            success=False,
            result=last_tool_result,
            error=err,
            start_time=start_time,
            retries_attempted=attempts_made - 1,
            state=state,
        )

    def _finalize_result(
        self,
        tool_name: str,
        success: bool,
        result: Optional[Dict[str, Any]],
        error: Optional[ToolErrorDict],
        start_time: float,
        retries_attempted: int,
        state: Optional[ClaimState] = None,
    ) -> Dict[str, Any]:
        """Format standardized output, record operational history, and log status."""
        duration_ms = round((time.time() - start_time) * 1000, 2)
        status_str = "success" if success else "failed"

        # Operational Log: Tool Result
        logger.info(f"[TOOL RESULT]\nStatus: {status_str}\nDuration: {duration_ms}ms")
        if not success and error:
            logger.info(f"Error: {error.get('type')}: {error.get('message')}")

        summary = self._generate_summary(tool_name, success, result, error)

        history_record = {
            "tool_name": tool_name,
            "status": status_str,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "retries_attempted": retries_attempted,
            "duration_ms": duration_ms,
        }
        self.execution_history.append(history_record)

        # Update shared ClaimState if provided
        if state is not None:
            state.record_history(history_record)
            if success and result:
                state.update_from_tool_result(tool_name, result)

        return {
            "success": success,
            "tool_name": tool_name,
            "result": result,
            "error": error if not success else None,
        }

    def _generate_summary(
        self,
        tool_name: str,
        success: bool,
        result: Optional[Dict[str, Any]],
        error: Optional[ToolErrorDict],
    ) -> str:
        """Create a concise operational summary without sensitive PII or chain-of-thought."""
        if not success:
            return f"Execution failed: {error.get('message') if error else 'unknown error'}"

        if not result or not isinstance(result, dict):
            return f"Executed '{tool_name}' successfully."

        # Document Extraction Tool Summary
        if tool_name in ("document_extraction_tool", "qwen_vl_extraction_tool"):
            pages = result.get("total_pages", len(result.get("extracted_documents", [])))
            docs = len(result.get("documents_processed", []))
            return f"Extracted {pages} page(s) across {docs} document(s) successfully."

        # Document Validation Tool Summary
        elif tool_name == "document_validation_tool":
            valid = result.get("valid", False)
            total = result.get("total_documents", 0)
            valid_cnt = result.get("valid_documents", 0)
            invalid_cnt = result.get("invalid_documents", 0)
            if valid:
                return f"All {total} document(s) validated successfully."
            return f"Validation complete: {valid_cnt}/{total} valid, {invalid_cnt} invalid."

        # Validity Checker Tool Summary
        elif tool_name == "validity_checker_tool":
            valid = result.get("valid", False)
            checks_cnt = len(result.get("checks", []))
            status = "PASSED" if valid else "FAILED"
            return f"Claim validity check {status} across {checks_cnt} document date(s)."

        # Missing Document Tool Summary
        elif tool_name == "missing_document_tool":
            missing = [d for d in result.get("missing_documents", []) if d.get("missing")]
            total_req = len(result.get("required_documents", []))
            return f"Missing document analysis complete: {len(missing)} missing out of {total_req} required."

        return f"Tool '{tool_name}' executed successfully."

    def get_history(self) -> List[Dict[str, Any]]:
        """Return operational tool execution history."""
        return list(self.execution_history)

    def clear_history(self) -> None:
        """Clear operational execution history."""
        self.execution_history.clear()
