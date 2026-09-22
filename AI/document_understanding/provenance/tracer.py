"""
Provenance and evidence traceability tracer.
Binds extracted values to source pages, verbatim text, layout blocks, and extraction methods.
"""

from typing import Optional, List
from ..schemas.common import Provenance, BoundingBox, ConfidenceLevel
from ..schemas.input_schema import RawBlockInput


class ProvenanceTracer:
    """Creates and resolves traceable evidence for extracted document fields."""

    @staticmethod
    def create_provenance(
        document_id: str,
        page_number: int,
        source_text: str,
        extraction_method: str,
        confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
        confidence_score: Optional[float] = None,
        bounding_box: Optional[BoundingBox] = None,
    ) -> Provenance:
        """
        Creates a Provenance object without fabricating any ungrounded locations.
        """
        clean_source = source_text.strip() if source_text else ""
        return Provenance(
            document_id=document_id,
            page_number=page_number,
            source_text=clean_source[:500],  # Bound source excerpt length
            bounding_box=bounding_box,
            extraction_method=extraction_method,
            confidence=confidence,
            confidence_score=confidence_score,
        )

    @staticmethod
    def find_block_bounding_box(
        target_text: str,
        blocks: List[RawBlockInput]
    ) -> Optional[BoundingBox]:
        """
        Finds the bounding box of a layout block that contains target_text.
        Returns None if target_text is not found or if blocks have no bbox.
        """
        if not target_text or not blocks:
            return None

        target_lower = target_text.strip().lower()
        for block in blocks:
            if block.bbox and target_lower in block.text.lower():
                return block.bbox

        return None
