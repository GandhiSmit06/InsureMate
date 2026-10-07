"""Ollama API client implementation for Phase 4."""
import json
import logging
from typing import List, Dict, Any, Optional
import requests

from phase4.config import Phase4Config, get_config

logger = logging.getLogger(__name__)


class OllamaClientError(Exception):
    """Exception raised when communication with Ollama fails."""
    pass


class OllamaClient:
    """HTTP client communicating with local Ollama service."""

    def __init__(self, config: Optional[Phase4Config] = None):
        self.config = config or get_config()
        self.base_url = self.config.ollama_base_url
        self.model = self.config.ollama_model
        self.timeout = self.config.ollama_timeout
        self.temperature = self.config.temperature

    def is_available(self) -> bool:
        """Check if local Ollama service is reachable and responsive."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        format_type: Optional[str] = "json"
    ) -> str:
        """Send chat request to Ollama /api/chat endpoint.

        Args:
            messages: List of message dicts: [{'role': 'user', 'content': '...'}]
            model: Model name override (defaults to config.ollama_model)
            format_type: Response format constraint ('json' by default)

        Returns:
            The raw text content from the assistant message.

        Raises:
            OllamaClientError: If the HTTP request fails or Ollama returns an error.
        """
        target_model = model or self.model
        url = f"{self.base_url}/api/chat"

        payload: Dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.temperature,
            }
        }
        if format_type:
            payload["format"] = format_type

        try:
            response = requests.post(
                url,
                json=payload,
                timeout=self.timeout
            )
        except requests.exceptions.ConnectionError as e:
            raise OllamaClientError(
                f"Failed to connect to Ollama at {self.base_url}. Ensure Ollama is running: {e}"
            ) from e
        except requests.exceptions.Timeout as e:
            raise OllamaClientError(
                f"Request to Ollama timed out after {self.timeout}s: {e}"
            ) from e
        except requests.exceptions.RequestException as e:
            raise OllamaClientError(f"HTTP request to Ollama failed: {e}") from e

        if response.status_code != 200:
            raise OllamaClientError(
                f"Ollama returned HTTP {response.status_code}: {response.text}"
            )

        try:
            data = response.json()
            message = data.get("message", {})
            content = message.get("content", "")
            return content
        except Exception as e:
            raise OllamaClientError(
                f"Failed to parse Ollama response body as JSON: {e}"
            ) from e
