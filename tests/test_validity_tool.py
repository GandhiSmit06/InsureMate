"""tests/test_validity_tool.py
Unit tests for Phase 6 ValidityCheckerTool.
Tests:
- Tool schema definition
- Standard execute() with explicit policy_data and document_data
- Standard execute() with auto-partitioning from extracted_data
- Valid date inside policy period vs expired date
- Backward compatibility with legacy run()
"""

import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.validity_checker_tool import ValidityCheckerTool


@pytest.fixture
def validity_tool():
    return ValidityCheckerTool()


@pytest.fixture
def standard_policy():
    return {
        "policy_number": "POL-2026-9900",
        "policy_holder_name": "Maulikkumar Pathak",
        "policy_start_date": "01/01/2026",
        "policy_end_date": "31/12/2026",
        "insured_names": ["Maulikkumar Pathak", "Parth Pathak"],
    }


def test_validity_tool_schema(validity_tool):
    """Verify tool exposes proper schema for agent discovery."""
    tool = validity_tool
    assert tool.name == "validity_checker_tool"
    assert "Deterministically verifies whether medical bills" in tool.description
    assert tool.schema["function"]["name"] == "validity_checker_tool"


def test_validity_tool_execute_valid_dates(validity_tool, standard_policy):
    """Test execute() with bill date within policy period."""
    tool = validity_tool
    bill = {
        "document_type": "medical_bill",
        "page_number": 1,
        "document_date": "15/08/2026",
        "patient_name": "Parth Pathak",
        "bill_amount": "25000",
    }
    payload = {
        "claim_id": "CLM-P6-VAL-01",
        "policy_data": standard_policy,
        "document_data": bill,
    }
    result = tool.execute(payload)

    assert result["success"] is True
    assert result["claim_id"] == "CLM-P6-VAL-01"
    assert result["validity_results"]["valid"] is True
    assert len(result["validity_results"]["checks"]) == 1
    assert result["errors"] == []


def test_validity_tool_execute_expired_date(validity_tool, standard_policy):
    """Test execute() with bill date after policy expiry."""
    tool = validity_tool
    bill_expired = {
        "document_type": "medical_bill",
        "page_number": 2,
        "document_date": "15/01/2027",  # Expired!
        "patient_name": "Parth Pathak",
        "bill_amount": "12000",
    }
    payload = {
        "claim_id": "CLM-P6-VAL-02",
        "policy_data": standard_policy,
        "document_data": [bill_expired],
    }
    result = tool.execute(payload)

    assert result["success"] is True
    assert result["validity_results"]["valid"] is False
    assert len(result["errors"]) > 0


def test_validity_tool_auto_partition(validity_tool, standard_policy):
    """Test execute() automatically partitions policy and bill from extracted_data."""
    tool = validity_tool
    policy_doc = dict(standard_policy)
    policy_doc["document_type"] = "insurance_policy"

    bill_doc = {
        "document_type": "medical_bill",
        "page_number": 2,
        "document_date": "10/05/2026",
        "patient_name": "Parth Pathak",
        "bill_amount": "15000",
    }
    payload = {
        "claim_id": "CLM-P6-AUTO",
        "extracted_data": {
            "total_pages": 2,
            "extracted_documents": [policy_doc, bill_doc],
        },
    }
    result = tool.execute(payload)

    assert result["success"] is True
    assert result["validity_results"]["valid"] is True
    assert len(result["validity_results"]["checks"]) == 1


def test_validity_tool_legacy_run(validity_tool, standard_policy):
    """Verify legacy run() method remains fully functional."""
    tool = validity_tool
    bill = {
        "document_type": "medical_bill",
        "page_number": 1,
        "document_date": "15/08/2026",
        "patient_name": "Parth Pathak",
    }
    res = tool.run(policy_data=standard_policy, document_data=bill)

    assert res["status"] == "success"
    assert res["valid"] is True
    assert len(res["checks"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
