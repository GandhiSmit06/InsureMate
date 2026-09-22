"""
Quality evaluation and issue detection engine.
Assesses OCR readability, logical date order, arithmetic consistency, and missing critical fields.
"""

from typing import List, Tuple
from datetime import datetime
from ..schemas.output_schema import (
    DocumentQualityReport,
    QualityIssue,
    ArithmeticReconciliation,
    ExtractedEntities,
    DocumentTypeHint,
    PageUnderstanding,
)
from ..schemas.input_schema import IngestedDocument
from ..schemas.common import FieldStatus
from ..normalization.text_normalizer import calculate_unreadable_char_ratio
from ..config import GARBLED_CHAR_RATIO_THRESHOLD


class DocumentQualityChecker:
    """Evaluates document legibility, arithmetic reconciliation, and logical consistency."""

    @classmethod
    def evaluate_quality(
        cls,
        ingested_doc: IngestedDocument,
        pages_understanding: List[PageUnderstanding],
        entities: ExtractedEntities,
        type_hints: List[DocumentTypeHint]
    ) -> Tuple[DocumentQualityReport, List[QualityIssue]]:
        issues: List[QualityIssue] = []

        # 1. Evaluate unreadable/garbled character ratio
        total_text = "".join([p.extracted_text for p in pages_understanding])
        unreadable_ratio = calculate_unreadable_char_ratio(total_text)

        if unreadable_ratio > GARBLED_CHAR_RATIO_THRESHOLD:
            issues.append(QualityIssue(
                code="HIGH_UNREADABLE_RATIO",
                severity="warning",
                description=f"Document contains {round(unreadable_ratio * 100, 1)}% unreadable/garbled characters. OCR quality may be degraded.",
            ))

        # 2. Check OCR confidence
        ocr_scores = [p.ocr_confidence_avg for p in ingested_doc.pages if p.ocr_confidence_avg is not None]
        avg_ocr_conf = round(sum(ocr_scores) / len(ocr_scores), 2) if ocr_scores else None

        if avg_ocr_conf is not None and avg_ocr_conf < 60.0:
            issues.append(QualityIssue(
                code="LOW_OCR_CONFIDENCE",
                severity="warning",
                description=f"Average OCR confidence is {avg_ocr_conf}%, indicating potential character recognition errors.",
            ))

        # 3. Check for scanned/image-based nature
        is_scanned = (
            ingested_doc.source_type in ("scanned_pdf", "image") or
            any(p.is_scanned for p in ingested_doc.pages)
        )

        # 4. Check for conflicting dates (e.g. Admission date after Discharge date)
        has_conflicting_dates = False
        adm_val = entities.encounter.admission_date.value
        dis_val = entities.encounter.discharge_date.value
        if adm_val and dis_val:
            try:
                adm_dt = datetime.strptime(str(adm_val), "%Y-%m-%d")
                dis_dt = datetime.strptime(str(dis_val), "%Y-%m-%d")
                if adm_dt > dis_dt:
                    has_conflicting_dates = True
                    issues.append(QualityIssue(
                        code="CONFLICTING_ENCOUNTER_DATES",
                        severity="error",
                        description=f"Admission date ({adm_val}) is chronologically after Discharge date ({dis_val}).",
                        field_reference="encounter.admission_date / encounter.discharge_date",
                    ))
            except (ValueError, TypeError):
                pass

        # 5. Arithmetic reconciliation between itemized charges and total amount
        reconciliation = cls._reconcile_finances(entities, issues)

        # 6. Check for missing critical fields based on top document type hint
        top_hint = type_hints[0].candidate_type if type_hints else "unknown"
        missing_critical = cls._check_missing_fields(top_hint, entities, issues)

        # 7. Determine overall quality rating
        overall_quality = "excellent"
        if unreadable_ratio > 0.30 or (avg_ocr_conf is not None and avg_ocr_conf < 40.0):
            overall_quality = "unreadable"
        elif unreadable_ratio > GARBLED_CHAR_RATIO_THRESHOLD or has_conflicting_dates:
            overall_quality = "degraded"
        elif is_scanned or issues:
            overall_quality = "good"

        report = DocumentQualityReport(
            overall_quality=overall_quality,
            unreadable_char_ratio=unreadable_ratio,
            ocr_confidence_avg=avg_ocr_conf,
            is_scanned_or_image_based=is_scanned,
            has_conflicting_dates=has_conflicting_dates,
            arithmetic_reconciliation=reconciliation,
            missing_critical_fields=missing_critical,
        )

        return report, issues

    @staticmethod
    def _reconcile_finances(
        entities: ExtractedEntities,
        issues: List[QualityIssue]
    ) -> ArithmeticReconciliation:
        charges = entities.financial.itemized_charges
        total_field = entities.financial.total_amount

        if not charges or total_field.value is None or total_field.status != FieldStatus.EXTRACTED:
            return ArithmeticReconciliation(checked=False, notes="Insufficient itemized charges or total amount for reconciliation")

        try:
            itemized_sum = round(sum([c.amount for c in charges if c.amount is not None]), 2)
            stated_total = round(float(total_field.value), 2)
            discrepancy = round(abs(itemized_sum - stated_total), 2)
            matches = discrepancy <= 1.0  # Allow minor rounding difference of 1.0

            if not matches:
                issues.append(QualityIssue(
                    code="ARITHMETIC_MISMATCH",
                    severity="warning",
                    description=f"Sum of itemized line items ({itemized_sum}) differs from stated total ({stated_total}) by {discrepancy}.",
                    field_reference="financial.total_amount",
                ))

            return ArithmeticReconciliation(
                checked=True,
                itemized_sum=itemized_sum,
                stated_total=stated_total,
                discrepancy=discrepancy,
                matches=matches,
                notes=None if matches else f"Discrepancy of {discrepancy} between itemized sum and stated total",
            )
        except (ValueError, TypeError) as e:
            return ArithmeticReconciliation(checked=False, notes=f"Reconciliation calculation error: {str(e)}")

    @staticmethod
    def _check_missing_fields(
        doc_type: str,
        entities: ExtractedEntities,
        issues: List[QualityIssue]
    ) -> List[str]:
        missing: List[str] = []

        if doc_type in ("hospital_invoice", "medical_bill"):
            if entities.financial.invoice_number.status != FieldStatus.EXTRACTED:
                missing.append("financial.invoice_number")
            if entities.financial.total_amount.status != FieldStatus.EXTRACTED:
                missing.append("financial.total_amount")
            if entities.financial.bill_date.status != FieldStatus.EXTRACTED:
                missing.append("financial.bill_date")

        elif doc_type == "discharge_summary":
            if entities.encounter.admission_date.status != FieldStatus.EXTRACTED:
                missing.append("encounter.admission_date")
            if entities.encounter.discharge_date.status != FieldStatus.EXTRACTED:
                missing.append("encounter.discharge_date")
            if entities.encounter.diagnosis_text.status != FieldStatus.EXTRACTED:
                missing.append("encounter.diagnosis_text")

        elif doc_type == "prescription":
            if entities.hospital.doctor_name.status != FieldStatus.EXTRACTED:
                missing.append("hospital.doctor_name")

        for m_field in missing:
            issues.append(QualityIssue(
                code="MISSING_CRITICAL_FIELD",
                severity="info",
                description=f"Field '{m_field}' typically expected for a '{doc_type}' was not found.",
                field_reference=m_field,
            ))

        return missing
