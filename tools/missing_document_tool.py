"""tools/missing_document_tool.py
Agent-ready callable tool wrapping dynamic missing document detection.
Adheres to the Phase 6 AgentTool interface for integration with Phase 5 Agent Orchestrator.
"""

from typing import Any, Dict, List, Optional
from services.missing_document.detector import MissingDocumentDetector, detect_missing_documents
from services.missing_document.llm_gateway import LLMGateway
from tools.base_tool import AgentTool
from utils.logger import logger


class MissingDocumentTool(AgentTool):
    """
    Callable Agent Tool: Missing Document Detection.
    Dynamically determines required documents for an insurance claim based on policy
    evidence from Phase 1, semantically compares against submitted claim documents,
    and identifies missing documents with exact 1-indexed page numbers.
    """

    name: str = "missing_document_tool"
    description: str = (
        "Dynamically determines required documents for an insurance claim based on policy "
        "terms, semantically compares against submitted claim documents, "
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
                        "claim_id": {
                            "type": "string",
                            "description": "Unique identifier for the claim (optional).",
                        },
                        "extracted_data": {
                            "type": "object",
                            "description": "Extracted document payload from DocumentExtractionTool.",
                        },
                        "validation_results": {
                            "type": "object",
                            "description": "Optional validation report from DocumentValidationTool.",
                        },
                        "validity_results": {
                            "type": "object",
                            "description": "Optional validity check report from ValidityCheckerTool.",
                        },
                        "phase1_output": {
                            "type": "object",
                            "description": "Legacy alias for extracted_data.",
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
                - 'extracted_data' OR 'phase1_output': Extracted document payload
                - 'validation_results' OR 'phase2_output': Optional validation output
                - 'validity_results' OR 'phase3_output': Optional validity output

        Returns:
            Standardized Phase 6 dictionary:
            {
                "success": bool,
                "claim_id": str,
                "missing_documents": list[dict],
                "errors": list[str]
            }
        """
        input_data = self.validate_input(input_data)
        claim_id = str(input_data.get("claim_id") or "CLM-UNKNOWN")

        # Map agent payload names to detector parameters
        p1 = input_data.get("extracted_data") or input_data.get("phase1_output")
        if p1 is None and ("extracted_documents" in input_data or "documents" in input_data):
            p1 = input_data

        p2 = input_data.get("validation_results") or input_data.get("phase2_output")
        p3 = input_data.get("validity_results") or input_data.get("phase3_output")

        try:
            raw_res = self.detector.detect(
                phase1_output=p1,
                phase2_output=p2,
                phase3_output=p3,
                **{k: v for k, v in input_data.items() if k not in ("claim_id", "extracted_data", "phase1_output", "validation_results", "phase2_output", "validity_results", "phase3_output")}
            )
            status = raw_res.get("status", "success")
            is_success = status in ("success", "no_requirements_found")
            missing_docs = raw_res.get("missing_documents") or raw_res.get("document_results") or []

            errors: List[str] = []
            if not is_success:
                err = raw_res.get("error") or f"Detection status: {status}"
                errors.append(str(err))

            result = {
                "success": is_success,
                "claim_id": claim_id,
                "missing_documents": missing_docs,
                "summary": raw_res.get("summary", {}),
                "required_documents": raw_res.get("required_documents", []),
                "document_results": raw_res.get("document_results", []),
                "detection_results": raw_res,
                "errors": errors,
                # Backward-compatible fields
                "status": status,
                "tool": self.name,
                "error": errors[0] if errors else None,
            }
            return result
        except Exception as e:
            logger.error(f"Tool execution failed in {self.name}: {e}")
            return {
                "success": False,
                "claim_id": claim_id,
                "missing_documents": [],
                "summary": {},
                "required_documents": [],
                "document_results": [],
                "detection_results": {},
                "errors": [str(e)],
                "status": "error",
                "tool": self.name,
                "error": str(e),
            }

    def run(
        self,
        phase1_output: Optional[Dict[str, Any]] = None,
        phase2_output: Optional[Dict[str, Any]] = None,
        phase3_output: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Legacy interface preserving full backward compatibility for Phase 1-4 callers.
        """
        logger.missing_doc("Executing MissingDocumentTool via run()...")
        res = self.detector.detect(
            phase1_output=phase1_output,
            phase2_output=phase2_output,
            phase3_output=phase3_output,
            **kwargs
        )
        if isinstance(res, dict):
            res["tool"] = self.name
            if "success" not in res:
                res["success"] = res.get("status") in ("success", "no_requirements_found")
        return res

    def __call__(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        if args and isinstance(args[0], dict) and "extracted_data" in args[0]:
            return self.execute(args[0])
        return self.run(*args, **kwargs)
