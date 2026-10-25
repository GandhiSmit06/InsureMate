"""
tests/test_policy_validation.py
Comprehensive test suite for Phase 3: Intelligent Insurance Policy PDF Validation
and Phase 1-2 regression prevention.
"""

import io
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.server import app
from services.document_validation.policy_validator import validate_policy_pdf, PolicyValidationResult

ROOT_DIR = Path(__file__).resolve().parent.parent
POLICY_PDF = ROOT_DIR / "InsureMate_Test_Health_Insurance_Policy.pdf"
CLAIM_PDF = ROOT_DIR / "InsureMate_Test_Health_Insurance_Claim_Documents.pdf"
SAMPLE_POLICY = ROOT_DIR / "sample_policy.pdf"
SCANNED_POLICY = ROOT_DIR / "4225IELVT38453879200000_policy_copy.pdf"
CLAIM_A_PDF = ROOT_DIR / "claim_A.pdf"
HOSPITAL_DOC_PDF = ROOT_DIR / "claim_hospital_document.pdf"

client = TestClient(app)


def test_valid_insurance_policy_schedule_accepted():
    """Verify that a standard insurance policy schedule is recognized and accepted."""
    assert POLICY_PDF.exists(), f"Missing fixture {POLICY_PDF}"
    content = POLICY_PDF.read_bytes()
    res = validate_policy_pdf(content, filename=POLICY_PDF.name)
    assert res.valid is True
    assert res.document_type == "insurance_policy"
    assert res.confidence >= 0.70
    assert res.error is None


def test_valid_policy_alternative_layout_accepted():
    """Verify that an alternative policy layout/sample policy is accepted."""
    target = SAMPLE_POLICY if SAMPLE_POLICY.exists() else (ROOT_DIR / "policy_A.pdf")
    assert target.exists()
    content = target.read_bytes()
    res = validate_policy_pdf(content, filename=target.name)
    assert res.valid is True
    assert res.document_type == "insurance_policy"


def test_scanned_policy_requiring_native_ocr_accepted():
    """Verify that a scanned policy without digital text is recognized via native OCR."""
    if SCANNED_POLICY.exists():
        content = SCANNED_POLICY.read_bytes()
        res = validate_policy_pdf(content, filename=SCANNED_POLICY.name)
        assert res.valid is True
        assert res.document_type == "insurance_policy"


def test_hospital_claim_document_rejected_in_policy_slot():
    """Verify that hospital bills and claim documents uploaded in policy slot are rejected."""
    assert CLAIM_PDF.exists(), f"Missing fixture {CLAIM_PDF}"
    content = CLAIM_PDF.read_bytes()
    res = validate_policy_pdf(content, filename=CLAIM_PDF.name)
    assert res.valid is False
    assert "insurance policy" in res.error.lower()
    assert ("medical or hospital record" in res.error.lower() or "not appear to be an insurance policy" in res.error.lower())


def test_claim_document_a_rejected_in_policy_slot():
    """Verify that claim_A.pdf is rejected when evaluated as a policy."""
    if CLAIM_A_PDF.exists():
        content = CLAIM_A_PDF.read_bytes()
        res = validate_policy_pdf(content, filename=CLAIM_A_PDF.name)
        assert res.valid is False
        assert "insurance policy" in res.error.lower()


def test_blank_pdf_rejected():
    """Verify that a blank PDF is safely rejected."""
    # Create minimal 1-page blank PDF
    blank_pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f\n0000000010 00000 n\n0000000053 00000 n\n0000000102 00000 n\n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF\n"
    )
    res = validate_policy_pdf(blank_pdf, filename="blank.pdf")
    assert res.valid is False
    assert "blank" in res.error.lower() or "no readable text" in res.error.lower()


def test_corrupted_malformed_pdf_rejected():
    """Verify that a malformed/corrupted PDF is rejected without crashing."""
    corrupted = b"%PDF-1.4\nNOT A VALID BODY STREAM REST OF FILE IS BROKEN AND JUNK TRASH"
    res = validate_policy_pdf(corrupted, filename="corrupted.pdf")
    assert res.valid is False
    assert "corrupted" in res.error.lower() or "unreadable" in res.error.lower()


def test_renamed_non_pdf_file_rejected():
    """Verify that a non-PDF file renamed with a .pdf extension fails magic byte inspection."""
    fake_pdf = b"Hello, this is just a plain text document pretending to be a PDF file. " * 5
    res = validate_policy_pdf(fake_pdf, filename="fake.pdf")
    assert res.valid is False
    assert "not a valid pdf" in res.error.lower()


def test_empty_file_rejected():
    """Verify that an empty 0-byte file is rejected."""
    res = validate_policy_pdf(b"", filename="empty.pdf")
    assert res.valid is False
    assert "empty" in res.error.lower() or "corrupted" in res.error.lower()


def test_api_validate_slot_policy_success():
    """Test POST /api/documents/validate-slot accepts valid policy."""
    with open(POLICY_PDF, "rb") as f:
        response = client.post(
            "/api/documents/validate-slot",
            data={"slot": "policy"},
            files={"file": (POLICY_PDF.name, f, "application/pdf")}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["slot"] == "policy"
    assert data["document_type"] == "insurance_policy"


def test_api_validate_slot_policy_rejection():
    """Test POST /api/documents/validate-slot rejects hospital claim document in policy slot."""
    with open(CLAIM_PDF, "rb") as f:
        response = client.post(
            "/api/documents/validate-slot",
            data={"slot": "policy"},
            files={"file": (CLAIM_PDF.name, f, "application/pdf")}
        )
    assert response.status_code == 400
    data = response.json()
    assert data["valid"] is False
    assert "insurance policy" in data["error"].lower()


def test_api_validate_slot_supporting_hospital_document_accepted():
    """Test POST /api/documents/validate-slot accepts hospital claim documents in hospital slot."""
    with open(CLAIM_PDF, "rb") as f:
        response = client.post(
            "/api/documents/validate-slot",
            data={"slot": "hospital"},
            files={"file": (CLAIM_PDF.name, f, "application/pdf")}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["slot"] == "hospital"


def test_api_claims_upload_blocks_invalid_policy():
    """Test that POST /api/claims/upload rejects non-policy document in policy_file."""
    with open(CLAIM_PDF, "rb") as f_bad_policy, open(CLAIM_PDF, "rb") as f_claim:
        response = client.post(
            "/api/claims/upload",
            data={"goal": "Test claim"},
            files={
                "policy_file": (CLAIM_PDF.name, f_bad_policy, "application/pdf"),
                "claim_file": (CLAIM_PDF.name, f_claim, "application/pdf")
            }
        )
    assert response.status_code == 400
    assert "insurance policy" in response.json()["detail"].lower()
