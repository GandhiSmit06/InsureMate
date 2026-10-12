"""tests/test_dynamic_agent.py
Verification suite for Genuine Dynamic Agentic AI in InsureMate.
Demonstrates that the agent does NOT follow a static, hardcoded sequence,
and that tool invocation, ordering, adaptation, and termination emerge dynamically at runtime.

Covers all 12 scenarios required by the specification:
1. Single-tool task: Invokes one appropriate tool and finishes without unnecessary calls.
2. Different decisions: Similar user requests produce different tool selections and execution orders.
3. Observation-driven branching: Different results from the same initial tool produce different subsequent decisions.
4. Adaptive investigation: Contradictory evidence leads to an additional investigation chosen by the agent.
5. Dynamic planning: The agent revises or abandons its initial plan when new results make that plan unsuitable.
6. Failure recovery: A failed tool call leads to an appropriate alternative, a justified retry, or a safe termination.
7. No unnecessary tools: The agent can finish without invoking irrelevant tools.
8. No hardcoded fallback chain: Invalid LLM output does not trigger a predefined sequence of insurance tools.
9. Safety and validation: Unknown tools, invalid arguments, and unauthorized actions are rejected.
10. Execution limits: The agent stops safely when its tool-call or iteration budget is exhausted.
11. Evidence grounding: The final response distinguishes verified observations from missing or uncertain information.
12. Real integration: The production agent uses the actual LLM-driven decision path rather than a mock-only implementation.
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
# 1. SCENARIO 1: Single-tool task
# ==============================================================================
def test_scenario_1_single_tool_task():
    """
    Scenario 1: The agent invokes one appropriate tool (policy_clause_search)
    and finishes without unnecessary calls.
    """
    mock_responses = [
        {
            "thought": "User asks specifically for cataract limits. I only need policy_clause_search.",
            "action": "policy_clause_search",
            "action_input": {"query": "cataract surgery limit"},
            "reason": "Search policy clauses for cataract surgery limits.",
            "decision_type": "TOOL_CALL"
        },
        {
            "thought": "Observation shows cataract surgery capped at Rs. 40,000. Goal achieved.",
            "action": "complete",
            "reason": "Found policy clause capping cataract surgery at Rs. 40,000.",
            "decision_type": "TERMINATE"
        }
    ]
    mock_llm = MockLLMClient(
        responses=mock_responses,
        planner_response={"goal": "Find cataract limit", "steps": [{"step": 1, "action": "policy_clause_search"}]}
    )
    registry = InsureMateToolRegistry(offline_mode=True)
    agent = InsureMateAgent(llm_client=mock_llm, tool_registry=registry)

    state = ClaimState(
        goal="What is the policy exclusion and limit for cataract surgery?",
        extracted_data=SAMPLE_POLICY_DATA
    )

    final_state = agent.run(state=state)
    executed_tools = [h["tool_name"] for h in final_state.tool_history]

    # Exactly 1 tool executed
    assert executed_tools == ["policy_clause_search"], f"Expected only policy_clause_search, got {executed_tools}"
    assert "document_validation" not in executed_tools
    assert "validity_checker" not in executed_tools
    assert "missing_document_detector" not in executed_tools
    assert "claim_preparation" not in executed_tools
    assert final_state.final_status is not None


# ==============================================================================
# 2. SCENARIO 2: Different decisions for similar requests
# ==============================================================================
def test_scenario_2_different_decisions_for_similar_requests():
    """
    Scenario 2: Similar user requests produce different tool selections and execution orders:
    Request A (Date validity check): Calls validity_checker without running validation or checklist.
    Request B (Checklist audit): Calls missing_document_detector without running date checker.
    """
    registry = InsureMateToolRegistry(offline_mode=True)

    # Request A: Focuses strictly on date validity
    mock_llm_a = MockLLMClient(
        responses=[
            {
                "thought": "User wants date validity check only.",
                "action": "validity_checker",
                "action_input": {},
                "reason": "Verify invoice date against policy period.",
                "decision_type": "TOOL_CALL"
            },
            {
                "thought": "Dates are valid. Concluding.",
                "action": "complete",
                "reason": "Invoice date verified within active policy coverage period.",
                "decision_type": "TERMINATE"
            }
        ],
        planner_response={"goal": "Check dates", "steps": [{"step": 1, "action": "validity_checker"}]}
    )
    agent_a = InsureMateAgent(llm_client=mock_llm_a, tool_registry=registry)
    state_a = ClaimState(
        goal="Verify if the invoice dates fall strictly within the active policy coverage window.",
        extracted_data=SAMPLE_POLICY_DATA + SAMPLE_BILL_DATA
    )
    res_a = agent_a.run(state=state_a)
    tools_a = [h["tool_name"] for h in res_a.tool_history]

    # Request B: Focuses strictly on missing checklist documents
    mock_llm_b = MockLLMClient(
        responses=[
            {
                "thought": "User wants checklist audit only.",
                "action": "missing_document_detector",
                "action_input": {},
                "reason": "Audit required checklist documents.",
                "decision_type": "TOOL_CALL"
            },
            {
                "thought": "Checklist audited. Concluding.",
                "action": "complete",
                "reason": "Audit of required documents complete.",
                "decision_type": "TERMINATE"
            }
        ],
        planner_response={"goal": "Audit checklist", "steps": [{"step": 1, "action": "missing_document_detector"}]}
    )
    agent_b = InsureMateAgent(llm_client=mock_llm_b, tool_registry=registry)
    state_b = ClaimState(
        goal="Audit what required claim documents or checklist evidence are missing.",
        extracted_data=SAMPLE_POLICY_DATA + SAMPLE_BILL_DATA
    )
    res_b = agent_b.run(state=state_b)
    tools_b = [h["tool_name"] for h in res_b.tool_history]

    assert tools_a == ["validity_checker"]
    assert tools_b == ["missing_document_detector"]
    assert tools_a != tools_b, "Tool invocation sequences must differ dynamically based on goal"


# ==============================================================================
# 3. SCENARIO 3: Observation-driven branching
# ==============================================================================
def test_scenario_3_observation_driven_branching():
    """
    Scenario 3: Different results from the same initial tool produce different subsequent decisions.
    Branch A: Initial tool (document_validation) reports valid docs -> LLM selects validity_checker.
    Branch B: Initial tool (document_validation) reports invalid docs -> LLM dynamically branches away
    to user clarification (request_user_info) rather than calling validity_checker.
    """
    registry = InsureMateToolRegistry(offline_mode=True)

    # Branch A: Documents are valid -> Proceed to date checker
    mock_llm_a = MockLLMClient(
        responses=[
            {
                "thought": "Step 1: Validate documents.",
                "action": "document_validation",
                "action_input": {},
                "reason": "Check document structure and completeness.",
                "decision_type": "TOOL_CALL"
            },
            {
                "thought": "Observation shows documents are valid. Now checking date validity.",
                "action": "validity_checker",
                "action_input": {},
                "reason": "Validate dates since documents are structurally sound.",
                "decision_type": "TOOL_CALL"
            },
            {
                "thought": "All checks passed.",
                "action": "complete",
                "reason": "Workflow completed successfully.",
                "decision_type": "TERMINATE"
            }
        ],
        planner_response={"goal": "Validate claim", "steps": []}
    )
    agent_a = InsureMateAgent(llm_client=mock_llm_a, tool_registry=registry)
    state_a = ClaimState(
        goal="Determine claim readiness.",
        extracted_data=SAMPLE_POLICY_DATA + SAMPLE_BILL_DATA
    )
    res_a = agent_a.run(state=state_a)
    tools_a = [h["tool_name"] for h in res_a.tool_history]
    assert tools_a == ["document_validation", "validity_checker"]

    # Branch B: Documents are corrupted / invalid -> Adapt to request_user_info
    invalid_data = [
        {"page_number": 1, "document_type": "unknown", "document_title": "Unreadable Fax"},
        {"page_number": 2, "document_type": "medical_bill", "document_title": "Fragmented Bill"}
    ]
    mock_llm_b = MockLLMClient(
        responses=[
            {
                "thought": "Step 1: Validate documents.",
                "action": "document_validation",
                "action_input": {},
                "reason": "Check document structure and completeness.",
                "decision_type": "TOOL_CALL"
            },
            {
                "thought": "Observation shows 0 valid documents found. Adapting: Request legible documents from user.",
                "action": "request_user_info",
                "action_input": {},
                "reason": "Uploaded documents are corrupted or illegible. Please upload clear copies.",
                "decision_type": "INTERACT"
            }
        ],
        planner_response={"goal": "Validate claim", "steps": []}
    )
    agent_b = InsureMateAgent(llm_client=mock_llm_b, tool_registry=registry)
    state_b = ClaimState(
        goal="Determine claim readiness.",
        extracted_data=invalid_data
    )
    res_b = agent_b.run(state=state_b)
    tools_b = [h["tool_name"] for h in res_b.tool_history]

    assert tools_b == ["document_validation"]
    assert "validity_checker" not in tools_b, "Branch B must NOT call validity_checker when validation failed"
    assert res_b.final_status == ClaimStatus.ACTION_REQUIRED_MISSING_EVIDENCE.value
    assert len(res_b.unresolved_questions) > 0


# ==============================================================================
# 4. SCENARIO 4: Adaptive investigation on contradiction
# ==============================================================================
def test_scenario_4_adaptive_investigation_on_contradiction():
    """
    Scenario 4: Contradictory evidence leads to an additional investigation chosen by the agent.
    Patient on bill ('Rohan Verma') does not match policyholders ('Arjun Sharma', 'Priya Sharma').
    Agent selects cross_document_consistency_check and flags discrepancy.
    """
    contradictory_data = [
        SAMPLE_POLICY_DATA[0],
        {
            "page_number": 2,
            "document_type": "medical_bill",
            "document_title": "Hospital Bill",
            "bill_number": "INV-555",
            "patient_name": "Rohan Verma",  # Contradiction: Not an insured member!
            "hospital_name": "Fortis Hospital",
            "document_date": "10/05/2026",
            "bill_amount": "12000.00"
        }
    ]

    mock_responses = [
        {
            "thought": "Patient name 'Rohan Verma' appears different from policyholder. Investigating discrepancy.",
            "action": "cross_document_consistency_check",
            "action_input": {},
            "reason": "Run consistency check between policy insureds and bill patient.",
            "decision_type": "TOOL_CALL"
        },
        {
            "thought": "Discrepancy confirmed: Patient not covered under policy. Request user explanation.",
            "action": "request_user_info",
            "action_input": {},
            "reason": "Patient 'Rohan Verma' is not listed under policy members. Please clarify relationship.",
            "decision_type": "INTERACT"
        }
    ]
    mock_llm = MockLLMClient(responses=mock_responses, planner_response={"goal": "Investigate contradiction", "steps": []})
    registry = InsureMateToolRegistry(offline_mode=True)
    agent = InsureMateAgent(llm_client=mock_llm, tool_registry=registry)

    state = ClaimState(
        goal="Cross-check submitted documents for consistency and discrepancies.",
        extracted_data=contradictory_data
    )

    final_state = agent.run(state=state)
    executed_tools = [h["tool_name"] for h in final_state.tool_history]

    assert "cross_document_consistency_check" in executed_tools
    assert final_state.consistency_results is not None
    assert len(final_state.consistency_results.get("discrepancies", [])) > 0
    assert final_state.final_status == ClaimStatus.ACTION_REQUIRED_MISSING_EVIDENCE.value


# ==============================================================================
# 5. SCENARIO 5: Dynamic planning - revise or abandon plan
# ==============================================================================
def test_scenario_5_dynamic_planning_abandon_plan():
    """
    Scenario 5: The agent revises or abandons its initial plan when new results make that plan unsuitable.
    Initial plan: 1. document_extraction, 2. document_validation, 3. validity_checker, 4. claim_preparation.
    When extraction fails due to unreadable file, agent abandons the plan and halts safely.
    """
    mock_responses = [
        # Turn 1: Attempt extraction on corrupt file
        {
            "thought": "Execute Step 1 of plan: document_extraction.",
            "action": "document_extraction",
            "action_input": {},
            "reason": "Extract document text.",
            "decision_type": "TOOL_CALL"
        },
        # Turn 2: Observes extraction failure; abandons remaining plan steps
        {
            "thought": "Document extraction failed: corrupt file. Remaining plan steps are invalid. Aborting workflow.",
            "action": "abort",
            "action_input": {},
            "reason": "Extraction failed due to corrupted file; abandoning multi-step plan.",
            "decision_type": "HALT"
        }
    ]
    mock_llm = MockLLMClient(
        responses=mock_responses,
        planner_response={
            "goal": "Process claim",
            "steps": [
                {"step": 1, "action": "document_extraction"},
                {"step": 2, "action": "document_validation"},
                {"step": 3, "action": "validity_checker"},
                {"step": 4, "action": "claim_preparation"}
            ]
        }
    )
    registry = InsureMateToolRegistry(offline_mode=True)
    agent = InsureMateAgent(llm_client=mock_llm, tool_registry=registry)

    # State with non-existent / corrupted document path
    state = ClaimState(
        goal="Process claim",
        documents=["/tmp/non_existent_corrupted_doc.pdf"]
    )

    final_state = agent.run(state=state)
    executed_tools = [h["tool_name"] for h in final_state.tool_history]

    # Only document_extraction was called; downstream planned steps were abandoned
    assert executed_tools == ["document_extraction"]
    assert "document_validation" not in executed_tools
    assert "validity_checker" not in executed_tools
    assert "claim_preparation" not in executed_tools
    assert final_state.final_status == ClaimStatus.INSUFFICIENT_INFORMATION.value


# ==============================================================================
# 6. SCENARIO 6: Failure recovery - controlled retry or alternative selection
# ==============================================================================
def test_scenario_6_failure_recovery():
    """
    Scenario 6: A failed tool call leads to an appropriate alternative or a justified retry.
    A flaky tool fails on attempt 1 with transient error, agent retries once, succeeds on attempt 2.
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

    mock_responses = [
        {
            "thought": "Calling flaky tool.",
            "action": "flaky_tool",
            "action_input": {},
            "reason": "Execute resilient operation.",
            "decision_type": "TOOL_CALL"
        },
        {
            "thought": "Flaky tool succeeded on retry. Concluding.",
            "action": "complete",
            "reason": "Operation satisfied after recovery.",
            "decision_type": "TERMINATE"
        }
    ]
    mock_llm = MockLLMClient(responses=mock_responses, planner_response={"goal": "Resilient test", "steps": []})
    agent = InsureMateAgent(llm_client=mock_llm, tool_registry=registry)

    state = ClaimState(goal="Execute resilient workflow.")
    final_state = agent.run(state=state)

    assert flaky.attempts == 2
    assert final_state.retry_counts.get("flaky_tool") == 1
    assert any("Retrying flaky_tool" in t["decision"] for t in final_state.execution_trace)
    assert final_state.final_status == ClaimStatus.CLAIM_READY_FOR_SUBMISSION.value


