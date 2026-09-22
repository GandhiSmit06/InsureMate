"""
Adapters and mock fixtures for Phase 1 ingestion data.
"""

from .phase1_adapter import Phase1InputAdapter
from .mock_inputs import (
    create_mock_hospital_invoice,
    create_mock_discharge_summary,
    create_mock_prescription,
    create_mock_diagnostic_report,
    create_mock_poor_ocr,
    create_mock_conflicting_dates,
    create_mock_blank_document,
)

__all__ = [
    "Phase1InputAdapter",
    "create_mock_hospital_invoice",
    "create_mock_discharge_summary",
    "create_mock_prescription",
    "create_mock_diagnostic_report",
    "create_mock_poor_ocr",
    "create_mock_conflicting_dates",
    "create_mock_blank_document",
]
