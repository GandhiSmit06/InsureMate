"""tests/test_missing_document_tool.py
Unit tests for Phase 6 MissingDocumentTool.
Tests:
- Tool schema definition
- Standard execute() with mocked LLM gateway (no remote/daemon requirement)
- Detection of present vs missing documents
- Backward compatibility with legacy run()
"""

import json
import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.missing_document.llm_gateway import LLMGateway
from tests.conftest import MockLLMClient
from tools.missing_document_tool import MissingDocumentTool


@pytest.fixture
def missing_doc_tool():
    # Configure mock responses for LLM calls:
    # 1. extract_policy_requirements -> returns required documents
    # 2. match_submitted_documents -> returns matching verdict
    call1_resp = json.dumps({
        "policy_requirements": [
            {"document_title": "Discharge Summary"},
            {"document_title": "Final Hospital Bill"}
        ]
    })
    call2_resp = json.dumps({
        "status": "success",
        "missing_documents": [
            {"sr_no": 1, "document_title": "Discharge Summary", "missing": False, "page_no": 2},
            {"sr_no": 2, "document_title": "Final Hospital Bill", "missing": True, "page_no": None}
        ]
    })
    client = MockLLMClient(responses=[call1_resp, call2_resp])
    gateway = LLMGateway(client=client)
    return MissingDocumentTool(gateway=gateway)


def test_missing_doc_tool_schema(missing_doc_tool):
    """Verify tool exposes proper schema for agent discovery."""
    tool = missing_doc_tool
    assert tool.name == "missing_document_tool"
    assert "Dynamically determines required documents" in tool.description
    assert tool.schema["function"]["name"] == "missing_document_tool"


def test_missing_doc_tool_execute(missing_doc_tool):
    """Test standard execute() identifying 1 present and 1 missing document."""
    tool = missing_doc_tool
    payload = {
        "claim_id": "CLM-P6-MISSING-01",
        "extracted_data": {
            "extracted_documents": [
                {
                    "page_number": 1,
                    "document_type": "insurance_policy",
                    "policy_clauses": ["Discharge summary required", "Hospital bill required"],
                },
                {
                    "page_number": 2,
                    "document_type": "hospital_document",
                    "document_title": "Discharge Summary",
                }
            ]
        }
    }
    result = tool.execute(payload)

    assert result["success"] is True
    assert result["claim_id"] == "CLM-P6-MISSING-01"
    assert len(result["missing_documents"]) == 2

    # One document missing, one document present
    missing_items = [d for d in result["missing_documents"] if d.get("missing")]
    present_items = [d for d in result["missing_documents"] if not d.get("missing")]

    assert len(missing_items) == 1
    assert missing_items[0]["document_title"] == "Final Hospital Bill"
    assert missing_items[0]["page_no"] is None

    assert len(present_items) == 1
    assert present_items[0]["document_title"] == "Discharge Summary"
    assert present_items[0]["page_no"] == 2


def test_missing_doc_tool_legacy_run():
    """Verify legacy run() method remains fully functional."""
    call1_resp = json.dumps({"policy_requirements": [{"document_title": "Discharge Summary"}]})
    call2_resp = json.dumps({
        "status": "success",
        "missing_documents": [{"sr_no": 1, "document_title": "Discharge Summary", "missing": False, "page_no": 2}]
    })
    client = MockLLMClient(responses=[call1_resp, call2_resp])
    tool = MissingDocumentTool(gateway=LLMGateway(client=client))

    phase1_payload = {
        "extracted_documents": [
            {"page_number": 1, "document_type": "insurance_policy", "policy_clauses": ["Requires Discharge summary"]},
            {"page_number": 2, "document_type": "hospital_document", "document_title": "Discharge Summary"}
        ]
    }
    res = tool.run(phase1_output=phase1_payload)

    assert res["status"] == "success"
    assert len(res["missing_documents"]) == 1
    assert res["missing_documents"][0]["missing"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
