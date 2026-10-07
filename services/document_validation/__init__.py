"""
services/document_validation package initialization.
"""

from services.document_validation.validator import (
    DocumentValidator,
    SingleDocumentValidationResult,
    DocumentValidationBatchResult,
    document_validation,
    DEFAULT_DOCUMENT_REQUIREMENTS,
    SUPPORTED_DOCUMENT_TYPES,
)

__all__ = [
    "DocumentValidator",
    "SingleDocumentValidationResult",
    "DocumentValidationBatchResult",
    "document_validation",
    "DEFAULT_DOCUMENT_REQUIREMENTS",
    "SUPPORTED_DOCUMENT_TYPES",
]
