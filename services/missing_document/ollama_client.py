"""services/missing_document/ollama_client.py
Local Ollama HTTP client communicating with Gemma 3.
Reads configuration from environment variables.
"""

import os
import requests
from typing import Any, Dict, List, Optional
from utils.logger import logger


class OllamaError(Exception):
    """Raised when communication with Ollama fails or times out."""
    pass


class OllamaClient:
    """HTTP client for local Ollama service."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None
    ):
        self.base_url = (
            base_url
            or os.environ.get("OLLAMA_BASE_URL")
            or "http://localhost:11434"
        ).rstrip("/")
        self.model = (
            model
            or os.environ.get("OLLAMA_MODEL")
            or "gemma3:latest"
        )
        env_timeout = os.environ.get("OLLAMA_TIMEOUT")
        self.timeout = timeout or (int(env_timeout) if env_timeout else 120)

    _cached_status: Optional[bool] = None
    _last_checked: float = 0.0

    def is_available(self, force_refresh: bool = False) -> bool:
        """Check if local Ollama daemon is reachable and responding, cached for 5s."""
        import time
        now = time.time()
        if not force_refresh and OllamaClient._cached_status is not None and (now - OllamaClient._last_checked) < 5.0:
            return OllamaClient._cached_status

        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=0.8)
            OllamaClient._cached_status = (resp.status_code == 200)
        except Exception:
            OllamaClient._cached_status = False

        OllamaClient._last_checked = now
        return OllamaClient._cached_status

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        format_type: Optional[str] = "json"
    ) -> str:
        """Send chat messages to local Ollama model and return string response."""
        target_model = model or self.model
        url = f"{self.base_url}/api/chat"
        payload: Dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "stream": False,
        }
        if format_type:
            payload["format"] = format_type

        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            message = data.get("message", {})
            content = message.get("content", "")
            return content
        except requests.exceptions.ConnectionError as e:
            raise OllamaError(
                f"Cannot connect to Ollama at {self.base_url}. Please ensure 'ollama serve' is running. Error: {e}"
            )
        except requests.exceptions.Timeout as e:
            raise OllamaError(
                f"Ollama request timed out after {self.timeout}s on model {target_model}: {e}"
            )
        except Exception as e:
            raise OllamaError(f"Ollama invocation failed: {e}")
