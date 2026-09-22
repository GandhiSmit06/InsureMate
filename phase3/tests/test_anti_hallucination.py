"""Test Case 9: Anti-Hallucination and Zero-Invention Verification."""

import pytest
from phase3.schema.models import RequirementItem, Category, Priority, PageText
from phase3.validator.hallucination_guard import HallucinationGuard
from phase3.tests.conftest import SAMPLE_MINIMAL_POLICY


def test_no_hallucinated_documents_in_minimal_policy(engine):
    """Test that the engine extracts strictly what is in the policy and does NOT invent unmentioned documents."""
    response = engine.process(
        policy_text=SAMPLE_MINIMAL_POLICY,
        claim_type="hospitalization",
        policy_name="Basic Hospital Cash Plan",
    )

    assert response.success is True
    # Should only have Claim Form and Discharge Card/Summary
    extracted_names = [r.name.lower() for r in response.requirements]

    assert any("claim form" in n for n in extracted_names)
    assert any("discharge" in n for n in extracted_names)

    # Strictly verify that unmentioned documents are NOT extracted
    forbidden_documents = [
        "fir",
        "medico-legal",
        "pan card",
        "cancelled cheque",
        "toxicology",
        "alcohol",
        "organ donor",
        "operation theatre",
        "implant",
        "pre-authorization",
        "passport",
        "driving license",
        "birth certificate",
        "electricity bill",
    ]

    for forbidden in forbidden_documents:
        for name in extracted_names:
            assert forbidden not in name, f"Hallucinated document detected: '{name}' contains '{forbidden}'"


def test_hallucination_guard_direct_rejection():
    """Unit test: verify HallucinationGuard explicitly drops fabricated requirements."""
    pages = [PageText(page_number=1, text="Hospitalization requires Discharge Summary and Final Bill.")]

    fake_item = RequirementItem(
        requirement_id="REQ-999",
        category=Category.DOCUMENT,
        name="International Passport Copy",
        description="Notarized copy of passport.",
        mandatory=True,
        priority=Priority.HIGH,
    )

    real_item = RequirementItem(
        requirement_id="REQ-001",
        category=Category.DOCUMENT,
        name="Hospital Discharge Summary",
        description="Discharge summary from hospital.",
        mandatory=True,
        priority=Priority.HIGH,
    )

    filtered = HallucinationGuard.filter_hallucinations([fake_item, real_item], pages)

    assert len(filtered) == 1
    assert filtered[0].name == "Hospital Discharge Summary"
