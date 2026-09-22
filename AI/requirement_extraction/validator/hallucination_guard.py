import re
import logging
from typing import List, Tuple
from ..schema.models import RequirementItem, PageText

logger = logging.getLogger("insuremate.requirement_extraction.validator.hallucination")


class HallucinationGuard:
    """Anti-hallucination guardrail that verifies extracted requirements are grounded in source text.
    Filters out any requirement where the primary entity or concept does not appear in the policy text.
    """

    STOPWORDS = {
        "and", "or", "the", "a", "an", "in", "of", "to", "for", "with",
        "on", "at", "by", "from", "up", "about", "into", "over", "after",
        "is", "are", "was", "were", "be", "been", "being", "have", "has",
        "had", "do", "does", "did", "claim", "claims", "required", "requirement",
        "hospital", "medical", "insurance", "policy", "documents", "document",
    }

    @classmethod
    def filter_hallucinations(
        cls,
        items: List[RequirementItem],
        pages: List[PageText],
    ) -> List[RequirementItem]:
        """Verify each requirement against the aggregated policy text and drop ungrounded ones."""
        full_text = " ".join(page.text for page in pages).lower()
        if not full_text.strip():
            return items

        grounded_items: List[RequirementItem] = []
        for item in items:
            if cls.is_grounded(item, full_text):
                grounded_items.append(item)
            else:
                logger.warning(
                    f"Hallucination Guard dropped ungrounded requirement: '{item.name}' "
                    f"(Category: {item.category.value}). Not found in policy text."
                )

        return grounded_items

    @classmethod
    def is_grounded(cls, item: RequirementItem, full_text_lower: str) -> bool:
        """Check if requirement has evidence in source text."""
        # Check source_clause first if available
        if item.source_clause:
            clean_clause = item.source_clause.strip().lower()
            if len(clean_clause) > 5 and clean_clause in full_text_lower:
                return True

        # Extract distinctive keywords from name
        name_tokens = cls._extract_key_tokens(item.name)
        if not name_tokens:
            return True

        # At least one major distinctive token must exist in the text
        matched_tokens = [tok for tok in name_tokens if tok in full_text_lower]

        # For single token, must match
        if len(name_tokens) == 1:
            return len(matched_tokens) >= 1

        # For multiple tokens, at least 1 or 50% must match
        return len(matched_tokens) >= 1

    @classmethod
    def _extract_key_tokens(cls, text: str) -> List[str]:
        """Extract alphanumeric key tokens excluding generic insurance stopwords."""
        words = re.findall(r"[a-zA-Z]{3,}", text.lower())
        return [w for w in words if w not in cls.STOPWORDS]
