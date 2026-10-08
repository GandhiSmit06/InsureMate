"""tools/validity_checker_tool.py
Agent-ready callable tool wrapping deterministic validity checking.
Adheres to the Phase 6 AgentTool interface for integration with Phase 5 Agent Orchestrator.
"""

from typing import Any, Dict, List, Optional, Union

from services.validity_checker.checker import ValidityChecker
from tools.base_tool import AgentTool
from utils.logger import logger


class ValidityCheckerTool(AgentTool):
    """
    Callable Agent Tool: Claim Validity Checker.
    Deterministically evaluates whether submitted medical bills and incident dates fall
    within the policy active duration window, normalizes dates, and verifies patient coverage.
    """

    name: str = "validity_checker_tool"
    description: str = (
        "Deterministically verifies whether medical bills and claim documents fall within "
        "policy coverage dates, checks date formatting, and cross-references patient identity."
    )

    def __init__(self):
        self.checker = ValidityChecker()

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
                        "policy_data": {
                            "type": "object",
                            "description": "Extracted policy document dictionary or list containing policy period.",
                        },
                        "document_data": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "List of extracted claim document pages (bills, reports) with dates.",
                        },
                        "extracted_data": {
                            "type": "object",
                            "description": "Optional complete extraction payload to auto-partition policy and claim documents.",
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
                - 'policy_data': Extracted policy dictionary or list
                - 'document_data': Extracted claim document list
                - 'extracted_data': Optional full extraction payload (auto-separated if policy_data/document_data not provided)

        Returns:
            Standardized Phase 6 dictionary:
            {
                "success": bool,
                "claim_id": str,
                "validity_results": dict,
                "errors": list[str]
            }
        """
        input_data = self.validate_input(input_data)
        claim_id = str(input_data.get("claim_id") or "CLM-UNKNOWN")

        policy_data = input_data.get("policy_data")
        document_data = input_data.get("document_data") or input_data.get("claim_data")

        # If policy_data or document_data are not explicitly separated, try auto-partitioning from extracted_data or documents
        if policy_data is None or document_data is None:
            extracted_pool: List[Dict[str, Any]] = []
            if "extracted_data" in input_data and input_data["extracted_data"]:
                ed = input_data["extracted_data"]
                if isinstance(ed, dict) and "extracted_documents" in ed:
                    extracted_pool = ed["extracted_documents"]
                elif isinstance(ed, list):
                    extracted_pool = ed
            elif "documents" in input_data and isinstance(input_data["documents"], list):
                if input_data["documents"] and isinstance(input_data["documents"][0], dict):
                    extracted_pool = input_data["documents"]

            if extracted_pool:
                derived_policy = []
                derived_claims = []
                for doc in extracted_pool:
                    if isinstance(doc, dict):
                        if doc.get("document_type") == "insurance_policy":
                            derived_policy.append(doc)
                        else:
                            derived_claims.append(doc)

                if policy_data is None and derived_policy:
                    policy_data = derived_policy[0] if len(derived_policy) == 1 else derived_policy
                if document_data is None and derived_claims:
                    document_data = derived_claims

        # Fallbacks for empty inputs
        policy_data = policy_data or {}
        document_data = document_data or []

        try:
            validity_result = self.checker.check_validity(
                policy_data=policy_data,
                document_data=document_data,
            )
            data = validity_result.to_dict()
            is_valid = data.get("valid", False)
            reasons = data.get("reasons", [])

            return {
                "success": True,
                "claim_id": claim_id,
                "validity_results": data,
                "errors": [] if is_valid else reasons,
                # Backward-compatible fields
                "status": "success",
                "tool": self.name,
                "valid": is_valid,
                "policy_period": data.get("policy_period", {}),
                "reasons": reasons,
                "checks": data.get("checks", []),
                "identity_match": data.get("identity_match"),
                "error": None,
            }
        except Exception as e:
            logger.error(f"Tool execution failed in {self.name}: {e}")
            return {
                "success": False,
                "claim_id": claim_id,
                "validity_results": {},
                "errors": [str(e)],
                "status": "error",
                "tool": self.name,
                "valid": False,
                "policy_period": {},
                "reasons": [f"Execution error: {e}"],
                "checks": [],
                "identity_match": None,
                "error": str(e),
            }

    def run(
        self,
        policy_data: Union[Dict[str, Any], List[Dict[str, Any]]],
        document_data: Union[Dict[str, Any], List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """
        Legacy interface preserving full backward compatibility for Phase 1-4 callers.
        """
        try:
            validity_result = self.checker.check_validity(
                policy_data=policy_data,
                document_data=document_data,
            )
            data = validity_result.to_dict()
            is_valid = data.get("valid", False)
            reasons = data.get("reasons", [])
            return {
                "success": True,
                "status": "success",
                "tool": self.name,
                "valid": is_valid,
                "policy_period": data["policy_period"],
                "reasons": reasons,
                "checks": data["checks"],
                "identity_match": data["identity_match"],
                "validity_results": data,
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
                "policy_period": {},
                "reasons": [f"Execution error: {e}"],
                "checks": [],
                "identity_match": None,
                "validity_results": {},
                "errors": [str(e)],
                "error": str(e),
            }

    def __call__(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        if args and isinstance(args[0], dict) and "policy_data" in args[0]:
            return self.execute(args[0])
        return self.run(*args, **kwargs)
