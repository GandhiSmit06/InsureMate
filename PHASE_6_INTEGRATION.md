# InsureMate Phase 6: Agent Tool Layer & Integration Guide

> **Developer Handoff Specification for Phase 5 (Agent Orchestrator / Planner)**

---

## 1. Overview & Architecture

Phase 6 provides the **modular Tool Layer, Tool Registry, and Tool Executor** for InsureMate.
It wraps the core insurance-claim processing engines (Phases 1–4) as deterministic, agent-callable tools with standardized schemas, safe execution, structured error handling, controlled retries, operational history, and shared claim state compatibility.

### Architectural Separation

```
          ┌────────────────────────────────────────┐
          │             PHASE 5 AGENT              │
          │               (The Brain)              │
          │  - Planning & Task Decomposition       │
          │  - Dynamic Tool Selection              │
          │  - Intermediate Observation & Decision │
          │  - Final Claim Readiness Verdict       │
          └───────────────────┬────────────────────┘
                              │
                              ▼
          ┌────────────────────────────────────────┐
          │             PHASE 6 LAYER              │
          │             (The Toolbox)              │
          │  - Tool Registry (Discovery/Lookup)    │
          │  - Tool Executor (Safe Invocation)     │
          │  - Standardized Result & Error Envelope│
          │  - Controlled Retries & Execution Log  │
          │  - Shared ClaimState Container         │
          └───────────────────┬────────────────────┘
                              │
      ┌───────────────────────┼───────────────────────┐
      ▼                       ▼                       ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────────┐
│  Extraction   │     │  Validation   │     │  Validity Check   │
│     Tool      │     │     Tool      │     │       Tool        │
│   (Qwen-VL)   │     │(Deterministic)│     │  (Policy Dates)   │
└───────┬───────┘     └───────┬───────┘     └─────────┬─────────┘
        │                     │                       │
        └─────────────────────┼───────────────────────┘
                              ▼
                    ┌───────────────────┐
                    │ Missing Document  │
                    │       Tool        │
                    │   (Gemma 3 LLM)   │
                    └───────────────────┘
```

**Key Principle**: Phase 6 **never hardcodes any workflow or tool sequence**. Phase 5 has complete autonomy to inspect available tools, decide which tool to call based on the claim state, and make subsequent decisions.

---

## 2. Available Tools Catalog

| Tool Name | Class | Canonical Description |
| :--- | :--- | :--- |
| `document_extraction_tool` | `DocumentExtractionTool` | Extracts structured insurance claim entities, policy clauses, and classifications from uploaded PDF documents page-by-page using Qwen-VL vision understanding, preserving 1-indexed page numbers. |
| `document_validation_tool` | `DocumentValidationTool` | Deterministically validates extracted documents against required claim fields by type (policy, medical bill, hospital record, report) and returns pass/fail with missing fields. |
| `validity_checker_tool` | `ValidityCheckerTool` | Deterministically verifies whether medical bills and claim documents fall within policy coverage dates, checks date formatting, and cross-references patient identity. |
| `missing_document_tool` | `MissingDocumentTool` | Dynamically determines required documents for an insurance claim based on policy terms, semantically compares against submitted claim documents, and identifies missing documents with exact 1-indexed page numbers. |

*(Legacy Alias: `qwen_vl_extraction_tool` maps directly to `document_extraction_tool`.)*

---

## 3. Tool Specifications: Inputs & Outputs

### 3.1 `document_extraction_tool`
Wraps the Qwen-VL multimodal extraction engine.

#### Expected Input
```python
{
    "claim_id": "CLM-2026-001",           # (Optional) Claim ID
    "documents": ["path/to/doc1.pdf"],     # List of file paths OR
    "pdf_path": "path/to/doc.pdf",         # Single file path
    "max_pages": 3                         # (Optional) Upper limit on pages to process
}
```

#### Expected Output (`result`)
```json
{
  "success": true,
  "claim_id": "CLM-2026-001",
  "extracted_data": {
    "total_pages": 2,
    "extracted_documents": [
      {
        "page_number": 1,
        "document_type": "insurance_policy",
        "document_title": "ICICI Lombard Policy Certificate",
        "policy_number": "4225i/ELVT/384538792/00/000",
        "policy_holder_name": "Maulikkumar Pathak",
        "policy_start_date": "12/03/2025",
        "policy_end_date": "11/03/2028",
        "policy_clauses": ["Discharge summary required", "Hospital bill required"]
      },
      {
        "page_number": 2,
        "document_type": "medical_bill",
        "document_title": "Final Inpatient Bill",
        "bill_number": "BILL-2024-95151",
        "patient_name": "Parth M. Pathak",
        "document_date": "25/10/2026",
        "bill_amount": "48500.00"
      }
    ]
  },
  "documents_processed": ["path/to/doc1.pdf"],
  "errors": []
}
```

