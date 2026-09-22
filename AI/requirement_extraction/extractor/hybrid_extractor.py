import logging
from typing import List, Optional
from ..schema.models import PageText, RequirementItem
from .base import BaseExtractor
from .rule_extractor import RuleExtractor
from .llm_extractor import LLMExtractor
from ..config import config

logger = logging.getLogger("insuremate.requirement_extraction.extractor.hybrid")


class HybridExtractor(BaseExtractor):
    """Hybrid orchestrator combining LLM and Rule extraction with automatic fallback."""

    def __init__(
        self,
        llm_extractor: Optional[LLMExtractor] = None,
        rule_extractor: Optional[RuleExtractor] = None,
    ):
        self.llm_extractor = llm_extractor or LLMExtractor()
        self.rule_extractor = rule_extractor or RuleExtractor()

    def extract(
        self,
        pages: List[PageText],
        claim_type: Optional[str] = None,
    ) -> List[RequirementItem]:
        """Extract requirements based on engine configuration and availability."""
        mode = config.ENGINE_MODE

        if mode == "rule_only":
            logger.info("Executing extraction using RuleExtractor (mode=rule_only).")
            return self.rule_extractor.extract(pages, claim_type)

        if mode == "llm_only":
            logger.info("Executing extraction using LLMExtractor (mode=llm_only).")
            return self.llm_extractor.extract(pages, claim_type)

        # Hybrid mode (default)
        if self.llm_extractor.is_available():
            try:
                logger.info("Attempting extraction with LLMExtractor...")
                items = self.llm_extractor.extract(pages, claim_type)
                if items:
                    logger.info(f"LLMExtractor successfully extracted {len(items)} requirements.")
                    return items
                logger.warning("LLMExtractor returned empty list, falling back to RuleExtractor.")
            except Exception as e:
                logger.warning(
                    f"LLMExtractor failed: {e}. Falling back to deterministic RuleExtractor."
                )

        logger.info("Executing extraction using RuleExtractor fallback.")
        return self.rule_extractor.extract(pages, claim_type)
