"""
Configuration settings and constants for Phase 2 Document Understanding.
"""

from typing import Set, Dict, List

# Supported document types for hints
SUPPORTED_DOC_TYPES: List[str] = [
    "hospital_invoice",
    "medical_bill",
    "discharge_summary",
    "prescription",
    "diagnostic_report",
    "admission_document",
    "insurance_form",
    "incident_document",
    "unknown",
]

# Supported Currencies and Symbols
CURRENCY_MAP: Dict[str, str] = {
    "₹": "INR",
    "rs": "INR",
    "rs.": "INR",
    "inr": "INR",
    "$": "USD",
    "usd": "USD",
    "€": "EUR",
    "eur": "EUR",
    "£": "GBP",
    "gbp": "GBP",
}

# Quality thresholds
GARBLED_CHAR_RATIO_THRESHOLD: float = 0.12  # Above 12% garbled characters raises a quality warning
MIN_REASONABLE_YEAR: int = 1920
MAX_REASONABLE_YEAR: int = 2050

# Default confidence thresholds
CONFIDENCE_HIGH: float = 0.80
CONFIDENCE_MEDIUM: float = 0.50
