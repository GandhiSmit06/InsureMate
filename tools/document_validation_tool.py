"""
tools/document_validation_tool.py
Agent-ready callable tool wrapping deterministic document validation.
Designed for registration with future Phase 4 InsureMate Agent Orchestrator.
"""

from typing import Any, Dict, List, Optional, Union

from services.document_validation.validator import DocumentValidator
from utils.logger import logger


class DocumentValidationTool:
    """
    Callable Agent Tool: Document Validation.
    Deterministically evaluates extracted claim documents against mandatory field requirements
    per document category, detecting incomplete documents with specific actionable reasons.
    """

    name: str = "document_validation_tool"
    description: str = (
        "Deterministically validates extracted documents against required claim fields by type "
        "(policy, medical bill, hospital record, report) and returns pass/fail with missing fields."
    )

    def __init__(self, custom_requirements: Optional[Dict[str, Dict[str, str]]] = None):
        self.validator = DocumentValidator(custom_requirements=custom_requirements)

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
                        "extracted_documents": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "List of extracted page dictionaries from QwenVLExtractionTool.",
                        },
                        "requirements": {
                            "type": "object",
                            "description": "Optional custom field requirements per document type.",
                        },
                    },
                    "required": ["extracted_documents"],
                },
            },
        }

    def run(
        self,
        extracted_documents: Union[List[Dict[str, Any]], Dict[str, Any]],
        requirements: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute tool call.

        Returns:
            Standardized agent observation dictionary.
        """
        try:
            validation_result = self.validator.validate_batch(
                extracted_documents=extracted_documents,
                requirements=requirements
            )
            data = validation_result.to_dict()
            return {
                "status": "success",
                "tool": self.name,
                "valid": data["valid"],
                "total_documents": data["total_documents"],
                "valid_documents": data["valid_documents"],
                "invalid_documents": data["invalid_documents"],
                "validation_result": data,
                "error": None,
            }
        except Exception as e:
            logger.error(f"Tool execution failed in {self.name}: {e}")
            return {
                "status": "error",
                "tool": self.name,
                "valid": False,
                "total_documents": 0,
                "valid_documents": 0,
                "invalid_documents": 0,
                "validation_result": {},
                "error": str(e),
            }

    def __call__(self, *args, **kwargs) -> Dict[str, Any]:
        return self.run(*args, **kwargs)
