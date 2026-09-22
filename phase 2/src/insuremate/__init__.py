"""
InsureMate — AI-Based Insurance Claim Preparation Agent.
A multi-module system for analyzing policy documents, medical records, and incident evidence.
"""

from .document_understanding import (
    DocumentUnderstandingPipeline,
    DocumentUnderstandingResult,
    FieldStatus,
    ConfidenceLevel,
    Provenance,
    BoundingBox,
    FieldValue,
    IngestedDocument,
    RawPageInput,
    RawTableInput,
    RawBlockInput,
    Phase1InputAdapter,
)

__version__ = "0.1.0"

__all__ = [
    "DocumentUnderstandingPipeline",
    "DocumentUnderstandingResult",
    "FieldStatus",
    "ConfidenceLevel",
    "Provenance",
    "BoundingBox",
    "FieldValue",
    "IngestedDocument",
    "RawPageInput",
    "RawTableInput",
    "RawBlockInput",
    "Phase1InputAdapter",
]
