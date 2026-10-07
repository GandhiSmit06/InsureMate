# InsureMate — Insurance Claim Preparation Agent
**Track B: Agentic AI Application | Semester Project**
**Phase 1: Qwen-VL Document Understanding + Phase 2: Document Validation + Phase 3: Validity Checker**

---

## 1. Project Purpose

**InsureMate** is an Agentic AI insurance claim preparation system designed to assist policyholders and claims adjudicators in preparing, validating, and verifying health insurance claims. 

The complete system workflow comprises:
1. **Policy Analyzer**
2. **Requirement Extractor**
3. **Document Checker**
4. **Missing Evidence Detector**
5. **Claim Preparation**

In this milestone (**Phases 1, 2, and 3**), we implement the core perceptual and verification foundations:
- **Phase 1: Qwen-VL Document Understanding Tool** (`QwenVLExtractionTool`)
  Converts multi-page PDFs to in-memory raster images (0 disk image files created) and performs structured vision entity extraction and classification with strict 1-indexed page tracking and a zero-hallucination policy.
- **Phase 2: Document Validation Tool** (`DocumentValidationTool`)
  Executes deterministic, rule-based field completeness validation for each document type (policy certificate, hospital records, medical bills, diagnostic reports, incident papers) detecting missing required fields and outputting actionable reasons.
- **Phase 3: Claim Validity Checker Tool** (`ValidityCheckerTool`)
  Deterministically compares incident and invoice dates against policy active coverage dates (`policy_start_date` to `policy_end_date`), supports multi-format date normalization, and verifies patient identity against floater policy family members.

> **Agentic AI Architecture Note:**
> To prepare for Phase 4 (Agent Orchestrator, Planning, and Tool Calling Loop), every phase is implemented as an independent, modular, callable **Tool** adhering to standard function calling specifications.

---

## 2. Project Architecture & Directory Structure

```
InsureMate/
├── .env.example                               # Environment template for Qwen-VL credentials
├── .gitignore                                 # Git ignore file (virtualenv, cache, etc.)
├── requirements.txt                           # Minimal pinned Python dependencies
├── main.py                                    # Unified CLI runner for tools and tests
├── README.md                                  # Comprehensive documentation
│
├── services/
│   ├── qwen_vl/
│   │   ├── __init__.py                        # Package exports
│   │   ├── pdf_processor.py                   # Multi-page in-memory PDF renderer (pypdfium2/PIL)
│   │   └── extractor.py                       # Qwen-VL multi-modal extractor & grounded fallback
│   │
│   ├── document_validation/
│   │   ├── __init__.py                        # Package exports
│   │   └── validator.py                       # Deterministic required-field rule engine
│   │
│   └── validity_checker/
│       ├── __init__.py                        # Package exports
│       └── checker.py                         # Date normalizer, coverage window checker, identity matcher
│
├── tools/
│   ├── __init__.py                            # Agent Tool Registry (get_insuremate_tools)
│   ├── qwen_vl_tool.py                        # QwenVLExtractionTool (LLM tool wrapper)
│   ├── document_validation_tool.py            # DocumentValidationTool (LLM tool wrapper)
│   └── validity_checker_tool.py               # ValidityCheckerTool (LLM tool wrapper)
│
├── utils/
│   ├── config.py                              # QwenConfig loader and validator
│   └── logger.py                              # Technical logger emitting [PDF], [QWEN-VL], [VALIDATION], [VALIDITY], [RESULT]
│
└── tests/
    ├── test_phase1.py                         # Phase 1 unit tests (PDF, page tracking, no-hallucination)
    ├── test_phase2.py                         # Phase 2 unit tests (8 mandatory validation tests)
    ├── test_phase3.py                         # Phase 3 unit tests (8 mandatory date validity tests)
    └── test_end_to_end.py                     # Full multi-tool integration test on real documents
```

---

## 3. Installation

### Prerequisites
- Python 3.10+ (tested on Python 3.12)
- Linux / macOS / Windows

### Setup Environment
```bash
# Clone the repository and navigate into directory
cd /path/to/InsureMate

# Create and activate Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install required dependencies
pip install -r requirements.txt
```

