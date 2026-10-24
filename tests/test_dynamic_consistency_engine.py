"""tests/test_dynamic_consistency_engine.py
Automated Test Suite for Dynamic Multi-Entity Cross-Document Consistency & Claim Integrity Engine.

Verifies:
1. Conflicting Insurer Test (e.g. ABC Health Insurance vs XYZ General Insurance)
2. Insurer Normalization & TPA Test (e.g. Sunrise Shield Co. Ltd. vs Sunrise Shield Health Insurance / MediAssist TPA)
3. Mismatched Policy Number Test (e.g. POL-999 vs ISB1-TEST-2025-001)
4. All Consistent Test (Clean coherent multi-page package -> CLAIM_READY_FOR_SUBMISSION)
5. End-to-end Autonomous Agent execution with consistency enforcement
"""

import pytest
from tools.cross_document_consistency_tool import CrossDocumentConsistencyTool
from agent.tools import ClaimPreparationAdapter, InsureMateToolRegistry
from agent.state import ClaimState, ClaimStatus
from agent.insuremate_agent import InsureMateAgent


# =============================================================================
# TEST 1: CONFLICTING INSURER TEST
# =============================================================================

def test_conflicting_insurer_detected():
    """
    Upload a bundle where policy is 'ABC Health Insurance' and a hospital
    admission bill reports 'XYZ General Insurance'.
    Verify the pipeline flags ACTION_REQUIRED_INVALID_DOCUMENTS with an explicit
    insurer discrepancy action item.
    """
    extracted_data = [
        {
            "page_number": 1,
            "document_type": "insurance_policy",
            "document_title": "Health Insurance Policy Schedule",
            "insurer_name": "ABC Health Insurance",
            "policy_number": "ISB1-TEST-2025-001",
            "policy_holder_name": "Aarav Mehta",
            "policy_start_date": "2024-01-01",
            "policy_end_date": "2025-12-31",
        },
        {
            "page_number": 2,
            "document_type": "hospital_document",
            "document_title": "Hospital Admission Record",
            "insurer_name": "XYZ General Insurance",
            "policy_number": "ISB1-TEST-2025-001",
            "patient_name": "Aarav Mehta",
            "hospital_name": "Metro Health Hospital",
            "document_date": "2024-05-10",
        },
        {
            "page_number": 3,
            "document_type": "medical_bill",
            "document_title": "Inpatient Final Bill",
            "insurer_name": "XYZ General Insurance",
            "policy_number": "ISB1-TEST-2025-001",
            "patient_name": "Aarav Mehta",
            "hospital_name": "Metro Health Hospital",
            "document_date": "2024-05-12",
            "bill_number": "BILL-9011",
            "bill_amount": 35000.0,
        },
    ]

    # 1. Run consistency tool
    tool = CrossDocumentConsistencyTool()
    result = tool.run(extracted_data)

    assert result["status"] == "success"
    assert result["consistent"] is False
    assert result["severity"] == "CRITICAL"
    assert len(result["discrepancies"]) >= 1

    discrepancy_text = " ".join(result["discrepancies"])
    assert "Conflicting insurance companies reported across documents" in discrepancy_text
    assert "ABC Health Insurance" in discrepancy_text
    assert "XYZ General Insurance" in discrepancy_text

    # 2. Run ClaimPreparationAdapter to verify readiness synthesis is blocked
    adapter = ClaimPreparationAdapter()
    state = ClaimState(
        claim_id="claim-conflicting-insurer",
        extracted_data=extracted_data,
        validation_result={"valid": True, "valid_documents": 3, "total_documents": 3},
        validity_result={"valid": True, "reasons": ["Incident date within policy coverage period."]},
        missing_documents={"missing_documents": [], "missing_count": 0},
        consistency_results=result,
    )

    exec_res = adapter.run(state)
    assert exec_res.status == "success"
    assert state.final_status == ClaimStatus.ACTION_REQUIRED_INVALID_DOCUMENTS.value
    assert state.final_report["is_ready"] is False
    assert state.final_report["consistency_status"] == "FAIL"
    assert state.final_report["consistency_severity"] == "CRITICAL"

    # Verify action items contain explicit insurer discrepancy instruction
    action_items_str = " ".join(state.final_report["action_items"])
    assert "Conflicting insurance companies" in action_items_str or "ABC Health Insurance" in action_items_str


# =============================================================================
# TEST 2: INSURER NORMALIZATION & TPA TEST
# =============================================================================

