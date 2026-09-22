"""
InsureMate - PaddleOCR Document Ingestion Module
High-accuracy text and tabular data extraction from scanned insurance documents using PaddleOCR.

Features:
  - Preserves uppercase/lowercase casing, punctuation (dates, colons, hyphens), and numbers.
  - Multi-line reading-order reconstruction (preserves horizontal key-value alignment).
  - Compatible with PaddleOCR 3.x and 2.x.
  - Page-by-page progress reporting with confidence scoring.
  - Fast execution on CPU / GPU.
"""

import os
import sys
import time
import json
import numpy as np
import pymupdf as fitz

try:
    from .pdfReader import validate_pdf
except (ImportError, ValueError):
    try:
        from pdfReader import validate_pdf
    except (ImportError, ValueError):
        # Standalone fallback validation
        def validate_pdf(path):
            if not os.path.exists(path):
                return {"valid": False, "error": f"File not found: {path}"}
            return {"valid": True, "error": None, "file_size_kb": round(os.path.getsize(path) / 1024, 2)}


_ocr_engine = None


def _get_ocr_engine(lang: str = "en"):
    """
    Lazy-load and initialize the PaddleOCR engine.
    Configured for high accuracy and compatibility across environments.
    """
    global _ocr_engine
    if _ocr_engine is None:
        from paddleocr import PaddleOCR
        import warnings
        warnings.filterwarnings("ignore", category=UserWarning)
        warnings.filterwarnings("ignore", category=DeprecationWarning)

        # Disable oneDNN/MKLDNN PIR array attribute conflict in Paddle 3.x
        try:
            _ocr_engine = PaddleOCR(
                lang=lang,
                enable_mkldnn=False,
                use_textline_orientation=True,
            )
        except Exception:
            # Fallback for older PaddleOCR 2.x versions
            _ocr_engine = PaddleOCR(
                lang=lang,
                use_angle_cls=True,
                show_log=False,
            )
    return _ocr_engine


def _render_page_to_image(page: fitz.Page, max_dimension: int = 1600) -> np.ndarray:
    """
    Render a PyMuPDF PDF page directly to a NumPy RGB array.
    1600px provides crisp detail for small table text and numbers without excessive memory usage.
    """
    rect = page.rect
    max_side = max(rect.width, rect.height)
    scale = (max_dimension / max_side) if max_side > 0 else 1.0
    matrix = fitz.Matrix(scale, scale)
    pixmap = page.get_pixmap(matrix=matrix, alpha=False)

    img = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
        pixmap.height, pixmap.width, 3
    )
    return img


def _reconstruct_page_lines(boxes, texts, scores) -> tuple[str, list[dict]]:
    """
    Reconstruct natural reading order and horizontally aligned fields (key-value pairs, tables).
    
    Groups words that share vertical alignment into unified lines, sorted left-to-right.
    """
    if not texts:
        return "", []

    elements = []
    for box, text, score in zip(boxes, texts, scores):
        t = text.strip()
        if not t:
            continue
        
        # Handle both [x1, y1, x2, y2] and 4-corner polygon formats
        box_arr = np.array(box)
        if box_arr.ndim == 2 and box_arr.shape == (4, 2):
            x1 = float(np.min(box_arr[:, 0]))
            y1 = float(np.min(box_arr[:, 1]))
            x2 = float(np.max(box_arr[:, 0]))
            y2 = float(np.max(box_arr[:, 1]))
        elif box_arr.size >= 4:
            b = box_arr.flatten()
            x1, y1, x2, y2 = float(b[0]), float(b[1]), float(b[2]), float(b[3])
        else:
            x1, y1, x2, y2 = 0.0, 0.0, 0.0, 0.0

        y_center = (y1 + y2) / 2.0
        h = max(y2 - y1, 1.0)
        elements.append({
            "box": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
            "y_center": y_center,
            "height": h,
            "text": t,
            "confidence": round(float(score), 4)
        })

    if not elements:
        return "", []

    # Sort primarily by vertical position (y1)
    elements.sort(key=lambda e: e["box"][1])

    structured_lines = []
    text_lines = []
    current_cluster = []

    for el in elements:
        if not current_cluster:
            current_cluster.append(el)
            continue

        # Check vertical overlap with current line cluster
        avg_center = sum(e["y_center"] for e in current_cluster) / len(current_cluster)
        avg_h = sum(e["height"] for e in current_cluster) / len(current_cluster)

        if abs(el["y_center"] - avg_center) < (avg_h * 0.55):
            current_cluster.append(el)
        else:
            # Finalize current line: sort left-to-right by x1
            current_cluster.sort(key=lambda e: e["box"][0])
            line_text = "   ".join(e["text"] for e in current_cluster)
            text_lines.append(line_text)
            structured_lines.append({
                "text": line_text,
                "confidence": round(float(np.mean([e["confidence"] for e in current_cluster])), 4),
                "elements": current_cluster,
            })
            current_cluster = [el]

    if current_cluster:
        current_cluster.sort(key=lambda e: e["box"][0])
        line_text = "   ".join(e["text"] for e in current_cluster)
        text_lines.append(line_text)
        structured_lines.append({
            "text": line_text,
            "confidence": round(float(np.mean([e["confidence"] for e in current_cluster])), 4),
            "elements": current_cluster,
        })

    return "\n".join(text_lines), structured_lines


