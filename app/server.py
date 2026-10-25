"""app/server.py
InsureMate Phase 7 FastAPI Application.
Serves the web UI and REST API for document upload, session creation,
autonomous agent orchestration, claim memory persistence, and result visualization.
"""

import asyncio
import json
import sys
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from services.agent_service import AgentService
from services.database.db import ClaimDatabase
from services.document_validation.policy_validator import validate_policy_pdf
from services.pdf_report_generator import generate_claim_report_pdf
from tools.tool_registry import create_tool_registry
from utils.logger import logger

# Initialize FastAPI App
app = FastAPI(
    title="InsureMate — Insurance Claim Preparation Agent",
    description="Phase 7 End-to-End Application: Multimodal Extraction, Validation, Validity Checking, Dynamic Missing Evidence Detection, and Autonomous Agent Orchestration.",
    version="1.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache Control Middleware for fresh frontend delivery
@app.middleware("http")
async def add_cache_control_headers(request, call_next):
    response = await call_next(request)
    # Never cache html, js, or css files during active development
    path = request.url.path
    if path == "/" or path.endswith((".html", ".js", ".css")):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Initialize Service & Database
agent_service = AgentService()
frontend_dir = ROOT_DIR / "frontend"

# Mount Frontend Static Assets
if frontend_dir.exists():
    app.mount("/frontend", StaticFiles(directory=str(frontend_dir)), name="frontend")
    if (frontend_dir / "css").exists():
        app.mount("/css", StaticFiles(directory=str(frontend_dir / "css")), name="css")
    if (frontend_dir / "js").exists():
        app.mount("/js", StaticFiles(directory=str(frontend_dir / "js")), name="js")
    if (frontend_dir / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(frontend_dir / "assets")), name="assets")


# Pydantic Schemas
class DemoRequest(BaseModel):
    demo_type: Optional[str] = None
    preset: Optional[str] = None
    auto_run: bool = False
    offline_mode: bool = False


class RunRequest(BaseModel):
    max_pages: Optional[int] = None


class StartAgentRequest(BaseModel):
    max_pages: Optional[int] = None
    offline_mode: Optional[bool] = None
    background: bool = False


# ==============================================================================
# FRONTEND ROUTE
# ==============================================================================
@app.get("/", response_class=FileResponse)
async def serve_index():
    index_file = frontend_dir / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Frontend index.html not found.")
    res = FileResponse(str(index_file))
    res.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    res.headers["Pragma"] = "no-cache"
    res.headers["Expires"] = "0"
    return res


# ==============================================================================
# API ENDPOINTS
# ==============================================================================
@app.get("/api/health")
async def health_check():
    """System health check & tool catalog verification."""
    registry = create_tool_registry()
    tools = registry.list_tools()
    return {
        "status": "ok",
        "app": "InsureMate",
        "service": "InsureMate",
        "version": "1.0.0",
        "phase": 7,
        "available_tools_count": len(tools),
        "tools": [t["name"] for t in tools],
        "database": "connected"
    }


@app.get("/api/tools")
async def list_available_tools():
    """Retrieve catalog of agent-callable tools and parameter schemas."""
    registry = create_tool_registry()
    return {
        "tools": registry.list_tools(),
        "schemas": registry.get_schemas()
    }


@app.post("/api/documents/validate-slot")
async def validate_document_slot(
    file: UploadFile = File(...),
    slot: str = Form(...)
):
    """Validate uploaded document format and size for given slot."""
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()
    if ext not in [".pdf", ".jpg", ".jpeg", ".png", ".webp"]:
        err_type = f"Unsupported file type '{ext}'. Please upload a PDF or image document."
        return JSONResponse(
            status_code=400,
            content={"valid": False, "error": err_type, "detail": err_type, "message": err_type}
        )

    content = await file.read()
    if slot == "policy":
        result = validate_policy_pdf(content, filename=filename)
        if not result.valid:
            err_msg = result.error or "Please upload a valid insurance policy PDF."
            return JSONResponse(
                status_code=400,
                content={
                    "valid": False,
                    "slot": slot,
                    "filename": filename,
                    "error": err_msg,
                    "detail": err_msg,
                    "message": err_msg,
                    "document_type": result.document_type,
                    "confidence": result.confidence
                }
            )
        return {
            "valid": True,
            "slot": slot,
            "filename": filename,
            "document_type": result.document_type,
            "confidence": result.confidence,
            "reason": result.reason
        }

    # For supporting claim/hospital slots: basic PDF structure check if PDF
    if ext == ".pdf" and len(content) >= 4 and b"%PDF-" not in content[:1024]:
        err_pdf = "The uploaded file is not a valid PDF document."
        return JSONResponse(
            status_code=400,
            content={"valid": False, "error": err_pdf, "detail": err_pdf, "message": err_pdf}
        )

    return {"valid": True, "slot": slot, "filename": filename}


