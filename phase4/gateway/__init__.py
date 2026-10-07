"""Gateway package for InsureMate Phase 4."""
from phase4.gateway.ollama_client import OllamaClient, OllamaClientError
from phase4.gateway.llm_gateway import LLMGateway, llm_gateway, extract_json_from_text

__all__ = [
    "OllamaClient",
    "OllamaClientError",
    "LLMGateway",
    "llm_gateway",
    "extract_json_from_text",
]
