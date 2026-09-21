# InsureMate

People often struggle to understand what documents they need for an insurance claim, what information is missing, which policy clauses matter, and what evidence should support the claim. InsureMate is designed to address this administrative problem by analyzing the policy and incident materials and preparing a structured claim package/checklist.

---

## Intelligent Document Ingestion Pipeline

A production-grade document ingestion and text extraction pipeline tailored for insurance policies, hospital records, and claims documentation.

### Features

- **Smart Hybrid Extraction (`documentIngestor.py`)**:
  - Automatically inspects each page of a PDF.
  - If digital text exists, extracts it in milliseconds with 100% precision via PyMuPDF.
  - If a page is scanned or image-based, automatically routes it to OCR.
- **State-of-the-Art OCR (`paddleOcr.py`)**:
  - Powered by **PaddleOCR (PP-OCRv6)** with direction angle classification.
  - Preserves full character casing (uppercase & lowercase), punctuation, colons, dates (`18/Nov/2024`), policy/claim numbers (`95151709-00`), emails, and phone numbers.
  - Features natural reading-order line reconstruction with horizontal clustering for tables and side-by-side key-value pairs.
- **Dual-Engine & Quality Scoring**:
  - Supports both **PaddleOCR** and **Keras-OCR** with safe process-isolation.
  - Automatic quality scoring evaluates model confidence, character set diversity, and punctuation preservation to select the best output.
- **Fast Digital Reader (`pdfReader.py`)**:
  - Instant metadata and digital text extraction via PyMuPDF.

---

### Project Structure

```
InsureMate/
├── AI/
│   └── documentIngestion/
│       ├── __init__.py            # Clean module exports
│       ├── documentIngestor.py    # Unified orchestrator (hybrid + quality evaluation)
│       ├── paddleOcr.py           # PaddleOCR engine with reading-order reconstruction
│       ├── ocr.py                 # Keras-OCR engine
│       └── pdfReader.py           # PyMuPDF digital text extractor
├── requirements.txt               # Project dependencies
├── requirement.txt                # Alias dependencies file
└── README.md
```

---

### Installation

```bash
pip install -r requirements.txt
```

---

### Quickstart

#### 1. Smart Hybrid Ingestion (Recommended)

Automatically detects digital vs. scanned pages and applies the best OCR engine:

```python
from AI.documentIngestion import ingest_document

# Ingest an entire document
result = ingest_document("path/to/claim_document.pdf", mode="auto", ocr_engine="best")

if result["success"]:
    print(f"Processed {result['total_pages']} pages:")
    for page in result["pages"]:
        print(f"Page {page['page_number']} ({page['method'].upper()}) - Quality: {page.get('quality_score', 1.0)*100:.1f}%")
        print(page["text"])
```

#### 2. Direct PaddleOCR Extraction

For pure image-based or scanned PDFs:

```python
from AI.documentIngestion import ocr_pdf_paddle

result = ocr_pdf_paddle("path/to/scanned_document.pdf", max_pages=5)
print(result["full_text"])
```

#### 3. Fast Digital PDF Reading

For native digital PDFs (soft copies):

```python
from AI.documentIngestion import read_pdf

result = read_pdf("path/to/policy.pdf")
print(result["full_text"])
```

---

## License
MIT
