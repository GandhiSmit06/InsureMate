"""
services/qwen_vl/pdf_processor.py
PDF rendering engine for Qwen-VL document understanding.
Converts multi-page PDFs to in-memory PIL images and base64 Data URLs.
CRITICAL: Operates 100% in-memory; NO temporary image files are written to disk.
"""

import base64
import io
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union
import pypdfium2 as pdfium
from PIL import Image

from utils.logger import logger


class PDFProcessingError(Exception):
    """Base exception for PDF processing errors."""
    pass


class MissingPDFError(PDFProcessingError):
    """Raised when PDF file is missing."""
    pass


class CorruptedPDFError(PDFProcessingError):
    """Raised when PDF file cannot be opened or is corrupted."""
    pass


class EmptyPDFError(PDFProcessingError):
    """Raised when PDF contains zero pages."""
    pass


class PageRenderError(PDFProcessingError):
    """Raised when a specific page fails to render."""
    pass


@dataclass
class PDFPage:
    """Represents a single processed PDF page held entirely in memory."""
    page_number: int  # 1-indexed (Page 1, Page 2, ...)
    width: int
    height: int
    image: Image.Image
    base64_data_url: str

    def to_dict(self) -> dict:
        return {
            "page_number": self.page_number,
            "width": self.width,
            "height": self.height,
            "has_image": self.image is not None,
        }


class PDFProcessor:
    """
    Renders PDF pages into memory images suitable for Qwen-VL.
    Guarantees strictly 1-indexed page numbering and zero disk I/O for images.
    """

    def __init__(self, dpi: int = 150):
        self.scale = dpi / 72.0  # pypdfium2 default is 72 dpi

    def process_pdf(
        self,
        pdf_path: Union[str, Path],
        max_pages: Optional[int] = None
    ) -> List[PDFPage]:
        """
        Convert PDF pages into in-memory PDFPage objects.

        Args:
            pdf_path: Path to the target PDF file.
            max_pages: Optional maximum number of pages to process.

        Returns:
            List of PDFPage objects with 1-indexed page_number.
        """
        path = Path(pdf_path).resolve()
        if not path.exists() or not path.is_file():
            err_msg = f"PDF file does not exist: {path}"
            logger.error(err_msg)
            raise MissingPDFError(err_msg)

        logger.pdf(f"Opening PDF document: {path.name}")

        try:
            doc = pdfium.PdfDocument(str(path))
        except Exception as e:
            err_msg = f"Failed to open or parse corrupted PDF: {path.name}. Error: {e}"
            logger.error(err_msg)
            raise CorruptedPDFError(err_msg) from e

        total_pages = len(doc)
        if total_pages == 0:
            err_msg = f"PDF document contains 0 pages: {path.name}"
            logger.error(err_msg)
            raise EmptyPDFError(err_msg)

        pages_to_process = min(total_pages, max_pages) if max_pages is not None else total_pages
        logger.pdf(f"Processing {pages_to_process} of {total_pages} total pages (in-memory)")

        processed_pages: List[PDFPage] = []

        for idx in range(pages_to_process):
            page_num = idx + 1  # Strictly 1-indexed
            try:
                logger.pdf(f"Rendering page {page_num}/{pages_to_process} in-memory")
                page = doc[idx]
                bitmap = page.render(scale=self.scale)
                pil_image = bitmap.to_pil()

                # Convert PIL Image to Base64 Data URL purely in memory (JPEG format for compactness)
                buffer = io.BytesIO()
                # Convert to RGB in case page rendered in RGBA
                if pil_image.mode != "RGB":
                    rgb_image = pil_image.convert("RGB")
                else:
                    rgb_image = pil_image
                rgb_image.save(buffer, format="JPEG", quality=85)
                image_bytes = buffer.getvalue()
                b64_str = base64.b64encode(image_bytes).decode("utf-8")
                data_url = f"data:image/jpeg;base64,{b64_str}"

                pdf_page = PDFPage(
                    page_number=page_num,
                    width=pil_image.width,
                    height=pil_image.height,
                    image=pil_image,
                    base64_data_url=data_url
                )
                processed_pages.append(pdf_page)

            except Exception as e:
                err_msg = f"Failed to render PDF page {page_num}: {e}"
                logger.error(err_msg)
                raise PageRenderError(err_msg) from e

        logger.pdf(f"Successfully processed {len(processed_pages)} pages in-memory without writing images to disk")
        return processed_pages
