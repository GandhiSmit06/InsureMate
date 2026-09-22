# InsureMate Integration Guide — Phase 2: Document Understanding

## 1. Executive Summary

This document specifies the integration contracts for **Phase 2: Document Understanding** within the **InsureMate** pipeline:
- **Upstream Integration (Phase 1 → Phase 2)**: Ingestion of raw PDFs, images, and OCR text into structured page blocks and metadata.
- **Downstream Integration (Phase 2 → Phase 3)**: Delivery of validated, provenance-tracked, and quality-scored data to the Medical Insurance Requirement Extraction module.

```
+--------------------------+
|  PHASE 1: INGESTION      |  (PDFs, Scans, Images, OCR)
+--------------------------+
             │
             ▼ IngestedDocument (JSON / Dict / Pydantic)
+--------------------------+
|  PHASE 2: UNDERSTANDING  |  [OUR MODULE]
|  - Normalization         |  (Unicode, Indian DD/MM/YYYY, Currency)
|  - Section Detection     |  (Diagnosis, Clinical Summary, Charges)
|  - Key-Value Extraction  |  (Label-Value pairs with provenance)
|  - Table Parser          |  (Itemized hospital bills, Lab results)
|  - Entity Extraction     |  (Patient, Hospital, Encounter, Financial)
|  - Document Type Hints   |  (Explainable candidate types & signals)
|  - Quality Assessment    |  (OCR garble, Conflicting dates, Math check)
+--------------------------+
             │
             ▼ DocumentUnderstandingResult (Schema v1.0)
+--------------------------+
|  PHASE 3: REQUIREMENT    |  (Medical Insurance Requirement Extraction)
|  EXTRACTION              |
+--------------------------+
```

---

## 2. Phase 1 → Phase 2 Integration

### 2.1 Input Data Contract
Phase 1 delivers an `IngestedDocument` object (or equivalent JSON/dict) to `DocumentUnderstandingPipeline.process()`:

```python
from document_understanding import DocumentUnderstandingPipeline, IngestedDocument, RawPageInput

pipeline = DocumentUnderstandingPipeline()

# Phase 1 can pass an IngestedDocument instance, Python dict, or JSON string:
result = pipeline.process(ingested_document)
```

### 2.2 IngestedDocument Schema

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `document_id` | `str` | Unique document identifier (e.g. `"doc_001"`). |
| `filename` | `Optional[str]` | Original filename (e.g. `"invoice.pdf"`). |
| `source_type` | `str` | `"pdf"`, `"scanned_pdf"`, `"image"`, or `"text_pdf"`. |
| `page_count` | `int` | Total number of pages. |
| `pages` | `List[RawPageInput]` | Page-by-page extracted data. |
| `metadata` | `Dict[str, Any]` | Ingestion metadata (MIME type, timestamps, etc.). |
| `ingestion_warnings` | `List[str]` | Any warnings encountered by Phase 1. |

### 2.3 RawPageInput Schema

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `page_number` | `int` | 1-indexed page number. |
| `raw_text` | `str` | Full text extracted from this page. |
| `blocks` | `List[RawBlockInput]` | (Optional) Layout blocks with bounding boxes and OCR confidence. |
| `tables` | `List[RawTableInput]` | (Optional) Tables pre-extracted by Phase 1. |
| `is_scanned` | `bool` | True if page was processed via OCR. |
| `ocr_confidence_avg` | `Optional[float]` | Average OCR confidence percentage (0.0 - 100.0). |

---

## 3. Phase 2 → Phase 3 Integration

Phase 2 produces a versioned, Pydantic-validated `DocumentUnderstandingResult` (Schema v1.0).

### 3.1 DocumentUnderstandingResult Schema

```json
{
  "schema_version": "1.0",
  "document_id": "doc_inv_001",
  "status": "completed",
  "document_metadata": {
    "source_type": "pdf",
    "page_count": 1,
    "detected_language": "en",
    "is_scanned": false,
    "filename": "apollo_hospital_invoice_ramesh.pdf"
  },
  "document_type_hints": [
    {
      "candidate_type": "hospital_invoice",
      "confidence": "high",
      "confidence_score": 1.0,
      "supporting_signals": [
        "Matched invoice title/heading",
        "Contains invoice/bill number label",
        "Contains total amount / financial settlement summary",
        "Contains itemized hospital charges"
      ]
    }
  ],
  "pages": [],
  "sections": [],
  "tables": [],
  "key_value_fields": [],
  "entities": {
    "patient": { "name": {...}, "patient_id": {...}, "age": {...}, "gender": {...} },
    "hospital": { "name": {...}, "doctor_name": {...}, "address": {...}, "registration_number": {...} },
    "encounter": { "admission_date": {...}, "discharge_date": {...}, "diagnosis_text": {...}, "procedure_text": {...} },
    "financial": { "invoice_number": {...}, "bill_date": {...}, "total_amount": {...}, "paid_amount": {...}, "itemized_charges": [...] }
  },
  "quality": {
    "overall_quality": "good",
    "unreadable_char_ratio": 0.0,
    "ocr_confidence_avg": null,
    "is_scanned_or_image_based": false,
    "has_conflicting_dates": false,
    "arithmetic_reconciliation": {
      "checked": true,
      "itemized_sum": 25500.0,
      "stated_total": 25500.0,
      "discrepancy": 0.0,
      "matches": true
    },
    "missing_critical_fields": []
  },
  "issues": []
}
```

---

## 4. Status Concepts & Provenance

Every extracted field follows explicit status concepts:
- `extracted`: Confidently found and parsed.
- `not_found`: Field is absent from the document (not fabricated).
- `unreadable`: Field location contains garbled characters or damaged text.
- `ambiguous`: Found but with multiple interpretations (e.g. `04/05/2023` could be May 4 or April 5).
- `extraction_error`: Parsing failed.

### Provenance Object:
```json
{
  "document_id": "doc_inv_001",
  "page_number": 1,
  "source_text": "Total Amount: ₹ 25,500.00",
  "bounding_box": null,
  "extraction_method": "key_value_heuristic",
  "confidence": "high",
  "confidence_score": 0.92
}
```
Downstream modules (Phase 3 & Phase 5) can use `provenance.source_text` and `provenance.page_number` to trace any extracted value directly back to the original source evidence.
