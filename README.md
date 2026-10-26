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

# InsureMate

InsureMate is an AI-assisted insurance claim preparation platform that turns policy and claim documents into a structured, reviewable readiness package. It combines multimodal document extraction, deterministic validation, policy-aware evidence discovery, cross-document checks, and an autonomous orchestration layer in one application.

The platform is designed for policyholders, claims teams, brokers, and developers building document-heavy insurance workflows. It helps users understand whether a claim is ready to submit, which evidence is missing, and what inconsistencies need attention before human review or insurer submission.

## What InsureMate does

- Accepts policy PDFs and supporting claim documents, including scanned documents and common image formats.
- Extracts visible fields, dates, identities, amounts, document types, and page-level provenance.
- Validates required fields and document structure with deterministic Python rules.
- Checks policy coverage dates and claimant identity across related documents.
- Reads policy language to identify evidence requirements instead of relying only on a fixed checklist.
- Detects missing documents and cross-document discrepancies such as name, date, and amount mismatches.
- Uses an agent orchestrator to select tools, preserve claim state, recover from tool failures, and produce a final readiness result.
- Stores sessions, execution activity, state snapshots, and reports in SQLite for traceability.
- Provides a browser dashboard and REST API for uploads, execution, progress, results, assistant questions, and report downloads.
- Supports a grounded offline mode for local development, demonstrations, and automated tests without an external language-model service.

## Core workflow

```text
Policy and claim documents
            |
            v
Document ingestion and page-aware extraction
            |
            v
Completeness, identity, date, and policy checks
            |
            v
Policy-aware evidence and discrepancy analysis
            |
            v
Agent orchestration with traceable claim state
            |
            v
Readiness verdict, missing evidence, findings, and report
```

Every result is intended to be explainable: extracted values retain their source page where available, validation findings include a reason, and agent activity is recorded as structured events rather than opaque output.

## Product capabilities

### Document intelligence

InsureMate processes digital and scanned documents through a layered extraction strategy. PDF pages can be rendered in memory, embedded text can be read directly, and OCR or vision-based extraction can be used when the source is image-based. The system avoids inventing values that are not visible and represents unavailable fields as unknown.

### Claim and policy analysis

The analysis layer normalizes common date formats, verifies that incident and service dates fall within the policy period, compares claimant identities, validates document-specific fields, and evaluates policy clauses relevant to the claim. It can identify requirements such as bills, discharge summaries, reports, incident records, or travel evidence from the supplied policy context.

### Autonomous orchestration

`InsureMateAgent` coordinates the analysis using a registered tool catalog and a shared `ClaimState`. The agent can plan work from a natural-language goal, invoke the appropriate tools, adapt when evidence is incomplete, and produce a bounded execution trace. Guardrails include iteration limits, structured errors, retry handling, and safe tool execution.

### Review-ready outputs

The final claim package can include:

- Overall readiness status and actionable explanation.
- Extracted document metadata and page references.
- Field-level validation results.
- Coverage-period and identity findings.
- Missing or recommended evidence.
- Cross-document consistency findings.
- Tool execution activity and timing.
- A downloadable PDF report.

## Architecture

```text
                        +----------------------+
                        |  Browser dashboard   |
                        |  HTML / CSS / JS     |
                        +----------+-----------+
                                   |
                                   v
                        +----------------------+
                        | FastAPI REST server  |
                        | Uploads and sessions |
                        +----------+-----------+
                                   |
             +---------------------+---------------------+
             |                     |                     |
             v                     v                     v
      Agent orchestration    Document tools        Assistant service
      planning and state     extraction, rules,    claim questions
                             evidence, consistency
             |                     |
             +---------------------+
                                   v
                        +----------------------+
                        | SQLite claim memory  |
                        | traces and reports   |
                        +----------------------+
```

### Repository layout

```text
InsureMate/
├── agent/                 Agent planning, decisions, state, and adapters
├── app/                   FastAPI application and HTTP endpoints
├── frontend/              Browser dashboard and static assets
├── services/              Application services, persistence, reports, and AI adapters
├── tools/                 Extraction, validation, evidence, registry, and executor tools
├── tests/                 Unit, integration, API, and end-to-end tests
├── main.py                Unified command-line entry point
├── requirements.txt       Python dependencies
└── .env.example           Optional local model configuration
```

