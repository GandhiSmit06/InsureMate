"""Test Case 3: Reimbursement Claim Requirement Extraction."""

import pytest
from phase3.schema.models import Category
from phase3.tests.conftest import SAMPLE_REIMBURSEMENT_POLICY


def test_reimbursement_claim_extraction(engine):
    """Verify reimbursement requirements and document submission deadlines."""
    response = engine.process(
        policy_text=SAMPLE_REIMBURSEMENT_POLICY,
        claim_type="reimbursement",
        policy_name="National Health Care",
    )

    assert response.success is True
    assert response.claim_type == "reimbursement"

    # Verify Submission Deadline
    sub_deadline = next(
        (r for r in response.requirements if "Submission Deadline" in r.name or r.category == Category.DEADLINE),
        None,
    )
    assert sub_deadline is not None
    assert sub_deadline.deadline is not None
    assert "30" in sub_deadline.deadline

    # Verify Treating Doctor Certificate
    doc_cert = next(
        (r for r in response.requirements if "Doctor Certificate" in r.name or "Treating Doctor" in r.name),
        None,
    )
    assert doc_cert is not None
    assert doc_cert.category == Category.DOCUMENT
    assert doc_cert.mandatory is True

    # Verify Claim Form
    claim_form = next(
        (r for r in response.requirements if "Claim Form" in r.name),
        None,
    )
    assert claim_form is not None
    assert claim_form.mandatory is True
