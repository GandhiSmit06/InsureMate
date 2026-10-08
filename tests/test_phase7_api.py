"""tests/test_phase7_api.py
Unit and Integration tests for InsureMate Phase 7 REST API endpoints.
Verifies:
- GET /api/health
- GET /api/tools
- POST /api/claims/demo
- POST /api/claims/upload
- GET /api/claims
- GET /api/claims/{claim_id}
- DELETE /api/claims/{claim_id}
"""

import io
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
    """Create a FastAPI TestClient."""
    return TestClient(app)


def test_health_check(client: TestClient):
    """Verify system health endpoint returns 200 OK and version."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "InsureMate"
    assert "version" in data


def test_list_tools(client: TestClient):
    """Verify tool discovery endpoint returns all four registered core tools."""
    response = client.get("/api/tools")
    assert response.status_code == 200
    data = response.json()
    assert "tools" in data
    tool_names = [t["name"] for t in data["tools"]]
    assert any("extraction" in t for t in tool_names)
    assert any("validation" in t for t in tool_names)
    assert any("validity" in t for t in tool_names)
    assert any("missing" in t for t in tool_names)


def test_create_demo_claim_health(client: TestClient):
    """Verify creating a health insurance demo claim session."""
    response = client.post("/api/claims/demo", json={"preset": "health"})
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert "claim_id" in data
    assert data["claim"]["claim_type"] == "health"
    assert data["claim"]["status"] == "pending"

    # Cleanup
    claim_id = data["claim_id"]
    client.delete(f"/api/claims/{claim_id}")


def test_create_demo_claim_invalid_preset(client: TestClient):
    """Verify 400 error when specifying an unknown demo preset."""
    response = client.post("/api/claims/demo", json={"preset": "unknown_preset_123"})
    assert response.status_code == 400
    assert "Invalid preset" in response.json()["detail"]


def test_upload_claim_documents(client: TestClient):
    """Verify uploading policy and claim PDFs to create a new session."""
    policy_content = b"%PDF-1.4 Mock Policy File Content"
    claim_content = b"%PDF-1.4 Mock Claim Hospital Bill"

    files = [
        ("policy_file", ("policy.pdf", io.BytesIO(policy_content), "application/pdf")),
        ("claim_files", ("bill1.pdf", io.BytesIO(claim_content), "application/pdf")),
    ]
    data = {
        "claim_type": "auto",
        "goal": "Verify auto insurance accident claim readiness"
    }

    response = client.post("/api/claims/upload", data=data, files=files)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["success"] is True
    assert "claim_id" in res_data
    assert res_data["claim"]["claim_type"] == "auto"

    claim_id = res_data["claim_id"]

    # Verify retrieval
    get_res = client.get(f"/api/claims/{claim_id}")
    assert get_res.status_code == 200
    retrieved = get_res.json()
    assert retrieved["claim"]["claim_id"] == claim_id
    assert retrieved["claim"]["status"] == "pending"

    # Verify list contains this claim
    list_res = client.get("/api/claims")
    assert list_res.status_code == 200
    claims_list = list_res.json()["claims"]
    assert any(c["claim_id"] == claim_id for c in claims_list)

    # Cleanup
    del_res = client.delete(f"/api/claims/{claim_id}")
    assert del_res.status_code == 200

    # Verify 404 after deletion
    get_after_del = client.get(f"/api/claims/{claim_id}")
    assert get_after_del.status_code == 404