---

### 3.2 `document_validation_tool`
Deterministically evaluates field completeness per document type.

#### Expected Input
```python
{
    "claim_id": "CLM-2026-001",           # (Optional) Claim ID
    "extracted_data": {...},               # Extraction payload (from Tool 1) OR
    "extracted_documents": [...],          # List of page dictionaries OR
    "requirements": {...}                  # (Optional) Custom requirements override
}
```

#### Expected Output (`result`)
```json
{
  "success": true,
  "claim_id": "CLM-2026-001",
  "validation_results": {
    "valid": true,
    "total_documents": 2,
    "valid_documents": 2,
    "invalid_documents": 0,
    "document_results": [
      {
        "document_type": "insurance_policy",
        "page_number": 1,
        "valid": true,
        "missing_fields": [],
        "reasons": []
      },
      {
        "document_type": "medical_bill",
        "page_number": 2,
        "valid": true,
        "missing_fields": [],
        "reasons": []
      }
    ],
    "reasons": []
  },
  "errors": []
}
```

---

### 3.3 `validity_checker_tool`
Evaluates date windows, date formats, and policy coverage.

#### Expected Input
```python
{
    "claim_id": "CLM-2026-001",           # (Optional) Claim ID
    "policy_data": {...},                  # Policy dict with start/end dates OR
    "document_data": [...],                # Bills/reports with document_date OR
    "extracted_data": {...}                # (Convenience) Complete extraction payload: auto-splits policy and claim docs!
}
```

#### Expected Output (`result`)
```json
{
  "success": true,
  "claim_id": "CLM-2026-001",
  "validity_results": {
    "valid": true,
    "policy_period": {
      "start_date": "12/03/2025",
      "end_date": "11/03/2028"
    },
    "reasons": [
      "Policy dates are available and valid (12/03/2025 to 11/03/2028).",
      "Document date (25/10/2026) falls within the policy validity period on page 2."
    ],
    "checks": [
      {
        "document_type": "medical_bill",
        "page_number": 2,
        "raw_date": "25/10/2026",
        "normalized_date": "2026-10-25",
        "valid": true,
        "reason": "Falls within policy validity period"
      }
    ],
    "identity_match": {
      "matched": true,
      "policy_holder": "Maulikkumar Pathak",
      "patient_name": "Parth M. Pathak"
    }
  },
  "errors": []
}
```

---

### 3.4 `missing_document_tool`
Dynamically discovers required evidence from policy terms and identifies missing documents.

#### Expected Input
```python
{
    "claim_id": "CLM-2026-001",           # (Optional) Claim ID
    "extracted_data": {...},               # Extraction payload (from Tool 1)
    "validation_results": {...},           # (Optional) Output from Tool 2
    "validity_results": {...}              # (Optional) Output from Tool 3
}
```

#### Expected Output (`result`)
```json
{
  "success": true,
  "claim_id": "CLM-2026-001",
  "missing_documents": [
    {
      "sr_no": 1,
      "document_title": "Discharge Summary",
      "missing": false,
      "page_no": 2
    },
    {
      "sr_no": 2,
      "document_title": "Final Hospital Bill",
      "missing": true,
      "page_no": null
    }
  ],
  "summary": {
    "total_required": 2,
    "total_submitted": 1,
    "total_missing": 1
  },
  "errors": []
}
```

---

## 4. How Phase 5 Integrates with Phase 6

### 4.1 Initializing Registry & Executor

```python
from tools import create_tool_registry, ToolExecutor, ClaimState

# 1. Initialize registry with all InsureMate tools
registry = create_tool_registry()

# 2. Initialize executor
executor = ToolExecutor(registry=registry)

# 3. Discover available tools (pass to your LLM system prompt / tool definitions)
available_tools = registry.list_tools()
# Returns:
# [
#   {"name": "document_extraction_tool", "description": "..."},
#   {"name": "document_validation_tool", "description": "..."},
#   {"name": "validity_checker_tool", "description": "..."},
#   {"name": "missing_document_tool", "description": "..."}
# ]

# If using LLM function calling (OpenAI / Ollama / LangChain):
tool_schemas = registry.get_schemas()
```

