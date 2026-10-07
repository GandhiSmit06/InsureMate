"""
utils/config.py
Configuration loader and validator for Qwen-VL in the InsureMate project.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Automatically load environment variables from root .env file if available
_ROOT_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = _ROOT_DIR / ".env"
if _ENV_FILE.exists():
    load_dotenv(dotenv_path=_ENV_FILE)
else:
    load_dotenv()


class ConfigurationError(Exception):
    """Raised when required configuration or API credentials are missing or invalid."""
    pass


@dataclass
class QwenConfig:
    """Configuration settings for Qwen-VL client."""
    api_key: str
    base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    model_name: str = "qwen-vl-max"
    max_tokens: int = 2048
    temperature: float = 0.1

    @classmethod
    def from_env(cls, env_path: Optional[str] = None) -> "QwenConfig":
        """
        Load configuration from environment variables or .env file.
        Checks QWEN_API_KEY, DASHSCOPE_API_KEY, and OPENROUTER_API_KEY.
        """
        if env_path:
            load_dotenv(dotenv_path=env_path, override=True)
        elif _ENV_FILE.exists():
            load_dotenv(dotenv_path=_ENV_FILE)
        else:
            load_dotenv()

        api_key = (
            os.getenv("QWEN_API_KEY")
            or os.getenv("DASHSCOPE_API_KEY")
            or os.getenv("OPENROUTER_API_KEY")
            or ""
        ).strip()

        base_url = os.getenv(
            "QWEN_BASE_URL",
            "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
        ).strip()

        model_name = os.getenv("QWEN_MODEL_NAME", "qwen-vl-max").strip()

        try:
            max_tokens = int(os.getenv("QWEN_MAX_TOKENS", "2048"))
        except ValueError:
            max_tokens = 2048

        try:
            temperature = float(os.getenv("QWEN_TEMPERATURE", "0.1"))
        except ValueError:
            temperature = 0.1

        return cls(
            api_key=api_key,
            base_url=base_url,
            model_name=model_name,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def validate(self) -> None:
        """
        Validate configuration parameters.
        Raises ConfigurationError if mandatory settings are missing.
        """
        if not self.api_key:
            raise ConfigurationError(
                "Missing Qwen-VL API Key!\n"
                "Please configure 'QWEN_API_KEY' in your .env file or environment variables.\n"
                "See .env.example for template settings."
            )

        if not self.base_url.startswith(("http://", "https://")):
            raise ConfigurationError(
                f"Invalid QWEN_BASE_URL: '{self.base_url}'. Base URL must start with http:// or https://"
            )

        if not self.model_name:
            raise ConfigurationError(
                "Model name cannot be empty. Please set QWEN_MODEL_NAME (e.g. 'qwen-vl-max')."
            )
