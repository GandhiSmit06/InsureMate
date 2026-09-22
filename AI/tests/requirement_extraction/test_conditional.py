"""Test Case 5: Policy Containing Conditional Requirements."""

import pytest
from AI.requirement_extraction.schema.models import Category
from .conftest import SAMPLE_CONDITIONAL_POLICY


def test_conditional_requirements_preservation(engine):
    """Verify that conditional requirements are preserved and not marked universally mandatory."""
    response = engine.process(
        policy_text=SAMPLE_CONDITIONAL_POLICY,
        claim_type="hospitalization",
        policy_name="Elite Health Shield",
    )

    assert response.success is True
    assert len(response.requirements) >= 3

    # 1. Indoor Case Papers (ICU conditional)
    icp_req = next(
        (r for r in response.requirements if "Indoor Case Papers" in r.name),
        None,
    )
    assert icp_req is not None
    assert icp_req.condition is not None
    assert icp_req.mandatory is False

    # 2. Organ Donor Screening
    donor_req = next(
        (r for r in response.requirements if "Organ Donor" in r.name),
        None,
    )
    assert donor_req is not None
    assert donor_req.category == Category.CONDITION
    assert donor_req.condition is not None
    assert donor_req.mandatory is False

    # 3. High-Value Claims KYC
    kyc_req = next(
        (r for r in response.requirements if "KYC" in r.name),
        None,
    )
    assert kyc_req is not None
    assert kyc_req.condition is not None
    assert "1,00,000" in kyc_req.condition or "exceed" in kyc_req.condition.lower()
    assert kyc_req.mandatory is False

    # Check that summary correctly accounts for conditional count
    assert response.summary.conditional_count >= 3