def ocr_pdf_paddle(
    file_path: str,
    max_dimension: int = 1600,
    max_pages: int | None = None,
    start_page: int = 1,
    verbose: bool = True,
) -> dict:
    """
    Extract text from a scanned or image-based PDF using PaddleOCR.

    Args:
        file_path: Path to the PDF document.
        max_dimension: Max pixel dimension to scale pages (default 1600px).
        max_pages: Limit the number of pages to process (None = all pages).
        start_page: 1-indexed starting page (default 1).
        verbose: Whether to print progress to console.

    Returns:
        dict:
            - success (bool): Extraction status.
            - error (str | None): Error message if failed.
            - file_name (str): Document file name.
            - file_size_kb (float): Document size.
            - total_doc_pages (int): Total pages in PDF.
            - processed_pages (int): Count of pages processed.
            - pages (list[dict]): Per-page extracted data:
                - page_number (int)
                - text (str): Formatted multi-line reconstructed text.
                - average_confidence (float): 0.0 - 1.0 confidence score.
                - line_count (int): Number of text lines.
                - lines (list[dict]): Detailed lines with coordinates & scores.
            - full_text (str): Complete reconstructed document text.
    """
    validation = validate_pdf(file_path)
    if not validation.get("valid", True):
        return {
            "success": False,
            "error": validation.get("error", "Invalid file"),
            "file_name": os.path.basename(file_path),
            "file_size_kb": validation.get("file_size_kb", 0),
            "total_doc_pages": 0,
            "processed_pages": 0,
            "pages": [],
            "full_text": "",
        }

    try:
        doc = fitz.open(file_path)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to open PDF document: {e}",
            "file_name": os.path.basename(file_path),
            "file_size_kb": validation.get("file_size_kb", 0),
            "total_doc_pages": 0,
            "processed_pages": 0,
            "pages": [],
            "full_text": "",
        }

    engine = _get_ocr_engine()
    total_doc_pages = doc.page_count
    start_idx = max(0, start_page - 1)
    end_idx = total_doc_pages if max_pages is None else min(total_doc_pages, start_idx + max_pages)

    pages_to_process = end_idx - start_idx
    if verbose:
        print(f"\n[PaddleOCR] Processing {pages_to_process} page(s) (Pages {start_idx + 1} to {end_idx}) of '{os.path.basename(file_path)}'...", flush=True)

    pages = []
    total_t0 = time.time()

    for page_idx in range(start_idx, end_idx):
        p_num = page_idx + 1
        t0 = time.time()
        if verbose:
            print(f"[Page {p_num}/{total_doc_pages}] Rendering & running PaddleOCR...", flush=True)

        page = doc.load_page(page_idx)
        img = _render_page_to_image(page, max_dimension=max_dimension)

        # PaddleOCR 3.x predict
        raw_res = engine.predict(img)
        item = raw_res[0] if raw_res and len(raw_res) > 0 else {}

        # Extract detected boxes, texts, scores
        boxes = item.get("rec_boxes", [])
        texts = item.get("rec_texts", [])
        scores = item.get("rec_scores", [])

        # Format into clean lines with proper horizontal clustering
        page_text, page_lines = _reconstruct_page_lines(boxes, texts, scores)

        conf_list = [float(s) for s in scores]
        avg_conf = round(float(np.mean(conf_list)), 4) if conf_list else 0.0
        elapsed = time.time() - t0

        if verbose:
            print(f"[Page {p_num}/{total_doc_pages}] Extracted {len(page_lines)} lines ({len(texts)} words) in {elapsed:.1f}s — avg conf: {avg_conf * 100:.1f}%", flush=True)

        pages.append({
            "page_number": p_num,
            "text": page_text,
            "average_confidence": avg_conf,
            "word_count": len(texts),
            "line_count": len(page_lines),
            "width": round(page.rect.width, 1),
            "height": round(page.rect.height, 1),
            "lines": page_lines,
        })

    doc.close()
    full_text = "\n\n--- Page Break ---\n\n".join(p["text"] for p in pages if p["text"].strip())
    total_elapsed = time.time() - total_t0

    if verbose:
        print(f"\n[PaddleOCR] Completed {len(pages)} page(s) in {total_elapsed:.1f}s.", flush=True)

    return {
        "success": True,
        "error": None,
        "file_name": os.path.basename(file_path),
        "file_size_kb": validation.get("file_size_kb", 0),
        "total_doc_pages": total_doc_pages,
        "processed_pages": len(pages),
        "pages": pages,
        "full_text": full_text,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python paddleOcr.py <path_to_pdf> [max_pages] [start_page] [output_path]")
        print("Example: python paddleOcr.py my_claim.pdf 0 1")
        sys.exit(1)

    pdf_path = sys.argv[1]
    raw_pages = sys.argv[2] if len(sys.argv) > 2 else "0"
    num_pages = None if raw_pages in ("0", "all", "none", "None") else int(raw_pages)
    start_pg = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else 1

    result = ocr_pdf_paddle(pdf_path, max_pages=num_pages, start_page=start_pg)

    if not result["success"]:
        print(f"\n[ERROR] {result['error']}")
        sys.exit(1)

    print("\n" + "=" * 70)
    print(f" PaddleOCR Ingestion Result: {result['file_name']}")
    print(f" Pages Processed: {result['processed_pages']} / {result['total_doc_pages']}")
    print("=" * 70)

    # Save full text to a file next to the PDF or current dir
    base_name = os.path.splitext(result['file_name'])[0]
    out_txt_file = os.path.join(os.getcwd(), f"{base_name}_paddle_extracted.txt")
    out_json_file = os.path.join(os.getcwd(), f"{base_name}_paddle_extracted.json")
    
    try:
        with open(out_txt_file, "w", encoding="utf-8") as f:
            f.write(result["full_text"])
        print(f"\n[SAVED] Full extracted text saved to: {out_txt_file}")
    except Exception as e:
        print(f"\n[WARN] Could not save text file: {e}")

    try:
        with open(out_json_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"[SAVED] Structured JSON data saved to: {out_json_file}")
    except Exception as e:
        pass

    for page in result["pages"]:
        print(f"\n--- PAGE {page['page_number']} ({page['line_count']} lines, {page['word_count']} words, Avg Confidence: {page['average_confidence']*100:.1f}%) ---")
        print("-" * 70)
        lines = page["text"].split("\n")
        display_lines = lines[:25]
        print("\n".join(display_lines))
        if len(lines) > 25:
            print(f"... [{len(lines) - 25} more lines omitted for preview] ...")

