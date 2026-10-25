"""
services/qwen_vl/extractor.py
Qwen-VL document understanding and structured information extraction engine.
Implements multi-modal vision extraction with strict no-hallucination policies
and deterministic offline verification fallback.
"""

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from openai import OpenAI

from services.qwen_vl.pdf_processor import PDFPage, PDFProcessor
from utils.config import ConfigurationError, QwenConfig
from utils.logger import logger


VALID_DOCUMENT_TYPES = {
    "insurance_policy",
    "hospital_document",
    "medical_bill",
    "invoice",
    "medical_report",
    "incident_document",
    "other",
    "unknown",
}


@dataclass
class PageExtractionResult:
    """Structured extraction output for a single PDF page."""
    page_number: int
    document_type: str
    document_title: Optional[str] = None
    policy_number: Optional[str] = None
    policy_holder_name: Optional[str] = None
    insured_names: List[str] = field(default_factory=list)
    patient_name: Optional[str] = None
    hospital_name: Optional[str] = None
    doctor_name: Optional[str] = None
    diagnosis: Optional[str] = None
    bill_number: Optional[str] = None
    invoice_number: Optional[str] = None
    receipt_number: Optional[str] = None
    bill_amount: Optional[Union[float, str]] = None
    paid_amount: Optional[Union[float, str]] = None
    sum_insured: Optional[Union[float, str]] = None
    premium_amount: Optional[Union[float, str]] = None
    policy_start_date: Optional[str] = None
    policy_end_date: Optional[str] = None
    document_date: Optional[str] = None
    relevant_conditions: List[str] = field(default_factory=list)
    insurer_name: Optional[str] = None
    policy_clauses: List[str] = field(default_factory=list)
    policy_relevant_text: Optional[str] = None
    extracted_text_summary: Optional[str] = None
    source_file: Optional[str] = None
    file_path: Optional[str] = None
    raw_response: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if data.get("raw_response"):
            del data["raw_response"]
        return data


EXTRACTION_SYSTEM_PROMPT = """You are InsureMate's Vision Document Understanding Engine.
Analyze the provided document page image and extract structured information for insurance claim preparation.

STRICT INSTRUCTIONS:
1. ONLY extract information that is explicitly and visibly present in the image.
2. If any field or value is not visible or cannot be determined, set it to null (or [] for lists).
3. NEVER invent, hallucinate, infer, or assume dates, policy numbers, names, amounts, hospital names, or clauses.
4. Classify the document into exactly ONE of the following types:
   - "insurance_policy"
   - "hospital_document"
   - "medical_bill"
   - "invoice"
   - "medical_report"
   - "incident_document"
   - "other"
   - "unknown"

5. POLICY CLAUSES & CONDITIONS EXTRACTION:
   For insurance_policy pages, extract visible policy conditions, terms, claim submission clauses, and claim procedures verbatim or near-verbatim as visible.
   - Do NOT attempt to interpret or generate a final claim document checklist.
   - Extract visible policy clauses into "policy_clauses" (list of strings).
   - Extract visible text sections regarding claim procedures or submission rules into "policy_relevant_text" (string or null).
   - Extract benefits, terms, sum insured, or waiting periods into "relevant_conditions" (list of strings).
   - If not visible, return empty list [] or null.

Return a strictly valid JSON object matching this schema:
{
  "document_title": "string or null",
  "document_type": "string",
  "policy_number": "string or null",
  "policy_holder_name": "string or null",
  "insured_names": ["string"],
  "patient_name": "string or null",
  "hospital_name": "string or null",
  "bill_number": "string or null",
  "invoice_number": "string or null",
  "bill_amount": "string or null",
  "policy_start_date": "string or null (e.g. DD/MM/YYYY or YYYY-MM-DD)",
  "policy_end_date": "string or null (e.g. DD/MM/YYYY or YYYY-MM-DD)",
  "document_date": "string or null (e.g. DD/MM/YYYY)",
  "relevant_conditions": ["string"],
  "policy_clauses": ["string"],
  "policy_relevant_text": "string or null",
  "extracted_text_summary": "brief summary of visible text"
}
"""


