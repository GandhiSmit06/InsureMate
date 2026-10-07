"""Configuration management for InsureMate Phase 4."""
import os
from pathlib import Path
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    # Load .env file from project root if present
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()
except ImportError:
    pass


@dataclass(frozen=True)
class Phase4Config:
    """Phase 4 configuration parameters."""
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "gemma3:latest")
    ollama_timeout: int = int(os.getenv("OLLAMA_TIMEOUT", "90"))
    temperature: float = 0.0


def get_config() -> Phase4Config:
    """Retrieve current Phase 4 configuration."""
    return Phase4Config()
