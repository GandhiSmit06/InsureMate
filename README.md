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
├── src/
│   └── insuremate/
│       ├── __init__.py                 # Top-level InsureMate exports
│       └── document_understanding/     # Phase 2 Module
│           ├── __init__.py             # Module exports
│           ├── config.py               # Thresholds, currencies, doc types
│           ├── exceptions.py           # Custom exception taxonomy
│           ├── pipeline.py             # DocumentUnderstandingPipeline orchestrator
│           ├── schemas/                # Pydantic v2 schemas
│           │   ├── common.py           # FieldStatus, ConfidenceLevel, Provenance
│           │   ├── input_schema.py     # Phase 1 ingestion data contract
│           │   └── output_schema.py    # Schema v1.0 result contract
│           ├── adapters/               # Integration adapters & mock fixtures
│           │   ├── phase1_adapter.py   # Validates & adapts Phase 1 inputs
│           │   └── mock_inputs.py      # Realistic test fixtures
│           ├── normalization/          # Normalizers
│           │   ├── text_normalizer.py  # Unicode NFKC & whitespace cleaner
│           │   ├── date_normalizer.py  # Indian DD/MM/YYYY & ISO date parser
│           │   └── amount_normalizer.py# Indian/Western currency & number parser
│           ├── extraction/             # Extraction engines
│           │   ├── section_detector.py # Heading & boundary parser
│           │   ├── key_value_extractor.py # Label-value pair extractor
│           │   ├── table_extractor.py  # Table parser & itemized billing
│           │   └── medical_entity_extractor.py # Patient, hospital, encounter, financial
│           ├── classification/         # Type hinting
│           │   └── doc_type_hints.py   # Explainable candidate types
│           ├── provenance/             # Evidence traceability
│           │   └── tracer.py           # Links extractions to source text
│           └── quality/                # Quality & reconciliation
│               └── quality_checker.py  # OCR evaluation & arithmetic reconciliation
│
├── tests/                              # Comprehensive test suite (36 tests)
│   ├── conftest.py                     # Shared pytest fixtures
│   ├── unit/                           # Normalization, extraction, quality unit tests
│   ├── integration/                    # Pipeline, schema, edge-case tests
│   └── fixtures/                       # JSON fixtures
│
├── examples/                           # Concrete demonstrations
│   ├── input_example.json              # Sample input from Phase 1
│   ├── output_example.json             # Sample Schema v1.0 output
│   ├── incomplete_ambiguous_output.json# Edge-case output
│   └── run_demo.py                     # Executable demonstration script
│
└── docs/                               # Integration guides
    ├── integration.md                  # Complete team integration guide
    └── phase3_integration_guide.md     # Dedicated guide for Phase 3 teammate
```

---

## 4. Getting Started

### Installation
```bash
pip install -r requirements.txt
```

### Running the Test Suite
```bash
python -m pytest tests/ -v
```
**Test Results**: 36 passed (100% pass rate in ~0.17s).

### Running the Demonstration
```bash
python examples/run_demo.py
```

---

## 5. Integration for Teammates

- **Phase 1 Ingestion Integration**: See [docs/integration.md](file:///d:/CollegeAiFolder/InsureMate/docs/integration.md).
- **Phase 3 Requirement Extraction Guide**: See [docs/phase3_integration_guide.md](file:///d:/CollegeAiFolder/InsureMate/docs/phase3_integration_guide.md).
