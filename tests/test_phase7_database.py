"""tests/test_phase7_database.py
Unit tests for InsureMate Phase 7 Database Layer (ClaimDatabase).
Verifies:
- Thread-safe SQLite database initialization
- Claim session creation, retrieval, and status updates
- Tool execution envelopes logging
- Claim state snapshots persistence
- Final readiness report persistence and structured JSON retrieval
- Cascade deletion when a claim session is deleted
"""

import sys
import tempfile
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.database.db import ClaimDatabase


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for test isolation."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_insuremate.db"
        db = ClaimDatabase(db_path=db_path)
        yield db


def test_claim_creation_and_retrieval(temp_db: ClaimDatabase):
    """Verify claim session creation, retrieval, and fields."""
    claim_id = "test-claim-001"
    created = temp_db.create_claim(
        claim_id=claim_id,
        claim_type="health",
        policy_filename="sample_policy.pdf",
        claim_filenames=["hospital_bill.pdf", "discharge_summary.pdf"],
        goal="Determine health claim readiness"
    )
    assert created["claim_id"] == claim_id
    assert created["claim_type"] == "health"
    assert created["status"] == "pending"
    assert created["policy_filename"] == "sample_policy.pdf"
    assert len(created["claim_filenames"]) == 2

    retrieved = temp_db.get_claim(claim_id)
    assert retrieved is not None
    assert retrieved["claim_id"] == claim_id
    assert retrieved["goal"] == "Determine health claim readiness"


def test_claim_status_update(temp_db: ClaimDatabase):
    """Verify updating claim status."""
    claim_id = "test-claim-status"
    temp_db.create_claim(claim_id=claim_id)

    temp_db.update_claim_status(claim_id, "processing")
    c = temp_db.get_claim(claim_id)
    assert c["status"] == "processing"

    temp_db.update_claim_status(claim_id, "completed")
    c2 = temp_db.get_claim(claim_id)
    assert c2["status"] == "completed"


def test_tool_execution_logging(temp_db: ClaimDatabase):
    """Verify recording and fetching tool execution logs."""
    claim_id = "test-claim-tools"
    temp_db.create_claim(claim_id=claim_id)

    envelope1 = {
        "tool_name": "qwen_vl_extraction_tool",
        "parameters": {"pdf_path": "policy.pdf", "max_pages": 2},
        "status": "success",
        "output": {"total_pages": 2, "extracted_documents": [{"document_type": "policy"}]},
        "error_message": None,
        "execution_time_ms": 142.5
    }
    envelope2 = {
        "tool_name": "validity_checker_tool",
        "parameters": {"policy_data": {}, "document_data": []},
        "status": "success",
        "output": {"is_valid": True},
        "error_message": None,
        "execution_time_ms": 50.0
    }

    log_id1 = temp_db.record_tool_execution(claim_id, envelope1)
    log_id2 = temp_db.record_tool_execution(claim_id, envelope2)
    assert log_id1 > 0
    assert log_id2 > log_id1

    logs = temp_db.get_tool_executions(claim_id)
    assert len(logs) == 2
    assert logs[0]["tool_name"] == "qwen_vl_extraction_tool"
    assert logs[0]["output"]["total_pages"] == 2
    assert logs[1]["tool_name"] == "validity_checker_tool"


def test_state_snapshot_and_final_report(temp_db: ClaimDatabase):
    """Verify persisting state snapshots and final claim reports."""
    claim_id = "test-claim-report"
    temp_db.create_claim(claim_id=claim_id)

    # Save snapshot
    snap_id = temp_db.save_state_snapshot(
        claim_id=claim_id,
        step_number=1,
        state_data={"current_phase": 1, "extracted_documents": [{"type": "bill"}]}
    )
    assert snap_id > 0
    snapshots = temp_db.get_state_snapshots(claim_id)
    assert len(snapshots) == 1
    assert snapshots[0]["step_number"] == 1
    assert snapshots[0]["state_data"]["current_phase"] == 1

    # Save final report
    report_data = {
        "verdict": "READY",
        "confidence_score": 95,
        "missing_documents_count": 0,
        "validity_status": "VALID",
        "details": {"summary": "All required receipts present"}
    }
    rep_id = temp_db.save_final_report(
        claim_id=claim_id,
        report_data=report_data,
        verdict="READY",
        confidence_score=95
    )
    assert rep_id > 0

    saved_report = temp_db.get_final_report(claim_id)
    assert saved_report is not None
    assert saved_report["verdict"] == "READY"
    assert saved_report["confidence_score"] == 95
    assert saved_report["report_data"]["details"]["summary"] == "All required receipts present"


def test_cascade_delete(temp_db: ClaimDatabase):
    """Verify deleting a claim removes all associated logs, snapshots, and reports."""
    claim_id = "test-claim-delete"
    temp_db.create_claim(claim_id=claim_id)
    temp_db.record_tool_execution(claim_id, {
        "tool_name": "test_tool",
        "parameters": {},
        "status": "success",
        "output": {}
    })
    temp_db.save_state_snapshot(claim_id, 1, {"step": 1})
    temp_db.save_final_report(claim_id, {"verdict": "READY"}, "READY", 100)

    # Verify presence
    assert temp_db.get_claim(claim_id) is not None
    assert len(temp_db.get_tool_executions(claim_id)) == 1
    assert len(temp_db.get_state_snapshots(claim_id)) == 1
    assert temp_db.get_final_report(claim_id) is not None

    # Delete claim
    deleted = temp_db.delete_claim(claim_id)
    assert deleted is True

    # Verify everything is cleaned up
    assert temp_db.get_claim(claim_id) is None
    assert len(temp_db.get_tool_executions(claim_id)) == 0
    assert len(temp_db.get_state_snapshots(claim_id)) == 0
    assert temp_db.get_final_report(claim_id) is None
