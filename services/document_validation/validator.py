"""
services/document_validation/validator.py
Deterministic document validation engine for InsureMate.
Validates extracted document metadata against required claim schema rules
without calling an LLM, ensuring fast, predictable, agent-ready execution.
"""

from dataclasses import asdict, dataclass, field
import re
from typing import Any, Dict, List, Optional, Union

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
            # Check range
            day_or_month_1 = nums[0]
            day_or_month_2 = nums[1]
            year = nums[2] if nums[2] > 100 else nums[0]
            return 1 <= day_or_month_1 <= 31 and 1 <= day_or_month_2 <= 31 and 1900 <= year <= 2100
        except Exception:
            return False

    def validate_batch(
        self,
        extracted_documents: Union[List[Dict[str, Any]], Dict[str, Any]],
        requirements: Optional[Dict[str, Any]] = None
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

        for doc in extracted_documents:
            custom_rules = requirements.get(doc.get("document_type")) if requirements else None
            res = self.validate_single_document(doc, custom_rules=custom_rules)
            results.append(res)
            if not res.valid:
                overall_reasons.extend(res.reasons)

        valid_count = sum(1 for r in results if r.valid)
        invalid_count = len(results) - valid_count
        overall_valid = invalid_count == 0 and len(results) > 0

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
    requirements: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Callable functional interface for Document Validation.
    """
    validator = DocumentValidator()
    result = validator.validate_batch(extracted_documents, requirements=requirements)
    return result.to_dict()
