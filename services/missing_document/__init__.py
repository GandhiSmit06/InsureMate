"""services/missing_document package.
Phase 4 Dynamic Policy Requirement Extraction and Missing Document Detection.
"""

from services.missing_document.detector import (
    MissingDocumentDetector,
    detect_missing_documents,
    run_phase4,
    format_detection_table,
)
from services.missing_document.llm_gateway import LLMGateway
from services.missing_document.ollama_client import OllamaClient, OllamaError
from services.missing_document.schemas import (
    MissingDocumentResponse,
    RequiredDocumentDefinition,
    DocumentResultItem,
    MissingDocumentSummary,
    Phase4ValidationError,
    validate_detection_output,
)
from services.missing_document.prompt_builder import (
    SYSTEM_REQUIREMENT_EXTRACTION_PROMPT,
    SYSTEM_MATCHING_PROMPT,
    build_requirement_extraction_prompt,
    build_matching_prompt,
    build_retry_prompt,
)

__all__ = [
    "MissingDocumentDetector",
    "detect_missing_documents",
    "run_phase4",
    "format_detection_table",
    "LLMGateway",
    "OllamaClient",
    "OllamaError",
    "MissingDocumentResponse",
    "RequiredDocumentDefinition",
    "DocumentResultItem",
    "MissingDocumentSummary",
    "Phase4ValidationError",
    "validate_detection_output",
    "SYSTEM_REQUIREMENT_EXTRACTION_PROMPT",
    "SYSTEM_MATCHING_PROMPT",
    "build_requirement_extraction_prompt",
    "build_matching_prompt",
    "build_retry_prompt",
]
