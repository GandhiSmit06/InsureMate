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
├── .env.example                               # Environment template for Qwen-VL & Ollama credentials
├── .gitignore                                 # Git ignore file (preserves test PDF fixtures)
├── requirements.txt                           # Complete dependencies (FastAPI, pydantic, httpx, winocr)
├── main.py                                    # Unified CLI runner for tools, agent, server, and tests
├── README.md                                  # Comprehensive documentation & setup guide
│
├── agent/                                     # Phase 5: Autonomous Agent Orchestrator & State
│   ├── __init__.py                            # Agent package exports
│   ├── insuremate_agent.py                    # InsureMateAgent main loop & tool coordinator
│   ├── planner.py                             # Multi-step strategic planning engine
│   ├── decision.py                            # Dynamic reactive decision engine
│   ├── state.py                               # ClaimState memory & step snapshots
│   └── tools.py                               # Agent-level tool adapters & registry
│
├── app/                                       # Phase 7: REST API Server & Backend
│   ├── __init__.py                            # Application package exports
│   ├── server.py                              # FastAPI REST API & static file server
│   └── static/                                # Packaged frontend static distribution
│
├── frontend/                                  # Phase 7: Web Application Interface
│   ├── index.html                             # Single Page Application HTML5
│   ├── css/                                   # Vanilla CSS stylesheets (glassmorphism dark UI)
│   │   ├── style.css                          # Core tokens, reset, typography
│   │   ├── dashboard.css                      # Layout, grid, inspection panels
│   │   ├── agent.css                          # Stepper, thought bubble, trace log
│   │   ├── upload.css                         # Drag-and-drop dropzones & demo buttons
│   │   └── responsive.css                     # Mobile & tablet responsiveness
│   └── js/                                    # Modular vanilla JavaScript logic
│       ├── app.js                             # UI event controllers & state coordinator
│       ├── api.js                             # REST API client
│       ├── agent.js                           # Stepper, thought bubble, trace UI
│       ├── claim.js                           # Claim status & inspection renderer
│       ├── documents.js                       # Extracted pages & document cards
│       ├── upload.js                          # File upload & dropzone handler
│       └── utils.js                           # Date, currency, string helpers
│
├── services/                                  # Core Perceptual & Business Logic Services
│   ├── agent_service.py                       # Unified service layer bridging API and Agent
│   ├── database/                              # SQLite persistence & claim memory
│   │   ├── __init__.py                        # Database package exports
│   │   └── db.py                              # Thread-safe SQLite database manager
│   ├── qwen_vl/                               # Phase 1: In-memory PDF & Qwen-VL Vision
│   │   ├── __init__.py                        # Package exports
│   │   ├── pdf_processor.py                   # Multi-page in-memory PDF renderer (pypdfium2/PIL/winocr)
│   │   └── extractor.py                       # Qwen-VL multi-modal extractor & grounded fallback
│   ├── document_validation/                   # Phase 2: Deterministic Document Validation
│   │   ├── __init__.py                        # Package exports
│   │   └── validator.py                       # Required-field rule engine
│   ├── validity_checker/                      # Phase 3: Date Validity & Period Checker
│   │   ├── __init__.py                        # Package exports
│   │   └── checker.py                         # Date normalizer, coverage window checker, identity matcher
│   └── missing_document/                      # Phase 4: Dynamic Missing Document Detection
│       ├── __init__.py                        # Package exports
│       ├── detector.py                        # Semantic document requirement matcher
│       ├── llm_gateway.py                     # Ollama / Gemma 3 gateway with retry
│       ├── ollama_client.py                   # Local Ollama client (http://localhost:11434)
│       ├── prompt_builder.py                  # Structured extraction & matching prompts
│       └── schemas.py                         # Pydantic V2 document requirement models
│
├── tools/                                     # Tool Definitions & Dynamic Executor (Phase 6)
│   ├── __init__.py                            # Agent Tool Registry (get_insuremate_tools)
│   ├── base_tool.py                           # BaseTool abstract interface & schema exporter
│   ├── tool_registry.py                       # Tool discovery & registration catalog
│   ├── tool_executor.py                       # Safe execution wrapper with retries & logging
│   ├── qwen_vl_tool.py                        # QwenVLExtractionTool wrapper
│   ├── document_validation_tool.py            # DocumentValidationTool wrapper
│   ├── validity_checker_tool.py               # ValidityCheckerTool wrapper
│   └── missing_document_tool.py               # MissingDocumentTool wrapper
│
├── utils/                                     # Cross-Cutting Utilities
│   ├── config.py                              # QwenConfig loader and validator
│   └── logger.py                              # Structured logger ([PDF], [AGENT], [API], [RESULT])
│
├── tests/                                     # Comprehensive Test Suite (78 Tests)
│   ├── conftest.py                            # Pytest fixtures and mock LLM clients
│   ├── test_phase1.py                         # Phase 1 unit tests (PDF rendering, page tracking)
│   ├── test_phase2.py                         # Phase 2 unit tests (8 document validation tests)
│   ├── test_phase3.py                         # Phase 3 unit tests (8 date validity tests)
│   ├── test_phase4.py                         # Phase 4 unit tests (15 dynamic detection tests)
│   ├── test_phase5.py                         # Phase 5 unit tests (8 autonomous agent tests)
│   ├── test_phase6_integration.py             # Phase 6 integration tests (ToolExecutor & Agent)
│   ├── test_phase7_api.py                     # Phase 7 REST API tests (FastAPI TestClient)
│   ├── test_phase7_database.py                # Phase 7 SQLite database & memory tests
│   ├── test_phase7_frontend_integration.py    # Phase 7 frontend asset & workflow tests
│   ├── test_phase7_integration.py             # Phase 7 end-to-end agent service integration
│   ├── test_tool_registry.py                  # Tool discovery & catalog tests
│   ├── test_tool_executor.py                  # Safe tool execution & retry tests
│   ├── test_master_fixes.py                   # Concurrency locks, OCR, and real PDF tests
│   └── test_end_to_end.py                     # Full multi-tool pipeline test on PDFs
│
└── [Sample & Diagnostic PDFs]                 # Test fixtures & one-click demo files
    ├── sample_policy.pdf                      # Health floater policy certificate
    ├── sample_claim.pdf                       # Hospital indoor admission & inpatient bill
    ├── policy_A.pdf                           # Health demo policy
    ├── claim_A.pdf                            # Health demo claim
    ├── policy_B.pdf                           # Travel demo policy
    └── claim_B.pdf                            # Travel demo claim
