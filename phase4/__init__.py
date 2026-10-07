"""InsureMate Phase 4: Missing-Document Detection.

This package implements Phase 4 of the InsureMate insurance claim processing pipeline.
It compares policy requirements against submitted documents and detects missing documents
using Ollama with gemma3:latest through a centralized gateway abstraction.
"""
from phase4.detector import detect_missing_documents, MissingDocumentDetector
from phase4.gateway.llm_gateway import LLMGateway, llm_gateway
from phase4.config import Phase4Config, get_config
from phase4.mock import load_phase3_sample

__all__ = [
    "detect_missing_documents",
    "MissingDocumentDetector",
    "LLMGateway",
    "llm_gateway",
    "Phase4Config",
    "get_config",
    "load_phase3_sample",
]
