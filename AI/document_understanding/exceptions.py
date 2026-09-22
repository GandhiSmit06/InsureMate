"""
Module-specific exceptions for Document Understanding.
"""


class DocumentUnderstandingError(Exception):
    """Base exception for all Document Understanding errors."""
    pass


class InvalidInputError(DocumentUnderstandingError):
    """Raised when the input from Phase 1 is missing, malformed, or invalid."""
    pass


class NormalizationError(DocumentUnderstandingError):
    """Raised when text, date, or financial normalization fails unrecoverably."""
    pass


class ExtractionError(DocumentUnderstandingError):
    """Raised when extraction engines fail to process document content."""
    pass


class QualityCheckError(DocumentUnderstandingError):
    """Raised during document quality evaluation."""
    pass
