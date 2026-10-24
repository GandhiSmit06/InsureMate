"""
services/document_validation/validator.py
Deterministic document validation engine for InsureMate.
Validates extracted document metadata against required claim schema rules
without calling an LLM, ensuring fast, predictable, agent-ready execution.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from utils.logger import logger


# Standard required fields and human-readable error explanations per document type
DEFAULT_DOCUMENT_REQUIREMENTS: Dict[str, Dict[str, str]] = {
    "insurance_policy": {
        "policy_number": "Policy number could not be identified.",
        "policy_start_date": "Policy start/effective date is missing.",
        "policy_end_date": "Policy end/expiry date is missing.",
        "policy_holder_name": "Policy holder name is missing.",
    },
    "medical_bill": {
        "document_date": "Bill date could not be identified.",
        "bill_number": "Bill/invoice number could not be identified.",
        "patient_name": "Patient/person name could not be identified.",
        "bill_amount": "Bill amount is missing or not visible.",
    },
    "invoice": {
        "document_date": "Invoice date could not be identified.",
        "invoice_number": "Invoice number could not be identified.",
        "patient_name": "Customer/patient name could not be identified.",
        "bill_amount": "Invoice total amount is missing.",
    },
    "medical_report": {
        "document_date": "Report date could not be identified.",
        "patient_name": "Patient name is missing on diagnostic report.",
        "hospital_name": "Hospital or diagnostic facility name is missing.",
    },
    "hospital_document": {
        "document_date": "Admission/document date could not be identified.",
        "patient_name": "Patient name is missing on hospital records.",
        "hospital_name": "Hospital name is missing on hospital records.",
    },
    "incident_document": {
        "document_date": "Incident date could not be identified.",
        "patient_name": "Person involved is not specified on incident document.",
    },
}

SUPPORTED_DOCUMENT_TYPES = set(DEFAULT_DOCUMENT_REQUIREMENTS.keys())


@dataclass
class SingleDocumentValidationResult:
    """Validation report for a single document page."""
    document_type: str
    page_number: int
    valid: bool
    missing_fields: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    document_title: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document": self.document_type,
            "document_type": self.document_type,
            "document_title": self.document_title,
            "page_number": self.page_number,
            "valid": self.valid,
            "missing_fields": self.missing_fields,
            "reasons": self.reasons,
        }


@dataclass
class DocumentValidationBatchResult:
    """Comprehensive validation report across all processed document pages."""
    valid: bool
    total_documents: int
    valid_documents: int
    invalid_documents: int
    document_results: List[SingleDocumentValidationResult]
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "total_documents": self.total_documents,
            "valid_documents": self.valid_documents,
            "invalid_documents": self.invalid_documents,
            "reasons": self.reasons,
            "document_results": [r.to_dict() for r in self.document_results],
        }


class DocumentValidator:
    """
    Deterministic rule-based validation engine.
    Checks field presence, non-emptiness, recognized categories, and value formats.
    """

    def __init__(self, custom_requirements: Optional[Dict[str, Dict[str, str]]] = None):
        self.requirements = custom_requirements or DEFAULT_DOCUMENT_REQUIREMENTS

    def validate_single_document(
        self,
        doc: Dict[str, Any],
        custom_rules: Optional[Dict[str, str]] = None
    ) -> SingleDocumentValidationResult:
        """
        Validate a single extracted page dictionary.
        """
        page_num = doc.get("page_number", 0)
        doc_type = str(doc.get("document_type", "unknown")).strip().lower()
        doc_title = doc.get("document_title")

        missing_fields: List[str] = []
        reasons: List[str] = []

        # 1. Unrecognized document type handling
        if doc_type not in SUPPORTED_DOCUMENT_TYPES:
            reasons.append(
                f"Document type '{doc_type}' on page {page_num} is unrecognized or unsupported for claim submission."
            )
            logger.validation(f"Page {page_num} validation failed: unrecognized type '{doc_type}'")
            return SingleDocumentValidationResult(
                document_type=doc_type,
                page_number=page_num,
                document_title=doc_title,
                valid=False,
                missing_fields=["recognized_document_type"],
                reasons=reasons,
            )

        # 2. Check required fields for this document type
        rules = custom_rules or self.requirements.get(doc_type, {})

        for field_name, missing_reason in rules.items():
            val = doc.get(field_name)

            # Special case aliases: e.g. bill_number / invoice_number
            if field_name == "bill_number" and (val is None or str(val).strip() == ""):
                val = doc.get("invoice_number")
            elif field_name == "invoice_number" and (val is None or str(val).strip() == ""):
                val = doc.get("bill_number")
            elif field_name == "policy_holder_name" and (val is None or str(val).strip() == ""):
                # If insured_names is populated, accept as policy holder/insured
                insured = doc.get("insured_names", [])
                if isinstance(insured, list) and len(insured) > 0:
                    val = insured[0]

            # Missing or null check
            if val is None or (isinstance(val, str) and str(val).strip() == ""):
                missing_fields.append(field_name)
                reasons.append(f"{missing_reason} (Page {page_num})")
            elif isinstance(val, list) and len(val) == 0:
                missing_fields.append(field_name)
                reasons.append(f"{missing_reason} (Page {page_num})")

        # 3. Format sanity checks (e.g. invalid date format or negative amount)
        self._validate_field_formats(doc, page_num, missing_fields, reasons)

        is_valid = len(missing_fields) == 0 and len(reasons) == 0

        if is_valid:
            reasons.append(f"All required fields for '{doc_type}' on page {page_num} are present and valid.")
            logger.validation(f"Page {page_num} ({doc_type}): VALID")
        else:
            logger.validation(f"Page {page_num} ({doc_type}): INVALID - {len(missing_fields)} missing fields")

        return SingleDocumentValidationResult(
            document_type=doc_type,
            page_number=page_num,
            document_title=doc_title,
            valid=is_valid,
            missing_fields=missing_fields,
            reasons=reasons,
        )

    def _validate_field_formats(
        self,
        doc: Dict[str, Any],
        page_num: int,
        missing_fields: List[str],
        reasons: List[str]
    ) -> None:
        """Deterministic checks for illegal or corrupt values (dates, amounts)."""
        # Validate date format if present
        date_fields = ["document_date", "policy_start_date", "policy_end_date"]
        for df in date_fields:
            date_val = doc.get(df)
            if date_val and isinstance(date_val, str) and date_val.strip():
                date_str = date_val.strip()
                # Basic sanity check: year between 1900 and 2100, month 1-12, day 1-31
                if not self._is_syntactically_valid_date(date_str):
                    if df not in missing_fields:
                        missing_fields.append(df)
                    reasons.append(f"Invalid date format or impossible date value '{date_str}' in field '{df}' (Page {page_num}).")

        # Validate bill amount if present
        if "bill_amount" in doc and doc["bill_amount"] is not None:
            raw_amt = str(doc["bill_amount"]).replace(",", "").replace("$", "").replace("₹", "").replace("Rs.", "").strip()
            try:
                amt_num = float(raw_amt)
                if amt_num < 0:
                    missing_fields.append("bill_amount")
                    reasons.append(f"Bill amount cannot be negative: {doc['bill_amount']} (Page {page_num}).")
            except ValueError:
                missing_fields.append("bill_amount")
                reasons.append(f"Bill amount '{doc['bill_amount']}' is not a valid numeric amount (Page {page_num}).")

    @staticmethod
    def _is_syntactically_valid_date(date_str: str) -> bool:
        """Checks if date string has plausible numeric components."""
        # Clean delimiters
        parts = re.split(r"[-/\s.]+", date_str)
        if len(parts) < 3:
            return False

        # Match named month e.g. 12-Mar-2025
        months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
        named_month = any(p.lower()[:3] in months for p in parts)
        if named_month:
            return True

        # Check numeric components
        try:
            nums = [int(p) for p in parts if p.isdigit()]
            if len(nums) < 3:
                return False
            if nums[0] > 1000:  # YYYY-MM-DD
                year, m_or_d1, m_or_d2 = nums[0], nums[1], nums[2]
                return 1 <= m_or_d1 <= 31 and 1 <= m_or_d2 <= 31 and 1900 <= year <= 2100
            elif nums[2] > 1000:  # DD-MM-YYYY or MM-DD-YYYY
                m_or_d1, m_or_d2, year = nums[0], nums[1], nums[2]
                return 1 <= m_or_d1 <= 31 and 1 <= m_or_d2 <= 31 and 1900 <= year <= 2100
            else:
                year = nums[2] if nums[2] > 100 else nums[0]
                return 1 <= nums[0] <= 31 and 1 <= nums[1] <= 31 and 1900 <= year <= 2100
        except Exception:
            return False

    def _validate_document_slot_alignment(
        self,
        extracted_documents: List[Dict[str, Any]],
        policy_file: Optional[Union[str, List[str]]] = None,
        claim_file: Optional[Union[str, List[str]]] = None,
    ) -> Tuple[bool, List[str]]:
        """
        Check that documents uploaded to policy slot vs claim slot contain the expected
        document types, detecting role mismatches and inverted uploads.
        """
        if not extracted_documents:
            return True, []

        from pathlib import Path

        def _to_names_and_paths(target: Optional[Union[str, List[str]]]) -> Tuple[Set[str], Set[str]]:
            names = set()
            paths = set()
            if not target:
                return names, paths
            items = target if isinstance(target, (list, tuple, set)) else [target]
            for item in items:
                if not item:
                    continue
                p = Path(str(item))
                names.add(p.name.lower())
                try:
                    paths.add(str(p.resolve()).lower())
                except Exception:
                    paths.add(str(p).lower())
            return names, paths

        pol_names, pol_paths = _to_names_and_paths(policy_file)
        clm_names, clm_paths = _to_names_and_paths(claim_file)

        policy_pages: List[Dict[str, Any]] = []
        claim_pages: List[Dict[str, Any]] = []

        for doc in extracted_documents:
            slot = doc.get("slot")
            src_name = (doc.get("source_file") or "").lower()
            file_p = (doc.get("file_path") or "").lower()

            is_policy_slot = (
                slot == "policy"
                or (pol_names and src_name in pol_names)
                or (pol_paths and file_p in pol_paths)
            )
            is_claim_slot = (
                slot == "claim"
                or (clm_names and src_name in clm_names)
                or (clm_paths and file_p in clm_paths)
            )

            if is_policy_slot and not is_claim_slot:
                policy_pages.append(doc)
            elif is_claim_slot and not is_policy_slot:
                claim_pages.append(doc)
            elif is_policy_slot and is_claim_slot:
                if slot == "policy":
                    policy_pages.append(doc)
                else:
                    claim_pages.append(doc)

        medical_types = {"hospital_document", "medical_bill", "invoice", "medical_report"}

        policy_slot_has_claim = False
        policy_filename = "Uploaded Policy Document"
        if policy_pages:
            p_types = [p.get("document_type") for p in policy_pages]
            num_pol = sum(1 for t in p_types if t == "insurance_policy")
            all_medical = len(p_types) > 0 and all(t in medical_types for t in p_types)
            if num_pol == 0 and all_medical:
                policy_slot_has_claim = True
                policy_filename = policy_pages[0].get("source_file") or (
                    Path(policy_file[0] if isinstance(policy_file, list) else str(policy_file)).name
                    if policy_file else "Insurance Policy Document"
                )

        claim_slot_has_policy = False
        claim_filename = "Uploaded Claim Document"
        if claim_pages:
            c_types = [p.get("document_type") for p in claim_pages]
            num_med = sum(1 for t in c_types if t in medical_types)
            all_policy = len(c_types) > 0 and all(t == "insurance_policy" for t in c_types)
            if num_med == 0 and all_policy:
                claim_slot_has_policy = True
                claim_filename = claim_pages[0].get("source_file") or (
                    Path(claim_file[0] if isinstance(claim_file, list) else str(claim_file)).name
                    if claim_file else "Claim Document"
                )

        # Inversion Detection: Both slots swapped
        reasons: List[str] = []
        if policy_slot_has_claim and claim_slot_has_policy:
            reasons.append(
                "Document Inversion Detected: Your Insurance Policy and Claim Documents appear to be swapped. "
                "Please re-upload with the Policy Contract in the Policy field and Hospital Bills/Discharge Summary in the Claim field."
            )
            reasons.append(
                f"Invalid document format: The document uploaded in the 'Insurance Policy' field ('{policy_filename}') "
                f"is a Hospital/Medical Claim document, not an Insurance Policy Contract. "
                f"Please upload the files in their correct corresponding fields."
            )
            reasons.append(
                f"Invalid document format: The document uploaded in the 'Claim Documents' field ('{claim_filename}') "
                f"is an Insurance Policy Schedule, not a Medical Claim Document."
            )
            return False, reasons

        # Individual slot failures
        if policy_slot_has_claim:
            reasons.append(
                f"Invalid document format: The document uploaded in the 'Insurance Policy' field ('{policy_filename}') "
                f"is a Hospital/Medical Claim document, not an Insurance Policy Contract. "
                f"Please upload the files in their correct corresponding fields."
            )
            return False, reasons

        if claim_slot_has_policy:
            reasons.append(
                f"Invalid document format: The document uploaded in the 'Claim Documents' field ('{claim_filename}') "
                f"is an Insurance Policy Schedule, not a Medical Claim Document."
            )
            return False, reasons

        return True, []

    def validate_batch(
        self,
        extracted_documents: Union[List[Dict[str, Any]], Dict[str, Any]],
        requirements: Optional[Dict[str, Any]] = None,
        policy_file: Optional[Union[str, List[str]]] = None,
        claim_file: Optional[Union[str, List[str]]] = None,
    ) -> DocumentValidationBatchResult:
        """
        Validate a batch of extracted documents or a single document.
        """
        logger.validation("Starting batch document validation")

        # Handle single document passed instead of list
        if isinstance(extracted_documents, dict):
            extracted_documents = [extracted_documents]

        if not extracted_documents:
            logger.validation("Validation failed: empty extraction result")
            return DocumentValidationBatchResult(
                valid=False,
                total_documents=0,
                valid_documents=0,
                invalid_documents=0,
                document_results=[],
                reasons=["No extracted documents provided for validation."],
            )

        results: List[SingleDocumentValidationResult] = []
        overall_reasons: List[str] = []

        # Collect document-level context across all pages of each document type
        type_contexts: Dict[str, Dict[str, Any]] = {}
        for doc in extracted_documents:
            dtype = doc.get("document_type")
            if dtype:
                ctx = type_contexts.setdefault(dtype, {})
                for k, v in doc.items():
                    if k in {"page_number", "document_title", "raw_response", "extracted_text_summary"}:
                        continue
                    if dtype == "insurance_policy" and k in {"bill_amount", "patient_name"}:
                        continue
                    if v is not None and str(v).strip() != "" and k not in ctx:
                        ctx[k] = v

        for doc in extracted_documents:
            dtype = doc.get("document_type")
            merged_doc = dict(doc)
            if dtype in type_contexts:
                for k, v in type_contexts[dtype].items():
                    if dtype == "insurance_policy" and k in {"bill_amount", "patient_name"}:
                        continue
                    if merged_doc.get(k) is None or str(merged_doc.get(k)).strip() == "":
                        merged_doc[k] = v
            custom_rules = requirements.get(dtype) if requirements else None
            res = self.validate_single_document(merged_doc, custom_rules=custom_rules)
            results.append(res)
            if not res.valid:
                overall_reasons.extend(res.reasons)

        valid_count = sum(1 for r in results if r.valid)
        invalid_count = len(results) - valid_count
        overall_valid = invalid_count == 0 and len(results) > 0

        # Validate slot-level semantic role alignment & inversion
        slot_valid, slot_reasons = self._validate_document_slot_alignment(
            extracted_documents=extracted_documents,
            policy_file=policy_file,
            claim_file=claim_file
        )
        if not slot_valid and slot_reasons:
            overall_valid = False
            for sr in reversed(slot_reasons):
                overall_reasons.insert(0, sr)
            # Mark all document results as invalid due to slot mismatch
            for r in results:
                r.valid = False
                for sr in reversed(slot_reasons):
                    if sr not in r.reasons:
                        r.reasons.insert(0, sr)
            valid_count = 0
            invalid_count = len(results)

        if overall_valid:
            overall_reasons.append(f"All {len(results)} submitted documents passed required field validation.")

        logger.result(
            f"Validation complete: total={len(results)}, valid={valid_count}, invalid={invalid_count}, overall_valid={overall_valid}"
        )

        return DocumentValidationBatchResult(
            valid=overall_valid,
            total_documents=len(results),
            valid_documents=valid_count,
            invalid_documents=invalid_count,
            document_results=results,
            reasons=overall_reasons,
        )


def document_validation(
    extracted_documents: Union[List[Dict[str, Any]], Dict[str, Any]],
    requirements: Optional[Dict[str, Any]] = None,
    policy_file: Optional[Union[str, List[str]]] = None,
    claim_file: Optional[Union[str, List[str]]] = None,
) -> Dict[str, Any]:
    """
    Callable functional interface for Document Validation.
    """
    validator = DocumentValidator()
    result = validator.validate_batch(
        extracted_documents,
        requirements=requirements,
        policy_file=policy_file,
        claim_file=claim_file
    )
    return result.to_dict()
