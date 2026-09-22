import uvicorn
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from phase3.api.routes import router
from phase3.config import config

logging.basicConfig(
    level=logging.DEBUG if config.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger("phase3")

app = FastAPI(
    title="InsureMate Phase 3: Medical Insurance Requirement Extraction",
    description=(
        "Autonomous AI/ML engine for extracting strictly structured insurance claim requirements "
        "directly from medical policy PDFs or policy text without external dependencies."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for frontend and cross-service interoperability
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Phase 3 routes
app.include_router(router)


@app.get("/", summary="Root Endpoint")
async def root():
    return {
        "message": "InsureMate Phase 3 Requirement Extraction API is running.",
        "documentation": "/docs",
        "health": "/api/phase3/health",
        "extract_endpoint": "/api/phase3/extract-requirements",
    }


if __name__ == "__main__":
    logger.info(f"Starting Phase 3 server on {config.HOST}:{config.PORT}...")
    uvicorn.run(
        "phase3.main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG,
    )
