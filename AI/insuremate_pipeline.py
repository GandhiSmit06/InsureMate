"""
InsureMate — Unified End-to-End Pipeline
Chains Phase 1 (Document Ingestion via PaddleOCR), Phase 2 (Document Understanding),
and Phase 3 (Medical Insurance Requirement Extraction & Compliance Verification)
to produce structured, provenance-tracked, policy-compliant results from raw PDF files.

Usage:
    from AI.insuremate_pipeline import process_document

    result = process_document("path/to/insurance_claim.pdf")
    print(result.entities.patient.name.value)
    print(result.entities.financial.total_amount.value)

    # Access Phase 3 requirements & compliance
    if result.phase3:
        print(f"Total Requirements: {len(result.phase3.requirements)}")
    if result.compliance:
        print(f"Compliance Score: {result.compliance['compliance_score_pct']}%")
"""

import os
import uuid
from typing import Optional, List, Dict, Any

from .documentIngestion.documentIngestor import ingest_document
from .document_understanding.pipeline import DocumentUnderstandingPipeline
from .document_understanding.schemas.input_schema import (
    IngestedDocument,
    RawPageInput,
)
from .document_understanding.schemas.output_schema import DocumentUnderstandingResult
from .requirement_extraction.engine import RequirementExtractionEngine
from .requirement_extraction.schema.models import (
    PageText,
    Phase3Response,
    Category,
)


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


def _convert_to_phase3_pages(pages_input) -> List[PageText]:
    """Convert Phase 1 or Phase 2 page representations into Phase 3 PageText objects."""
    result = []
    for p in pages_input:
        if isinstance(p, dict):
            p_num = p.get("page_number", 1)
            text = p.get("text", "")
        else:
            p_num = getattr(p, "page_number", 1)
            text = getattr(p, "raw_text", getattr(p, "extracted_text", ""))
        result.append(PageText(page_number=p_num, text=text))
    return result


