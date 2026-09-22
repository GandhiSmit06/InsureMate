# Phase 3 Integration Guide — Consuming Document Understanding

**For**: Phase 3 Teammate (Medical Insurance Requirement Extraction)  
**From**: Phase 2 Module (Document Understanding)  
**Schema Version**: `1.0`

---

## 1. Why You Don't Need to Re-Parse PDFs

Phase 2 converts raw PDFs, scans, and images into structured, typed Python objects (`DocumentUnderstandingResult`). You do not need to install `pdfplumber`, `PyMuPDF`, or regex engines in Phase 3.

All extracted data is already:
1. Normalized (Unicode, Indian DD/MM/YYYY dates, currency amounts).
2. Segmented into semantic sections (e.g. Diagnosis, Clinical Summary, Itemized Charges).
3. Organized into structured entities (Patient, Hospital, Encounter, Financial).
4. Tagged with exact provenance (document ID, page number, verbatim source text).
5. Scored for quality and consistency (arithmetic reconciliation, logical date checking).

---

## 2. Quick Start: Consuming the Output

```python
from document_understanding import DocumentUnderstandingPipeline, FieldStatus

# 1. Initialize the pipeline
pipeline = DocumentUnderstandingPipeline()

# 2. Process an ingested document (from Phase 1)
result = pipeline.process(ingested_document)

# 3. Access Document Type Hints
top_hint = result.document_type_hints[0]
print(f"Candidate Type: {top_hint.candidate_type} (Score: {top_hint.confidence_score})")
print(f"Signals: {top_hint.supporting_signals}")

# 4. Access Patient & Hospital Entities
if result.entities.patient.name.status == FieldStatus.EXTRACTED:
    patient_name = result.entities.patient.name.value
    print(f"Patient Name: {patient_name}")
    print(f"Source Evidence: {result.entities.patient.name.provenance.source_text}")

# 5. Access Encounter Details (Dates & Diagnosis)
if result.entities.encounter.diagnosis_text.status == FieldStatus.EXTRACTED:
    # Diagnosis strictly as documented in source text (NOT a medical opinion)
    diagnosis = result.entities.encounter.diagnosis_text.value
    print(f"Documented Diagnosis: {diagnosis}")

admission_date = result.entities.encounter.admission_date.value  # ISO string: "2024-03-12"
discharge_date = result.entities.encounter.discharge_date.value  # ISO string: "2024-03-15"

# 6. Access Financial & Itemized Charges
total_amount = result.entities.financial.total_amount.value  # Float: 25500.0
currency = result.entities.financial.currency.value          # "INR"

for charge in result.entities.financial.itemized_charges:
    print(f"- {charge.description}: Qty {charge.quantity} @ {charge.unit_price} = {charge.amount}")

# 7. Access Document Sections Directly
for section in result.sections:
    print(f"Section [{section.normalized_heading}] on Page {section.page_number}:")
    print(f"Content: {section.content[:100]}...\n")
```

---

## 3. Handling Uncertainty & Status

Phase 2 never fabricates values. Always inspect `field.status`:

```python
from document_understanding import FieldStatus

field = result.entities.financial.invoice_number

if field.status == FieldStatus.EXTRACTED:
    print("Found:", field.value)
elif field.status == FieldStatus.NOT_FOUND:
    print("Field not present in document (no requirement matched)")
elif field.status == FieldStatus.UNREADABLE:
    print("Field location unreadable (damaged or poor OCR):", field.notes)
elif field.status == FieldStatus.AMBIGUOUS:
    print("Field ambiguous:", field.notes)
```

---

## 4. Checking Document Quality & Conflicts

Before extracting insurance policy requirements, check document quality:

```python
# Check if encounter dates conflict
if result.quality.has_conflicting_dates:
    print("WARNING: Admission date is AFTER discharge date!")

# Check arithmetic reconciliation of hospital bills
rec = result.quality.arithmetic_reconciliation
if rec.checked and not rec.matches:
    print(f"WARNING: Bill discrepancy of {rec.discrepancy} between itemized items and total amount!")

# Check OCR legibility
if result.quality.overall_quality in ("degraded", "unreadable"):
    print("WARNING: Document image quality is poor; extra scrutiny needed.")
```

---

## 5. Traceability for Downstream Modules

Every important extracted field includes a `provenance` property:
- `provenance.page_number`: Where to highlight in UI or PDF viewer.
- `provenance.source_text`: Verbatim text that supported the extraction.
- `provenance.extraction_method`: How it was extracted (`key_value_heuristic`, `phase1_table_matrix`, `regex_dr_pattern`).
- `provenance.confidence`: Categorical confidence (`high`, `medium`, `low`).

This allows Phase 5 (Requirement ↔ Evidence Matching) to link each requirement back to verifiable text.
