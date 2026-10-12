"""tests/test_dynamic_agent.py
Verification suite for Genuine Dynamic Agentic AI in InsureMate.
Demonstrates that the agent does NOT follow a static, hardcoded sequence,
and that tool invocation, ordering, adaptation, and termination emerge dynamically at runtime.

Tests:
1. test_scenario_1_single_tool_clause_query: Request requiring only one tool (clause search), avoiding unnecessary tools.
2. test_scenario_2_different_requests_different_tool_orders: Two similar requests requiring legitimately different tool orders.
3. test_scenario_3_result_changes_agent_plan: Tool result (validation failure) causes agent to dynamically change direction.
4. test_scenario_4_missing_info_triggers_additional_tool: Missing policy triggers missing evidence detection instead of date check.
5. test_scenario_5_contradictory_evidence_triggers_investigation: Contradictory hospital/patient data triggers consistency check.
6. test_scenario_6_failed_tool_recovery_attempt: Failed tool call leads to controlled recovery/retry.
7. test_scenario_7_task_terminates_without_unnecessary_tools: Date check goal terminates without validation or checklist tools.
8. test_scenario_8_execution_limit_stops_safely: Bounded execution stops agent safely when max iterations reached.
9. test_scenario_9_llm_driven_dynamic_tool_selection: Verifies LLM-controlled tool choice and argument passing.
"""

import json
from pathlib import Path
import sys
from typing import Any, Dict, List
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agent.insuremate_agent import InsureMateAgent
from agent.state import ClaimState, ClaimStatus
from agent.tools import InsureMateToolRegistry, ToolExecutionResult
from agent.decision import AgentDecision, InsureMateDecisionEngine
from tests.conftest import MockLLMClient
from services.missing_document.llm_gateway import LLMGateway
from tools.missing_document_tool import MissingDocumentTool


# Sample Data Fixtures
SAMPLE_POLICY_DATA = [
    {
        "page_number": 1,
        "document_type": "insurance_policy",
        "document_title": "Gold Health Floater Policy",
        "policy_number": "POL-2026-999",
        "policy_holder_name": "Arjun Sharma",
        "insured_names": ["Arjun Sharma", "Priya Sharma"],
        "policy_start_date": "01/01/2026",
        "policy_end_date": "31/12/2026",
        "policy_clauses": [
            "Cataract surgery coverage is capped at Rs. 40,000 per eye.",
            "Pre-existing diseases have a 24-month waiting period.",
            "Room rent limit is 1% of sum insured per day.",
            "Original discharge summary and itemized hospital bills are mandatory for claim submission."
        ],
        "relevant_conditions": [
            "24 months waiting period for specific ailments",
            "Maternity expenses covered after 36 months"
        ],
        "policy_relevant_text": "Cataract treatment limit: Rs. 40,000 per eye. Pre-existing conditions waiting period: 24 months."
    }
]

SAMPLE_BILL_DATA = [
    {
        "page_number": 2,
        "document_type": "medical_bill",
        "document_title": "Inpatient Hospital Bill",
        "bill_number": "INV-789",
        "patient_name": "Priya Sharma",
        "hospital_name": "Apollo City Hospital",
        "document_date": "15/06/2026",
        "bill_amount": "35000.00"
    }
]

SAMPLE_DISCHARGE_SUMMARY = [
    {
        "page_number": 3,
        "document_type": "hospital_document",
        "document_title": "Hospital Discharge Summary",
        "patient_name": "Priya Sharma",
        "hospital_name": "Apollo City Hospital",
        "document_date": "15/06/2026"
    }
]


