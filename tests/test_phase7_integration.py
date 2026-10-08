"""tests/test_phase7_integration.py
End-to-End Integration tests for InsureMate Phase 7:
Upload / Session Creation -> Agent Autonomous Planning -> Tool Execution -> 
Claim State Persistence -> Final Readiness Report -> Database Memory Recall.
"""

import sys
import tempfile
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agent.state import ClaimStatus
from services.agent_service import AgentService
from services.database.db import ClaimDatabase


@pytest.fixture
def agent_service_isolated():
    """Create an AgentService with an isolated temporary DB and upload directory."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_isolated.db"
        upload_dir = Path(tmp_dir) / "uploads"
        service = AgentService(db_path=db_path, upload_dir=upload_dir)
        yield service


def test_end_to_end_agent_service_workflow(agent_service_isolated: AgentService):
    """Test full Phase 7 workflow:
    1. Create demo claim session
    2. Run autonomous agent in offline mode
    3. Verify tool history envelopes logged in DB
    4. Verify final report saved with valid verdict and readiness metrics
    5. Verify memory retrieval via get_claim()
    """
    # Step 1: Create demo claim
    claim = agent_service_isolated.create_demo_claim(preset="health")
    claim_id = claim["claim_id"]
    assert claim["status"] == "pending"
    assert claim["claim_type"] == "health"

    # Step 2: Execute autonomous agent run
    result = agent_service_isolated.run_claim(
        claim_id=claim_id,
        offline_mode=True,
        max_pages=2
    )

    # Step 3: Verify execution success & state
    assert result["success"] is True
    assert result["status"] == "completed"
    assert "final_report" in result
    final_report = result["final_report"]
    assert final_report is not None
    assert "verdict" in final_report
    valid_verdicts = [s.value for s in ClaimStatus] + ["READY", "ACTION_REQUIRED", "PENDING_DOCUMENTS", "INVALID_CLAIM_DATES"]
    assert final_report["verdict"] in valid_verdicts


    # Step 4: Verify tool envelopes recorded in database
    executions = agent_service_isolated.db.get_tool_executions(claim_id)
    assert len(executions) >= 3, "Expected at least 3 tool execution envelopes logged in DB"

    tool_names = [e["tool_name"] for e in executions]
    assert any("extraction" in name or "qwen" in name for name in tool_names)
    assert any("valid" in name for name in tool_names)

    # Step 5: Verify claim state snapshots recorded
    snapshots = agent_service_isolated.db.get_state_snapshots(claim_id)
    assert len(snapshots) >= 1, "Expected state snapshots to be persisted in DB"

    # Step 6: Verify final report stored in database
    stored_report = agent_service_isolated.db.get_final_report(claim_id)
    assert stored_report is not None
    assert stored_report["claim_id"] == claim_id
    assert stored_report["verdict"] == final_report["verdict"]

    # Step 7: Verify comprehensive claim bundle retrieval
    bundle = agent_service_isolated.get_claim(claim_id)
    assert bundle is not None
    assert bundle["claim"]["status"] == "completed"
    assert len(bundle["tool_executions"]) == len(executions)
    assert bundle["final_report"] is not None

    # Step 8: Verify claim listing in history
    claims_list = agent_service_isolated.list_claims()
    assert len(claims_list) >= 1
    found = next((c for c in claims_list if c["claim_id"] == claim_id), None)
    assert found is not None
    assert found["status"] == "completed"
    assert found["verdict"] == final_report["verdict"]


def test_agent_service_travel_preset(agent_service_isolated: AgentService):
    """Test travel demo preset end-to-end execution."""
    claim = agent_service_isolated.create_demo_claim(preset="travel")
    claim_id = claim["claim_id"]

    result = agent_service_isolated.run_claim(
        claim_id=claim_id,
        offline_mode=True,
        max_pages=2
    )

    assert result["success"] is True
    assert result["status"] == "completed"
    assert result["final_report"] is not None
    valid_verdicts = [s.value for s in ClaimStatus] + ["READY", "ACTION_REQUIRED", "PENDING_DOCUMENTS", "INVALID_CLAIM_DATES"]
    assert result["final_report"]["verdict"] in valid_verdicts