```

---

## 3. Installation

### Prerequisites
- Python 3.10, 3.11, 3.12, or 3.13
- Git
- Windows, macOS, or Linux

---

### Step-by-Step Setup

#### Step 1: Clone the Repository
```bash
git clone https://github.com/GandhiSmit06/InsureMate.git
cd InsureMate
```

#### Step 2: Create & Activate Virtual Environment

**On Windows (PowerShell):**
```powershell
python -m venv .venv
# If PowerShell script execution is restricted, enable it for this session:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
.\.venv\Scripts\Activate.ps1
```

**On Windows (Command Prompt - CMD):**
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

**On macOS / Linux (bash or zsh):**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### Step 3: Upgrade pip & Install Dependencies
```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

> **Note on Dependencies:**
> `requirements.txt` contains all core and phase dependencies:
> - `fastapi`, `uvicorn`, `python-multipart` — Web Application & REST API
> - `pydantic>=2.6.0` — Structured data schemas & validation
> - `pypdfium2>=5.0.0`, `pillow>=10.0.0` — In-memory raster PDF rendering
> - `winocr` — Windows native OCR fallback (automatically installed on Windows, skipped on Linux/macOS)
> - `openai>=1.20.0`, `requests>=2.28.0`, `python-dotenv>=1.0.0` — LLM connectivity & configuration
> - `pytest>=7.0.0`, `httpx>=0.24.0` — Test framework and FastAPI TestClient

---

## 4. Environment Configuration & Setup

InsureMate includes a ready-to-use template file `.env.example`.

Create your local `.env` configuration:

**On Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

**On Windows (Command Prompt):**
```cmd
copy .env.example .env
```

**On macOS / Linux:**
```bash
cp .env.example .env
```

### Config Options (`.env`):
```ini
# 1. Qwen-VL Vision Extractor Configuration (Phase 1)
# DashScope: https://dashscope.console.aliyun.com/
# OpenRouter: https://openrouter.ai/keys
QWEN_API_KEY=your_dashscope_api_key_here
QWEN_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
QWEN_MODEL_NAME=qwen-vl-max
QWEN_MAX_TOKENS=2048
QWEN_TEMPERATURE=0.1

# 2. Local Ollama & Gemma 3 Configuration (Phase 4 Dynamic Detection)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma3:latest
OLLAMA_TIMEOUT=120
```

