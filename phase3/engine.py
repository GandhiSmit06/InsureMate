import logging
from typing import List, Optional, Union
from phase3.schema.models import (
    PageText,
    RequirementItem,
    Phase3Response,
    ExtractionSummary,
)
from phase3.ingestion.pdf_reader import PDFReader
from phase3.extractor.hybrid_extractor import HybridExtractor
from phase3.extractor.base import BaseExtractor
from phase3.validator.hallucination_guard import HallucinationGuard
from phase3.validator.schema_validator import SchemaValidator
from phase3.normalizer.requirement_normalizer import RequirementNormalizer
from phase3.deduplicator.requirement_deduplicator import RequirementDeduplicator

logger = logging.getLogger("phase3.engine")


class RequirementExtractionEngine:
    """Core Orchestrator for Phase 3: Medical Insurance Requirement Extraction.
    Takes Policy PDF or Policy Text and produces strict, validated claim requirements.
    """

    def __init__(self, extractor: Optional[BaseExtractor] = None):
        self.extractor = extractor or HybridExtractor()

    def process(
        self,
        policy_text: Optional[str] = None,
        pdf_bytes: Optional[bytes] = None,
        claim_type: Optional[str] = None,
        policy_name: Optional[str] = None,
    ) -> Phase3Response:
        """Execute the end-to-end requirement extraction pipeline."""
        try:
            # 1. Ingestion: Extract PageText objects
            pages: List[PageText] = []
            if pdf_bytes and len(pdf_bytes) > 0:
                logger.info(f"Ingesting PDF ({len(pdf_bytes)} bytes)...")
                pages = PDFReader.extract_from_bytes(pdf_bytes)
            elif policy_text and policy_text.strip():
                logger.info("Ingesting raw policy text...")
                pages = PDFReader.extract_from_text(policy_text)
            else:
                return Phase3Response(
                    success=False,
                    claim_type=claim_type,
                    policy_name=policy_name,
                    error="No policy text or PDF file provided.",
                    requirements=[],
                )

            if not pages:
                return Phase3Response(
                    success=False,
                    claim_type=claim_type,
                    policy_name=policy_name,
                    error="Unable to extract any readable text from provided input.",
                    requirements=[],
                )

            # 2. Extract Raw Requirements
            raw_items = self.extractor.extract(pages, claim_type=claim_type)

            # 3. Anti-Hallucination Guardrail
            grounded_items = HallucinationGuard.filter_hallucinations(raw_items, pages)

            # 4. Normalization
            normalized_items = RequirementNormalizer.normalize_list(grounded_items)

            # 5. Deduplication and sequential ID indexing
            deduped_items = RequirementDeduplicator.deduplicate(normalized_items)

            # 6. Schema Validation & Summary Computation
            validated_items, summary = SchemaValidator.validate_items(deduped_items)

            # 7. Assemble Strict Response
            return Phase3Response(
                success=True,
                claim_type=claim_type or "hospitalization",
                policy_name=policy_name,
                summary=summary,
                requirements=validated_items,
            )

        except Exception as e:
            logger.error(f"Error during requirement extraction: {e}", exc_info=True)
            return Phase3Response(
                success=False,
                claim_type=claim_type,
                policy_name=policy_name,
                error=f"Extraction failed: {str(e)}",
                requirements=[],
            )
