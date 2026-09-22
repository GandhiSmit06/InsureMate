import re
import logging
from typing import List, Dict, Tuple
from ..schema.models import RequirementItem, Priority

logger = logging.getLogger("insuremate.requirement_extraction.deduplicator")


class RequirementDeduplicator:
    """Deduplicates and merges similar requirement items.
    Consolidates required_information fields, preserves highest priority,
    and assigns clean sequential IDs (REQ-001, REQ-002, ...).
    """

    PRIORITY_WEIGHT = {
        Priority.HIGH: 3,
        Priority.MEDIUM: 2,
        Priority.LOW: 1,
    }

    @classmethod
    def deduplicate(cls, items: List[RequirementItem]) -> List[RequirementItem]:
        """Merge duplicate/similar requirements and re-index requirement IDs."""
        if not items:
            return []

        merged_dict: Dict[str, RequirementItem] = {}

        for item in items:
            key = cls._make_dedup_key(item)

            if key not in merged_dict:
                # Add a clone
                merged_dict[key] = item.model_copy(deep=True)
            else:
                existing = merged_dict[key]
                cls._merge_into(existing, item)

        # Convert back to list and assign clean sequential requirement_ids
        deduped_items = list(merged_dict.values())
        for idx, req in enumerate(deduped_items, start=1):
            req.requirement_id = f"REQ-{idx:03d}"

        return deduped_items

    @classmethod
    def _make_dedup_key(cls, item: RequirementItem) -> str:
        """Generate deduplication fingerprint from category and simplified name."""
        # Normalize name into core keywords
        norm_name = re.sub(r"[^a-zA-Z0-9]+", " ", item.name.lower()).strip()
        words = sorted(list(set(norm_name.split())))
        core_name = "_".join(words[:4])
        return f"{item.category.value}::{core_name}"

    @classmethod
    def _merge_into(cls, target: RequirementItem, source: RequirementItem):
        """Merge attributes of source into target."""
        # 1. Merge required_information
        combined_info = list(target.required_information)
        seen = set(combined_info)
        for field in source.required_information:
            if field not in seen:
                seen.add(field)
                combined_info.append(field)
        target.required_information = combined_info

        # 2. Retain higher priority
        target_weight = cls.PRIORITY_WEIGHT.get(target.priority, 1)
        source_weight = cls.PRIORITY_WEIGHT.get(source.priority, 1)
        if source_weight > target_weight:
            target.priority = source.priority

        # 3. Prefer longer/more descriptive description
        if len(source.description) > len(target.description):
            target.description = source.description

        # 4. Preserve deadline if target lacks it
        if not target.deadline and source.deadline:
            target.deadline = source.deadline

        # 5. Preserve condition if target lacks it
        if not target.condition and source.condition:
            target.condition = source.condition
            target.mandatory = False

        # 6. Preserve source_page if target has none
        if target.source_page is None and source.source_page is not None:
            target.source_page = source.source_page

        # 7. Preserve source_clause if target has none
        if not target.source_clause and source.source_clause:
            target.source_clause = source.source_clause