---

### 4.2 Standard Execution Envelope

Every tool call returns a uniform response structure:

#### Success Response
```python
response = executor.execute(
    tool_name="document_validation_tool",
    input_data={"extracted_data": {...}},
    retry_count=1,          # Optional: retries upon transient failure
    state=claim_state       # Optional: automatically updates ClaimState
)

# Standard Envelope:
{
    "success": True,
    "tool_name": "document_validation_tool",
    "result": { ... },      # Tool-specific payload (see Section 3)
    "error": None
}
```

#### Failure Response
The executor **never crashes the workflow**. If an error occurs, it returns:
```python
{
    "success": False,
    "tool_name": "document_validation_tool",
    "result": None,
    "error": {
        "type": "ToolValidationError",          # or "ToolNotFoundError", "ToolExecutionError"
        "message": "Human-readable explanation of the issue"
    }
}
```

---

### 4.3 Shared `ClaimState`

Phase 6 includes a lightweight `ClaimState` container designed to carry context across multiple agent decisions:

```python
from tools import ClaimState

state = ClaimState(claim_id="CLAIM-1002")

# Pass state directly into executor.execute
executor.execute("document_extraction_tool", {"documents": ["claim.pdf"]}, state=state)

# State automatically updates:
# - state.extracted_data
# - state.documents
# - state.tool_history
# - state.current_step

# Access like an object or a dictionary:
print(state.current_step)           # "document_extraction_completed"
print(state["extracted_data"])      # {...}
```

---

## 5. End-to-End Phase 5 → Phase 6 Interaction Example

Here is a minimal pattern demonstrating how the Phase 5 Agent coordinates tools:

```python
from tools import create_tool_registry, ToolExecutor, ClaimState

def run_agentic_claim_process(policy_file: str, claim_file: str):
    # Setup Phase 6
    registry = create_tool_registry()
    executor = ToolExecutor(registry=registry)
    state = ClaimState(claim_id="CLM-LIVE-901")

    # Step 1: Agent decides to extract documents
    step1 = executor.execute(
        "document_extraction_tool",
        {"claim_id": state.claim_id, "documents": [policy_file, claim_file]},
        state=state
    )
    if not step1["success"]:
        return {"status": "FAILED", "reason": step1["error"]["message"]}

    # Step 2: Agent observes extraction, decides to validate
    step2 = executor.execute(
        "document_validation_tool",
        {"claim_id": state.claim_id, "extracted_data": state.extracted_data},
        state=state
    )

    # Step 3: Agent checks validity dates
    step3 = executor.execute(
        "validity_checker_tool",
        {"claim_id": state.claim_id, "extracted_data": state.extracted_data},
        state=state
    )

    # Step 4: Agent checks missing evidence
    step4 = executor.execute(
        "missing_document_tool",
        {
            "claim_id": state.claim_id,
            "extracted_data": state.extracted_data,
            "validation_results": state.validation_results,
            "validity_results": state.validity_results,
        },
        state=state
    )

    # Agent inspects history & synthesizes final decision
    history = executor.get_history()
    print(f"Executed {len(history)} tools successfully.")
    
    return {
        "claim_id": state.claim_id,
        "is_valid": state.validity_results.get("valid", False),
        "missing_documents": state.missing_documents,
        "history": history
    }
```

---

## 6. What Phase 5 Must NOT Depend On

1. **Do NOT import low-level engines directly**:
   - Avoid importing `services.qwen_vl.extractor`
   - Avoid importing `services.document_validation.validator`
   - Avoid importing `services.validity_checker.checker`
   - Avoid importing `services.missing_document.detector`
   - **Always invoke tools via `ToolExecutor` and `ToolRegistry`**.

2. **Do NOT assume a fixed execution order**:
   - Phase 6 allows calling tools in any sequence.
   - Tools can be called conditionally, repeatedly, or skipped based on agent logic.

3. **Do NOT manage model initializations or internal paths**:
   - Tool initialization is handled automatically by `create_tool_registry()`.

4. **Do NOT invent custom error parsing**:
   - Rely on `response["success"]` and `response["error"]`.
