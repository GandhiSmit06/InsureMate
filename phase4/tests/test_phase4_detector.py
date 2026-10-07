"""Unit tests for InsureMate Phase 4 Missing-Document Detection.

Implements all 8 required test scenarios from the specification plus schema edge cases:
- Test 1: All documents present
- Test 2: Discharge document missing
- Test 3: Multiple documents missing
- Test 4: Semantic matching (Discharge Summary <-> Patient Discharge Record)
- Test 5: Semantic matching (Final Hospital Bill <-> Final Hospital Invoice)
- Test 6: Valid LLM response (no retry)
- Test 7: Invalid LLM response (retries once, succeeds)
- Test 8: Both attempts invalid (retries once, returns structured error)
"""
import json
import pytest
from phase4.detector import detect_missing_documents
from phase4.gateway.llm_gateway import LLMGateway
from phase4.schemas.output_schema import (
    validate_output_against_requirements,
    Phase4ValidationError,
    MissingDocumentItem,
)
from phase4.tests.conftest import MockLLMClient


def test_1_all_documents_present(all_documents_present_data):
    """TEST 1 — ALL DOCUMENTS PRESENT

    Every policy requirement has a corresponding submitted document.
    Expected: missing=false for every requirement, valid page numbers.
    """
    mock_llm_response = json.dumps({
        "missing_documents": [
            {"sr_no": 1, "document_title": "Discharge Summary", "missing": False, "page_no": 5},
            {"sr_no": 2, "document_title": "Final Hospital Bill", "missing": False, "page_no": 7},
            {"sr_no": 3, "document_title": "Investigation Reports", "missing": False, "page_no": 8},
            {"sr_no": 4, "document_title": "Prescription", "missing": False, "page_no": 10},
            {"sr_no": 5, "document_title": "Pharmacy Bills", "missing": False, "page_no": 12}
        ]
    })
    client = MockLLMClient([mock_llm_response])
    result = detect_missing_documents(all_documents_present_data, client=client)

    assert "missing_documents" in result
    docs = result["missing_documents"]
    assert len(docs) == 5

    for doc in docs:
        assert doc["missing"] is False
        assert doc["page_no"] is not None
        assert isinstance(doc["page_no"], int)

    assert client.call_count == 1


def test_2_discharge_document_missing(discharge_missing_data):
    """TEST 2 — DISCHARGE DOCUMENT MISSING

    Patient Discharge Record is removed from submitted_documents.
    Expected: Discharge Summary has missing=true and page_no=null.
    """
    mock_llm_response = json.dumps({
        "missing_documents": [
            {"sr_no": 1, "document_title": "Discharge Summary", "missing": True, "page_no": None},
            {"sr_no": 2, "document_title": "Final Hospital Bill", "missing": False, "page_no": 7},
            {"sr_no": 3, "document_title": "Investigation Reports", "missing": True, "page_no": None},
            {"sr_no": 4, "document_title": "Prescription", "missing": False, "page_no": 10},
            {"sr_no": 5, "document_title": "Pharmacy Bills", "missing": True, "page_no": None}
        ]
    })
    client = MockLLMClient([mock_llm_response])
    result = detect_missing_documents(discharge_missing_data, client=client)

    assert "missing_documents" in result
    docs = {d["document_title"]: d for d in result["missing_documents"]}

    discharge = docs.get("Discharge Summary")
    assert discharge is not None
    assert discharge["missing"] is True
    assert discharge["page_no"] is None


def test_3_multiple_documents_missing(multiple_missing_data):
    """TEST 3 — MULTIPLE DOCUMENTS MISSING

    Discharge Summary, Investigation Reports, and Pharmacy Bills are missing.
    Expected: Investigation Reports and Pharmacy Bills must be marked missing=true, page_no=null.
    """
    mock_llm_response = json.dumps({
        "missing_documents": [
            {"sr_no": 1, "document_title": "Discharge Summary", "missing": True, "page_no": None},
            {"sr_no": 2, "document_title": "Final Hospital Bill", "missing": False, "page_no": 7},
            {"sr_no": 3, "document_title": "Investigation Reports", "missing": True, "page_no": None},
            {"sr_no": 4, "document_title": "Prescription", "missing": False, "page_no": 10},
            {"sr_no": 5, "document_title": "Pharmacy Bills", "missing": True, "page_no": None}
        ]
    })
    client = MockLLMClient([mock_llm_response])
    result = detect_missing_documents(multiple_missing_data, client=client)

    assert "missing_documents" in result
    docs = {d["document_title"]: d for d in result["missing_documents"]}

    assert docs["Investigation Reports"]["missing"] is True
    assert docs["Investigation Reports"]["page_no"] is None

    assert docs["Pharmacy Bills"]["missing"] is True
    assert docs["Pharmacy Bills"]["page_no"] is None


