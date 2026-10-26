<p align="center">
  <img src="frontend/assets/animated-header.svg" alt="InsureMate Autonomous Claim Agent" width="800" style="max-width: 100%; height: auto;" />
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10+-38BDF8.svg?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10+" /></a>
  <a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/FastAPI-0.110+-059669.svg?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" /></a>
  <a href="https://docs.pydantic.dev/"><img src="https://img.shields.io/badge/pydantic-v2-E11D48.svg?style=for-the-badge&logo=pydantic&logoColor=white" alt="Pydantic v2" /></a>
  <a href="tests/"><img src="https://img.shields.io/badge/tests-102%20passed-10B981.svg?style=for-the-badge&logo=pytest&logoColor=white" alt="Tests" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-8B5CF6.svg?style=for-the-badge" alt="License: MIT" /></a>
</p>

---

## 1. Project Purpose & System Overview

**InsureMate** is an enterprise-grade Agentic AI insurance claim preparation and adjudication system. It empowers policyholders, agents, and claims adjudicators to inspect, validate, audit, and verify health and travel insurance claims autonomously.

Unlike traditional static rule engines or brittle pipeline scripts, InsureMate operates as an **autonomous agent** capable of:
1. Formulating strategic multi-step hypotheses and analysis plans.
2. Selecting and invoking tools dynamically based on real-time document observations.
3. Adapting and re-planning when deficiencies, discrepancies, or unreadable scans are detected.
4. Extracting requirements dynamically from real policy clauses rather than hardcoded checklists.
5. Persisting complete intermediate audit traces and claim state snapshots in SQLite memory.
6. Presenting findings through an interactive glassmorphic web dashboard with real-time thought bubbles, progress steppers, and readiness verdicts.

### The Complete 6-Stage Autonomous Lifecycle:

```
┌─────────────────┐     ┌─────────────────────┐     ┌──────────────────────┐
│ 1. Policy       │ ──> │ 2. Document         │ ──> │ 3. Field             │
│    Analyzer     │     │    Extractor        │     │    Completeness      │
│ (Clauses & Sum) │     │ (Qwen-VL + winocr)  │     │ (Rule Validation)    │
└─────────────────┘     └─────────────────────┘     └──────────────────────┘
                                                               │
┌─────────────────┐     ┌─────────────────────┐                ▼
│ 6. Claim        │ <── │ 5. Missing Evidence │ <── ┌──────────────────────┐
│    Preparation  │     │    Detector         │     │ 4. Period & Identity │
│ (Readiness Pkg) │     │ (Gemma 3 / Dynamic) │     │    Validity Checker  │
└─────────────────┘     └─────────────────────┘     └──────────────────────┘
```

---

## 2. Full System Architecture & Directory Structure

