"""Test Case 4: Accident-Related Claim Requirement Extraction."""

import pytest
from phase3.schema.models import Category
from phase3.tests.conftest import SAMPLE_ACCIDENT_POLICY


def test_accident_claim_extraction(engine):
    """Verify accident-specific requirements: FIR, MLC, toxicology, and surgical notes."""
    response = engine.process(
        policy_text=SAMPLE_ACCIDENT_POLICY,
        claim_type="accident",
        policy_name="Accident Care Policy",
    )

    assert response.success is True
    assert response.claim_type == "accident"

    names = [r.name for r in response.requirements]
    assert any("FIR" in name or "Medico-Legal" in name for name in names)
    assert any("Alcohol" in name or "Toxicology" in name for name in names)

    # Inspect FIR / MLC
    fir_req = next(
        r for r in response.requirements if "FIR" in r.name or "Medico-Legal" in r.name
    )
    assert fir_req.category == Category.DOCUMENT
    assert fir_req.evidence_type == "legal_document"
    assert fir_req.condition is not None
    assert "accident" in fir_req.condition.lower()
    # It is conditional, so not marked universally mandatory
    assert fir_req.mandatory is False
    assert "fir_number" in fir_req.required_information
    assert "mlc_number" in fir_req.required_information

    # Inspect Toxicology report
    tox_req = next(
        r for r in response.requirements if "Alcohol" in r.name or "Toxicology" in r.name
    )
    assert tox_req.category == Category.DOCUMENT
    assert tox_req.condition is not None
    assert tox_req.mandatory is False

    # Inspect OT Notes & Implant Invoices
    assert any("Operation Theatre" in name for name in names)
    assert any("Implant" in name for name in names)
