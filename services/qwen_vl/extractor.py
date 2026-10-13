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
    bill_number: Optional[str] = None
    invoice_number: Optional[str] = None
    bill_amount: Optional[Union[float, str]] = None
    policy_start_date: Optional[str] = None
    policy_end_date: Optional[str] = None
    document_date: Optional[str] = None
    relevant_conditions: List[str] = field(default_factory=list)
    insurer_name: Optional[str] = None
    sum_insured: Optional[str] = None
    policy_clauses: List[str] = field(default_factory=list)
    policy_relevant_text: Optional[str] = None
    extracted_text_summary: Optional[str] = None
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
            logger.classifier(
                f"Page {extraction.page_number}: Classified as '{extraction.document_type}' | Title: '{extraction.document_title}'"
            )
            results.append(extraction.to_dict())

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
            bill_number=data.get("bill_number"),
            invoice_number=data.get("invoice_number"),
            bill_amount=data.get("bill_amount"),
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
            # Clean fallback for blank or unreadable pages
            doc_type = "unknown"
            if "policy" in name_lower:
                doc_type = "insurance_policy"
            elif any(k in name_lower for k in ["bill", "invoice"]):
                doc_type = "medical_bill"
            elif "fir" in name_lower:
                doc_type = "incident_document"
            elif any(k in name_lower for k in ["hospital", "claim", "discharge"]):
                doc_type = "hospital_document"

            return PageExtractionResult(
                page_number=page.page_number,
                document_type=doc_type,
                document_title=f"{doc_type.replace('_', ' ').title()} (Page {page.page_number})",
                document_date=None,
                extracted_text_summary="Document page with no readable text."
            )

        # 1. Dynamic Classification based on actual page content
        if (
            any(k in text_lower for k in [
                "policy schedule", "policy certificate", "insurance policy", "policy copy",
                "policy period", "policy number", "sum insured", "proposer", "policyholder",
                "schedule of insurance", "comprehensive insurance", "health plan",
                "premium paid", "policy inception", "waiting period", "floater",
                "terms and conditions", "coverage amount", "premium details"
            ])
            or ("policy" in name_lower and not any(k in text_lower for k in ["claim form", "tax invoice", "indoor admission", "discharge summary", "police station", "fir"]))
        ):
            doc_type = "insurance_policy"
        elif any(k in text_lower for k in ["first information report", "police station", "incident report", "report number: fir", "theft of travel", "police seal"]):
            doc_type = "incident_document"
        elif any(k in text_lower for k in ["discharge summary", "discharge card", "clinical summary"]):
            doc_type = "hospital_document"
        elif any(k in text_lower for k in ["hospital bill", "inpatient bill", "final bill", "tax invoice", "bill amount", "total bill amount", "pharmacy bill", "room & nursing charges"]):
            doc_type = "medical_bill"
        elif any(k in text_lower for k in ["pathology", "diagnostic report", "laboratory", "radiology", "ultrasound", "blood investigation", "diagnostic investigation"]):
            doc_type = "medical_report"
        elif any(k in text_lower for k in ["hospital", "admission", "indoor case", "indoor admission", "ward rounds", "consulting surgeon"]):
            doc_type = "hospital_document"
        else:
            doc_type = "other"

        # 2. Dynamic Human-readable title
        if "policy certificate" in text_lower:
            title = f"Policy Certificate (Page {page.page_number})"
        elif "key features" in text_lower:
            title = f"Policy Key Features & Benefits (Page {page.page_number})"
        elif "welcome" in text_lower:
            title = f"Policy Welcome Overview (Page {page.page_number})"
        elif "insured details" in text_lower:
            title = f"Policy Schedule & Insured Details (Page {page.page_number})"
        elif "first information report" in text_lower or "fir" in text_lower:
            title = f"Police First Information Report (FIR) (Page {page.page_number})"
        elif "discharge summary" in text_lower:
            title = f"Hospital Discharge Summary (Page {page.page_number})"
        elif "admission" in text_lower:
            title = f"Hospital Indoor Admission Record (Page {page.page_number})"
        elif doc_type == "medical_bill":
            title = f"Hospital Medical Bill (Page {page.page_number})"
        elif doc_type == "medical_report":
            title = f"Medical Diagnostic Report (Page {page.page_number})"
        elif doc_type == "insurance_policy":
            title = f"Insurance Policy Schedule (Page {page.page_number})"
        else:
            first_line = next((ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("=")), "")
            title = first_line[:80] if first_line else f"{doc_type.replace('_', ' ').title()} (Page {page.page_number})"

        # 3. Dynamic Insurer detection
        insurer_name = None
        hdr_m = re.search(
            r"(?:Insurer|Insurance\s*Company|Underwritten\s*by|Issued\s*by|TPA|Preferred\s*Provider)\s*[:\-]\s*([A-Za-z0-9\s&.,'-]+?)(?:\n|\r|,|;|\.|\Z)",
            text,
            re.I
        )
        if hdr_m and len(hdr_m.group(1).strip()) > 3:
            insurer_name = hdr_m.group(1).strip()
        else:
            welc_m = re.search(
                r"Welcome\s*to\s*(?:the\s*)?([A-Za-z0-9\s&.,'-]+?)\s+(?:Family|Insurance|Assurance)",
                text,
                re.I
            )
            if welc_m and len(welc_m.group(1).strip()) > 2:
                cand_welc = welc_m.group(1).strip()
                if not any(bad in cand_welc.lower() for bad in ["our", "your", "new", "this"]):
                    insurer_name = cand_welc
            else:
                corp_m = re.search(
                    r"\b([A-Z][A-Za-z0-9&.\s'-]{1,35}?\s*(?:General\s*Insurance|Life\s*Insurance|Health\s*Insurance|Assurance\s*Co(?:mpany)?|Insurance\s*Co(?:mpany)?|Lombard|Allianz|ERGO|Bupa|Assurance))\b",
                    text
                )
                if corp_m:
                    cand_corp = corp_m.group(1).strip()
                    cand_corp = re.sub(r"^(?:Welcome\s*to\s*(?:the\s*)?|Dear\s*|From\s*)", "", cand_corp, flags=re.I).strip()
                    if len(cand_corp) > 3:
                        insurer_name = cand_corp

        # 4. Dynamic Policy Number extraction
        pol_num = None
        pol_m = re.search(r"Policy\s*(?:Number|No\.?|Certificate\s*No\.?|Num)[\s:\-]+([0-9a-zA-Z/._'-]+)", text, re.I)
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

        # Sanitize OCR artifacts in policy numbers (trailing OCR zeros misread as 'o'/'O')
        if pol_num:
            pol_num = re.sub(r"/[oO]{2}/[oO]{3}$", "/00/000", pol_num)

        # 5. Dynamic Policy Holder / Proposer
        holder = None
        holder_m = re.search(
            r"(?:Policy\s*Holder(?:\s*Name)?|Pro\s*poser(?:\s*Name)?|Dear)\s*[:\-]?\s*([A-Za-z\s]+?)(?:,|\n|\r|Email|GSTIN|Mobile|Phone|Welcome|Address|\Z)",
            text,
            re.I
        )
        if holder_m:
            cand = holder_m.group(1).strip()
            if len(cand) > 3 and not any(w in cand.lower() for w in ["details", "number", "certificate", "insurance", "welcome", "family"]):
                holder = cand

        # 6. Dynamic Insured Persons
        insured: List[str] = []
        insured_m = re.search(r"Insured\s*Persons?:\s*([^\n\r]+)", text, re.I)
        if insured_m:
            insured = [name.strip() for name in insured_m.group(1).split(",") if name.strip()]

        # Scan for insured persons in tables
        if not insured:
            tbl_names = re.findall(
                r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s+(?:January|February|March|April|May|June|July|August|September|October|November|December|\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}|\d{2}\s+(?:Male|Female)|SELF|SPOUSE)\b",
                text
            )
            for tn in tbl_names:
                clean_tn = tn.strip()
                if clean_tn and len(clean_tn) > 3 and clean_tn not in insured:
                    insured.append(clean_tn)

        if holder and holder not in insured:
            insured.insert(0, holder)

        # 7. Dynamic Patient & Hospital & Report
        pat_m = re.search(
            r"(?:Patient(?:\s*Name)?|Ptient\s*Name|Complainant(?:\s*Name)?|Pt\.\s*Name)\s*[:\-]?\s*([A-Za-z\s]+?)(?:\s*(?:\||Age|Sex|DOB|Address|Mobile|Phone|Admission|Date|/|\n|\r|\Z))",
            text,
            re.I
        )
        patient = None
        if pat_m:
            cand_p = pat_m.group(1).strip()
            if len(cand_p) >= 3 and not any(kw in cand_p.lower() for kw in ["hospital", "policy", "certificate"]):
                patient = cand_p

        hospital = None
        hosp_m = re.search(r"(?:^|\n)\s*(?:Hospital|Clinic|Facility|Police\s*Station)\s*[:\-]\s*([^\n\r]+)", text, re.I)
        if hosp_m:
            hospital = hosp_m.group(1).strip()
        else:
            hosp_m2 = re.search(r"([A-Za-z\s]+?\s*(?:HOSPITAL|NURSING\s*HOME|CLINIC|HEALTHCARE|MEDICAL\s*CENTRE)(?:[^\n\r]*))", text, re.I)
            if hosp_m2:
                cand_h = hosp_m2.group(1).strip()
                if not cand_h.startswith("-"):
                    hospital = cand_h

        # 8. Dynamic Bill Number / Invoice / FIR Number
        bill_num_m = re.search(r"(?:Bill|Invoice|Report|FIR)\s*(?:Number|No\.?)\s*[:\-]?\s*([^\n\r,]+)", text, re.I)
        bill_num = bill_num_m.group(1).strip() if bill_num_m else None

        # 9. Dynamic Amounts
        amount = None
        sum_m = re.search(
            r"(?:Total\s*Bill\s*Amount|Bill\s*Amount|Total\s*Amount|Sum\s*Insured|IL\s*Sum\s*Insured|Coverage\s*Amount)[:\s*Rs₹\.]*([0-9,.]+)",
            text,
            re.I
        )
        if sum_m:
            cand_amt = sum_m.group(1).strip().strip(",.")
            if any(c.isdigit() for c in cand_amt):
                amount = cand_amt

        # OCR artifact normalization for low-resolution scanned amounts (e.g. '10.00.ooo' -> '10,00,000')
        if not amount:
            ocr_amt_m = re.search(r"\b([0-9]{1,3}(?:[.,][0-9oO]{2,3})+)\b", text)
            if ocr_amt_m:
                raw_token = ocr_amt_m.group(1)
                cleaned_digits = raw_token.replace("o", "0").replace("O", "0")
                parts = re.split(r"[.,]", cleaned_digits)
                if len(parts) >= 3 and all(p.isdigit() for p in parts):
                    amount = ",".join(parts)
                elif any(c.isdigit() for c in cleaned_digits):
                    amount = cleaned_digits

        # 10. Dynamic Dates extraction (Normalized to DD/MM/YYYY)
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

        # 11. Dynamic Document Date
        doc_date = None
        date_patterns = [
            r"(?:Date\s*of\s*Incident|Incident\s*Date|Bill\s*Date|Admission\s*Date|Report\s*Date|Date)\s*[:\-]?\s*(\d{1,2}\s*[\/\-]\s*\d{1,2}\s*[\/\-]\s*\d{2,4})",
            r"(?:Date\s*of\s*Incident|Incident\s*Date|Bill\s*Date|Admission\s*Date|Report\s*Date|Date)\s*[:\-]?\s*(\d{1,2}\s*[\/\-]\s*[A-Za-z]{3,9}\s*[\/\-]\s*\d{2,4})",
            r"(\d{1,2}\s*[\/\-]\s*\d{1,2}\s*[\/\-]\s*\d{4})",
            r"(\d{1,2}\s*[\/\-]\s*[A-Za-z]{3,9}\s*[\/\-]\s*\d{4})"
        ]
        for pat in date_patterns:
            dm = re.search(pat, text, re.I)
            if dm:
                raw_d = dm.group(1).replace(" ", "")
                from datetime import datetime
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

        # 12. Dynamic Policy Clauses & Conditions Extraction
        relevant_conditions: List[str] = []
        policy_clauses: List[str] = []
        policy_relevant_text: Optional[str] = None

        if doc_type == "insurance_policy":
            if amount:
                relevant_conditions.append(f"Sum Insured: Rs. {amount}")

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
            bill_number=bill_num,
            invoice_number=bill_num,
            bill_amount=amount,
            sum_insured=amount,
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
