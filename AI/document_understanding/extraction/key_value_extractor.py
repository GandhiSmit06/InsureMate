"""
Key-Value pair extractor for semi-structured forms, invoices, and medical summaries.
Supports single-line and multi-field lines (e.g. 'Age: 45  Gender: Male  DOA: 12/03/2024').
"""

import re
from typing import List, Tuple, Optional
from ..schemas.output_schema import KeyValueField
from ..schemas.input_schema import RawPageInput
from ..schemas.common import FieldStatus, ConfidenceLevel
from ..provenance.tracer import ProvenanceTracer

# Mapping of common label regexes to normalized keys
LABEL_MAPPINGS = [
    (r"registration\s*(?:no|number)|reg\.?\s*(?:no|number)", "registration_number"),
    (r"patient(?:\s*['’]?s)?\s*name|name\s+of\s+patient|pt\.?\s*name|name", "patient_name"),
    (r"patient\s*id|uhid|mrn|ip\s*(?:no|number)|indoor\s*p\.?\s*no", "patient_id"),
    (r"age(?:\s*\/\s*sex)?", "age"),
    (r"gender|sex", "gender"),
    (r"^(?:name\s+of\s+)?(?:hospital|clinic|nursing\s+home)(?:\s*name)?$|hospital\s*name|clinic\s*name", "hospital_name"),
    (r"doctor(?:\s*['’]?s)?\s*name|treating\s*doctor|consultant(?:\s+physician)?|referred\s*by", "doctor_name"),
    (r"date\s*of\s*admission|admission\s*date|doa\s*\/\s*toa|\bdoa\b", "admission_date"),
    (r"date\s*of\s*discharge|discharge\s*date|dod\s*\/\s*tod|\bdod\b", "discharge_date"),
    (r"contact(?:\s*no|\s*number)?|phone(?:\s*no|\s*number)?|mobile(?:\s*no|\s*number)?|\bmob\b", "contact_number"),
    (r"address|permanent\s+address|residence|add", "patient_address"),
    (r"invoice\s*(?:no|number)|bill\s*(?:no|number)", "invoice_number"),
    (r"invoice\s*date|bill\s*date", "bill_date"),
    (r"total\s*amount|gross\s*amount|bill\s*total|net\s*amount", "total_amount"),
    (r"advance\s*paid|paid\s*amount|amount\s*received", "paid_amount"),
    (r"balance\s*(?:amount|due)|amount\s*due|net\s*payable", "balance_amount"),
    (r"(?:final\s+)?diagnosis|provisional\s+d(?:iagnosis)?", "diagnosis"),
    (r"policy\s*(?:no|number)|tpa\s*(?:id|card)", "policy_number"),
]


