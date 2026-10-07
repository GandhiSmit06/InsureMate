"""tests/conftest.py
Global fixtures and mock LLM client for InsureMate tests.
"""

from typing import Any, Dict, List, Optional
import pytest
from services.missing_document.ollama_client import OllamaClient


class MockLLMClient:
    """Mock LLM client allowing sequential scripted responses and call tracking."""

    def __init__(self, responses: Optional[List[Any]] = None):
        self.responses = list(responses or [])
        self.call_count = 0
        self.recorded_calls = []

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        format_type: Optional[str] = "json"
    ) -> str:
        self.call_count += 1
        self.recorded_calls.append({
            "messages": messages,
            "model": model,
            "format_type": format_type
        })
        if not self.responses:
            raise RuntimeError("MockLLMClient: No more responses configured.")
        resp = self.responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp

    def is_available(self) -> bool:
        return True


@pytest.fixture
def mock_llm_client():
    return MockLLMClient()
