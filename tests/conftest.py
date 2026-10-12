import json
from typing import Any, Dict, List, Optional, Union
import pytest
from services.missing_document.ollama_client import OllamaClient


class MockLLMClient:
    """Mock LLM client allowing sequential scripted responses, call tracking, and planner decoupling."""

    def __init__(
        self,
        responses: Optional[List[Any]] = None,
        planner_response: Optional[Union[str, Dict[str, Any]]] = None
    ):
        self.responses = list(responses or [])
        self.planner_response = json.dumps(planner_response) if isinstance(planner_response, dict) else planner_response
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
        # Check if this is a planner call and we have a dedicated planner response
        content_text = " ".join(m.get("content", "") for m in messages).lower()
        if ("insurance workflow planner" in content_text or "planning agent" in content_text or "insuremate planning" in content_text) and self.planner_response is not None:
            return self.planner_response

        if not self.responses:
            raise RuntimeError(f"MockLLMClient: No more responses configured. Call count: {self.call_count}")
        resp = self.responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        if isinstance(resp, dict):
            return json.dumps(resp)
        return resp

    def is_available(self) -> bool:
        return True


@pytest.fixture
def mock_llm_client():
    return MockLLMClient()

