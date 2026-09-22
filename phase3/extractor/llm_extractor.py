import json
import logging
import re
from typing import List, Optional, Dict, Any
import httpx

from phase3.schema.models import PageText, RequirementItem, Category, Priority
from phase3.extractor.base import BaseExtractor
from phase3.prompt.system_prompt import (
    PHASE3_SYSTEM_PROMPT,
    PHASE3_USER_PROMPT_TEMPLATE,
)
from phase3.config import config

logger = logging.getLogger("phase3.extractor.llm")


class LLMExtractor(BaseExtractor):
    """LLM-based extractor that uses structured JSON output to extract claim requirements."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.provider = (provider or config.LLM_PROVIDER).lower()
        self.model_name = model_name or config.MODEL_NAME

        # Resolve API key based on provider or auto-detection
        if self.provider == "gemini" or (self.provider == "auto" and config.GEMINI_API_KEY):
            self.provider = "gemini"
            self.api_key = api_key or config.GEMINI_API_KEY
            if not self.model_name or "gemini" not in self.model_name:
                self.model_name = "gemini-1.5-flash"
        elif self.provider == "openai" or (self.provider == "auto" and config.OPENAI_API_KEY):
            self.provider = "openai"
            self.api_key = api_key or config.OPENAI_API_KEY
            if not self.model_name or "gpt" not in self.model_name:
                self.model_name = "gpt-4o-mini"
        else:
            self.api_key = api_key or config.GEMINI_API_KEY or config.OPENAI_API_KEY

    def is_available(self) -> bool:
        """Check if an LLM API key and provider are configured."""
        return bool(self.api_key)

    def extract(
        self,
        pages: List[PageText],
        claim_type: Optional[str] = None,
    ) -> List[RequirementItem]:
        """Extract requirements using the configured LLM."""
        if not self.is_available():
            raise RuntimeError("LLM API key is not configured.")

        # Build document text with page markers
        formatted_pages = []
        for page in pages:
            formatted_pages.append(f"--- Page {page.page_number} ---\n{page.text}")
        doc_content = "\n\n".join(formatted_pages)

        user_prompt = PHASE3_USER_PROMPT_TEMPLATE.format(
            claim_type=claim_type or "hospitalization",
            document_pages=doc_content[:config.MAX_TEXT_LENGTH],
        )

        raw_json = self._call_llm(user_prompt)
        return self._parse_llm_json(raw_json)

    def _call_llm(self, user_prompt: str) -> str:
        """Call either Gemini or OpenAI compatible REST API."""
        if self.provider == "gemini":
            return self._call_gemini_api(user_prompt)
        elif self.provider == "openai":
            return self._call_openai_api(user_prompt)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def _call_gemini_api(self, user_prompt: str) -> str:
        """Invoke Gemini API via HTTP directly (using httpx)."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": PHASE3_SYSTEM_PROMPT + "\n\n" + user_prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "response_mime_type": "application/json",
            },
        }

        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as e:
            logger.error(f"Malformed Gemini response: {data}")
            raise RuntimeError(f"Unexpected response format from Gemini API: {e}")

    def _call_openai_api(self, user_prompt: str) -> str:
        """Invoke OpenAI-compatible chat completion endpoint."""
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": PHASE3_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }

        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            logger.error(f"Malformed OpenAI response: {data}")
            raise RuntimeError(f"Unexpected response format from OpenAI API: {e}")

    def _parse_llm_json(self, raw_content: str) -> List[RequirementItem]:
        """Safely parse LLM JSON string into List[RequirementItem]."""
        clean_text = raw_content.strip()
        # Remove potential markdown code fences ```json ... ```
        if clean_text.startswith("```"):
            clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text)
            clean_text = re.sub(r"\s*```$", "", clean_text)

        parsed = json.loads(clean_text)
        req_list = parsed.get("requirements", [])
        if not isinstance(req_list, list):
            req_list = [req_list]

        items: List[RequirementItem] = []
        for i, item_data in enumerate(req_list):
            if not isinstance(item_data, dict):
                continue

            # Ensure valid requirement_id
            req_id = item_data.get("requirement_id") or f"REQ-{i+1:03d}"

            # Ensure valid category
            cat_raw = str(item_data.get("category", "DOCUMENT")).upper()
            try:
                category = Category(cat_raw)
            except ValueError:
                category = Category.DOCUMENT

            # Ensure valid priority
            prio_raw = str(item_data.get("priority", "HIGH")).upper()
            try:
                priority = Priority(prio_raw)
            except ValueError:
                priority = Priority.HIGH

            req = RequirementItem(
                requirement_id=req_id,
                category=category,
                name=str(item_data.get("name", f"Requirement {i+1}")),
                description=str(item_data.get("description", "")),
                mandatory=bool(item_data.get("mandatory", True)),
                priority=priority,
                applies_when=item_data.get("applies_when"),
                condition=item_data.get("condition"),
                deadline=item_data.get("deadline"),
                evidence_type=item_data.get("evidence_type"),
                required_information=list(item_data.get("required_information") or []),
                source_clause=item_data.get("source_clause"),
                source_page=item_data.get("source_page"),
            )
            items.append(req)

        return items