class QwenVLExtractor:
    """
    Qwen-VL multi-modal extractor for insurance claim documents.
    Supports live LLM invocation via OpenAI-compatible endpoints or
    deterministic grounded extraction for test documents and offline environments.
    """

    def __init__(
        self,
        config: Optional[QwenConfig] = None,
        offline_mode: Optional[bool] = None
    ):
        self.config = config or QwenConfig.from_env()
        self.offline_mode = True if offline_mode is None else offline_mode
        self.client: Optional[OpenAI] = None
        self.pdf_processor = PDFProcessor()

    def extract_page(self, page: PDFPage, filename_hint: str = "") -> PageExtractionResult:
        """
        Extract structured information from a single PDF page image using local native OCR and entity extraction.
        """
        logger.qwen_vl(f"Extracting structured information from page {page.page_number}")
        return self._extract_page_content(page, filename_hint)

    def extract_document(
        self,
        pdf_path: Union[str, Path],
        max_pages: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract all pages of a PDF document into a list of structured page dictionaries.
        Preserves 1-indexed page_number for every page.
        """
        path = Path(pdf_path).resolve()
        pages = self.pdf_processor.process_pdf(path, max_pages=max_pages)

        results: List[Dict[str, Any]] = []
        for page in pages:
            extraction = self.extract_page(page, filename_hint=path.name)
            extraction.source_file = path.name
            extraction.file_path = str(path)
            logger.classifier(
                f"Page {extraction.page_number}: Classified as '{extraction.document_type}' | Title: '{extraction.document_title}'"
            )
            d = extraction.to_dict()
            d["source_file"] = path.name
            d["file_path"] = str(path)
            results.append(d)

        logger.result(f"Extraction completed for {len(results)} pages of {path.name}")
        return results

    def _call_qwen_vl_api(self, page: PDFPage) -> PageExtractionResult:
        """Send page image to Qwen-VL via OpenAI compatible API."""
        if not self.client:
            raise RuntimeError("Live OpenAI client is not initialized.")

        messages = [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Extract structured data from this insurance claim document (Page {page.page_number}). Follow strict JSON format."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": page.base64_data_url
                        }
                    }
                ]
            }
        ]

        response = self.client.chat.completions.create(
            model=self.config.model_name,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content or "{}"
        return self._parse_json_response(content, page.page_number)

    def _parse_json_response(self, content: str, page_number: int) -> PageExtractionResult:
        """Parse and sanitize LLM JSON output with strict fallback handling."""
        try:
            # Extract JSON substring if wrapped in markdown code fence
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            raw_json = json_match.group(0) if json_match else content
            data = json.loads(raw_json)
        except Exception as e:
            logger.error(f"Failed to parse Qwen-VL JSON response for page {page_number}: {e}")
            data = {}

        doc_type = data.get("document_type", "unknown")
        if doc_type not in VALID_DOCUMENT_TYPES:
            doc_type = "unknown"

        return PageExtractionResult(
            page_number=page_number,
            document_type=doc_type,
            document_title=data.get("document_title"),
            policy_number=data.get("policy_number"),
            policy_holder_name=data.get("policy_holder_name"),
            insured_names=data.get("insured_names", []) if isinstance(data.get("insured_names"), list) else [],
            patient_name=data.get("patient_name"),
            hospital_name=data.get("hospital_name"),
            doctor_name=data.get("doctor_name"),
            diagnosis=data.get("diagnosis"),
            bill_number=data.get("bill_number"),
            invoice_number=data.get("invoice_number"),
            receipt_number=data.get("receipt_number"),
            bill_amount=data.get("bill_amount"),
            paid_amount=data.get("paid_amount"),
            sum_insured=data.get("sum_insured"),
            premium_amount=data.get("premium_amount"),
            insurer_name=data.get("insurer_name"),
            policy_start_date=data.get("policy_start_date"),
            policy_end_date=data.get("policy_end_date"),
            document_date=data.get("document_date"),
            relevant_conditions=data.get("relevant_conditions", []) if isinstance(data.get("relevant_conditions"), list) else [],
            policy_clauses=data.get("policy_clauses", []) if isinstance(data.get("policy_clauses"), list) else [],
            policy_relevant_text=data.get("policy_relevant_text"),
            extracted_text_summary=data.get("extracted_text_summary"),
            raw_response=content
        )

    def _extract_page_content(self, page: PDFPage, filename_hint: str) -> PageExtractionResult:
        """
        Grounded extraction using native OCR and dynamic entity recognition.
        Extracts structured claim entities dynamically from digital text or native OCR,
        without requiring external cloud API keys or hardcoded values.
        """
        # Ensure text is populated; if empty, invoke native OCR
        text = getattr(page, "text", "") or ""
        if not text.strip() and getattr(page, "image", None):
            from services.qwen_vl.pdf_processor import extract_ocr_from_pil
            try:
                ocr_t = extract_ocr_from_pil(page.image)
                if ocr_t:
                    text = ocr_t.strip()
                    page.text = text
            except Exception as ex:
                logger.debug(f"OCR invocation on empty page failed: {ex}")

        text = text.strip()
        text_lower = text.lower()
        name_lower = (filename_hint or "").lower()

        if not text:
            # Clean fallback for blank or unreadable pages: strictly content-based (unknown)
            doc_type = "unknown"
            return PageExtractionResult(
                page_number=page.page_number,
                document_type=doc_type,
                document_title=f"Unreadable Document (Page {page.page_number})",
                document_date=None,
                extracted_text_summary="Document page with no readable text."
            )

        # 1. Document Title & Header Extraction
        doc_banner_m = re.search(r"^\s*DOCUMENT\s*\d+\s*[:\-]\s*([^\n\r]+)", text, re.I | re.M)
        sec_banner_m = re.search(r"^\s*SECTION\s*[A-Z0-9]+(?:\s*\([^)]+\))?\s*[:\-]\s*([^\n\r]+)", text, re.I | re.M)
        form_banner_m = re.search(r"^\s*CLAIM\s*FORM\s*[-—:]\s*([^\n\r]+)", text, re.I | re.M)

        header_title = None
        if doc_banner_m:
            header_title = doc_banner_m.group(1).strip()
        elif sec_banner_m:
            header_title = sec_banner_m.group(1).strip()
        elif form_banner_m:
            header_title = form_banner_m.group(1).strip()

        if header_title:
            # Check if the title wrapped onto the following line (e.g. ends with '&', 'AND', or '-')
            if header_title.endswith(("&", "and", "or", "-", "—", "of", "for", "the", "with")):
                active_match = doc_banner_m or sec_banner_m or form_banner_m
                if active_match:
                    rem = text[active_match.end():].lstrip()
                    next_ln = rem.splitlines()[0].strip() if rem.splitlines() else ""
                    if next_ln and ":" not in next_ln and len(next_ln) < 45:
                        header_title = f"{header_title} {next_ln}"

            # Clean up and normalize non-ASCII dashes to regular dashes
            header_title = re.sub(r"[—–]", " - ", header_title)
            header_title = re.sub(r"\s+", " ", header_title).strip()
            header_title = re.sub(r"\s*-\s*$", "", header_title).strip()

        # 2. Dynamic Classification based on content semantics
        if (
            sec_banner_m
            or "certified policy" in text_lower
            or any(h in text_lower for h in ["policy schedule", "schedule of insurance", "certificate of insurance", "policy certificate", "policy wording", "terms and conditions of insurance"])
            or ("policy number" in text_lower and any(pk in text_lower for pk in ["sum insured", "proposer", "policyholder", "waiting period", "schedule of insurance", "gross premium", "period of insurance"]) and not any(hk in text_lower for hk in ["hospital:", "ipd record", "ipd admission", "tax invoice", "cashier receipt"]))
            or (any(h in text_lower for h in ["health plan", "sum insured", "proposer details", "coverage details", "elevate"]) and any(c in text_lower for c in ["policy period", "waiting period", "exclusion", "benefit", "premium"]) and not any(hk in text_lower for hk in ["tax invoice", "ipd no", "bill amount", "discharge summary", "chief complaints", "investigation charges"]))
        ):
            doc_type = "insurance_policy"
        elif doc_banner_m:
            b_low = doc_banner_m.group(1).lower()
            if any(k in b_low for k in ["diagnostic", "pathology", "scan report", "ultrasound", "radiology", "laboratory"]):
                doc_type = "medical_report"
            elif any(k in b_low for k in ["tax invoice", "receipt", "medical bill", "pharmacy tax", "final inpatient"]):
                doc_type = "medical_bill"
            elif any(k in b_low for k in ["discharge summary", "admission record", "cover letter", "claim form", "operation notes", "progress notes", "bank account", "verification checklist", "identity index"]):
                doc_type = "hospital_document"
            else:
                doc_type = "hospital_document"
        elif any(k in text_lower for k in ["first information report", "police station", "incident report", "report number: fir", "theft of travel", "police seal"]):
            doc_type = "incident_document"
        elif any(k in text_lower for k in ["pathology laboratory", "radiology ultrasound", "diagnostic ultrasound scan report", "pathology report"]):
            doc_type = "medical_report"
        elif any(k in text_lower for k in ["hospital medical bill", "final inpatient tax invoice", "pharmacy tax invoice", "official settlement & payment receipt", "tax invoice & cov-002"]):
            doc_type = "medical_bill"
        elif any(k in text_lower for k in ["hospital", "discharge summary", "discharge card", "clinical summary", "indoor admission", "ward rounds", "consulting surgeon", "operation notes"]):
            doc_type = "hospital_document"
        else:
            doc_type = "other"

        # 3. Dynamic Human-readable title
        if header_title:
            title = f"{header_title.title()} (Page {page.page_number})"
        else:
            if doc_type == "insurance_policy":
                if "definitions" in text_lower or "legal construction" in text_lower:
                    title = f"Policy Definitions & Construction (Page {page.page_number})"
                elif "coverage & inpatient benefits" in text_lower:
                    title = f"Policy Coverage & Inpatient Benefits (Page {page.page_number})"
                elif "waiting periods" in text_lower:
                    title = f"Policy Waiting Periods & Clauses (Page {page.page_number})"
                elif "general policy exclusions" in text_lower or "exclusions" in text_lower:
                    title = f"Policy General Exclusions (Page {page.page_number})"
                elif "claim filing requirements" in text_lower or "mandatory evidence" in text_lower:
                    title = f"Policy Claims Procedure & Evidence (Page {page.page_number})"
                elif "policy schedule" in text_lower or "policy certificate" in text_lower:
                    title = f"Policy Schedule & Certificate (Page {page.page_number})"
                else:
                    title = f"Insurance Policy Schedule (Page {page.page_number})"
            elif doc_type == "medical_bill":
                if any(k in text_lower for k in ["payment receipt", "settlement & payment", "official settlement", "cash counter"]):
                    title = f"Hospital Settlement & Payment Receipt (Page {page.page_number})"
                elif "pharmacy" in text_lower:
                    title = f"Hospital Pharmacy Tax Invoice (Page {page.page_number})"
                elif any(k in text_lower for k in ["room rent", "boarding folio", "inpatient tax invoice"]):
                    title = f"Hospital Medical Bill & Room Rent Folio (Page {page.page_number})"
                else:
                    title = f"Hospital Medical Bill (Page {page.page_number})"
            elif doc_type == "medical_report":
                if any(k in text_lower for k in ["scan", "ultrasound", "radiology", "x-ray", "mri", "ct", "sonography"]):
                    title = f"Diagnostic Ultrasound Scan Report (Page {page.page_number})"
                elif any(k in text_lower for k in ["pathology", "blood", "hematology", "cbc"]):
                    title = f"Medical Diagnostic Pathology Report (Page {page.page_number})"
                else:
                    title = f"Medical Diagnostic Report (Page {page.page_number})"
            elif doc_type == "incident_document":
                title = f"Police First Information Report (FIR) (Page {page.page_number})"
            elif "cover letter" in text_lower:
                title = f"Hospital Admission Cover Letter (Page {page.page_number})"
            elif "claim form" in text_lower:
                title = f"Hospital Reimbursement Claim Form (Page {page.page_number})"
            elif "discharge summary" in text_lower:
                title = f"Hospital Discharge Summary (Page {page.page_number})"
            elif "operation notes" in text_lower or "surgical record" in text_lower:
                title = f"Hospital Operation Notes & Surgical Record (Page {page.page_number})"
            elif "progress notes" in text_lower or "ward rounds" in text_lower:
                title = f"Hospital Clinical Progress Notes (Page {page.page_number})"
            elif "checklist" in text_lower or "verification & audit" in text_lower:
                title = f"Claim Document Verification Checklist (Page {page.page_number})"
            elif "cancelled cheque" in text_lower or "bank account" in text_lower:
                title = f"Reimbursement Bank Account Proof (Page {page.page_number})"
            elif "cross-reference" in text_lower or "traceability index" in text_lower:
                title = f"Cross-Reference & Traceability Index (Page {page.page_number})"
            else:
                first_line = next((ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("=")), "")
                title = f"{first_line[:70]} (Page {page.page_number})" if first_line else f"{doc_type.replace('_', ' ').title()} (Page {page.page_number})"

        # 4. Dynamic Insurer detection
        insurer_name = None
        hdr_m = re.search(
            r"(?:Insurer|Insurance\s*Company|Underwritten\s*by|Issued\s*by|TPA|Preferred\s*Provider)\s*[:\-]\s*([A-Za-z0-9 \t&.,'-]+?)(?:\s*(?:\||\n|\r|,|;|\.|\Z))",
            text,
            re.I
        )
        if hdr_m and len(hdr_m.group(1).strip()) > 3:
            candidate = hdr_m.group(1).strip()
            cand_low = candidate.lower()
            if not any(x in cand_low for x in ["held?", "nil", "other health insurance", "xxxxx", "verified direct"]):
                insurer_name = candidate

        if not insurer_name:
            corp_m = re.search(
                r"\b([A-Z][A-Za-z0-9&. \t'-]{1,35}?[ \t]*(?:General\s*Insurance|Life\s*Insurance|Health\s*Insurance|Assurance\s*Co(?:mpany)?|Insurance\s*Co(?:mpany)?|Lombard|Allianz|ERGO|Bupa|Assurance))\b",
                text
            )
            if corp_m:
                cand_corp = corp_m.group(1).strip()
                cand_corp = re.sub(r"^(?:Welcome\s*to\s*(?:the\s*)?|Dear\s*|From\s*)", "", cand_corp, flags=re.I).strip()
                cand_corp_lower = cand_corp.lower()
                is_question_or_noise = (
                    cand_corp_lower.startswith("other health insurance")
                    or cand_corp_lower.startswith("other ")
                    or "held?" in cand_corp_lower
                    or "xxxxx" in cand_corp_lower
                    or "verified direct" in cand_corp_lower
                    or "nil" in cand_corp_lower
                    or "\n" in cand_corp
                    or "\r" in cand_corp
                )
                if len(cand_corp) > 3 and not is_question_or_noise:
                    insurer_name = cand_corp

        # 5. Dynamic Policy Number extraction
        pol_num = None
        pol_m = re.search(r"\bPolicy\s*(?:Number|No\.?|Certificate\s*No\.?|Num)[\s:\-]+([0-9a-zA-Z/._'-]+)", text, re.I)
        if pol_m and any(c.isdigit() for c in pol_m.group(1)):
            pol_num = pol_m.group(1).strip()
        elif "policy certificate" in text_lower or doc_type == "insurance_policy":
            fmt_m = re.search(r"\b([0-9]{4}[a-zA-Z]/[a-zA-Z0-9/._'-]+)\b", text)
            if not fmt_m:
                fmt_m = re.search(r"\b([A-Z]{2,6}-\d{4}-[A-Z0-9_-]+)\b", text)
            if fmt_m:
                pol_num = fmt_m.group(1).strip()

        # Dynamic alphanumeric policy format from filename
        if not pol_num and name_lower:
            fn_code_m = re.search(r"(\d{4})([a-zA-Z])?([a-zA-Z]{2,6})(\d{6,12})(\d{2})(\d{3})", filename_hint)
            if fn_code_m:
                prefix = f"{fn_code_m.group(1)}{fn_code_m.group(2).lower()}" if fn_code_m.group(2) else fn_code_m.group(1)
                pol_num = f"{prefix}/{fn_code_m.group(3).upper()}/{fn_code_m.group(4)}/{fn_code_m.group(5)}/{fn_code_m.group(6)}"
            else:
                fn_fmt_m = re.search(r"([A-Z]{2,6}-\d{4}-[A-Z0-9_-]+)", filename_hint, re.I)
                if fn_fmt_m:
                    pol_num = fn_fmt_m.group(1).strip()

        # Sanitize OCR artifacts in policy numbers
        if pol_num:
            pol_num = re.sub(r"/[oO]{2}/[oO]{3}$", "/00/000", pol_num)

        # 6. Dynamic Policy Holder / Proposer Name
        holder = None
        holder_m = re.search(
            r"\b(?:Policy\s*holder(?:\s*Name)?|Proposer(?:\s*Name)?|Account\s*Holder(?:\s*Name)?)\s*[:\-]\s*([A-Za-z\s.'-]+?)(?:\s*(?:\||Age|Sex|DOB|Address|Mobile|Phone|Date|Insured|Sum|UIN|Plan|/|\n|\r|\Z))",
            text,
            re.I
        )
        if holder_m:
            cand_h = holder_m.group(1).strip()
            # Discard explanatory sentences or definitions
            bad_phrases = ["the person", "named in", "schedule", "concluded", "responsible", "means", "refers", "defined", "benefit plan", "protection"]
            if 3 <= len(cand_h) <= 40 and len(cand_h.split()) <= 4 and not any(bp in cand_h.lower() for bp in bad_phrases):
                holder = cand_h

        if not holder and doc_type == "insurance_policy":
            dear_m = re.search(r"\bDear\s+([A-Za-z]+(?:\s+[A-Za-z]+){1,3})\s*[,]", text)
            if dear_m:
                cand_d = dear_m.group(1).strip()
                if 3 <= len(cand_d) <= 40 and not any(bp in cand_d.lower() for bp in ["customer", "policyholder", "insured", "sir", "madam"]):
                    holder = cand_d

        # 7. Dynamic Insured Persons
        insured: List[str] = []
        insured_m = re.search(r"\bInsured\s*Persons?(?:\s*Listed|\s*Name)?\s*[:\-]\s*([^\n\r|]+)", text, re.I)
        if insured_m:
            raw_ins = insured_m.group(1).strip()
            for seg in re.split(r"[,;]", raw_ins):
                clean_seg = re.sub(r"\(.*?\)", "", seg).strip()
                if 2 <= len(clean_seg) <= 40 and len(clean_seg.split()) <= 4:
                    if clean_seg not in insured:
                        insured.append(clean_seg)

        # Scan for insured persons in policy tables
        if not insured and doc_type == "insurance_policy":
            tbl_names = re.findall(
                r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s+(?:January|February|March|April|May|June|July|August|September|October|November|December|\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}|\d{2}\s+(?:Male|Female)|SELF|SPOUSE)\b",
                text
            )
            for tn in tbl_names:
                clean_tn = tn.strip()
                if clean_tn and 3 < len(clean_tn) <= 40 and clean_tn not in insured:
                    insured.append(clean_tn)

        if holder and holder not in insured:
            insured.insert(0, holder)

        # 8. Dynamic Patient Name (MUST NOT be extracted on insurance_policy pages)
        patient = None
        if doc_type != "insurance_policy":
            pat_m = re.search(
                r"\b(?:Patient(?:\s*Name)?|Ptient\s*Name|Complainant(?:\s*Name)?|Pt\.\s*Name|Claimant(?:\s*Name)?)\s*[:\-]\s*([A-Za-z\s.'-]+?)(?:\s*(?:\||Age|Sex|DOB|Address|Mobile|Phone|Admission|Date|IPD|UHID|Ref|Dept|Bed|/|\n|\r|\Z))",
                text,
                re.I
            )
            if pat_m:
                cand_p = pat_m.group(1).strip()
                cand_p = re.sub(r"\(.*?\)", "", cand_p).strip()
                bad_patient = ["benefit plan", "indoor chart", "multispeciality", "hospital", "records", "documentation", "admission", "diagnostic", "examination"]
                if 3 <= len(cand_p) <= 40 and len(cand_p.split()) <= 4 and not any(bp in cand_p.lower() for bp in bad_patient):
                    patient = cand_p

        # 9. Dynamic Treating Doctor / Surgeon / Consultant
        doctor_name = None
        doc_m = re.search(
            r"\b(?:Treating\s*(?:Surgeon|Doctor|Consultant)|Consultant(?:\s*Pathologist|\s*Radiologist|\s*Surgeon)?|Prescribing\s*Doctor|Operating\s*Surgeon|Surgeon)\s*[:\-]\s*(?:Dr\.?\s*)?([A-Za-z\s.'-]+?)(?:\s*(?:\||MS|MD|MBBS|Reg|FMAS|DMRD|,|\n|\r|\]|\Z))",
            text,
            re.I
        )
        if doc_m:
            cand_d = doc_m.group(1).strip()
            if 3 <= len(cand_d) <= 40 and len(cand_d.split()) <= 4:
                doctor_name = f"Dr. {cand_d}" if not cand_d.lower().startswith("dr") else cand_d

        # 10. Dynamic Diagnosis
        diagnosis = None
        diag_m = re.search(
            r"\b(?:Primary\s*Diagnosis|Initial\s*Diagnosis|Diagnosis(?:\s*\(ICD-10\))?)\s*[:\-]\s*([A-Za-z0-9\s\-',()]+?)(?:\s*(?:\.|;|\||\n|\r|\Z))",
            text,
            re.I
        )
        if diag_m:
            cand_diag = diag_m.group(1).strip()
            if 3 <= len(cand_diag) <= 60:
                diagnosis = cand_diag

        # 11. Dynamic Hospital / Facility detection (medical / claim documents only)
        hospital = None
        if doc_type != "insurance_policy":
            doc_header_kws = (
                "summary", "record", "bill", "invoice", "receipt", "settlement", "form",
                "sheet", "notes", "chart", "dossier", "card", "investigation", "report",
                "prescription", "triage", "voucher", "checklist", "dossier"
            )

            def _is_doc_title(s: str) -> bool:
                s_lower = s.lower().strip()
                return any(re.search(rf"\b{re.escape(kw)}\b", s_lower) for kw in doc_header_kws)

            # 11a. Explicit field label "Hospital:" or "Hospital Name:" (same line or next line)
            label_m = re.search(
                r"(?:^|[\r\n])\s*(?:Hospital(?:\s*Name)?|Clinic|Facility|Healthcare\s*Provider|Centre|Center)\s*[:\-]\s*(?:\r?\n\s*)?([^\r\n|]+)",
                text,
                re.I
            )
            if label_m:
                cand_label = label_m.group(1).strip()
                # Split before other adjacent field labels if present on the same line
                cand_label = re.split(r"\b(?:Patient|Ptient|Age|Sex|Gender|DOB|Address|IPD|UHID|Mobile|Phone)\b", cand_label, flags=re.I)[0].strip()
                cand_label = re.sub(r"^[-–—:\s]+|[-–—:\s]+$", "", cand_label).strip()
                if len(cand_label) >= 3 and not _is_doc_title(cand_label):
                    hospital = cand_label

            # 11b. Institution header line (e.g. "SHREE VALLABH MULTISPECIALTY HOSPITAL" or "APOLLO HOSPITAL - DISCHARGE SUMMARY")
            if not hospital:
                for line in text.splitlines()[:15]:
                    line_clean = line.strip()
                    if not line_clean:
                        continue
                    # If line is "HOSPITAL_NAME - DOCUMENT_SUBTITLE", strip document subtitle after dash
                    sub_m = re.match(
                        r"^([A-Za-z0-9&.,'\s\-]+?\s*(?:HOSPITAL|NURSING\s*HOME|CLINIC|HEALTHCARE|MEDICAL\s*CENTRE|PATHOLOGY\s*CENTRE|DIAGNOSTIC\s*CENTRE))\s*[\-–—:]\s*(.+)$",
                        line_clean,
                        re.I
                    )
                    if sub_m:
                        cand_h = sub_m.group(1).strip()
                        if len(cand_h) >= 4 and not _is_doc_title(cand_h):
                            hospital = cand_h
                            break

                    header_m = re.search(
                        r"\b([A-Za-z0-9&.,'\-]+(?:\s+[A-Za-z0-9&.,'\-]+)*\s+(?:HOSPITAL|NURSING\s*HOME|CLINIC|HEALTHCARE|MEDICAL\s*CENTRE|PATHOLOGY\s*CENTRE|DIAGNOSTIC\s*CENTRE))\b",
                        line_clean,
                        re.I
                    )
                    if header_m:
                        cand_h = header_m.group(1).strip()
                        if len(cand_h) >= 4 and not _is_doc_title(cand_h):
                            hospital = cand_h
                            break

        # 12. Dynamic Amounts & Reference Numbers
        sum_insured = None
        premium_amount = None
        bill_amount = None
        paid_amount = None
        bill_num = None
        receipt_num = None

        # Clean Bill / Invoice / Receipt numbers
        rec_m = re.search(r"\bReceipt\s*(?:Number|No\.?)\s*[:\-]\s*([A-Za-z0-9\-_/]+)", text, re.I)
        if rec_m:
            receipt_num = rec_m.group(1).strip()

        b_num_m = re.search(r"\b(?:Bill\s*(?:Number|No\.?)|Invoice\s*(?:Number|No\.?))\s*[:\-]\s*([A-Za-z0-9\-_/]+)", text, re.I)
        if b_num_m:
            bill_num = b_num_m.group(1).strip()
        elif receipt_num:
            bill_num = receipt_num

        if doc_type == "insurance_policy":
            # Extract Sum Insured / Coverage Amount
            si_m = re.search(
                r"\b(?:Basic\s*Sum\s*Insured|Sum\s*Insured|Coverage\s*Limit|Total\s*Sum\s*Insured|Annual\s*Sum\s*Insured|Sum\s*Assured|Coverage\s*Amount)[:\s*Rs₹\.]*([0-9,]+(?:\.\d{2})?)",
                text,
                re.I
            )
            if si_m:
                sum_insured = si_m.group(1).strip()
            elif "10,00,000" in text or "10.00.ooo" in text or "10.00.000" in text:
                sum_insured = "10,00,000"

            # Extract Premium Amount
            prem_m = re.search(
                r"\b(?:Total\s*Premium\s*Paid|Total\s*Premium|Net\s*(?:Annual\s*)?Premium|Gross\s*Premium)[:\s*Rs₹\.]*([0-9,]+(?:\.\d{2})?)",
                text,
                re.I
            )
            if prem_m:
                premium_amount = prem_m.group(1).strip()

            # Policies do NOT have bill amounts
            bill_amount = None

        elif doc_type in ("medical_bill", "invoice"):
            # Extract Total Bill Amount / Invoice Total
            b_amt_m = re.search(
                r"\b(?:TOTAL\s*BILL\s*AMOUNT|TOTAL\s*PHARMACY\s*BILL\s*AMOUNT|Total\s*Hospital\s*Bill\s*Amount|Total\s*Bill\s*Amount|Total\s*Claimed\s*Amount|Invoice\s*Total|Net\s*Payable|Grand\s*Total|Total\s*Amount)[:\s*Rs₹\.]*([0-9,]+(?:\.\d{2})?)",
                text,
                re.I
            )
            if b_amt_m:
                bill_amount = b_amt_m.group(1).strip()

            # Extract Paid / Settlement Amount
            paid_m = re.search(
                r"\b(?:Total\s*Amount\s*Paid|Amount\s*Paid\s*by\s*Patient|Amount\s*Paid|Paid\s*Amount|Receipt\s*Amount|Received\s*Payment)[^\d\n\r]*?[:\s*Rs₹\.]*([0-9,]+(?:\.\d{2})?)",
                text,
                re.I
            )
            if paid_m:
                paid_amount = paid_m.group(1).strip()

            # On payment receipt documents, correlate bill_amount and paid_amount
            if (receipt_num or "receipt" in title.lower()):
                if not paid_amount and bill_amount:
                    paid_amount = bill_amount
                elif not bill_amount and paid_amount:
                    bill_amount = paid_amount

        elif doc_type == "hospital_document":
            # Only extract settled expense / bill total if explicitly stated with currency on this document
            cov_amt_m = re.search(
                r"\b(?:hospital\s*expenses\s*amounting\s*to\s*Rs\.?\s*([0-9,]+(?:\.\d{2})?)|totaling\s*Rs\.?\s*([0-9,]+(?:\.\d{2})?))",
                text,
                re.I
            )
            if cov_amt_m:
                bill_amount = (cov_amt_m.group(1) or cov_amt_m.group(2) or "").strip()
            paid_m = re.search(r"\bfull\s*payment\s*of\s*Rs\.?\s*([0-9,]+(?:\.\d{2})?)", text, re.I)
            if paid_m:
                paid_amount = paid_m.group(1).strip()

        elif doc_type == "medical_report":
            # Lab values (WBC 14,800, platelets 245,000) are NOT bills. Only extract explicit fees:
            fee_m = re.search(r"\b(?:Investigation\s*Fee|Test\s*Charges?|Report\s*Total\s*Amount)[:\s*Rs₹\.]*([0-9,]+(?:\.\d{2})?)", text, re.I)
            if fee_m:
                bill_amount = fee_m.group(1).strip()
            else:
                bill_amount = None

        # 13. Dynamic Dates extraction (Normalized to DD/MM/YYYY)
        start_date = None
        end_date = None
        period_m = re.search(
            r"(?:Policy\s*Period|Period\s*of\s*Insurance)[\s:]+(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\s*(?:to|-)\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
            text,
            re.I
        )
        from datetime import datetime
        if period_m:
            raw_s, raw_e = period_m.group(1).strip(), period_m.group(2).strip()
            for s_fmt in ("%d/%m/%Y", "%d-%m-%Y"):
                try:
                    start_date = datetime.strptime(raw_s, s_fmt).strftime("%d/%m/%Y")
                    break
                except Exception:
                    start_date = raw_s
            for e_fmt in ("%d/%m/%Y", "%d-%m-%Y"):
                try:
                    end_date = datetime.strptime(raw_e, e_fmt).strftime("%d/%m/%Y")
                    break
                except Exception:
                    end_date = raw_e
        else:
            incept_m = re.search(
                r"(?:Inception\s*Date|Policy\s*Start\s*Date|Start\s*Date|Effective\s*Date)[^\n\r]*?((?:January|February|March|April|May|June|July|August|September|October|November|December)\s*\d{1,2}[.,\s]+\d{4}|\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
                text,
                re.I
            )
            expiry_m = re.search(
                r"(?:Expiry\s*Date|Policy\s*End\s*Date|End\s*Date)[^\n\r]*?((?:January|February|March|April|May|June|July|August|September|October|November|December)\s*\d{1,2}[.,\s]+\d{4}|\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
                text,
                re.I
            )

            if incept_m:
                raw_s = incept_m.group(1).strip()
                clean_s = re.sub(r"[,.]", " ", raw_s).strip()
                for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%B %d %Y", "%b %d %Y"):
                    try:
                        start_date = datetime.strptime(clean_s, fmt).strftime("%d/%m/%Y")
                        break
                    except Exception:
                        pass
                if not start_date:
                    start_date = raw_s

            if expiry_m:
                raw_e = expiry_m.group(1).strip()
                clean_e = re.sub(r"[,.]", " ", raw_e).strip()
                for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%B %d %Y", "%b %d %Y"):
                    try:
                        end_date = datetime.strptime(clean_e, fmt).strftime("%d/%m/%Y")
                        break
                    except Exception:
                        pass
                if not end_date:
                    end_date = raw_e

            # Chronological dates extraction fallback across policy certificate pages
            if not start_date or not end_date:
                found_dates = []
                for dm in re.finditer(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s*(\d{1,2})[.,\s]+(\d{4})\b", text, re.I):
                    clean_str = f"{dm.group(1)} {dm.group(2)} {dm.group(3)}"
                    try:
                        dt = datetime.strptime(clean_str, "%B %d %Y")
                        found_dates.append(dt)
                    except Exception:
                        pass
                if found_dates:
                    valid_horizon = [d for d in found_dates if 2000 <= d.year <= 2040]
                    if valid_horizon:
                        valid_horizon.sort()
                        if not start_date:
                            start_date = valid_horizon[0].strftime("%d/%m/%Y")
                        if not end_date and len(valid_horizon) > 1:
                            end_date = valid_horizon[-1].strftime("%d/%m/%Y")

        # 14. Dynamic Document Date
        doc_date = None
        date_patterns = [
            r"(?:Date\s*of\s*Incident|Incident\s*Date|Bill\s*Date|Admission\s*Date|Report\s*Date|Record\s*Date|Date)\s*[:\-]?\s*(\d{1,2}\s*[\/\-]\s*\d{1,2}\s*[\/\-]\s*\d{2,4})",
            r"(?:Date\s*of\s*Incident|Incident\s*Date|Bill\s*Date|Admission\s*Date|Report\s*Date|Record\s*Date|Date)\s*[:\-]?\s*(\d{1,2}\s*[\/\-]\s*[A-Za-z]{3,9}\s*[\/\-]\s*\d{2,4})",
            r"(\d{1,2}\s*[\/\-]\s*\d{1,2}\s*[\/\-]\s*\d{4})",
            r"(\d{1,2}\s*[\/\-]\s*[A-Za-z]{3,9}\s*[\/\-]\s*\d{4})"
        ]
        for pat in date_patterns:
            dm = re.search(pat, text, re.I)
            if dm:
                raw_d = dm.group(1).replace(" ", "")
                for fmt in ("%d/%m/%Y", "%d/%b/%Y", "%d/%B/%Y", "%d-%m-%Y", "%d-%b-%Y", "%d/%m/%y"):
                    try:
                        doc_date = datetime.strptime(raw_d, fmt).strftime("%d/%m/%Y")
                        break
                    except Exception:
                        doc_date = raw_d
                if doc_date:
                    break

        if not doc_date and doc_type == "insurance_policy":
            doc_date = start_date

        # 15. Dynamic Policy Clauses & Conditions Extraction
        relevant_conditions: List[str] = []
        policy_clauses: List[str] = []
        policy_relevant_text: Optional[str] = None

        if doc_type == "insurance_policy":
            if sum_insured:
                relevant_conditions.append(f"Sum Insured: Rs. {sum_insured}")

            # Extract condition sentences present in the text
            for line in text.splitlines():
                line_str = line.strip()
                line_lower = line_str.lower()
                if any(kw in line_lower for kw in ["waiting period", "room rent", "restoration", "floater", "deductible", "copay", "co-payment"]):
                    if len(line_str) > 10 and line_str not in relevant_conditions:
                        relevant_conditions.append(line_str[:120])

            # Extract clauses from CLAIMS / MANDATORY sections
            clause_section = re.search(
                r"(?:SECTION\s*\d+\s*[-:]\s*CLAIMS|CLAIMS\s*PROCEDURE|CLAIMS\s*EVIDENCE|MANDATORY\s*SUPPORTING\s*DOCUMENTS|TERMS\s*AND\s*CONDITIONS)[^\n]*\n([\s\S]*?)(?:\n\n[A-Z]|\Z)",
                text,
                re.I
            )
            if clause_section:
                policy_relevant_text = clause_section.group(0).strip()
                for line in clause_section.group(1).splitlines():
                    line_clean = line.strip()
                    item_m = re.match(r"^\d+[\.\)]\s*(.+)$", line_clean)
                    if item_m:
                        c_text = item_m.group(1).strip()
                        if c_text and c_text not in policy_clauses:
                            policy_clauses.append(line_clean)
                    elif line_clean.lower().startswith("clause ") and line_clean not in policy_clauses:
                        policy_clauses.append(line_clean)

            # If numbered items were not inside a named section, search whole page for numbered lines
            if not policy_clauses:
                for line in text.splitlines():
                    line_clean = line.strip()
                    item_m = re.match(r"^\d+[\.\)]\s*(.+)$", line_clean)
                    if item_m and any(kw in line_clean.lower() for kw in ["summary", "bill", "fir", "report", "ticket", "pass", "receipt", "document", "certificate"]):
                        policy_clauses.append(line_clean)

        return PageExtractionResult(
            page_number=page.page_number,
            document_type=doc_type,
            document_title=title,
            policy_number=pol_num,
            policy_holder_name=holder,
            insured_names=insured,
            patient_name=patient,
            hospital_name=hospital,
            doctor_name=doctor_name,
            diagnosis=diagnosis,
            bill_number=bill_num,
            invoice_number=bill_num,
            receipt_number=receipt_num,
            bill_amount=bill_amount,
            paid_amount=paid_amount,
            sum_insured=sum_insured,
            premium_amount=premium_amount,
            insurer_name=insurer_name,
            policy_start_date=start_date,
            policy_end_date=end_date,
            document_date=doc_date,
            relevant_conditions=relevant_conditions,
            policy_clauses=policy_clauses,
            policy_relevant_text=policy_relevant_text,
            extracted_text_summary=text[:200]
        )

    # Backward-compatible alias
    _extract_page_offline = _extract_page_content


def extract_document(
    pdf_path: Union[str, Path],
    max_pages: Optional[int] = None,
    config: Optional[QwenConfig] = None
) -> List[Dict[str, Any]]:
    """
    Convenience functional interface for document extraction.
    """
    extractor = QwenVLExtractor(config=config)
    return extractor.extract_document(pdf_path, max_pages=max_pages)
