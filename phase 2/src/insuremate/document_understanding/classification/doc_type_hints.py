"""
Document type hint engine.
Provides explainable candidate document types with supporting signals and confidence scores.
Note: This provides structural hints for Phase 3; full evidence classification is handled in Phase 4.
"""

import re
from typing import List, Dict, Tuple
from ..schemas.output_schema import DocumentTypeHint, DocumentSection, KeyValueField, ExtractedTable
from ..schemas.input_schema import RawPageInput
from ..schemas.common import ConfidenceLevel

# Rule definitions: (candidate_type, weight, pattern, signal_description)
DOC_TYPE_RULES = {
    "hospital_invoice": [
        (r"\b(tax\s+invoice|hospital\s+invoice|final\s+bill|inpatient\s+bill|patient\s+bill)\b", 0.40, "Matched invoice title/heading"),
        (r"\b(invoice\s*(?:no|number)|bill\s*(?:no|number))\b", 0.25, "Contains invoice/bill number label"),
        (r"\b(total\s*amount|net\s*payable|gross\s*amount|subtotal)\b", 0.20, "Contains total amount / financial settlement summary"),
        (r"\b(itemized|charges|bed\s*charges|nursing\s*charges|pharmacy\s*charges)\b", 0.15, "Contains itemized hospital charges"),
    ],
    "discharge_summary": [
        (r"\b(discharge\s+summary|discharge\s+card|clinical\s+summary)\b", 0.45, "Matched discharge summary title"),
        (r"\b(date\s+of\s+discharge|d\.?o\.?d\.?|discharge\s+date)\b", 0.20, "Contains discharge date field"),
        (r"\b(diagnosis|chief\s+complaint|history\s+of\s+present\s+illness)\b", 0.20, "Contains clinical diagnosis/complaints section"),
        (r"\b(treatment\s+given|course\s+in\s+hospital|condition\s+at\s+discharge|discharge\s+advice)\b", 0.15, "Contains hospital course / discharge advice"),
    ],
    "prescription": [
        (r"\b(prescription|rx\b|medical\s+prescription)\b", 0.45, "Contains Rx or prescription marker"),
        (r"\b(tablet|tab\.|capsule|cap\.|syrup|syp\.|mg\b|dosage|od|bd|tds|sos)\b", 0.35, "Contains pharmaceutical dosage / frequency abbreviations"),
        (r"\b(dr\.|doctor|consultant|reg\s+no)\b", 0.20, "Contains prescribing doctor details"),
    ],
    "diagnostic_report": [
        (r"\b(investigation\s+report|diagnostic\s+report|laboratory\s+report|pathology\s+report|radiology\s+report|x-ray|ct\s+scan|mri\s+report)\b", 0.45, "Contains lab/radiology title"),
        (r"\b(test\s+name|result|reference\s+interval|biological\s+ref|specimen)\b", 0.30, "Contains test result / reference range markers"),
        (r"\b(normal\s+range|units|observed\s+value|impression)\b", 0.25, "Contains laboratory units or diagnostic impression"),
    ],
    "admission_document": [
        (r"\b(admission\s+record|admission\s+form|inpatient\s+registration|admission\s+slip)\b", 0.45, "Contains admission form title"),
        (r"\b(date\s+of\s+admission|d\.?o\.?a\.?|admitted\s+on)\b", 0.30, "Contains admission date/time"),
        (r"\b(ward\s+no|bed\s+no|room\s+category|admitting\s+doctor)\b", 0.25, "Contains ward/bed allocation details"),
    ],
    "insurance_form": [
        (r"\b(claim\s+form|pre[\s\-]?authorization\s+form|cashless\s+request|tpa\s+query)\b", 0.45, "Contains insurance claim/pre-auth title"),
        (r"\b(policy\s*(?:no|number)|member\s*id|tpa\s*(?:name|id)|sum\s*insured)\b", 0.35, "Contains policy/TPA member identification"),
        (r"\b(insurer|third\s+party\s+administrator|claimant\s+signature)\b", 0.20, "Contains insurance declaration terms"),
    ],
    "incident_document": [
        (r"\b(first\s+information\s+report|f\.?i\.?r\.?|police\s+intimation|medico[\s\-]legal\s+case|mlc)\b", 0.50, "Contains FIR or Medico-Legal Case (MLC) title"),
        (r"\b(police\s+station|incident\s+date|accident\s+details|time\s+of\s+incident)\b", 0.30, "Contains incident or police report details"),
        (r"\b(witness|investigating\s+officer|ipc\s+section)\b", 0.20, "Contains legal/investigative terms"),
    ],
}


class DocumentTypeHintEngine:
    """Evaluates text and structure against transparent rules to propose document type hints."""

    @classmethod
    def generate_hints(
        cls,
        pages: List[RawPageInput],
        sections: List[DocumentSection],
        key_values: List[KeyValueField],
        tables: List[ExtractedTable]
    ) -> List[DocumentTypeHint]:
        # Aggregate full document text
        full_text = " ".join([p.raw_text for p in pages])
        section_headings = " ".join([s.heading for s in sections])
        kv_labels = " ".join([kv.label for kv in key_values])
        search_corpus = f"{full_text} {section_headings} {kv_labels}"

        scores: Dict[str, Tuple[float, List[str]]] = {}

        for doc_type, rules in DOC_TYPE_RULES.items():
            total_score = 0.0
            signals: List[str] = []

            for pattern, weight, desc in rules:
                if re.search(pattern, search_corpus, re.IGNORECASE):
                    total_score += weight
                    signals.append(desc)

            if total_score > 0.15:
                scores[doc_type] = (round(min(total_score, 1.0), 2), signals)

        # Build list of hints sorted by score descending
        hints: List[DocumentTypeHint] = []
        for doc_type, (score, signals) in sorted(scores.items(), key=lambda item: item[1][0], reverse=True):
            if score >= 0.70:
                conf = ConfidenceLevel.HIGH
            elif score >= 0.40:
                conf = ConfidenceLevel.MEDIUM
            else:
                conf = ConfidenceLevel.LOW

            hints.append(DocumentTypeHint(
                candidate_type=doc_type,
                confidence=conf,
                confidence_score=score,
                supporting_signals=signals,
            ))

        # If no known type reached threshold, return unknown
        if not hints:
            hints.append(DocumentTypeHint(
                candidate_type="unknown",
                confidence=ConfidenceLevel.LOW,
                confidence_score=0.10,
                supporting_signals=["No recognizable medical or insurance structural patterns detected"],
            ))

        return hints
