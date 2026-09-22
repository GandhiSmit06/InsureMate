"""
Common enums, models, and provenance structures for Document Understanding.
"""

from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field, ConfigDict


class FieldStatus(str, Enum):
    """Explicit status concept for any field or extraction target."""
    EXTRACTED = "extracted"
    NOT_FOUND = "not_found"
    UNREADABLE = "unreadable"
    AMBIGUOUS = "ambiguous"
    EXTRACTION_ERROR = "extraction_error"


class ConfidenceLevel(str, Enum):
    """Categorical confidence level based on documented rules."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNAVAILABLE = "unavailable"


class BoundingBox(BaseModel):
    """Coordinates of an extracted element within a page."""
    model_config = ConfigDict(frozen=True)

    x0: float = Field(..., description="Left coordinate")
    y0: float = Field(..., description="Top coordinate")
    x1: float = Field(..., description="Right coordinate")
    y1: float = Field(..., description="Bottom coordinate")
    page_number: int = Field(..., ge=1, description="1-indexed page number")
    unit: str = Field(default="pt", description="Coordinate unit (e.g. pt, px, norm)")


class Provenance(BaseModel):
    """Evidence traceability for every extracted field."""
    model_config = ConfigDict(frozen=True)

    document_id: str = Field(..., description="Unique document identifier")
    page_number: int = Field(..., ge=1, description="1-indexed page number where the field was found")
    source_text: str = Field(..., description="Exact or verbatim source text excerpt")
    bounding_box: Optional[BoundingBox] = Field(default=None, description="Bounding box if available")
    extraction_method: str = Field(..., description="Method used (e.g. regex, key_value_heuristic, table_parser)")
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.HIGH, description="Confidence level")
    confidence_score: Optional[float] = Field(
        default=None, 
        ge=0.0, 
        le=1.0, 
        description="Optional calibrated score (0.0 to 1.0) if supported, otherwise null"
    )


class FieldValue(BaseModel):
    """Generic wrapper for extracted values preserving status and provenance."""
    value: Optional[Any] = Field(default=None, description="Normalized or parsed value")
    raw_text: Optional[str] = Field(default=None, description="Original verbatim text from document")
    status: FieldStatus = Field(default=FieldStatus.EXTRACTED, description="Extraction status")
    provenance: Optional[Provenance] = Field(default=None, description="Source provenance")
    notes: Optional[str] = Field(default=None, description="Explanation for ambiguous or unreadable status")