> **Zero-Setup Offline & Deterministic Mode:**
> **No API keys or external services are strictly required!**
> If `QWEN_API_KEY` is not provided (or left as placeholder `your_api_key_here`), and Ollama is not running, the system automatically runs in **Deterministic Offline Grounded Mode**.
> All 78 unit, integration, API, and end-to-end tests run reliably offline with 100% pass rate.

## 5. Tool Usage & Execution Instructions

### A. Phase 1: Qwen-VL Document Extraction Tool
Converts PDF pages into memory images and extracts structured insurance fields:
```bash
python main.py --phase 1 --max-pages 2 --pdf "sample_policy.pdf"
```

Programmatic Usage:
```python
from tools.qwen_vl_tool import QwenVLExtractionTool

tool = QwenVLExtractionTool()
result = tool.run(pdf_path="sample_policy.pdf", max_pages=1)
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
        "patient_name": "Jane Doe",
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
    "insured_names": ["John Doe", "Jane Doe"]
}
claim_docs = [
    {
        "page_number": 2,
        "document_type": "medical_bill",
        "document_date": "15/08/2026",
        "patient_name": "Jane Doe"
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

### Option A: Run Full Pytest Suite (Recommended & Cross-Platform)
```bash
# Universally reliable command on Windows (PowerShell/CMD) and macOS/Linux:
python -m pytest

# Run with concise progress:
python -m pytest -q

# Run with detailed verbose output:
python -m pytest -v
```

### Option B: Run via Unified CLI Runner
```bash
python main.py --test-all
```

### Option C: Run Phase-Specific Test Modules
```bash
# Phase 1: PDF rendering in RAM, 1-indexed page tracking & no hallucination
python tests/test_phase1.py

# Phase 2: All 8 mandatory document validation scenarios
python tests/test_phase2.py

# Phase 3: All 8 mandatory date validity scenarios
python tests/test_phase3.py

# Phase 4: Dynamic missing document detection (15 tests)
python tests/test_phase4.py

# Phase 5: Autonomous InsureMate Agent Orchestrator (8 tests)
python tests/test_phase5.py

# Phase 6: Tool registry & executor integration tests
python -m pytest tests/test_phase6_integration.py tests/test_tool_registry.py tests/test_tool_executor.py

# Phase 7: REST API, SQLite database, and frontend integration tests
python -m pytest tests/test_phase7_api.py tests/test_phase7_database.py tests/test_phase7_frontend_integration.py tests/test_phase7_integration.py

# End-to-end integration test on documents
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

Example run on sample insurance and claim documents:
1. `sample_policy.pdf` (Comprehensive Health Floater Policy)
2. `sample_claim.pdf` (Hospital Admission and Inpatient Bill Records)

```
================================================================================
FINAL INTERMEDIATE OBSERVATION TABLE FOR AGENT
================================================================================
Sr.No  | Document Title                      | Type               | Page  | Validation | Period Check
-----------------------------------------------------------------------------------------------------
1      | Health Floater Certificate          | insurance_policy   | 1     | PASS       | POLICY BASE
2      | Hospital Indoor Admission Record    | hospital_document  | 1     | PASS       | FAIL (Pre-Policy)
3      | Hospital Final Inpatient Bill       | medical_bill       | 2     | PASS       | FAIL (Pre-Policy)
4      | Pathology Diagnostic Investigation  | medical_report     | 3     | PASS       | FAIL (Pre-Policy)

SUMMARY REASONS FOR CLAIM DECISION:
 - Policy dates are available and valid (12/03/2025 to 11/03/2028).
 - Document date (19/10/2024) falls outside the policy validity period: prior to policy inception (12/03/2025) on page 1.
 - Document date (25/10/2024) falls outside the policy validity period: prior to policy inception (12/03/2025) on page 2.
 - Document date (20/10/2024) falls outside the policy validity period: prior to policy inception (12/03/2025) on page 3.
 - Patient name 'Jane Doe' successfully matched against covered policy member(s).
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

## 10. Complete Multi-Phase Agent Architecture (Phases 1–7)

The InsureMate system is structured as an end-to-end autonomous agentic workflow:

```
                    USER / WEB UI
                          │ (Upload Policy & Claim PDFs)
                          ▼
               FASTAPI REST API SERVER
             (Session ID & Upload Staging)
                          │
                          ▼
                  AGENT SERVICE LAYER
                          │
                          ▼
                  INSUREMATE AGENT
            (Autonomous Planning & Reasoning)
                          │
                          ▼
                    TOOL REGISTRY
                          │
                          ▼
                    TOOL EXECUTOR
                          │
          ┌───────────────┼───────────────┬───────────────────┐
          │               │               │                   │
          ▼               ▼               ▼                   ▼
      Qwen-VL        Document          Claim               Dynamic
     Extraction     Validation        Validity             Missing
        Tool           Tool           Checker             Documents
     (Phase 1)      (Phase 2)        (Phase 3)            (Phase 4)
          │               │               │                   │
          └───────────────┼───────────────┴───────────────────┘
                          │
                          ▼
                     CLAIM STATE
             (Snapshot Memory & Audit Trail)
                          │
                          ▼
                 DECISION ENGINE
             (Final Readiness Verdict)
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
   SQLITE DATABASE                  MODERN WEB UI
   - claims                         - Glassmorphism dark aesthetic
   - tool_executions                - Live 6-step progress stepper
   - claim_state_snapshots          - Interactive Agent reasoning
   - final_reports                  - Missing Evidence Checklist
                                    - Date Validity Analysis
                                    - Audit trail & Claim memory
