"""services/missing_document/llm_gateway.py
Centralized LLM Gateway for Phase 4.
Coordinates communication with Gemma 3 via OllamaClient, robust JSON parsing,
and exactly-once retry without storing hardcoded document requirements.
"""

import json
import re
from typing import Any, Dict, List, Optional
from services.missing_document.ollama_client import OllamaClient, OllamaError
from services.missing_document.prompt_builder import (
    SYSTEM_MATCHING_PROMPT,
    SYSTEM_REQUIREMENT_EXTRACTION_PROMPT,
    build_requirement_extraction_messages,
    build_requirement_extraction_prompt,
    build_matching_messages,
    build_matching_prompt,
    build_retry_prompt,
)
from services.missing_document.schemas import (
    MissingDocumentResponse,
    Phase4ValidationError,
    RequiredDocumentDefinition,
    validate_detection_output,
)
from utils.logger import logger


def extract_json_from_text(raw_text: str) -> Dict[str, Any]:
    """Extract and parse a JSON object from raw LLM output."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if match:
            cleaned = match.group(1).strip()

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
        if isinstance(data, list):
            return {"document_results": data}
    except json.JSONDecodeError:
        pass

    # Regex substring match for outermost balanced braces
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    # Regex array fallback
    arr_match = re.search(r"\[[\s\S]*\]", cleaned)
    if arr_match:
        try:
            arr_data = json.loads(arr_match.group(0))
            if isinstance(arr_data, list):
                return {"document_results": arr_data}
        except json.JSONDecodeError:
            pass

    raise Phase4ValidationError(f"Could not parse valid JSON from LLM response: {raw_text[:200]}")


class LLMGateway:
    """Central gateway for executing Phase 4 LLM reasoning tasks."""

    def __init__(self, client: Optional[OllamaClient] = None):
        self.client = client or OllamaClient()

    def extract_policy_requirements(
        self,
        policy_documents: List[Dict[str, Any]],
        conditions: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Call #1: Use Gemma 3 to dynamically determine required documents from policy evidence."""
        messages = build_requirement_extraction_messages(
            policy_documents=policy_documents,
            conditions=conditions
        )
        logger.missing_doc("Calling LLM Gateway for dynamic requirement extraction...")
        raw_response = self.client.chat(
            messages=messages,
            format_type="json"
        )

        try:
            parsed = extract_json_from_text(raw_response)
        except Exception as e:
            # Retry once on malformed requirement JSON
            retry_prompt = build_retry_prompt(messages[1]["content"], raw_response, str(e))
            raw_response = self.client.chat(
                messages=[
                    messages[0],
                    messages[1],
                    {"role": "assistant", "content": raw_response},
                    {"role": "user", "content": retry_prompt}
                ],
                format_type="json"
            )
            parsed = extract_json_from_text(raw_response)

        if isinstance(parsed, list):
            raw_list = parsed
        elif isinstance(parsed, dict):
            raw_list = (
                parsed.get("required_documents")
                or parsed.get("policy_requirements")
                or parsed.get("document_results")
                or []
            )
        else:
            raw_list = []
        requirements: List[Dict[str, Any]] = []
        for idx, item in enumerate(raw_list, start=1):
            if isinstance(item, str):
                requirements.append({
                    "sr_no": idx,
                    "document_title": item.strip(),
                    "source": "policy",
                    "reason": "Explicitly stated in policy content"
                })
            elif isinstance(item, dict) and item.get("document_title"):
                requirements.append({
                    "sr_no": idx,
                    "document_title": item["document_title"].strip(),
                    "source": item.get("source", "policy"),
                    "reason": item.get("reason", "")
                })

        return requirements

    def match_submitted_documents(
        self,
        required_documents: List[Dict[str, Any]],
        submitted_documents: List[Dict[str, Any]],
        phase2_notes: Optional[List[Dict[str, Any]]] = None,
        phase3_context: Optional[Dict[str, Any]] = None,
        valid_submitted_pages: Optional[List[int]] = None
    ) -> MissingDocumentResponse:
        """Call #2: Use Gemma 3 to semantically match submitted documents against requirements."""
        messages = build_matching_messages(
            required_documents=required_documents,
            submitted_documents=submitted_documents,
            phase2_validation_notes=phase2_notes,
            phase3_validity_context=phase3_context
        )

        # Attempt 1
        logger.missing_doc("Calling LLM Gateway for semantic document matching (Attempt 1/2)...")
        raw_resp = self.client.chat(
            messages=messages,
            format_type="json"
        )

        try:
            parsed = extract_json_from_text(raw_resp)
            parsed["required_documents"] = required_documents
            return validate_detection_output(parsed, valid_submitted_pages=valid_submitted_pages)
        except Exception as first_error:
            logger.missing_doc(f"Attempt 1 validation error: {first_error}. Triggering exactly-once retry...")

            # Attempt 2 (Retry exactly once)
            retry_content = f"""CRITICAL: Your previous response was INVALID and failed strict schema validation.

VALIDATION ERROR:
{first_error}

PREVIOUS INVALID RESPONSE:
{raw_resp}

CORRECTION INSTRUCTIONS:
- Fix the validation error above.
- You MUST output a JSON object containing the root key "document_results".
- Ensure every item has a sequential sr_no starting from 1.
- If missing is false, page_number MUST be an integer taken directly from submitted_documents and matched_submitted_document must be non-null.
- If missing is true, page_number MUST be null and matched_submitted_document must be null.
- Output ONLY valid JSON:"""

            retry_messages = [
                messages[0],
                messages[1],
                {"role": "assistant", "content": raw_resp},
                {"role": "user", "content": retry_content}
            ]

            raw_retry_resp = self.client.chat(
                messages=retry_messages,
                format_type="json"
            )

            try:
                parsed_retry = extract_json_from_text(raw_retry_resp)
                parsed_retry["required_documents"] = required_documents
                return validate_detection_output(parsed_retry, valid_submitted_pages=valid_submitted_pages)
            except Exception as second_error:
                logger.error(f"Attempt 2 retry failed validation: {second_error}")
                req_defs = [
                    RequiredDocumentDefinition(
                        sr_no=r.get("sr_no", idx),
                        document_title=r.get("document_title", ""),
                        source=r.get("source", "policy"),
                        reason=r.get("reason", "")
                    ) if isinstance(r, dict) else r
                    for idx, r in enumerate(required_documents, start=1)
                ]
                # Structured error on second failure
                return MissingDocumentResponse(
                    status="error",
                    tool="missing_document_tool",
                    required_documents=req_defs,
                    document_results=[],
                    reason=f"LLM output failed validation after retry: {second_error}",
                    error={
                        "attempt_1_error": str(first_error),
                        "attempt_2_error": str(second_error),
                        "raw_response": raw_retry_resp
                    }
                )
