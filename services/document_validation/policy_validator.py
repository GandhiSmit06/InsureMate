"""services/document_validation/policy_validator.py
Intelligent Content-Based Insurance Policy Document Validator & Semantic Classifier.

Evaluates documents intended for the insurance policy slot:
- Validates binary PDF structure (magic bytes, page tree, encryption, readability).
- Extracts embedded digital text or applies native OCR for scanned documents.
- Performs semantic structural classification to distinguish genuine insurance policies
  (contracts, policy schedules, certificates of insurance, policy wordings) from medical
  records (discharge summaries, admission records), bills/invoices, lab reports,
  unrelated contracts (employment, lease), and blank/corrupted files.
- Operates strictly on document content, not filenames or arbitrary heuristic scores.
"""

from dataclasses import dataclass, field
import io
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple

import pypdfium2

from services.qwen_vl.pdf_processor import extract_ocr_from_pil
from utils.logger import logger


@dataclass
class PolicyValidationResult:
    """Structured result returned by the Intelligent Document Classification Pipeline."""
    valid: bool
    document_type: str = "unknown"
    decision: str = "uncertain"  # "valid_policy" | "not_a_policy" | "uncertain"
    confidence: float = 0.0
    reason: str = ""
    error: Optional[str] = None
    signals_detected: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "document_type": self.document_type,
            "decision": self.decision,
            "confidence": self.confidence,
            "reason": self.reason,
            "error": self.error,
            "signals": self.signals_detected,
        }


# Semantic structural patterns distinguishing insurance policy contracts
POLICY_CONTRACT_INDICATORS = [
    # Document Nature / Schedule
    (r"\b(?:policy\s*schedule|schedule\s*of\s*insurance|certificate\s*of\s*insurance|policy\s*certificate|policy\s*wording|policy\s*contract|terms\s*and\s*conditions\s*of\s*insurance)\b", "contract_schedule_heading"),
    (r"\b(?:certified\s*policy|schedule\s*of\s*premium|insurance\s*product\s*information|proposer\s*and\s*policy\s*details|section\s*a[:\-]\s*policy\s*schedule)\b", "policy_section_heading"),
    # Core Underwriting & Coverage Provisions
    (r"\b(?:sum\s*insured|basic\s*sum\s*insured|coverage\s*limit|total\s*sum\s*insured|sum\s*assured)\b", "sum_insured_provision"),
    (r"\b(?:policy\s*period|period\s*of\s*insurance|policy\s*inception|policy\s*commencement|policy\s*expiry)\b", "coverage_period_provision"),
    (r"\b(?:gross\s*premium|net\s*premium|total\s*premium|premium\s*rate|annual\s*premium)\b", "premium_structure_provision"),
    (r"\b(?:proposer|policyholder|policy\s*holder)\b", "policyholder_role"),
    (r"\b(?:insured\s*persons?|insured\s*members?|covered\s*persons?|beneficiar(?:y|ies))\b", "insured_members_role"),
    (r"\b(?:deductible|cumulative\s*bonus|no\s*claim\s*bonus|co-?payment|nil\s*co-?payment)\b", "cost_sharing_terms"),
    (r"\b(?:waiting\s*period|statutory\s*waiting|pre-existing\s*diseases?\s*waiting)\b", "waiting_period_clause"),
    (r"\b(?:general\s*exclusions|policy\s*exclusions|non-indemnifiable\s*expenses)\b", "exclusions_clause"),
    (r"\b(?:claim\s*filing\s*requirements|mandatory\s*evidence|claim\s*submission\s*procedure)\b", "claims_procedure_clause"),
    (r"\b(?:underwritten\s*by|irda\s*registration|uin\s*[:\-]|stamp\s*duty|inpatient\s*benefit\s*plan|health\s*insurance\s*policy|travel\s*insurance\s*policy|motor\s*insurance\s*policy)\b", "underwriting_regulatory_mark"),
    (r"\b(?:health\s*insurance\s*provider|insurance\s*provider|general\s*insurance\s*services|policy\s*kit|health\s*cards?|mediclaim\s*insurance)\b", "insurance_service_indicators"),
    (r"\b(?:agent\s*name|agent\s*code|intermediary\s*name|broker\s*code|intermediary\s*code)\b", "insurance_intermediary_role"),
    (r"\b(?:policy\s*no[\s.:]|policy\s*number[\s.:]|certificate\s*no[\s.:]|certificate\s*number[\s.:])\b", "policy_number_present"),
]