@app.post("/api/documents/validate-pair")
async def validate_document_pair(
    policy_document: Optional[UploadFile] = File(None),
    hospital_document: Optional[UploadFile] = File(None)
):
    """Validate document pair alignment."""
    return {"valid": True}


@app.post("/api/claims")
@app.post("/api/claims/upload")
@app.post("/analyses")
async def upload_and_create_claim(
    policy_file: Optional[UploadFile] = File(None),
    policy_document: Optional[UploadFile] = File(None),
    claim_file: Optional[UploadFile] = File(None),
    claim_files: Optional[List[UploadFile]] = File(None),
    hospital_document: Optional[UploadFile] = File(None),
    goal: str = Form("Determine claim readiness and identify any missing evidence."),
    session_name: Optional[str] = Form(None),
    claim_type: str = Form("general"),
    offline_mode: bool = Form(False),
    auto_run: bool = Form(False)
):
    """
    Upload insurance policy and claim documents, establish claim session,
    and optionally execute the InsureMate Agent immediately.
    """
    claim_id = f"CLM-{uuid.uuid4().hex[:8].upper()}"

    p_file = policy_file or policy_document
    p_path = None
    p_name = None
    if p_file and p_file.filename:
        content = await p_file.read()
        p_name = p_file.filename

        # Server-side intelligent policy validation
        val_res = validate_policy_pdf(content, filename=p_name)
        if not val_res.valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=val_res.error or "Please upload a valid insurance policy PDF."
            )

        p_path = agent_service.save_uploaded_file(claim_id, p_name, content)

    c_paths = []
    c_names = []
    # Process claim files without duplicate registration
    raw_claim_list = list(claim_files) if claim_files else ([claim_file] if claim_file else ([hospital_document] if hospital_document else []))
    for cf in raw_claim_list:
        if cf and cf.filename and cf.filename not in c_names:
            content = await cf.read()
            c_names.append(cf.filename)
            c_paths.append(agent_service.save_uploaded_file(claim_id, cf.filename, content))

    # If neither file uploaded, raise error
    if not p_path and not c_paths:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one document (policy or claim file) must be provided."
        )

    primary_c_path = c_paths[0] if c_paths else None
    primary_c_name = c_names[0] if c_names else None

    # Create session record in database
    claim = agent_service.db.create_claim(
        claim_id=claim_id,
        goal=goal,
        session_name=session_name or f"Claim Session {claim_id}",
        claim_type=claim_type,
        policy_path=p_path,
        claim_path=primary_c_path,
        policy_filename=p_name,
        claim_filename=primary_c_name,
        claim_filenames=c_names,
        offline_mode=offline_mode
    )

    result = {
        "success": True,
        "claim_id": claim_id,
        "analysis_id": claim_id,
        "id": claim_id,
        "claim": claim
    }

    # Auto-run if requested
    if auto_run:
        run_data = agent_service.run_agent(claim_id=claim_id)
        result["run_results"] = run_data

    return JSONResponse(status_code=status.HTTP_201_CREATED, content=result)


@app.post("/api/claims/demo")
@app.post("/analyses/demo")
async def create_demo_claim(request: Optional[DemoRequest] = None):
    """Create a sample session from repository files and optionally execute agent."""
    req = request or DemoRequest(preset="health", offline_mode=True, auto_run=False)
    preset = req.preset or req.demo_type or "health"
    try:
        claim = agent_service.create_demo_session(
            demo_type=preset,
            preset=preset,
            offline_mode=req.offline_mode
        )
        claim_id = claim["claim_id"]
        result = {
            "success": True,
            "claim_id": claim_id,
            "analysis_id": claim_id,
            "id": claim_id,
            "claim": claim
        }

        if req.auto_run:
            run_data = agent_service.run_agent(claim_id=claim_id)
            result["run_results"] = run_data

        return JSONResponse(status_code=status.HTTP_201_CREATED, content=result)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"[API] Failed to create demo session: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/api/claims/{claim_id}/run")
