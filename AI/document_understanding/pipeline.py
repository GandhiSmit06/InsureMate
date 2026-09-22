"""
Master Document Understanding Pipeline.
Orchestrates Phase 1 input adaptation, normalization, section detection,
table parsing, key-value extraction, entity recognition, document type hinting,
and quality evaluation.
"""

from typing import Union, Dict, Any, List
from .schemas.input_schema import IngestedDocument
from .schemas.output_schema import (
    DocumentUnderstandingResult,
    DocumentMetadata,
    PageUnderstanding,
)
from .adapters.phase1_adapter import Phase1InputAdapter
from .extraction.section_detector import SectionDetector
from .extraction.key_value_extractor import KeyValueExtractor
from .extraction.table_extractor import TableExtractor
from .extraction.medical_entity_extractor import MedicalEntityExtractor
from .classification.doc_type_hints import DocumentTypeHintEngine
from .quality.quality_checker import DocumentQualityChecker
from .normalization.text_normalizer import calculate_unreadable_char_ratio
from .exceptions import DocumentUnderstandingError


class DocumentUnderstandingPipeline:
    """
    Executes end-to-end document understanding on ingested documents
    to produce structured Schema v1.0 results for Phase 3.
    """

    def __init__(self):
        self.adapter = Phase1InputAdapter()

    def process(self, raw_input: Union[IngestedDocument, Dict[str, Any], str]) -> DocumentUnderstandingResult:
        """
        Executes the full understanding pipeline.

        Args:
            raw_input: IngestedDocument model, dictionary, or JSON string.

        Returns:
            DocumentUnderstandingResult containing structured tables, sections,
            entities, type hints, quality report, and provenance.
        """
        # Step 1: Adapt and validate Phase 1 input
        ingested_doc = self.adapter.adapt(raw_input)

        doc_id = ingested_doc.document_id

        # Step 2: Handle edge case of blank/empty document
        if not ingested_doc.pages or all(not p.raw_text.strip() for p in ingested_doc.pages):
            return self._build_empty_document_result(ingested_doc)

        # Step 3: Extract sections
        sections = SectionDetector.detect_sections(doc_id, ingested_doc.pages)

        # Step 4: Extract key-value pairs
        key_values = KeyValueExtractor.extract_key_values(doc_id, ingested_doc.pages)

        # Step 5: Extract tables and itemized charges
        tables, itemized_charges = TableExtractor.extract_tables(doc_id, ingested_doc.pages)

        # Step 6: Extract medical, administrative, and financial entities
        entities = MedicalEntityExtractor.extract_entities(
            doc_id, ingested_doc.pages, key_values, sections, itemized_charges
        )

        # Step 7: Propose explainable document type hints
        type_hints = DocumentTypeHintEngine.generate_hints(
            ingested_doc.pages, sections, key_values, tables
        )

        # Step 8: Build page-level understanding summaries
        pages_understanding: List[PageUnderstanding] = []
        for page in ingested_doc.pages:
            pg_kv_count = sum(1 for kv in key_values if kv.provenance and kv.provenance.page_number == page.page_number)
            pg_tbl_count = sum(1 for tbl in tables if tbl.page_number == page.page_number)
            unreadable_ratio = calculate_unreadable_char_ratio(page.raw_text)

            pages_understanding.append(PageUnderstanding(
                page_number=page.page_number,
                extracted_text=page.raw_text,
                is_scanned=page.is_scanned,
                unreadable_char_ratio=unreadable_ratio,
                tables_count=pg_tbl_count,
                key_values_count=pg_kv_count,
            ))

        # Step 9: Evaluate quality, arithmetic reconciliation, and issue reporting
        quality_report, issues = DocumentQualityChecker.evaluate_quality(
            ingested_doc, pages_understanding, entities, type_hints
        )

        # Step 10: Determine overall status
        status = "completed"
        if quality_report.overall_quality == "unreadable":
            status = "partial"
        elif any(i.severity == "error" for i in issues):
            status = "partial"

        # Step 11: Build document metadata
        metadata = DocumentMetadata(
            source_type=ingested_doc.source_type,
            page_count=ingested_doc.page_count,
            detected_language="en",  # Can be extended to multi-language detection
            is_scanned=quality_report.is_scanned_or_image_based,
            filename=ingested_doc.filename,
        )

        return DocumentUnderstandingResult(
            schema_version="1.0",
            document_id=doc_id,
            status=status,
            document_metadata=metadata,
            document_type_hints=type_hints,
            pages=pages_understanding,
            sections=sections,
            tables=tables,
            key_value_fields=key_values,
            entities=entities,
            quality=quality_report,
            issues=issues,
        )

    @staticmethod
    def _build_empty_document_result(ingested_doc: IngestedDocument) -> DocumentUnderstandingResult:
        """Handles completely empty or blank documents gracefully."""
        from .schemas.output_schema import (
            DocumentQualityReport,
            ExtractedEntities,
            DocumentTypeHint,
            QualityIssue,
        )
        from .schemas.common import ConfidenceLevel

        metadata = DocumentMetadata(
            source_type=ingested_doc.source_type,
            page_count=ingested_doc.page_count,
            detected_language="unknown",
            is_scanned=any(p.is_scanned for p in ingested_doc.pages),
            filename=ingested_doc.filename,
        )

        issues = [
            QualityIssue(
                code="EMPTY_DOCUMENT",
                severity="error",
                description="Document contains no readable text or pages.",
            )
        ]

        quality = DocumentQualityReport(
            overall_quality="unreadable",
            unreadable_char_ratio=1.0 if not ingested_doc.pages else 0.0,
            is_scanned_or_image_based=metadata.is_scanned,
            missing_critical_fields=["all"],
        )

        type_hints = [
            DocumentTypeHint(
                candidate_type="unknown",
                confidence=ConfidenceLevel.LOW,
                confidence_score=0.0,
                supporting_signals=["Document is empty"],
            )
        ]

        return DocumentUnderstandingResult(
            schema_version="1.0",
            document_id=ingested_doc.document_id,
            status="failed",
            document_metadata=metadata,
            document_type_hints=type_hints,
            pages=[],
            sections=[],
            tables=[],
            key_value_fields=[],
            entities=ExtractedEntities(),
            quality=quality,
            issues=issues,
        )
