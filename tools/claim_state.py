"""tools/claim_state.py
Shared Claim State Model for InsureMate.
Provides a lightweight, predictable state container allowing the Phase 5 Agent
to maintain context across multiple independent tool invocations.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone


class ClaimState:
    """
    Lightweight Claim State container for Agent-Tool coordination.

    Maintains contextual outputs across multiple tool calls without enforcing
    any fixed sequence or rigid pipeline order.
    """

    def __init__(
        self,
        claim_id: Optional[str] = None,
        documents: Optional[List[Any]] = None,
        extracted_data: Optional[Dict[str, Any]] = None,
        validation_results: Optional[Dict[str, Any]] = None,
        validity_results: Optional[Dict[str, Any]] = None,
        missing_documents: Optional[List[Dict[str, Any]]] = None,
        tool_history: Optional[List[Dict[str, Any]]] = None,
        current_step: Optional[str] = None,
        final_result: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.claim_id: str = claim_id or f"CLM-{int(datetime.now(timezone.utc).timestamp())}"
        self.documents: List[Any] = list(documents or [])
        self.extracted_data: Dict[str, Any] = dict(extracted_data or {})
        self.validation_results: Dict[str, Any] = dict(validation_results or {})
        self.validity_results: Dict[str, Any] = dict(validity_results or {})
        self.missing_documents: List[Dict[str, Any]] = list(missing_documents or [])
        self.tool_history: List[Dict[str, Any]] = list(tool_history or [])
        self.current_step: Optional[str] = current_step
        self.final_result: Optional[Dict[str, Any]] = final_result
        self.metadata: Dict[str, Any] = dict(metadata or {})

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to a plain JSON-serializable dictionary."""
        return {
            "claim_id": self.claim_id,
            "documents": self.documents,
            "extracted_data": self.extracted_data,
            "validation_results": self.validation_results,
            "validity_results": self.validity_results,
            "missing_documents": self.missing_documents,
            "tool_history": self.tool_history,
            "current_step": self.current_step,
            "final_result": self.final_result,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClaimState":
        """Instantiate ClaimState from an existing dictionary."""
        return cls(
            claim_id=data.get("claim_id"),
            documents=data.get("documents"),
            extracted_data=data.get("extracted_data"),
            validation_results=data.get("validation_results"),
            validity_results=data.get("validity_results"),
            missing_documents=data.get("missing_documents"),
            tool_history=data.get("tool_history"),
            current_step=data.get("current_step"),
            final_result=data.get("final_result"),
            metadata=data.get("metadata"),
        )

    def record_history(self, entry: Dict[str, Any]) -> None:
        """Append an operational record to the tool history log."""
        self.tool_history.append(entry)

    def update_from_tool_result(self, tool_name: str, result: Dict[str, Any]) -> None:
        """
        Update appropriate state fields based on the executed tool's output.
        Normalizes outputs flexibly regardless of whether result comes directly from
        tool.execute() or from ToolExecutor.
        """
        if not isinstance(result, dict):
            return

        # Unwrap if inside executor wrapper {"success": True, "result": {...}}
        payload = result.get("result") if ("result" in result and "success" in result) else result
        if not isinstance(payload, dict):
            return

        if "claim_id" in payload and payload["claim_id"]:
            self.claim_id = str(payload["claim_id"])

        if tool_name in ("document_extraction_tool", "qwen_vl_extraction_tool"):
            if "extracted_data" in payload:
                self.extracted_data = payload["extracted_data"]
            elif "extracted_documents" in payload:
                self.extracted_data = {
                    "total_pages": payload.get("total_pages", len(payload["extracted_documents"])),
                    "extracted_documents": payload["extracted_documents"],
                }
            if "documents_processed" in payload:
                for doc in payload["documents_processed"]:
                    if doc not in self.documents:
                        self.documents.append(doc)
            self.current_step = "document_extraction_completed"

        elif tool_name == "document_validation_tool":
            if "validation_results" in payload:
                self.validation_results = payload["validation_results"]
            elif "validation_result" in payload:
                self.validation_results = payload["validation_result"]
            self.current_step = "document_validation_completed"

        elif tool_name == "validity_checker_tool":
            if "validity_results" in payload:
                self.validity_results = payload["validity_results"]
            else:
                self.validity_results = {
                    "valid": payload.get("valid", False),
                    "policy_period": payload.get("policy_period", {}),
                    "reasons": payload.get("reasons", []),
                    "checks": payload.get("checks", []),
                    "identity_match": payload.get("identity_match"),
                }
            self.current_step = "validity_check_completed"

        elif tool_name == "missing_document_tool":
            if "missing_documents" in payload:
                self.missing_documents = payload["missing_documents"]
            elif "document_results" in payload:
                self.missing_documents = payload["document_results"]
            self.current_step = "missing_document_analysis_completed"

    # Dict-like access compatibility for ease of use in Phase 5
    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def __setitem__(self, key: str, value: Any) -> None:
        setattr(self, key, value)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
