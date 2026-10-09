"""services/missing_document/schemas.py
Pydantic data models and strict validation for Phase 4 Missing Document Detection.
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


class Phase4ValidationError(Exception):
    """Raised when LLM output violates schema or business constraints."""
    pass


class RequiredDocumentDefinition(BaseModel):
    """Definition of a document required by the insurance policy."""
    model_config = ConfigDict(extra="ignore")

    sr_no: int = Field(..., ge=1, description="1-indexed sequential requirement number.")
    document_title: str = Field(..., min_length=1, description="Canonical title of the required document.")
    source: str = Field(default="policy", description="Source of requirement: policy clause, condition, or terms.")
    reason: Optional[str] = Field(default=None, description="Explanation why this document is required.")


class DocumentResultItem(BaseModel):
    """Result of semantic matching for a single required document."""
    model_config = ConfigDict(extra="ignore")

    sr_no: int = Field(..., ge=1, description="Sequential index matching required document.")
    document_title: str = Field(..., min_length=1, description="Title of required document.")
    missing: bool = Field(..., description="True if document is missing, False if present.")
    page_number: Optional[int] = Field(default=None, description="Exact 1-indexed page number from Phase 1, or null if missing.")
    matched_submitted_document: Optional[str] = Field(default=None, description="Title of matching submitted document, or null if missing.")
    reason: str = Field(default="", description="Detailed reasoning for match or missing determination.")

    @field_validator("missing", mode="before")
    @classmethod
    def validate_strict_bool(cls, v: Any) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            if v.lower() in ("true", "yes", "1"):
                return True
            if v.lower() in ("false", "no", "0"):
                return False
        raise ValueError(f"'missing' must be a boolean (True/False), got {type(v).__name__}: {v!r}")

    @field_validator("page_number", mode="before")
    @classmethod
    def validate_page_number_type(cls, v: Any) -> Optional[int]:
        if v is None or v == "null" or v == "":
            return None
        if isinstance(v, int) and not isinstance(v, bool):
            if v < 1:
                raise ValueError(f"'page_number' must be a positive integer, got {v}")
            return v
        if isinstance(v, str) and v.isdigit():
            val = int(v)
            if val < 1:
                raise ValueError(f"'page_number' must be a positive integer, got {val}")
            return val
        raise ValueError(f"'page_number' must be an integer or null, got {type(v).__name__}: {v!r}")

    @model_validator(mode="after")
    def validate_missing_page_correlation(self) -> "DocumentResultItem":
        if self.missing is True:
            if self.page_number is not None:
                raise ValueError(
                    f"Document '{self.document_title}' is marked missing=True, so 'page_number' must be null, but got {self.page_number}"
                )
            self.matched_submitted_document = None
        else:
            if self.page_number is None:
                raise ValueError(
                    f"Document '{self.document_title}' is marked missing=False, so 'page_number' must be a positive integer from Phase 1, but got null"
                )
            if not self.matched_submitted_document:
                self.matched_submitted_document = self.document_title
        return self


class MissingDocumentSummary(BaseModel):
    """Aggregate counts for detection results."""
    model_config = ConfigDict(extra="ignore")

    total_required: int = Field(default=0, ge=0)
    present: int = Field(default=0, ge=0)
    missing: int = Field(default=0, ge=0)
    total_found: int = Field(default=0, ge=0)
    total_missing: int = Field(default=0, ge=0)

    @model_validator(mode="before")
    @classmethod
    def populate_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            present = data.get("present", data.get("total_found", 0))
            missing = data.get("missing", data.get("total_missing", 0))
            data["present"] = present
            data["missing"] = missing
            data["total_found"] = present
            data["total_missing"] = missing
        return data


class MissingDocumentResponse(BaseModel):
    """Standardized root output object for Phase 4 Missing Document Detection."""
    model_config = ConfigDict(extra="ignore")

    status: str = Field(default="success")
    tool: str = Field(default="missing_document_tool")
    required_documents: List[RequiredDocumentDefinition] = Field(default_factory=list)
    document_results: List[DocumentResultItem] = Field(default_factory=list)
    summary: MissingDocumentSummary = Field(default_factory=MissingDocumentSummary)
    reason: Optional[str] = Field(default=None)
    error: Optional[Any] = Field(default=None)

    @property
    def missing_documents(self) -> List[Dict[str, Any]]:
        """Convenience property mapping document_results with page_no compatibility."""
        return [
            {
                "sr_no": r.sr_no,
                "document_title": r.document_title,
                "required_document": r.document_title,
                "document_name": r.document_title,
                "name": r.document_title,
                "missing": r.missing,
                "page_number": r.page_number,
                "page_no": r.page_number,
                "matched_submitted_document": r.matched_submitted_document,
                "submitted_document_title": r.matched_submitted_document,
                "reason": r.reason,
            }
            for r in self.document_results
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "tool": self.tool,
            "required_documents": [doc.model_dump() for doc in self.required_documents],
            "document_results": [r.model_dump() for r in self.document_results],
            "missing_documents": self.missing_documents,
            "summary": self.summary.model_dump(),
            "reason": self.reason,
            "error": self.error,
        }

    def to_table(self) -> str:
        """Format as markdown decision table:
        | Sr.No | Document Title | Missing or not | Page No. |
        """
        lines = [
            "| Sr.No | Document Title | Missing or not | Page No. |",
            "| :---: | :------------- | :------------: | :------: |"
        ]
        if not self.document_results:
            lines.append("| - | No required documents specified in policy | - | - |")
            return "\n".join(lines)

        for doc in self.document_results:
            missing_text = "Yes" if doc.missing else "No"
            page_text = str(doc.page_number) if doc.page_number is not None else "null"
            lines.append(f"| {doc.sr_no} | {doc.document_title} | {missing_text} | {page_text} |")
        return "\n".join(lines)


def validate_detection_output(
    response_data: Any,
    valid_submitted_pages: Optional[List[int]] = None
) -> MissingDocumentResponse:
    """Strictly validates LLM output JSON against schema and constraints."""
    if not isinstance(response_data, dict):
        raise Phase4ValidationError(f"Expected JSON root to be an object/dict, got {type(response_data).__name__}")

    raw_reqs = response_data.get("required_documents", [])
    raw_results = response_data.get("document_results")
    if raw_results is None:
        raw_results = response_data.get("missing_documents")
    if raw_results is None:
        raise Phase4ValidationError("LLM response missing required root key 'document_results' or 'missing_documents'.")

    if not isinstance(raw_reqs, list):
        raise Phase4ValidationError(f"'required_documents' must be a list, got {type(raw_reqs).__name__}")
    if not isinstance(raw_results, list):
        raise Phase4ValidationError(f"'document_results' must be a list, got {type(raw_results).__name__}")

    validated_reqs: List[RequiredDocumentDefinition] = []
    for idx, req in enumerate(raw_reqs, start=1):
        if not isinstance(req, dict):
            raise Phase4ValidationError(f"Required document item {idx} must be a dict.")
        if "sr_no" not in req or req["sr_no"] != idx:
            req["sr_no"] = idx
        try:
            val_req = RequiredDocumentDefinition.model_validate(req)
            validated_reqs.append(val_req)
        except Exception as e:
            raise Phase4ValidationError(f"Failed validating required_document {idx}: {e}")

    validated_results: List[DocumentResultItem] = []
    valid_page_set = set(valid_submitted_pages or [])

    for idx, item in enumerate(raw_results, start=1):
        if not isinstance(item, dict):
            raise Phase4ValidationError(f"Document result item {idx} must be a dict.")
        if "sr_no" not in item or item["sr_no"] != idx:
            item["sr_no"] = idx

        # Standardize page_number / page_no
        if "page_number" not in item and "page_no" in item:
            item["page_number"] = item["page_no"]

        # Standardize matched_submitted_document / submitted_document_title
        if "matched_submitted_document" not in item and "submitted_document_title" in item:
            item["matched_submitted_document"] = item["submitted_document_title"]

        try:
            val_item = DocumentResultItem.model_validate(item)
        except Exception as e:
            raise Phase4ValidationError(f"Failed validating document_result {idx}: {e}")

        # Check page_number integrity against submitted Phase 1 pages
        if not val_item.missing and val_item.page_number is not None and valid_page_set:
            if val_item.page_number not in valid_page_set:
                raise Phase4ValidationError(
                    f"Page {val_item.page_number} for '{val_item.document_title}' does not exist in submitted Phase 1 documents (valid pages: {sorted(list(valid_page_set))})"
                )

        validated_results.append(val_item)

    total_req = len(validated_results) if validated_results else len(validated_reqs)
    present_cnt = sum(1 for d in validated_results if not d.missing)
    missing_cnt = sum(1 for d in validated_results if d.missing)

    summary = MissingDocumentSummary(
        total_required=total_req,
        present=present_cnt,
        missing=missing_cnt,
        total_found=present_cnt,
        total_missing=missing_cnt,
    )

    return MissingDocumentResponse(
        status="success",
        tool="missing_document_tool",
        required_documents=validated_reqs,
        document_results=validated_results,
        summary=summary,
        reason=response_data.get("reason"),
        error=None
    )
