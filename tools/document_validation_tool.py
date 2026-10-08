"""tools/document_validation_tool.py
Agent-ready callable tool wrapping deterministic document validation.
Adheres to the Phase 6 AgentTool interface for integration with Phase 5 Agent Orchestrator.
"""

from typing import Any, Dict, List, Optional, Union

from services.document_validation.validator import DocumentValidator
from tools.base_tool import AgentTool
from utils.logger import logger


class DocumentValidationTool(AgentTool):
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
                        "claim_id": {
                            "type": "string",
                            "description": "Unique identifier for the claim (optional).",
                        },
                        "extracted_data": {
                            "type": "object",
                            "description": "Extraction payload containing extracted_documents list.",
                        },
                        "extracted_documents": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "List of extracted page dictionaries from DocumentExtractionTool.",
                        },
                        "requirements": {
                            "type": "object",
                            "description": "Optional custom field requirements per document type.",
                        },
                    },
                },
            },
        }

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Standard Phase 6 Tool Execution contract.

        Args:
            input_data: Dictionary containing:
                - 'claim_id': Optional claim identifier
                - 'extracted_data' OR 'extracted_documents' OR 'documents': Document payloads
                - 'requirements': Optional custom requirements dictionary

        Returns:
            Standardized Phase 6 dictionary:
            {
                "success": bool,
                "claim_id": str,
                "validation_results": dict,
                "errors": list[str]
            }
        """
        input_data = self.validate_input(input_data)
        claim_id = str(input_data.get("claim_id") or "CLM-UNKNOWN")
        requirements = input_data.get("requirements")

        # Resolve extracted documents from varied agent payload formats
        extracted_docs: Any = None
        if "extracted_data" in input_data and input_data["extracted_data"]:
            ed = input_data["extracted_data"]
            if isinstance(ed, dict) and "extracted_documents" in ed:
                extracted_docs = ed["extracted_documents"]
            else:
                extracted_docs = ed
        elif "extracted_documents" in input_data:
            extracted_docs = input_data["extracted_documents"]
        elif "documents" in input_data and isinstance(input_data["documents"], list):
            # Check if elements are already extracted entity dictionaries
            if input_data["documents"] and isinstance(input_data["documents"][0], dict) and "document_type" in input_data["documents"][0]:
                extracted_docs = input_data["documents"]
        elif "page_number" in input_data or "document_type" in input_data:
            # Single document passed directly
            extracted_docs = input_data

        if extracted_docs is None:
            # Fall back to checking if input_data has any document lists
            extracted_docs = []

        try:
            validation_result = self.validator.validate_batch(
                extracted_documents=extracted_docs,
                requirements=requirements,
            )
            data = validation_result.to_dict()
            is_valid = data.get("valid", False)
            reasons = data.get("reasons", [])

            return {
                "success": True,
                "claim_id": claim_id,
                "validation_results": data,
                "errors": [] if is_valid else reasons,
                # Backward-compatible fields
                "status": "success",
                "tool": self.name,
                "valid": is_valid,
                "total_documents": data.get("total_documents", 0),
                "valid_documents": data.get("valid_documents", 0),
                "invalid_documents": data.get("invalid_documents", 0),
                "validation_result": data,
                "error": None,
            }
        except Exception as e:
            logger.error(f"Tool execution failed in {self.name}: {e}")
            return {
                "success": False,
                "claim_id": claim_id,
                "validation_results": {},
                "errors": [str(e)],
                "status": "error",
                "tool": self.name,
                "valid": False,
                "total_documents": 0,
                "valid_documents": 0,
                "invalid_documents": 0,
                "validation_result": {},
                "error": str(e),
            }

    def run(
        self,
        extracted_documents: Union[List[Dict[str, Any]], Dict[str, Any]],
        requirements: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Legacy interface preserving full backward compatibility for Phase 1-4 callers.
        """
        try:
            validation_result = self.validator.validate_batch(
                extracted_documents=extracted_documents,
                requirements=requirements,
            )
            data = validation_result.to_dict()
            is_valid = data.get("valid", False)
            reasons = data.get("reasons", [])
            return {
                "success": True,
                "status": "success",
                "tool": self.name,
                "valid": is_valid,
                "total_documents": data["total_documents"],
                "valid_documents": data["valid_documents"],
                "invalid_documents": data["invalid_documents"],
                "validation_result": data,
                "validation_results": data,
                "errors": [] if is_valid else reasons,
                "error": None,
            }
        except Exception as e:
            logger.error(f"Tool execution failed in {self.name}: {e}")
            return {
                "success": False,
                "status": "error",
                "tool": self.name,
                "valid": False,
                "total_documents": 0,
                "valid_documents": 0,
                "invalid_documents": 0,
                "validation_result": {},
                "validation_results": {},
                "errors": [str(e)],
                "error": str(e),
            }

    def __call__(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        if args and isinstance(args[0], dict) and "extracted_data" in args[0]:
            return self.execute(args[0])
        return self.run(*args, **kwargs)