---

## 4. Environment Configuration & Qwen-VL Setup

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Edit `.env` to configure your preferred Qwen-VL endpoint:
```ini
# Alibaba Cloud DashScope / Compatible Endpoint
QWEN_API_KEY=your_dashscope_api_key_here
QWEN_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
QWEN_MODEL_NAME=qwen-vl-max
QWEN_MAX_TOKENS=2048
QWEN_TEMPERATURE=0.1
```

> **Offline & Deterministic Mode:**
> If `QWEN_API_KEY` is not provided or remains as placeholder, the system automatically runs in **Deterministic Grounded Mode**. This guarantees that all unit tests, automated CI/CD pipelines, and local test runs execute reliably without requiring external network connectivity or paid API credits.

---

## 5. Tool Usage & Execution Instructions

### A. Phase 1: Qwen-VL Document Extraction Tool
Converts PDF pages into memory images and extracts structured insurance fields:
```bash
python main.py --phase 1 --max-pages 2 --pdf "4225IELVT38453879200000_policy_copy.pdf"
```

Programmatic Usage:
```python
from tools.qwen_vl_tool import QwenVLExtractionTool

tool = QwenVLExtractionTool()
result = tool.run(pdf_path="4225IELVT38453879200000_policy_copy.pdf", max_pages=1)
print(result["extracted_documents"])
```

### B. Phase 2: Document Validation Tool
Deterministically checks required fields for policies, hospital documents, medical bills, invoices, and diagnostic reports:
```bash
python main.py --phase 2
```

Programmatic Usage:
```python
from tools.document_validation_tool import DocumentValidationTool

tool = DocumentValidationTool()
sample_docs = [
    {
        "page_number": 2,
        "document_type": "medical_bill",
        "bill_number": "INV-101",
        "patient_name": "Parth Pathak",
        "document_date": "15/08/2026",
        "bill_amount": "48500.00"
    }
]
validation = tool.run(sample_docs)
print("Is valid:", validation["valid"])
```

### C. Phase 3: Claim Validity Checker Tool
Checks if claim dates fall inside policy start/end dates, handles date normalization, and checks family member identity:
```bash
python main.py --phase 3
```

Programmatic Usage:
```python
from tools.validity_checker_tool import ValidityCheckerTool

tool = ValidityCheckerTool()
policy = {
    "policy_start_date": "12/03/2025",
    "policy_end_date": "11/03/2028",
    "insured_names": ["Maulikkumar Pathak", "Parth Pathak"]
}
claim_docs = [
    {
        "page_number": 2,
        "document_type": "medical_bill",
        "document_date": "15/08/2026",
        "patient_name": "Parth Pathak"
    }
]
validity = tool.run(policy_data=policy, document_data=claim_docs)
print("Valid:", validity["valid"])
print("Reasons:", validity["reasons"])
```

### D. End-to-End Pipeline
Executes the full pipeline across all three tools on real workspace PDF documents:
```bash
python main.py --end-to-end
```

---

## 6. How to Run Tests

Run all unit tests and end-to-end tests with a single command:
```bash
python main.py --test-all
```

Or run individual test modules:
```bash
# Phase 1 tests (PDF in-memory rendering, page tracking, no-hallucination)
python tests/test_phase1.py

# Phase 2 tests (All 8 mandatory document validation scenarios)
python tests/test_phase2.py

# Phase 3 tests (All 8 mandatory date validity scenarios)
python tests/test_phase3.py

# End-to-end integration test
python tests/test_end_to_end.py
```

---

## 7. Test Results Overview

