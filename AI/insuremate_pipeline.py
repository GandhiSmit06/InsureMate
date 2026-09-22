"""
InsureMate — Unified End-to-End Pipeline
Chains Phase 1 (Document Ingestion via PaddleOCR) with Phase 2 (Document Understanding)
to produce structured, provenance-tracked, quality-evaluated results from raw PDF files.

Usage:
    from AI.insuremate_pipeline import process_document

    result = process_document("path/to/insurance_claim.pdf")
    print(result.entities.patient.name.value)
    print(result.entities.financial.total_amount.value)
"""

import os
import uuid
from typing import Optional

from .documentIngestion.documentIngestor import ingest_document
from .document_understanding.pipeline import DocumentUnderstandingPipeline
from .document_understanding.schemas.input_schema import (
    IngestedDocument,
    RawPageInput,
    RawTableInput,
)
from .document_understanding.schemas.output_schema import DocumentUnderstandingResult


def _convert_phase1_to_phase2(phase1_result: dict, file_path: str) -> IngestedDocument:
    """
    Converts the Phase 1 ingest_document() dict output into a Phase 2 IngestedDocument model.

    Maps extraction methods ('digital' vs 'ocr'), OCR confidence scores,
    and page dimensions into the standardized schema contract.
    """
    doc_id = f"doc_{uuid.uuid4().hex[:12]}"
    filename = phase1_result.get("file_name", os.path.basename(file_path))

    pages = []
    for p in phase1_result.get("pages", []):
        is_scanned = p.get("method", "digital") == "ocr"
        ocr_conf = None
        if is_scanned:
            # Convert 0.0–1.0 confidence to percentage for Phase 2
            raw_conf = p.get("confidence", p.get("quality_score", None))
            if raw_conf is not None:
                ocr_conf = round(float(raw_conf) * 100, 2) if raw_conf <= 1.0 else round(float(raw_conf), 2)

        pages.append(RawPageInput(
            page_number=p.get("page_number", 1),
            raw_text=p.get("text", ""),
            is_scanned=is_scanned,
            ocr_confidence_avg=ocr_conf,
            width=p.get("width"),
            height=p.get("height"),
        ))

    # Determine source type
    summary = phase1_result.get("summary", {})
    digital_pages = summary.get("digital_pages", 0)
    ocr_pages = summary.get("ocr_pages", 0)

    if ocr_pages > 0 and digital_pages == 0:
        source_type = "scanned_pdf"
    elif ocr_pages > 0 and digital_pages > 0:
        source_type = "mixed_pdf"
    else:
        source_type = "pdf"

    # Collect ingestion warnings
    warnings = []
    for p in phase1_result.get("pages", []):
        if p.get("quality_score") is not None and p["quality_score"] < 0.5:
            warnings.append(f"Low OCR quality ({p['quality_score']*100:.0f}%) on page {p.get('page_number', '?')}")

    return IngestedDocument(
        document_id=doc_id,
        filename=filename,
        source_type=source_type,
        page_count=phase1_result.get("total_pages", len(pages)),
        pages=pages,
        metadata={
            "file_size_kb": phase1_result.get("file_size_kb", 0),
            "digital_pages": digital_pages,
            "ocr_pages": ocr_pages,
        },
        ingestion_warnings=warnings,
    )


def process_document(
    file_path: str,
    mode: str = "auto",
    max_pages: Optional[int] = None,
    start_page: int = 1,
    verbose: bool = True,
) -> DocumentUnderstandingResult:
    """
    End-to-end document processing pipeline: PDF → Ingestion → Understanding.

    Chains Phase 1 (PaddleOCR-powered document ingestion) with Phase 2
    (structured understanding, entity extraction, quality evaluation).

    Args:
        file_path: Path to the PDF file.
        mode: 'auto' (hybrid digital/OCR), 'digital' (force text extraction), 'ocr' (force PaddleOCR).
        max_pages: Maximum pages to process (None = all).
        start_page: 1-indexed starting page.
        verbose: Whether to print progress.

    Returns:
        DocumentUnderstandingResult with structured entities, sections, tables,
        key-value fields, quality report, and full provenance tracing.

    Raises:
        RuntimeError: If Phase 1 ingestion fails completely.
    """
    # Phase 1: Document Ingestion
    if verbose:
        print(f"\n{'='*70}")
        print(f" InsureMate - Processing: {os.path.basename(file_path)}")
        print(f"{'='*70}")

    phase1_result = ingest_document(
        file_path=file_path,
        mode=mode,
        max_pages=max_pages,
        start_page=start_page,
        verbose=verbose,
    )

    if not phase1_result.get("success", False):
        raise RuntimeError(
            f"Phase 1 ingestion failed: {phase1_result.get('error', 'Unknown error')}"
        )

    # Convert Phase 1 output to Phase 2 input schema
    ingested_doc = _convert_phase1_to_phase2(phase1_result, file_path)

    if verbose:
        print(f"\n[Pipeline] Phase 1 complete -> {ingested_doc.page_count} pages ingested ({ingested_doc.source_type})")
        print(f"[Pipeline] Starting Phase 2: Document Understanding...", flush=True)

    # Phase 2: Document Understanding
    pipeline = DocumentUnderstandingPipeline()
    result = pipeline.process(ingested_doc)

    if verbose:
        print(f"[Pipeline] Phase 2 complete -> Status: {result.status}")
        if result.document_type_hints:
            hint = result.document_type_hints[0]
            print(f"[Pipeline] Document Type: {hint.candidate_type} (confidence: {hint.confidence.value}, score: {hint.confidence_score})")
        print(f"[Pipeline] Quality: {result.quality.overall_quality}")
        if result.issues:
            print(f"[Pipeline] Issues ({len(result.issues)}):")
            for issue in result.issues:
                print(f"  [{issue.severity.upper()}] {issue.code}: {issue.description}")
        print(f"{'='*70}\n")

    return result
