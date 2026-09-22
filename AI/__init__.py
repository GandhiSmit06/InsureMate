"""
InsureMate AI Package
Unified AI pipeline for insurance document processing.

Modules:
  - documentIngestion: PDF reading, validation, and PaddleOCR-based text extraction.
  - document_understanding: Structured understanding, entity extraction, quality evaluation.
  - insuremate_pipeline: End-to-end PDF → structured result pipeline.

Note: Heavy dependencies (PaddleOCR, PyMuPDF) are imported lazily.
      The document_understanding sub-package works independently without OCR dependencies.
"""

__version__ = "0.2.0"


def process_document(*args, **kwargs):
    """Lazy wrapper for the unified pipeline. Imports OCR dependencies only when called."""
    from .insuremate_pipeline import process_document as _process_document
    return _process_document(*args, **kwargs)


def ingest_document(*args, **kwargs):
    """Lazy wrapper for Phase 1 ingestion."""
    from .documentIngestion import ingest_document as _ingest_document
    return _ingest_document(*args, **kwargs)


# Phase 2 (document understanding) can always be imported directly
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

# Phase 3 (requirement extraction)
from .requirement_extraction import (
    RequirementExtractionEngine,
    PageText,
    RequirementItem,
    Phase3Request,
    Phase3Response,
    ExtractionSummary,
    Category,
    Priority,
)
from . import requirement_extraction

__all__ = [
    # Unified pipeline
    "process_document",
    # Phase 1: Ingestion (lazy)
    "ingest_document",
    # Phase 2: Document Understanding
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
    # Phase 3: Requirement Extraction
    "RequirementExtractionEngine",
    "PageText",
    "RequirementItem",
    "Phase3Request",
    "Phase3Response",
    "ExtractionSummary",
    "Category",
    "Priority",
    "requirement_extraction",
]
