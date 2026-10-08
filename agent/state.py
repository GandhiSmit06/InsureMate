"""agent/state.py
Working state for InsureMate claim processing session.
Maintains context, intermediate tool observations, plans, execution trace, and final status.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class ClaimStatus(str, Enum):
    INITIALIZED = "INITIALIZED"
    IN_PROGRESS = "IN_PROGRESS"
    CLAIM_READY_FOR_SUBMISSION = "CLAIM_READY_FOR_SUBMISSION"
    ACTION_REQUIRED_MISSING_EVIDENCE = "ACTION_REQUIRED_MISSING_EVIDENCE"
    ACTION_REQUIRED_INVALID_DOCUMENTS = "ACTION_REQUIRED_INVALID_DOCUMENTS"
    INVALID_CLAIM_DATES = "INVALID_CLAIM_DATES"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"
    FAILED = "FAILED"


@dataclass
class ToolHistoryEntry:
    tool_name: str
    status: str
    summary: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    inputs_summary: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TraceEntry:
    step_number: int
    decision: str
    tool: Optional[str]
    tool_result: Optional[str]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ClaimState:
    """
    Central claim session working state.
    Preserves context, memory, and intermediate observations across tool invocations.
    """
    claim_id: str = field(default_factory=lambda: f"claim-{uuid.uuid4().hex[:8]}")
    goal: str = "Analyze this insurance claim and determine whether the submitted documents are valid and whether any required evidence is missing."
    documents: List[str] = field(default_factory=list)
    document_classifications: Dict[int, str] = field(default_factory=dict)
    page_numbers: List[int] = field(default_factory=list)
    extracted_data: List[Dict[str, Any]] = field(default_factory=list)
    validation_result: Optional[Dict[str, Any]] = None
    validity_result: Optional[Dict[str, Any]] = None
    missing_documents: Optional[Dict[str, Any]] = None
    current_plan: Optional[Dict[str, Any]] = None
    current_step: Optional[str] = None
    completed_steps: List[str] = field(default_factory=list)
    tool_history: List[Dict[str, Any]] = field(default_factory=list)
    execution_trace: List[Dict[str, Any]] = field(default_factory=list)
    final_status: Optional[str] = None
    final_report: Optional[Dict[str, Any]] = None
    errors: List[str] = field(default_factory=list)
    retry_counts: Dict[str, int] = field(default_factory=dict)
    max_iterations: int = 10
    iteration_count: int = 0

    def record_tool_execution(
        self,
        tool_name: str,
        status: str,
        summary: str,
        inputs_summary: Optional[str] = None,
        error: Optional[str] = None
    ) -> None:
        """Record tool execution in tool history."""
        entry = ToolHistoryEntry(
            tool_name=tool_name,
            status=status,
            summary=summary,
            inputs_summary=inputs_summary,
            error=error
        )
        self.tool_history.append(entry.to_dict())

    def record_trace(
        self,
        decision: str,
        tool: Optional[str] = None,
        tool_result: Optional[str] = None
    ) -> None:
        """Record human-readable trace entry without exposing internal private CoT."""
        entry = TraceEntry(
            step_number=len(self.execution_trace) + 1,
            decision=decision,
            tool=tool,
            tool_result=tool_result
        )
        self.execution_trace.append(entry.to_dict())

    def mark_step_completed(self, step_name: str) -> None:
        """Mark a step as completed in current state and update current plan."""
        if step_name not in self.completed_steps:
            self.completed_steps.append(step_name)

        if self.current_plan and "steps" in self.current_plan:
            for step in self.current_plan["steps"]:
                if step.get("action") == step_name:
                    step["status"] = "completed"

    def mark_step_failed(self, step_name: str, error_msg: str) -> None:
        """Record step failure and log error."""
        self.errors.append(f"{step_name}: {error_msg}")
        if self.current_plan and "steps" in self.current_plan:
            for step in self.current_plan["steps"]:
                if step.get("action") == step_name:
                    step["status"] = "failed"

    def can_retry(self, tool_name: str, max_retries: int = 1) -> bool:
        """Check if a tool can be retried (at most once)."""
        current_retries = self.retry_counts.get(tool_name, 0)
        return current_retries < max_retries

    def increment_retry(self, tool_name: str) -> None:
        """Increment retry count for tool."""
        self.retry_counts[tool_name] = self.retry_counts.get(tool_name, 0) + 1

    def is_finished(self) -> bool:
        """Check if claim execution has reached a terminal status."""
        return self.final_status is not None

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to a clean JSON-serializable dictionary."""
        return {
            "claim_id": self.claim_id,
            "goal": self.goal,
            "documents": self.documents,
            "document_classifications": self.document_classifications,
            "page_numbers": self.page_numbers,
            "extracted_data": self.extracted_data,
            "validation_result": self.validation_result,
            "validity_result": self.validity_result,
            "missing_documents": self.missing_documents,
            "current_plan": self.current_plan,
            "current_step": self.current_step,
            "completed_steps": self.completed_steps,
            "tool_history": self.tool_history,
            "execution_trace": self.execution_trace,
            "final_status": self.final_status,
            "final_report": self.final_report,
            "errors": self.errors,
            "iteration_count": self.iteration_count,
        }

    @property
    def validation_results(self) -> Optional[Dict[str, Any]]:
        return self.validation_result

    @validation_results.setter
    def validation_results(self, val: Optional[Dict[str, Any]]) -> None:
        self.validation_result = val

    @property
    def validity_results(self) -> Optional[Dict[str, Any]]:
        return self.validity_result

    @validity_results.setter
    def validity_results(self, val: Optional[Dict[str, Any]]) -> None:
        self.validity_result = val

    def record_history(self, entry: Dict[str, Any]) -> None:
        """Phase 6 compatible tool history logging."""
        self.tool_history.append(entry)

    def update_from_tool_result(self, tool_name: str, result: Dict[str, Any]) -> None:
        """Phase 6 compatible tool state updater."""
        if not isinstance(result, dict):
            return
        payload = result.get("result") if ("result" in result and "success" in result) else result
        if not isinstance(payload, dict):
            return

        if "claim_id" in payload and payload["claim_id"]:
            self.claim_id = str(payload["claim_id"])

        if tool_name in ("document_extraction_tool", "qwen_vl_extraction_tool", "document_extraction"):
            if "extracted_data" in payload:
                ed = payload["extracted_data"]
                if isinstance(ed, dict) and "extracted_documents" in ed:
                    self.extracted_data = ed["extracted_documents"]
                elif isinstance(ed, list):
                    self.extracted_data = ed
            elif "extracted_documents" in payload:
                self.extracted_data = payload["extracted_documents"]
            self.current_step = "document_extraction_completed"

        elif tool_name in ("document_validation_tool", "document_validation"):
            if "validation_results" in payload:
                self.validation_result = payload["validation_results"]
            elif "validation_result" in payload:
                self.validation_result = payload["validation_result"]
            self.current_step = "document_validation_completed"

        elif tool_name in ("validity_checker_tool", "validity_checker"):
            if "validity_results" in payload:
                self.validity_result = payload["validity_results"]
            elif "validity_result" in payload:
                self.validity_result = payload["validity_result"]
            self.current_step = "validity_checker_completed"

        elif tool_name in ("missing_document_tool", "missing_document_detector"):
            self.missing_documents = payload
            self.current_step = "missing_document_analysis_completed"

    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(key)

    def __setitem__(self, key: str, value: Any) -> None:
        setattr(self, key, value)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClaimState":
        """Instantiate ClaimState from dictionary."""
        filtered = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**filtered)

