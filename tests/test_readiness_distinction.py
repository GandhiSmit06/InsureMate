"""
Targeted tests for Phase 4: Verification of Claim Readiness & Assessment Correctness.
Validates that the system strictly distinguishes between:
1. Ready claims (all mandatory checks pass)
2. Claims requiring additional documents / missing evidence
3. Claims with invalid dates or invalid documents
4. Incomplete assessments (checks have not run or remain unresolved)
5. Technical failures (iteration limit, tool failure, abort)
"""
import pytest
from agent.state import ClaimState, ClaimStatus
from agent.tools import InsureMateToolRegistry, ClaimPreparationAdapter
from agent.insuremate_agent import InsureMateAgent


SAMPLE_VALID_POLICY = {
    "document_type": "insurance_policy",
    "policy_holder": "Ananya Sharma",
    "policy_number": "POL-992288",
    "effective_date": "2024-01-01",
    "expiration_date": "2024-12-31",
    "coverage_details": "Comprehensive Health Plan"
}

SAMPLE_VALID_BILL = {
    "document_type": "hospital_bill",
    "patient_name": "Ananya Sharma",
    "invoice_number": "INV-7721",
    "service_date": "2024-05-15",
    "admission_date": "2024-05-14",
    "discharge_date": "2024-05-16",
    "total_amount": "45000.00"
}


from tests.conftest import MockLLMClient


def test_readiness_all_checks_passed():
    """All mandatory checks pass -> CLAIM_READY_FOR_SUBMISSION."""
    adapter = ClaimPreparationAdapter()
    state = ClaimState(
        claim_id="test-claim-ready",
        extracted_data=[SAMPLE_VALID_POLICY, SAMPLE_VALID_BILL],
        validation_result={"valid": True, "valid_documents": 2, "total_documents": 2},
        validity_result={"valid": True, "reasons": ["Dates are within coverage"]},
        missing_documents={"missing_documents": [], "missing_count": 0}
    )
    res = adapter.run(state)
    assert res.status == "success"
    assert state.final_status == ClaimStatus.CLAIM_READY_FOR_SUBMISSION.value
    assert state.final_report["is_ready"] is True


def test_readiness_document_validation_failed():
    """Document validation failed -> ACTION_REQUIRED_INVALID_DOCUMENTS."""
    adapter = ClaimPreparationAdapter()
    state = ClaimState(
        claim_id="test-claim-invalid-doc",
        extracted_data=[SAMPLE_VALID_POLICY, SAMPLE_VALID_BILL],
        validation_result={"valid": False, "reasons": ["Missing mandatory invoice number"]},
        validity_result={"valid": True, "reasons": []},
        missing_documents={"missing_documents": [], "missing_count": 0}
    )
    res = adapter.run(state)
    assert res.status == "success"
    assert state.final_status == ClaimStatus.ACTION_REQUIRED_INVALID_DOCUMENTS.value
    assert state.final_report["is_ready"] is False


def test_readiness_date_outside_policy_period():
    """Incident date falls outside coverage -> INVALID_CLAIM_DATES."""
    adapter = ClaimPreparationAdapter()
    state = ClaimState(
        claim_id="test-claim-invalid-dates",
        extracted_data=[SAMPLE_VALID_POLICY, SAMPLE_VALID_BILL],
        validation_result={"valid": True, "reasons": []},
        validity_result={"valid": False, "reasons": ["Service date 2025-05-15 is after policy expiration 2024-12-31"]},
        missing_documents={"missing_documents": [], "missing_count": 0}
    )
    res = adapter.run(state)
    assert res.status == "success"
    assert state.final_status == ClaimStatus.INVALID_CLAIM_DATES.value
    assert state.final_report["is_ready"] is False


def test_readiness_missing_documents_detected():
    """Mandatory evidence missing -> ACTION_REQUIRED_MISSING_EVIDENCE."""
    adapter = ClaimPreparationAdapter()
    state = ClaimState(
        claim_id="test-claim-missing-docs",
        extracted_data=[SAMPLE_VALID_POLICY, SAMPLE_VALID_BILL],
        validation_result={"valid": True, "reasons": []},
        validity_result={"valid": True, "reasons": []},
        missing_documents={
            "missing_documents": [
                {"document_type": "discharge_summary", "document_title": "Discharge Summary", "missing": True}
            ],
            "missing_count": 1
        }
    )
    res = adapter.run(state)
    assert res.status == "success"
    assert state.final_status == ClaimStatus.ACTION_REQUIRED_MISSING_EVIDENCE.value
    assert state.final_report["is_ready"] is False
    assert "Discharge Summary" in state.final_report["missing_documents"]