def test_insurer_normalization_and_tpa_pass():
    """
    Policy is 'Sunrise Shield Health Insurance Co. Ltd.' and bill is
    'Sunrise Shield Health Insurance' (or mentions TPA relationship).
    Verify this passes dynamically as consistent without false positives.
    """
    tool = CrossDocumentConsistencyTool()

    # Case A: Minor legal suffixes (Co. Ltd., Limited, etc.)
    docs_minor_variants = [
        {
            "page_number": 1,
            "document_type": "insurance_policy",
            "insurer_name": "Sunrise Shield Health Insurance Co. Ltd.",
            "policy_number": "POL-2025-001",
            "policy_holder_name": "Aarav Mehta",
        },
        {
            "page_number": 2,
            "document_type": "hospital_document",
            "insurer_name": "Sunrise Shield Health Insurance",
            "policy_number": "POL-2025-001",
            "patient_name": "Aarav Mehta",
            "hospital_name": "City Care Hospital",
        },
    ]

    res_a = tool.run(docs_minor_variants)
    assert res_a["consistent"] is True
    assert res_a["severity"] == "NONE"
    assert len(res_a["discrepancies"]) == 0

    # Case B: TPA relationship ("MediAssist TPA for Sunrise Shield")
    docs_tpa = [
        {
            "page_number": 1,
            "document_type": "insurance_policy",
            "insurer_name": "Sunrise Shield",
            "policy_number": "POL-2025-001",
            "policy_holder_name": "Aarav Mehta",
        },
        {
            "page_number": 2,
            "document_type": "hospital_document",
            "insurer_name": "MediAssist TPA for Sunrise Shield",
            "policy_number": "POL-2025-001",
            "patient_name": "Aarav Mehta",
            "hospital_name": "City Care Hospital",
        },
    ]

    res_b = tool.run(docs_tpa)
    assert res_b["consistent"] is True
    assert res_b["severity"] == "NONE"
    assert len(res_b["discrepancies"]) == 0


# =============================================================================
# TEST 3: MISMATCHED POLICY NUMBER TEST
# =============================================================================

def test_mismatched_policy_number_flagged():
    """
    Hospital document references 'POL-999' while policy schedule is 'ISB1-TEST-2025-001'.
    Verify it is flagged with POLICY_NUMBER_MISMATCH and CRITICAL severity.
    """
    extracted_data = [
        {
            "page_number": 1,
            "document_type": "insurance_policy",
            "insurer_name": "Sunrise Shield Health Insurance",
            "policy_number": "ISB1-TEST-2025-001",
            "policy_holder_name": "Priya Sharma",
        },
        {
            "page_number": 2,
            "document_type": "hospital_document",
            "insurer_name": "Sunrise Shield Health Insurance",
            "policy_number": "POL-999",
            "patient_name": "Priya Sharma",
            "hospital_name": "Apollo Clinic",
        },
    ]

    tool = CrossDocumentConsistencyTool()
    res = tool.run(extracted_data)

    assert res["consistent"] is False
    assert res["severity"] == "CRITICAL"
    assert any("Policy number mismatch" in d for d in res["discrepancies"])
    assert any("POL-999" in d for d in res["discrepancies"])

    # Synthesis should flag ACTION_REQUIRED_INVALID_DOCUMENTS
    adapter = ClaimPreparationAdapter()
    state = ClaimState(
        claim_id="claim-policy-mismatch",
        extracted_data=extracted_data,
        validation_result={"valid": True, "valid_documents": 2, "total_documents": 2},
        validity_result={"valid": True, "reasons": ["Valid dates"]},
        missing_documents={"missing_documents": [], "missing_count": 0},
        consistency_results=res,
    )
    adapter.run(state)
    assert state.final_status == ClaimStatus.ACTION_REQUIRED_INVALID_DOCUMENTS.value
    assert state.final_report["is_ready"] is False
    assert any("POL-999" in item for item in state.final_report["action_items"])


# =============================================================================
# TEST 4: ALL CONSISTENT TEST
# =============================================================================

