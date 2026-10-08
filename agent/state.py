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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClaimState":
        """Instantiate ClaimState from dictionary."""
        filtered = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**filtered)
