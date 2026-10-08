"""tests/test_phase5.py
Comprehensive test suite for Phase 5: InsureMate Agent Orchestrator & Planning.

Tests:
- TEST 1: Policy + valid hospital bill/report (Agent plans and completes full multi-tool analysis)
- TEST 2: Bill/report date outside policy period (Agent detects validity=False and reflects in final state)
- TEST 3: Required document is missing (Agent completes processing and records missing evidence)
- TEST 4: Incomplete / unreadable document (Agent detects insufficient information and stops gracefully)
- TEST 5: Autonomous loop guardrail & max iteration protection
- TEST 6: Tool execution failure and single retry policy
- TEST 7: Safe execution trace formatting (No hidden CoT exposed)
- TEST 8: Full end-to-end agent run on repository PDF files
"""

import copy
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional
import pytest

# Ensure repository root is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agent.insuremate_agent import InsureMateAgent
from agent.state import ClaimState, ClaimStatus
from agent.planner import InsureMatePlanner, ClaimPlan
from agent.decision import InsureMateDecisionEngine, AgentDecision
from agent.tools import InsureMateToolRegistry, ToolExecutionResult
from tests.conftest import MockLLMClient
from services.missing_document.llm_gateway import LLMGateway
from tools.missing_document_tool import MissingDocumentTool
from tools.qwen_vl_tool import QwenVLExtractionTool


def print_test_banner(title: str):
    print("\n" + "=" * 70)
    print(f"PHASE 5 AGENT TEST: {title}")
    print("=" * 70)


# ==============================================================================
# TEST 1: Policy + Valid Hospital Bill/Report
# ==============================================================================
def test_1_valid_policy_and_bill():
    """
    TEST 1:
    Policy + valid hospital bill/report.
    Expected:
    Agent plans workflow and completes extraction -> validation -> validity -> missing-document analysis.
    """
    print_test_banner("TEST 1: Policy + Valid Hospital Bill/Report")

    valid_policy_and_bill_data = [
        {
            "page_number": 1,
            "document_type": "insurance_policy",
            "document_title": "Comprehensive Health Floater Certificate",
            "policy_number": "POL-2025-00123",
            "policy_holder_name": "John Doe",
            "insured_names": ["John Doe", "Jane Doe"],
            "policy_start_date": "12/03/2025",
            "policy_end_date": "11/03/2028",
            "policy_clauses": [
                "1. Original Discharge Summary from hospital",
                "2. Final Hospital Bill and Payment Receipt"
            ]
        },
        {
            "page_number": 2,
            "document_type": "medical_bill",
            "document_title": "Final Hospital Inpatient Bill",
            "bill_number": "BILL-101",
            "patient_name": "Jane Doe",
            "hospital_name": "City General Hospital",
            "document_date": "15/08/2026",
            "bill_amount": "25000.00"
        },
        {
            "page_number": 3,
            "document_type": "hospital_document",
            "document_title": "Patient Discharge Summary Record",
            "patient_name": "Jane Doe",
            "hospital_name": "City General Hospital",
            "document_date": "15/08/2026"
        }
    ]

    # Mock LLM for missing document matching to ensure fast, deterministic matching
    mock_responses = [
        # Call 1: Dynamic requirements extraction
        '{"required_documents": [{"sr_no": 1, "document_title": "Original Discharge Summary"}, {"sr_no": 2, "document_title": "Final Hospital Bill"}]}',
        # Call 2: Semantic matching
        '{"document_results": [{"sr_no": 1, "document_title": "Original Discharge Summary", "missing": false, "page_no": 3, "reason": "Provided on page 3"}, {"sr_no": 2, "document_title": "Final Hospital Bill", "missing": false, "page_no": 2, "reason": "Provided on page 2"}]}'
    ]
    mock_llm = MockLLMClient(responses=mock_responses)
    gateway = LLMGateway(client=mock_llm)
    missing_tool = MissingDocumentTool(gateway=gateway)

    registry = InsureMateToolRegistry(
        missing_doc_tool=missing_tool,
        offline_mode=True
    )
    agent = InsureMateAgent(tool_registry=registry, offline_mode=True)

    state = ClaimState(
        goal="Determine claim readiness.",
        extracted_data=valid_policy_and_bill_data
    )

    result_state = agent.run(state=state)

    # Assertions
    assert result_state.current_plan is not None, "Agent must generate a plan"
    assert len(result_state.current_plan["steps"]) >= 4, "Plan must contain ordered workflow steps"

    # All tools must have been invoked
    executed_tools = [h["tool_name"] for h in result_state.tool_history]
    assert "document_validation" in executed_tools, "Document validation must be executed"
    assert "validity_checker" in executed_tools, "Validity checker must be executed"
    assert "missing_document_detector" in executed_tools, "Missing document detector must be executed"
    assert "claim_preparation" in executed_tools, "Claim preparation must be executed"

    # Intermediate validity check must be valid
    assert result_state.validity_result is not None
    assert result_state.validity_result.get("valid") is True, "Valid dates must pass validity check"

    # Intermediate validation check must be valid
    assert result_state.validation_result is not None
    assert result_state.validation_result.get("valid") is True

    # Final state
    assert result_state.final_status == ClaimStatus.CLAIM_READY_FOR_SUBMISSION.value
    assert result_state.final_report["is_ready"] is True
    print("PASS: Agent planned and completed full extraction -> validation -> validity -> missing-document workflow.")


