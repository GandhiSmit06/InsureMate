"""tests/test_validation_tool.py
Unit tests for Phase 6 DocumentValidationTool.
Tests:
- Tool schema definition
- Standard execute() with extracted_data dictionary
- Standard execute() with extracted_documents list
- Validation pass and failure cases
- Backward compatibility with legacy run()
"""

import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.document_validation_tool import DocumentValidationTool


@pytest.fixture
def validation_tool():
    return DocumentValidationTool()


@pytest.fixture
def valid_policy_doc():
    return {
        "page_number": 1,
        "document_type": "insurance_policy",
        "document_title": "ICICI Lombard Policy Certificate",
        "policy_number": "4225i/ELVT/384538792/00/000",
        "policy_holder_name": "Maulikkumar Pathak",
        "policy_start_date": "12/03/2025",
        "policy_end_date": "11/03/2028",
    }


@pytest.fixture
def valid_bill_doc():
    return {
        "page_number": 2,
        "document_type": "medical_bill",
        "document_title": "Final Inpatient Bill",
        "bill_number": "BILL-2024-95151",
        "patient_name": "Parth M. Pathak",
        "document_date": "25/10/2024",
        "bill_amount": "48,500.00",
    }


def test_validation_tool_schema(validation_tool):
    """Verify tool exposes proper schema for agent discovery."""
    tool = validation_tool
    assert tool.name == "document_validation_tool"
    assert "Deterministically validates extracted documents" in tool.description
    assert tool.schema["function"]["name"] == "document_validation_tool"


def test_validation_tool_execute_valid_batch(validation_tool, valid_policy_doc, valid_bill_doc):
    """Test standard execute() with valid extracted_data."""
    tool = validation_tool
    payload = {
        "claim_id": "CLM-P6-VAL-01",
        "extracted_data": {
            "total_pages": 2,
            "extracted_documents": [valid_policy_doc, valid_bill_doc],
        },
    }
    result = tool.execute(payload)

    assert result["success"] is True
    assert result["claim_id"] == "CLM-P6-VAL-01"
    assert result["validation_results"]["valid"] is True
    assert result["validation_results"]["total_documents"] == 2
    assert result["validation_results"]["valid_documents"] == 2
    assert result["validation_results"]["invalid_documents"] == 0
    assert result["errors"] == []


def test_validation_tool_execute_invalid_document(validation_tool, valid_policy_doc):
    """Test standard execute() with a document missing required fields."""
    tool = validation_tool
    corrupt_bill = {
        "page_number": 2,
        "document_type": "medical_bill",
        "bill_number": None,  # Missing!
        "patient_name": "Parth Pathak",
        "document_date": None,  # Missing!
        "bill_amount": "1000",
    }
    payload = {
        "claim_id": "CLM-P6-VAL-02",
        "extracted_documents": [valid_policy_doc, corrupt_bill],
    }
    result = tool.execute(payload)

    assert result["success"] is True  # Tool execution succeeded, identified validation failure
    assert result["validation_results"]["valid"] is False
    assert result["validation_results"]["invalid_documents"] == 1
    assert len(result["errors"]) > 0


def test_validation_tool_execute_empty(validation_tool):
    """Test execute() with empty documents returns valid=False."""
    tool = validation_tool
    result = tool.execute({"claim_id": "CLM-EMPTY", "extracted_data": []})

    assert result["success"] is True
    assert result["validation_results"]["valid"] is False
    assert result["validation_results"]["total_documents"] == 0


def test_validation_tool_legacy_run(validation_tool, valid_policy_doc):
    """Verify legacy run() method remains fully functional."""
    tool = validation_tool
    res = tool.run(valid_policy_doc)

    assert res["status"] == "success"
    assert res["valid"] is True
    assert res["total_documents"] == 1
    assert res["error"] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