def test_readiness_incomplete_assessment_missing_validation():
    """Validation check has NOT been executed -> INSUFFICIENT_INFORMATION (never ready)."""
    adapter = ClaimPreparationAdapter()
    state = ClaimState(
        claim_id="test-incomplete-no-validation",
        extracted_data=[SAMPLE_VALID_POLICY, SAMPLE_VALID_BILL],
        validation_result=None,  # Validation not run!
        validity_result={"valid": True, "reasons": []},
        missing_documents={"missing_documents": [], "missing_count": 0}
    )
    res = adapter.run(state)
    assert res.status == "success"
    assert state.final_status == ClaimStatus.INSUFFICIENT_INFORMATION.value
    assert state.final_report["is_ready"] is False


def test_readiness_incomplete_assessment_missing_validity():
    """Date validity check has NOT been executed -> INSUFFICIENT_INFORMATION (never ready)."""
    adapter = ClaimPreparationAdapter()
    state = ClaimState(
        claim_id="test-incomplete-no-validity",
        extracted_data=[SAMPLE_VALID_POLICY, SAMPLE_VALID_BILL],
        validation_result={"valid": True, "reasons": []},
        validity_result=None,  # Validity not run!
        missing_documents={"missing_documents": [], "missing_count": 0}
    )
    res = adapter.run(state)
    assert res.status == "success"
    assert state.final_status == ClaimStatus.INSUFFICIENT_INFORMATION.value
    assert state.final_report["is_ready"] is False


def test_readiness_agent_premature_complete_without_checks():
    """
    If the agent prematurely decides to 'complete' without executing validation/validity checks,
    it must NOT mark the claim as ready; it must resolve to INSUFFICIENT_INFORMATION.
    """
    mock_responses = [
        {
            "thought": "Deciding to finish immediately without checking.",
            "action": "complete",
            "reason": "Done.",
            "decision_type": "TERMINATE"
        }
    ]
    mock_llm = MockLLMClient(responses=mock_responses, planner_response={"goal": "Assess claim readiness", "steps": []})
    agent = InsureMateAgent(llm_client=mock_llm, tool_registry=InsureMateToolRegistry(offline_mode=True))
    state = ClaimState(
        claim_id="test-premature-complete",
        goal="Assess claim readiness",
        extracted_data=[SAMPLE_VALID_POLICY, SAMPLE_VALID_BILL]
    )
    final_state = agent.run(state=state)
    assert final_state.final_status == ClaimStatus.INSUFFICIENT_INFORMATION.value
    assert final_state.final_report["is_ready"] is False


def test_readiness_agent_max_iterations_limit():
    """
    If the agent loops or reaches max iterations, it must fail safely with FAILED status,
    NOT marked as complete or ready.
    """
    mock_responses = [
        {
            "thought": "Searching policy clauses.",
            "action": "policy_clause_search",
            "action_input": {"query": "coverage"},
            "reason": "Search 1",
            "decision_type": "TOOL_CALL"
        },
        {
            "thought": "Searching policy clauses.",
            "action": "policy_clause_search",
            "action_input": {"query": "coverage"},
            "reason": "Search 2",
            "decision_type": "TOOL_CALL"
        },
        {
            "thought": "Searching policy clauses.",
            "action": "policy_clause_search",
            "action_input": {"query": "coverage"},
            "reason": "Search 3",
            "decision_type": "TOOL_CALL"
        }
    ]
    mock_llm = MockLLMClient(responses=mock_responses, planner_response={"goal": "Assess claim", "steps": []})
    agent = InsureMateAgent(llm_client=mock_llm, tool_registry=InsureMateToolRegistry(offline_mode=True))
    state = ClaimState(
        claim_id="test-iteration-limit",
        goal="Assess claim",
        extracted_data=[SAMPLE_VALID_POLICY, SAMPLE_VALID_BILL],
        max_iterations=3
    )
    final_state = agent.run(state=state)
    assert final_state.iteration_count >= 3
    assert final_state.final_status == ClaimStatus.FAILED.value
    assert final_state.final_report["is_ready"] is False


def test_readiness_unreadable_file_abort():
    """Unreadable or empty files abort cleanly with INSUFFICIENT_INFORMATION."""
    mock_responses = [
        {
            "thought": "File is completely unreadable.",
            "action": "abort",
            "reason": "Unreadable file format.",
            "decision_type": "HALT"
        }
    ]
    mock_llm = MockLLMClient(responses=mock_responses, planner_response={"goal": "Process corrupted claim", "steps": []})
    agent = InsureMateAgent(llm_client=mock_llm, tool_registry=InsureMateToolRegistry(offline_mode=True))
    state = ClaimState(
        claim_id="test-unreadable-file",
        goal="Process corrupted claim"
    )
    final_state = agent.run(state=state)
    assert final_state.final_status == ClaimStatus.INSUFFICIENT_INFORMATION.value
    assert final_state.final_report["is_ready"] is False
