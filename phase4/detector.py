"""Phase 4 Detector: Missing-Document Detection component.

This module provides the primary interface for Phase 4. It receives structured
Phase 3 data, coordinates through the LLM gateway, and produces the validated
detection result.
"""
from typing import Dict, Any, Union, Optional
from phase4.gateway.llm_gateway import LLMGateway, llm_gateway
from phase4.schemas.input_schema import Phase3Data


class MissingDocumentDetector:
    """Missing document detector component."""

    def __init__(self, gateway: Optional[LLMGateway] = None):
        self.gateway = gateway or LLMGateway()

    def detect(self, phase3_data: Union[Dict[str, Any], Phase3Data]) -> Dict[str, Any]:
        """Detect missing documents from structured Phase-3 input.

        Args:
            phase3_data: Dictionary or Phase3Data instance containing
                         policy_requirements and submitted_documents.

        Returns:
            Validated result dict or structured error.
        """
        return self.gateway.detect(phase3_data)


def detect_missing_documents(
    phase3_data: Union[Dict[str, Any], Phase3Data],
    gateway: Optional[LLMGateway] = None,
    client: Optional[Any] = None
) -> Dict[str, Any]:
    """Primary Phase 4 function.

    Takes structured Phase-3 data, delegates to LLM gateway, and returns
    the validated missing document detection results.

    Example usage:
        result = detect_missing_documents(phase3_data)
        if "missing_documents" in result:
            for item in result["missing_documents"]:
                print(item["document_title"], item["missing"], item["page_no"])
        else:
            print("Error:", result["error"])

    Args:
        phase3_data: Structured Phase-3 data (dict or Phase3Data)
        gateway: Optional pre-configured LLMGateway
        client: Optional mock or custom LLM client

    Returns:
        Validated Phase 4 response dictionary:
        {
          "missing_documents": [
            {
              "sr_no": 1,
              "document_title": "Discharge Summary",
              "missing": false,
              "page_no": 5
            }
          ]
        }
        Or on failure:
        {
          "error": "MALFORMED_LLM_RESPONSE",
          "message": "...",
          "details": {...}
        }
    """
    if gateway is None:
        gateway = LLMGateway(client=client)
    return gateway.detect(phase3_data)