# ==============================================================================
# 1. SCENARIO 1: Request requiring only one tool, avoiding unnecessary tools
# ==============================================================================
def test_scenario_1_single_tool_clause_query():
    """
    User Goal: 'What is the policy exclusion and limit for cataract surgery?'
    The agent must invoke policy_clause_search directly and conclude without
    running unnecessary hospital bill validation, date checks, or missing document tools.
    """
    registry = InsureMateToolRegistry(offline_mode=True)
    agent = InsureMateAgent(tool_registry=registry, offline_mode=True)

    state = ClaimState(
        goal="What is the policy exclusion and limit for cataract surgery?",
        extracted_data=SAMPLE_POLICY_DATA
    )

    final_state = agent.run(state=state)

    executed_tools = [h["tool_name"] for h in final_state.tool_history]

    # Must invoke policy_clause_search
    assert "policy_clause_search" in executed_tools, "Agent must select policy_clause_search"

    # Must NOT run unnecessary tools
    assert "document_validation" not in executed_tools, "Validation must NOT be called for clause query"
    assert "validity_checker" not in executed_tools, "Validity checker must NOT be called for clause query"
    assert "missing_document_detector" not in executed_tools, "Missing doc detector must NOT be called for clause query"

    # Exactly 1 tool executed because pre-extracted data was available
    assert len(executed_tools) == 1, f"Expected exactly 1 tool call, got {executed_tools}"
    assert final_state.final_status is not None


# ==============================================================================
# 2. SCENARIO 2: Two requests that legitimately require different tool orders
# ==============================================================================
def test_scenario_2_different_requests_different_tool_orders():
    """
    Verifies that tool invocation order is NOT fixed, but emerges from distinct goals:
    Request A (Date validity check): Calls validity_checker without running validation.
    Request B (Checklist audit): Calls missing_document_detector without running date checker.
    """
    registry = InsureMateToolRegistry(offline_mode=True)

    # Request A: Focuses strictly on date validity
    agent_a = InsureMateAgent(tool_registry=registry, offline_mode=True)
    state_a = ClaimState(
        goal="Verify if the invoice dates fall strictly within the active policy coverage window.",
        extracted_data=SAMPLE_POLICY_DATA + SAMPLE_BILL_DATA
    )
    res_a = agent_a.run(state=state_a)
    tools_a = [h["tool_name"] for h in res_a.tool_history]

    # Request B: Focuses strictly on missing checklist documents
    agent_b = InsureMateAgent(tool_registry=registry, offline_mode=True)
    state_b = ClaimState(
        goal="Audit what required claim documents or checklist evidence are missing.",
        extracted_data=SAMPLE_POLICY_DATA + SAMPLE_BILL_DATA
    )
    res_b = agent_b.run(state=state_b)
    tools_b = [h["tool_name"] for h in res_b.tool_history]

    # Verify completely different tool orders and sets
    assert "validity_checker" in tools_a
    assert "document_validation" not in tools_a, "Request A must not run validation"

    assert "missing_document_detector" in tools_b
    assert "validity_checker" not in tools_b, "Request B must not run date checks"

    assert tools_a != tools_b, "Tool invocation sequences must differ based on goal"


# ==============================================================================
# 3. SCENARIO 3: Tool result causes the agent to dynamically change its plan
# ==============================================================================
def test_scenario_3_result_changes_agent_plan():
    """
    When document validation reveals that ALL documents are invalid/corrupted,
    the agent must adapt its plan, skip downstream validity date checking,
    and proceed directly to claim preparation to record deficiencies.
    """
    # Corrupted / invalid document data (missing mandatory patient, bill number, amounts)
    invalid_data = [
        {
            "page_number": 1,
            "document_type": "unknown",
            "document_title": "Unreadable Fax"
        },
        {
            "page_number": 2,
            "document_type": "medical_bill",
            "document_title": "Fragmented Bill"
            # Missing patient_name, hospital_name, bill_number, bill_amount, document_date
        }
    ]

    registry = InsureMateToolRegistry(offline_mode=True)
    agent = InsureMateAgent(tool_registry=registry, offline_mode=True)

    state = ClaimState(
        goal="Determine claim readiness.",
        extracted_data=invalid_data
    )

    final_state = agent.run(state=state)
    executed_tools = [h["tool_name"] for h in final_state.tool_history]

    assert "document_validation" in executed_tools
    # Because validation detected 0 valid documents, validity_checker must be skipped
    assert "validity_checker" not in executed_tools, "Downstream validity checker must be skipped when validation fails"
    assert "claim_preparation" in executed_tools

    # Trace shows decision adaptation
    assert final_state.final_status == ClaimStatus.ACTION_REQUIRED_INVALID_DOCUMENTS.value