def test_4_semantic_matching_discharge_record(sample_phase3_data):
    """TEST 4 — SEMANTIC MATCHING: Discharge Summary <-> Patient Discharge Record

    Required: 'Discharge Summary'
    Submitted: 'Patient Discharge Record' (page 5)
    Expected: missing=false, page_no=5.
    """
    mock_llm_response = json.dumps({
        "missing_documents": [
            {"sr_no": 1, "document_title": "Discharge Summary", "missing": False, "page_no": 5},
            {"sr_no": 2, "document_title": "Final Hospital Bill", "missing": False, "page_no": 7},
            {"sr_no": 3, "document_title": "Investigation Reports", "missing": True, "page_no": None},
            {"sr_no": 4, "document_title": "Prescription", "missing": False, "page_no": 10},
            {"sr_no": 5, "document_title": "Pharmacy Bills", "missing": True, "page_no": None}
        ]
    })
    client = MockLLMClient([mock_llm_response])
    result = detect_missing_documents(sample_phase3_data, client=client)

    docs = {d["document_title"]: d for d in result["missing_documents"]}
    assert docs["Discharge Summary"]["missing"] is False
    assert docs["Discharge Summary"]["page_no"] == 5


def test_5_semantic_matching_hospital_invoice(sample_phase3_data):
    """TEST 5 — SEMANTIC MATCHING: Final Hospital Bill <-> Final Hospital Invoice

    Required: 'Final Hospital Bill'
    Submitted: 'Final Hospital Invoice' (page 7)
    Expected: missing=false, page_no=7.
    """
    mock_llm_response = json.dumps({
        "missing_documents": [
            {"sr_no": 1, "document_title": "Discharge Summary", "missing": False, "page_no": 5},
            {"sr_no": 2, "document_title": "Final Hospital Bill", "missing": False, "page_no": 7},
            {"sr_no": 3, "document_title": "Investigation Reports", "missing": True, "page_no": None},
            {"sr_no": 4, "document_title": "Prescription", "missing": False, "page_no": 10},
            {"sr_no": 5, "document_title": "Pharmacy Bills", "missing": True, "page_no": None}
        ]
    })
    client = MockLLMClient([mock_llm_response])
    result = detect_missing_documents(sample_phase3_data, client=client)

    docs = {d["document_title"]: d for d in result["missing_documents"]}
    assert docs["Final Hospital Bill"]["missing"] is False
    assert docs["Final Hospital Bill"]["page_no"] == 7


def test_6_valid_llm_response_no_retry(sample_phase3_data):
    """TEST 6 — VALID LLM RESPONSE

    Mock a valid response.
    Verify:
    - JSON validation succeeds.
    - retry is NOT called (call_count == 1).
    """
    valid_resp = json.dumps({
        "missing_documents": [
            {"sr_no": 1, "document_title": "Discharge Summary", "missing": False, "page_no": 5},
            {"sr_no": 2, "document_title": "Final Hospital Bill", "missing": False, "page_no": 7},
            {"sr_no": 3, "document_title": "Investigation Reports", "missing": True, "page_no": None},
            {"sr_no": 4, "document_title": "Prescription", "missing": False, "page_no": 10},
            {"sr_no": 5, "document_title": "Pharmacy Bills", "missing": True, "page_no": None}
        ]
    })
    client = MockLLMClient([valid_resp])
    result = detect_missing_documents(sample_phase3_data, client=client)

    assert "missing_documents" in result
    assert "error" not in result
    assert client.call_count == 1


