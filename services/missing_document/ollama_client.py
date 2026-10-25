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
        raw_url = (
            base_url
            or os.environ.get("OLLAMA_BASE_URL")
            or "http://127.0.0.1:11434"
        ).rstrip("/")
        # Avoid Windows localhost IPv6 resolution delay (which causes 2s latency and timeouts)
        if "localhost:11434" in raw_url:
            raw_url = raw_url.replace("localhost:11434", "127.0.0.1:11434")
        self.base_url = raw_url
        self.model = (
            model
            or os.environ.get("OLLAMA_MODEL")
            or "gemma3:latest"
        )
        env_timeout = os.environ.get("OLLAMA_TIMEOUT")
        self.timeout = timeout or (int(env_timeout) if env_timeout else 120)

    _cached_status: Optional[bool] = None
    _last_checked: float = 0.0
    use_openai_fallback: bool = False

    def is_available(self, force_refresh: bool = False) -> bool:
        """Check if local Ollama daemon or OpenAI fallback is reachable and responding, cached for 5s."""
        import time
        now = time.time()
        if not force_refresh and OllamaClient._cached_status is not None and (now - OllamaClient._last_checked) < 5.0:
            return OllamaClient._cached_status

        is_avail = False
        try:
            # Check 127.0.0.1 directly to avoid DNS delays; use 3.0s timeout
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3.0)
            if resp.status_code == 200:
                is_avail = True
                data = resp.json()
                models = [m.get("name") for m in data.get("models", []) if m.get("name")]
                # If target model is not found in installed models list, select first chat-compatible model
                if models and self.model not in models:
                    preferred = ["gemma3", "qwen2.5", "llama3.2", "gemma2", "gemma", "mistral", "llama3", "qwen"]
                    chosen = None
                    for pref in preferred:
                        for m in models:
                            if pref in m.lower():
                                chosen = m
                                break
                        if chosen:
                            break
                    if not chosen:
                        chosen = models[0]
                    logger.info(
                        f"[OLLAMA] Target model '{self.model}' not found in installed models. Auto-selected fallback: '{chosen}'"
                    )
                    self.model = chosen
        except Exception:
            is_avail = False

        # Support optional fallback to OpenAI-compatible endpoints if Ollama is unreachable
        if not is_avail and os.environ.get("OPENAI_API_KEY"):
            is_avail = True
            self.use_openai_fallback = True
        else:
            self.use_openai_fallback = False

        OllamaClient._cached_status = is_avail
        OllamaClient._last_checked = now
        return OllamaClient._cached_status

    def _call_openai_fallback(
        self,
        messages: List[Dict[str, str]],
        format_type: Optional[str] = "json"
    ) -> str:
        """Fallback to OpenAI-compatible API endpoint when Ollama is unreachable."""
        openai_key = os.environ.get("OPENAI_API_KEY", "")
        openai_base = (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        openai_model = os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
        headers = {
            "Authorization": f"Bearer {openai_key}",
            "Content-Type": "application/json"
        }
        payload: Dict[str, Any] = {
            "model": openai_model,
            "messages": messages,
            "temperature": 0.1
        }
        if format_type == "json":
            payload["response_format"] = {"type": "json_object"}
        try:
            resp = requests.post(f"{openai_base}/chat/completions", headers=headers, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            raise OllamaError(f"OpenAI fallback invocation failed: {e}")

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        format_type: Optional[str] = "json"
    ) -> str:
        """Send chat messages to local Ollama model (or OpenAI fallback) and return string response."""
        if getattr(self, "use_openai_fallback", False):
            return self._call_openai_fallback(messages, format_type=format_type)

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
            if os.environ.get("OPENAI_API_KEY"):
                logger.info("[OLLAMA] Ollama unreachable, switching to OpenAI-compatible fallback.")
                return self._call_openai_fallback(messages, format_type=format_type)
            raise OllamaError(
                f"Cannot connect to Ollama at {self.base_url}. Please ensure 'ollama serve' is running. Error: {e}"
            )
        except requests.exceptions.Timeout as e:
            raise OllamaError(
                f"Ollama request timed out after {self.timeout}s on model {target_model}: {e}"
            )
        except Exception as e:
            raise OllamaError(f"Ollama invocation failed: {e}")