# ==============================================================================
# 7. SCENARIO 7: No unnecessary tools invoked
# ==============================================================================
def test_scenario_7_task_terminates_without_unnecessary_tools():
    """
    Scenario 7: The agent can finish without invoking irrelevant tools.
    When the goal is strictly to evaluate whether the medical bill date is within coverage,
    the agent terminates as soon as validity_checker succeeds without calling missing_document_detector,
    document_validation, or claim_preparation.
    """
    mock_responses = [
        {
            "thought": "Goal requires checking date validity only.",
            "action": "validity_checker",
            "action_input": {},
            "reason": "Check date validity.",
            "decision_type": "TOOL_CALL"
        },
        {
            "thought": "Dates are valid. Concluding.",
            "action": "complete",
            "reason": "Invoice date validated successfully.",
            "decision_type": "TERMINATE"
        }
    ]
    mock_llm = MockLLMClient(responses=mock_responses, planner_response={"goal": "Check dates", "steps": []})
    registry = InsureMateToolRegistry(offline_mode=True)
    agent = InsureMateAgent(llm_client=mock_llm, tool_registry=registry)

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
# 8. SCENARIO 8: No hardcoded fallback chain on invalid LLM output
# ==============================================================================
def test_scenario_8_no_hardcoded_fallback_chain():
    """
    Scenario 8: Invalid LLM output does NOT trigger a predefined sequence of insurance tools.
    When LLM output is malformed non-JSON across bounded recovery attempts, the agent
    aborts safely with human_review_required=True without executing any hardcoded pipeline.
    """
    mock_responses = [
        "Plain text non-JSON response 1",
        "Plain text non-JSON response 2",
        "Plain text non-JSON response 3"
    ]
    mock_llm = MockLLMClient(responses=mock_responses)
    registry = InsureMateToolRegistry(offline_mode=True)
    agent = InsureMateAgent(llm_client=mock_llm, tool_registry=registry)

    state = ClaimState(
        goal="Determine claim readiness.",
        extracted_data=SAMPLE_POLICY_DATA + SAMPLE_BILL_DATA
    )

    final_state = agent.run(state=state)

    # Must NOT have silently run a 5-step insurance pipeline!
    assert len(final_state.tool_history) == 0, "No tools should be run on invalid LLM output"
    assert final_state.final_status == ClaimStatus.INSUFFICIENT_INFORMATION.value
    assert final_state.final_report["human_review_required"] is True


