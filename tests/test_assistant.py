"""tests/test_assistant.py
Unit and Integration tests for InsureMate AI Document Assistant.
Validates:
1. "Are we eligible for policy claim?"
2. "Is anything missing?"
3. "Which documents are missing?"
4. "What is the policy expiry date?"
5. "Why is this claim marked as having a discrepancy?"
6. "Does this policy cover the treatment described in my documents?"
7. "What should I do next to prepare this claim?"
8. "What is DSA?" (out of scope refusal)
9. "Explain bubble sort" (out of scope refusal)
10. Question not in documents (explicit uncertainty)

Additional validations:
- Different questions produce different relevant answers.
- The model receives the actual question and relevant evidence.
- The correct analysis context is used.
- Graceful handling of Ollama unavailability and timeouts.
- REST API integration via TestClient.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.server import app
from services.assistant_service import (
    ask_assistant,
    build_focused_context,
    is_insurance_domain,
    OUT_OF_SCOPE_RESPONSE,
    GREETING_RESPONSE
)
from services.missing_document.ollama_client import OllamaClient, OllamaError


@pytest.fixture
def sample_claim_ready():
    """Mock claim that is CLAIM_READY_FOR_SUBMISSION with all evidence verified."""
    return {
        "claim": {
            "claim_id": "CLM-TEST-001",
            "claim_type": "health",
            "status": "completed"
        },
        "verdict": "CLAIM_READY_FOR_SUBMISSION",
        "latest_state": {
            "verified_facts": {
                "patient_name": "Aarav Mehta",
                "hospital_name": "Harmony Multispeciality Hospital",
                "admission_date": "12/09/2026",
                "discharge_date": "15/09/2026",
                "total_bill_amount": "85,000.00",
                "diagnosis": "Acute Appendicitis"
            },
            "validity_result": {
                "valid": True,
                "policy_period": {
                    "policy_number": "SSHI-TEST-2026-001",
                    "policy_start_date": "01/04/2026",
                    "policy_end_date": "31/03/2027"
                },
                "checks": [
                    {"raw_date": "12/09/2026", "valid": True},
                    {"raw_date": "15/09/2026", "valid": True}
                ],
                "reasons": []
            },
            "missing_documents": {
                "document_results": [
                    {
                        "document_title": "Hospital Discharge Summary",
                        "missing": False,
                        "page_number": 5,
                        "reason": "Clause 13 requires discharge summary detailing diagnosis."
                    },
                    {
                        "document_title": "Hospital Medical Bill & COV-002 Room Rent Folio",
                        "missing": False,
                        "page_number": 10,
                        "reason": "Clause 13 requires original itemized bills."
                    }
                ]
            },
            "extracted_data": [
                {
                    "page_number": 1,
                    "document_type": "insurance_policy",
                    "policy_clauses": [
                        "Clause 13: All medical claims require discharge summary and hospital bills."
                    ]
                }
            ]
        },
        "final_report": {
            "verdict": "CLAIM_READY_FOR_SUBMISSION",
            "decision_summary": "All documents validated, coverage dates verified, entities consistent."
        }
    }


@pytest.fixture
def sample_claim_missing_evidence():
    """Mock claim that is ACTION_REQUIRED_MISSING_EVIDENCE with missing docs."""
    return {
        "claim": {
            "claim_id": "CLM-TEST-002",
            "claim_type": "health",
            "status": "completed"
        },
        "verdict": "ACTION_REQUIRED_MISSING_EVIDENCE",
        "latest_state": {
            "verified_facts": {
                "patient_name": "Rohan Sharma",
                "hospital_name": "City Care Hospital",
                "total_bill_amount": "45,000.00"
            },
            "validity_result": {
                "valid": True,
                "policy_period": {
                    "policy_number": "POL-2026-999",
                    "policy_start_date": "01/01/2026",
                    "policy_end_date": "31/12/2026"
                }
            },
            "missing_documents": {
                "document_results": [
                    {
                        "document_title": "Original Discharge Summary",
                        "missing": True,
                        "reason": "Required to confirm clinical diagnosis and treatment duration."
                    },
                    {
                        "document_title": "Itemized Pharmacy Receipts",
                        "missing": True,
                        "reason": "Required to substantiate medication charges of INR 12,000."
                    },
                    {
                        "document_title": "Indoor Patient Admission Record",
                        "missing": False,
                        "page_number": 2,
                        "reason": "Submitted and verified."
                    }
                ]
            }
        },
        "final_report": {
            "verdict": "ACTION_REQUIRED_MISSING_EVIDENCE",
            "decision_summary": "Discharge summary and pharmacy bills are missing."
        }
    }


def test_domain_scope_filtering():
    """Verify out-of-scope queries (DSA, algorithms, general knowledge) are rejected."""
    # Out of scope
    assert not is_insurance_domain("What is DSA?")
    assert not is_insurance_domain("Explain bubble sort")
    assert not is_insurance_domain("Write quicksort in python")
    assert not is_insurance_domain("Who won the cricket match?")
    assert not is_insurance_domain("What is the capital of France?")

    # In scope
    assert is_insurance_domain("Are we eligible for policy claim?")
    assert is_insurance_domain("Is anything missing?")
    assert is_insurance_domain("Which documents are missing?")
    assert is_insurance_domain("What is the policy expiry date?")
    assert is_insurance_domain("Why is this claim marked as having a discrepancy?")
    assert is_insurance_domain("Does this policy cover the treatment described in my documents?")
    assert is_insurance_domain("What should I do next to prepare this claim?")
    assert is_insurance_domain("Who is the patient?")
    assert is_insurance_domain("What is the total bill amount?")


def test_out_of_scope_rejection_message(sample_claim_ready):
    """Verify that asking 'What is DSA?' and 'Explain bubble sort' returns polite deflection without calling Ollama."""
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True

    # Test DSA
    res_dsa = ask_assistant(sample_claim_ready, "What is DSA?", client=mock_ollama)
    assert res_dsa["answer"] == OUT_OF_SCOPE_RESPONSE
    mock_ollama.chat.assert_not_called()

    # Test Bubble Sort
    res_bs = ask_assistant(sample_claim_ready, "Explain bubble sort", client=mock_ollama)
    assert res_bs["answer"] == OUT_OF_SCOPE_RESPONSE
    mock_ollama.chat.assert_not_called()


def test_greeting_response(sample_claim_ready):
    """Verify simple greetings are handled politely."""
    res = ask_assistant(sample_claim_ready, "Hello")
    assert "InsureMate" in res["answer"]


def test_context_construction_grounded(sample_claim_ready):
    """Verify that context includes correct claim ID, dates, and evidence checklist."""
    ctx = build_focused_context(sample_claim_ready, "Are we eligible for policy claim?")
    assert "CLM-TEST-001" in ctx
    assert "CLAIM_READY_FOR_SUBMISSION" in ctx
    assert "01/04/2026 to 31/03/2027" in ctx
    assert "Aarav Mehta" in ctx
    assert "Harmony Multispeciality Hospital" in ctx
    assert "Hospital Discharge Summary" in ctx
    assert "Truly Missing Required Documents: None" in ctx


def test_question_eligibility_grounded(sample_claim_ready):
    """Verify question 1: 'Are we eligible for policy claim?' sends grounded context to model."""
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    mock_ollama.chat.return_value = (
        "Yes, you are eligible for the claim. All mandatory documents (Discharge Summary, Medical Bill) "
        "have been verified, dates (12/09/2026 to 15/09/2026) fall within the active policy period (01/04/2026 to 31/03/2027), "
        "and no discrepancies were found. Please note that CLAIM_READY_FOR_SUBMISSION indicates administrative readiness "
        "and is subject to final insurer adjudication."
    )

    res = ask_assistant(sample_claim_ready, "Are we eligible for policy claim?", client=mock_ollama)
    assert "eligible" in res["answer"].lower()
    assert "01/04/2026" in res["answer"]

    # Verify model received the actual question and context
    call_args = mock_ollama.chat.call_args[0]
    messages = call_args[0]
    assert any("Are we eligible for policy claim?" in m["content"] for m in messages)
    assert any("CLM-TEST-001" in m["content"] for m in messages)


def test_question_missing_documents_grounded(sample_claim_missing_evidence):
    """Verify question 2 & 3: 'Is anything missing?' and 'Which documents are missing?' correctly lists missing items."""
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    mock_ollama.chat.return_value = (
        "The following documents are missing from your submission:\n"
        "• Original Discharge Summary (Required to confirm clinical diagnosis)\n"
        "• Itemized Pharmacy Receipts (Required to substantiate medication charges)\n\n"
        "The Indoor Patient Admission Record has been submitted and verified."
    )

    res = ask_assistant(sample_claim_missing_evidence, "Which documents are missing?", client=mock_ollama)
    assert "Original Discharge Summary" in res["answer"]
    assert "Pharmacy Receipts" in res["answer"]

    # Verify context informed the model about missing items
    call_args = mock_ollama.chat.call_args[0]
    messages = call_args[0]
    assert any("Original Discharge Summary" in m["content"] for m in messages)
    assert any("MISSING" in m["content"] for m in messages)


def test_question_expiry_date(sample_claim_ready):
    """Verify question 4: 'What is the policy expiry date?'."""
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    mock_ollama.chat.return_value = "The policy expiry date is 31/03/2027."

    res = ask_assistant(sample_claim_ready, "What is the policy expiry date?", client=mock_ollama)
    assert "31/03/2027" in res["answer"]


def test_question_discrepancy(sample_claim_ready):
    """Verify question 5: 'Why is this claim marked as having a discrepancy?'."""
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    mock_ollama.chat.return_value = "No discrepancies were detected across the validated documents for this claim."

    res = ask_assistant(sample_claim_ready, "Why is this claim marked as having a discrepancy?", client=mock_ollama)
    assert "No discrepancies" in res["answer"]


def test_question_coverage(sample_claim_ready):
    """Verify question 6: 'Does this policy cover the treatment described in my documents?'."""
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    mock_ollama.chat.return_value = "Yes, Acute Appendicitis treatment is covered within the active policy period."

    res = ask_assistant(sample_claim_ready, "Does this policy cover the treatment described in my documents?", client=mock_ollama)
    assert "covered" in res["answer"].lower()


def test_question_next_steps(sample_claim_ready):
    """Verify question 7: 'What should I do next to prepare this claim?'."""
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    mock_ollama.chat.return_value = "All documents are ready. You can now submit the claim package to your insurer for adjudication."

    res = ask_assistant(sample_claim_ready, "What should I do next to prepare this claim?", client=mock_ollama)
    assert "submit" in res["answer"].lower()


def test_question_explicit_uncertainty(sample_claim_ready):
    """Verify question 10: Question not available in documents returns explicit uncertainty."""
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    mock_ollama.chat.return_value = "The requested information regarding vehicle registration is not available in the uploaded health policy and hospital documents."

    res = ask_assistant(sample_claim_ready, "What is the vehicle registration number?", client=mock_ollama)
    assert "not available" in res["answer"].lower()


def test_ollama_unavailable_graceful_handling(sample_claim_ready):
    """Verify graceful error reporting when Ollama daemon is offline or model is unavailable."""
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = False

    res = ask_assistant(sample_claim_ready, "Are we eligible for policy claim?", client=mock_ollama)
    assert "currently unavailable" in res["answer"]
    assert "ollama serve" in res["answer"]


def test_ollama_timeout_graceful_handling(sample_claim_ready):
    """Verify graceful handling when Ollama times out."""
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.is_available.return_value = True
    mock_ollama.chat.side_effect = OllamaError("Ollama request timed out after 120s on model gemma3:latest")

    res = ask_assistant(sample_claim_ready, "Are we eligible for policy claim?", client=mock_ollama)
    assert "Unable to generate response from Ollama" in res["answer"]
    assert "timed out" in res["answer"]


def test_rest_api_assistant_endpoint():
    """Verify REST API POST /api/claims/{claim_id}/assistant integrates with ask_assistant."""
    client = TestClient(app)

    # 1. Unknown claim -> 404
    r_404 = client.post("/api/claims/CLM-NONEXISTENT/assistant", json={"question": "Is anything missing?"})
    assert r_404.status_code == 404

    # 2. Existing claim -> 200 with answer
    # Use CLM-7F63C637 which exists in DB
    r = client.post("/api/claims/CLM-7F63C637/assistant", json={"question": "What is DSA?"})
    assert r.status_code == 200
    data = r.json()
    assert "answer" in data
    assert data["answer"] == OUT_OF_SCOPE_RESPONSE
