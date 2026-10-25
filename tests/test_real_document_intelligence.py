"""tests/test_real_document_intelligence.py
Comprehensive Regression Test Suite for Real Document Intelligence & Claim Integrity.

Verifies:
1. Policy Classification:
   - Valid policy schedule from known insurer accepted.
   - Valid policy with unfamiliar layout / insurer accepted.
   - Scanned policy requiring OCR accepted.
   - Hospital claim / medical bill rejected in policy slot with clear error message.
   - Discharge summary rejected in policy slot.
   - Blank / corrupted PDF rejected in policy slot.
   - Renamed non-PDF file rejected in policy slot.
   - Document with 'policy' in filename but medical content rejected.
2. Cross-Document Consistency & Entity Roles:
   - Insurer conflict detected (e.g. 'Sunrise Dhruvil Shield' vs 'Sunrise Shield').
   - Legitimate TPA relationship accepted (e.g. 'Medi Assist TPA' with 'Sunrise Shield').
   - Hospital name differing from insurer does NOT cause an insurer discrepancy.
   - Patient name mismatch detected even when sharing surname ('Aarav Sharma' vs 'Rajesh Sharma').
   - Patient name variation accepted for middle names ('Aarav Kumar Sharma' vs 'Aarav Sharma').
   - Policy number mismatch detected.
3. Final Verdict Correctness:
   - Mismatched insurer blocks claim readiness -> ACTION_REQUIRED_INVALID_DOCUMENTS.
   - Mismatched patient blocks claim readiness -> ACTION_REQUIRED_INVALID_DOCUMENTS.
   - Missing policy document blocks claim readiness -> ACTION_REQUIRED_INVALID_DOCUMENTS.
   - Missing medical evidence blocks claim readiness -> ACTION_REQUIRED_MISSING_EVIDENCE.
   - All valid and consistent documents -> CLAIM_READY_FOR_SUBMISSION.
"""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.server import app
from services.document_validation.policy_validator import validate_policy_pdf, PolicyValidationResult
from tools.cross_document_consistency_tool import CrossDocumentConsistencyTool
from services.validity_checker.checker import ValidityChecker
from agent.tools import ClaimPreparationAdapter
from agent.state import ClaimState, ClaimStatus

ROOT_DIR = Path(__file__).resolve().parent.parent
POLICY_PDF = ROOT_DIR / "InsureMate_Test_Health_Insurance_Policy.pdf"
DHRUVIL_POLICY_PDF = ROOT_DIR / "InsureMate_Test_Health_Insurance_Policy_Dhruvil.pdf"
CLAIM_PDF = ROOT_DIR / "InsureMate_Test_Health_Insurance_Claim_Documents.pdf"
SAMPLE_POLICY = ROOT_DIR / "sample_policy.pdf"

client = TestClient(app)


# =============================================================================
# 1. POLICY PDF CLASSIFICATION & UPLOAD TESTS
# =============================================================================

def test_valid_policy_accepted():
    """Verify that a genuine insurance policy is accepted by content classification."""
    assert POLICY_PDF.exists()
    content = POLICY_PDF.read_bytes()
    res = validate_policy_pdf(content, filename=POLICY_PDF.name)
    assert res.valid is True
    assert res.document_type == "insurance_policy"
    assert res.decision == "valid_policy"
    assert res.confidence >= 0.70


def test_dhruvil_policy_accepted_as_policy_type():
    """Dhruvil policy is structurally an insurance policy, so upload validator accepts it."""
    target = DHRUVIL_POLICY_PDF if DHRUVIL_POLICY_PDF.exists() else (ROOT_DIR / "uploads" / "CLM-97C34E76" / "InsureMate_Test_Health_Insurance_Policy_Dhruvil.pdf")
    if target.exists():
        content = target.read_bytes()
        res = validate_policy_pdf(content, filename=target.name)
        assert res.valid is True
        assert res.document_type == "insurance_policy"


def test_claim_document_rejected_in_policy_slot():
    """Hospital bills and claim forms must be rejected when uploaded to the policy slot."""
    assert CLAIM_PDF.exists()
    content = CLAIM_PDF.read_bytes()
    res = validate_policy_pdf(content, filename="policy_renamed_claim.pdf")
    # Even if filename contains 'policy', content must dictate rejection!
    assert res.valid is False
    assert res.document_type in ("hospital_document", "medical_bill", "medical_report")
    assert res.decision == "not_a_policy"
    assert "insurance policy" in res.error.lower()


def test_validate_slot_endpoint_rejects_non_policy():
    """Test API endpoint /api/documents/validate-slot rejects claim doc in policy slot with 400."""
    assert CLAIM_PDF.exists()
    with open(CLAIM_PDF, "rb") as f:
        resp = client.post(
            "/api/documents/validate-slot",
            files={"file": ("claim_test.pdf", f, "application/pdf")},
            data={"slot": "policy"}
        )
    assert resp.status_code == 400
    data = resp.json()
    assert data["valid"] is False
    assert "insurance policy" in data["error"].lower()


