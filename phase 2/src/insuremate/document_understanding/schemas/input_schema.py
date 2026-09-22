"""
Input schema representing the output of Phase 1 (Document Ingestion).
This defines the contract between Phase 1 and Phase 2.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from .common import BoundingBox


class RawBlockInput(BaseModel):
    """A layout block or OCR line detected on a page."""
    model_config = ConfigDict(extra="ignore")

    text: str = Field(..., description="Text content within the block")
    bbox: Optional[BoundingBox] = Field(default=None, description="Bounding box if available")
    block_type: str = Field(default="text", description="Block type: text, header, table_cell, ocr_line")
    ocr_confidence: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="OCR confidence percentage")


class RawTableInput(BaseModel):
    """A table detected by Phase 1 (e.g. via pdfplumber or OCR layout engine)."""
    model_config = ConfigDict(extra="ignore")

    page_number: int = Field(..., ge=1)
    rows: List[List[str]] = Field(default_factory=list, description="Matrix of cell text strings")
    bbox: Optional[BoundingBox] = Field(default=None)


class RawPageInput(BaseModel):
    """A single page ingested from a document."""
    model_config = ConfigDict(extra="ignore")

    page_number: int = Field(..., ge=1, description="1-indexed page number")
    raw_text: str = Field(..., description="Full text extracted from this page")
    blocks: List[RawBlockInput] = Field(default_factory=list, description="Layout blocks if available")
    tables: List[RawTableInput] = Field(default_factory=list, description="Extracted tables if available")
    is_scanned: bool = Field(default=False, description="True if page was processed via OCR")
    ocr_confidence_avg: Optional[float] = Field(default=None, description="Average OCR confidence across page")
    width: Optional[float] = Field(default=None, description="Page width in points/pixels")
    height: Optional[float] = Field(default=None, description="Page height in points/pixels")


class IngestedDocument(BaseModel):
    """The complete ingested document object received from Phase 1."""
    model_config = ConfigDict(extra="ignore")

    document_id: str = Field(..., description="Unique document ID assigned during ingestion")
    filename: Optional[str] = Field(default=None, description="Original filename")
    source_type: str = Field(
        default="pdf", 
        description="Source document format (e.g. pdf, text_pdf, scanned_pdf, image)"
    )
    page_count: int = Field(..., ge=0, description="Total number of pages")
    pages: List[RawPageInput] = Field(default_factory=list, description="Page-wise extracted data")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="File metadata, mime-type, timestamps")
    ingestion_warnings: List[str] = Field(default_factory=list, description="Warnings encountered during ingestion")
