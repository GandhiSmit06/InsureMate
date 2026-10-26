"""tests/test_regression_deleted_uploads.py
Comprehensive regression tests for InsureMate analysis lifecycle, deleted upload isolation,
validation execution state, and accurate verdict aggregation.
"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from agent.state import ClaimState, ClaimStatus
from agent.tools import (
    ClaimPreparationAdapter,
    DocumentValidationAdapter,
    ValidityCheckerAdapter,
)
from services.database.db import ClaimDatabase
from services.agent_service import AgentService
from tools.qwen_vl_tool import QwenVLExtractionTool


# Paths to test sample PDFs
ROOT_DIR = Path(__file__).resolve().parent.parent
SAMPLE_POLICY_PDF = ROOT_DIR / "InsureMate_Test_Health_Insurance_Policy.pdf"
SAMPLE_CLAIM_PDF = ROOT_DIR / "InsureMate_Test_Health_Insurance_Claim_Documents.pdf"


@pytest.fixture
def temp_workspace():
    tmp_dir = Path(tempfile.mkdtemp(prefix="insuremate_test_ws_"))
    db_path = tmp_dir / "test_insuremate.db"
    uploads_dir = tmp_dir / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    yield tmp_dir, db_path, uploads_dir
    shutil.rmtree(tmp_dir, ignore_errors=True)


# ==============================================================================
# 1. Valid current analysis after deleting unrelated old upload files
# ==============================================================================
def test_scenario_1_valid_analysis_after_deleting_unrelated_old_uploads(temp_workspace):
    """Deleting old/unrelated files from uploads directory must NOT break current analysis."""
    _, db_path, uploads_dir = temp_workspace
    service = AgentService(db_path=db_path, upload_dir=uploads_dir)

    # 1. Create an unrelated old claim and populate old files
    old_claim = service.create_session(offline_mode=True)
    old_claim_id = old_claim["claim_id"]
    old_dir = uploads_dir / old_claim_id
    old_dir.mkdir(parents=True, exist_ok=True)
    old_dummy = old_dir / "old_unrelated_file.pdf"
    old_dummy.write_text("Dummy content for old file")

    # Also place an unrelated orphan file in root of uploads
    orphan_file = uploads_dir / "unrelated_orphan.pdf"
    orphan_file.write_text("Orphan content")

    # 2. Create the current claim with valid documents
    curr_policy = uploads_dir / "Current_Policy.pdf"
    curr_claim_doc = uploads_dir / "Current_Claim.pdf"
    shutil.copyfile(SAMPLE_POLICY_PDF, curr_policy)
    shutil.copyfile(SAMPLE_CLAIM_PDF, curr_claim_doc)

    current_claim = service.create_session(
        policy_file_path=str(curr_policy),
        claim_file_path=str(curr_claim_doc),
        offline_mode=True
    )
    current_claim_id = current_claim["claim_id"]

    # 3. Delete the unrelated old upload files
    shutil.rmtree(old_dir, ignore_errors=True)
    if orphan_file.exists():
        orphan_file.unlink()

    assert not old_dir.exists()
    assert not orphan_file.exists()

    # 4. Run analysis on current claim
    history = service.run_agent(current_claim_id, offline_mode=True)

    # Must complete successfully and not be marked INSUFFICIENT_INFORMATION due to missing old files
    assert history["verdict"] != ClaimStatus.INSUFFICIENT_INFORMATION.value
    assert history["verdict"] in (
        ClaimStatus.CLAIM_READY_FOR_SUBMISSION.value,
        ClaimStatus.ACTION_REQUIRED_MISSING_EVIDENCE.value,
    )
    assert len(history.get("latest_state", {}).get("extracted_data", [])) > 0
    assert history.get("latest_state", {}).get("validation_result") is not None


# ==============================================================================
# 2. Current analysis whose required source document has actually been deleted
# ==============================================================================
def test_scenario_2_current_analysis_source_document_deleted(temp_workspace):
    """If a file genuinely required by the current analysis is deleted, accurately report it."""
    _, db_path, uploads_dir = temp_workspace
    service = AgentService(db_path=db_path, upload_dir=uploads_dir)

    required_policy = uploads_dir / "Required_Policy.pdf"
    shutil.copyfile(SAMPLE_POLICY_PDF, required_policy)

    claim = service.create_session(
        policy_file_path=str(required_policy),
        offline_mode=True
    )
    claim_id = claim["claim_id"]

    # Genuinely delete the required source file
    required_policy.unlink()
    assert not required_policy.exists()

    # Run agent
    history = service.run_agent(claim_id, offline_mode=True)

    # Must report that the required source file is missing
    assert history["verdict"] == ClaimStatus.INSUFFICIENT_INFORMATION.value
    errs = history.get("latest_state", {}).get("errors", [])
    assert any("Required source document not found" in e for e in errs)
    report = history.get("final_report", {})
    assert "Required source document not found" in report.get("decision_summary", "")


# ==============================================================================
# 3. Analysis with completed validation results persisted in the database
# ==============================================================================
def test_scenario_3_completed_validation_results_persisted_in_db(temp_workspace):
    """Completed validation results must be properly persisted in SQLite."""
    _, db_path, uploads_dir = temp_workspace
    service = AgentService(db_path=db_path, upload_dir=uploads_dir)

    policy_file = uploads_dir / "Persist_Policy.pdf"
    claim_file = uploads_dir / "Persist_Claim.pdf"
    shutil.copyfile(SAMPLE_POLICY_PDF, policy_file)
    shutil.copyfile(SAMPLE_CLAIM_PDF, claim_file)

    claim = service.create_session(
        policy_file_path=str(policy_file),
        claim_file_path=str(claim_file),
        offline_mode=True
    )
    claim_id = claim["claim_id"]

    service.run_agent(claim_id, offline_mode=True)

    # Directly inspect database records
    db = ClaimDatabase(db_path=db_path)
    claim_record = db.get_claim(claim_id)
    assert claim_record is not None
    assert claim_record.get("status") is not None

    snapshots = db.get_state_snapshots(claim_id)
    assert len(snapshots) > 0
    final_snap = snapshots[-1]
    state_data = final_snap.get("state_data", {})
    assert state_data.get("validation_result") is not None
    assert state_data.get("validity_result") is not None


# ==============================================================================
# 4. Analysis whose mandatory validation has genuinely not executed
# ==============================================================================
def test_scenario_4_mandatory_validation_genuinely_not_executed():
    """If mandatory validation has genuinely not executed, accurately report incomplete."""
    state = ClaimState(
        claim_id="CLM-TEST-UNEXEC",
        goal="Determine claim readiness.",
        extracted_data=[],  # No data extracted
        validation_result=None,
        validity_result=None,
    )
    result = ClaimPreparationAdapter().run(state)
    assert result.status == "success"
    assert state.final_status == ClaimStatus.INSUFFICIENT_INFORMATION.value
    assert "No documents available" in state.final_report.get("decision_summary", "")


# ==============================================================================
# 5. Analysis where validation fails
# ==============================================================================
def test_scenario_5_analysis_where_validation_fails():
    """If validation executes and fails, report ACTION_REQUIRED_INVALID_DOCUMENTS."""
    invalid_data = [
        {"page_number": 1, "document_type": "unknown", "document_title": "Unreadable Fax"},
        {"page_number": 2, "document_type": "medical_bill", "document_title": "Damaged Bill"},
    ]
    state = ClaimState(
        claim_id="CLM-INVALID-DOCS",
        goal="Determine claim readiness.",
        extracted_data=invalid_data,
    )
    # Run validation
    DocumentValidationAdapter().run(state)
    assert state.validation_result is not None
    assert state.validation_result.get("valid") is False

    # Run claim prep
    ClaimPreparationAdapter().run(state)
    assert state.final_status == ClaimStatus.ACTION_REQUIRED_INVALID_DOCUMENTS.value
    assert "failed mandatory field validation" in state.final_report.get("decision_summary", "")


# ==============================================================================
# 6. Correct propagation of OCR extraction results into validation
# ==============================================================================
def test_scenario_6_correct_propagation_of_ocr_into_validation():
    """Extracted OCR fields (dates, amounts, policy info) propagate cleanly to validation."""
    extraction_tool = QwenVLExtractionTool(offline_mode=True)
    res = extraction_tool.run(SAMPLE_POLICY_PDF, max_pages=2)
    assert res.get("status") == "success"
    extracted_docs = res.get("extracted_documents", [])
    assert len(extracted_docs) > 0

    state = ClaimState(
        claim_id="CLM-OCR-PROP",
        goal="Determine claim readiness.",
        documents=[str(SAMPLE_POLICY_PDF)],
        extracted_data=extracted_docs,
    )

    # Document validation consumes extracted data
    val_res = DocumentValidationAdapter().run(state)
    assert val_res.status == "success"
    assert state.validation_result is not None
    assert state.validation_result.get("total_documents") == len(extracted_docs)

    # Date checker consumes extracted data
    date_res = ValidityCheckerAdapter().run(state)
    assert date_res.status == "success"
    assert state.validity_result is not None


# ==============================================================================
# 7. Correct page-level field provenance after the OCR fix
# ==============================================================================
def test_scenario_7_page_level_provenance_preserved():
    """Ensure page numbers are 1-indexed and field provenance is preserved."""
    extraction_tool = QwenVLExtractionTool(offline_mode=True)
    res = extraction_tool.run(SAMPLE_CLAIM_PDF, max_pages=3)
    pages = res.get("extracted_documents", [])

    for idx, p in enumerate(pages):
        assert p["page_number"] == idx + 1
        assert "document_type" in p
        assert "source_file" in p or "document_name" in p


# ==============================================================================
# 8. Report uses correct analysis ID and its associated documents
# ==============================================================================
def test_scenario_8_report_uses_correct_analysis_id_and_associated_docs(temp_workspace):
    """Two concurrent/sequential claims must not cross-contaminate documents."""
    _, db_path, uploads_dir = temp_workspace
    service = AgentService(db_path=db_path, upload_dir=uploads_dir)

    # Claim A
    doc_a = uploads_dir / "PolicyA.pdf"
    shutil.copyfile(SAMPLE_POLICY_PDF, doc_a)
    claim_a = service.create_session(policy_file_path=str(doc_a), offline_mode=True)
    id_a = claim_a["claim_id"]
    hist_a = service.run_agent(id_a, offline_mode=True)

    # Claim B
    doc_b = uploads_dir / "ClaimB.pdf"
    shutil.copyfile(SAMPLE_CLAIM_PDF, doc_b)
    claim_b = service.create_session(claim_file_path=str(doc_b), offline_mode=True)
    id_b = claim_b["claim_id"]
    hist_b = service.run_agent(id_b, offline_mode=True)

    assert hist_a["claim"]["claim_id"] == id_a
    assert hist_b["claim"]["claim_id"] == id_b
    assert hist_a["claim"]["claim_id"] != hist_b["claim"]["claim_id"]

    docs_a = [p.get("source_file") for p in hist_a.get("latest_state", {}).get("extracted_data", [])]
    docs_b = [p.get("source_file") for p in hist_b.get("latest_state", {}).get("extracted_data", [])]

    assert all("PolicyA" in d for d in docs_a if d)
    assert all("ClaimB" in d for d in docs_b if d)


# ==============================================================================
# 9. Existing analysis whose results are retrieved after application restarts
# ==============================================================================
def test_scenario_9_existing_analysis_retrieved_after_restart(temp_workspace):
    """Re-instantiating AgentService retrieves identical persisted results."""
    _, db_path, uploads_dir = temp_workspace
    service1 = AgentService(db_path=db_path, upload_dir=uploads_dir)

    policy_file = uploads_dir / "Restart_Policy.pdf"
    claim_file = uploads_dir / "Restart_Claim.pdf"
    shutil.copyfile(SAMPLE_POLICY_PDF, policy_file)
    shutil.copyfile(SAMPLE_CLAIM_PDF, claim_file)

    claim = service1.create_session(
        policy_file_path=str(policy_file),
        claim_file_path=str(claim_file),
        offline_mode=True
    )
    claim_id = claim["claim_id"]

    res1 = service1.run_agent(claim_id, offline_mode=True)

    # Simulate restart by instantiating new AgentService
    service2 = AgentService(db_path=db_path, upload_dir=uploads_dir)
    res2 = service2.get_claim(claim_id)

    assert res2["claim"]["claim_id"] == claim_id
    assert res2["verdict"] == res1["verdict"]
    assert len(res2.get("latest_state", {}).get("extracted_data", [])) == len(res1.get("latest_state", {}).get("extracted_data", []))
    assert res2.get("final_report", {}).get("verdict") == res1.get("final_report", {}).get("verdict")
    assert res2.get("final_report", {}).get("status") == res1.get("final_report", {}).get("status")
    assert res2.get("final_report", {}).get("is_ready") == res1.get("final_report", {}).get("is_ready")


# ==============================================================================
# 10. Accurate frontend representation of backend validation status
# ==============================================================================
def test_scenario_10_accurate_frontend_status_representation():
    """Verify backend status maps to accurate frontend indicators."""
    # When status is INSUFFICIENT_INFORMATION
    state = ClaimState(
        claim_id="CLM-INSUFF",
        goal="Determine claim readiness.",
        extracted_data=[],
        errors=["Missing document paths."]
    )
    ClaimPreparationAdapter().run(state)
    report = state.final_report
    assert report["status"] == ClaimStatus.INSUFFICIENT_INFORMATION.value
    # Coverage validity is NOT_CHECKED when validity was never run
    assert report["coverage_validity_status"] == "NOT_CHECKED"
    assert report["is_ready"] is False
