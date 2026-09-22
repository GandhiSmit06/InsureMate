from __future__ import annotations
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class Category(str, Enum):
    DOCUMENT = "DOCUMENT"
    INFORMATION = "INFORMATION"
    CONDITION = "CONDITION"
    ACTION = "ACTION"
    DEADLINE = "DEADLINE"
    FINANCIAL = "FINANCIAL"


class Priority(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RequirementItem(BaseModel):
    """Structured Claim Requirement item extracted from insurance policy."""
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    requirement_id: str = Field(
        ...,
        description="Unique sequential identifier, e.g., REQ-001",
        examples=["REQ-001"],
    )
    category: Category = Field(
        ...,
        description="Requirement category: DOCUMENT, INFORMATION, CONDITION, ACTION, DEADLINE, FINANCIAL",
    )
    name: str = Field(
        ...,
        description="Canonical requirement name, e.g., Hospital Discharge Summary",
    )
    description: str = Field(
        ...,
        description="Clear description of what is required according to the policy",
    )
    mandatory: bool = Field(
        ...,
        description="Whether this requirement is mandatory (true) or optional/conditional (false)",
    )
    priority: Priority = Field(
        default=Priority.HIGH,
        description="Priority level: HIGH, MEDIUM, LOW",
    )
    applies_when: Optional[str] = Field(
        default=None,
        description="Context in which requirement applies, e.g., 'Hospitalization claim', 'Cashless admission'",
    )
    condition: Optional[str] = Field(
        default=None,
        description="Trigger condition if requirement is conditional, otherwise null",
    )
    deadline: Optional[str] = Field(
        default=None,
        description="Specific timeframe or deadline if stated in policy, otherwise null",
    )
    evidence_type: Optional[str] = Field(
        default=None,
        description="Type of evidence, e.g., hospital_document, financial_receipt, legal_document, claim_form",
    )
    required_information: List[str] = Field(
        default_factory=list,
        description="Required fields or data elements needed inside this document or action",
    )
    source_clause: Optional[str] = Field(
        default=None,
        description="Exact clause title or excerpt from policy text where requirement was found",
    )
    source_page: Optional[int] = Field(
        default=None,
        description="Page number in policy document where requirement is stated (1-indexed)",
    )


class PageText(BaseModel):
    """Represents text extracted from a specific page of a policy document."""
    page_number: int = Field(..., ge=1)
    text: str


class ExtractionSummary(BaseModel):
    """Summary metrics of the extraction process."""
    total_requirements: int = 0
    mandatory_count: int = 0
    conditional_count: int = 0
    categories: Dict[str, int] = Field(default_factory=dict)


class Phase3Request(BaseModel):
    """Request payload for requirement extraction."""
    claim_type: Optional[str] = Field(
        default=None,
        description="Optional claim type, e.g., 'hospitalization', 'cashless', 'reimbursement', 'accident'",
    )
    policy_text: Optional[str] = Field(
        default=None,
        description="Full text of the insurance policy if text input is used",
    )
    policy_name: Optional[str] = Field(
        default=None,
        description="Optional policy name or title",
    )


class Phase3Response(BaseModel):
    """Strict JSON Response for Phase 3 Requirement Extraction."""
    model_config = ConfigDict(populate_by_name=True)

    success: bool = True
    claim_type: Optional[str] = None
    policy_name: Optional[str] = None
    summary: Optional[ExtractionSummary] = None
    requirements: List[RequirementItem] = Field(default_factory=list)
    error: Optional[str] = None