# Semantic structural patterns distinguishing medical encounter records & hospital bills
CLINICAL_ENCOUNTER_INDICATORS = [
    (r"\b(?:discharge\s*summary|discharge\s*card|clinical\s*summary|indoor\s*admission|ipd\s*record|ipd\s*admission|uhid)\b", "clinical_admission_discharge"),
    (r"\b(?:chief\s*complaints|history\s*of\s*present\s*illness|clinical\s*findings|physical\s*examination|provisional\s*diagnosis|final\s*diagnosis)\b", "clinical_diagnosis_history"),
    (r"\b(?:treating\s*doctor|consulting\s*surgeon|attending\s*physician|operating\s*surgeon|anesthetist|consultant\s*pathologist)\b", "treating_physician_role"),
    (r"\b(?:operation\s*notes|surgical\s*record|procedure\s*performed|course\s*in\s*hospital|condition\s*at\s*discharge|treatment\s*given)\b", "surgical_hospital_notes"),
    (r"\b(?:prescription|rx\s*[:\-]|dosage|medication\s*advised|follow-?up\s*advice|tab\.|syr\.|inj\.)\b", "prescription_medication"),
]

MEDICAL_BILLING_INDICATORS = [
    (r"\b(?:inpatient\s*bill|inpatient\s*tax\s*invoice|final\s*hospital\s*bill|hospital\s*medical\s*bill|pharmacy\s*tax\s*invoice)\b", "hospital_tax_invoice"),
    (r"\b(?:official\s*settlement\s*&\s*payment\s*receipt|cash\s*counter\s*receipt|interim\s*bill|discharge\s*bill)\b", "cashier_settlement_receipt"),
    (r"\b(?:room\s*rent|boarding\s*charges|nursing\s*charges|icu\s*charges|ot\s*charges|investigation\s*charges|pharmacy\s*charges)\b", "itemized_hospital_charges"),
    (r"\b(?:total\s*bill\s*amount|net\s*payable|amount\s*received|balance\s*due|hospital\s*gstin|ipd\s*no)\b", "hospital_billing_totals"),
]

DIAGNOSTIC_REPORT_INDICATORS = [
    (r"\b(?:pathology\s*laboratory|radiology\s*ultrasound|diagnostic\s*scan|laboratory\s*investigation|blood\s*examination|biochemistry\s*report)\b", "lab_investigation_heading"),
    (r"\b(?:biological\s*reference\s*interval|observed\s*value|specimen|impression|radiologist\s*impression|histopathology)\b", "lab_test_findings"),
]

INCIDENT_REPORT_INDICATORS = [
    (r"\b(?:first\s*information\s*report|police\s*station|fir\s*no|theft\s*report|incident\s*documentation)\b", "police_incident_record"),
]

UNRELATED_CONTRACT_INDICATORS = [
    (r"\b(?:employment\s*agreement|employment\s*contract|job\s*description|employee\s*duties|salary\s*breakup|ctc\s*per\s*annum)\b", "employment_contract"),
    (r"\b(?:non-disclosure\s*agreement|confidentiality\s*agreement|nda\s*effective\s*date|receiving\s*party|disclosing\s*party)\b", "nda_agreement"),
    (r"\b(?:software\s*license\s*agreement|terms\s*of\s*service|end\s*user\s*license|lease\s*deed|tenancy\s*agreement|tenant|landlord)\b", "general_legal_contract"),
    (r"\b(?:curriculum\s*vitae|resume|work\s*experience|education\s*qualifications|technical\s*skills)\b", "resume_cv"),
]


