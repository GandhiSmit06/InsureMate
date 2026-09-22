"""
Section and heading detector for medical and insurance documents.
Detects semantic sections (e.g. Diagnosis, Clinical Summary, Itemized Charges).
"""

import re
from typing import List, Tuple, Optional
from ..schemas.output_schema import DocumentSection
from ..schemas.input_schema import RawPageInput
from ..provenance.tracer import ProvenanceTracer
from ..schemas.common import ConfidenceLevel

# Standard medical and insurance section patterns
KNOWN_SECTION_PATTERNS = [
    (r"(?:final\s+)?diagnosis(?:\s*[:\-])?", "diagnosis"),
    (r"provisional\s+diagnosis(?:\s*[:\-])?", "provisional_diagnosis"),
    (r"clinical\s+summary|brief\s+history|chief\s+complaints?", "clinical_summary"),
    (r"admission\s+details|patient\s+details|admission\s+record", "admission_details"),
    (r"treatment\s+given|procedure[s]?\s+performed|surgical\s+notes", "treatment_and_procedures"),
    (r"investigations?|diagnostic\s+findings?|lab\s+reports?", "investigations_and_lab"),
    (r"itemized\s+charges?|bill\s+breakdown|summary\s+of\s+charges|billing\s+details", "itemized_charges"),
    (r"discharge\s+advice|advice\s+on\s+discharge|follow\s*up\s+advice", "discharge_advice"),
    (r"doctor['’]?s\s+notes|consultant\s+notes|physician\s+remarks", "doctor_notes"),
    (r"insurance\s+details|tpa\s+details|pre[\s\-]?auth(?:orization)?\s+details", "insurance_and_policy"),
]


class SectionDetector:
    """Detects headings and segments document pages into semantic sections."""

    @classmethod
    def detect_sections(
        cls,
        document_id: str,
        pages: List[RawPageInput]
    ) -> List[DocumentSection]:
        sections: List[DocumentSection] = []

        for page in pages:
            lines = page.raw_text.split("\n")
            current_heading: Optional[str] = None
            current_norm_heading: Optional[str] = None
            current_content_lines: List[str] = []
            heading_line_idx = 0

            for idx, raw_line in enumerate(lines):
                line = raw_line.strip()
                if not line:
                    continue

                # Check if this line looks like a section header
                detected_norm = cls._match_heading(line)
                if detected_norm:
                    # Save previous section if exists
                    if current_heading and current_content_lines:
                        content_text = "\n".join(current_content_lines).strip()
                        if content_text:
                            prov = ProvenanceTracer.create_provenance(
                                document_id=document_id,
                                page_number=page.page_number,
                                source_text=current_heading + "\n" + content_text[:150],
                                extraction_method="layout_and_heading_heuristic",
                                confidence=ConfidenceLevel.HIGH,
                                confidence_score=0.90,
                                bounding_box=ProvenanceTracer.find_block_bounding_box(current_heading, page.blocks),
                            )
                            sections.append(DocumentSection(
                                heading=current_heading,
                                normalized_heading=current_norm_heading,
                                content=content_text,
                                page_number=page.page_number,
                                provenance=prov,
                            ))

                    current_heading = line
                    current_norm_heading = detected_norm
                    current_content_lines = []
                    heading_line_idx = idx
                else:
                    if current_heading:
                        current_content_lines.append(line)

            # Flush trailing section on page
            if current_heading and current_content_lines:
                content_text = "\n".join(current_content_lines).strip()
                if content_text:
                    prov = ProvenanceTracer.create_provenance(
                        document_id=document_id,
                        page_number=page.page_number,
                        source_text=current_heading + "\n" + content_text[:150],
                        extraction_method="layout_and_heading_heuristic",
                        confidence=ConfidenceLevel.HIGH,
                        confidence_score=0.90,
                        bounding_box=ProvenanceTracer.find_block_bounding_box(current_heading, page.blocks),
                    )
                    sections.append(DocumentSection(
                        heading=current_heading,
                        normalized_heading=current_norm_heading,
                        content=content_text,
                        page_number=page.page_number,
                        provenance=prov,
                    ))

        return sections

    @staticmethod
    def _match_heading(line: str) -> Optional[str]:
        """Matches a line against known heading patterns."""
        # Headings are typically relatively short (< 60 chars)
        if len(line) > 70:
            return None

        # Check against known patterns
        for pattern, norm_name in KNOWN_SECTION_PATTERNS:
            if re.match(r"^" + pattern + r"$", line, re.IGNORECASE) or re.match(r"^###?\s*" + pattern, line, re.IGNORECASE):
                return norm_name
            # Also match if ends with colon or all caps
            if re.match(r"^" + pattern + r"\s*:", line, re.IGNORECASE):
                return norm_name

        # Generic all-caps short heading check (e.g. "CLINICAL SUMMARY")
        if line.isupper() and 4 < len(line) < 40 and not line.isdigit():
            for pattern, norm_name in KNOWN_SECTION_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    return norm_name

        return None
