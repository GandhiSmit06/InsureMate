"""Output schema definitions and strict validation for Phase 4.

Ensures LLM response conforms to the required Phase 4 format:
{
  "missing_documents": [
    {
      "sr_no": 1,
      "document_title": "Discharge Summary",
      "missing": false,
      "page_no": 5
    }
  ]
}
"""
from typing import List, Optional, Any, Union
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


class Phase4ValidationError(Exception):
    """Exception raised when LLM output violates Phase 4 schema or semantic constraints."""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class MissingDocumentItem(BaseModel):
    """A single missing-document detection item."""
    model_config = ConfigDict(extra="forbid")

    sr_no: int = Field(
        ...,
        ge=1,
        description="Sequential serial number starting from 1."
    )
    document_title: str = Field(
        ...,
        min_length=1,
        description="The required policy document title."
    )
    missing: bool = Field(
        ...,
        description="True if the required document is missing, False otherwise."
    )
    page_no: Optional[int] = Field(
        default=None,
        description="Page number where the document is found, or null if missing."
    )

    @field_validator("missing", mode="before")
    @classmethod
    def validate_strict_bool(cls, v: Any) -> bool:
        """Ensure missing is strictly a boolean."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            if v.lower() == "true":
                return True
            if v.lower() == "false":
                return False
        raise ValueError(f"'missing' must be a boolean (true/false), got {type(v).__name__}: {v!r}")

    @field_validator("page_no", mode="before")
    @classmethod
    def validate_page_no_type(cls, v: Any) -> Optional[int]:
        """Ensure page_no is integer or None."""
        if v is None:
            return None
        if isinstance(v, int) and not isinstance(v, bool):
            if v < 1:
                raise ValueError(f"'page_no' must be a positive integer, got {v}")
            return v
        if isinstance(v, str) and v.isdigit():
            val = int(v)
            if val < 1:
                raise ValueError(f"'page_no' must be a positive integer, got {val}")
            return val
        raise ValueError(f"'page_no' must be an integer or null, got {type(v).__name__}: {v!r}")

    @model_validator(mode="after")
    def validate_missing_and_page_correlation(self) -> "MissingDocumentItem":
        """Cross-validate missing status and page_no."""
        if self.missing is True:
            if self.page_no is not None:
                raise ValueError(
                    f"Document '{self.document_title}' is marked missing=true, so 'page_no' must be null, but got {self.page_no}"
                )
        else:
            if self.page_no is None:
                raise ValueError(
                    f"Document '{self.document_title}' is marked missing=false, so 'page_no' must be an integer page number, but got null"
                )
        return self


class MissingDocumentsResponse(BaseModel):
    """The root output wrapper for Phase 4 detection."""
    model_config = ConfigDict(extra="forbid")

    missing_documents: List[MissingDocumentItem] = Field(
        ...,
        description="Array of missing document detection items."
    )


def validate_output_against_requirements(
    response_data: Any,
    required_titles: List[str]
) -> MissingDocumentsResponse:
    """Strictly validate parsed LLM response against the expected schema and policy requirements.

    Validation rules:
    - missing_documents exists and is a list
    - every item matches MissingDocumentItem schema
    - number of items equals number of policy requirements
    - sr_no starts at 1 and is strictly sequential (1, 2, 3...)
    - every required policy document appears exactly once in the response
    - document_title matches the required policy document title
    - order matches policy requirements order

    Args:
        response_data: Parsed dictionary from LLM JSON response.
        required_titles: List of expected document_title strings from policy_requirements.

    Returns:
        Validated MissingDocumentsResponse instance.

    Raises:
        Phase4ValidationError: If any rule is violated.
    """
    if not isinstance(response_data, dict):
        raise Phase4ValidationError(
            f"Expected JSON root to be an object/dict, got {type(response_data).__name__}"
        )

    if "missing_documents" not in response_data:
        raise Phase4ValidationError(
            "Missing required top-level key 'missing_documents' in JSON response."
        )

    extra_keys = set(response_data.keys()) - {"missing_documents"}
    if extra_keys:
        raise Phase4ValidationError(
            f"Extraneous top-level keys found: {list(extra_keys)}. Only 'missing_documents' is allowed."
        )

    raw_items = response_data.get("missing_documents")
    if not isinstance(raw_items, list):
        raise Phase4ValidationError(
            f"'missing_documents' must be an array/list, got {type(raw_items).__name__}"
        )

    expected_count = len(required_titles)
    actual_count = len(raw_items)
    if actual_count != expected_count:
        raise Phase4ValidationError(
            f"Item count mismatch: expected {expected_count} items matching policy requirements, but got {actual_count} items."
        )

    # Validate individual items through Pydantic
    validated_items: List[MissingDocumentItem] = []
    seen_titles = []

    for idx, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            raise Phase4ValidationError(
                f"Item at index {idx} must be an object/dict, got {type(item).__name__}"
            )

        try:
            val_item = MissingDocumentItem.model_validate(item)
        except Exception as e:
            raise Phase4ValidationError(f"Item at index {idx} failed schema validation: {e}")

        # Check sequential sr_no
        if val_item.sr_no != idx:
            raise Phase4ValidationError(
                f"Item at index {idx} has invalid sr_no={val_item.sr_no}. sr_no must start at 1 and be sequential (expected {idx})."
            )

        # Check title matches policy requirement at this index (preserves order)
        expected_title = required_titles[idx - 1]
        if val_item.document_title.strip().lower() != expected_title.strip().lower():
            raise Phase4ValidationError(
                f"Item sr_no={idx} has document_title '{val_item.document_title}', but expected required policy document '{expected_title}'."
            )

        # Canonicalize title to the exact policy requirement title string
        val_item.document_title = expected_title

        seen_titles.append(val_item.document_title)
        validated_items.append(val_item)

    # Check that all required titles appear exactly once
    if len(seen_titles) != len(set(seen_titles)):
        raise Phase4ValidationError("Duplicate document titles found in missing_documents response.")

    return MissingDocumentsResponse(missing_documents=validated_items)
