"""Test Case 7: Policy with Ambiguous and Discretionary Wording."""

import pytest
from phase3.schema.models import Category
from phase3.tests.conftest import SAMPLE_AMBIGUOUS_POLICY


def test_ambiguous_wording_handling(engine):
    """Verify handling of discretionary clauses without hallucinating specific documents."""
    response = engine.process(
        policy_text=SAMPLE_AMBIGUOUS_POLICY,
        claim_type="hospitalization",
        policy_name="Flexi-Care",
    )

    assert response.success is True
    assert len(response.requirements) >= 1

    discretionary_item = response.requirements[0]
    assert discretionary_item.mandatory is False
    assert discretionary_item.condition is not None
    assert "discretion" in discretionary_item.condition.lower() or "insurer" in discretionary_item.description.lower()

    # Verify that engine did NOT invent specific non-existent documents
    names = [r.name.lower() for r in response.requirements]
    assert not any("passport" in n for n in names)
    assert not any("driving license" in n for n in names)
    assert not any("tax return" in n for n in names)
