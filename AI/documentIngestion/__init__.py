"""
InsureMate Document Ingestion Package
Provides tools for reading and extracting text from insurance documents (PDFs).

Modules:
  - pdfReader: Fast digital/softcopy PDF extraction via PyMuPDF.
  - ocr: Computer vision OCR for scanned documents/photos via keras_ocr.
  - documentIngestor: Smart unified pipeline handling both automatically.
"""

from .pdfReader import read_pdf, validate_pdf
from .ocr import ocr_pdf
from .paddleOcr import ocr_pdf_paddle
from .documentIngestor import ingest_document

__all__ = [
    "read_pdf",
    "validate_pdf",
    "ocr_pdf",
    "ocr_pdf_paddle",
    "ingest_document",
]

