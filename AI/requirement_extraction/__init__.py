"""InsureMate Phase 3: Medical Insurance Requirement Extraction Engine.

Extracts structured, explainable claim requirements directly from
insurance policy documents (PDF, text, or pre-extracted pages).
"""

from .engine import RequirementExtractionEngine
from .schema.models import (
    PageText,
    RequirementItem,
    Phase3Request,
    Phase3Response,
    ExtractionSummary,
    Category,
    Priority,
)
from .config import config

__version__ = "1.0.0"
__all__ = [
    "RequirementExtractionEngine",
    "PageText",
    "RequirementItem",
    "Phase3Request",
    "Phase3Response",
    "ExtractionSummary",
    "Category",
    "Priority",
    "config",
]
