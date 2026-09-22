import os
from typing import Optional
from dotenv import load_dotenv

# Load .env if present
load_dotenv()


class Phase3Config:
    """Configuration settings for Phase 3 Requirement Extraction Engine."""

    # LLM Settings
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    LLM_PROVIDER: str = os.getenv("PHASE3_LLM_PROVIDER", "auto").lower()  # "gemini", "openai", "auto", "none"
    MODEL_NAME: str = os.getenv("PHASE3_MODEL_NAME", "gemini-1.5-flash")

    # Engine Execution Mode
    # "hybrid": try LLM if available, fallback to deterministic rule engine
    # "rule_only": use deterministic rule & NLP parser only (guaranteed offline)
    # "llm_only": use LLM only (raises error if unavailable)
    ENGINE_MODE: str = os.getenv("PHASE3_ENGINE_MODE", "hybrid").lower()

    # Extraction Settings
    MAX_POLICY_PAGES: int = int(os.getenv("PHASE3_MAX_PAGES", "100"))
    MAX_TEXT_LENGTH: int = int(os.getenv("PHASE3_MAX_TEXT_LEN", "500000"))

    # Server Settings
    HOST: str = os.getenv("PHASE3_HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PHASE3_PORT", "8000"))
    DEBUG: bool = os.getenv("PHASE3_DEBUG", "false").lower() in ("true", "1", "yes")


config = Phase3Config()