```

---

## 11. Phase 7: Web Application & UI Features

InsureMate Phase 7 introduces an end-to-end fullstack interface crafted with vanilla HTML5, modern CSS3 (glassmorphic dark design with custom micro-animations), and reactive JavaScript:

### Key UI Features:
1. **Document Upload Hub:**
   - Drag-and-drop file upload zones for Insurance Policy PDFs and Incident/Claim PDFs.
   - Quick Demo preset buttons (`Health Claim Demo` and `Travel Claim Demo`) for instant one-click demonstration.
   - Configurable analysis goal and deterministic execution mode toggles.
2. **Interactive 6-Step Progress Stepper:**
   - Visual step indicator tracking: Session Init ➔ Document Extraction ➔ Validation ➔ Validity Check ➔ Missing Evidence ➔ Claim Preparation.
   - Dynamic step states (`active`, `completed`, `error`) with pulse indicators.
3. **Agent Thought Bubble & Live Trace:**
   - Real-time display of the Agent's reasoning, active tool selections, and intermediate observations.
4. **Final Readiness Verdict Banner:**
   - High-contrast visual verdict cards for `CLAIM_READY_FOR_SUBMISSION` (Emerald), `ACTION_REQUIRED_MISSING_DOCS` (Amber), and `INVALID_CLAIM_DATES` (Rose).
   - High-level metric counters: Pages Analyzed, Validation Pass Rate, Required Docs Found, Missing Items.
5. **Multi-Tab Inspection Panels:**
   - **Missing Evidence Table:** Dynamic checklist matching policy requirements against submitted claim evidence with 1-indexed page links.
   - **Validity Analysis:** Multi-date comparison table, coverage window check, and patient identity verification.
   - **Extracted Pages:** Extracted document entities, classifications, and page numbers.
   - **Tool Audit Log:** Chronological record of tool invocations, inputs, execution duration, and outputs.
   - **Raw JSON:** Full inspection of the final claim readiness package.
6. **Claim History & Memory Sidebar:**
   - Persistent claim session recall allowing users to inspect past analyzed claims directly from SQLite database memory.

---

## 12. Phase 7: Database Architecture & Claim Memory

InsureMate persists all claim sessions, intermediate execution envelopes, and final reports using a thread-safe SQLite database (`services/database/db.py`):

- **`claims` Table:** Stores session ID, name, goal, policy/claim file paths, claim type, status, and timestamps.
- **`tool_executions` Table:** Audit log storing each tool call, parameters, execution time (ms), success flag, and output data.
- **`claim_state_snapshots` Table:** Serialized intermediate `ClaimState` snapshots taken at each phase.
- **`final_reports` Table:** Structured final readiness report, verdict, missing count, validity pass flag, and decision summary.

Foreign keys with `ON DELETE CASCADE` ensure complete data consistency upon session deletion.

---

## 13. REST API Endpoints

The Phase 7 FastAPI application exposes the following endpoints:

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Serves the InsureMate Phase 7 Single Page Application |
| `GET` | `/api/health` | Health check verifying tool registry and database connectivity |
| `GET` | `/api/tools` | Discovers registered tools and their JSON schemas |
| `POST` | `/api/claims/upload` | Uploads PDF files, creates session, and optionally auto-runs agent |
| `POST` | `/api/claims/demo` | Creates preset demo session (`health` or `travel`) |
| `POST` | `/api/claims/{id}/run` | Triggers autonomous Agent execution on an existing claim |
| `GET` | `/api/claims/{id}` | Fetches complete claim memory bundle (state, tools, report) |
| `GET` | `/api/claims` | Lists historical claim sessions with pagination |
| `DELETE` | `/api/claims/{id}` | Deletes a claim session and cleans up uploaded files |

---

## 14. How to Run

### Option A: Launch Web Application (Phase 7 UI)
```bash
# Launch via CLI shortcut:
python main.py --app

