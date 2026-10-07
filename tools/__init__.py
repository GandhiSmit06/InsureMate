"""tools package initialization.
Exports all callable Agent tools for the InsureMate Agent Orchestrator.
"""
from tools.qwen_vl_tool import QwenVLExtractionTool
from tools.document_validation_tool import DocumentValidationTool
from tools.validity_checker_tool import ValidityCheckerTool
from tools.missing_document_tool import MissingDocumentTool

__all__ = [
    "QwenVLExtractionTool",
    "DocumentValidationTool",
    "ValidityCheckerTool",
    "MissingDocumentTool",
    "get_insuremate_tools",
]


def get_insuremate_tools():
    """
    Returns an initialized registry of all InsureMate Agent tools.
    Ready for immediate registration with LangChain, LlamaIndex, or raw OpenAI tool calls.
    """
    return [
        QwenVLExtractionTool(),
        DocumentValidationTool(),
        ValidityCheckerTool(),
        MissingDocumentTool(),
    ]
