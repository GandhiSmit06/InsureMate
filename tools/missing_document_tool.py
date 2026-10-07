"""tools/missing_document_tool.py
Agent-ready callable tool wrapping dynamic missing document detection.
Designed for registration with InsureMate Agent Orchestrator.
"""

from typing import Any, Dict, List, Optional
from services.missing_document.detector import MissingDocumentDetector, detect_missing_documents
from services.missing_document.llm_gateway import LLMGateway
from utils.logger import logger


class MissingDocumentTool:
    """
    Callable Agent Tool: Missing Document Detection.
    Dynamically determines required documents for an insurance claim based on policy
    evidence from Phase 1, semantically compares against submitted claim documents,
    and identifies missing documents with exact 1-indexed page numbers.
    """

    name: str = "missing_document_tool"
    description: str = (
        "Dynamically determines required documents for an insurance claim based on policy "
        "terms from Phase 1, semantically compares against submitted claim documents, "
        "and identifies missing documents with exact 1-indexed page numbers."
    )

    def __init__(self, gateway: Optional[LLMGateway] = None):
        self.detector = MissingDocumentDetector(gateway=gateway)

    @property
    def schema(self) -> Dict[str, Any]:
        """JSON schema definition for LLM tool calling registration."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "phase1_output": {
                            "type": "object",
                            "description": "Extracted document payload from QwenVLExtractionTool.",
                        },
                        "phase2_output": {
                            "type": "object",
                            "description": "Optional validation report from DocumentValidationTool.",
                        },
                        "phase3_output": {
                            "type": "object",
                            "description": "Optional validity check report from ValidityCheckerTool.",
                        },
                    },
                    "required": ["phase1_output"],
                },
            },
        }

    def run(
        self,
        phase1_output: Optional[Dict[str, Any]] = None,
        phase2_output: Optional[Dict[str, Any]] = None,
        phase3_output: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Execute missing document detection."""
        logger.missing_doc("Executing MissingDocumentTool...")
        return self.detector.detect(
            phase1_output=phase1_output,
            phase2_output=phase2_output,
            phase3_output=phase3_output,
            **kwargs
        )
