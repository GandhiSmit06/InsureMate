import io
import re
import logging
from typing import List, Union
from phase3.schema.models import PageText

logger = logging.getLogger("phase3.ingestion")


class PDFReader:
    """Self-contained PDF text extraction utility for Phase 3.
    Extracts text page-by-page to ensure strict page traceability for requirements.
    """

    @staticmethod
    def extract_from_bytes(pdf_bytes: bytes) -> List[PageText]:
        """Extract text from raw PDF bytes using pypdfium2."""
        if not pdf_bytes or len(pdf_bytes) == 0:
            raise ValueError("Empty PDF byte stream provided.")

        try:
            import pypdfium2 as pdfium
        except ImportError:
            logger.error("pypdfium2 is not installed.")
            raise RuntimeError("PDF extraction library (pypdfium2) is not installed.")

        pages: List[PageText] = []
        try:
            doc = pdfium.PdfDocument(io.BytesIO(pdf_bytes))
            for index, page in enumerate(doc):
                page_num = index + 1
                try:
                    text_page = page.get_textpage()
                    page_text = text_page.get_text_range()
                    # Clean up text
                    cleaned = PDFReader._clean_page_text(page_text)
                    pages.append(PageText(page_number=page_num, text=cleaned))
                except Exception as ex:
                    logger.warning(f"Error reading page {page_num}: {ex}")
                    pages.append(PageText(page_number=page_num, text=""))
            doc.close()
        except Exception as e:
            logger.error(f"Failed to parse PDF document: {e}")
            raise ValueError(f"Could not parse PDF file: {str(e)}")

        return pages

    @staticmethod
    def extract_from_text(raw_text: str) -> List[PageText]:
        """Parse raw text into structured PageText objects.
        Detects page markers like '--- Page 1 ---' or 'Page 1 of 10' if present,
        otherwise assigns entire text to page 1.
        """
        if not raw_text or not raw_text.strip():
            return []

        # Check for common page marker patterns, e.g., '--- Page 1 ---', '[Page 1]', 'Page 1 of 5'
        page_pattern = re.compile(
            r"(?:^|\n)\s*(?:---|===|___)?\s*(?:\[?\s*Page\s+(\d+)\s*(?:of\s+\d+)?\s*\]?)\s*(?:---|===|___)?\s*(?:\n|$)",
            re.IGNORECASE,
        )

        matches = list(page_pattern.finditer(raw_text))
        if not matches:
            # Single page document
            return [PageText(page_number=1, text=raw_text.strip())]

        pages: List[PageText] = []
        last_idx = 0
        first_match = matches[0]

        # If there's text before the first page marker, treat as page 1
        if first_match.start() > 0:
            preamble = raw_text[: first_match.start()].strip()
            if preamble:
                pages.append(PageText(page_number=1, text=preamble))

        for i, match in enumerate(matches):
            page_num = int(match.group(1))
            start_pos = match.end()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(raw_text)
            page_content = raw_text[start_pos:end_pos].strip()
            pages.append(PageText(page_number=page_num, text=page_content))

        return pages

    @staticmethod
    def _clean_page_text(text: str) -> str:
        """Clean extracted PDF text: normalize whitespace and remove control chars."""
        if not text:
            return ""
        # Replace non-breaking spaces and weird tabs
        text = text.replace("\xa0", " ").replace("\r\n", "\n").replace("\r", "\n")
        # Remove consecutive blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def extract_pages_from_bytes(pdf_bytes: bytes) -> List[PageText]:
    return PDFReader.extract_from_bytes(pdf_bytes)


def extract_pages_from_text(raw_text: str) -> List[PageText]:
    return PDFReader.extract_from_text(raw_text)