```
InsureMate/
├── .env.example                               # Environment template for Qwen-VL & Ollama credentials
├── .env                                       # Local environment configuration
├── .gitignore                                 # Git ignore configuration (preserves test PDF fixtures)
├── requirements.txt                           # Production and test dependencies
├── main.py                                    # Unified CLI runner for tools, agent, server, and tests
├── PHASE_6_INTEGRATION.md                     # Technical handoff specification for Tool Layer & Registry
├── README.md                                  # Comprehensive documentation & system guide
├── insuremate.db                              # SQLite database (claims, traces, snapshots, reports)
│
├── agent/                                     # Phase 5: Autonomous Agent Orchestrator & State
│   ├── __init__.py                            # Agent package exports
│   ├── insuremate_agent.py                    # InsureMateAgent main loop, executor & coordinator
│   ├── planner.py                             # Multi-step strategic planning & dynamic replanning
│   ├── decision.py                            # Reactive LLM/grounded decision engine
│   ├── state.py                               # ClaimState memory container, traces & snapshots
│   └── tools.py                               # Agent-level tool adapters & registry interface
│
├── app/                                       # Phase 7: REST API Server & Backend
│   ├── __init__.py                            # Application package exports
│   └── server.py                              # FastAPI REST API & static asset server
│
├── frontend/                                  # Phase 7: Modern Web UI (Single Page Application)
│   ├── index.html                             # Semantic HTML5 glassmorphic dashboard
│   ├── css/                                   # Vanilla CSS stylesheets
│   │   ├── style.css                          # Design tokens, reset, typography, cards
│   │   ├── dashboard.css                      # Grid layout, metric cards, inspection panels
│   │   ├── agent.css                          # 6-step progress stepper, thought bubble, trace log
│   │   ├── upload.css                         # Drag-and-drop dropzones & preset demo buttons
│   │   └── responsive.css                     # Mobile and tablet responsiveness
│   └── js/                                    # Modular vanilla JavaScript logic
│       ├── app.js                             # App coordinator & UI event handlers
│       ├── api.js                             # REST API client for backend communication
│       ├── agent.js                           # Progress stepper, thought bubble & trace animations
│       ├── claim.js                           # Claim status & verdict card renderer
│       ├── documents.js                       # Extracted page view & metadata cards
│       ├── upload.js                          # Drag-and-drop upload & preset loader
│       ├── state.js                           # Client-side state manager
│       └── utils.js                           # Date, currency, badge & string formatters
│
├── services/                                  # Core Perceptual & Business Logic Services
│   ├── agent_service.py                       # Unified service layer bridging API and Agent
│   ├── database/                              # SQLite persistence & claim memory
│   │   ├── __init__.py                        # Database package exports
│   │   └── db.py                              # Thread-safe SQLite manager & migrations
│   ├── qwen_vl/                               # Phase 1: In-Memory PDF & Vision Extractor
│   │   ├── __init__.py                        # Package exports
│   │   ├── pdf_processor.py                   # Multi-page in-memory PDF renderer (pypdfium2/winocr)
│   │   └── extractor.py                       # Structured vision entity extractor & grounded fallback
│   ├── document_validation/                   # Phase 2: Deterministic Document Validation
│   │   ├── __init__.py                        # Package exports
│   │   └── validator.py                       # Required-field completeness engine
│   ├── validity_checker/                      # Phase 3: Date Validity & Period Checker
│   │   ├── __init__.py                        # Package exports
│   │   └── checker.py                         # Date normalizer, coverage window checker, identity matcher
│   └── missing_document/                      # Phase 4: Dynamic Missing Document Detection
│       ├── __init__.py                        # Package exports
│       ├── detector.py                        # Semantic document requirement matcher
│       ├── llm_gateway.py                     # Local Ollama / Gemma 3 gateway with retry
│       ├── ollama_client.py                   # Lightweight local Ollama HTTP client
│       ├── prompt_builder.py                  # Structured extraction & matching prompts
│       └── schemas.py                         # Pydantic V2 document requirement models
│
├── tools/                                     # Phase 6: Standardized Tool Catalog & Safe Executor
│   ├── __init__.py                            # Tool registry exports
│   ├── base_tool.py                           # BaseTool abstract interface & schema generator
│   ├── claim_state.py                         # Shared claim state container for Phase 6 tools
│   ├── tool_registry.py                       # Tool discovery, cataloging & registration
│   ├── tool_executor.py                       # Safe execution wrapper with timing, logging & retry
│   ├── qwen_extraction_tool.py                # DocumentExtractionTool (Qwen-VL multimodal)
│   ├── qwen_vl_tool.py                        # QwenVLExtractionTool alias
│   ├── document_validation_tool.py            # DocumentValidationTool wrapper
│   ├── validity_checker_tool.py               # ValidityCheckerTool wrapper
│   ├── missing_document_tool.py               # MissingDocumentTool wrapper
│   ├── policy_clause_search_tool.py           # PolicyClauseSearchTool
│   └── cross_document_consistency_tool.py     # CrossDocumentConsistencyTool
│
├── tests/                                     # Comprehensive Test Suite (102 Tests across 20 Suites)
    ├── conftest.py                            # Pytest fixtures and mock LLM clients
    ├── test_dynamic_agent.py                  # Dynamic agent reasoning & adaptive execution (12 tests)
    ├── test_extraction_tool.py                # DocumentExtractionTool schema & wrapper (7 tests)
    ├── test_master_fixes.py                   # Master concurrency locks, OCR & real PDFs (3 tests)
    ├── test_missing_document_tool.py          # MissingDocumentTool wrapper (3 tests)
    ├── test_phase1.py                         # Phase 1: In-memory PDF, page tracking & no hallucination (5 tests)
    ├── test_phase2.py                         # Phase 2: Document field validation rules (8 tests)
    ├── test_phase3.py                         # Phase 3: Date validity & identity matching (8 tests)
    ├── test_phase4.py                         # Phase 4: Dynamic missing document detection (15 tests)
    ├── test_phase5.py                         # Phase 5: Autonomous agent planning & loop guardrails (8 tests)
    ├── test_phase6_integration.py             # Phase 6: Tool registry & executor integration (4 tests)
    ├── test_phase7_api.py                     # Phase 7: FastAPI REST endpoints & TestClient (6 tests)
    ├── test_phase7_database.py                # Phase 7: SQLite schema & memory persistence (7 tests)
    ├── test_phase7_frontend_integration.py    # Phase 7: Frontend static serving & HTML structure (4 tests)
    ├── test_phase7_integration.py             # Phase 7: AgentService lifecycle & session tracking (3 tests)
    ├── test_readiness_distinction.py          # Distinction between ready, missing docs & invalid dates (5 tests)
    ├── test_tool_executor.py                  # Safe tool execution, timeouts & retries (5 tests)
    ├── test_tool_registry.py                  # Tool discovery, catalogs & schema export (4 tests)
    ├── test_validation_tool.py                # DocumentValidationTool adapter testing (2 tests)
    ├── test_validity_tool.py                  # ValidityCheckerTool adapter testing (3 tests)
    └── test_end_to_end.py                     # Multi-phase real PDF pipeline execution (1 test)

```

