"""tools package initialization.
Exports all callable Agent tools, Tool Registry, Tool Executor, and Claim State
for the InsureMate Agent Orchestrator (Phase 5).
"""

from tools.base_tool import AgentTool
from tools.claim_state import ClaimState
from tools.document_validation_tool import DocumentValidationTool
from tools.missing_document_tool import MissingDocumentTool
from tools.qwen_extraction_tool import DocumentExtractionTool, QwenVLExtractionTool
from tools.tool_executor import ToolErrorDict, ToolExecutor
from tools.tool_registry import ToolRegistry, create_tool_registry
from tools.validity_checker_tool import ValidityCheckerTool

__all__ = [
    "AgentTool",
    "ClaimState",
    "DocumentExtractionTool",
    "QwenVLExtractionTool",
    "DocumentValidationTool",
    "ValidityCheckerTool",
    "MissingDocumentTool",
    "ToolRegistry",
    "ToolExecutor",
    "ToolErrorDict",
    "create_tool_registry",
    "get_insuremate_tools",
]


def get_insuremate_tools():
    """
    Returns an initialized list of all InsureMate Agent tools.
    Ready for immediate registration with LangChain, LlamaIndex, or raw OpenAI tool calls.
    """
    return [
        DocumentExtractionTool(),
        DocumentValidationTool(),
        ValidityCheckerTool(),
        MissingDocumentTool(),
    ]