def test_7_invalid_first_response_retry_succeeds(sample_phase3_data):
    """TEST 7 — INVALID LLM RESPONSE

    Mock the first LLM response as invalid JSON.
    Verify:
    - validation fails on attempt 1
    - exactly one retry happens (call_count == 2)
    - second valid response is accepted.
    """
    invalid_resp_1 = "This is not valid JSON at all!"
    valid_resp_2 = json.dumps({
        "missing_documents": [
            {"sr_no": 1, "document_title": "Discharge Summary", "missing": False, "page_no": 5},
            {"sr_no": 2, "document_title": "Final Hospital Bill", "missing": False, "page_no": 7},
            {"sr_no": 3, "document_title": "Investigation Reports", "missing": True, "page_no": None},
            {"sr_no": 4, "document_title": "Prescription", "missing": False, "page_no": 10},
            {"sr_no": 5, "document_title": "Pharmacy Bills", "missing": True, "page_no": None}
        ]
    })
    client = MockLLMClient([invalid_resp_1, valid_resp_2])
    result = detect_missing_documents(sample_phase3_data, client=client)

    assert client.call_count == 2
    assert "missing_documents" in result
    assert "error" not in result
    assert len(result["missing_documents"]) == 5


def test_8_both_attempts_invalid_returns_structured_error(sample_phase3_data):
    """TEST 8 — BOTH ATTEMPTS INVALID

    Mock both responses as invalid.
    Verify:
    - exactly one retry occurs (call_count == 2)
    - the function returns a clear structured error
    - malformed data is not returned as a successful result.
    """
    invalid_resp_1 = "I am an AI and cannot produce JSON."
    invalid_resp_2 = "{\"invalid_format\": true}"

    client = MockLLMClient([invalid_resp_1, invalid_resp_2])
    result = detect_missing_documents(sample_phase3_data, client=client)

    # Must have called exactly 2 times (attempt 1 + 1 retry)
    assert client.call_count == 2
    # Must NOT return successful missing_documents
    assert "missing_documents" not in result
    # Must return structured error
    assert "error" in result
    assert result["error"] == "MALFORMED_LLM_RESPONSE"
    assert result["details"]["attempts"] == 2
    assert "last_error" in result["details"]


def test_markdown_code_fence_parsing(sample_phase3_data):
    """Verify that JSON wrapped in markdown code blocks ```json ... ``` is correctly parsed."""
    markdown_wrapped = """Here is the result:
```json
{
  "missing_documents": [
    {"sr_no": 1, "document_title": "Discharge Summary", "missing": false, "page_no": 5},
    {"sr_no": 2, "document_title": "Final Hospital Bill", "missing": false, "page_no": 7},
    {"sr_no": 3, "document_title": "Investigation Reports", "missing": true, "page_no": null},
    {"sr_no": 4, "document_title": "Prescription", "missing": false, "page_no": 10},
    {"sr_no": 5, "document_title": "Pharmacy Bills", "missing": true, "page_no": null}
  ]
}
```
Hope this helps!"""
    client = MockLLMClient([markdown_wrapped])
    result = detect_missing_documents(sample_phase3_data, client=client)

    assert "missing_documents" in result
    assert client.call_count == 1


def test_schema_validation_rejects_missing_page_no_when_present():
    """Schema must reject an item where missing=false but page_no is null."""
    with pytest.raises(Exception):
        MissingDocumentItem(
            sr_no=1,
            document_title="Discharge Summary",
            missing=False,
            page_no=None
        )


def test_schema_validation_rejects_page_no_when_missing():
    """Schema must reject an item where missing=true but page_no is provided."""
    with pytest.raises(Exception):
        MissingDocumentItem(
            sr_no=1,
            document_title="Discharge Summary",
            missing=True,
            page_no=5
        )


def test_schema_validation_rejects_non_sequential_sr_no(sample_phase3_data):
    """Schema must reject non-sequential sr_no."""
    titles = [req["document_title"] for req in sample_phase3_data["policy_requirements"]]
    bad_data = {
        "missing_documents": [
            {"sr_no": 1, "document_title": "Discharge Summary", "missing": False, "page_no": 5},
            {"sr_no": 3, "document_title": "Final Hospital Bill", "missing": False, "page_no": 7},  # skipped 2!
            {"sr_no": 3, "document_title": "Investigation Reports", "missing": True, "page_no": None},
            {"sr_no": 4, "document_title": "Prescription", "missing": False, "page_no": 10},
            {"sr_no": 5, "document_title": "Pharmacy Bills", "missing": True, "page_no": None}
        ]
    }
    with pytest.raises(Phase4ValidationError) as exc_info:
        validate_output_against_requirements(bad_data, titles)
    assert "sequential" in str(exc_info.value).lower()