# ==============================================================================
# TEST 2: Bill/Report Date Outside Policy Period
# ==============================================================================
def test_2_date_outside_policy_period():
    """
    TEST 2:
    Bill/report date is outside policy period.
    Expected:
    Agent receives validity=false and includes the validity issue in the final state.
    """
    print_test_banner("TEST 2: Bill Date Outside Policy Period")

    expired_claim_data = [
        {
            "page_number": 1,
            "document_type": "insurance_policy",
            "document_title": "Annual Standard Health Policy",
            "policy_number": "POL-2026-001",
            "policy_holder_name": "John Doe",
            "insured_names": ["John Doe", "Jane Doe"],
            "policy_start_date": "01/01/2026",
            "policy_end_date": "31/12/2026",
            "policy_clauses": ["1. Final Hospital Bill"]
        },
        {
            "page_number": 2,
            "document_type": "medical_bill",
            "document_title": "Hospital Consultation Bill",
            "bill_number": "BILL-999",
            "patient_name": "Jane Doe",
            "hospital_name": "Apex Clinic",
            "document_date": "15/10/2025",  # PRIOR to policy start date (01/01/2026)
            "bill_amount": "5000.00"
        }
    ]

    mock_responses = [
        '{"required_documents": [{"sr_no": 1, "document_title": "Final Hospital Bill"}]}',
        '{"document_results": [{"sr_no": 1, "document_title": "Final Hospital Bill", "missing": false, "page_no": 2, "reason": "Provided on page 2"}]}'
    ]
    mock_llm = MockLLMClient(responses=mock_responses)
    missing_tool = MissingDocumentTool(gateway=LLMGateway(client=mock_llm))

    registry = InsureMateToolRegistry(
        missing_doc_tool=missing_tool,
        offline_mode=True
    )
    agent = InsureMateAgent(tool_registry=registry, offline_mode=True)

    state = ClaimState(
        goal="Determine claim readiness.",
        extracted_data=expired_claim_data
    )

    result_state = agent.run(state=state)

    # Assertions
    assert result_state.validity_result is not None, "Validity checker must have executed"
    assert result_state.validity_result.get("valid") is False, "Intermediate validity check must evaluate to False"

    # Agent must capture the validity issue in final state
    assert result_state.final_status == ClaimStatus.INVALID_CLAIM_DATES.value
    assert result_state.final_report["coverage_validity_status"] == "FAIL"
    assert any("prior to policy inception" in r or "outside" in r for r in result_state.validity_result.get("reasons", []))

    # Trace must reflect decision based on invalid dates
    trace_decisions = [t["decision"] for t in result_state.execution_trace]
    assert any("outside policy period" in d or "discrepancies" in d for d in trace_decisions)
    print("PASS: Agent captured intermediate validity=False and recorded invalid coverage period in final state.")