def classify_document_content(text: str) -> Tuple[str, str, float, List[str], str]:
    """
    Perform content-based semantic document classification.

    Analyzes document text across structural, contractual, clinical, billing, and unrelated provisions.

    Returns:
        (predicted_document_type, decision, confidence, supporting_evidence, explanation)
    """
    text_lower = text.lower()

    policy_signals: List[str] = []
    clinical_signals: List[str] = []
    billing_signals: List[str] = []
    diagnostic_signals: List[str] = []
    incident_signals: List[str] = []
    unrelated_signals: List[str] = []

    for pattern, name in POLICY_CONTRACT_INDICATORS:
        if re.search(pattern, text_lower):
            policy_signals.append(name)

    for pattern, name in CLINICAL_ENCOUNTER_INDICATORS:
        if re.search(pattern, text_lower):
            clinical_signals.append(name)

    for pattern, name in MEDICAL_BILLING_INDICATORS:
        if re.search(pattern, text_lower):
            billing_signals.append(name)

    for pattern, name in DIAGNOSTIC_REPORT_INDICATORS:
        if re.search(pattern, text_lower):
            diagnostic_signals.append(name)

    for pattern, name in INCIDENT_REPORT_INDICATORS:
        if re.search(pattern, text_lower):
            incident_signals.append(name)

    for pattern, name in UNRELATED_CONTRACT_INDICATORS:
        if re.search(pattern, text_lower):
            unrelated_signals.append(name)

    # Policy number detection
    has_policy_number = bool(
        re.search(r"\b(?:policy\s*(?:number|no\.?|certificate\s*no\.?|num)|certificate\s*number)[\s:\-]+([0-9a-zA-Z/._'-]+)", text_lower)
    )
    if has_policy_number:
        policy_signals.append("policy_number_present")

    # Group medical signals
    total_medical_signals = clinical_signals + billing_signals + diagnostic_signals

    # Distinguish document types
    # 1. Unrelated non-insurance contract / resume
    if len(unrelated_signals) >= 2 and len(unrelated_signals) > len(policy_signals):
        return (
            "unrelated_document",
            "not_a_policy",
            0.92,
            unrelated_signals,
            "Document content represents a general non-insurance contract, agreement, or resume.",
        )

    # 2. Incident or Police record
    if len(incident_signals) >= 2 and len(incident_signals) > len(policy_signals):
        return (
            "incident_document",
            "not_a_policy",
            0.90,
            incident_signals,
            "Document content represents a police report or incident record.",
        )

    # 3. Medical Diagnostic Scan or Pathology Report
    if len(diagnostic_signals) >= 2 and len(diagnostic_signals) >= len(policy_signals):
        return (
            "medical_report",
            "not_a_policy",
            0.95,
            diagnostic_signals,
            "Document content represents a diagnostic, pathology, or radiology medical report.",
        )

    # 4. Medical Bill or Hospital Invoice
    if len(billing_signals) >= 2 and len(billing_signals) > len(policy_signals):
        return (
            "medical_bill",
            "not_a_policy",
            0.95,
            billing_signals,
            "Document content represents an itemized medical bill, hospital tax invoice, or receipt.",
        )

    # 5. Clinical Encounter / Hospital Indoor Admission / Discharge Record
    if len(clinical_signals) >= 2 and len(clinical_signals) > len(policy_signals):
        return (
            "hospital_document",
            "not_a_policy",
            0.95,
            clinical_signals,
            "Document content represents a clinical hospital encounter, admission record, or discharge summary.",
        )

    # If medical signals strongly dominate over policy signals
    if len(total_medical_signals) >= 3 and len(total_medical_signals) > (len(policy_signals) * 1.5):
        primary_med = (
            "medical_bill" if len(billing_signals) >= max(len(clinical_signals), len(diagnostic_signals))
            else ("medical_report" if len(diagnostic_signals) >= len(clinical_signals) else "hospital_document")
        )
        return (
            primary_med,
            "not_a_policy",
            0.92,
            total_medical_signals,
            "Document content represents a medical or hospital claim record, not an insurance policy.",
        )

    # 6. Valid Insurance Policy Contract / Schedule / Certificate
    # Required core pillars of an insurance policy contract:
    has_schedule_or_contract = any(
        s in policy_signals for s in ["contract_schedule_heading", "policy_section_heading", "underwriting_regulatory_mark", "insurance_service_indicators"]
    )
    has_coverage_or_premium = any(
        s in policy_signals for s in ["sum_insured_provision", "coverage_period_provision", "premium_structure_provision", "cost_sharing_terms"]
    )
    has_parties = any(
        s in policy_signals for s in ["policyholder_role", "insured_members_role", "policy_number_present", "insurance_intermediary_role"]
    )
    has_underwriting_terms = any(
        s in policy_signals for s in ["waiting_period_clause", "exclusions_clause", "claims_procedure_clause"]
    )

    core_pillars_count = sum([has_schedule_or_contract, has_coverage_or_premium, has_parties, has_underwriting_terms])

    if (
        (has_schedule_or_contract and (has_coverage_or_premium or has_parties or len(policy_signals) >= 2))
        or (core_pillars_count >= 2 and len(policy_signals) >= 2)
    ) and len(total_medical_signals) <= len(policy_signals):
        confidence = min(0.99, 0.70 + (core_pillars_count * 0.07) + (len(policy_signals) * 0.02))
        return (
            "insurance_policy",
            "valid_policy",
            round(confidence, 2),
            policy_signals,
            "Verified insurance policy contract with coverage schedule, underwriting terms, and insured parties.",
        )

    # If policy signals exist but insufficient to prove an active policy schedule/contract
    if len(policy_signals) >= 1:
        return (
            "uncertain_document",
            "uncertain",
            0.40,
            policy_signals,
            "Document contains isolated insurance terminology but lacks conclusive policy schedule or contract structure.",
        )

    # Default: Unrelated or unclassified document
    return (
        "unrelated_document",
        "not_a_policy",
        0.15,
        [],
        "Document does not exhibit structure or contractual terms of an insurance policy.",
    )