# ==============================================================================
# 4. SCENARIO 4: Missing information triggers an additional tool call
# ==============================================================================
def test_scenario_4_missing_info_triggers_additional_tool():
    """
    When submitted claim lacks an insurance policy document, the agent recognizes
    it cannot evaluate validity dates and triggers missing_document_detector to audit
    the missing policy certificate.
    """
    # Only medical bills submitted, NO insurance policy
    bills_only_data = SAMPLE_BILL_DATA + SAMPLE_DISCHARGE_SUMMARY

    registry = InsureMateToolRegistry(offline_mode=True)
    agent = InsureMateAgent(tool_registry=registry, offline_mode=True)

    state = ClaimState(
        goal="Determine claim readiness.",
        extracted_data=bills_only_data
    )

    final_state = agent.run(state=state)
    executed_tools = [h["tool_name"] for h in final_state.tool_history]

    # Must recognize policy is missing and invoke missing_document_detector
    assert "missing_document_detector" in executed_tools


# ==============================================================================
# 5. SCENARIO 5: Contradictory evidence triggers investigation
# ==============================================================================
def test_scenario_5_contradictory_evidence_triggers_investigation():
    """
    When submitted documents contain potential contradictions (e.g. Patient on hospital bill
    does not match the policyholder/insureds), cross_document_consistency_check is invoked
    and identifies the discrepancy.
    """
    contradictory_data = [
        SAMPLE_POLICY_DATA[0],  # Insured: Arjun Sharma, Priya Sharma
        {
            "page_number": 2,
            "document_type": "medical_bill",
            "document_title": "Hospital Bill",
            "bill_number": "INV-555",
            "patient_name": "Rohan Verma",  # Contradiction: Not on policy!
            "hospital_name": "Fortis Hospital",
            "document_date": "10/05/2026",
            "bill_amount": "12000.00"
        }
    ]

    registry = InsureMateToolRegistry(offline_mode=True)
    agent = InsureMateAgent(tool_registry=registry, offline_mode=True)

    state = ClaimState(
        goal="Cross-check submitted documents for consistency and discrepancies.",
        extracted_data=contradictory_data
    )

    final_state = agent.run(state=state)
    executed_tools = [h["tool_name"] for h in final_state.tool_history]

    assert "cross_document_consistency_check" in executed_tools
    consistency_entry = [h for h in final_state.tool_history if h["tool_name"] == "cross_document_consistency_check"][0]
    assert "does not match" in consistency_entry["summary"] or "discrepancy" in consistency_entry["summary"].lower()


# ==============================================================================
# 6. SCENARIO 6: Failed tool call leads to a suitable recovery attempt
# ==============================================================================
def test_scenario_6_failed_tool_recovery_attempt():
    """
    When a tool call encounters an error (e.g., transient failure), the agent
    recovers using controlled retry policy and captures the result safely without crashing.
    """
    class FlakyTool:
        name = "flaky_tool"
        description = "A tool that fails on first call and succeeds on second call."
        attempts = 0

        def run(self, state, **kwargs):
            self.attempts += 1
            if self.attempts == 1:
                return ToolExecutionResult(
                    tool_name=self.name,
                    status="error",
                    summary="Transient network timeout",
                    data={},
                    error="Timeout connecting to external service."
                )
            return ToolExecutionResult(
                tool_name=self.name,
                status="success",
                summary="Operation succeeded on retry.",
                data={"result": "OK"}
            )

    registry = InsureMateToolRegistry(offline_mode=True)
    flaky = FlakyTool()
    registry.register(flaky)

    # Mock decision engine that calls the flaky tool
    class MockDecisionEngine:
        call_count = 0
        def decide_next_action(self, state, tool_registry=None):
            self.call_count += 1
            if self.call_count == 1:
                return AgentDecision(action="flaky_tool", reason="Execute operation.")
            return AgentDecision(action="complete", reason="Operation satisfied.")

    agent = InsureMateAgent(tool_registry=registry, offline_mode=True)
    agent.decision_engine = MockDecisionEngine()

    state = ClaimState(goal="Execute resilient workflow.")
    final_state = agent.run(state=state)

    # Tool was retried and succeeded
    assert flaky.attempts == 2
    assert final_state.retry_counts.get("flaky_tool") == 1
    assert any("Retrying flaky_tool" in t["decision"] for t in final_state.execution_trace)


