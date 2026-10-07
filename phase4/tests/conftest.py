"""Pytest fixtures and mock client for Phase 4 testing."""
import json
import pytest
from typing import List, Optional, Any
from phase4.mock import load_phase3_sample
from phase4.gateway.ollama_client import OllamaClient


class MockLLMClient:
    """Mock LLM client allowing predictable responses and call recording."""

    def __init__(self, responses: Optional[List[Any]] = None):
        """
        Args:
            responses: List of raw string responses (or exceptions) to return sequentially.
        """
        self.responses = list(responses or [])
        self.call_count = 0
        self.recorded_calls = []

    def chat(self, messages: List[dict], model: Optional[str] = None, format_type: Optional[str] = "json") -> str:
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
def sample_phase3_data():
    """Returns the base sample Phase-3 data."""
    return load_phase3_sample()


@pytest.fixture
def all_documents_present_data():
    """Policy requirements and submitted documents where all 5 are submitted."""
    return {
        "policy_requirements": [
            {"document_title": "Discharge Summary"},
            {"document_title": "Final Hospital Bill"},
            {"document_title": "Investigation Reports"},
            {"document_title": "Prescription"},
            {"document_title": "Pharmacy Bills"}
        ],
        "submitted_documents": [
            {"document_title": "Patient Discharge Record", "page_no": 5},
            {"document_title": "Final Hospital Invoice", "page_no": 7},
            {"document_title": "Lab Investigation Reports", "page_no": 8},
            {"document_title": "Doctor Prescription", "page_no": 10},
            {"document_title": "Pharmacy Bills & Receipts", "page_no": 12}
        ]
    }


@pytest.fixture
def discharge_missing_data():
    """Submitted documents without Patient Discharge Record."""
    return {
        "policy_requirements": [
            {"document_title": "Discharge Summary"},
            {"document_title": "Final Hospital Bill"},
            {"document_title": "Investigation Reports"},
            {"document_title": "Prescription"},
            {"document_title": "Pharmacy Bills"}
        ],
        "submitted_documents": [
            # "Patient Discharge Record" is deliberately removed!
            {"document_title": "Final Hospital Invoice", "page_no": 7},
            {"document_title": "Doctor Prescription", "page_no": 10}
        ]
    }


@pytest.fixture
def multiple_missing_data():
    """Multiple documents missing: Discharge Summary, Investigation Reports, Pharmacy Bills."""
    return {
        "policy_requirements": [
            {"document_title": "Discharge Summary"},
            {"document_title": "Final Hospital Bill"},
            {"document_title": "Investigation Reports"},
            {"document_title": "Prescription"},
            {"document_title": "Pharmacy Bills"}
        ],
        "submitted_documents": [
            {"document_title": "Final Hospital Invoice", "page_no": 7},
            {"document_title": "Doctor Prescription", "page_no": 10}
        ]
    }
