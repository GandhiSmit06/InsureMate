"""tests/test_extraction_tool.py
Unit tests for Phase 6 DocumentExtractionTool (Qwen-VL adapter).
Tests:
- Tool schema definition
- Execution with single pdf_path
- Execution with documents list
- Backward compatibility with legacy run()
- Error handling on missing/non-existent PDF
- Backward-compatible alias QwenVLExtractionTool
"""

import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.qwen_extraction_tool import DocumentExtractionTool, QwenVLExtractionTool


@pytest.fixture
def extraction_tool():
    # Use offline mode for deterministic unit testing without remote API dependencies
    return DocumentExtractionTool(offline_mode=True)


def test_extraction_tool_schema(extraction_tool):
    """Verify tool exposes proper schema for agent discovery."""
    tool = extraction_tool
    assert tool.name == "document_extraction_tool"
    assert "Extracts structured insurance claim" in tool.description
    assert tool.schema["type"] == "function"
    assert tool.schema["function"]["name"] == "document_extraction_tool"


def test_extraction_tool_execute_single_pdf(extraction_tool):
    """Test standard execute() with single pdf_path."""
    tool = extraction_tool
    pdf_path = ROOT_DIR / "policy_A.pdf"

    payload = {
        "claim_id": "CLM-P6-001",
        "pdf_path": str(pdf_path),
        "max_pages": 1,
    }
    result = tool.execute(payload)

    assert result["success"] is True
    assert result["claim_id"] == "CLM-P6-001"
    assert result["extracted_data"]["total_pages"] == 1
    assert len(result["documents_processed"]) == 1
    assert len(result["extracted_data"]["extracted_documents"]) == 1
    assert result["status"] == "success"


def test_extraction_tool_execute_documents_list(extraction_tool):
    """Test standard execute() with multiple documents in 'documents' list."""
    tool = extraction_tool
    docs = [str(ROOT_DIR / "policy_A.pdf"), str(ROOT_DIR / "claim_A.pdf")]

    payload = {
        "claim_id": "CLM-P6-002",
        "documents": docs,
        "max_pages": 1,
    }
    result = tool.execute(payload)

    assert result["success"] is True
    assert result["claim_id"] == "CLM-P6-002"
    assert len(result["documents_processed"]) == 2
    assert result["extracted_data"]["total_pages"] >= 2


def test_extraction_tool_missing_input(extraction_tool):
    """Calling execute with no document paths returns controlled error."""
    tool = extraction_tool
    result = tool.execute({"claim_id": "CLM-EMPTY"})

    assert result["success"] is False
    assert len(result["errors"]) > 0
    assert "No document paths provided" in result["errors"][0]


def test_extraction_tool_non_existent_file(extraction_tool):
    """Calling execute with non-existent file path handles error gracefully."""
    tool = extraction_tool
    result = tool.execute({"pdf_path": "non_existent_file_xyz.pdf"})

    assert result["success"] is False
    assert len(result["errors"]) > 0


def test_extraction_tool_legacy_run(extraction_tool):
    """Verify legacy run() method remains fully functional."""
    tool = extraction_tool
    pdf_path = ROOT_DIR / "policy_A.pdf"

    res = tool.run(pdf_path, max_pages=1)
    assert res["status"] == "success"
    assert res["total_pages"] == 1
    assert len(res["extracted_documents"]) == 1


def test_alias_compatibility():
    """Verify QwenVLExtractionTool is identical alias to DocumentExtractionTool."""
    assert QwenVLExtractionTool is DocumentExtractionTool
    legacy_tool = QwenVLExtractionTool(offline_mode=True)
    assert isinstance(legacy_tool, DocumentExtractionTool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
