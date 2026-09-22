"""
InsureMate - Unified Document Ingestor
Intelligently combines fast digital PDF text extraction (PyMuPDF)
and Computer Vision OCR (PaddleOCR) with automatic quality evaluation.

Features:
  - Smart Hybrid Processing: Inspects each page:
    * If a page has digital text, extracts it in milliseconds (100% exact).
    * If a page is scanned/photo/image-based, triggers PaddleOCR.
  - PaddleOCR Engine (PP-OCRv6):
    * Preserves uppercase/lowercase, punctuation, numbers, and layout.
  - Multi-page document support (1KB – 100MB).
  - Configurable modes: 'auto' (hybrid), 'digital' (force softcopy), 'ocr' (force OCR).
"""

import os
import re
import sys
import time
import numpy as np
import pymupdf as fitz

try:
    from .pdfReader import validate_pdf, read_pdf
except (ImportError, ValueError):
    from pdfReader import validate_pdf, read_pdf


DEFAULT_MIN_DIGITAL_CHARS = 30


def evaluate_ocr_quality(text: str, confidence: float = 0.0, word_count: int = 0) -> float:
    """
    Calculate an objective quality score (0.0 to 1.0) for extracted OCR text.

    Rubric:
      - Confidence (35%): Model recognition confidence score.
      - Punctuation & Symbols (25%): Crucial for dates (18/Nov/2024), claim numbers (95151709-00),
        amounts, colons, and doctor notes.
      - Casing Diversity (20%): Preservation of uppercase & lowercase (names, acronyms, headings).
      - Word Completeness (20%): Non-empty, alphanumeric word count.
    """
    if not text or not text.strip():
        return 0.0

    raw = text.strip()
    words = raw.split()
    total_words = word_count or len(words)
    total_chars = max(len(raw), 1)

    # 1. Punctuation and symbols presence (dates, dashes, colons, slashes, numbers)
    punct_count = len(re.findall(r"[\:\-\/\.\,\@\#\$\%\&\(\)\_\d]", raw))
    punct_ratio = min(1.0, (punct_count / total_chars) * 6.0)

    # 2. Casing diversity (has both uppercase and lowercase)
    has_upper = bool(re.search(r"[A-Z]", raw))
    has_lower = bool(re.search(r"[a-z]", raw))
    casing_score = 1.0 if (has_upper and has_lower) else (0.5 if has_upper else 0.2)

    # 3. Completeness / density
    word_score = min(1.0, total_words / 35.0)

    # 4. Confidence (normalized 0.0 - 1.0)
    conf_score = max(0.0, min(1.0, confidence if confidence > 0 else 0.8))

    composite_score = (
        0.35 * conf_score
        + 0.25 * punct_ratio
        + 0.20 * casing_score
        + 0.20 * word_score
    )
    return round(float(composite_score), 4)


