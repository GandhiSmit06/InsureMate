# InsureMate — Phase 3: Medical Insurance Requirement Extraction

## Overview
Phase 3 is an autonomous, AI-powered Medical Insurance Requirement Extraction Engine for **InsureMate**. It analyzes health insurance policy documents (PDF or raw text) and answers:

> **"WHAT DOES THE INSURANCE POLICY REQUIRE FOR THIS CLAIM?"**

It extracts:
- Required documents (discharge summary, final bills, receipts, prescriptions, diagnostic reports, claim form, etc.)
- Required information inside documents (patient name, admission/discharge dates, diagnosis, doctor signature, itemized charges)
- Required conditions (network hospital rule, continuous 24-hour hospitalization, organ donor clearance)
- Required actions (claim notice/intimation, submission of papers)
- Deadlines & time limits (e.g. within 24 hours of emergency admission, within 30 days of discharge)
- Financial requirements (copay percentages, deductibles, room rent limits)
- Conditional requirements (e.g., accident -> FIR/MLC; surgery -> OT notes & implant invoice; ICU > 48h -> daily progress charts)

---

## Architecture & Independence

```
InsureMate/phase3/
├── api/
│   ├── __init__.py
│   └── routes.py             # FastAPI routes for /api/phase3/extract-requirements & health
├── deduplicator/
│   ├── __init__.py
│   └── requirement_deduplicator.py # Deduplicates and merges overlapping clauses & info
├── extractor/
│   ├── __init__.py
│   ├── base.py               # Abstract Base Extractor
│   ├── hybrid_extractor.py   # Hybrid coordinator with automatic fallback
│   ├── llm_extractor.py      # LLM-based structured extraction (Gemini / OpenAI)
│   └── rule_extractor.py     # Deterministic domain rule & NLP extractor (zero-hallucination)
├── ingestion/
│   ├── __init__.py
│   └── pdf_reader.py         # Independent PDF text extraction using pypdfium2 with per-page tracking
├── normalizer/
│   ├── __init__.py
│   └── requirement_normalizer.py # Standardizes canonical names, categories, and deadlines
├── prompt/
│   ├── __init__.py
│   └── system_prompt.py      # System prompts, JSON schema, and extraction guidelines
├── schema/
│   ├── __init__.py
│   └── models.py             # Strict Pydantic models (RequirementItem, Phase3Response, etc.)
├── validator/
│   ├── __init__.py
│   ├── hallucination_guard.py# Text-grounding guardrail against fabricated documents
│   └── schema_validator.py   # Strict schema enforcement & summary metrics
├── tests/
│   ├── conftest.py           # Realistic test policies and fixtures
│   ├── test_accident.py      # Test 4: Accident claims (FIR, MLC, toxicology)
│   ├── test_ambiguous.py     # Test 7: Discretionary/ambiguous clauses
│   ├── test_anti_hallucination.py # Test 9: Anti-hallucination / zero-invention verification
│   ├── test_api_endpoints.py # Test 11: HTTP API JSON & PDF multipart uploads
│   ├── test_cashless.py      # Test 2: Cashless pre-auth & network hospital conditions
│   ├── test_conditional.py   # Test 5: Conditional requirements (ICU, organ donor, KYC)
│   ├── test_deadlines.py     # Test 6: Deadlines & time limits
│   ├── test_deduplication.py # Test 8: Deduplication and consolidation
│   ├── test_hospitalization.py # Test 1: Standard inpatient hospitalization
│   ├── test_pdf_upload.py    # Test 10: Multi-page PDF upload with page traceability
│   └── test_reimbursement.py # Test 3: Reimbursement claims & submission timelines
├── config.py                 # Environment configuration
├── engine.py                 # Core RequirementExtractionEngine pipeline orchestrator
├── main.py                   # Standalone FastAPI server
└── requirements.txt          # Python dependencies
```

### Complete Independence Guarantee
Phase 3 does **NOT** rely on:
- Phase 1 PDF/document ingestion code
- Phase 2 document understanding output
- Any internal database or API from previous phases
- Any teammate's modules

It includes its own fast PDF parser (`pypdfium2`), page splitter, anti-hallucination guard, and domain extractor.

---

## API Specification

### 1. Extract Requirements
- **Endpoint**: `POST /api/phase3/extract-requirements`
- **Supported Content Types**:
  1. `application/json` (with `policy_text`, optional `claim_type`, optional `policy_name`)
  2. `multipart/form-data` (with `file` as PDF or TXT, optional `claim_type`, optional `policy_name`)