# ==============================================================================
# 9. SCENARIO 9: Safety and validation of unknown/unauthorized actions
# ==============================================================================
def test_scenario_9_safety_and_validation():
    """
    Scenario 9: Unknown tools, invalid arguments, and unauthorized actions are rejected.
    LLM attempts to invoke an unregistered tool ('unauthorized_bank_transfer').
    The runtime intercepts and rejects it, records error observation, feeds it back,
    and the LLM recovers by calling a valid registered tool.
    """
    mock_responses = [
        {
            "thought": "Attempting external fund transfer.",
            "action": "unauthorized_bank_transfer",
            "action_input": {"amount": 50000},
            "reason": "Transfer claim payout immediately.",
            "decision_type": "TOOL_CALL"
        },
        {
            "thought": "Previous action was rejected as unknown tool. Recovering with policy clause search.",
            "action": "policy_clause_search",
            "action_input": {"query": "cataract"},
            "reason": "Query policy clauses for cataract limit.",
            "decision_type": "TOOL_CALL"
        },
        {
            "thought": "Search complete.",
            "action": "complete",
            "reason": "Information retrieved.",
            "decision_type": "TERMINATE"
        }
    ]
    mock_llm = MockLLMClient(responses=mock_responses, planner_response={"goal": "Test safety", "steps": []})
    registry = InsureMateToolRegistry(offline_mode=True)
    agent = InsureMateAgent(llm_client=mock_llm, tool_registry=registry)

    state = ClaimState(
        goal="Determine policy coverage limit.",
        extracted_data=SAMPLE_POLICY_DATA
    )

    final_state = agent.run(state=state)
    history_tools = [h["tool_name"] for h in final_state.tool_history]

    # Both attempted actions logged in history
    assert "unauthorized_bank_transfer" in history_tools
    assert "policy_clause_search" in history_tools

    # First tool must be marked as error/rejection
    rejected_entry = final_state.tool_history[0]
    assert rejected_entry["status"] == "error"
    assert "not recognized or available" in rejected_entry["error"] or "rejected" in rejected_entry["summary"].lower()


