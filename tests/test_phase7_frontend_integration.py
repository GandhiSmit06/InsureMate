"""tests/test_phase7_frontend_integration.py
Comprehensive integration tests for InsureMate Phase 7 Frontend & REST API.
Verifies HTML shell, static assets, autonomous agent orchestration,
state recall, and granular reporting sub-endpoints.
"""

import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.server import app


@pytest.fixture
def client():
    return TestClient(app)


def test_frontend_index_and_assets(client: TestClient):
    """Verify HTML shell and static CSS/JS assets are served with 200 OK."""
    # 1. Main index
    res = client.get("/")
    assert res.status_code == 200
    html = res.text
    assert "InsureMate" in html
    assert "Autonomous Agent" in html
    assert "stepper-track" in html
    assert "agent-completed-actions" in html
    assert "missing-evidence-tbody" in html

    # 2. CSS files
    assert client.get("/css/style.css").status_code == 200
    assert client.get("/css/dashboard.css").status_code == 200
    assert client.get("/css/upload.css").status_code == 200
    assert client.get("/css/agent.css").status_code == 200
    assert client.get("/css/responsive.css").status_code == 200

    # 3. JS files
    assert client.get("/js/utils.js").status_code == 200
    assert client.get("/js/api.js").status_code == 200
    assert client.get("/js/state.js").status_code == 200
    assert client.get("/js/dashboard.js").status_code == 200
    assert client.get("/js/upload.js").status_code == 200
    assert client.get("/js/agent.js").status_code == 200
    assert client.get("/js/documents.js").status_code == 200
    assert client.get("/js/claim.js").status_code == 200
    assert client.get("/js/app.js").status_code == 200


def test_agent_orchestration_and_sub_endpoints_workflow(client: TestClient):
    """Verify end-to-end flow:
    1. Create demo claim
    2. Start agent via /api/claims/{id}/agent/start
    3. Query agent status and activity
    4. Query documents, result, missing documents, validity, validation
    5. Clean up claim
    """
    # Step 1: Create Demo Claim
    create_res = client.post("/api/claims/demo", json={"preset": "health", "offline_mode": True})
    assert create_res.status_code == 201
    claim_id = create_res.json()["claim_id"]
    assert claim_id.startswith("CLM-")

    try:
        # Step 2: Trigger Agent
        run_res = client.post(
            f"/api/claims/{claim_id}/agent/start",
            json={"max_pages": 2, "offline_mode": True, "background": False}
        )
        assert run_res.status_code == 200
        run_data = run_res.json()
        assert run_data["status"] == "completed"
        assert "final_report" in run_data

        # Step 3: Check Agent Status
        status_res = client.get(f"/api/claims/{claim_id}/agent/status")
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["claim_id"] == claim_id
        assert status_data["status"] == "completed"
        assert status_data["has_result"] is True
        assert status_data["tool_count"] >= 3

        # Step 4: Check Agent Activity
        act_res = client.get(f"/api/claims/{claim_id}/agent/activity")
        assert act_res.status_code == 200
        act_data = act_res.json()
        assert len(act_data["tool_executions"]) >= 3
        assert len(act_data["execution_trace"]) >= 1

        # Step 5: Check Documents Sub-Endpoint
        docs_res = client.get(f"/api/claims/{claim_id}/documents")
        assert docs_res.status_code == 200
        docs_data = docs_res.json()
        assert docs_data["claim_id"] == claim_id
        assert len(docs_data["extracted_pages"]) >= 1

        # Step 6: Check Final Result Sub-Endpoint
        res_res = client.get(f"/api/claims/{claim_id}/result")
        assert res_res.status_code == 200
        res_data = res_res.json()
        assert res_data["final_report"] is not None
        assert "verdict" in res_data

        # Step 7: Check Missing Documents Sub-Endpoint
        miss_res = client.get(f"/api/claims/{claim_id}/missing-documents")
        assert miss_res.status_code == 200
        miss_data = miss_res.json()
        assert "missing_documents" in miss_data

        # Step 8: Check Validity Sub-Endpoint
        val_res = client.get(f"/api/claims/{claim_id}/validity")
        assert val_res.status_code == 200
        assert "validity_result" in val_res.json()

        # Step 9: Check Validation Sub-Endpoint
        valid_res = client.get(f"/api/claims/{claim_id}/validation")
        assert valid_res.status_code == 200
        assert "validation_result" in valid_res.json()

    finally:
        # Step 10: Clean up
        del_res = client.delete(f"/api/claims/{claim_id}")
        assert del_res.status_code == 200