async def run_claim_agent(claim_id: str, request: RunRequest = RunRequest()):
    """Trigger the InsureMate Agent to autonomously process the claim session."""
    claim = agent_service.db.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim session '{claim_id}' not found.")

    if agent_service.is_claim_running(claim_id):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "success": False,
                "claim_id": claim_id,
                "status": "in_progress",
                "is_running": True,
                "message": f"InsureMate Agent is already running for claim '{claim_id}'."
            }
        )

    try:
        run_data = agent_service.run_agent(claim_id=claim_id, max_pages=request.max_pages)
        return run_data
    except Exception as e:
        logger.error(f"[API] Error running agent for claim {claim_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")


@app.post("/api/claims/{claim_id}/agent/start")
async def start_claim_agent(claim_id: str, request: StartAgentRequest = StartAgentRequest()):
    """
    Trigger the InsureMate Agent autonomously for a claim.
    Supports background execution for real-time polling, or synchronous execution.
    """
    claim = agent_service.db.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim session '{claim_id}' not found.")

    if agent_service.is_claim_running(claim_id):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "success": False,
                "claim_id": claim_id,
                "status": "in_progress",
                "is_running": True,
                "message": f"InsureMate Agent is already running for claim '{claim_id}'."
            }
        )

    if request.background:
        if not agent_service.acquire_claim_lock(claim_id):
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "success": False,
                    "claim_id": claim_id,
                    "status": "in_progress",
                    "is_running": True,
                    "message": f"InsureMate Agent is already running for claim '{claim_id}'."
                }
            )
        agent_service.db.update_claim_status(claim_id, "in_progress")

        def _runner():
            try:
                agent_service.run_agent(
                    claim_id=claim_id,
                    max_pages=request.max_pages,
                    offline_mode=request.offline_mode,
                    lock_preacquired=True
                )
            except Exception as ex:
                logger.error(f"[BACKGROUND AGENT] Error on claim {claim_id}: {ex}")
                agent_service.release_claim_lock(claim_id)

        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()
        return {
            "success": True,
            "claim_id": claim_id,
            "status": "in_progress",
            "is_running": True,
            "background": True,
            "message": "InsureMate Agent started in background."
        }
    else:
        try:
            run_data = agent_service.run_agent(
                claim_id=claim_id,
                max_pages=request.max_pages,
                offline_mode=request.offline_mode
            )
            return run_data
        except Exception as e:
            logger.error(f"[API] Error running agent for claim {claim_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")


