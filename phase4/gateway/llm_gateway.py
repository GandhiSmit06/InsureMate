"""LLM Gateway abstraction for Phase 4 Missing-Document Detection.

Centralizes prompt construction, Ollama communication, response parsing,
strict schema validation, and exactly-once retry logic.
"""
import re
import json
import logging
from typing import Dict, Any, List, Optional, Union

from phase4.config import Phase4Config, get_config
from phase4.gateway.ollama_client import OllamaClient, OllamaClientError
from phase4.prompts.prompt_builder import build_detection_prompt, build_retry_prompt
from phase4.schemas.input_schema import Phase3Data, PolicyRequirement, SubmittedDocument
from phase4.schemas.output_schema import (
    MissingDocumentsResponse,
    Phase4ValidationError,
    validate_output_against_requirements,
)

logger = logging.getLogger(__name__)


def extract_json_from_text(raw_text: str) -> Dict[str, Any]:
    """Extract and parse JSON from raw LLM output.

    Handles:
    - Pure JSON
    - Markdown fenced JSON blocks (```json ... ```)
    - Surrounding conversational text
    """
    cleaned = raw_text.strip()
    if not cleaned:
        raise Phase4ValidationError("LLM returned empty response.")

    # 1. Try direct parse
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # 2. Try extracting from markdown fence ```json ... ``` or ``` ... ```
    fence_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    match = re.search(fence_pattern, cleaned)
    if match:
        fence_content = match.group(1).strip()
        try:
            data = json.loads(fence_content)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    # 3. Try finding outermost matching braces { ... }
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        substring = cleaned[first_brace : last_brace + 1]
        try:
            data = json.loads(substring)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    raise Phase4ValidationError(
        f"Failed to extract valid JSON object from LLM response: {raw_text[:200]}..."
    )


class LLMGateway:
    """Centralized LLM gateway for Phase 4 missing-document detection."""

    def __init__(
        self,
        client: Optional[Any] = None,
        config: Optional[Phase4Config] = None
    ):
        self.config = config or get_config()
        self.client = client or OllamaClient(config=self.config)

    def detect(self, phase3_data: Union[Dict[str, Any], Phase3Data]) -> Dict[str, Any]:
        """Execute missing-document detection pipeline.

        Workflow:
        1. Parse and validate input Phase-3 data.
        2. Build detection prompt.
        3. Send to Ollama (gemma3:latest).
        4. Parse and validate output.
        5. If invalid, retry exactly once with error feedback.
        6. Validate second response.
        7. If still invalid, return structured error.

        Args:
            phase3_data: Structured Phase-3 data as dict or Phase3Data instance.

        Returns:
            Dict matching required schema:
            {"missing_documents": [...]}
            OR structured error dict if both attempts fail:
            {"error": "MALFORMED_LLM_RESPONSE", "message": "...", "details": {...}}
        """
        # Validate input structure
        if isinstance(phase3_data, dict):
            validated_input = Phase3Data.model_validate(phase3_data)
        elif isinstance(phase3_data, Phase3Data):
            validated_input = phase3_data
        else:
            raise TypeError(
                f"phase3_data must be a dict or Phase3Data instance, got {type(phase3_data).__name__}"
            )

        policy_reqs = [
            {"document_title": req.document_title}
            for req in validated_input.policy_requirements
        ]
        submitted_docs = [
            {"document_title": doc.document_title, "page_no": doc.page_no}
            for doc in validated_input.submitted_documents
        ]
        required_titles = [req.document_title for req in validated_input.policy_requirements]

        # Build initial prompt
        initial_prompt = build_detection_prompt(
            policy_requirements=policy_reqs,
            submitted_documents=submitted_docs
        )

        max_attempts = 2
        last_error = ""
        last_raw_response = ""

        current_prompt = initial_prompt

        for attempt in range(1, max_attempts + 1):
            logger.info("Sending request to LLM (Attempt %d/%d)...", attempt, max_attempts)

            try:
                raw_response = self.client.chat(
                    messages=[{"role": "user", "content": current_prompt}],
                    format_type="json"
                )
            except Exception as e:
                logger.error("LLM client communication error on attempt %d: %s", attempt, e)
                last_error = f"LLM communication error: {e}"
                last_raw_response = ""
                # Communication error on Ollama request
                if attempt < max_attempts:
                    # Retry communication once
                    continue
                else:
                    return {
                        "error": "LLM_COMMUNICATION_ERROR",
                        "message": str(e),
                        "details": {
                            "attempts": attempt,
                            "last_error": last_error,
                        }
                    }

            last_raw_response = raw_response

            # Attempt JSON parse and schema validation
            try:
                parsed_json = extract_json_from_text(raw_response)
                validated_resp = validate_output_against_requirements(
                    parsed_json,
                    required_titles=required_titles
                )
                # Success!
                return {
                    "missing_documents": [
                        item.model_dump()
                        for item in validated_resp.missing_documents
                    ]
                }
            except (Phase4ValidationError, Exception) as err:
                last_error = str(err)
                logger.warning(
                    "Validation failed on attempt %d/%d: %s",
                    attempt,
                    max_attempts,
                    last_error
                )

                if attempt < max_attempts:
                    # Build retry prompt with error feedback
                    current_prompt = build_retry_prompt(
                        original_prompt=initial_prompt,
                        invalid_response=raw_response,
                        error_reason=last_error
                    )

        # Both attempts exhausted and failed
        return {
            "error": "MALFORMED_LLM_RESPONSE",
            "message": f"LLM response failed validation after {max_attempts} attempts: {last_error}",
            "details": {
                "attempts": max_attempts,
                "last_error": last_error,
                "last_raw_response": last_raw_response
            }
        }


def llm_gateway(
    phase3_data: Union[Dict[str, Any], Phase3Data],
    client: Optional[Any] = None,
    config: Optional[Phase4Config] = None
) -> Dict[str, Any]:
    """Functional interface for the LLM gateway.

    result = llm_gateway(phase3_data)
    """
    gateway = LLMGateway(client=client, config=config)
    return gateway.detect(phase3_data)
