"""
InsureMate - OCR Module
Extracts text from scanned / image-based PDFs using keras_ocr.

Workflow:
  1. Validate the PDF (reuses validation from pdfReader).
  2. Render each PDF page to a high-resolution image using PyMuPDF.
  3. Run keras_ocr's CRAFT detector + CRNN recognizer pipeline on each image.
  4. Reconstruct readable text by sorting detected words spatially
     (top-to-bottom, left-to-right) and grouping them into lines.
"""

import os
import sys

# ---------------------------------------------------------------------------
# GPU Memory Management (prevent OOM on 4GB / 6GB laptop GPUs)
# ---------------------------------------------------------------------------
os.environ["TF_FORCE_GPU_ALLOW_GROWTH"] = "true"
os.environ["TF_GPU_ALLOCATOR"] = "cuda_malloc_async"

# Keras 2 / tf_keras compatibility shim for keras_ocr.
os.environ["TF_USE_LEGACY_KERAS"] = "1"
try:
    import tf_keras as legacy_keras
    sys.modules["keras"] = legacy_keras
except ImportError:
    pass

import tensorflow as tf

# Enable dynamic GPU memory growth so TF doesn't greedy-allocate all 4GB VRAM
try:
    for gpu in tf.config.list_physical_devices("GPU"):
        tf.config.experimental.set_memory_growth(gpu, True)
except Exception:
    pass

import numpy as np

# ---------------------------------------------------------------------------
# NumPy 2.x compatibility shim for imgaug (keras_ocr dependency).
# ---------------------------------------------------------------------------
if not hasattr(np, "sctypes"):
    np.sctypes = {
        "int": [np.int8, np.int16, np.int32, np.int64],
        "uint": [np.uint8, np.uint16, np.uint32, np.uint64],
        "float": [np.float16, np.float32, np.float64],
        "complex": [np.complex64, np.complex128],
        "others": [bool, object, bytes, str, np.void],
    }

import pymupdf as fitz  # PyMuPDF (modern import)
import keras_ocr

try:
    from .pdfReader import validate_pdf
except (ImportError, ValueError):
    from pdfReader import validate_pdf


# ---------------------------------------------------------------------------
# Module-level pipeline (lazy-loaded so import is cheap)
# ---------------------------------------------------------------------------
_pipeline: keras_ocr.pipeline.Pipeline | None = None


def _get_pipeline() -> keras_ocr.pipeline.Pipeline:
    """Return a shared keras_ocr Pipeline, creating it on first call."""
    global _pipeline
    if _pipeline is None:
        _pipeline = keras_ocr.pipeline.Pipeline()
    return _pipeline


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

import time

def _render_page_to_image(page: fitz.Page, max_dimension: int = 1400) -> np.ndarray:
    """
    Render a PyMuPDF page directly to a NumPy RGB array scaled to max_dimension.
    
    1400px captures fine 8pt-10pt tabular print and small numbers accurately
    while staying well within RTX 3050 VRAM thanks to cuda_malloc_async.

    Args:
        page: A PyMuPDF Page object.
        max_dimension: Maximum pixel width or height (default 1400).

    Returns:
        numpy.ndarray of shape (H, W, 3) with dtype uint8.
    """
    rect = page.rect
    max_side = max(rect.width, rect.height)
    scale = (max_dimension / max_side) if max_side > 0 else 1.0
    matrix = fitz.Matrix(scale, scale)
    pixmap = page.get_pixmap(matrix=matrix, alpha=False)

    # Convert pixmap samples (bytes) → NumPy array
    img = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
        pixmap.height, pixmap.width, 3
    )
    return img


