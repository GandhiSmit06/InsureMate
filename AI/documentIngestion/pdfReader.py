"""
InsureMate - PDF Reader Module
Reads and extracts text from uploaded PDF documents using PyMuPDF.

Accepts PDFs between 100KB and 1MB, supports multi-page documents.
"""

import os
import pymupdf as fitz  # PyMuPDF (modern import)


# File size constraints (in bytes)
MIN_FILE_SIZE = 1 * 1024   # 1 KB
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB


def validate_pdf(file_path: str) -> dict:
    """
    Validate that the file exists, is a PDF, and meets size requirements.

    Args:
        file_path: Absolute or relative path to the PDF file.

    Returns:
        dict with keys:
            - valid (bool): Whether the file passed all checks.
            - error (str | None): Description of what failed, or None if valid.
            - file_size_kb (float | None): File size in KB if the file exists.
    """
    # Check file exists
    if not os.path.exists(file_path):
        return {"valid": False, "error": f"File not found: {file_path}", "file_size_kb": None}

    # Check extension
    if not file_path.lower().endswith(".pdf"):
        return {"valid": False, "error": "File is not a PDF. Only .pdf files are accepted.", "file_size_kb": None}

    # Check file size
    file_size = os.path.getsize(file_path)
    file_size_kb = round(file_size / 1024, 2)

    if file_size < MIN_FILE_SIZE:
        return {
            "valid": False,
            "error": f"File too small ({file_size_kb} KB). Minimum size is 100 KB.",
            "file_size_kb": file_size_kb,
        }

    if file_size > MAX_FILE_SIZE:
        return {
            "valid": False,
            "error": f"File too large ({file_size_kb} KB). Maximum size is 1024 KB (1 MB).",
            "file_size_kb": file_size_kb,
        }

    return {"valid": True, "error": None, "file_size_kb": file_size_kb}


def read_pdf(file_path: str) -> dict:
    """
    Validate and read a PDF file, extracting text from every page.

    Args:
        file_path: Path to the PDF file to read.

    Returns:
        dict with keys:
            - success (bool): Whether reading succeeded.
            - error (str | None): Error message if something failed.
            - file_name (str): Base name of the file.
            - file_size_kb (float): Size in KB.
            - total_pages (int): Number of pages in the PDF.
            - metadata (dict): PDF metadata (title, author, subject, etc.).
            - pages (list[dict]): Per-page data, each containing:
                - page_number (int): 1-indexed page number.
                - text (str): Extracted text content.
                - width (float): Page width in points.
                - height (float): Page height in points.
    """
    # --- Step 1: Validate ---
    validation = validate_pdf(file_path)
    if not validation["valid"]:
        return {
            "success": False,
            "error": validation["error"],
            "file_name": os.path.basename(file_path),
            "file_size_kb": validation["file_size_kb"],
            "total_pages": 0,
            "metadata": {},
            "pages": [],
        }

    # --- Step 2: Open and read with PyMuPDF ---
    try:
        doc = fitz.open(file_path)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to open PDF: {e}",
            "file_name": os.path.basename(file_path),
            "file_size_kb": validation["file_size_kb"],
            "total_pages": 0,
            "metadata": {},
            "pages": [],
        }

    # Extract metadata
    metadata = doc.metadata or {}

    # Extract text from each page
    pages = []
    for page_number in range(doc.page_count):
        page = doc.load_page(page_number)
        text = page.get_text("text")
        rect = page.rect

        pages.append({
            "page_number": page_number + 1,
            "text": text,
            "width": round(rect.width, 2),
            "height": round(rect.height, 2),
        })

    total_pages = doc.page_count
    doc.close()

    return {
        "success": True,
        "error": None,
        "file_name": os.path.basename(file_path),
        "file_size_kb": validation["file_size_kb"],
        "total_pages": total_pages,
        "metadata": metadata,
        "pages": pages,
    }


# ---------------------------------------------------------------------------
# CLI entry point – allows quick testing via: python pdfReader.py <path>
# ---------------------------------------------------------------------------
# if __name__ == "__main__":
#     import sys

#     if len(sys.argv) < 2:
#         print("Usage: python pdfReader.py <path_to_pdf>")
#         sys.exit(1)

#     pdf_path = sys.argv[1]
#     result = read_pdf(pdf_path)

#     if not result["success"]:
#         print(f"[ERROR] {result['error']}")
#         sys.exit(1)

#     # Print summary
#     print(f"File      : {result['file_name']}")
#     print(f"Size      : {result['file_size_kb']} KB")
#     print(f"Pages     : {result['total_pages']}")

#     if result["metadata"].get("title"):
#         print(f"Title     : {result['metadata']['title']}")
#     if result["metadata"].get("author"):
#         print(f"Author    : {result['metadata']['author']}")

#     print("-" * 60)

#     for page in result["pages"]:
#         print(f"\n--- Page {page['page_number']} ({page['width']} x {page['height']} pts) ---")
#         text = page["text"].strip()
#         if text:
#             # # Show first 500 chars per page in CLI mode
#             preview = text[:-1]
#             # if len(text) > 500:
#             #     preview += "\n... [truncated]"
#             print(preview)
#         # else:
#         #     print("[No extractable text on this page]")