---

## 3. Installation & Environment Setup

### System Prerequisites
- **Python**: Version 3.10, 3.11, 3.12, or 3.13
- **Operating System**: Windows 10/11, macOS (Intel/Apple Silicon), or Linux (Ubuntu, Debian, CentOS)
- **Git**

---

### Step-by-Step Installation

#### Step 1: Clone the Repository
```bash
git clone https://github.com/GandhiSmit06/InsureMate.git
cd InsureMate
```

#### Step 2: Create & Activate Virtual Environment

**On Windows (PowerShell):**
```powershell
python -m venv .venv
# If script execution is restricted in PowerShell, permit it for the process:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
.\.venv\Scripts\Activate.ps1
```

**On Windows (Command Prompt - CMD):**
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

**On macOS / Linux (bash/zsh):**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### Step 3: Upgrade pip & Install Dependencies
```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

#### Dependencies Overview (`requirements.txt`):
| Package | Version | Purpose |
| :--- | :--- | :--- |
| `fastapi` | `>=0.110.0` | High-performance async web framework for REST API |
| `uvicorn` | `>=0.28.0` | Production ASGI web server |
| `python-multipart`| `>=0.0.9` | Multipart form parsing for PDF file uploads |
| `pydantic` | `>=2.6.0` | Pydantic V2 data validation and schema definitions |
| `pypdfium2` | `>=5.0.0` | In-memory PDF rasterizer (0 temporary disk files) |
| `pillow` | `>=10.0.0` | High-performance image manipulation in memory |
| `winocr` | `>=0.0.14` | Native Windows Media OCR engine for scanned PDFs |
| `openai` | `>=1.20.0` | OpenAI-compatible client for DashScope / OpenRouter Qwen-VL |
| `requests` | `>=2.28.0` | HTTP communications for local Ollama daemon |
| `python-dotenv` | `>=1.0.0` | Automatic `.env` environment loading |
| `pytest` | `>=7.0.0` | Test discovery and test execution suite |
| `httpx` | `>=0.24.0` | Async HTTP client for FastAPI `TestClient` |
| `reportlab` | `>=3.6.0` | Synthetic test PDF generation scripts |

---

## 4. Configuration & Offline Mode

InsureMate provides a ready-to-use `.env.example` template.

Create your local configuration:

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
# DashScope (Alibaba): https://dashscope.console.aliyun.com/
# OpenRouter: https://openrouter.ai/keys
QWEN_API_KEY=your_dashscope_api_key_here
QWEN_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
QWEN_MODEL_NAME=qwen-vl-max
QWEN_MAX_TOKENS=2048
QWEN_TEMPERATURE=0.1

# 2. Local Ollama & Gemma 3 Configuration (Phase 4 Dynamic Detection & Phase 5 Reasoning)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma3:latest
OLLAMA_TIMEOUT=120
```