# ==============================================================================
# 7. SCENARIO 7: Task terminates without invoking unnecessary tools
# ==============================================================================
def test_scenario_7_task_terminates_without_unnecessary_tools():
    """
    When the goal is strictly to evaluate whether the medical bill date is within coverage,
    the agent terminates as soon as validity_checker succeeds without calling missing_document_detector
    or full claim_preparation.
    """
    registry = InsureMateToolRegistry(offline_mode=True)
    agent = InsureMateAgent(tool_registry=registry, offline_mode=True)

    state = ClaimState(
        goal="Check date validity of the submitted medical bill against policy duration.",
        extracted_data=SAMPLE_POLICY_DATA + SAMPLE_BILL_DATA
    )

    final_state = agent.run(state=state)
    executed_tools = [h["tool_name"] for h in final_state.tool_history]

    assert executed_tools == ["validity_checker"]
    assert "missing_document_detector" not in executed_tools
    assert "document_validation" not in executed_tools
    assert "claim_preparation" not in executed_tools


# ==============================================================================
# 8. SCENARIO 8: Execution limit stops the agent safely
# ==============================================================================
def test_scenario_8_execution_limit_stops_safely():
    """
    Verifies bounded execution: If an execution limit (max_iterations) is reached,
    the agent stops safely without infinite looping, records the iteration bound in errors and trace,
    and returns a controlled final state.
    """
    registry = InsureMateToolRegistry(offline_mode=True)
    agent = InsureMateAgent(tool_registry=registry, max_iterations=2, offline_mode=True)

    # Agent given multi-step claim readiness goal with max_iterations=2
    state = ClaimState(
        goal="Determine claim readiness.",
        extracted_data=SAMPLE_POLICY_DATA + SAMPLE_BILL_DATA,
        max_iterations=2
    )

    final_state = agent.run(state=state)

    # Must stop at exactly 2 iterations
    assert final_state.iteration_count == 2
    assert final_state.final_status == ClaimStatus.FAILED.value
    assert any("maximum limit of 2 iterations" in err for err in final_state.errors)
    assert final_state.final_report["is_ready"] is False


# ==============================================================================
# 9. SCENARIO 9: LLM-Driven Dynamic Decision & Argument Selection
# ==============================================================================
def test_scenario_9_llm_driven_dynamic_tool_selection():
    """
    Tests that an active LLM dynamically chooses tools and parameters at runtime,
    and the InsureMateAgent executes the LLM's selected tool with its exact parameters.
    """
    # Scripted LLM responses simulating autonomous reasoning
    mock_responses = [
        # LLM Plan Generation: Dynamically outlines required steps
        json.dumps({
            "goal": "Find cataract surgery limits.",
            "steps": [
                {"step": 1, "action": "policy_clause_search", "reason": "Query policy clauses for cataract limits.", "status": "pending"}
            ]
        }),
        # LLM Turn 1: Chooses policy_clause_search with custom query
        '{"thought": "User wants to check cataract surgery limits.", "action": "policy_clause_search", "action_input": {"query": "cataract surgery limit"}, "reason": "Query policy clauses for cataract limits.", "decision_type": "TOOL_CALL"}',
        # LLM Turn 2: Examines result and decides to complete
        '{"thought": "Clause was found on page 1 capped at Rs 40,000. Goal achieved.", "action": "complete", "reason": "Cataract limit clause located and answered.", "decision_type": "TERMINATE"}'
    ]
    mock_llm = MockLLMClient(responses=mock_responses)

    registry = InsureMateToolRegistry(offline_mode=True)
    agent = InsureMateAgent(llm_client=mock_llm, tool_registry=registry)

    state = ClaimState(
        goal="Find cataract surgery limits.",
        extracted_data=SAMPLE_POLICY_DATA
    )

    final_state = agent.run(state=state)
    executed_tools = [h["tool_name"] for h in final_state.tool_history]

    assert executed_tools == ["policy_clause_search"]
    search_entry = final_state.tool_history[0]
    assert "cataract surgery limit" in search_entry["inputs_summary"]
    assert "40,000" in search_entry["summary"] or "Cataract" in search_entry["summary"]
    assert final_state.final_status is not None
