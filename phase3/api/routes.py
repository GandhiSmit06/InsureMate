import logging
from typing import Optional
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, status, Request
from fastapi.responses import JSONResponse

from phase3.schema.models import Phase3Request, Phase3Response
from phase3.engine import RequirementExtractionEngine
from phase3.config import config
from phase3.extractor.llm_extractor import LLMExtractor

logger = logging.getLogger("phase3.api")

router = APIRouter(prefix="/api/phase3", tags=["Phase 3 - Requirement Extraction"])
engine = RequirementExtractionEngine()


@router.get("/health", summary="Health Check for Phase 3")
async def health_check():
    """Verify Phase 3 service status and engine configuration."""
    llm_extractor = LLMExtractor()
    return {
        "status": "healthy",
        "module": "InsureMate Phase 3: Medical Insurance Requirement Extraction",
        "version": "1.0.0",
        "engine_mode": config.ENGINE_MODE,
        "llm_available": llm_extractor.is_available(),
        "llm_provider": llm_extractor.provider if llm_extractor.is_available() else "none",
    }


@router.post(
    "/extract-requirements",
    response_model=Phase3Response,
    summary="Extract Insurance Claim Requirements from Policy",
    description="Accepts either JSON with policy_text or multipart/form-data with a policy PDF file.",
)
async def extract_requirements(
    request: Request,
    payload: Optional[Phase3Request] = None,
    file: Optional[UploadFile] = File(None),
    claim_type: Optional[str] = Form(None),
    policy_name: Optional[str] = Form(None),
):
    content_type = request.headers.get("content-type", "")

    # 1. Handle JSON input
    if "application/json" in content_type:
        try:
            body = await request.json()
            req_data = Phase3Request(**body)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid JSON request body: {str(e)}",
            )

        if not req_data.policy_text or not req_data.policy_text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Field 'policy_text' must not be empty.",
            )

        resp = engine.process(
            policy_text=req_data.policy_text,
            claim_type=req_data.claim_type,
            policy_name=req_data.policy_name,
        )
        if not resp.success:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=resp.error or "Failed to extract requirements.",
            )
        return resp

    # 2. Handle Multipart / File Upload
    if file:
        filename = file.filename or ""
        if not filename.lower().endswith((".pdf", ".txt")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF and text (.txt) files are accepted.",
            )

        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        if filename.lower().endswith(".pdf"):
            resp = engine.process(
                pdf_bytes=file_bytes,
                claim_type=claim_type,
                policy_name=policy_name or filename,
            )
        else:
            # Plain text file
            text_content = file_bytes.decode("utf-8", errors="ignore")
            resp = engine.process(
                policy_text=text_content,
                claim_type=claim_type,
                policy_name=policy_name or filename,
            )

        if not resp.success:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=resp.error or "Failed to extract requirements from file.",
            )
        return resp

    # If neither JSON nor file provided
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Please provide either JSON with 'policy_text' or a multipart form with a 'file'.",
    )