| Test Suite | Scenario Tested | Expected Result | Actual Result | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | In-Memory PDF Processing & Page Tracking | 3 pages in RAM, numbers [1,2,3], 0 files on disk | 3 pages in RAM, numbers [1,2,3], 0 files on disk | **PASS** |
| **Phase 1** | Document Classification | Category in standard set | Category: `insurance_policy` | **PASS** |
| **Phase 1** | No Hallucination Policy | Non-visible fields return null | `bill_number=None, hospital=None` | **PASS** |
| **Phase 1** | Missing PDF File Error Handling | `status='error'`, informative error | `status='error'`, file missing error | **PASS** |
| **Phase 1** | Corrupted PDF File Error Handling | `status='error'`, corrupted format error | `status='error'`, data format error | **PASS** |
| **Phase 2** | TEST 1: Valid policy document | `valid=True`, `missing_fields=[]` | `valid=True`, `missing_fields=[]` | **PASS** |
| **Phase 2** | TEST 2: Policy missing required field | `valid=False`, missing `policy_number` | `valid=False`, missing `policy_number` | **PASS** |
| **Phase 2** | TEST 3: Valid medical bill | `valid=True`, `missing_fields=[]` | `valid=True`, `missing_fields=[]` | **PASS** |
| **Phase 2** | TEST 4: Medical bill missing required field | `valid=False`, missing `document_date` | `valid=False`, missing `document_date` | **PASS** |
| **Phase 2** | TEST 5: Valid medical report | `valid=True`, `missing_fields=[]` | `valid=True`, `missing_fields=[]` | **PASS** |
| **Phase 2** | TEST 6: Unrecognized document | `valid=False`, unrecognized category | `valid=False`, unrecognized category | **PASS** |
| **Phase 2** | TEST 7: Empty extraction result | `valid=False`, empty list detected | `valid=False`, empty list detected | **PASS** |
| **Phase 2** | TEST 8: Invalid extracted value | `valid=False`, negative bill amount caught | `valid=False`, negative amount caught | **PASS** |
| **Phase 3** | TEST 1: Valid policy + bill in period | `valid=True`, within period reason | `valid=True`, within period reason | **PASS** |
| **Phase 3** | TEST 2: Bill date before policy start | `valid=False`, prior to inception | `valid=False`, prior to inception | **PASS** |
| **Phase 3** | TEST 3: Bill date after policy expiry | `valid=False`, after expiry | `valid=False`, after expiry | **PASS** |
| **Phase 3** | TEST 4: Missing policy start date | `valid=False`, missing start date | `valid=False`, missing start date | **PASS** |
| **Phase 3** | TEST 5: Missing policy end date | `valid=False`, missing end date | `valid=False`, missing end date | **PASS** |
| **Phase 3** | TEST 6: Missing bill/report date | `valid=False`, missing document date | `valid=False`, missing document date | **PASS** |
| **Phase 3** | TEST 7: Invalid date format | `valid=False`, unparseable date | `valid=False`, unparseable date | **PASS** |
| **Phase 3** | TEST 8: Mixed valid/invalid docs | `valid=False`, individual 2 PASS, 1 FAIL | `valid=False`, individual 2 PASS, 1 FAIL | **PASS** |
| **E2E** | Full 3-Tool Chain on Real PDFs | PDF -> Extract -> Validate -> Validity | 4 pages processed, dates compared, intermediate table | **PASS** |

---

## 8. End-to-End Execution Trace

Example run on the two real PDF documents in the repository:
1. `4225IELVT38453879200000_policy_copy.pdf` (ICICI Lombard Elevate Floater Policy)
2. `DOCUMENTS FOR Re- activation REQUEST OF CLAIM NO.95151709.pdf` (Shree Vallabh Hospital Records)

```
================================================================================
FINAL INTERMEDIATE OBSERVATION TABLE FOR AGENT
================================================================================
Sr.No  | Document Title                      | Type               | Page  | Validation | Period Check
-----------------------------------------------------------------------------------------------------
1      | ICICI Lombard Health AdvantEdge /   | insurance_policy   | 1     | PASS       | POLICY BASE
2      | Shree Vallabh Hospital Indoor Admi  | hospital_document  | 1     | PASS       | FAIL (Pre-Policy)
3      | Shree Vallabh Hospital Final Inpat  | medical_bill       | 2     | PASS       | FAIL (Pre-Policy)
4      | Pathology Diagnostic Investigation  | medical_report     | 3     | PASS       | FAIL (Pre-Policy)

SUMMARY REASONS FOR CLAIM DECISION:
 - Policy dates are available and valid (12/03/2025 to 11/03/2028).
 - Document date (19/10/2024) falls outside the policy validity period: prior to policy inception (12/03/2025) on page 1.
 - Document date (25/10/2024) falls outside the policy validity period: prior to policy inception (12/03/2025) on page 2.
 - Document date (20/10/2024) falls outside the policy validity period: prior to policy inception (12/03/2025) on page 3.
 - Patient name 'PARTH M. PATHAK' successfully matched against covered policy member(s).
```