## Getting started

### Requirements

- Python 3.10 or newer
- pip and a virtual-environment tool
- Optional: Ollama for local model-assisted reasoning
- Optional: a configured vision-model provider for remote extraction

### Installation

```bash
git clone https://github.com/GandhiSmit06/InsureMate.git
cd InsureMate

python -m venv .venv
source .venv/bin/activate              # macOS/Linux
# .venv\Scripts\activate               # Windows

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` when local model configuration is needed:

```bash
cp .env.example .env
```

InsureMate can run in deterministic grounded mode when optional model credentials or Ollama are unavailable. This mode is suitable for the standard local workflow and test suite.

## Running the application

Start the web application:

```bash
python main.py --serve
```

Open [http://localhost:8000](http://localhost:8000) in a browser. Use `--host` and `--port` to expose a different interface or port:

```bash
python main.py --serve --host 127.0.0.1 --port 8080
```

Run the agent directly against supplied documents:

```bash
python main.py --agent \
  --policy path/to/policy.pdf \
  --claim path/to/claim.pdf \
  --goal "Determine claim readiness and identify missing evidence" \
  --offline
```

The command-line interface also supports document extraction, validation, validity checks, missing-evidence analysis, end-to-end execution, and the complete test suite. Run `python main.py --help` for the current options.

## REST API

The FastAPI service exposes the following groups of endpoints:

| Area | Representative endpoints | Purpose |
| --- | --- | --- |
| Health and tools | `GET /api/health`, `GET /api/tools` | Inspect service health and registered tool schemas |
| Upload and validation | `POST /api/documents/validate-slot`, `POST /api/claims/upload` | Validate files and create claim sessions |
| Execution | `POST /api/claims/{id}/run`, `POST /api/claims/{id}/agent/start` | Start claim analysis |
| Progress | `GET /api/claims/{id}/agent/status`, `GET /api/claims/{id}/agent/activity` | Monitor execution |
| Results | `GET /api/claims/{id}/result`, `/validity`, `/validation` | Retrieve analysis findings |
| Evidence and documents | `GET /api/claims/{id}/missing-documents`, `/documents` | Review supplied and missing evidence |
| Reports and assistance | `GET /api/claims/{id}/report`, `POST /api/claims/{id}/assistant` | Download a report or ask a claim question |
| History | `GET /api/claims`, `GET /api/claims/{id}`, `DELETE /api/claims/{id}` | Manage persisted claim sessions |

Interactive API documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs) while the server is running.

## Configuration

The optional `.env` file supports local model settings:

```dotenv
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma3:latest
OLLAMA_TIMEOUT=120
```

Provider-specific credentials are read by the corresponding extraction and reasoning services when configured. Keep secrets in local environment files and never commit them to the repository.

## Testing

Run the full suite:

```bash
python -m pytest
```

Run a focused test module:

```bash
python -m pytest tests/test_phase7_api.py
```

The tests cover extraction, validation, policy and claim analysis, missing evidence, tool registration and execution, persistence, API behavior, frontend integration, and end-to-end workflows.

## Design principles

- **Evidence first:** findings are grounded in supplied documents and retain provenance where possible.
- **Deterministic by default:** rule-based checks remain usable without network services.
- **Policy aware:** evidence requirements are derived from the policy context rather than assumed universally.
- **Human reviewable:** the system prepares and explains a claim; it does not make an irreversible insurer decision.
- **Traceable execution:** tool calls, state transitions, errors, and final outputs are structured for inspection.
- **Safe extensibility:** new capabilities can be registered through the shared tool registry and executor.

## Security and operational notes

InsureMate is a development and claim-preparation application. Protect uploaded documents and the SQLite database as sensitive data, restrict the API before deploying outside a trusted local network, and configure authentication, authorization, HTTPS, storage controls, and retention policies for production use.

## License

InsureMate is distributed under the MIT License. See [LICENSE](LICENSE) for details.

<br />

<p align="center">
  <img src="frontend/assets/animated-footer.svg" alt="InsureMate Animated Footer" width="800" style="max-width: 100%; height: auto;" />
</p>
