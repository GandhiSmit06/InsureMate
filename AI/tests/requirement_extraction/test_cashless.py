"""Test Case 2: Cashless Treatment Requirement Extraction."""

import pytest
from AI.requirement_extraction.schema.models import Category
from .conftest import SAMPLE_CASHLESS_POLICY


def test_cashless_treatment_extraction(engine):
    """Verify extraction of cashless pre-auth, network hospital conditions, and intimation timelines."""
    response = engine.process(
        policy_text=SAMPLE_CASHLESS_POLICY,
        claim_type="cashless",
        policy_name="SecureHealth Policy",
    )

    assert response.success is True
    assert response.claim_type == "cashless"

    # Verify Network Hospital Condition
    network_cond = next(
        (r for r in response.requirements if "Network Hospital" in r.name),
        None,
    )
    assert network_cond is not None
    assert network_cond.category == Category.CONDITION
    assert network_cond.condition is not None
    assert "network" in network_cond.condition.lower()

    # Verify Pre-Authorization requirement
    preauth_req = next(
        (r for r in response.requirements if "Pre-Authorization" in r.name or "Approval" in r.name),
        None,
    )
    assert preauth_req is not None
    assert preauth_req.category == Category.DOCUMENT
    assert preauth_req.condition is not None

    # Verify Emergency Intimation Deadline
    emergency_deadline = next(
        (r for r in response.requirements if "Emergency" in r.name and r.category == Category.DEADLINE),
        None,
    )
    assert emergency_deadline is not None
    assert emergency_deadline.deadline is not None
    assert "24" in emergency_deadline.deadline
