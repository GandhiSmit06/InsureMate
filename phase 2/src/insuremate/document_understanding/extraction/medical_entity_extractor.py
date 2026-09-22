"""
Entity extractor for medical, administrative, encounter, and financial entities.
Gathers evidence from key-value pairs, document sections, and layout text while strictly preserving uncertainty.
"""

import re
from typing import List, Optional, Dict
from ..schemas.output_schema import (
    ExtractedEntities,
    PatientEntities,
    HospitalEntities,
    EncounterEntities,
    FinancialEntities,
    ItemizedCharge,
    KeyValueField,
    DocumentSection,
)
from ..schemas.input_schema import RawPageInput
from ..schemas.common import FieldStatus, ConfidenceLevel, FieldValue, Provenance
from ..normalization.date_normalizer import normalize_date_string
from ..normalization.amount_normalizer import normalize_amount_string
from ..provenance.tracer import ProvenanceTracer


class MedicalEntityExtractor:
    """Extracts structured entities across patient, hospital, encounter, and financial categories."""

    @classmethod
    def extract_entities(
        cls,
        document_id: str,
        pages: List[RawPageInput],
        key_values: List[KeyValueField],
        sections: List[DocumentSection],
        itemized_charges: List[ItemizedCharge]
    ) -> ExtractedEntities:
        # Build index of key-values by normalized key for rapid lookup
        kv_map: Dict[str, KeyValueField] = {kv.normalized_key: kv for kv in key_values}

        patient = cls._extract_patient(document_id, pages, kv_map)
        hospital = cls._extract_hospital(document_id, pages, kv_map)
        encounter = cls._extract_encounter(document_id, pages, kv_map, sections)
        financial = cls._extract_financial(document_id, pages, kv_map, itemized_charges)

        return ExtractedEntities(
            patient=patient,
            hospital=hospital,
            encounter=encounter,
            financial=financial,
        )

    @classmethod
    def _extract_patient(
        cls,
        document_id: str,
        pages: List[RawPageInput],
        kv_map: Dict[str, KeyValueField]
    ) -> PatientEntities:
        # Patient Name
        name_val = FieldValue(status=FieldStatus.NOT_FOUND)
        if "patient_name" in kv_map and kv_map["patient_name"].value:
            kv = kv_map["patient_name"]
            name_val = FieldValue(
                value=kv.value,
                raw_text=kv.value,
                status=FieldStatus.EXTRACTED,
                provenance=kv.provenance,
            )

        # Patient ID / UHID
        pid_val = FieldValue(status=FieldStatus.NOT_FOUND)
        if "patient_id" in kv_map and kv_map["patient_id"].value:
            kv = kv_map["patient_id"]
            pid_val = FieldValue(
                value=kv.value,
                raw_text=kv.value,
                status=FieldStatus.EXTRACTED,
                provenance=kv.provenance,
            )

        # Age
        age_val = FieldValue(status=FieldStatus.NOT_FOUND)
        if "age" in kv_map and kv_map["age"].value:
            kv = kv_map["age"]
            # Clean numeric age if mixed with 'Yrs' or 'Years'
            raw_age = kv.value
            age_clean = re.sub(r"[^\d]", "", raw_age)
            val = int(age_clean) if age_clean else raw_age
            age_val = FieldValue(
                value=val,
                raw_text=raw_age,
                status=FieldStatus.EXTRACTED,
                provenance=kv.provenance,
            )

        # Gender
        gender_val = FieldValue(status=FieldStatus.NOT_FOUND)
        if "gender" in kv_map and kv_map["gender"].value:
            kv = kv_map["gender"]
            raw_g = kv.value.strip().lower()
            norm_g = "Male" if raw_g.startswith("m") else ("Female" if raw_g.startswith("f") else kv.value)
            gender_val = FieldValue(
                value=norm_g,
                raw_text=kv.value,
                status=FieldStatus.EXTRACTED,
                provenance=kv.provenance,
            )
        elif "age" in kv_map and "/" in kv_map["age"].value:
            # Often formatted as '45 / M' in age field
            parts = kv_map["age"].value.split("/")
            if len(parts) >= 2:
                g_text = parts[1].strip().lower()
                norm_g = "Male" if g_text.startswith("m") else ("Female" if g_text.startswith("f") else None)
                if norm_g:
                    gender_val = FieldValue(
                        value=norm_g,
                        raw_text=parts[1].strip(),
                        status=FieldStatus.EXTRACTED,
                        provenance=kv_map["age"].provenance,
                    )

        return PatientEntities(
            name=name_val,
            patient_id=pid_val,
            age=age_val,
            gender=gender_val,
        )

    @classmethod
    def _extract_hospital(
        cls,
        document_id: str,
        pages: List[RawPageInput],
        kv_map: Dict[str, KeyValueField]
    ) -> HospitalEntities:
        h_name_val = FieldValue(status=FieldStatus.NOT_FOUND)
        if "hospital_name" in kv_map and kv_map["hospital_name"].value:
            kv = kv_map["hospital_name"]
            h_name_val = FieldValue(
                value=kv.value,
                raw_text=kv.value,
                status=FieldStatus.EXTRACTED,
                provenance=kv.provenance,
            )
        else:
            # Fallback: check first page top 3 lines for "Hospital", "Clinic", "Healthcare", "Medical Center"
            if pages and pages[0].raw_text:
                top_lines = pages[0].raw_text.split("\n")[:4]
                for line in top_lines:
                    trimmed = line.strip()
                    if re.search(r"\b(hospital|clinic|healthcare|medical\s+centre?|nursing\s+home)\b", trimmed, re.IGNORECASE):
                        prov = ProvenanceTracer.create_provenance(
                            document_id=document_id,
                            page_number=1,
                            source_text=trimmed,
                            extraction_method="top_line_header_heuristic",
                            confidence=ConfidenceLevel.MEDIUM,
                            confidence_score=0.75,
                        )
                        h_name_val = FieldValue(
                            value=trimmed,
                            raw_text=trimmed,
                            status=FieldStatus.EXTRACTED,
                            provenance=prov,
                        )
                        break

        # Doctor Name
        doc_val = FieldValue(status=FieldStatus.NOT_FOUND)
        if "doctor_name" in kv_map and kv_map["doctor_name"].value:
            kv = kv_map["doctor_name"]
            doc_val = FieldValue(
                value=kv.value,
                raw_text=kv.value,
                status=FieldStatus.EXTRACTED,
                provenance=kv.provenance,
            )
        else:
            # Search for Dr. in text
            for page in pages:
                match = re.search(r"\b(Dr\.?\s+[A-Za-z\.\s]{2,35}?)(?:,|\n|$)", page.raw_text, re.IGNORECASE)
                if match:
                    dr_text = match.group(1).strip()
                    prov = ProvenanceTracer.create_provenance(
                        document_id=document_id,
                        page_number=page.page_number,
                        source_text=dr_text,
                        extraction_method="regex_dr_pattern",
                        confidence=ConfidenceLevel.MEDIUM,
                        confidence_score=0.70,
                    )
                    doc_val = FieldValue(
                        value=dr_text,
                        raw_text=dr_text,
                        status=FieldStatus.EXTRACTED,
                        provenance=prov,
                    )
                    break

        # Address & Registration Number
        addr_val = FieldValue(status=FieldStatus.NOT_FOUND)
        reg_val = FieldValue(status=FieldStatus.NOT_FOUND)
        dep_val = FieldValue(status=FieldStatus.NOT_FOUND)

        if "hospital_address" in kv_map and kv_map["hospital_address"].value:
            addr_val = FieldValue(
                value=kv_map["hospital_address"].value,
                raw_text=kv_map["hospital_address"].value,
                status=FieldStatus.EXTRACTED,
                provenance=kv_map["hospital_address"].provenance,
            )

        if "registration_number" in kv_map and kv_map["registration_number"].value:
            reg_val = FieldValue(
                value=kv_map["registration_number"].value,
                raw_text=kv_map["registration_number"].value,
                status=FieldStatus.EXTRACTED,
                provenance=kv_map["registration_number"].provenance,
            )

        if "department" in kv_map and kv_map["department"].value:
            dep_val = FieldValue(
                value=kv_map["department"].value,
                raw_text=kv_map["department"].value,
                status=FieldStatus.EXTRACTED,
                provenance=kv_map["department"].provenance,
            )

        return HospitalEntities(
            name=h_name_val,
            address=addr_val,
            registration_number=reg_val,
            doctor_name=doc_val,
            department=dep_val,
        )

    @classmethod
    def _extract_encounter(
        cls,
        document_id: str,
        pages: List[RawPageInput],
        kv_map: Dict[str, KeyValueField],
        sections: List[DocumentSection]
    ) -> EncounterEntities:
        # Admission Date
        adm_val = FieldValue(status=FieldStatus.NOT_FOUND)
        if "admission_date" in kv_map and kv_map["admission_date"].value:
            kv = kv_map["admission_date"]
            norm_date, status, notes = normalize_date_string(kv.value, prefer_day_first=True)
            adm_val = FieldValue(
                value=norm_date or kv.value,
                raw_text=kv.value,
                status=status if norm_date else FieldStatus.AMBIGUOUS,
                provenance=kv.provenance,
                notes=notes,
            )

        # Discharge Date
        dis_val = FieldValue(status=FieldStatus.NOT_FOUND)
        if "discharge_date" in kv_map and kv_map["discharge_date"].value:
            kv = kv_map["discharge_date"]
            norm_date, status, notes = normalize_date_string(kv.value, prefer_day_first=True)
            dis_val = FieldValue(
                value=norm_date or kv.value,
                raw_text=kv.value,
                status=status if norm_date else FieldStatus.AMBIGUOUS,
                provenance=kv.provenance,
                notes=notes,
            )

        # Diagnosis strictly as documented in source
        diag_val = FieldValue(status=FieldStatus.NOT_FOUND)
        if "diagnosis" in kv_map and kv_map["diagnosis"].value:
            kv = kv_map["diagnosis"]
            diag_val = FieldValue(
                value=kv.value,
                raw_text=kv.value,
                status=FieldStatus.EXTRACTED,
                provenance=kv.provenance,
                notes="Extracted from key-value pair. Not a verified medical diagnosis."
            )
        else:
            # Check sections for diagnosis
            diag_sec = next((s for s in sections if s.normalized_heading in ("diagnosis", "provisional_diagnosis")), None)
            if diag_sec and diag_sec.content:
                diag_val = FieldValue(
                    value=diag_sec.content,
                    raw_text=diag_sec.content,
                    status=FieldStatus.EXTRACTED,
                    provenance=diag_sec.provenance,
                    notes="Extracted verbatim from document section. Not a verified medical diagnosis."
                )

        # Procedure / Treatment text strictly as documented
        proc_val = FieldValue(status=FieldStatus.NOT_FOUND)
        proc_sec = next((s for s in sections if s.normalized_heading == "treatment_and_procedures"), None)
        if proc_sec and proc_sec.content:
            proc_val = FieldValue(
                value=proc_sec.content,
                raw_text=proc_sec.content,
                status=FieldStatus.EXTRACTED,
                provenance=proc_sec.provenance,
                notes="Extracted verbatim from document section. Not medically verified."
            )

        return EncounterEntities(
            admission_date=adm_val,
            discharge_date=dis_val,
            procedure_date=FieldValue(status=FieldStatus.NOT_FOUND),
            visit_date=FieldValue(status=FieldStatus.NOT_FOUND),
            diagnosis_text=diag_val,
            procedure_text=proc_val,
        )

    @classmethod
    def _extract_financial(
        cls,
        document_id: str,
        pages: List[RawPageInput],
        kv_map: Dict[str, KeyValueField],
        itemized_charges: List[ItemizedCharge]
    ) -> FinancialEntities:
        # Invoice number
        inv_val = FieldValue(status=FieldStatus.NOT_FOUND)
        if "invoice_number" in kv_map and kv_map["invoice_number"].value:
            kv = kv_map["invoice_number"]
            inv_val = FieldValue(
                value=kv.value,
                raw_text=kv.value,
                status=FieldStatus.EXTRACTED,
                provenance=kv.provenance,
            )

        # Bill date
        bill_dt_val = FieldValue(status=FieldStatus.NOT_FOUND)
        if "bill_date" in kv_map and kv_map["bill_date"].value:
            kv = kv_map["bill_date"]
            norm_date, status, notes = normalize_date_string(kv.value, prefer_day_first=True)
            bill_dt_val = FieldValue(
                value=norm_date or kv.value,
                raw_text=kv.value,
                status=status if norm_date else FieldStatus.AMBIGUOUS,
                provenance=kv.provenance,
                notes=notes,
            )

        # Total amount & Currency
        tot_val = FieldValue(status=FieldStatus.NOT_FOUND)
        curr_val = FieldValue(status=FieldStatus.NOT_FOUND)

        if "total_amount" in kv_map and kv_map["total_amount"].value:
            kv = kv_map["total_amount"]
            amt, curr, status, notes = normalize_amount_string(kv.value)
            tot_val = FieldValue(
                value=amt,
                raw_text=kv.value,
                status=status if amt is not None else FieldStatus.EXTRACTION_ERROR,
                provenance=kv.provenance,
                notes=notes,
            )
            if curr:
                curr_val = FieldValue(
                    value=curr,
                    raw_text=curr,
                    status=FieldStatus.EXTRACTED,
                    provenance=kv.provenance,
                )

        # Paid amount
        paid_val = FieldValue(status=FieldStatus.NOT_FOUND)
        if "paid_amount" in kv_map and kv_map["paid_amount"].value:
            kv = kv_map["paid_amount"]
            amt, curr, status, notes = normalize_amount_string(kv.value)
            paid_val = FieldValue(
                value=amt,
                raw_text=kv.value,
                status=status if amt is not None else FieldStatus.EXTRACTION_ERROR,
                provenance=kv.provenance,
                notes=notes,
            )

        # Balance amount
        bal_val = FieldValue(status=FieldStatus.NOT_FOUND)
        if "balance_amount" in kv_map and kv_map["balance_amount"].value:
            kv = kv_map["balance_amount"]
            amt, curr, status, notes = normalize_amount_string(kv.value)
            bal_val = FieldValue(
                value=amt,
                raw_text=kv.value,
                status=status if amt is not None else FieldStatus.EXTRACTION_ERROR,
                provenance=kv.provenance,
                notes=notes,
            )

        return FinancialEntities(
            invoice_number=inv_val,
            bill_date=bill_dt_val,
            total_amount=tot_val,
            paid_amount=paid_val,
            balance_amount=bal_val,
            currency=curr_val,
            itemized_charges=itemized_charges,
        )
