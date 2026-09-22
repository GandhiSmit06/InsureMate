"""Test Case 1: Hospitalization Claim Requirement Extraction."""

import pytest
from AI.requirement_extraction.schema.models import Category, Priority
from .conftest import SAMPLE_HOSPITALIZATION_POLICY


def test_hospitalization_claim_extraction(engine):
    """Verify extraction of standard inpatient hospitalization requirements."""
    response = engine.process(
        policy_text=SAMPLE_HOSPITALIZATION_POLICY,
        claim_type="hospitalization",
        policy_name="Mediclaim Plus",
    )

    assert response.success is True
    assert response.claim_type == "hospitalization"
    assert response.policy_name == "Mediclaim Plus"
    assert len(response.requirements) >= 5

    # Check for Discharge Summary
    names = [r.name for r in response.requirements]
    assert any("Discharge Summary" in name for name in names)
    assert any("Bill" in name for name in names)
    assert any("Receipt" in name for name in names)
    assert any("Prescription" in name for name in names)
    assert any("Diagnostic" in name or "Investigation" in name for name in names)

    # Inspect Discharge Summary details
    discharge_summary = next(
        r for r in response.requirements if "Discharge Summary" in r.name
    )
    assert discharge_summary.category == Category.DOCUMENT
    assert discharge_summary.mandatory is True
    assert discharge_summary.priority == Priority.HIGH
    assert discharge_summary.evidence_type == "hospital_document"
    assert "patient_name" in discharge_summary.required_information
    assert "admission_date" in discharge_summary.required_information
    assert "diagnosis" in discharge_summary.required_information
    assert discharge_summary.requirement_id.startswith("REQ-")

    # Verify summary metrics
    assert response.summary is not None
    assert response.summary.total_requirements == len(response.requirements)
    assert response.summary.mandatory_count >= 5
    assert response.summary.categories["DOCUMENT"] >= 5