def ingest_document(
    file_path: str,
    mode: str = "auto",
    min_digital_chars: int = DEFAULT_MIN_DIGITAL_CHARS,
    max_pages: int | None = None,
    start_page: int = 1,
    verbose: bool = True,
    device: str | None = None,
) -> dict:
    """
    Ingest an insurance PDF with smart hybrid digital/OCR extraction using PaddleOCR.

    Args:
        file_path: Path to the PDF file.
        mode: 'auto' (hybrid), 'digital' (softcopy text only), or 'ocr' (force OCR).
        min_digital_chars: Minimum character threshold for digital text validity.
        max_pages: Limit number of pages to process (None = all pages).
        start_page: 1-indexed start page.
        verbose: Whether to print progress to console.

    Returns:
        dict with extraction status, pages, quality metrics, and full text.
    """
    validation = validate_pdf(file_path)
    if not validation.get("valid", True):
        return {
            "success": False,
            "error": validation.get("error", "Invalid file"),
            "file_name": os.path.basename(file_path),
            "file_size_kb": validation.get("file_size_kb", 0),
            "total_pages": 0,
            "pages": [],
            "full_text": "",
        }

    # 1. Forced Digital Mode
    if mode.lower() == "digital":
        digital_res = read_pdf(file_path)
        if not digital_res["success"]:
            return digital_res
        pages = []
        for p in digital_res["pages"]:
            words = len(p["text"].split())
            pages.append({
                "page_number": p["page_number"],
                "method": "digital",
                "ocr_engine": None,
                "text": p["text"],
                "word_count": words,
                "quality_score": 1.0,
            })
        full_text = "\n\n--- Page Break ---\n\n".join(p["text"] for p in pages if p["text"].strip())
        return {
            **digital_res,
            "pages": pages,
            "summary": {"digital_pages": len(pages), "ocr_pages": 0, "full_text": full_text},
        }

    # 2. Open Document
    try:
        doc = fitz.open(file_path)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to open PDF: {e}",
            "file_name": os.path.basename(file_path),
            "file_size_kb": validation.get("file_size_kb", 0),
            "total_pages": 0,
            "pages": [],
            "full_text": "",
        }

    paddle_engine = None

    total_doc_pages = doc.page_count
    start_idx = max(0, start_page - 1)
    end_idx = total_doc_pages if max_pages is None else min(total_doc_pages, start_idx + max_pages)

    if verbose:
        print(f"\n[Ingestor] Processing {end_idx - start_idx} page(s) (mode='{mode}') from '{os.path.basename(file_path)}'...", flush=True)

    pages = []
    digital_count = 0
    ocr_count = 0
    total_t0 = time.time()

    for page_idx in range(start_idx, end_idx):
        p_num = page_idx + 1
        t0 = time.time()
        page = doc.load_page(page_idx)
        rect = page.rect
        digital_text = page.get_text("text").strip() if mode.lower() != "ocr" else ""

        # Check if page has readable digital text
        if len(digital_text) >= min_digital_chars:
            words = len(digital_text.split())
            elapsed = time.time() - t0
            if verbose:
                print(f"[Page {p_num}/{total_doc_pages}] [DIGITAL] Extracted in {elapsed*1000:.1f}ms ({words} words)", flush=True)
            pages.append({
                "page_number": p_num,
                "method": "digital",
                "ocr_engine": None,
                "text": digital_text,
                "word_count": words,
                "quality_score": 1.0,
                "width": round(rect.width, 1),
                "height": round(rect.height, 1),
            })
            digital_count += 1
            continue

        # Scanned Page -> Run PaddleOCR
        if paddle_engine is None:
            try:
                from .paddleOcr import _get_ocr_engine, _render_page_to_image, _reconstruct_page_lines
            except (ImportError, ValueError):
                from paddleOcr import _get_ocr_engine, _render_page_to_image, _reconstruct_page_lines
            paddle_engine = _get_ocr_engine(device=device)

        img = _render_page_to_image(page, max_dimension=2400)
        raw_res = paddle_engine.predict(img)
        item = raw_res[0] if raw_res and len(raw_res) > 0 else {}
        boxes = item.get("rec_boxes", [])
        texts = item.get("rec_texts", [])
        scores = item.get("rec_scores", [])
        selected_text, _ = _reconstruct_page_lines(boxes, texts, scores)
        p_conf = float(np.mean([float(s) for s in scores])) if scores else 0.0
        best_score = evaluate_ocr_quality(selected_text, p_conf, len(texts))

        elapsed = time.time() - t0
        words = len(selected_text.split())
        if verbose:
            comp_str = f" [Quality: {best_score*100:.1f}%]" if best_score else ""
            print(f"[Page {p_num}/{total_doc_pages}] [OCR - PADDLE]{comp_str} Done in {elapsed:.1f}s ({words} words)", flush=True)

        pages.append({
            "page_number": p_num,
            "method": "ocr",
            "ocr_engine": "paddle",
            "quality_score": best_score,
            "confidence": round(p_conf, 4),
            "text": selected_text,
            "word_count": words,
            "width": round(rect.width, 1),
            "height": round(rect.height, 1),
        })
        ocr_count += 1

    doc.close()
    full_text = "\n\n--- Page Break ---\n\n".join(p["text"] for p in pages if p["text"].strip())
    total_elapsed = time.time() - total_t0

    if verbose:
        print(f"\n[Ingestor] Completed {len(pages)} pages in {total_elapsed:.1f}s (Digital: {digital_count}, OCR: {ocr_count}).", flush=True)

    return {
        "success": True,
        "error": None,
        "file_name": os.path.basename(file_path),
        "file_size_kb": validation.get("file_size_kb", 0),
        "total_pages": len(pages),
        "pages": pages,
        "summary": {
            "digital_pages": digital_count,
            "ocr_pages": ocr_count,
            "full_text": full_text,
        },
    }


# ---------------------------------------------------------------------------
# CLI Test Runner
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python documentIngestor.py <path_to_pdf> [auto|digital|ocr] [max_pages] [start_page]")
        print("Example: python documentIngestor.py my_claim.pdf auto 2 1")
        sys.exit(1)

    pdf_file = sys.argv[1]
    sel_mode = sys.argv[2] if len(sys.argv) > 2 else "auto"
    raw_pages = sys.argv[3] if len(sys.argv) > 3 else "0"
    num_pages = None if raw_pages in ("0", "all", "none", "None") else int(raw_pages)
    start_pg = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4].isdigit() else 1

    res = ingest_document(pdf_file, mode=sel_mode, max_pages=num_pages, start_page=start_pg)

    if not res["success"]:
        print(f"[ERROR] {res['error']}")
        sys.exit(1)

    print("\n" + "=" * 70)
    print(f" Document Ingestion Result: {res['file_name']} ({res['file_size_kb']} KB)")
    print(f" Total Pages: {res['total_pages']} (Digital: {res['summary']['digital_pages']}, OCR: {res['summary']['ocr_pages']})")
    print("=" * 70)

    for pg in res["pages"]:
        eng_label = f" ({pg['ocr_engine'].upper()})" if pg.get("ocr_engine") else ""
        score_label = f" - Quality: {pg.get('quality_score', 0)*100:.1f}%" if pg.get("quality_score") is not None else ""
        print(f"\n[Page {pg['page_number']} - Method: {pg['method'].upper()}{eng_label}{score_label} - Words: {pg['word_count']}]")
        sample = pg["text"][:300]
        if len(pg["text"]) > 300:
            sample += "... [truncated]"
        print(sample if sample.strip() else "[No text extracted]")