def validate_policy_pdf(
    content: bytes,
    filename: str = "",
    max_check_pages: int = 5,
    max_file_size: int = 25 * 1024 * 1024,
) -> PolicyValidationResult:
    """
    Intelligently validate an uploaded file for the insurance policy slot using
    content-based document classification and structural verification.

    Workflow:
    1. Validates actual PDF file structure (magic bytes, page tree, uncorrupted).
    2. Extracts digital text or applies OCR for scanned files across pages.
    3. Semantically classifies document content (policy contract vs hospital/claim/unrelated).
    4. Applies calibrated acceptance policy without defaulting to approval on failure.

    Args:
        content: Binary bytes of uploaded file.
        filename: Optional filename (used for logging only; NEVER for classification decisions).
        max_check_pages: Number of initial pages to inspect.
        max_file_size: Max allowed file size in bytes (default 25MB).

    Returns:
        PolicyValidationResult with validity decision, document type, and user-readable feedback.
    """
    # 1. Basic byte & size verification
    if not content or len(content) < 100:
        return PolicyValidationResult(
            valid=False,
            document_type="blank_or_unreadable",
            decision="not_a_policy",
            confidence=0.0,
            error="The uploaded file is empty or corrupted. Please upload a valid, readable insurance policy PDF.",
            reason="Zero or insufficient byte payload."
        )

    if len(content) > max_file_size:
        return PolicyValidationResult(
            valid=False,
            document_type="oversized_document",
            decision="not_a_policy",
            confidence=0.0,
            error="The uploaded file exceeds the 25 MB limit. Please upload a smaller insurance policy PDF.",
            reason=f"File size {len(content)} bytes exceeds {max_file_size} limit."
        )

    # 2. Magic byte check for PDF format
    if b"%PDF-" not in content[:1024]:
        return PolicyValidationResult(
            valid=False,
            document_type="unsupported_format",
            decision="not_a_policy",
            confidence=0.0,
            error="Invalid file format. The uploaded file is not a valid PDF document. Please upload a valid insurance policy PDF.",
            reason="PDF magic byte header (%PDF-) missing."
        )

    # 3. PDF Structural integrity & encryption check
    try:
        doc = pypdfium2.PdfDocument(content)
    except Exception as ex:
        err_msg = str(ex).lower()
        if "password" in err_msg or "encrypt" in err_msg:
            return PolicyValidationResult(
                valid=False,
                document_type="encrypted_pdf",
                decision="not_a_policy",
                confidence=0.0,
                error="The PDF is password protected or encrypted. Please upload an unencrypted insurance policy PDF.",
                reason="Document is password protected or encrypted."
            )
        return PolicyValidationResult(
            valid=False,
            document_type="corrupted_pdf",
            decision="not_a_policy",
            confidence=0.0,
            error="The PDF file appears to be corrupted or unreadable. Please upload a valid, readable copy.",
            reason=f"PDF parsing error: {ex}"
        )

    page_count = len(doc)
    if page_count == 0:
        return PolicyValidationResult(
            valid=False,
            document_type="blank_or_unreadable",
            decision="not_a_policy",
            confidence=0.0,
            error="The PDF contains no pages. Please upload a valid insurance policy PDF.",
            reason="PDF has 0 pages."
        )

    # 4. Text extraction across inspected pages (with OCR fallback for scans)
    pages_to_check = min(max_check_pages, page_count)
    combined_text = ""
    scanned_pages_ocred = 0

    for i in range(pages_to_check):
        try:
            page = doc[i]
            pt = page.get_textpage().get_text_range()
            if not pt or len(pt.strip()) < 15:
                # Page has insufficient digital text: invoke native OCR
                try:
                    img = page.render().to_pil()
                    ocr_t = extract_ocr_from_pil(img)
                    if ocr_t:
                        pt = ocr_t
                        scanned_pages_ocred += 1
                except Exception as ocr_ex:
                    logger.debug(f"[POLICY-VALIDATOR] OCR fallback page {i} error: {ocr_ex}")
            combined_text += " " + (pt or "")
        except Exception as page_ex:
            logger.debug(f"[POLICY-VALIDATOR] Error reading page {i}: {page_ex}")

    combined_text = combined_text.strip()
    if len(combined_text) < 30:
        return PolicyValidationResult(
            valid=False,
            document_type="blank_or_unreadable",
            decision="not_a_policy",
            confidence=0.0,
            error="The uploaded document appears to be blank or contains no readable text. Please upload a readable insurance policy PDF.",
            reason="Less than 30 characters of readable text extracted across inspected pages."
        )

    # 5. Semantic content classification
    doc_type, decision, confidence, signals, reason = classify_document_content(combined_text)

    logger.info(
        f"[POLICY-VALIDATOR] {filename or 'Document'} evaluation: "
        f"type='{doc_type}', decision='{decision}', confidence={confidence}, "
        f"signals={len(signals)}, ocred={scanned_pages_ocred}"
    )

    if decision == "valid_policy":
        return PolicyValidationResult(
            valid=True,
            document_type=doc_type,
            decision=decision,
            confidence=confidence,
            reason=reason,
            signals_detected=signals,
        )

    # If medical or hospital record uploaded to policy slot
    if doc_type in ("hospital_document", "medical_bill", "medical_report"):
        return PolicyValidationResult(
            valid=False,
            document_type=doc_type,
            decision=decision,
            confidence=confidence,
            error="This document does not appear to be an insurance policy. It appears to be a medical or hospital record. Please upload your insurance policy PDF.",
            reason=reason,
            signals_detected=signals,
        )

    # If uncertain or ambiguous
    if decision == "uncertain":
        return PolicyValidationResult(
            valid=False,
            document_type=doc_type,
            decision=decision,
            confidence=confidence,
            error="Unable to confirm this document is a valid insurance policy. Please upload a complete insurance policy schedule or contract PDF.",
            reason=reason,
            signals_detected=signals,
        )

    # Unrelated document
    return PolicyValidationResult(
        valid=False,
        document_type=doc_type,
        decision=decision,
        confidence=confidence,
        error="This document does not appear to be an insurance policy. Please upload your insurance policy PDF.",
        reason=reason,
        signals_detected=signals,
    )
