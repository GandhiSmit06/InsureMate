"""Test Case 6: Policy with Explicit Deadlines and Time Limits."""

import pytest
from AI.requirement_extraction.schema.models import Category
from .conftest import SAMPLE_DEADLINES_POLICY


def test_deadlines_exact_capture(engine):
    """Verify exact capture of intimation, document submission, and query deadlines."""
    response = engine.process(
        policy_text=SAMPLE_DEADLINES_POLICY,
        claim_type="hospitalization",
        policy_name="ChronoHealth Policy",
    )

    assert response.success is True
    deadline_items = [r for r in response.requirements if r.category == Category.DEADLINE]
    assert len(deadline_items) >= 2

    # 1. Emergency Intimation Deadline
    emergency_item = next(
        (r for r in deadline_items if "Emergency" in r.name),
        None,
    )
    assert emergency_item is not None
    assert emergency_item.deadline is not None
    assert "24" in emergency_item.deadline

    # 2. Document Submission Deadline
    submission_item = next(
        (r for r in deadline_items if "Submission" in r.name),
        None,
    )
    assert submission_item is not None
    assert submission_item.deadline is not None
    assert "15" in submission_item.deadline

    # 3. Query Response Deadline
    query_item = next(
        (r for r in deadline_items if "Query" in r.name),
        None,
    )
    assert query_item is not None
    assert query_item.deadline is not None
    assert "15" in query_item.deadline
