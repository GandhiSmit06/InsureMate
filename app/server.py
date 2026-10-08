"""app/server.py
InsureMate Phase 7 FastAPI Application.
Serves the web UI and REST API for document upload, session creation,
autonomous agent orchestration, claim memory persistence, and result visualization.
"""

import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from services.agent_service import AgentService
from services.database.db import ClaimDatabase
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

# Initialize Service & Database
agent_service = AgentService()
static_dir = Path(__file__).resolve().parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)

# Mount Static Files
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# Pydantic Schemas
class DemoRequest(BaseModel):
    demo_type: Optional[str] = None
    preset: Optional[str] = None
    auto_run: bool = False
    offline_mode: bool = True


class RunRequest(BaseModel):
    max_pages: Optional[int] = 3


# ==============================================================================
# FRONTEND ROUTE
# ==============================================================================
@app.get("/", response_class=FileResponse)
async def serve_index():
    index_file = static_dir / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Index HTML not found.")
    return FileResponse(str(index_file))


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


@app.post("/api/claims/upload")
async def upload_and_create_claim(
    policy_file: Optional[UploadFile] = File(None),
    claim_file: Optional[UploadFile] = File(None),
    claim_files: Optional[List[UploadFile]] = File(None),
    goal: str = Form("Determine claim readiness and identify any missing evidence."),
    session_name: Optional[str] = Form(None),
    claim_type: str = Form("general"),
    offline_mode: bool = Form(True),
    auto_run: bool = Form(False)
):
    """
    Upload insurance policy and claim documents, establish claim session,
    and optionally execute the InsureMate Agent immediately.
    """
    claim_id = f"CLM-{uuid.uuid4().hex[:8].upper()}"

    p_path = None
    p_name = None
    if policy_file and policy_file.filename:
        content = await policy_file.read()
        p_name = policy_file.filename
        p_path = agent_service.save_uploaded_file(claim_id, p_name, content)

    c_paths = []
    c_names = []
    # Single claim_file
    if claim_file and claim_file.filename:
        content = await claim_file.read()
        c_names.append(claim_file.filename)
        c_paths.append(agent_service.save_uploaded_file(claim_id, claim_file.filename, content))

    # Multiple claim_files
    if claim_files:
        for cf in claim_files:
            if cf.filename:
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
        "claim": claim
    }

    # Auto-run if requested
    if auto_run:
        run_data = agent_service.run_agent(claim_id=claim_id)
        result["run_results"] = run_data

    return JSONResponse(status_code=status.HTTP_201_CREATED, content=result)


@app.post("/api/claims/demo")
async def create_demo_claim(request: DemoRequest):
    """Create a sample session from repository files and optionally execute agent."""
    preset = request.preset or request.demo_type or "health"
    try:
        claim = agent_service.create_demo_session(
            demo_type=preset,
            preset=preset,
            offline_mode=request.offline_mode
        )
        claim_id = claim["claim_id"]
        result = {
            "success": True,
            "claim_id": claim_id,
            "claim": claim
        }

        if request.auto_run:
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

    try:
        run_data = agent_service.run_agent(claim_id=claim_id, max_pages=request.max_pages)
        return run_data
    except Exception as e:
        logger.error(f"[API] Error running agent for claim {claim_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")


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
async def delete_claim(claim_id: str):
    """Delete a claim session and its uploaded artifacts."""
    deleted = agent_service.delete_claim(claim_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Claim session '{claim_id}' not found.")
    return {"success": True, "deleted_claim_id": claim_id}


def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Launch the uvicorn web server."""
    import uvicorn
    print("\n" + "=" * 70)
    print("      LAUNCHING INSUREMATE PHASE 7 WEB APPLICATION")
    print(f"      Access UI at: http://localhost:{port} or http://127.0.0.1:{port}")
    print("=" * 70 + "\n")
    uvicorn.run("app.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run_server()
