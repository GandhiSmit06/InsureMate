"""tests/test_master_pipeline_fixes.py
Comprehensive verification and acceptance tests for InsureMate Pipeline & LLM Fixes:
1. Slot alignment & document inversion validation
2. Full 27-page extraction (11-page policy + 16-page claim) without 10-page truncation
3. Ollama dynamic model discovery & robust JSON repair
4. End-to-end acceptance tests
"""

import json
from pathlib import Path
import pytest

from agent.insuremate_agent import InsureMateAgent
from agent.state import ClaimState, ClaimStatus
from agent.decision import AgentDecision, InsureMateDecisionEngine
from services.document_validation.validator import DocumentValidator, document_validation
from services.missing_document.llm_gateway import extract_json_from_text
from services.missing_document.ollama_client import OllamaClient
from services.qwen_vl.extractor import extract_document, PageExtractionResult

POLICY_PDF = Path("test_documents/InsureMate_Test_Health_Insurance_Policy.pdf").resolve()
CLAIM_PDF = Path("test_documents/InsureMate_Test_Health_Insurance_Claim_Documents.pdf").resolve()


# -----------------------------------------------------------------------------
# TASK 1: Document Slot Alignment & Inversion Detection
# -----------------------------------------------------------------------------

def test_document_slot_alignment_inversion_detected():
    """Test that swapping policy and claim documents triggers explicit inversion failure."""
    validator = DocumentValidator()

    # Claim doc pages assigned to policy slot, Policy doc pages assigned to claim slot
    extracted_docs = [
        {"document_type": "hospital_document", "source_file": "claim.pdf", "slot": "policy", "page_number": 1, "patient_name": "John", "document_date": "10/01/2025", "hospital_name": "City Hospital"},
        {"document_type": "medical_bill", "source_file": "claim.pdf", "slot": "policy", "page_number": 2, "patient_name": "John", "document_date": "10/01/2025", "bill_number": "B1", "bill_amount": 5000},
        {"document_type": "insurance_policy", "source_file": "policy.pdf", "slot": "claim", "page_number": 1, "policy_number": "POL1", "policy_start_date": "01/01/2025", "policy_end_date": "31/12/2025", "policy_holder_name": "John"},
    ]

    result = validator.validate_batch(
        extracted_documents=extracted_docs,
        policy_file="claim.pdf",
        claim_file="policy.pdf"
    )

    assert result.valid is False
    assert result.invalid_documents == len(extracted_docs)
    reasons_str = " ".join(result.reasons)
    assert "Document Inversion Detected" in reasons_str
    assert "Your Insurance Policy and Claim Documents appear to be swapped" in reasons_str
    assert "The document uploaded in the 'Insurance Policy' field ('claim.pdf') is a Hospital/Medical Claim document" in reasons_str
    assert "The document uploaded in the 'Claim Documents' field ('policy.pdf') is an Insurance Policy Schedule" in reasons_str


def test_document_slot_alignment_policy_slot_mismatch_only():
    """Test failure when hospital claim doc is uploaded into policy slot alone."""
    validator = DocumentValidator()
    extracted_docs = [
        {"document_type": "hospital_document", "source_file": "hospital_file.pdf", "slot": "policy", "page_number": 1, "patient_name": "John", "document_date": "10/01/2025", "hospital_name": "City Hospital"},
        {"document_type": "medical_bill", "source_file": "bills.pdf", "slot": "claim", "page_number": 1, "patient_name": "John", "document_date": "10/01/2025", "bill_number": "B1", "bill_amount": 5000},
    ]

    result = validator.validate_batch(
        extracted_documents=extracted_docs,
        policy_file="hospital_file.pdf",
        claim_file="bills.pdf"
    )

    assert result.valid is False
    reasons_str = " ".join(result.reasons)
    assert "Invalid document format: The document uploaded in the 'Insurance Policy' field ('hospital_file.pdf') is a Hospital/Medical Claim document" in reasons_str


def test_document_slot_alignment_claim_slot_mismatch_only():
    """Test failure when policy doc is uploaded into claim slot alone."""
    validator = DocumentValidator()
    extracted_docs = [
        {"document_type": "insurance_policy", "source_file": "policy.pdf", "slot": "policy", "page_number": 1, "policy_number": "POL1", "policy_start_date": "01/01/2025", "policy_end_date": "31/12/2025", "policy_holder_name": "John"},
        {"document_type": "insurance_policy", "source_file": "another_policy.pdf", "slot": "claim", "page_number": 1, "policy_number": "POL2", "policy_start_date": "01/01/2025", "policy_end_date": "31/12/2025", "policy_holder_name": "John"},
    ]

    result = validator.validate_batch(
        extracted_documents=extracted_docs,
        policy_file="policy.pdf",
        claim_file="another_policy.pdf"
    )

    assert result.valid is False
    reasons_str = " ".join(result.reasons)
    assert "Invalid document format: The document uploaded in the 'Claim Documents' field ('another_policy.pdf') is an Insurance Policy Schedule" in reasons_str


# -----------------------------------------------------------------------------
# TASK 2: 10-Page Truncation Bug Elimination & Source Tagging
# -----------------------------------------------------------------------------

def test_source_file_and_file_path_tagged_in_extraction():
    """Ensure PageExtractionResult and extract_document attach source_file and file_path."""
    res = PageExtractionResult(page_number=1, document_type="insurance_policy", source_file="my_policy.pdf", file_path="/path/my_policy.pdf")
    d = res.to_dict()
    assert d.get("source_file") == "my_policy.pdf"
    assert d.get("file_path") == "/path/my_policy.pdf"

    # Test real PDF extraction for policy
    assert POLICY_PDF.exists(), f"Policy PDF not found: {POLICY_PDF}"
    policy_pages = extract_document(POLICY_PDF)
    assert len(policy_pages) == 11, f"Expected 11 pages for policy PDF, got {len(policy_pages)}"
    assert policy_pages[0].get("source_file") == POLICY_PDF.name
    assert policy_pages[0].get("file_path") == str(POLICY_PDF)