def _predictions_to_text(predictions: list) -> str:
    """
    Convert keras_ocr predictions into human-readable, well-structured text.

    Uses bounding-box vertical overlap clustering:
      - Groups words on the same line if their vertical spans overlap by >= 40%.
      - Prevents single-word fragmented line splits on uneven document text.
      - Sorts lines vertically (top-to-bottom) and words horizontally (left-to-right).
      - Filters out single-character noise artifacts.

    Args:
        predictions: List of (text, box) tuples from keras_ocr.

    Returns:
        Reconstructed multi-line string.
    """
    if not predictions:
        return ""

    boxes = []
    for word, box in predictions:
        # Filter obvious single-letter noise characters except common valid ones
        clean_word = word.strip()
        if not clean_word:
            continue
        if len(clean_word) == 1 and clean_word not in "0123456789asdim":
            continue

        box = np.array(box)
        x_min = float(box[:, 0].min())
        x_max = float(box[:, 0].max())
        y_min = float(box[:, 1].min())
        y_max = float(box[:, 1].max())
        y_center = (y_min + y_max) / 2.0
        height = y_max - y_min

        boxes.append({
            "word": clean_word,
            "x_min": x_min,
            "x_max": x_max,
            "y_min": y_min,
            "y_max": y_max,
            "y_center": y_center,
            "height": height,
        })

    if not boxes:
        return ""

    # Sort initially from top to bottom
    boxes.sort(key=lambda b: b["y_min"])

    # Cluster into lines using vertical overlap
    lines = []
    for b in boxes:
        placed = False
        for line in lines:
            line_y_min = np.mean([item["y_min"] for item in line])
            line_y_max = np.mean([item["y_max"] for item in line])
            line_h = line_y_max - line_y_min
            overlap = min(b["y_max"], line_y_max) - max(b["y_min"], line_y_min)

            # Minimum height between current box and the line average
            min_h = min(b["height"], line_h)
            if min_h > 0 and (overlap / min_h) >= 0.40:
                line.append(b)
                placed = True
                break

        if not placed:
            lines.append([b])

    # Sort lines from top to bottom by average y_min
    lines.sort(key=lambda l: np.mean([item["y_min"] for item in l]))

    # Inside each line, sort words from left to right by x_min
    formatted_lines = []
    for line in lines:
        line.sort(key=lambda item: item["x_min"])
        line_str = " ".join(item["word"] for item in line)
        if line_str.strip():
            formatted_lines.append(line_str)

    return "\n".join(formatted_lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ocr_pdf(file_path: str, max_dimension: int = 1400, dpi: int = 150) -> dict:
    """
    Extract text from a scanned / image-based PDF using OCR.

    Args:
        file_path: Path to the PDF file.
        max_dimension: Maximum dimension (pixels) to scale the page to (default 1280).
        dpi: Fallback DPI if max_dimension is not used.

    Returns:
        dict with keys:
            - success (bool): Whether OCR succeeded.
            - error (str | None): Error message if something failed.
            - file_name (str): Base name of the file.
            - file_size_kb (float | None): Size in KB.
            - total_pages (int): Number of pages in the PDF.
            - pages (list[dict]): Per-page results, each containing:
                - page_number (int): 1-indexed page number.
                - text (str): OCR-extracted text.
                - width (float): Page width in points.
                - height (float): Page height in points.
                - word_count (int): Number of words detected on the page.
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
            "pages": [],
        }

    # --- Step 2: Open PDF ---
    try:
        doc = fitz.open(file_path)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to open PDF: {e}",
            "file_name": os.path.basename(file_path),
            "file_size_kb": validation["file_size_kb"],
            "total_pages": 0,
            "pages": [],
        }

    # --- Step 3: Run OCR page by page ---
    pipeline = _get_pipeline()
    pages = []

    for page_index in range(doc.page_count):
        t0 = time.time()
        print(f"[OCR] Processing page {page_index + 1}/{doc.page_count}...", flush=True)
        page = doc.load_page(page_index)
        rect = page.rect

        # Render page to image scaled to max_dimension (optimal for CRAFT)
        img = _render_page_to_image(page, max_dimension=max_dimension)

        # Run keras_ocr (expects a list of images)
        prediction_groups = pipeline.recognize([img])
        predictions = prediction_groups[0]

        # Convert predictions → readable text
        text = _predictions_to_text(predictions)
        elapsed = time.time() - t0
        print(f"[OCR] Page {page_index + 1}/{doc.page_count} done in {elapsed:.1f}s ({len(predictions)} words)", flush=True)

        pages.append({
            "page_number": page_index + 1,
            "text": text,
            "width": round(rect.width, 2),
            "height": round(rect.height, 2),
            "word_count": len(predictions),
        })

    total_pages = doc.page_count
    doc.close()

    return {
        "success": True,
        "error": None,
        "file_name": os.path.basename(file_path),
        "file_size_kb": validation["file_size_kb"],
        "total_pages": total_pages,
        "pages": pages,
    }
