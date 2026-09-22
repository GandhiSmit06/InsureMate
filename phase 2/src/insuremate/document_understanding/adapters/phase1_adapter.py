"""
Phase 1 Ingestion Adapter.
Validates, normalizes, and adapts raw data from Phase 1 into the standardized IngestedDocument model.
Supports IngestedDocument instances, dicts, and JSON strings.
"""

import json
from typing import Union, Dict, Any
from pydantic import ValidationError
from ..schemas.input_schema import IngestedDocument, RawPageInput
from ..exceptions import InvalidInputError
from ..normalization.text_normalizer import normalize_unicode_and_whitespace


class Phase1InputAdapter:
    """Adapts raw Phase 1 ingestion outputs into standardized IngestedDocument models."""

    @classmethod
    def adapt(cls, raw_input: Union[IngestedDocument, Dict[str, Any], str]) -> IngestedDocument:
        """
        Accepts IngestedDocument, dict, or JSON string and returns a validated IngestedDocument
        with normalized page text.
        """
        if isinstance(raw_input, IngestedDocument):
            doc = raw_input
        elif isinstance(raw_input, str):
            try:
                data = json.loads(raw_input)
                doc = IngestedDocument.model_validate(data)
            except (json.JSONDecodeError, ValidationError) as e:
                raise InvalidInputError(f"Failed to parse JSON input from Phase 1: {str(e)}") from e
        elif isinstance(raw_input, dict):
            try:
                doc = IngestedDocument.model_validate(raw_input)
            except ValidationError as e:
                raise InvalidInputError(f"Invalid Phase 1 data schema: {str(e)}") from e
        else:
            raise InvalidInputError(f"Unsupported input type for Phase 1 adapter: {type(raw_input)}")

        # Normalize text on all pages
        normalized_pages = []
        for p in doc.pages:
            norm_text = normalize_unicode_and_whitespace(p.raw_text)
            normalized_pages.append(
                RawPageInput(
                    page_number=p.page_number,
                    raw_text=norm_text,
                    blocks=p.blocks,
                    tables=p.tables,
                    is_scanned=p.is_scanned,
                    ocr_confidence_avg=p.ocr_confidence_avg,
                    width=p.width,
                    height=p.height,
                )
            )

        return IngestedDocument(
            document_id=doc.document_id,
            filename=doc.filename,
            source_type=doc.source_type,
            page_count=doc.page_count,
            pages=normalized_pages,
            metadata=doc.metadata,
            ingestion_warnings=doc.ingestion_warnings,
        )