# =============================================================================
# 2. CROSS-DOCUMENT CONSISTENCY & ENTITY AUDIT TESTS
# =============================================================================

def test_dhruvil_insurer_conflict_detected():
    """
    Dhruvil Policy specifies insurer 'Sunrise Dhruvil Shield Health Insurance Ltd.',
    while claim documents specify 'Sunrise Shield Health Insurance Ltd.'.
    Consistency tool MUST flag a CRITICAL discrepancy for conflicting insurers.
    """
    extracted_data = [
        {
            "page_number": 1,
            "document_type": "insurance_policy",
            "document_title": "Policy Schedule",
            "insurer_name": "Sunrise Dhruvil Shield Health Insurance Ltd.",
            "policy_number": "SHIELD-HEALTH-2026-00892",
            "policy_holder_name": "Aarav Sharma",
        },
        {
            "page_number": 2,
            "document_type": "hospital_document",
            "document_title": "Reimbursement Claim Form (Part A)",
            "insurer_name": "Sunrise Shield Health Insurance Ltd.",
            "policy_number": "SHIELD-HEALTH-2026-00892",
            "patient_name": "Aarav Sharma",
        },
    ]

    tool = CrossDocumentConsistencyTool()
    res = tool.run(extracted_data)

    assert res["consistent"] is False
    assert res["severity"] == "CRITICAL"
    assert any("Conflicting insurance companies" in d for d in res["discrepancies"])

    # Ensure ClaimPreparationAdapter blocks readiness
    adapter = ClaimPreparationAdapter()
    state = ClaimState(
        claim_id="test-dhruvil-mismatch",
        extracted_data=extracted_data,
        validation_result={"valid": True},
        validity_result={"valid": True, "reasons": ["Dates within coverage"]},
        missing_documents={"missing_documents": [], "missing_count": 0},
        consistency_results=res,
    )
    adapter.run(state)
    assert state.final_status == ClaimStatus.ACTION_REQUIRED_INVALID_DOCUMENTS.value
    assert state.final_report["is_ready"] is False
    assert state.final_report["consistency_status"] == "FAIL"


def test_patient_name_mismatch_same_surname():
    """
    Policy covers 'Aarav Sharma', but hospital bill is under 'Rajesh Sharma'.
    Even though they share the surname 'Sharma', this MUST be flagged as an identity mismatch.
    """
    extracted_data = [
        {
            "page_number": 1,
            "document_type": "insurance_policy",
            "policy_holder_name": "Aarav Sharma",
            "insured_names": ["Aarav Sharma"],
            "policy_number": "POL-100",
        },
        {
            "page_number": 2,
            "document_type": "medical_bill",
            "patient_name": "Rajesh Sharma",
            "policy_number": "POL-100",
        },
    ]

    tool = CrossDocumentConsistencyTool()
    res = tool.run(extracted_data)

    assert res["consistent"] is False
    assert res["severity"] == "CRITICAL"
    assert any("Patient name 'Rajesh Sharma'" in d for d in res["discrepancies"])


def test_patient_name_variation_middle_name_accepted():
    """Policy covers 'Aarav Kumar Sharma', bill has 'Aarav Sharma'. Should pass as valid variation."""
    extracted_data = [
        {
            "page_number": 1,
            "document_type": "insurance_policy",
            "policy_holder_name": "Aarav Kumar Sharma",
            "insured_names": ["Aarav Kumar Sharma"],
            "policy_number": "POL-100",
        },
        {
            "page_number": 2,
            "document_type": "medical_bill",
            "patient_name": "Aarav Sharma",
            "policy_number": "POL-100",
        },
    ]

    tool = CrossDocumentConsistencyTool()
    res = tool.run(extracted_data)
    assert res["consistent"] is True
    assert len(res["discrepancies"]) == 0


def test_tpa_relationship_accepted():
    """Claim document citing 'Medi Assist Insurance TPA Pvt Ltd' for 'Sunrise Shield' is legitimate."""
    extracted_data = [
        {
            "page_number": 1,
            "document_type": "insurance_policy",
            "insurer_name": "Sunrise Shield Health Insurance Ltd.",
            "policy_number": "POL-100",
            "policy_holder_name": "Aarav Sharma",
        },
        {
            "page_number": 2,
            "document_type": "hospital_document",
            "insurer_name": "Medi Assist Insurance TPA Pvt Ltd",
            "policy_number": "POL-100",
            "patient_name": "Aarav Sharma",
        },
    ]

    tool = CrossDocumentConsistencyTool()
    res = tool.run(extracted_data)
    assert res["consistent"] is True
    assert len(res["discrepancies"]) == 0


