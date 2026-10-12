"""
services/qwen_vl/pdf_processor.py
PDF rendering engine for Qwen-VL document understanding.
Converts multi-page PDFs to in-memory PIL images and base64 Data URLs.
CRITICAL: Operates 100% in-memory; NO temporary image files are written to disk.
"""

import base64
import concurrent.futures
import io
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union
import pypdfium2 as pdfium
from PIL import Image

from utils.logger import logger


import os
import requests


def extract_ocr_from_pil(pil_img: Image.Image) -> str:
    """Run Qwen-VL or local Gemma 3 vision OCR on rendered PIL image when embedded digital text is absent."""
    try:
        # Convert PIL Image to Base64 JPEG in-memory (0 disk I/O)
        buffer = io.BytesIO()
        rgb_img = pil_img.convert("RGB") if pil_img.mode != "RGB" else pil_img
        rgb_img.save(buffer, format="JPEG", quality=80)
        b64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")

        # 1. Primary: Local Gemma 3 vision OCR via Ollama
        ollama_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        ollama_model = os.getenv("OLLAMA_MODEL", os.getenv("QWEN_MODEL_NAME", "gemma3:latest"))

        try:
            resp = requests.post(
                f"{ollama_base}/api/chat",
                json={
                    "model": ollama_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": "Transcribe all visible text from this document image accurately and verbatim. Return ONLY the transcribed text.",
                            "images": [b64_str],
                        }
                    ],
                    "stream": False,
                },
                timeout=45,
            )
            if resp.status_code == 200:
                content = resp.json().get("message", {}).get("content", "").strip()
                if content:
                    return content
        except Exception as e:
            logger.debug(f"Local Gemma 3 vision OCR skipped/unavailable: {e}")

        # 2. Secondary: Qwen-VL API (DashScope / OpenAI-compatible endpoint)
        qwen_api_key = os.getenv("QWEN_API_KEY", "")
        qwen_base_url = os.getenv("QWEN_BASE_URL", "")
        if qwen_api_key and qwen_api_key != "ollama" and not qwen_api_key.startswith("your_"):
            try:
                from openai import OpenAI
                client = OpenAI(api_key=qwen_api_key, base_url=qwen_base_url or None)
                model_name = os.getenv("QWEN_MODEL_NAME", "qwen-vl-max")
                res = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Transcribe all visible text from this document image verbatim. Return ONLY the transcribed text."},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_str}"}},
                            ],
                        }
                    ],
                    max_tokens=2048,
                    temperature=0.1,
                )
                text = (res.choices[0].message.content or "").strip()
                if text:
                    return text
            except Exception as e:
                logger.debug(f"Qwen-VL vision OCR skipped/unavailable: {e}")

    except Exception as e:
        logger.debug(f"Vision OCR extraction fallback skipped: {e}")
    return ""


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
    text: str = ""

    def to_dict(self) -> dict:
        return {
            "page_number": self.page_number,
            "width": self.width,
            "height": self.height,
            "has_image": self.image is not None,
            "text": self.text,
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

        try:
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

                    # Extract digital text if present
                    page_text = ""
                    try:
                        textpage = page.get_textpage()
                        page_text = textpage.get_text_range()
                    except Exception:
                        page_text = ""

                    # If page has no extractable digital text, run native OCR on rendered image
                    if not page_text or len(page_text.strip()) < 20:
                        ocr_text = extract_ocr_from_pil(rgb_image)
                        if ocr_text:
                            page_text = ocr_text
                            logger.pdf(f"Page {page_num}: OCR recognized {len(ocr_text)} characters")

                    pdf_page = PDFPage(
                        page_number=page_num,
                        width=pil_image.width,
                        height=pil_image.height,
                        image=pil_image,
                        base64_data_url=data_url,
                        text=page_text
                    )
                    processed_pages.append(pdf_page)

                except Exception as e:
                    err_msg = f"Failed to render PDF page {page_num}: {e}"
                    logger.error(err_msg)
                    raise PageRenderError(err_msg) from e

            logger.pdf(f"Successfully processed {len(processed_pages)} pages in-memory without writing images to disk")
            return processed_pages
        finally:
            try:
                doc.close()
            except Exception:
                pass
