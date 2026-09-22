"""
Test suite configuration and shared fixtures for Phase 2 Document Understanding.
"""

import sys
from pathlib import Path
import pytest

# Ensure src is in python path
src_path = Path(__file__).resolve().parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from insuremate.document_understanding.adapters.mock_inputs import (
    create_mock_hospital_invoice,
    create_mock_discharge_summary,
    create_mock_prescription,
    create_mock_diagnostic_report,
    create_mock_poor_ocr,
    create_mock_conflicting_dates,
    create_mock_blank_document,
)
from insuremate.document_understanding.pipeline import DocumentUnderstandingPipeline


@pytest.fixture
def pipeline():
    return DocumentUnderstandingPipeline()


@pytest.fixture
def mock_invoice():
    return create_mock_hospital_invoice()


@pytest.fixture
def mock_discharge_summary():
    return create_mock_discharge_summary()


@pytest.fixture
def mock_prescription():
    return create_mock_prescription()


@pytest.fixture
def mock_diagnostic_report():
    return create_mock_diagnostic_report()


@pytest.fixture
def mock_poor_ocr():
    return create_mock_poor_ocr()


@pytest.fixture
def mock_conflicting_dates():
    return create_mock_conflicting_dates()


@pytest.fixture
def mock_blank():
    return create_mock_blank_document()
