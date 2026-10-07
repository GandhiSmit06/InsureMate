"""
tools/validity_checker_tool.py
Agent-ready callable tool wrapping deterministic validity checking.
Designed for registration with future Phase 4 InsureMate Agent Orchestrator.
"""

from typing import Any, Dict, List, Optional, Union

from services.validity_checker.checker import ValidityChecker
from utils.logger import logger


class ValidityCheckerTool:
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
                        "policy_data": {
                            "type": "object",
                            "description": "Extracted policy document dictionary or list containing policy period.",
                        },
                        "document_data": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "List of extracted claim document pages (bills, reports) with dates.",
                        },
                    },
                    "required": ["policy_data", "document_data"],
                },
            },
        }

    def run(
        self,
        policy_data: Union[Dict[str, Any], List[Dict[str, Any]]],
        document_data: Union[Dict[str, Any], List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """
        Execute tool call.

        Returns:
            Standardized agent observation dictionary.
        """
        try:
            validity_result = self.checker.check_validity(
                policy_data=policy_data,
                document_data=document_data
            )
            data = validity_result.to_dict()
            return {
                "status": "success",
                "tool": self.name,
                "valid": data["valid"],
                "policy_period": data["policy_period"],
                "reasons": data["reasons"],
                "checks": data["checks"],
                "identity_match": data["identity_match"],
                "error": None,
            }
        except Exception as e:
            logger.error(f"Tool execution failed in {self.name}: {e}")
            return {
                "status": "error",
                "tool": self.name,
                "valid": False,
                "policy_period": {},
                "reasons": [f"Execution error: {e}"],
                "checks": [],
                "identity_match": None,
                "error": str(e),
            }

    def __call__(self, *args, **kwargs) -> Dict[str, Any]:
        return self.run(*args, **kwargs)
