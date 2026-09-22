# InsureMate — AI-Based Insurance Claim Preparation Agent

People often struggle to understand what documents they need for an insurance claim, what information is missing, which policy clauses matter, and what evidence should support the claim. InsureMate is designed to address this administrative problem by analyzing the policy and incident materials and preparing a structured claim package/checklist.

---

## 1. Project Workflow & Architecture

InsureMate is structured into modular pipeline phases:

- **PHASE 1**: PDF / Document Ingestion (`insuremate.ingestion`)
- **PHASE 2**: **Document Understanding** (`insuremate.document_understanding`) — **Implemented**
- **PHASE 3**: Medical Insurance Requirement Extraction (`insuremate.requirements_extraction`)
- **PHASE 4**: Evidence / Document Classification
- **PHASE 5**: Requirement ↔ Evidence Matching
- **PHASE 6**: Missing Evidence Detection
- **PHASE 7**: Policy Clause Retrieval / RAG
- **PHASE 8**: Agentic Orchestration
- **PHASE 9**: Claim-Readiness Report
- **PHASE 10**: FastAPI Backend
- **PHASE 11**: Frontend
- **PHASE 12**: Testing + Evaluation

---

## 2. Phase 2: Document Understanding Module

The `insuremate.document_understanding` module converts ingested documents into structured, trustworthy, provenance-tracked, and quality-evaluated information for consumption by Phase 3 and downstream modules.

### Core Capabilities:
- **Evidence Traceability (Provenance)**: Every extracted entity, key-value pair, and section retains its source page, verbatim excerpt, and extraction method.
- **Preserves Uncertainty**: Distinguishes between `extracted`, `not_found`, `unreadable`, and `ambiguous` data without fabricating ungrounded information.
- **Medical & Financial Entities**: Extracts patient demographics, hospital/doctor information, encounter dates/diagnoses (strictly as documented), invoice numbers, and itemized charges.
- **Explainable Document Type Hints**: Proposes candidate types (`hospital_invoice`, `discharge_summary`, `prescription`, `diagnostic_report`) with transparent signal scoring.
- **Quality & Consistency Checks**: Assesses OCR legibility, flags conflicting encounter dates (e.g. admission after discharge), and performs arithmetic reconciliation between itemized charges and stated total bill amounts.
- **Multilingual Support**: Fully preserves Unicode text (English, Hindi, Gujarati).

---

## 3. Project Structure

```
InsureMate/
├── README.md                           # Project overview and architecture guide
├── requirements.txt                    # Project dependencies
├── pyproject.toml                      # Build and pytest configuration
│
└── AI/                                 # Unified AI Module
    ├── __init__.py                     # Unified package exports & pipeline integration
    ├── insuremate_pipeline.py          # End-to-end process_document() pipeline
    ├── documentIngestion/              # Phase 1: Ingestion & PaddleOCR extraction
    │   ├── __init__.py
    │   ├── documentIngestor.py         # PyMuPDF & PaddleOCR ingestor
    │   ├── paddle_ocr.py               # Pure PaddleOCR wrapper
    │   └── utils.py                    # PDF rendering & bbox utils
    ├── document_understanding/         # Phase 2: Understanding & structuring
    │   ├── __init__.py                 # Module exports
    │   ├── config.py                   # Thresholds, currencies, doc types
    │   ├── exceptions.py               # Custom exception taxonomy
    │   ├── pipeline.py                 # DocumentUnderstandingPipeline orchestrator
    │   ├── schemas/                    # Pydantic v2 schemas
    │   ├── adapters/                   # Integration adapters & mock fixtures
    │   ├── normalization/              # Text, date, amount normalizers
    │   ├── extraction/                 # Section, key-value, table, medical extractors
    │   ├── classification/             # Type hinting
    │   ├── provenance/                 # Evidence traceability
    │   └── quality/                    # OCR evaluation & arithmetic reconciliation
    ├── tests/                          # Pipeline and unit test suite
    │   ├── conftest.py                 # Shared pytest fixtures
    │   ├── test_pipeline.py            # End-to-end integration tests
    │   └── evaluation/                 # Evaluation dataset & benchmarks
    ├── examples/                       # Concrete demonstrations
    │   ├── input_example.json          # Sample input from Phase 1
    │   ├── output_example.json         # Sample Schema v1.0 output
    │   └── run_demo.py                 # Executable demonstration script
    └── docs/                           # Integration guides & reports
        ├── evaluation_report.md        # Comprehensive evaluation report
        ├── integration.md              # Phase 1-2 integration guide
        └── phase3_integration_guide.md # Guide for Phase 3 integration
```

---

## 4. Getting Started

### Installation
```bash
pip install -r requirements.txt
```

### Running the Test Suite
```bash
pytest AI/tests/
```

### Running the Demonstration
```bash
python AI/examples/run_demo.py
```

---

## 5. Integration for Teammates

- **Phase 1 Ingestion Integration**: See [AI/docs/integration.md](file:///d:/Permanent/InsureMate/AI/docs/integration.md).
- **Phase 3 Requirement Extraction Guide**: See [AI/docs/phase3_integration_guide.md](file:///d:/Permanent/InsureMate/AI/docs/phase3_integration_guide.md).
