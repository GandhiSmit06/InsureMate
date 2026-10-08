"""tools/qwen_vl_tool.py
Legacy wrapper and alias module for DocumentExtractionTool.
Maintains backward compatibility with Phase 1-4 code while providing Phase 6 AgentTool integration.
"""

from tools.qwen_extraction_tool import DocumentExtractionTool, QwenVLExtractionTool

__all__ = ["DocumentExtractionTool", "QwenVLExtractionTool"]