def test_all_consistent_claim_ready_for_submission():
    """
    Fully coherent multi-page claim (insurer, policy number, patient name,
    hospital, dates, and amounts) passes cleanly to CLAIM_READY_FOR_SUBMISSION.
    """
    extracted_data = [
        {
            "page_number": 1,
            "document_type": "insurance_policy",
            "insurer_name": "Sunrise Shield Health Insurance Co. Ltd.",
            "policy_number": "ISB1-TEST-2025-001",
            "policy_holder_name": "Aarav Mehta",
            "policy_start_date": "2024-01-01",
            "policy_end_date": "2025-12-31",
        },
        {
            "page_number": 2,
            "document_type": "hospital_document",
            "insurer_name": "Sunrise Shield Health Insurance",
            "policy_number": "ISB1-TEST-2025-001",
            "patient_name": "Mehta, Aarav",  # Name permutation test
            "hospital_name": "City Care Hospital",
            "document_date": "2024-05-10",
        },
        {
            "page_number": 3,
            "document_type": "medical_bill",
            "insurer_name": "Sunrise Shield",
            "policy_number": "ISB1-TEST-2025-001",
            "patient_name": "Mr. Aarav Mehta",  # Title prefix test
            "hospital_name": "City Care Hospital",
            "document_date": "2024-05-12",
            "bill_number": "BILL-1004",
            "bill_amount": 25000.0,
        },
    ]

    tool = CrossDocumentConsistencyTool()
    consistency_res = tool.run(extracted_data)

    assert consistency_res["consistent"] is True
    assert consistency_res["severity"] == "NONE"
    assert len(consistency_res["discrepancies"]) == 0

    adapter = ClaimPreparationAdapter()
    state = ClaimState(
        claim_id="claim-coherent",
        extracted_data=extracted_data,
        validation_result={"valid": True, "valid_documents": 3, "total_documents": 3},
        validity_result={"valid": True, "reasons": ["Incident date 2024-05-10 within policy duration 2024-01-01 to 2025-12-31."]},
        missing_documents={"missing_documents": [], "missing_count": 0},
        consistency_results=consistency_res,
    )

    adapter.run(state)
    assert state.final_status == ClaimStatus.CLAIM_READY_FOR_SUBMISSION.value
    assert state.final_report["is_ready"] is True
    assert state.final_report["consistency_status"] == "PASS"


# =============================================================================
# TEST 5: AUTONOMOUS AGENT ORCHESTRATION WITH CONSISTENCY CHECK
# =============================================================================

def test_autonomous_agent_detects_contradictory_insurer():
    """
    InsureMateAgent running in grounded offline mode with extracted documents
    containing conflicting insurer entities must invoke cross_document_consistency_check,
    halt submission readiness, and transition claim to ACTION_REQUIRED_INVALID_DOCUMENTS.
    """
    extracted_data = [
        {
            "page_number": 1,
            "document_type": "insurance_policy",
            "insurer_name": "Sunrise Shield Health Insurance",
            "policy_number": "ISB1-TEST-2025-001",
            "policy_holder_name": "Rohit Verma",
            "policy_start_date": "2024-01-01",
            "policy_end_date": "2025-12-31",
        },
        {
            "page_number": 2,
            "document_type": "hospital_document",
            "insurer_name": "Star Global Health Insurance",
            "policy_number": "ISB1-TEST-2025-001",
            "patient_name": "Rohit Verma",
            "hospital_name": "Fortis Hospital",
            "document_date": "2024-06-15",
        },
        {
            "page_number": 3,
            "document_type": "medical_bill",
            "insurer_name": "Star Global Health Insurance",
            "policy_number": "ISB1-TEST-2025-001",
            "patient_name": "Rohit Verma",
            "hospital_name": "Fortis Hospital",
            "document_date": "2024-06-18",
            "bill_number": "INV-4411",
            "bill_amount": 42000.0,
        },
    ]

    agent = InsureMateAgent(offline_mode=True)
    state = ClaimState(
        claim_id="test-agent-conflicting-insurer",
        extracted_data=extracted_data,
        goal="Determine claim readiness and validate submitted documents.",
    )

    final_state = agent.run(state=state)

    # Verify agent invoked cross_document_consistency_check
    completed = final_state.completed_steps
    assert "cross_document_consistency_check" in completed or any(
        h.get("tool_name") == "cross_document_consistency_check" for h in final_state.tool_history
    )

    # Verify claim readiness was blocked
    assert final_state.final_status == ClaimStatus.ACTION_REQUIRED_INVALID_DOCUMENTS.value
    assert final_state.final_report["is_ready"] is False
    assert final_state.final_report["consistency_status"] == "FAIL"
    assert any("Conflicting insurance companies" in item for item in final_state.final_report["action_items"])