def verify_claim_compliance(
    phase2_result: DocumentUnderstandingResult,
    requirements: Phase3Response,
) -> dict:
    """
    Evaluates whether the extracted claim documentation and entities from Phase 2
    satisfy the insurance requirements extracted in Phase 3.
    """
    checklist = []
    fulfilled_count = 0
    missing_mandatory = 0
    conditional_count = 0

    entities = phase2_result.entities
    doc_types = [h.candidate_type.lower() for h in phase2_result.document_type_hints]

    for req in requirements.requirements:
        item_status = "MISSING"
        evidence = None
        req_name_lower = req.name.lower()
        cat = req.category

        if cat == Category.DOCUMENT:
            if "discharge" in req_name_lower and any("discharge" in dt for dt in doc_types):
                item_status = "FULFILLED"
                evidence = "Discharge Summary detected in claim package"
            elif ("bill" in req_name_lower or "invoice" in req_name_lower) and any("invoice" in dt or "bill" in dt for dt in doc_types):
                item_status = "FULFILLED"
                evidence = "Hospital Invoice / Final Bill detected"
            elif "prescription" in req_name_lower and any("prescription" in dt for dt in doc_types):
                item_status = "FULFILLED"
                evidence = "Prescription detected"
            elif "diagnostic" in req_name_lower and any("diagnostic" in dt for dt in doc_types):
                item_status = "FULFILLED"
                evidence = "Diagnostic / Investigation report detected"
            elif "claim form" in req_name_lower and any("insurance_form" in dt or "claim_form" in dt for dt in doc_types):
                item_status = "FULFILLED"
                evidence = "Insurance Claim Form detected"
            elif not req.mandatory:
                item_status = "CONDITIONAL"
                evidence = f"Conditional document: {req.condition or 'conditional upon specific treatments'}"

        elif cat == Category.INFORMATION:
            if "patient" in req_name_lower:
                if entities.patient.name.status.value == "extracted":
                    item_status = "FULFILLED"
                    evidence = f"Patient Name: {entities.patient.name.value}"
            elif "date" in req_name_lower or "admission" in req_name_lower or "discharge" in req_name_lower:
                adm = entities.encounter.admission_date.value
                dis = entities.encounter.discharge_date.value
                if adm or dis:
                    item_status = "FULFILLED"
                    evidence = f"Admission: {adm or 'N/A'}, Discharge: {dis or 'N/A'}"
            elif "diagnosis" in req_name_lower or "disease" in req_name_lower:
                if entities.encounter.diagnosis_text.status.value == "extracted":
                    item_status = "FULFILLED"
                    evidence = f"Diagnosis: {entities.encounter.diagnosis_text.value}"
            elif "doctor" in req_name_lower or "physician" in req_name_lower:
                if entities.encounter.attending_physician.status.value == "extracted":
                    item_status = "FULFILLED"
                    evidence = f"Doctor: {entities.encounter.attending_physician.value}"
            elif "hospital" in req_name_lower:
                if entities.hospital.name.status.value == "extracted":
                    item_status = "FULFILLED"
                    evidence = f"Hospital: {entities.hospital.name.value}"

        elif cat == Category.FINANCIAL:
            if entities.financial.total_amount.status.value == "extracted":
                item_status = "FULFILLED"
                curr = entities.financial.currency.value or "INR"
                evidence = f"Total Claimed Amount: {entities.financial.total_amount.value} {curr}"

        elif cat in (Category.CONDITION, Category.DEADLINE, Category.ACTION):
            if req.condition or not req.mandatory:
                item_status = "CONDITIONAL"
                evidence = req.condition or req.deadline or "Requires verification against policy clause"
            else:
                item_status = "PENDING_REVIEW"
                evidence = req.description

        if item_status == "FULFILLED":
            fulfilled_count += 1
        elif item_status == "CONDITIONAL":
            conditional_count += 1
        elif req.mandatory:
            missing_mandatory += 1

        checklist.append({
            "requirement_id": req.requirement_id,
            "category": req.category.value,
            "name": req.name,
            "mandatory": req.mandatory,
            "priority": req.priority.value,
            "status": item_status,
            "evidence": evidence,
            "deadline": req.deadline,
        })

    total = len(requirements.requirements)
    non_cond = max(1, total - conditional_count)
    score_pct = round((fulfilled_count / non_cond) * 100, 1) if non_cond > 0 else 100.0

    return {
        "total_requirements": total,
        "fulfilled_count": fulfilled_count,
        "missing_mandatory": missing_mandatory,
        "conditional_count": conditional_count,
        "compliance_score_pct": min(100.0, score_pct),
        "checklist": checklist,
    }


class InsureMatePipelineResult:
    """
    Master unified pipeline result spanning Phase 1, Phase 2, and Phase 3.
    Delegates attribute access to Phase 2 DocumentUnderstandingResult for backward compatibility.
    """

    def __init__(
        self,
        phase1: dict,
        phase2: DocumentUnderstandingResult,
        phase3: Optional[Phase3Response] = None,
        compliance: Optional[dict] = None,
    ):
        self.phase1 = phase1
        self.phase2 = phase2
        self.phase3 = phase3
        self.compliance = compliance

    def __getattr__(self, name: str):
        # Transparently delegate attributes to Phase 2 result (e.g. entities, quality, status)
        return getattr(self.phase2, name)

    def to_dict(self) -> dict:
        """Serialize full 3-phase pipeline result into a unified JSON-compatible dict."""
        out = {
            "phase1_ingestion": self.phase1,
            "phase2_understanding": self.phase2.model_dump(),
        }
        if self.phase3:
            out["phase3_requirements"] = self.phase3.model_dump()
        if self.compliance:
            out["compliance_evaluation"] = self.compliance
        return out