#### Request Example (JSON)
```json
{
  "claim_type": "hospitalization",
  "policy_name": "Mediclaim Plus",
  "policy_text": "Clause 5.1: The insured shall submit duly filled Claim Form, Hospital Discharge Summary, itemized Final Hospital Bill with breakup, and original payment receipts within 30 days of discharge."
}
```

#### Request Example (cURL - JSON)
```bash
curl -X POST http://localhost:8000/api/phase3/extract-requirements \
  -H "Content-Type: application/json" \
  -d '{
    "claim_type": "hospitalization",
    "policy_text": "Documents Required: Original Claim Form, Hospital Discharge Summary, Final Bill with itemized breakup, and Payment Receipts. In case of emergency hospitalization, notice must be given within 24 hours."
  }'
```

#### Request Example (cURL - PDF Upload)
```bash
curl -X POST http://localhost:8000/api/phase3/extract-requirements \
  -F "file=@/path/to/policy.pdf" \
  -F "claim_type=hospitalization"
```

#### Strict JSON Output Format
```json
{
  "success": true,
  "claim_type": "hospitalization",
  "policy_name": "Mediclaim Plus",
  "summary": {
    "total_requirements": 4,
    "mandatory_count": 3,
    "conditional_count": 1,
    "categories": {
      "DOCUMENT": 3,
      "DEADLINE": 1,
      "CONDITION": 0,
      "ACTION": 0,
      "INFORMATION": 0,
      "FINANCIAL": 0
    }
  },
  "requirements": [
    {
      "requirement_id": "REQ-001",
      "category": "DOCUMENT",
      "name": "Claim Form",
      "description": "Duly filled and signed official claim form (Part A and/or Part B).",
      "mandatory": true,
      "priority": "HIGH",
      "applies_when": "Hospitalization claim",
      "condition": null,
      "deadline": null,
      "evidence_type": "claim_form",
      "required_information": [
        "policy_number",
        "claimant_name",
        "treating_doctor_signature",
        "hospital_seal"
      ],
      "source_clause": "Documents Required for Claim",
      "source_page": 1
    },
    {
      "requirement_id": "REQ-002",
      "category": "DOCUMENT",
      "name": "Hospital Discharge Summary",
      "description": "Official discharge summary or card issued by the treating hospital.",
      "mandatory": true,
      "priority": "HIGH",
      "applies_when": "Hospitalization claim",
      "condition": null,
      "deadline": null,
      "evidence_type": "hospital_document",
      "required_information": [
        "patient_name",
        "admission_date",
        "discharge_date",
        "diagnosis",
        "treatment_given",
        "doctor_signature"
      ],
      "source_clause": "Documents Required for Claim",
      "source_page": 1
    }
  ]
}
```

### 2. Health Check
- **Endpoint**: `GET /api/phase3/health`
```json
{
  "status": "healthy",
  "module": "InsureMate Phase 3: Medical Insurance Requirement Extraction",
  "version": "1.0.0",
  "engine_mode": "hybrid",
  "llm_available": false,
  "llm_provider": "none"
}
```

---

## Setup & Running Instructions

### 1. Install Dependencies
```bash
pip install -r InsureMate/phase3/requirements.txt
```

### 2. Configure Environment (Optional for LLM)
If you wish to use Google Gemini or OpenAI LLMs:
Create a `.env` file in the project root:
```env
# Optional LLM integration (if omitted, high-precision deterministic rule engine runs automatically)
GEMINI_API_KEY="your-gemini-api-key"
# or
OPENAI_API_KEY="your-openai-api-key"

PHASE3_ENGINE_MODE="hybrid"   # Options: "hybrid", "rule_only", "llm_only"
PHASE3_PORT=8000
```

### 3. Start the Phase 3 Server
From `InsureMate/InsureMate`:
```bash
python run_server.py
# or
uvicorn phase3.main:app --host 0.0.0.0 --port 8000 --reload
```
Interactive Swagger UI will be available at: **`http://localhost:8000/docs`**

### 4. Run Automated Tests
```bash
pytest phase3/tests -v
```

---

## Integration Contract for Subsequent Phases

```
Phase 3: Medical Insurance Requirement Extraction
   │  Output: Strict Requirement JSON (REQ-001, REQ-002, ...)
   ▼
Phase 4: Evidence Classification
   │  Classifies user submitted uploads into evidence categories
   ▼
Phase 5: Requirement ↔ Evidence Matching
   │  Aligns submitted evidence against Phase 3 requirement IDs
   ▼
Phase 6: Missing Evidence Detection
      Detects requirements from Phase 3 without matching evidence
```
*(Phase 3 strictly refrains from evidence classification or missing document detection).*
