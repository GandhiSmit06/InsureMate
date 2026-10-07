"""Integration tests for Phase 4 using live Ollama service and gemma3:latest.

These tests run against the live local Ollama service (http://localhost:11434).
They are automatically skipped if Ollama is not reachable or the model is not present,
ensuring unit test suites remain fast and self-contained.
"""
import pytest
from phase4.config import get_config
from phase4.gateway.ollama_client import OllamaClient
from phase4.detector import detect_missing_documents
from phase4.mock import load_phase3_sample


def is_ollama_ready() -> bool:
    """Check if local Ollama is reachable and gemma3 is available."""
    client = OllamaClient()
    return client.is_available()


@pytest.mark.integration
class TestLiveOllamaIntegration:
    """Integration test suite executing against local Ollama with gemma3:latest."""

    @pytest.fixture(autouse=True)
    def check_ollama(self):
        if not is_ollama_ready():
            pytest.skip("Local Ollama service (http://localhost:11434) is not available.")

    def test_live_gemma3_sample_detection(self):
        """Test live gemma3 inference with phase4/mock/phase3_sample.json."""
        sample_data = load_phase3_sample()
        result = detect_missing_documents(sample_data)

        assert "missing_documents" in result, f"Expected successful detection, got: {result}"
        docs = {d["document_title"]: d for d in result["missing_documents"]}

        # Check required document count
        assert len(result["missing_documents"]) == len(sample_data["policy_requirements"])

        # Semantic matching checks:
        # 1. "Discharge Summary" <-> "Patient Discharge Record" (page 5)
        assert docs["Discharge Summary"]["missing"] is False
        assert docs["Discharge Summary"]["page_no"] == 5

        # 2. "Final Hospital Bill" <-> "Final Hospital Invoice" (page 7)
        assert docs["Final Hospital Bill"]["missing"] is False
        assert docs["Final Hospital Bill"]["page_no"] == 7

        # 3. "Prescription" <-> "Doctor Prescription" (page 10)
        assert docs["Prescription"]["missing"] is False
        assert docs["Prescription"]["page_no"] == 10

        # 4. "Investigation Reports" - not submitted
        assert docs["Investigation Reports"]["missing"] is True
        assert docs["Investigation Reports"]["page_no"] is None

        # 5. "Pharmacy Bills" - not submitted
        assert docs["Pharmacy Bills"]["missing"] is True
        assert docs["Pharmacy Bills"]["page_no"] == None

    def test_live_gemma3_discharge_document_missing(self):
        """Test live gemma3 when Patient Discharge Record is deliberately removed."""
        sample_data = load_phase3_sample()
        # Remove Patient Discharge Record
        sample_data["submitted_documents"] = [
            doc for doc in sample_data["submitted_documents"]
            if "discharge" not in doc["document_title"].lower()
        ]

        result = detect_missing_documents(sample_data)

        assert "missing_documents" in result, f"Expected successful detection, got: {result}"
        docs = {d["document_title"]: d for d in result["missing_documents"]}

        discharge = docs["Discharge Summary"]
        assert discharge["missing"] is True, "Discharge Summary must be flagged missing!"
        assert discharge["page_no"] is None