def process_document(
    file_path: str,
    mode: str = "auto",
    max_pages: Optional[int] = None,
    start_page: int = 1,
    verbose: bool = True,
    extract_requirements: bool = True,
    policy_file: Optional[str] = None,
    policy_text: Optional[str] = None,
    claim_type: Optional[str] = "hospitalization",
) -> InsureMatePipelineResult:
    """
    End-to-end 3-Phase document processing pipeline:
    PDF → Phase 1 Ingestion → Phase 2 Understanding → Phase 3 Requirement Extraction & Compliance.

    Args:
        file_path: Path to the primary claim or policy PDF file.
        mode: 'auto' (hybrid digital/OCR), 'digital' (force text extraction), 'ocr' (force PaddleOCR).
        max_pages: Maximum pages to process (None = all).
        start_page: 1-indexed starting page.
        verbose: Whether to print progress.
        extract_requirements: If True, executes Phase 3 requirement extraction.
        policy_file: Optional separate policy document PDF against which to verify the claim.
        policy_text: Optional separate policy text string against which to verify the claim.
        claim_type: Context for requirements ('hospitalization', 'cashless', 'reimbursement', 'accident').

    Returns:
        InsureMatePipelineResult with phase1, phase2, phase3, and compliance evaluation.
    """
    # -------------------------------------------------------------------------
    # Phase 1: Document Ingestion & OCR
    # -------------------------------------------------------------------------
    if verbose:
        print(f"\n{'='*70}")
        print(f" InsureMate Unified Pipeline — Processing: {os.path.basename(file_path)}")
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

    # -------------------------------------------------------------------------
    # Phase 2: Document Understanding & Structuring
    # -------------------------------------------------------------------------
    ingested_doc = _convert_phase1_to_phase2(phase1_result, file_path)

    if verbose:
        print(f"\n[Pipeline] Phase 1 complete -> {ingested_doc.page_count} pages ingested ({ingested_doc.source_type})")
        print(f"[Pipeline] Starting Phase 2: Document Understanding...", flush=True)

    pipeline = DocumentUnderstandingPipeline()
    phase2_result = pipeline.process(ingested_doc)

    if verbose:
        print(f"[Pipeline] Phase 2 complete -> Status: {phase2_result.status.upper()}")
        if phase2_result.document_type_hints:
            hint = phase2_result.document_type_hints[0]
            print(f"[Pipeline] Document Type: {hint.candidate_type} (confidence: {hint.confidence.value}, score: {hint.confidence_score})")
        print(f"[Pipeline] Quality: {phase2_result.quality.overall_quality}")

    # -------------------------------------------------------------------------
    # Phase 3: Requirement Extraction & Compliance Adjudication
    # -------------------------------------------------------------------------
    phase3_result = None
    compliance_eval = None

    if extract_requirements:
        if verbose:
            print(f"[Pipeline] Starting Phase 3: Requirement Extraction & Compliance...", flush=True)

        engine = RequirementExtractionEngine()

        if policy_file and os.path.exists(policy_file):
            # Extract requirements from explicitly provided policy document
            phase3_result = engine.process(file_path=policy_file, claim_type=claim_type)
        elif policy_text and policy_text.strip():
            # Extract requirements from explicitly provided policy text
            phase3_result = engine.process(policy_text=policy_text, claim_type=claim_type)
        else:
            # Extract requirements directly from the ingested document pages
            p3_pages = _convert_to_phase3_pages(ingested_doc.pages)
            phase3_result = engine.process(pages=p3_pages, claim_type=claim_type)

        if phase3_result and phase3_result.success and phase3_result.requirements:
            compliance_eval = verify_claim_compliance(phase2_result, phase3_result)
            if verbose:
                print(f"[Pipeline] Phase 3 complete -> Extracted {len(phase3_result.requirements)} requirements.")
                print(f"[Pipeline] Compliance Score: {compliance_eval['compliance_score_pct']}% "
                      f"({compliance_eval['fulfilled_count']} fulfilled, "
                      f"{compliance_eval['missing_mandatory']} missing mandatory, "
                      f"{compliance_eval['conditional_count']} conditional)")
        elif verbose:
            print(f"[Pipeline] Phase 3 complete -> No policy requirements extracted from input.")

    if verbose:
        print(f"{'='*70}\n")

    return InsureMatePipelineResult(
        phase1=phase1_result,
        phase2=phase2_result,
        phase3=phase3_result,
        compliance=compliance_eval,
    )
