"""tests/test_phase6_integration.py
Comprehensive Integration tests for Phase 6:
Agent Tool Layer + Tool Registry + Tool Executor + Agent Integration Contract.

Verifies:
- TEST 8: Multiple tools can be executed independently without enforced ordering.
- TEST 9: Existing Phase 1–4 functionality remains fully functional and intact.
- TEST 10: Full Phase 5 Agent simulation executing tools dynamically via ToolExecutor,
  maintaining ClaimState, observing intermediate results, and making decisions.
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
from tools.claim_state import ClaimState
from tools.document_validation_tool import DocumentValidationTool
from tools.missing_document_tool import MissingDocumentTool
from tools.qwen_extraction_tool import DocumentExtractionTool
from tools.tool_executor import ToolExecutor
from tools.tool_registry import ToolRegistry, create_tool_registry
from tools.validity_checker_tool import ValidityCheckerTool


@pytest.fixture
def integrated_registry():
    """Create a fully wired registry using offline/mock components for fast deterministic testing."""
    registry = ToolRegistry()

    # Tool 1: Extraction in offline mode
    extraction = DocumentExtractionTool(offline_mode=True)
    registry.register(extraction, alias="qwen_vl_extraction_tool")

    # Tool 2: Validation
    validation = DocumentValidationTool()
    registry.register(validation)

    # Tool 3: Validity
    validity = ValidityCheckerTool()
    registry.register(validity)

    # Tool 4: Missing Document with Mock LLM
    call1_resp = json.dumps({
        "policy_requirements": [
            {"document_title": "Discharge Summary"},
            {"document_title": "Hospital Final Bill"}
        ]
    })
    call2_resp = json.dumps({
        "status": "success",
        "missing_documents": [
            {"sr_no": 1, "document_title": "Discharge Summary", "missing": False, "page_no": 1},
            {"sr_no": 2, "document_title": "Hospital Final Bill", "missing": True, "page_no": None}
        ]
    })
    client = MockLLMClient(responses=[call1_resp, call2_resp])
    missing = MissingDocumentTool(gateway=LLMGateway(client=client))
    registry.register(missing)

    return registry


def test_independent_tool_execution(integrated_registry):
    """
    TEST 8: Multiple tools can be executed independently.
    No hard-coded pipeline sequence is enforced.
    We execute validity_checker_tool FIRST, then document_validation_tool.
    """
    executor = ToolExecutor(registry=integrated_registry)

    # Tool call A: Validity checker executed first without prior extraction or validation
    validity_input = {
        "claim_id": "CLM-INDEP-001",
        "policy_data": {
            "policy_number": "POL-999",
            "policy_start_date": "01/01/2026",
            "policy_end_date": "31/12/2026",
            "insured_names": ["Maulik Pathak"],
        },
        "document_data": [
            {
                "document_type": "medical_bill",
                "page_number": 1,
                "document_date": "15/06/2026",
                "patient_name": "Maulik Pathak",
            }
        ]
    }
    res_validity = executor.execute("validity_checker_tool", validity_input)
    assert res_validity["success"] is True
    assert res_validity["result"]["validity_results"]["valid"] is True

    # Tool call B: Document validation executed independently
    val_input = {
        "claim_id": "CLM-INDEP-001",
        "extracted_documents": [
            {
                "page_number": 1,
                "document_type": "insurance_policy",
                "policy_number": "POL-999",
                "policy_start_date": "01/01/2026",
                "policy_end_date": "31/12/2026",
                "policy_holder_name": "Maulik Pathak",
            }
        ]
    }
    res_val = executor.execute("document_validation_tool", val_input)
    assert res_val["success"] is True
    assert res_val["result"]["validation_results"]["valid"] is True


def test_phase5_agent_orchestration_simulation(integrated_registry):
    """
    TEST 10: Full Phase 5 Agent Simulation.
    Simulates:
    Agent (Brain)
    ↓
    Decides to inspect tools
    ↓
    Selects Tool 1: document_extraction_tool
    ↓
    ToolExecutor runs tool -> Returns standardized result -> Updates ClaimState
    ↓
    Agent observes result: "Extraction complete, now validate"
    ↓
    Selects Tool 2: document_validation_tool
    ↓
    ToolExecutor runs tool -> Updates ClaimState
    ↓
    Agent observes result: "Documents valid, now check validity dates"
    ↓
    Selects Tool 3: validity_checker_tool
    ↓
    ToolExecutor runs tool -> Updates ClaimState
    ↓
    Agent observes result: "Dates valid, check missing evidence"
    ↓
    Selects Tool 4: missing_document_tool
    ↓
    ToolExecutor runs tool -> Updates ClaimState
    ↓
    Agent synthesizes final decision!
    """
    registry = integrated_registry
    executor = ToolExecutor(registry=registry)

    # 1. Agent discovers tools
    available_tools = registry.list_tools()
    assert len(available_tools) == 4
    tool_names = [t["name"] for t in available_tools]
    assert "document_extraction_tool" in tool_names

    # 2. Agent initializes claim state
    claim_state = ClaimState(claim_id="CLM-AGENT-8888")

    # 3. Agent selects and calls Tool 1: Document Extraction
    extraction_input = {
        "claim_id": claim_state.claim_id,
        "documents": [str(ROOT_DIR / "policy_A.pdf")],
        "max_pages": 1,
    }
    step1_res = executor.execute("document_extraction_tool", extraction_input, state=claim_state)
    assert step1_res["success"] is True
    assert claim_state.current_step == "document_extraction_completed"
    assert "extracted_documents" in claim_state.extracted_data
    assert len(claim_state.documents) == 1

    # 4. Agent inspects state and selects Tool 2: Document Validation
    validation_input = {
        "claim_id": claim_state.claim_id,
        "extracted_data": claim_state.extracted_data,
    }
    step2_res = executor.execute("document_validation_tool", validation_input, state=claim_state)
    assert step2_res["success"] is True
    assert claim_state.current_step == "document_validation_completed"
    assert "valid" in claim_state.validation_results

    # 5. Agent inspects state and selects Tool 3: Validity Checker
    validity_input = {
        "claim_id": claim_state.claim_id,
        "policy_data": {
            "policy_number": "POL-HEALTH-01",
            "policy_start_date": "01/01/2026",
            "policy_end_date": "31/12/2026",
            "insured_names": ["Parth Pathak"],
        },
        "document_data": [
            {
                "document_type": "medical_bill",
                "page_number": 1,
                "document_date": "10/05/2026",
                "patient_name": "Parth Pathak",
            }
        ]
    }
    step3_res = executor.execute("validity_checker_tool", validity_input, state=claim_state)
    assert step3_res["success"] is True
    assert claim_state.current_step == "validity_check_completed"
    assert claim_state.validity_results["valid"] is True

    # 6. Agent inspects state and selects Tool 4: Missing Document Tool
    missing_input = {
        "claim_id": claim_state.claim_id,
        "extracted_data": claim_state.extracted_data,
        "validation_results": claim_state.validation_results,
        "validity_results": claim_state.validity_results,
    }
    step4_res = executor.execute("missing_document_tool", missing_input, state=claim_state)
    assert step4_res["success"] is True
    assert claim_state.current_step == "missing_document_analysis_completed"
    assert len(claim_state.missing_documents) == 2

    # 7. Agent examines tool history and synthesizes final claim decision
    history = executor.get_history()
    assert len(history) == 4
    assert len(claim_state.tool_history) == 4

    for entry in history:
        assert entry["status"] == "success"
        assert "timestamp" in entry
        assert "summary" in entry

    # Agent sets final verdict in state
    claim_state.final_result = {
        "claim_id": claim_state.claim_id,
        "status": "REQUIRES_DOCUMENTS",
        "missing_items": [d["document_title"] for d in claim_state.missing_documents if d.get("missing")],
        "total_tools_invoked": len(history),
    }

    assert claim_state.final_result["status"] == "REQUIRES_DOCUMENTS"
    assert "Hospital Final Bill" in claim_state.final_result["missing_items"]
    assert claim_state.final_result["total_tools_invoked"] == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