# Or launch specifying custom port/host:
python main.py --serve --port 8000

# Open your browser at:
# http://localhost:8000
```

### Option B: Run Autonomous Agent via CLI (Phase 5/6)
```bash
# Run agent on repository sample documents (offline deterministic mode):
python main.py --agent --offline

# Run agent with specific documents:
python main.py --agent --policy policy_A.pdf --claim claim_A.pdf --goal "Verify hospitalization claim"
```

### Option C: Run Complete Test Suite
```bash
# Run complete test suite across all 7 phases (78 tests):
python -m pytest

# Run via unified CLI runner:
python main.py --test-all

# Run Phase 7 specific tests:
python -m pytest tests/test_phase7_database.py tests/test_phase7_api.py tests/test_phase7_integration.py
```
*(All 78/78 tests pass with 100% pass rate).*

---

## 15. Troubleshooting & Cloning Guide (Quick Fixes)

If you or a collaborator cloned the repository and encountered errors, check the solutions below:

### 1. `ModuleNotFoundError: No module named 'httpx'`
- **Reason:** FastAPI's `TestClient` (used in API and integration tests) requires `httpx`.
- **Fix:** Update dependencies by running:
  ```bash
  python -m pip install -r requirements.txt
  ```

### 2. `ImportError: cannot import name 'field_validator' from 'pydantic'`
- **Reason:** An older version of Pydantic (v1) was installed in your Python environment. InsureMate requires Pydantic v2.
- **Fix:** Run:
  ```bash
  python -m pip install "pydantic>=2.6.0"
  ```

### 3. `pytest : The term 'pytest' is not recognized as the name of a cmdlet...` (Windows)
- **Reason:** The virtual environment's `Scripts/` directory is not in your Windows system PATH in PowerShell.
- **Fix:** Always invoke pytest through python module syntax:
  ```bash
  python -m pytest
  ```
  Or use the unified CLI runner:
  ```bash
  python main.py --test-all
  ```

### 4. `File ...\Activate.ps1 cannot be loaded because running scripts is disabled on this system` (PowerShell)
- **Reason:** Windows PowerShell disables running unsigned script files by default.
- **Fix:** Allow script execution for the current PowerShell terminal session:
  ```powershell
  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
  .\.venv\Scripts\Activate.ps1
  ```

### 5. Missing Sample PDF Documents (`Target policy document does not exist` or `Diagnostic file ... must exist`)
- **Reason:** Previous `.gitignore` ignored `*.pdf`, preventing sample test fixture PDFs from being pulled.
- **Fix:** `.gitignore` has now been updated to whitelist and preserve essential test fixtures (`sample_policy.pdf`, `sample_claim.pdf`, `policy_A.pdf`, `claim_A.pdf`, `policy_B.pdf`, `claim_B.pdf`, and `4225IELVT38453879200000_policy_copy.pdf`). Pull the latest changes:
  ```bash
  git pull origin main
  ```

### 6. Scanned PDF Native OCR (Windows)
- **Reason:** Scanned PDFs lacking digital text fall back to Windows native Media OCR via `winocr`.
- **Fix:** `winocr>=0.0.14` is included in `requirements.txt` with the Windows environment marker `sys_platform == "win32"`. It installs automatically on Windows and is skipped on macOS/Linux.

### 7. Port 8000 Already In Use
- **Reason:** Another web service is running on port 8000.
- **Fix:** Launch InsureMate on a different port:
  ```bash
  python main.py --serve --port 8080
  ```

### 8. Ollama or Qwen-VL API Key Not Configured
- **Reason:** You don't have paid API keys or a local Ollama daemon running.
- **Fix:** **Zero setup needed!** InsureMate automatically falls back to **Deterministic Grounded Mode**. All tests, demos, and claim preparation features function smoothly out-of-the-box without network connectivity or external LLM dependencies.



