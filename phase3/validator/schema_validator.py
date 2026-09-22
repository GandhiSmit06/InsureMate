import logging
from typing import List, Tuple
from phase3.schema.models import (
    RequirementItem,
    Category,
    Priority,
    ExtractionSummary,
)

logger = logging.getLogger("phase3.validator.schema")


class SchemaValidator:
    """Validates requirements against strict Phase 3 JSON schema constraints."""

    ALLOWED_CATEGORIES = {c.value for c in Category}
    ALLOWED_PRIORITIES = {p.value for p in Priority}

    @classmethod
    def validate_items(
        cls, items: List[RequirementItem]
    ) -> Tuple[List[RequirementItem], ExtractionSummary]:
        """Validate a list of RequirementItems and produce an ExtractionSummary.

        Raises:
            ValueError: If a requirement fails strict structural constraints.
        """
        valid_items: List[RequirementItem] = []
        mandatory_count = 0
        conditional_count = 0
        category_counts = {cat: 0 for cat in cls.ALLOWED_CATEGORIES}

        for idx, item in enumerate(items, start=1):
            # 1. Validate Category
            if item.category.value not in cls.ALLOWED_CATEGORIES:
                raise ValueError(
                    f"Requirement at index {idx} has invalid category: '{item.category}'. "
                    f"Allowed: {cls.ALLOWED_CATEGORIES}"
                )

            # 2. Validate Priority
            if item.priority.value not in cls.ALLOWED_PRIORITIES:
                raise ValueError(
                    f"Requirement at index {idx} has invalid priority: '{item.priority}'. "
                    f"Allowed: {cls.ALLOWED_PRIORITIES}"
                )

            # 3. Validate requirement_id
            if not item.requirement_id or not item.requirement_id.startswith("REQ-"):
                # Normalize if invalid
                item.requirement_id = f"REQ-{idx:03d}"

            # 4. Validate name and description
            if not item.name or not item.name.strip():
                raise ValueError(f"Requirement at index {idx} has empty name.")
            if not item.description or not item.description.strip():
                raise ValueError(f"Requirement at index {idx} has empty description.")

            # 5. Check mandatory vs conditional coherence
            if item.condition and item.mandatory:
                logger.warning(
                    f"Requirement '{item.name}' has condition '{item.condition}' but was marked mandatory. "
                    "Auto-adjusting mandatory to False."
                )
                item.mandatory = False

            if item.mandatory:
                mandatory_count += 1
            else:
                conditional_count += 1

            category_counts[item.category.value] = (
                category_counts.get(item.category.value, 0) + 1
            )
            valid_items.append(item)

        summary = ExtractionSummary(
            total_requirements=len(valid_items),
            mandatory_count=mandatory_count,
            conditional_count=conditional_count,
            categories=category_counts,
        )

        return valid_items, summary
