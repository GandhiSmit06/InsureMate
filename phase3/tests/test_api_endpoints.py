"""Test Case 11: FastAPI HTTP API Endpoints Test."""

import io
import pytest
from fastapi.testclient import TestClient
from phase3.main import app
from phase3.tests.conftest import SAMPLE_HOSPITALIZATION_POLICY
from phase3.tests.test_pdf_upload import create_test_pdf_bytes

client = TestClient(app)


def test_health_check_endpoint():
    """Verify GET /api/phase3/health returns HTTP 200 and valid status."""
    response = client.get("/api/phase3/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "InsureMate Phase 3" in data["module"]
    assert "version" in data


def test_root_endpoint():
    """Verify GET / returns documentation and links."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "extract_endpoint" in data


def test_extract_requirements_json():
    """Verify POST /api/phase3/extract-requirements with JSON body."""
    payload = {
        "claim_type": "hospitalization",
        "policy_text": SAMPLE_HOSPITALIZATION_POLICY,
        "policy_name": "Mediclaim API Test",
    }
    response = client.post(
        "/api/phase3/extract-requirements",
        json=payload,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["claim_type"] == "hospitalization"
    assert data["policy_name"] == "Mediclaim API Test"
    assert isinstance(data["requirements"], list)
    assert len(data["requirements"]) >= 4

    # Verify requirement item structure
    first = data["requirements"][0]
    assert "requirement_id" in first
    assert "category" in first
    assert "name" in first
    assert "mandatory" in first
    assert "priority" in first


def test_extract_requirements_pdf_upload():
    """Verify POST /api/phase3/extract-requirements with multipart PDF upload."""
    pdf_bytes = create_test_pdf_bytes([
        "Policy requires Hospital Discharge Summary and Final Hospital Bill."
    ])

    files = {
        "file": ("policy.pdf", io.BytesIO(pdf_bytes), "application/pdf")
    }
    data = {
        "claim_type": "hospitalization",
        "policy_name": "Uploaded Policy",
    }

    response = client.post(
        "/api/phase3/extract-requirements",
        data=data,
        files=files,
    )
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["success"] is True
    assert len(res_json["requirements"]) >= 1


def test_extract_requirements_empty_input():
    """Verify that empty request triggers HTTP 400."""
    response = client.post(
        "/api/phase3/extract-requirements",
        json={"policy_text": ""},
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400


def test_extract_requirements_invalid_file_type():
    """Verify that uploading non-PDF/non-text file returns HTTP 400."""
    files = {
        "file": ("document.exe", io.BytesIO(b"fake executable"), "application/octet-stream")
    }
    response = client.post(
        "/api/phase3/extract-requirements",
        files=files,
    )
    assert response.status_code == 400