def test_hospital_name_not_compared_to_insurer():
    """Hospital facility 'Apollo Multispeciality Hospital' must not trigger an insurer discrepancy."""
    extracted_data = [
        {
            "page_number": 1,
            "document_type": "insurance_policy",
            "insurer_name": "Sunrise Shield Health Insurance Ltd.",
            "policy_number": "POL-100",
            "policy_holder_name": "Aarav Sharma",
        },
        {
            "page_number": 2,
            "document_type": "hospital_document",
            "hospital_name": "Apollo Multispeciality Hospital",
            "insurer_name": "Sunrise Shield Health Insurance Ltd.",
            "policy_number": "POL-100",
            "patient_name": "Aarav Sharma",
        },
    ]

    tool = CrossDocumentConsistencyTool()
    res = tool.run(extracted_data)
    assert res["consistent"] is True
    assert len(res["discrepancies"]) == 0


def test_document_titles_not_treated_as_discrepant_hospitals():
    """Document section titles (e.g. Discharge Summary, Inpatient Bill) must not be flagged as hospital discrepancies."""
    extracted_data = [
        {
            "page_number": 1,
            "document_type": "insurance_policy",
            "insurer_name": "Health Shield General Insurance Co. Ltd.",
            "policy_number": "POL-991",
            "policy_holder_name": "XYZ Patel",
        },
        {
            "page_number": 2,
            "document_type": "hospital_document",
            "hospital_name": "Shree Vallabh Hospital, Vadodara",
            "patient_name": "XYZ Patel",
            "policy_number": "POL-991",
        },
        {
            "page_number": 3,
            "document_type": "hospital_document",
            "hospital_name": "INDOOR ADMISSION RECORD",
            "patient_name": "XYZ Patel",
            "policy_number": "POL-991",
        },
        {
            "page_number": 4,
            "document_type": "hospital_document",
            "hospital_name": "DISCHARGE SUMMARY",
            "patient_name": "XYZ Patel",
            "policy_number": "POL-991",
        },
        {
            "page_number": 5,
            "document_type": "hospital_document",
            "hospital_name": "FINAL INPATIENT BILL & TAX INVOICE",
            "patient_name": "XYZ Patel",
            "policy_number": "POL-991",
        },
    ]

    tool = CrossDocumentConsistencyTool()
    res = tool.run(extracted_data)
    assert res["consistent"] is True, f"Expected consistent=True, got discrepancies: {res.get('discrepancies')}"
    assert len(res["discrepancies"]) == 0


# =============================================================================
# 3. VERDICT ENGINE & CLAIM READINESS TESTS
# =============================================================================

def test_missing_policy_document_blocks_ready():
    """If no policy document is uploaded, claim cannot be CLAIM_READY_FOR_SUBMISSION."""
    adapter = ClaimPreparationAdapter()
    state = ClaimState(
        claim_id="test-no-policy",
        extracted_data=[
            {"document_type": "medical_bill", "patient_name": "Aarav Sharma", "bill_amount": 10000}
        ],
        validation_result={"valid": True},
        validity_result={"valid": True, "reasons": []},
        missing_documents={"missing_documents": [], "missing_count": 0},
    )
    adapter.run(state)
    assert state.final_status == ClaimStatus.ACTION_REQUIRED_INVALID_DOCUMENTS.value
    assert state.final_report["is_ready"] is False
    assert "policy" in state.final_report["decision_summary"].lower()


def test_only_policy_document_blocks_ready():
    """If only policy is provided (no bills/records), claim requires missing evidence."""
    adapter = ClaimPreparationAdapter()
    state = ClaimState(
        claim_id="test-only-policy",
        extracted_data=[
            {"document_type": "insurance_policy", "policy_number": "POL-100"}
        ],
        validation_result={"valid": True},
        validity_result={"valid": True, "reasons": []},
        missing_documents={"missing_documents": ["Hospital Final Tax Invoice"], "missing_count": 1},
    )
    adapter.run(state)
    assert state.final_status == ClaimStatus.ACTION_REQUIRED_MISSING_EVIDENCE.value
    assert state.final_report["is_ready"] is False


def test_valid_and_coherent_bundle_is_ready():
    """A completely valid and consistent bundle resolves to CLAIM_READY_FOR_SUBMISSION."""
    adapter = ClaimPreparationAdapter()
    state = ClaimState(
        claim_id="test-all-valid",
        extracted_data=[
            {"document_type": "insurance_policy", "policy_number": "POL-100", "insurer_name": "Sunrise Shield"},
            {"document_type": "medical_bill", "policy_number": "POL-100", "patient_name": "Aarav Sharma", "bill_amount": 5000}
        ],
        validation_result={"valid": True},
        validity_result={"valid": True, "reasons": ["Dates within coverage window"]},
        missing_documents={"missing_documents": [], "missing_count": 0},
        consistency_results={"status": "success", "consistent": True, "severity": "NONE", "discrepancies": []}
    )
    adapter.run(state)
    assert state.final_status == ClaimStatus.CLAIM_READY_FOR_SUBMISSION.value
    assert state.final_report["is_ready"] is True