> [!NOTE]
> ### Zero-Setup Deterministic Grounded Mode
> **No external API keys or background Ollama daemons are required to run InsureMate!**
> If `QWEN_API_KEY` is not provided and Ollama is not active, InsureMate automatically runs in **Deterministic Offline Grounded Mode**.
> - In-memory PDF rendering works 100% locally using `pypdfium2` and `winocr`.
> - Document field validation and date validity checks run deterministically via Python rule engines.
> - Policy requirement reasoning uses grounded semantic deduction from extracted policy clauses.
> - All **102 unit, integration, API, and end-to-end tests run reliably offline with a 100% pass rate**.

---

## 5. Phase-by-Phase Technical Specifications

### Phase 1: Qwen-VL Multimodal Vision Extraction Tool
- **Implementation**: [`services/qwen_vl/`](file:///d:/InsureMate/services/qwen_vl/) & [`tools/qwen_extraction_tool.py`](file:///d:/InsureMate/tools/qwen_extraction_tool.py)
- **Zero Temporary Disk Files**: Converts multi-page PDFs to in-memory PIL raster images via `pypdfium2`. Zero `.png` or `.jpg` temporary files are written to disk.
- **Scanned Document Native OCR**: When embedded digital text is absent, falls back to Windows native `winocr` or vision understanding without sending heavy loads to external LLMs.
- **Strict 1-Indexed Page Tracking**: Every entity extracted retains its exact physical PDF page number.
- **Zero Hallucination Policy**: Fields not visible in the document return `None`/`null`; values are never fabricated.

### Phase 2: Deterministic Document Completeness Validation
- **Implementation**: [`services/document_validation/`](file:///d:/InsureMate/services/document_validation/) & [`tools/document_validation_tool.py`](file:///d:/InsureMate/tools/document_validation_tool.py)
- **Fast Rule Engine**: Validates metadata against document schemas without making expensive LLM calls.
- **Supported Document Types**:
  - `insurance_policy`: Requires policy number, validity start date, validity end date, policy holder name.
  - `medical_bill`: Requires document date, bill number, patient name, bill amount (> 0).
  - `hospital_document`: Requires document date, patient name, hospital name.
  - `medical_report`: Requires report date, patient name, diagnostic facility/hospital.
  - `invoice`: Requires invoice number, invoice date, customer/patient name, amount.
  - `incident_document`: Requires incident date, description, reporting entity.

### Phase 3: Claim Validity & Policy Period Checker
- **Implementation**: [`services/validity_checker/`](file:///d:/InsureMate/services/validity_checker/) & [`tools/validity_checker_tool.py`](file:///d:/InsureMate/tools/validity_checker_tool.py)
- **Multi-Format Date Normalization**: Automatically normalizes ISO, Indian (`DD/MM/YYYY`), US (`MM/DD/YYYY`), and natural textual dates (`15 Aug 2026`).
- **Coverage Period Verification**: Verifies whether incident and hospital billing dates fall strictly within the active policy window (`policy_start_date` to `policy_end_date`).
- **Patient Identity Matching**: Compares claimant names against floater policy schedules and lists of insured family members using case-insensitive token matching.

### Phase 4: Dynamic Missing Document Detection
- **Implementation**: [`services/missing_document/`](file:///d:/InsureMate/services/missing_document/) & [`tools/missing_document_tool.py`](file:///d:/InsureMate/tools/missing_document_tool.py)
- **Architectural Shift**: Eliminates hardcoded document requirement lists. Requirements are dynamically reasoned from the actual policy text by Gemma 3 or grounded semantic deduction.
- **Distinct Requirements for Distinct Policies**:
  - Health Policy (e.g. `policy_A.pdf`): Dynamically extracts requirements for Discharge Summary and Final Hospital Bill.
  - Travel Policy (e.g. `policy_B.pdf`): Dynamically extracts requirements for Police FIR / Complaint and Travel Boarding Pass / Ticket.
- **Robust Error Recovery**: Built-in JSON extraction, Pydantic V2 schema validation, and exactly-once LLM retry for malformed responses.

### Phase 5: Autonomous InsureMate Agent Orchestrator
- **Implementation**: [`agent/insuremate_agent.py`](file:///d:/InsureMate/agent/insuremate_agent.py), [`agent/planner.py`](file:///d:/InsureMate/agent/planner.py), [`agent/decision.py`](file:///d:/InsureMate/agent/decision.py), [`agent/state.py`](file:///d:/InsureMate/agent/state.py)
- **Multi-Step Strategic Planning**: Decomposes natural language goals into open questions and advisory plan steps. Dynamically adapts or abandons plan branches upon observing document defects.
- **Autonomous Tool Calling Loop**: Selects tools dynamically conditioned on intermediate observations without hardcoding any static sequence.
- **Context & Memory Container**: Maintains `ClaimState` across all intermediate steps with audit traces, tool inputs/outputs, timing, and snapshot history.
- **Guardrails**: Hard limit on iterations (`max_iterations`), single-retry failure policy per tool, and clean trace formatting without exposed internal Chain-of-Thought.

### Phase 6: Standardized Tool Registry & Safe Executor Layer
- **Implementation**: [`tools/`](file:///d:/InsureMate/tools/) & [`PHASE_6_INTEGRATION.md`](file:///d:/InsureMate/PHASE_6_INTEGRATION.md)
- **Catalog & Discovery**: `ToolRegistry` provides dynamic tool registration and exports OpenAI-compatible JSON function calling schemas.
- **Safe Execution Envelope**: `ToolExecutor` wraps all tool invocations with timing (ms), error catching, retry management, and structured logging.
- **Cross-Document Consistency**: `CrossDocumentConsistencyTool` detects cross-document discrepancies (e.g., patient name mismatches between bill and discharge summary, total bill calculation conflicts).
- **Clause Search**: `PolicyClauseSearchTool` scans policy documents for sub-limits, exclusions, and deductibles.

### Phase 7: Modern Fullstack Web UI, REST API & SQLite Claim Memory
- **Implementation**: [`app/server.py`](file:///d:/InsureMate/app/server.py), [`services/agent_service.py`](file:///d:/InsureMate/services/agent_service.py), [`services/database/db.py`](file:///d:/InsureMate/services/database/db.py), [`frontend/`](file:///d:/InsureMate/frontend/)
- **FastAPI Backend**: Provides asynchronous REST API endpoints for uploading documents, initiating agent sessions, polling execution progress, and querying persistent history.
- **Thread-Safe SQLite Memory**: Persists claim sessions, tool execution records, intermediate `ClaimState` snapshots, and final readiness packages.
- **Glassmorphic Web Interface**: Built with modern vanilla HTML5, CSS3, and reactive JavaScript.

---

## 6. Phase 7: Web Application & UI Walkthrough

InsureMate features an interactive, glassmorphic dark-mode web application accessible directly in any modern browser:

### Key Interface Modules:
1. **Document Upload Hub:**
   - Drag-and-drop file dropzones for Policy PDFs and Claim/Incident PDFs.
   - **One-Click Demo Presets**:
     - `Health Claim Demo`: Loads `policy_A.pdf` + `claim_A.pdf`.
     - `Travel Claim Demo`: Loads `policy_B.pdf` + `claim_B.pdf`.
   - Goal configuration and execution mode toggles.
2. **Interactive 6-Step Progress Stepper:**
   - Real-time animated step indicator tracking:
     `Session Init` ➔ `Document Extraction` ➔ `Validation` ➔ `Validity Check` ➔ `Missing Evidence` ➔ `Claim Preparation`.
   - Visual states: `pending`, `active` (pulsing emerald glow), `completed`, and `error`.
3. **Agent Thought Bubble & Live Trace:**
   - Real-time visual bubble rendering the Agent's active reasoning, current action, and intermediate findings.
4. **Final Readiness Verdict Banner:**
   - High-contrast verdict cards:
     - 🟢 **`CLAIM_READY_FOR_SUBMISSION`**: All documents valid, within coverage period, zero missing evidence.
     - 🟡 **`ACTION_REQUIRED_MISSING_EVIDENCE`**: Policy valid, but mandatory documents are missing.
     - 🔴 **`INVALID_CLAIM_DATES`**: Dates fall outside policy coverage or identity mismatch.
   - High-level metric counters: Pages Analyzed, Validation Rate, Required Docs, Missing Items.
5. **Multi-Tab Inspection Panels:**
   - **Missing Evidence Checklist**: Dynamic table showing required items, submission status, and 1-indexed page links.
   - **Validity Analysis**: Policy dates vs claim dates comparison and patient identity verification.
   - **Extracted Pages**: Page-by-page entity inspector displaying detected categories and metadata.
   - **Tool Audit Log**: Chronological record of tool invocations, execution times (ms), and statuses.
   - **Raw JSON**: Complete inspection of the final claim readiness package.
6. **Claim History & Memory Sidebar:**
   - Instant recall of past analyzed claims directly from persistent SQLite database memory.

---

## 7. REST API Reference

The Phase 7 FastAPI application exposes the following RESTful endpoints:

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Serves the InsureMate Phase 7 Web Application (Single Page App) |
| `GET` | `/api/health` | Health check verifying tool registry and database connectivity |
| `GET` | `/api/tools` | Discovers registered tools and their JSON schemas |
| `POST`| `/api/claims/upload` | Uploads PDF files, creates session, and runs autonomous agent |
| `POST`| `/api/claims/demo` | Creates and executes a preset demo session (`health` or `travel`) |
| `POST`| `/api/claims/{id}/run` | Triggers autonomous agent execution on an existing claim session |
| `GET` | `/api/claims/{id}` | Fetches complete claim memory bundle (state, tools, report, snapshots) |
| `GET` | `/api/claims` | Lists historical claim sessions with pagination |
| `DELETE` | `/api/claims/{id}` | Deletes a claim session and cleans up uploaded files |

---

## 8. Database Architecture & Claim Memory

InsureMate persists all claim sessions, intermediate execution envelopes, and final reports using a thread-safe SQLite database (`services/database/db.py`):

```
┌────────────────────────────────────────────────────────┐
│                        CLAIMS                          │
│  claim_id (PK), claim_name, goal, policy_path,         │
│  claim_path, claim_type, status, created_at, updated_at│
└───────────────────────────┬────────────────────────────┘
                            │ 1:N (CASCADE)
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
┌──────────────────┐┌──────────────────┐┌──────────────────┐
│ TOOL_EXECUTIONS  ││CLAIM_STATE_SNAPS ││  FINAL_REPORTS   │
│ execution_id (PK)││ snapshot_id (PK) ││ report_id (PK)   │
│ claim_id (FK)    ││ claim_id (FK)    ││ claim_id (FK)    │
│ tool_name        ││ iteration        ││ is_ready         │
│ parameters       ││ step_name        ││ final_status     │
│ execution_time_ms││ state_snapshot   ││ missing_count    │
│ success          ││ created_at       ││ validity_passed  │
│ output_data      │└──────────────────┘│ decision_summary │
│ created_at       │                    │ full_report_json │
└──────────────────┘                    └──────────────────┘
```

---

## 9. How to Run InsureMate

### Option A: Launch Web Application (Phase 7 UI)
```bash
# Launch using unified CLI shortcut:
python main.py --app

# Or launch specifying custom port and host:
python main.py --serve --port 8000 --host 0.0.0.0

# Open your browser at:
# http://localhost:8000
```

### Option B: Run Autonomous Agent via CLI (Phase 5/6)
```bash
# Run agent on repository sample documents (offline deterministic mode):
python main.py --agent --offline

# Run agent on specific policy and claim documents:
python main.py --agent --policy policy_A.pdf --claim claim_A.pdf --goal "Verify hospitalization claim"
```

### Option C: Run Phase-Specific Tools
```bash
# Phase 1: Qwen-VL Multimodal Document Extraction
python main.py --phase 1 --pdf sample_policy.pdf --max-pages 2

# Phase 2: Document Completeness Validation
python main.py --phase 2

# Phase 3: Claim Validity & Policy Period Check
python main.py --phase 3

# Phase 4: Dynamic Missing Document Detection
python main.py --phase 4 --policy policy_A.pdf

# Complete 4-Phase Pipeline on Real Documents
python main.py --end-to-end
```

### Option D: Regenerate Synthetic Test PDF Fixtures
```bash
# Generate health insurance policy and claim documents:
python scripts/generate_sample_pdfs.py

# Generate overseas travel protection policy and baggage claim documents:
python scripts/generate_travel_policy_and_claim_b.py

# Generate comprehensive 11-page and 16-page test PDFs:
python scripts/generate_comprehensive_test_documents.py
```

---

## 10. Comprehensive Test Suite & Results (102 Tests)

InsureMate includes an exhaustive automated test suite comprising **102 tests across 20 distinct test suites** covering all 7 phases:

### Running the Tests:
```bash
# Option 1: Run full Pytest suite (cross-platform):
python -m pytest

# Option 2: Run with concise progress:
python -m pytest -q

# Option 3: Run via unified CLI runner:
python main.py --test-all

# Option 4: Run specific phase test module:
python tests/test_phase1.py
python tests/test_phase2.py
python tests/test_phase3.py
python tests/test_phase4.py
python tests/test_phase5.py
python -m pytest tests/test_phase7_api.py tests/test_phase7_database.py
```

### Test Suite Breakdown:

| Test Module | Phase / Component | Tests | Primary Focus | Status |
| :--- | :--- | :---: | :--- | :---: |
| [`test_phase1.py`](file:///d:/InsureMate/tests/test_phase1.py) | Phase 1: Qwen-VL Vision | 5 | In-memory RAM rendering (0 disk files), 1-indexed pages, no hallucination | **PASS** |
| [`test_phase2.py`](file:///d:/InsureMate/tests/test_phase2.py) | Phase 2: Field Validation | 8 | 8 mandatory validation scenarios, mandatory fields, amount checks | **PASS** |
| [`test_phase3.py`](file:///d:/InsureMate/tests/test_phase3.py) | Phase 3: Date Validity | 8 | 8 date validity scenarios, normalization, period windows, floater members | **PASS** |
| [`test_phase4.py`](file:///d:/InsureMate/tests/test_phase4.py) | Phase 4: Missing Evidence | 15 | Dynamic requirement extraction from clauses, Gemma 3 reasoning, retries | **PASS** |
| [`test_phase5.py`](file:///d:/InsureMate/tests/test_phase5.py) | Phase 5: Autonomous Agent | 8 | Multi-step planning, dynamic tool selection, loop guardrails, safe trace | **PASS** |
| [`test_phase6_integration.py`](file:///d:/InsureMate/tests/test_phase6_integration.py) | Phase 6: Tool Layer | 4 | ToolRegistry, ToolExecutor integration with Phase 5 InsureMateAgent | **PASS** |
| [`test_phase7_api.py`](file:///d:/InsureMate/tests/test_phase7_api.py) | Phase 7: REST API | 6 | FastAPI endpoints (`/api/claims`, `/api/tools`, `/api/claims/upload`, etc.) | **PASS** |
| [`test_phase7_database.py`](file:///d:/InsureMate/tests/test_phase7_database.py) | Phase 7: Database Memory | 7 | SQLite schema, cascade deletion, state snapshots, tool execution audit | **PASS** |
| [`test_phase7_frontend_integration.py`](file:///d:/InsureMate/tests/test_phase7_frontend_integration.py) | Phase 7: Frontend | 4 | Static file serving, HTML5 structure, glassmorphic CSS tokens | **PASS** |
| [`test_phase7_integration.py`](file:///d:/InsureMate/tests/test_phase7_integration.py) | Phase 7: Agent Service | 3 | Full AgentService lifecycle bridging UI, Database, and Agent | **PASS** |
| [`test_dynamic_agent.py`](file:///d:/InsureMate/tests/test_dynamic_agent.py) | Phase 5/6: Dynamic Reasoning | 12 | Plan updates, hypothesis tracking, state adaptation, fallback modes | **PASS** |
| [`test_extraction_tool.py`](file:///d:/InsureMate/tests/test_extraction_tool.py) | Phase 1/6: Tool Adapter | 7 | DocumentExtractionTool schema, execution, error envelopes | **PASS** |
| [`test_master_fixes.py`](file:///d:/InsureMate/tests/test_master_fixes.py) | Master Verification | 3 | Concurrency locks, native OCR (`winocr`), real PDF document execution | **PASS** |
| [`test_missing_document_tool.py`](file:///d:/InsureMate/tests/test_missing_document_tool.py) | Phase 4/6: Tool Adapter | 3 | MissingDocumentTool execution envelope and dynamic schema compliance | **PASS** |
| [`test_readiness_distinction.py`](file:///d:/InsureMate/tests/test_readiness_distinction.py) | Final Decision Engine | 5 | Accurate distinction between Ready, Missing Evidence, and Invalid Dates | **PASS** |
| [`test_tool_executor.py`](file:///d:/InsureMate/tests/test_tool_executor.py) | Phase 6: Tool Executor | 5 | Safe invocation, timing measurement, error envelopes, bounded retries | **PASS** |
| [`test_tool_registry.py`](file:///d:/InsureMate/tests/test_tool_registry.py) | Phase 6: Tool Registry | 4 | Tool catalog discovery, duplicate prevention, JSON schema export | **PASS** |
| [`test_validation_tool.py`](file:///d:/InsureMate/tests/test_validation_tool.py) | Phase 2/6: Tool Adapter | 2 | DocumentValidationTool adapter execution and result mapping | **PASS** |
| [`test_validity_tool.py`](file:///d:/InsureMate/tests/test_validity_tool.py) | Phase 3/6: Tool Adapter | 3 | ValidityCheckerTool adapter execution and date validity mapping | **PASS** |
| [`test_end_to_end.py`](file:///d:/InsureMate/tests/test_end_to_end.py) | End-to-End Pipeline | 1 | Complete multi-phase pipeline execution on real PDF files | **PASS** |
| **Total** | **Full System** | **102** | **Complete coverage across all 7 development phases** | **100% PASS** |

---

## 11. Troubleshooting & Quick Fixes

### 1. `ModuleNotFoundError: No module named 'reportlab'`
- **Reason:** The PDF generation scripts in `scripts/` require `reportlab`.
- **Fix:** Install all updated dependencies:
  ```bash
  python -m pip install -r requirements.txt
  ```

### 2. `ModuleNotFoundError: No module named 'httpx'`
- **Reason:** FastAPI's `TestClient` (used in API and integration tests) requires `httpx`.
- **Fix:** Run:
  ```bash
  python -m pip install httpx>=0.24.0
  ```

### 3. `ImportError: cannot import name 'field_validator' from 'pydantic'`
- **Reason:** An older version of Pydantic (v1) was installed in your Python environment. InsureMate requires Pydantic v2.
- **Fix:** Update Pydantic:
  ```bash
  python -m pip install "pydantic>=2.6.0"
  ```

### 4. `pytest : The term 'pytest' is not recognized as the name of a cmdlet...` (Windows)
- **Reason:** The virtual environment's `Scripts/` directory is not in your Windows system PATH in PowerShell.
- **Fix:** Always invoke pytest through python module syntax:
  ```bash
  python -m pytest
  ```
  Or use the unified CLI runner:
  ```bash
  python main.py --test-all
  ```

### 5. `File ...\Activate.ps1 cannot be loaded because running scripts is disabled on this system` (PowerShell)
- **Reason:** Windows PowerShell disables running unsigned script files by default.
- **Fix:** Allow script execution for the current PowerShell terminal session:
  ```powershell
  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
  .\.venv\Scripts\Activate.ps1
  ```

### 6. Scanned PDF Native OCR (Windows)
- **Reason:** Scanned PDFs lacking digital text fall back to Windows native Media OCR via `winocr`.
- **Fix:** `winocr>=0.0.14` is included in `requirements.txt` with the Windows environment marker `sys_platform == "win32"`. It installs automatically on Windows and is safely skipped on macOS/Linux.

### 7. Port 8000 Already in Use
- **Reason:** Another web service or previous server process is listening on port 8000.
- **Fix:** Launch InsureMate on a different port:
  ```bash
  python main.py --serve --port 8080
  ```

### 8. Ollama or Qwen-VL API Key Not Configured
- **Reason:** You don't have paid API keys or a local Ollama daemon running.
- **Fix:** **Zero setup needed!** InsureMate automatically falls back to **Deterministic Grounded Mode**. All tests, demos, and claim preparation features function smoothly out-of-the-box without network connectivity or external LLM dependencies.

---

## 12. Authors & Academic Context

- **Project**: InsureMate — Insurance Claim Preparation Agent
- **Track**: Track B — Agentic AI Application (Semester Project)
- **Repository**: [GandhiSmit06/InsureMate](https://github.com/GandhiSmit06/InsureMate)
- **License**: MIT

<br />

<p align="center">
  <img src="frontend/assets/animated-footer.svg" alt="InsureMate Animated Footer" width="800" style="max-width: 100%; height: auto;" />
</p>