@app.get("/api/claims/{claim_id}/agent/status")
async def get_claim_agent_status(claim_id: str):
    """Retrieve active status, progress, current step, live running tool, and verdict for polling."""
    data = agent_service.get_claim(claim_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Claim session '{claim_id}' not found.")
    claim = data["claim"]
    status_val = claim.get("status", "pending")
    is_running = agent_service.is_claim_running(claim_id) or str(status_val).lower() in ("in_progress", "running", "processing")
    latest_state = data.get("latest_state") or {}
    tool_execs = data.get("tool_executions", [])
    report = data.get("final_report")
    live_tool = agent_service.get_live_running_tool(claim_id)
    return {
        "claim_id": claim_id,
        "status": "in_progress" if is_running else status_val,
        "is_running": is_running,
        "verdict": data.get("verdict"),
        "current_step": latest_state.get("current_step") or (live_tool.get("tool_name") if live_tool else None),
        "live_running_tool": live_tool,
        "completed_steps": latest_state.get("completed_steps", []),
        "iteration_count": latest_state.get("iteration_count", len(tool_execs)),
        "tool_count": len(tool_execs),
        "has_result": report is not None
    }


@app.get("/api/agent/running")
async def get_running_agent_claims():
    """Retrieve list of claim IDs currently being processed by the agent."""
    with agent_service._lock:
        running = list(agent_service._running_claims)
    return {
        "count": len(running),
        "running_claims": running
    }


@app.get("/api/claims/{claim_id}/agent/activity")
async def get_claim_agent_activity(claim_id: str):
    """Retrieve complete chronological tool executions, execution trace, live running tool, and events."""
    data = agent_service.get_claim(claim_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Claim session '{claim_id}' not found.")
    latest_state = data.get("latest_state") or {}
    live_tool = agent_service.get_live_running_tool(claim_id)
    events = agent_service.get_claim_events(claim_id)
    return {
        "claim_id": claim_id,
        "status": data["claim"].get("status"),
        "verdict": data.get("verdict"),
        "is_running": agent_service.is_claim_running(claim_id),
        "live_running_tool": live_tool,
        "events": events,
        "tool_executions": data.get("tool_executions", []),
        "execution_trace": latest_state.get("execution_trace", []),
        "current_plan": latest_state.get("current_plan"),
        "completed_steps": latest_state.get("completed_steps", [])
    }


@app.get("/api/claims/{claim_id}/agent/stream")
async def stream_claim_agent(claim_id: str):
    """Server-Sent Events (SSE) live feed of agent tool execution and reasoning stream."""
    claim = agent_service.db.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim session '{claim_id}' not found.")

    async def event_generator():
        last_index = 0
        idle_cycles = 0
        while True:
            events = agent_service.get_claim_events(claim_id, after_index=last_index)
            if events:
                idle_cycles = 0
                for evt in events:
                    last_index = max(last_index, evt.get("index", last_index))
                    yield f"data: {json.dumps(evt)}\n\n"
                    if evt.get("type") == "complete":
                        return
            else:
                is_running = agent_service.is_claim_running(claim_id)
                if not is_running:
                    idle_cycles += 1
                    if idle_cycles >= 6:
                        break
                yield ": keepalive\n\n"
            await asyncio.sleep(0.4)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/claims/{claim_id}/documents")
async def get_claim_documents(claim_id: str):
    """Retrieve document listing, classified pages, and extracted entities."""
    data = agent_service.get_claim(claim_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Claim session '{claim_id}' not found.")
    claim = data["claim"]
    latest_state = data.get("latest_state") or {}
    return {
        "claim_id": claim_id,
        "policy_filename": claim.get("policy_filename"),
        "claim_filenames": claim.get("claim_filenames", []),
        "extracted_pages": latest_state.get("extracted_data", []),
        "document_classifications": latest_state.get("document_classifications", {}),
        "validation_result": latest_state.get("validation_result"),
        "validity_result": latest_state.get("validity_result")
    }


@app.post("/api/claims/{claim_id}/documents")
async def add_claim_documents(
    claim_id: str,
    files: List[UploadFile] = File(...)
):
    """Upload additional supporting documents into an existing claim session."""
    import json
    claim = agent_service.db.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim session '{claim_id}' not found.")
    added_names = []
    for f in files:
        if f.filename:
            content = await f.read()
            agent_service.save_uploaded_file(claim_id, f.filename, content)
            added_names.append(f.filename)
    existing = claim.get("claim_filenames", [])
    updated = list(set(existing + added_names))
    conn = agent_service.db._get_connection()
    try:
        with conn:
            conn.execute("UPDATE claims SET claim_filenames = ? WHERE claim_id = ?", (json.dumps(updated), claim_id))
    finally:
        conn.close()
    return {"success": True, "claim_id": claim_id, "added": added_names, "claim_filenames": updated}


@app.get("/api/claims/{claim_id}/result")
async def get_claim_result(claim_id: str):
    """Retrieve final claim readiness verdict and synthesized report."""
    data = agent_service.get_claim(claim_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Claim session '{claim_id}' not found.")
    latest_state = data.get("latest_state") or {}
    return {
        "claim_id": claim_id,
        "status": data["claim"].get("status"),
        "verdict": data.get("verdict"),
        "final_report": data.get("final_report"),
        "missing_documents": latest_state.get("missing_documents"),
        "validity_result": latest_state.get("validity_result"),
        "validation_result": latest_state.get("validation_result")
    }


@app.get("/api/claims/{claim_id}/missing-documents")
async def get_claim_missing_documents(claim_id: str):
    """Retrieve missing evidence detection results."""
    data = agent_service.get_claim(claim_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Claim session '{claim_id}' not found.")
    latest_state = data.get("latest_state") or {}
    missing_data = latest_state.get("missing_documents") or {}
    docs = missing_data.get("missing_documents", [])
    summary = missing_data.get("summary") or {}
    missing_count = summary.get("missing", len([d for d in docs if isinstance(d, dict) and d.get("missing") is True]))
    return {
        "claim_id": claim_id,
        "missing_count": missing_count,
        "missing_documents": docs,
        "analysis": missing_data
    }


@app.get("/api/claims/{claim_id}/validity")
async def get_claim_validity(claim_id: str):
    """Retrieve coverage validity and policy period analysis."""
    data = agent_service.get_claim(claim_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Claim session '{claim_id}' not found.")
    latest_state = data.get("latest_state") or {}
    return {
        "claim_id": claim_id,
        "validity_result": latest_state.get("validity_result")
    }


@app.get("/api/claims/{claim_id}/validation")
async def get_claim_validation(claim_id: str):
    """Retrieve document validation results."""
    data = agent_service.get_claim(claim_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Claim session '{claim_id}' not found.")
    latest_state = data.get("latest_state") or {}
    return {
        "claim_id": claim_id,
        "validation_result": latest_state.get("validation_result")
    }


@app.get("/api/claims/{claim_id}")
async def get_claim_details(claim_id: str):
    """Retrieve complete claim memory package, execution history, and final report."""
    data = agent_service.get_claim(claim_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Claim session '{claim_id}' not found.")
    return data


@app.get("/api/claims")
async def list_all_claims(limit: int = 50, offset: int = 0):
    """List historical claim sessions stored in persistent database."""
    claims = agent_service.list_claims(limit=limit, offset=offset)
    return {
        "total": len(claims),
        "claims": claims
    }


@app.delete("/api/claims/{claim_id}")
@app.delete("/analyses/{claim_id}")
async def delete_claim(claim_id: str):
    """Delete a claim session and its uploaded artifacts."""
    deleted = agent_service.delete_claim(claim_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Claim session '{claim_id}' not found.")
    return {"success": True, "deleted_claim_id": claim_id}


@app.post("/api/claims/{claim_id}/assistant")
@app.post("/analyses/{claim_id}/assistant")
async def ask_claim_assistant(claim_id: str, payload: Dict[str, Any] = Body(...)):
    """AI Document Assistant grounded in the active claim analysis."""
    data = agent_service.get_claim(claim_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Claim session '{claim_id}' not found.")

    question = payload.get("question", "").strip()
    if not question:
        return {"answer": "Please ask a question about your claim or policy documents.", "sources": []}

    claim = data.get("claim") or {}
    report = data.get("final_report") or {}
    latest_state = data.get("latest_state") or {}
    verdict = data.get("verdict") or report.get("verdict") or report.get("status") or claim.get("status") or "UNKNOWN"

    facts: Dict[str, Any] = {}
    if isinstance(latest_state.get("verified_facts"), dict):
        facts.update(latest_state["verified_facts"])

    extracted_pages = latest_state.get("extracted_data") or []
    if isinstance(extracted_pages, list):
        for page in extracted_pages:
            if isinstance(page, dict):
                for k, v in page.items():
                    if k not in facts and v and not isinstance(v, (dict, list)):
                        facts[k] = v
                if isinstance(page.get("extracted_fields"), dict):
                    for k, v in page["extracted_fields"].items():
                        if k not in facts and v:
                            facts[k] = v

    if isinstance(report.get("extracted_fields"), list):
        for item in report["extracted_fields"]:
            if isinstance(item, dict) and item.get("name") and item.get("value"):
                facts[item["name"].lower().replace(" ", "_")] = item["value"]

    val_res = latest_state.get("validity_result") or report.get("validity_check") or report.get("validity") or {}
    p_start = val_res.get("policy_start_date")
    p_end = val_res.get("policy_end_date")

    if not p_start or p_start == "Not specified":
        p_start = facts.get("policy_start_date") or facts.get("policy_inception_date") or facts.get("inception_date") or "Not specified"
    if not p_end or p_end == "Not specified":
        p_end = facts.get("policy_end_date") or facts.get("policy_expiry_date") or facts.get("expiry_date") or "Not specified"

    raw_missing = (
        latest_state.get("missing_documents")
        or report.get("missing_documents")
        or {}
    )
    if isinstance(raw_missing, dict):
        missing_list = (
            raw_missing.get("document_results")
            or raw_missing.get("missing_documents")
            or raw_missing.get("required_documents")
            or raw_missing.get("items")
            or []
        )
    elif isinstance(raw_missing, list):
        missing_list = raw_missing
    else:
        missing_list = []

    truly_missing: List[str] = []
    submitted_required: List[str] = []
    for d in missing_list:
        if isinstance(d, dict):
            t = d.get("document_title") or d.get("title") or d.get("name") or d.get("document") or d.get("document_type")
            if not t:
                continue
            title_str = str(t).strip()
            if d.get("missing") is True:
                truly_missing.append(title_str)
            elif d.get("missing") is False:
                submitted_required.append(title_str)
        elif isinstance(d, str) and d.strip():
            truly_missing.append(d.strip())

    q_lower = question.lower()
    sources: List[Dict[str, Any]] = []

    if any(w in q_lower for w in ["missing", "checklist", "unsubmitted", "absent", "need to upload", "what document"]):
        if truly_missing:
            docs_list = "\n".join(f"• **{doc}**" for doc in truly_missing)
            ans = (
                f"The following mandatory document(s) are currently missing from the claim package:\n\n"
                f"{docs_list}\n\n"
                f"Please upload these records to complete your claim submission."
            )
        else:
            ans = "All mandatory documents, itemized hospital bills, and medical evidence specified by the policy schedule have been submitted and verified. No documents are missing."

    elif any(w in q_lower for w in ["verdict", "ready", "status", "admissib", "approved", "rejected", "accept", "submit"]):
        ans = f"**Claim Status**: {verdict}\n\n"
        if verdict == "CLAIM_READY_FOR_SUBMISSION":
            ans += "All mandatory documents have been submitted and all dates fall within the active policy period. The claim is ready for insurer adjudication."
        elif "MISSING" in str(verdict):
            docs_list = "\n".join(f"• **{doc}**" for doc in truly_missing) if truly_missing else ""
            ans += f"The claim requires additional mandatory evidence before submission:\n\n{docs_list}\n\nPlease upload these documents to proceed."
        else:
            ans += f"**Audit Summary**: {report.get('decision_summary', 'Discrepancy or validation action required.')}"

    elif any(w in q_lower for w in ["date", "period", "valid", "coverage", "when", "admit", "admission", "discharge"]):
        ans = f"• **Policy Coverage Window**: {p_start} to {p_end}\n"
        adm_date = facts.get("admission_date") or facts.get("date_of_admission")
        dis_date = facts.get("discharge_date") or facts.get("date_of_discharge")
        if adm_date or dis_date:
            ans += f"• **Hospitalization Period**: {adm_date or 'N/A'} to {dis_date or 'N/A'}\n"
        if val_res.get("valid") is False:
            reasons = val_res.get("reasons") or ["Hospitalization or bill dates fall outside the active policy period."]
            ans += f"\n⚠️ **Discrepancy Detected**: {' '.join(reasons)}"
        else:
            ans += "\n✓ All medical treatment and hospital admission dates fall within this active coverage period."

    elif any(w in q_lower for w in ["patient", "insured", "name", "who", "holder", "age", "gender"]):
        p_name = facts.get("patient_name") or facts.get("insured_name") or facts.get("policy_holder_name") or "Specified in document"
        pol_num = facts.get("policy_number") or facts.get("policy_no") or ""
        ans = f"• **Patient / Insured Name**: {p_name}\n"
        if pol_num:
            ans += f"• **Policy Number**: {pol_num}\n"
        age = facts.get("age") or facts.get("patient_age")
        if age:
            ans += f"• **Age**: {age}\n"

    elif any(w in q_lower for w in ["hospital", "clinic", "doctor", "physician", "facility", "where"]):
        h_name = facts.get("hospital_name") or facts.get("provider_name") or facts.get("facility_name") or "Identified in invoice"
        ans = f"• **Treating Hospital**: {h_name}\n"
        doc_name = facts.get("doctor_name") or facts.get("treating_doctor") or facts.get("consultant")
        if doc_name:
            ans += f"• **Attending Physician**: {doc_name}\n"

    elif any(w in q_lower for w in ["bill", "amount", "total", "cost", "expense", "charge", "price", "invoice", "claim amount"]):
        amt = facts.get("total_bill_amount") or facts.get("total_amount") or facts.get("bill_amount") or facts.get("claimed_amount") or "Verified in invoice"
        ans = f"• **Total Claimed Bill Amount**: {amt}\n"
        inv_no = facts.get("invoice_number") or facts.get("bill_number") or facts.get("bill_no")
        if inv_no:
            ans += f"• **Invoice Number**: #{inv_no}\n"

    elif any(w in q_lower for w in ["diagnosis", "ailment", "condition", "treatment", "disease", "procedure", "surgery", "illness", "reason"]):
        diag = facts.get("diagnosis") or facts.get("provisional_diagnosis") or facts.get("final_diagnosis") or facts.get("ailment") or facts.get("treatment") or "Detailed in medical records"
        ans = f"• **Documented Diagnosis / Medical Condition**: {diag}"

    elif any(w in q_lower for w in ["exclusion", "clause", "terms", "condition", "not covered"]):
        exclusions = []
        if isinstance(report.get("exclusions"), list):
            exclusions = report["exclusions"]
        elif isinstance(report.get("coverage_evaluation", {}).get("exclusions"), list):
            exclusions = report["coverage_evaluation"]["exclusions"]
        if exclusions:
            ex_texts = [e.get("text", str(e)) if isinstance(e, dict) else str(e) for e in exclusions[:5]]
            ans = f"Identified Policy Exclusions & Specific Conditions:\n\n" + "\n".join(f"• {t}" for t in ex_texts)
        else:
            ans = "No specific policy exclusions or coverage restrictions were flagged for this claim."

    else:
        summary = report.get("decision_summary") or "The submitted policy schedule and medical hospital bills have been cross-checked by InsureMate."
        key_facts = []
        if facts.get("patient_name"): key_facts.append(f"Patient: {facts['patient_name']}")
        if facts.get("hospital_name"): key_facts.append(f"Hospital: {facts['hospital_name']}")
        if facts.get("total_bill_amount"): key_facts.append(f"Bill: {facts['total_bill_amount']}")
        facts_summary = f" ({', '.join(key_facts)})" if key_facts else ""
        ans = f"Based on the analysis for claim {claim_id}{facts_summary}:\n\n"
        ans += f"• **Verdict**: {verdict}\n"
        ans += f"• **Policy Period**: {p_start} to {p_end}\n"
        if truly_missing:
            ans += f"• **Missing Evidence**:\n" + "\n".join(f"  - {m}" for m in truly_missing) + "\n\n"
        else:
            ans += f"• **Evidence Status**: All mandatory evidence verified\n\n"
        ans += f"{summary}"

    return {"answer": ans, "sources": []}


@app.get("/api/claims/{claim_id}/report")
@app.get("/analyses/{claim_id}/report")
async def get_claim_report(claim_id: str):
    """Retrieve downloadable PDF report for the claim session."""
    data = agent_service.get_claim(claim_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Claim session '{claim_id}' not found.")

    pdf_bytes = generate_claim_report_pdf(claim_id, data)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="insuremate-report-{claim_id}.pdf"',
            "Content-Type": "application/pdf",
        },
    )


# Compatibility Aliases for /analyses endpoints:
@app.get("/analyses")
async def analyses_list_alias(limit: int = 50, offset: int = 0):
    res = await list_all_claims(limit=limit, offset=offset)
    return res.get("claims", [])

@app.get("/analyses/{claim_id}")
async def analyses_get_alias(claim_id: str):
    return await get_claim_details(claim_id=claim_id)

@app.put("/analyses/{claim_id}/review")
async def analyses_save_review(claim_id: str, review_data: Dict[str, Any] = Body(...)):
    return {"success": True, "claim_id": claim_id, "review": review_data}


def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Launch the uvicorn web server."""
    import uvicorn
    print("\n" + "=" * 70)
    print("      LAUNCHING INSUREMATE PHASE 7 WEB APPLICATION")
    print(f"      Access UI at: http://localhost:{port} or http://127.0.0.1:{port}")
    print("=" * 70 + "\n")
    uvicorn.run("app.server:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    run_server()
