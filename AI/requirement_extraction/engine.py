import os
import logging
from typing import List, Optional, Union
from .schema.models import (
    PageText,
    RequirementItem,
    Phase3Response,
    ExtractionSummary,
)
from .ingestion.pdf_reader import PDFReader
from .extractor.hybrid_extractor import HybridExtractor
from .extractor.base import BaseExtractor
from .validator.hallucination_guard import HallucinationGuard
from .validator.schema_validator import SchemaValidator
from .normalizer.requirement_normalizer import RequirementNormalizer
from .deduplicator.requirement_deduplicator import RequirementDeduplicator

logger = logging.getLogger("insuremate.requirement_extraction.engine")


class RequirementExtractionEngine:
    """Core Orchestrator for Phase 3: Medical Insurance Requirement Extraction.
    Takes Policy PDF, Policy Text, or pre-extracted pages and produces strict, validated claim requirements.
    """

    def __init__(self, extractor: Optional[BaseExtractor] = None):
        self.extractor = extractor or HybridExtractor()

    def process(
        self,
        policy_text: Optional[str] = None,
        pdf_bytes: Optional[bytes] = None,
        claim_type: Optional[str] = None,
        policy_name: Optional[str] = None,
        pages: Optional[List[PageText]] = None,
        file_path: Optional[str] = None,
    ) -> Phase3Response:
        """Execute the end-to-end requirement extraction pipeline."""
        try:
            # 1. Ingestion: Extract PageText objects
            input_pages: List[PageText] = []
            if pages and len(pages) > 0:
                input_pages = pages
            elif pdf_bytes and len(pdf_bytes) > 0:
                logger.info(f"Ingesting PDF ({len(pdf_bytes)} bytes)...")
                input_pages = PDFReader.extract_from_bytes(pdf_bytes)
            elif file_path and os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    content = f.read()
                input_pages = PDFReader.extract_from_bytes(content)
            elif policy_text and policy_text.strip():
                logger.info("Ingesting raw policy text...")
                input_pages = PDFReader.extract_from_text(policy_text)
            else:
                return Phase3Response(
                    success=False,
                    claim_type=claim_type,
                    policy_name=policy_name,
                    error="No policy text, PDF file, or pages provided.",
                    requirements=[],
                )

            if not input_pages:
                return Phase3Response(
                    success=False,
                    claim_type=claim_type,
                    policy_name=policy_name,
                    error="Unable to extract any readable text from provided input.",
                    requirements=[],
                )

            # 2. Extract Raw Requirements
            raw_items = self.extractor.extract(input_pages, claim_type=claim_type)

            # 3. Anti-Hallucination Guardrail
            grounded_items = HallucinationGuard.filter_hallucinations(raw_items, input_pages)

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