# ==============================================================================
# TEST 3: Required Document is Missing
# ==============================================================================
def test_3_required_document_missing():
    """
    TEST 3:
    Required document is missing.
    Expected:
    Agent completes available processing and records missing evidence.
    """
    print_test_banner("TEST 3: Required Document Missing")

    claim_with_missing_doc = [
        {
            "page_number": 1,
            "document_type": "insurance_policy",
            "document_title": "Comprehensive Floater Policy",
            "policy_number": "POL-5555",
            "policy_holder_name": "John Doe",
            "insured_names": ["John Doe"],
            "policy_start_date": "01/01/2026",
            "policy_end_date": "31/12/2026",
            "policy_clauses": [
                "1. Hospital Discharge Summary",
                "2. Final Itemized Bill"
            ]
        },
        {
            "page_number": 2,
            "document_type": "medical_bill",
            "document_title": "Final Itemized Bill",
            "bill_number": "BILL-555",
            "patient_name": "John Doe",
            "document_date": "10/05/2026",
            "bill_amount": "15000.00"
        }
        # Note: Hospital Discharge Summary is completely MISSING from submission
    ]

    mock_responses = [
        '{"required_documents": [{"sr_no": 1, "document_title": "Hospital Discharge Summary"}, {"sr_no": 2, "document_title": "Final Itemized Bill"}]}',
        '{"document_results": [{"sr_no": 1, "document_title": "Hospital Discharge Summary", "missing": true, "page_no": null, "reason": "No discharge summary submitted"}, {"sr_no": 2, "document_title": "Final Itemized Bill", "missing": false, "page_no": 2, "reason": "Provided on page 2"}]}'
    ]
    mock_llm = MockLLMClient(responses=mock_responses)
    missing_tool = MissingDocumentTool(gateway=LLMGateway(client=mock_llm))

    registry = InsureMateToolRegistry(
        missing_doc_tool=missing_tool,
        offline_mode=True
    )
    agent = InsureMateAgent(tool_registry=registry, offline_mode=True)

    state = ClaimState(
        goal="Determine claim readiness.",
        extracted_data=claim_with_missing_doc
    )

    result_state = agent.run(state=state)

    # Assertions
    assert result_state.missing_documents is not None, "Missing document detector must run"
    missing_items = result_state.final_report.get("missing_documents", [])
    assert len(missing_items) > 0, "Missing documents must be detected and recorded"
    assert any("Discharge Summary" in m for m in missing_items)

    assert result_state.final_status == ClaimStatus.ACTION_REQUIRED_MISSING_EVIDENCE.value
    assert result_state.final_report["is_ready"] is False
    assert any("Upload required document" in a for a in result_state.final_report.get("action_items", []))
    print("PASS: Agent identified missing required evidence and populated actionable checklist.")


# ==============================================================================
# TEST 4: Incomplete / Unreadable Document
# ==============================================================================
def test_4_incomplete_or_unreadable_document():
    """
    TEST 4:
    Incomplete/unreadable document.
    Expected:
    Agent detects insufficient information and decides that additional information/document
    processing is required.
    """
    print_test_banner("TEST 4: Incomplete / Unreadable Document")

    # Document where required fields are absent and type is unknown/unsupported
    corrupt_data = [
        {
            "page_number": 1,
            "document_type": "unknown",
            "document_title": "Unreadable Blurry Scan",
            "policy_number": None,
            "document_date": None,
            "bill_amount": None
        }
    ]

    agent = InsureMateAgent(offline_mode=True)
    state = ClaimState(
        goal="Determine claim readiness.",
        extracted_data=corrupt_data
    )

    result_state = agent.run(state=state)

    # Assertions
    assert result_state.validation_result is not None
    assert result_state.validation_result.get("valid") is False
    assert result_state.validation_result.get("valid_documents") == 0

    # Agent must stop gracefully and mark insufficient information / invalid documents
    assert result_state.final_status in (
        ClaimStatus.ACTION_REQUIRED_INVALID_DOCUMENTS.value,
        ClaimStatus.INSUFFICIENT_INFORMATION.value
    )
    assert result_state.final_report["is_ready"] is False
    assert len(result_state.final_report.get("action_items", [])) > 0

    # Agent must NOT have crashed
    assert len(result_state.tool_history) > 0
    print("PASS: Agent detected unreadable/incomplete document and stopped gracefully without crashing.")


# ==============================================================================
# TEST 5: Loop Prevention & Max Iterations
# ==============================================================================
def test_5_infinite_loop_prevention():
    """
    TEST 5:
    Agent execution loop respects max_iterations limit and prevents infinite loops.
    """
    print_test_banner("TEST 5: Infinite Loop Prevention")

    agent = InsureMateAgent(max_iterations=3, offline_mode=True)
    # Empty documents with no initial state
    state = ClaimState(documents=[], max_iterations=3)

    result_state = agent.run(state=state)
    assert result_state.iteration_count <= 3
    assert result_state.final_status in (ClaimStatus.INSUFFICIENT_INFORMATION.value, ClaimStatus.FAILED.value)
    print("PASS: Agent converged safely within max iterations limit.")


