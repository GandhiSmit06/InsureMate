"""Input schema definitions for Phase 4 Missing-Document Detection.

Defines the structure expected from Phase 3 pipeline output.
"""
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class PolicyRequirement(BaseModel):
    """A document required by the insurance policy."""
    model_config = ConfigDict(extra="forbid")

    document_title: str = Field(
        ...,
        min_length=1,
        description="The formal title/category of the required document."
    )


class SubmittedDocument(BaseModel):
    """A document classified and extracted from submitted claim files."""
    model_config = ConfigDict(extra="forbid")

    document_title: str = Field(
        ...,
        min_length=1,
        description="The title/category of the document as detected in the claim."
    )
    page_no: int = Field(
        ...,
        ge=1,
        description="Page number in the claim bundle where this document is located."
    )


class Phase3Data(BaseModel):
    """The complete payload passed from Phase 3 to Phase 4."""
    model_config = ConfigDict(extra="forbid")

    policy_requirements: List[PolicyRequirement] = Field(
        ...,
        min_length=1,
        description="List of documents required by the insurance policy."
    )
    submitted_documents: List[SubmittedDocument] = Field(
        default_factory=list,
        description="List of documents submitted with page numbers."
    )
