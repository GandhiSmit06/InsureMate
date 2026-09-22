"""
InsureMate — Phase 2: Document Understanding Module.
Provides structured, provenance-tracked, and quality-evaluated extraction
from ingested medical, billing, and incident documents.
"""

from .pipeline import DocumentUnderstandingPipeline
from .schemas.output_schema import DocumentUnderstandingResult
from .schemas.input_schema import IngestedDocument, RawPageInput, RawTableInput, RawBlockInput
from .schemas.common import FieldStatus, ConfidenceLevel, Provenance, BoundingBox, FieldValue
from .adapters.phase1_adapter import Phase1InputAdapter

__version__ = "1.0.0"

__all__ = [
    "DocumentUnderstandingPipeline",
    "DocumentUnderstandingResult",
    "IngestedDocument",
    "RawPageInput",
    "RawTableInput",
    "RawBlockInput",
    "FieldStatus",
    "ConfidenceLevel",
    "Provenance",
    "BoundingBox",
    "FieldValue",
    "Phase1InputAdapter",
]