---

## 9. Phase 4: Dynamic Missing-Document Detection

### Architectural Shift: Old Design vs. New Dynamic Design

| Dimension | Old Design (Legacy) | New Design (Dynamic Agentic) |
| :--- | :--- | :--- |
| **Requirement Source** | Static list hardcoded in Python code | **Dynamically extracted by LLM from actual policy document** |
| **Fixed Assumption** | Assumed all claims need discharge summary & bills | **No assumptions**: Only requires what the specific policy states |
| **Document Matching** | Simple string/contains matching or static synonyms | **Semantic reasoning** by Gemma 3 (`gemma3:latest` on local Ollama) |
| **Page Traceability** | Arbitrary or manual | **1-indexed page number strictly preserved from Phase 1** |
| **Missing Status** | Static dictionary lookup | `missing=true` -> `page_no=null`; `missing=false` -> exact `page_no` |

### Integrated Pipeline Flow:
```
        PDF Document(s)
              │
              ▼
           PHASE 1: Qwen-VL Vision Extractor
              │
       ┌───────┴────────────────────────┐
       ▼                                ▼
Policy Information             Submitted Claim Documents
       │                                │
       ▼                                │
Dynamic Policy Requirements            │
       │                                │
       ▼                                │
PHASE 2: Field Validation              │
       │                                │
       ▼                                │
PHASE 3: Validity Checker              │
       │                                │
       └───────┬────────────────────────┘
               │
               ▼
    PHASE 4: Gemma 3 LLM Gateway (http://localhost:11434)
               │
       (Semantic Equivalence Matching + Exactly-Once Retry)
               │
               ▼
    Final Missing Document Checklist Table
```

### Example Output (Illustrative Demonstration Only):
```markdown
| Sr.No | Document Title | Missing or not | Page No. |
| :---: | :------------- | :------------: | :------: |
| 1 | Original Discharge Summary | No | 5 |
| 2 | Final Hospital Bill | No | 7 |
| 3 | Investigation Reports | Yes | null |
```
*(Note: The document titles above are illustrative examples. The production system produces titles dynamically matching the uploaded policy).*

---

## 10. Agentic Readiness & Tool Registry

All four modules are encapsulated as standardized callable tools ready to be registered directly with an Agent Orchestrator:

1. **`QwenVLExtractionTool`** (`tools/qwen_vl_tool.py`): Extracts visual documents with 1-indexed pages and zero disk images.
2. **`DocumentValidationTool`** (`tools/document_validation_tool.py`): Deterministically checks required field completeness per document category.
3. **`ValidityCheckerTool`** (`tools/validity_checker_tool.py`): Deterministically verifies claim dates against policy coverage term and checks patient identity.
4. **`MissingDocumentTool` / `MissingDocumentDetectorTool`** (`tools/missing_document_tool.py`): Dynamically determines required documents from policy terms and semantically compares submitted claim documents.

Registry in `tools/__init__.py`:
```python
from tools import get_insuremate_tools, MissingDocumentTool

# Register all 4 tools in one line:
tools = get_insuremate_tools()
```

---

## 11. Command-Line Usage

```bash
# Run full 4-phase end-to-end pipeline:
python main.py --end-to-end

# Run complete test suite (Phase 1, Phase 2, Phase 3, Phase 4, and End-to-End):
python main.py --test-all

# Run Phase 4 detector independently:
python run_phase4.py --demo-policy-a
python run_phase4.py --demo-policy-b

# Run Phase 4 dedicated test suite (8 mandatory dynamic tests + anti-hardcoding):
python -m pytest tests/test_phase4.py -v

# Run full project pytest suite:
python -m pytest -v
```