def test_claim_document_extracts_all_16_pages():
    """Ensure claim bundle extracts 16 of 16 pages, including pages 11-16."""
    assert CLAIM_PDF.exists(), f"Claim PDF not found: {CLAIM_PDF}"
    claim_pages = extract_document(CLAIM_PDF)
    assert len(claim_pages) == 16, f"Expected 16 pages for claim bundle, got {len(claim_pages)}"

    page_numbers = [p["page_number"] for p in claim_pages]
    for p_num in range(1, 17):
        assert p_num in page_numbers, f"Page {p_num} missing from claim extraction"

    # Pages 11 to 16 check
    p11 = claim_pages[10]
    p12 = claim_pages[11]
    p13 = claim_pages[12]
    p14 = claim_pages[13]
    p15 = claim_pages[14]
    p16 = claim_pages[15]

    assert p11["page_number"] == 11
    assert p12["page_number"] == 12
    assert p13["page_number"] == 13
    assert p14["page_number"] == 14
    assert p15["page_number"] == 15
    assert p16["page_number"] == 16


# -----------------------------------------------------------------------------
# TASK 3: Ollama Dynamic Discovery & Robust JSON Repair
# -----------------------------------------------------------------------------

def test_robust_json_extraction():
    """Test extract_json_from_text handles markdown code fences, chatter, and regex repair."""
    # Case 1: Markdown code block with chatter
    text1 = "Here is the response you asked for:\n```json\n{\"action\": \"document_validation\", \"reason\": \"Validating fields\", \"action_input\": {}}\n```\nHope that helps!"
    res1 = extract_json_from_text(text1)
    assert res1["action"] == "document_validation"
    assert res1["reason"] == "Validating fields"

    # Case 2: Broken JSON with conversational chatter where regex repair recovers keys
    text2 = "Sure! I decided: 'action': 'claim_preparation', 'reason': 'Ready to finalize', 'action_input': {'foo': 'bar'}"
    res2 = extract_json_from_text(text2)
    assert res2["action"] == "claim_preparation"
    assert res2["reason"] == "Ready to finalize"
    assert res2["action_input"] == {"foo": "bar"}


def test_ollama_model_fallback_detection(monkeypatch):
    """Test Ollama client auto-selects available model when configured model is not installed."""
    client = OllamaClient(model="gemma3:latest")

    class MockResponse:
        status_code = 200
        def json(self):
            return {
                "models": [
                    {"name": "qwen2.5:latest"},
                    {"name": "llama3.2:latest"}
                ]
            }

    import requests
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: MockResponse())

    avail = client.is_available(force_refresh=True)
    assert avail is True
    # Auto-selected qwen2.5:latest since gemma3:latest was absent
    assert client.model == "qwen2.5:latest"


# -----------------------------------------------------------------------------
# TASK 4: Acceptance End-to-End Tests
# -----------------------------------------------------------------------------

def test_acceptance_inverted_document_upload_fails():
    """
    Acceptance Test 1: Upload Policy into Claim slot and Claim into Policy slot.
    Validation MUST fail immediately with ACTION_REQUIRED_INVALID_DOCUMENTS.
    """
    state = ClaimState(
        claim_id="TEST-INVERTED-001",
        goal="Determine claim readiness and validate documents.",
        documents=[str(CLAIM_PDF), str(POLICY_PDF)],
        policy_documents=[str(CLAIM_PDF)],  # Swapped!
        claim_documents=[str(POLICY_PDF)]   # Swapped!
    )

    agent = InsureMateAgent(offline_mode=True)
    final_state = agent.run(state)

    assert final_state.final_status == ClaimStatus.ACTION_REQUIRED_INVALID_DOCUMENTS.value
    assert final_state.final_report is not None
    assert final_state.final_report.get("is_ready") is False

    report_str = json.dumps(final_state.final_report)
    assert "Invalid document format" in report_str or "Document Inversion Detected" in report_str
    assert "Hospital/Medical Claim document" in report_str or "swapped" in report_str


def test_acceptance_normal_document_upload_processes_all_27_pages():
    """
    Acceptance Test 2: Upload Policy into Policy slot and Claim into Claim slot.
    All 11 policy pages + 16 claim pages = 27 pages MUST be extracted and audited.
    Final status MUST be CLAIM_READY_FOR_SUBMISSION.
    """
    state = ClaimState(
        claim_id="TEST-NORMAL-002",
        goal="Determine claim readiness.",
        documents=[str(POLICY_PDF), str(CLAIM_PDF)],
        policy_documents=[str(POLICY_PDF)],
        claim_documents=[str(CLAIM_PDF)]
    )

    agent = InsureMateAgent(offline_mode=True)
    final_state = agent.run(state)

    # All 27 pages extracted
    assert len(final_state.extracted_data) == 27, f"Expected 27 extracted pages, got {len(final_state.extracted_data)}"

    # Check validity status
    assert final_state.validation_result is not None
    assert final_state.validation_result.get("valid") is True

    assert final_state.validity_result is not None
    assert final_state.validity_result.get("valid") is True

    # Final verdict
    assert final_state.final_status == ClaimStatus.CLAIM_READY_FOR_SUBMISSION.value
    assert final_state.final_report.get("is_ready") is True
