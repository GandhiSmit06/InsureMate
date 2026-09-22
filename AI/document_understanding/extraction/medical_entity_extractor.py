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
        # Index all key-values by normalized key
        kv_groups: Dict[str, List[KeyValueField]] = {}
        for kv in key_values:
            kv_groups.setdefault(kv.normalized_key, []).append(kv)

        # Select the best candidate for each key to prevent noisy later pages
        # (e.g. handwritten nurse charts) from overwriting clean early-page forms
        kv_map: Dict[str, KeyValueField] = {}
        for k, items in kv_groups.items():
            best = cls._select_best_candidate(k, items)
            if best:
                kv_map[k] = best

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
    def _select_best_candidate(cls, key: str, items: List[KeyValueField]) -> Optional[KeyValueField]:
        """Selects highest quality key-value field candidate using page priority and value heuristics."""
        if not items:
            return None
        if len(items) == 1:
            return items[0]

        best_item = None
        best_score = -999.0

        for item in items:
            val = (item.value or "").strip()
            if not val:
                continue

            score = 1.0
            pg = item.provenance.page_number if item.provenance else 1

            # Early page priority (Pages 1-4 are usually Admission/Discharge forms or Invoices)
            if pg <= 4:
                score += 1.5 - (pg * 0.1)
            elif pg > 10:
                score -= 1.0

            if key == "patient_name":
                clean_v = re.sub(r"^[:\-\s/_.~*,|]+|[:\-\s/_.~*,|]+$", "", val).strip()
                clean_v = re.sub(r"\s+[:\-]?\s*(?:age(?:\/sex)?|gender|sex|uhid|ipd|doa|dod|dr|ame)\b.*$", "", clean_v, flags=re.IGNORECASE).strip()
                words = [w for w in re.split(r"[\s\.\-]+", clean_v) if len(w) > 1 and w.isalpha()]
                if len(words) >= 2:
                    score += 3.0
                elif len(words) == 1:
                    score += 0.5
                else:
                    score -= 5.0
                # Heavily penalize relative/signee fields
                if re.search(r"\b(relative|mother|father|relation|wife|husband|sign|mother\))\b", val, re.IGNORECASE):
                    score -= 15.0
                if re.search(r"^[A-Z][\-\.][A-Za-z]", clean_v):
                    score -= 6.0
                if any(c.isdigit() for c in clean_v):
                    score -= 3.0

            elif key == "hospital_name":
                if re.search(r"\b(hospital|clinic|healthcare|centre|center|nursing\s+home)\b", val, re.IGNORECASE):
                    score += 2.0
                if len(val) < 4 or re.match(r"^[\d\s/\-]+$", val):
                    score -= 10.0

            elif key in ("admission_date", "discharge_date", "bill_date"):
                norm_d, st, _ = normalize_date_string(val, prefer_day_first=True)
                if norm_d:
                    score += 2.0
                else:
                    score -= 5.0
                if re.match(r"^\d{8,12}$", re.sub(r"\s+", "", val)):
                    score -= 10.0

            elif key == "doctor_name":
                if re.search(r"\b(Dr\.?|Doctor|Physician|Consultant)\b", val, re.IGNORECASE):
                    score += 2.0

            if score > best_score:
                best_score = score
                best_item = item

        return best_item or items[0]

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
            clean_name = re.sub(r"^[:\-\s/_.~*,|]+|[:\-\s/_.~*,|]+$", "", kv.value).strip()
            clean_name = re.sub(r"\s+[:\-]?\s*(?:age(?:\/sex)?|gender|sex|uhid|ipd|doa|dod|dr|ame)\b.*$", "", clean_name, flags=re.IGNORECASE).strip()
            if clean_name.islower() or clean_name.isupper():
                clean_name = " ".join(w.capitalize() for w in clean_name.split())

            name_val = FieldValue(
                value=clean_name,
                raw_text=kv.value,
                status=FieldStatus.EXTRACTED if clean_name else FieldStatus.NOT_FOUND,
                provenance=kv.provenance,
            )

        # Patient ID / UHID
        pid_val = FieldValue(status=FieldStatus.NOT_FOUND)
        if "patient_id" in kv_map and kv_map["patient_id"].value:
            kv = kv_map["patient_id"]
            clean_pid = re.sub(r"^[^\w]+|[^\w]+$", "", kv.value).strip()
            pid_val = FieldValue(
                value=clean_pid or kv.value,
                raw_text=kv.value,
                status=FieldStatus.EXTRACTED,
                provenance=kv.provenance,
            )
        else:
            # Fallback search for Indoor P. No or UHID or IPD No across early pages
            for page in pages[:5]:
                m_pid = re.search(r"\b(?:Indoor\s*P\.?\s*No\.?|IPD\s*(?:No|Number)?|UHID|MRN|CL\s*No\.?)\s*[:\-]?\s*([A-Za-z0-9\/\-]+)", page.raw_text, re.IGNORECASE)
                if m_pid:
                    pid_text = m_pid.group(1).strip()
                    prov = ProvenanceTracer.create_provenance(
                        document_id=document_id,
                        page_number=page.page_number,
                        source_text=m_pid.group(0),
                        extraction_method="regex_patient_id_pattern",
                        confidence=ConfidenceLevel.HIGH,
                        confidence_score=0.90,
                    )
                    pid_val = FieldValue(
                        value=pid_text,
                        raw_text=m_pid.group(0),
                        status=FieldStatus.EXTRACTED,
                        provenance=prov,
                    )
                    break

        # Age
        age_val = FieldValue(status=FieldStatus.NOT_FOUND)
        if "age" in kv_map and kv_map["age"].value:
            kv = kv_map["age"]
            raw_age = kv.value
            # Match leading digits or digits before slash/pipe (e.g. '18|m' -> 18)
            m_age = re.search(r"\b(\d{1,3})\b", raw_age)
            val = int(m_age.group(1)) if m_age else raw_age
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
        elif "age" in kv_map and ("/" in kv_map["age"].value or "|" in kv_map["age"].value):
            # Formatted as '18|m' or '45 / M' in age field
            raw_combined = kv_map["age"].value.replace("|", "/")
            parts = raw_combined.split("/")
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

        if "hospital_name" in kv_map and kv_map["hospital_name"].value:
            kv = kv_map["hospital_name"]
            val = kv.value.strip()
            if len(val) >= 4 and not re.match(r"^[\d\s/\-]+$", val):
                if val.isupper():
                    val = " ".join(w.capitalize() for w in val.split())
                h_name_val = FieldValue(
                    value=val,
                    raw_text=kv.value,
                    status=FieldStatus.EXTRACTED,
                    provenance=kv.provenance,
                )

        # Fallback: scan early pages (pages 1 to 5) for hospital headers and stamps
        if h_name_val.status != FieldStatus.EXTRACTED:
            for page in pages[:5]:
                if not page.raw_text:
                    continue
                lines = [l.strip() for l in page.raw_text.split("\n")]
                for i, line in enumerate(lines):
                    trimmed = line.strip()
                    m = re.search(r"\b([A-Za-z\s\.\']{2,30}\s+(?:hospital|clinic|nursing\s+home|medical\s+centre?))\b", trimmed, re.IGNORECASE)
                    if m:
                        matched_h = m.group(1).strip()
                        matched_h = re.sub(r"^[A-Z]{2,4}\s+", "", matched_h).strip()
                        if not re.search(r"\b(date|no|form|bill|admission)\b", matched_h, re.IGNORECASE) and len(matched_h) >= 5:
                            h_title = " ".join(w.capitalize() for w in matched_h.split())
                            prov = ProvenanceTracer.create_provenance(
                                document_id=document_id,
                                page_number=page.page_number,
                                source_text=trimmed,
                                extraction_method="hospital_header_stamp_heuristic",
                                confidence=ConfidenceLevel.HIGH,
                                confidence_score=0.92,
                            )
                            h_name_val = FieldValue(
                                value=h_title,
                                raw_text=trimmed,
                                status=FieldStatus.EXTRACTED,
                                provenance=prov,
                            )
                            # Extract hospital address from subsequent lines of the stamp
                            if addr_val.status != FieldStatus.EXTRACTED and i + 1 < len(lines):
                                addr_parts = []
                                for j in range(i + 1, min(i + 3, len(lines))):
                                    clean_l = re.sub(r"(?:MOB|TEL|PHONE|EMAIL|MO).*$", "", lines[j], flags=re.IGNORECASE).strip(" ,.:-")
                                    if clean_l and len(clean_l) > 3 and not re.search(r"^\d+$", clean_l):
                                        addr_parts.append(clean_l)
                                if addr_parts:
                                    h_addr = ", ".join(addr_parts)
                                    addr_val = FieldValue(
                                        value=h_addr,
                                        raw_text="\n".join(lines[i+1:min(i+3, len(lines))]),
                                        status=FieldStatus.EXTRACTED,
                                        provenance=prov,
                                    )
                            break
                if h_name_val.status == FieldStatus.EXTRACTED:
                    break

        # Doctor Name
        doc_val = FieldValue(status=FieldStatus.NOT_FOUND)
        if "doctor_name" in kv_map and kv_map["doctor_name"].value:
            kv = kv_map["doctor_name"]
            val = kv.value.strip()
            if val.isupper():
                val = " ".join(w.capitalize() for w in val.split())
            doc_val = FieldValue(
                value=val,
                raw_text=kv.value,
                status=FieldStatus.EXTRACTED,
                provenance=kv.provenance,
            )
        else:
            # Search for Dr. in early pages (pages 1 to 5)
            for page in pages[:5]:
                match = re.search(r"\b(Dr\.?\s+[A-Za-z\.\s]{2,35}?)(?:,|\n|$|M\.D|MBBS)", page.raw_text, re.IGNORECASE)
                if match:
                    dr_text = match.group(1).strip()
                    if dr_text.isupper():
                        dr_text = " ".join(w.capitalize() for w in dr_text.split())
                    prov = ProvenanceTracer.create_provenance(
                        document_id=document_id,
                        page_number=page.page_number,
                        source_text=dr_text,
                        extraction_method="regex_dr_pattern",
                        confidence=ConfidenceLevel.HIGH,
                        confidence_score=0.85,
                    )
                    doc_val = FieldValue(
                        value=dr_text,
                        raw_text=dr_text,
                        status=FieldStatus.EXTRACTED,
                        provenance=prov,
                    )
                    break

        # Address & Registration Number
        if addr_val.status != FieldStatus.EXTRACTED and "hospital_address" in kv_map and kv_map["hospital_address"].value:
            addr_val = FieldValue(
                value=kv_map["hospital_address"].value,
                raw_text=kv_map["hospital_address"].value,
                status=FieldStatus.EXTRACTED,
                provenance=kv_map["hospital_address"].provenance,
            )
        elif addr_val.status != FieldStatus.EXTRACTED:
            best_addr = None
            best_score = -1
            best_prov = None
            best_raw = ""

            for page in pages[:5]:
                lines = [l.strip() for l in page.raw_text.split("\n")]
                for i, line in enumerate(lines):
                    if re.search(r"\b(hospital|clinic|nursing\s+home)\b", line, re.IGNORECASE):
                        addr_parts = []
                        for j in range(i + 1, min(i + 4, len(lines))):
                            clean_l = re.sub(r"(?:MOB|TEL|PHONE|EMAIL|MO|MQB).*$", "", lines[j], flags=re.IGNORECASE).strip(" ,.:-")
                            clean_l = re.sub(r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4}\b", "", clean_l).strip(" ,.:-")
                            if clean_l and len(clean_l) > 3 and not re.search(r"^\d+$", clean_l):
                                addr_parts.append(clean_l)
                        if addr_parts:
                            cand = ", ".join(addr_parts)
                            score = len(cand)
                            if re.search(r"\b(road|rasta|station|nr|near|opp|street|circle|nagar|char\s*rasta)\b", cand, re.IGNORECASE):
                                score += 50
                            if score > best_score:
                                best_score = score
                                best_addr = cand
                                best_raw = "\n".join(lines[i+1:min(i+4, len(lines))])
                                best_prov = ProvenanceTracer.create_provenance(
                                    document_id=document_id,
                                    page_number=page.page_number,
                                    source_text=cand,
                                    extraction_method="hospital_address_stamp_heuristic",
                                    confidence=ConfidenceLevel.HIGH,
                                    confidence_score=0.90,
                                )

            if best_addr and best_prov:
                addr_val = FieldValue(
                    value=best_addr,
                    raw_text=best_raw,
                    status=FieldStatus.EXTRACTED,
                    provenance=best_prov,
                )

        if "registration_number" in kv_map and kv_map["registration_number"].value:
            reg_val = FieldValue(
                value=kv_map["registration_number"].value,
                raw_text=kv_map["registration_number"].value,
                status=FieldStatus.EXTRACTED,
                provenance=kv_map["registration_number"].provenance,
            )
        else:
            # Fallback search for Reg No on early pages (e.g. 'Reg. No.: G-15135')
            for page in pages[:5]:
                m_reg = re.search(r"\b(?:Reg\.?\s*(?:No\.?|Number)?|Registration\s*(?:No\.?|Number)?)\s*[:\-]\s*([A-Za-z0-9\-]+)", page.raw_text, re.IGNORECASE)
                if m_reg:
                    reg_text = m_reg.group(1).strip()
                    prov = ProvenanceTracer.create_provenance(
                        document_id=document_id,
                        page_number=page.page_number,
                        source_text=m_reg.group(0),
                        extraction_method="regex_reg_no_pattern",
                        confidence=ConfidenceLevel.HIGH,
                        confidence_score=0.90,
                    )
                    reg_val = FieldValue(
                        value=reg_text,
                        raw_text=reg_text,
                        status=FieldStatus.EXTRACTED,
                        provenance=prov,
                    )
                    break

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
