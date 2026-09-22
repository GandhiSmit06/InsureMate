"""Test Case 8: Policy Containing Duplicate / Similar Requirements."""

import pytest
from AI.requirement_extraction.schema.models import Category
from .conftest import SAMPLE_DUPLICATE_POLICY


def test_duplicate_requirement_deduplication(engine):
    """Verify that duplicate and overlapping requirements across clauses/pages are merged."""
    response = engine.process(
        policy_text=SAMPLE_DUPLICATE_POLICY,
        claim_type="hospitalization",
        policy_name="Optima Health Plan",
    )

    assert response.success is True

    # Count occurrences of Discharge Summary and Hospital Bill
    discharge_summaries = [
        r for r in response.requirements if "Discharge Summary" in r.name
    ]
    bills = [
        r for r in response.requirements if "Hospital Final Bill" in r.name or "Itemized" in r.name
    ]
    receipts = [
        r for r in response.requirements if "Payment Receipts" in r.name
    ]

    # Deduplication MUST ensure exactly 1 item per canonical document
    assert len(discharge_summaries) == 1, f"Expected 1 Discharge Summary, got {len(discharge_summaries)}"
    assert len(bills) == 1, f"Expected 1 Hospital Bill, got {len(bills)}"
    assert len(receipts) == 1, f"Expected 1 Receipt item, got {len(receipts)}"

    # Check merged required_information in Discharge Summary
    ds = discharge_summaries[0]
    assert "diagnosis" in ds.required_information
    assert "admission_date" in ds.required_information
    assert "discharge_date" in ds.required_information

    # Check sequential IDs
    ids = [r.requirement_id for r in response.requirements]
    assert ids == [f"REQ-{i+1:03d}" for i in range(len(response.requirements))]