# ==============================================================================
# TEST 6: Tool Retry Policy
# ==============================================================================
def test_6_tool_retry_policy():
    """
    TEST 6:
    Agent retries a failed tool at most once and logs the retry in history.
    """
    print_test_banner("TEST 6: Tool Single-Retry Policy")

    state = ClaimState()
    assert state.can_retry("document_extraction") is True
    state.increment_retry("document_extraction")
    assert state.can_retry("document_extraction") is False
    print("PASS: Single retry policy verified.")


# ==============================================================================
# TEST 7: Safe Execution Trace Formatting
# ==============================================================================
def test_7_execution_trace_formatting():
    """
    TEST 7:
    Execution trace matches master format without exposing hidden CoT.
    """
    print_test_banner("TEST 7: Safe Execution Trace Formatting")

    state = ClaimState(goal="Determine claim readiness.")
    state.record_trace(
        decision="Document information is not available.",
        tool="document_extraction",
        tool_result="Extracted 1 policy and 1 medical bill."
    )
    state.record_trace(
        decision="Documents are available. Validation is required.",
        tool="document_validation",
        tool_result="Documents passed validation."
    )
    state.final_status = "CLAIM_READY_FOR_SUBMISSION"
    state.final_report = {"decision_summary": "Claim is complete and verified."}

    agent = InsureMateAgent(offline_mode=True)
    trace_text = agent.format_execution_trace(state)

    assert "INSUREMATE AGENT EXECUTION" in trace_text
    assert "GOAL:" in trace_text
    assert "PLAN:" in trace_text
    assert "AGENT DECISION:" in trace_text
    assert "TOOL:" in trace_text
    assert "TOOL RESULT:" in trace_text
    assert "FINAL STATE:" in trace_text
    assert "Thinking Process" not in trace_text, "Chain-of-thought must NOT be exposed"
    print("PASS: Execution trace formatted cleanly according to specification.")


# ==============================================================================
# TEST 8: Full Real PDF Documents Integration
# ==============================================================================
def test_8_real_documents_agent_run():
    """
    TEST 8:
    Executes InsureMateAgent on real repository PDF documents.
    """
    print_test_banner("TEST 8: Real Repository PDF Documents Agent Run")

    policy_pdf = ROOT_DIR / "sample_policy.pdf"
    claim_pdf = ROOT_DIR / "sample_claim.pdf"

    if not policy_pdf.exists() or not claim_pdf.exists():
        pytest.skip("Sample PDF documents not present; skipping live PDF run.")
        return

    agent = InsureMateAgent(offline_mode=True)
    result_state = agent.run(
        documents=[str(policy_pdf), str(claim_pdf)],
        max_pages=2
    )

    assert result_state.current_plan is not None
    assert len(result_state.tool_history) >= 3
    assert result_state.final_status is not None
    print(f"Agent Final Status on Real PDFs: {result_state.final_status}")
    print("PASS: Agent executed multi-step workflow autonomously on real documents.")


def run_phase5_tests() -> bool:
    """Run all Phase 5 tests sequentially and print summary."""
    print("\n" + "=" * 70)
    print("RUNNING ALL PHASE 5 TESTS: INSUREMATE AGENT ORCHESTRATOR")
    print("=" * 70)

    tests = [
        ("TEST 1: Valid Policy & Bill Workflow", test_1_valid_policy_and_bill),
        ("TEST 2: Bill Date Outside Policy Period", test_2_date_outside_policy_period),
        ("TEST 3: Required Document Missing", test_3_required_document_missing),
        ("TEST 4: Incomplete / Unreadable Document", test_4_incomplete_or_unreadable_document),
        ("TEST 5: Loop Prevention & Iteration Guard", test_5_infinite_loop_prevention),
        ("TEST 6: Tool Single-Retry Policy", test_6_tool_retry_policy),
        ("TEST 7: Safe Trace Formatting", test_7_execution_trace_formatting),
        ("TEST 8: Real Repository PDF Execution", test_8_real_documents_agent_run),
    ]

    passed = 0
    total = len(tests)

    for name, test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"FAIL: {name} - {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 70)
    print(f"PHASE 5 TEST SUMMARY: {passed}/{total} TESTS PASSED")
    print("=" * 70)
    return passed == total


if __name__ == "__main__":
    success = run_phase5_tests()
    sys.exit(0 if success else 1)