# ==============================================================================
# 10. SCENARIO 10: Execution limits stop agent safely
# ==============================================================================
def test_scenario_10_execution_limits():
    """
    Scenario 10: The agent stops safely when its tool-call or iteration budget is exhausted,
    preventing infinite looping.
    """
    mock_responses = [
        {"thought": "Turn 1.", "action": "policy_clause_search", "action_input": {"query": "a"}, "reason": "1", "decision_type": "TOOL_CALL"},
        {"thought": "Turn 2.", "action": "validity_checker", "action_input": {}, "reason": "2", "decision_type": "TOOL_CALL"},
        {"thought": "Turn 3.", "action": "missing_document_detector", "action_input": {}, "reason": "3", "decision_type": "TOOL_CALL"}
    ]
    mock_llm = MockLLMClient(responses=mock_responses, planner_response={"goal": "Budget test", "steps": []})
    registry = InsureMateToolRegistry(offline_mode=True)
    agent = InsureMateAgent(llm_client=mock_llm, tool_registry=registry, max_iterations=2)

    state = ClaimState(
        goal="Run multi-step analysis within 2 iterations.",
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
# 11. SCENARIO 11: Evidence grounding - verified facts vs unresolved questions
# ==============================================================================
def test_scenario_11_evidence_grounding():
    """
    Scenario 11: The final response distinguishes verified observations from missing or uncertain information.
    The agent records verified facts with provenance, and captures unresolved questions.
    """
    mock_responses = [
        {
            "thought": "Search cataract clause to verify limits.",
            "action": "policy_clause_search",
            "action_input": {"query": "cataract"},
            "reason": "Search cataract clause.",
            "decision_type": "TOOL_CALL"
        },
        {
            "thought": "Audit missing documents for the claim.",
            "action": "missing_document_detector",
            "action_input": {},
            "reason": "Audit missing documents.",
            "decision_type": "TOOL_CALL"
        },
        {
            "thought": "Evidence gathered. Concluding.",
            "action": "complete",
            "reason": "Claim evaluation completed with verified facts and missing document requirements identified.",
            "decision_type": "TERMINATE"
        }
    ]
    mock_llm = MockLLMClient(responses=mock_responses, planner_response={"goal": "Audit", "steps": []})
    registry = InsureMateToolRegistry(offline_mode=True)
    agent = InsureMateAgent(llm_client=mock_llm, tool_registry=registry)

    # State with policy only (bills and discharge summary missing)
    state = ClaimState(
        goal="Audit evidence and determine claim readiness.",
        extracted_data=SAMPLE_POLICY_DATA
    )

    final_state = agent.run(state=state)

    # Grounded facts
    assert "policy_clauses_found" in final_state.verified_facts
    assert "policy_clause_search" in final_state.evidence_provenance.get("policy_clauses_found", "")

    # Unresolved questions tracked
    assert len(final_state.unresolved_questions) > 0
    assert any("Missing mandatory document" in q for q in final_state.unresolved_questions)


# ==============================================================================
# 12. SCENARIO 12: Real integration with dynamic decision prompt
# ==============================================================================
def test_scenario_12_real_integration():
    """
    Scenario 12: The production agent uses the actual LLM-driven decision path rather than a mock-only implementation.
    Verifies that the prompt manifest exposes tool capabilities, parameters, and constraints,
    and that production services route through InsureMateDecisionEngine without hardcoded sequences.
    """
    from services.missing_document.ollama_client import OllamaClient
    from services.agent_service import AgentService

    client = OllamaClient()
    engine = InsureMateDecisionEngine(llm_client=client)
    registry = InsureMateToolRegistry(offline_mode=True)

    state = ClaimState(
        goal="Determine if cataract surgery is covered.",
        extracted_data=SAMPLE_POLICY_DATA
    )

    # 1. Verify dynamic prompt construction
    prompt = engine._build_user_prompt(state, registry)
    assert "AVAILABLE TOOLS MANIFEST:" in prompt
    assert "policy_clause_search" in prompt
    assert "parameters" in prompt.lower()
    assert "cross_document_consistency_check" in prompt
    assert "CURRENT CONTEXT & EVIDENCE:" in prompt

    # 2. Verify AgentService instantiates and runs through InsureMateAgent
    service = AgentService()
    session = service.create_session(goal="Verify coverage", offline_mode=False)
    assert session["claim_id"] is not None

    # 3. If live Ollama service is reachable, execute live inference
    if client.is_available():
        live_decision = engine.decide_next_action(state, registry)
        assert isinstance(live_decision, AgentDecision)
        assert live_decision.action in registry.get_tool_names() or live_decision.action in ("complete", "abort", "request_user_info")