class KeyValueExtractor:
    """Extracts key-value fields from pages with source provenance."""

    @classmethod
    def extract_key_values(
        cls,
        document_id: str,
        pages: List[RawPageInput]
    ) -> List[KeyValueField]:
        results: List[KeyValueField] = []
        counter = 1

        for page in pages:
            lines = page.raw_text.split("\n")
            for line in lines:
                clean_line = line.strip()
                if not clean_line:
                    continue

                # Split line into key-value candidate chunks (handling multi-column and multiple colons)
                chunks = cls._split_into_kv_chunks(clean_line)
                for chunk in chunks:
                    chunk = chunk.strip()
                    if not chunk:
                        continue

                    kv_pair = cls._parse_single_kv(chunk)
                    if kv_pair:
                        label, value, norm_key = kv_pair
                        field_id = f"kv_{document_id}_p{page.page_number}_{counter}"
                        counter += 1

                        prov = ProvenanceTracer.create_provenance(
                            document_id=document_id,
                            page_number=page.page_number,
                            source_text=chunk,
                            extraction_method="key_value_heuristic",
                            confidence=ConfidenceLevel.HIGH,
                            confidence_score=0.92,
                            bounding_box=ProvenanceTracer.find_block_bounding_box(chunk, page.blocks),
                        )

                        results.append(KeyValueField(
                            field_id=field_id,
                            label=label,
                            normalized_key=norm_key,
                            value=value,
                            status=FieldStatus.EXTRACTED if value else FieldStatus.NOT_FOUND,
                            provenance=prov,
                        ))

        return results

    @staticmethod
    def _parse_single_kv(text: str) -> Optional[Tuple[str, str, str]]:
        """
        Attempts to parse a label-value pair separated by ':', '-', or known form prefixes.
        Returns (label, value, normalized_key) or None.
        """
        # Strip stray leading punctuation often pushed from previous column boundaries
        text = re.sub(r"^[:\-\|\s]+", "", text).strip()
        if not text:
            return None

        # 1. Match label : value or label - value
        match = re.match(r"^([^:\-]{2,40})[:\-]\s*(.+)$", text)
        if not match:
            # 2. Fallback: match colon-less or trailing-colon form fields (e.g. 'Name Parth Maulikkumar :', 'Name Parth Maulikkumar')
            match = re.match(
                r"^(?:[A-Z0-9][\.\)]\s*)?(name\s+of\s+patient|patient(?:\s*['’]?s)?\s*name|pt\.?\s*name|name|address|add|doa\s*\/\s*toa|dod\s*\/\s*tod|provisional\s+d(?:iagnosis)?)\s+(.+?)[:\-]?$",
                text,
                re.IGNORECASE,
            )

        if not match:
            return None

        raw_label = match.group(1).strip()
        raw_val = match.group(2).strip()

        # Clean bullets/indexes like "A. ", "1. ", "(1) ", "). " from label
        raw_label = re.sub(r"^[\W\d_]+\s*", "", raw_label).strip()

        # Discard if label has too many words or looks like a full sentence
        if len(raw_label.split()) > 6 or raw_label.endswith("."):
            return None

        # Sanitize value: strip leading/trailing punctuation and quotation marks
        raw_val = re.sub(r"^[:\-\s/_.~*,|]+|[:\-\s/_.~*,|]+$", "", raw_val).strip()

        # Reject empty or purely punctuation/placeholder values
        if not raw_val or raw_val.lower() in (
            "//", "/ /", "/  /", "---", "- -", "...", "..",
            "nil", "none", "n/a", "na", "null", "not available"
        ):
            return None

        # If value has trailing adjacent column headers (e.g. 'parth maulikkumar : Age/Sex'), trim them
        raw_val = re.sub(
            r"\s+[:\-]?\s*(?:age(?:\/sex)?|gender|sex|uhid|ipd|doa|dod|dr)\s*[:\-]?.*$",
            "",
            raw_val,
            flags=re.IGNORECASE
        ).strip()

        if not raw_val:
            return None

        # If label contains pipe, e.g. "Consultant Physician | Reg. No", resolve key using rightmost segment
        label_for_norm = raw_label.split("|")[-1].strip() if "|" in raw_label else raw_label

        # Normalize key with strict pattern group matching
        norm_key = "unknown_field"
        for pattern, k in LABEL_MAPPINGS:
            if re.search(r"\b(?:" + pattern + r")\b", label_for_norm, re.IGNORECASE):
                norm_key = k
                break

        if norm_key == "unknown_field":
            norm_key = re.sub(r"[^a-zA-Z0-9]+", "_", label_for_norm.lower()).strip("_")

        return raw_label, raw_val, norm_key

    @classmethod
    def _split_into_kv_chunks(cls, line: str) -> List[str]:
        """Splits a line into candidate key-value chunks, handling columns and multi-colon lines."""
        raw_chunks = re.split(r"\s{2,}", line)
        refined_chunks = []
        for chunk in raw_chunks:
            chunk = chunk.strip()
            if not chunk:
                continue
            # If chunk still contains multiple colons (e.g. "Label1: Val1 Label2: Val2")
            if chunk.count(":") > 1:
                sub_parts = re.split(r"(?<=\S)\s+(?=[A-Za-z0-9/]{2,15}:)", chunk)
                refined_chunks.extend(p.strip() for p in sub_parts if p.strip())
            else:
                refined_chunks.append(chunk)
        return refined_chunks
