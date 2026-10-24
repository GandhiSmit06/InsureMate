"""tests/test_policy_coverage_date_resolution.py
Unit tests verifying dynamic policy coverage date resolution across industry synonyms,
standardized key aliases in policy_period, and absence of hardcoded date fallbacks.
"""

import pytest
from services.validity_checker.checker import ValidityChecker
from tools.validity_checker_tool import ValidityCheckerTool


def test_dynamic_policy_date_synonyms_resolution():
    """Verify validity checker resolves start and end dates from diverse synonym nomenclatures."""
    checker = ValidityChecker()

    # Test Case 1: Inception and Expiry nomenclature
    policy_data_1 = {
        "policy_number": "POL-TEST-001",
        "inception_date": "01/04/2026",
        "expiry_date": "31/03/2027",
    }
    claim_docs_1 = [
        {"document_type": "hospital_document", "page_number": 2, "document_date": "15/09/2026"}
    ]

    res1 = checker.check_validity(policy_data=policy_data_1, document_data=claim_docs_1)
    assert res1.valid is True
    period1 = res1.policy_period
    assert period1["policy_start_date"] == "01/04/2026"
    assert period1["policy_end_date"] == "31/03/2027"
    assert period1["start"] == "01/04/2026"
    assert period1["end"] == "31/03/2027"

    # Test Case 2: Effective date and Expiration date nomenclature
    policy_data_2 = {
        "policy_number": "POL-TEST-002",
        "effective_date": "2026-06-01",
        "expiration_date": "2027-05-31",
    }
    claim_docs_2 = [
        {"document_type": "medical_bill", "page_number": 3, "bill_date": "2026-10-15"}
    ]

    res2 = checker.check_validity(policy_data=policy_data_2, document_data=claim_docs_2)
    assert res2.valid is True
    period2 = res2.policy_period
    assert period2["start"] == "01/06/2026"
    assert period2["end"] == "31/05/2027"
    assert period2["policy_start_date"] == "01/06/2026"
    assert period2["policy_end_date"] == "31/05/2027"


def test_multi_page_policy_date_aggregation():
    """Verify that dates spread across multiple policy pages are correctly aggregated."""
    checker = ValidityChecker()
    policy_pages = [
        {"document_type": "insurance_policy", "page_number": 1, "policy_number": "POL-AGG-123"},
        {"document_type": "insurance_policy", "page_number": 2, "coverage_start_date": "01/01/2026"},
        {"document_type": "insurance_policy", "page_number": 3, "coverage_end_date": "31/12/2026"}
    ]
    claim_docs = [
        {"document_type": "hospital_bill", "page_number": 4, "document_date": "10/05/2026"}
    ]

    res = checker.check_validity(policy_data=policy_pages, document_data=claim_docs)
    assert res.valid is True
    assert res.policy_period["start"] == "01/01/2026"
    assert res.policy_period["end"] == "31/12/2026"


def test_validity_checker_tool_returns_standardized_keys():
    """Verify tool wrapper returns both canonical and shorthand aliases in tool results."""
    tool = ValidityCheckerTool()
    input_data = {
        "policy_data": {
            "policy_number": "POL-TOOL-001",
            "from_date": "15/05/2026",
            "to_date": "14/05/2027"
        },
        "document_data": [
            {"document_type": "admission_record", "page_number": 2, "document_date": "20/07/2026"}
        ]
    }
    result = tool.execute(input_data)
    assert result["success"] is True
    period = result["policy_period"]
    assert period["start"] == "15/05/2026"
    assert period["end"] == "14/05/2027"
    assert period["policy_start_date"] == "15/05/2026"
    assert period["policy_end_date"] == "14/05/2027"
