"""
tools/qwen_vl_tool.py
Agent-ready callable tool wrapping Qwen-VL document processing & extraction.
Designed for registration with future Phase 4 InsureMate Agent Orchestrator.
"""

from typing import Any, Dict, List, Optional, Union
from pathlib import Path

from services.qwen_vl.extractor import QwenVLExtractor
from utils.config import QwenConfig
from utils.logger import logger


class QwenVLExtractionTool:
    """
    Callable Agent Tool: Qwen-VL Document Understanding.
    Converts multi-page PDFs to in-memory images and extracts structured
    claim entities while strictly preserving 1-indexed page numbers.
    """

    name: str = "qwen_vl_extraction_tool"
    description: str = (
        "Extracts structured insurance claim entities and classifications from PDF documents "
        "page-by-page using Qwen-VL vision understanding, preserving 1-indexed page numbers."
    )

    def __init__(self, config: Optional[QwenConfig] = None, offline_mode: Optional[bool] = None):
        self.extractor = QwenVLExtractor(config=config, offline_mode=offline_mode)

    @property
    def schema(self) -> Dict[str, Any]:
        """JSON schema definition for LLM tool calling registration."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pdf_path": {
                            "type": "string",
                            "description": "Absolute or relative filesystem path to the PDF document.",
                        },
                        "max_pages": {
                            "type": "integer",
                            "description": "Optional upper limit on page count to process.",
                        },
                    },
                    "required": ["pdf_path"],
                },
            },
        }

    def run(
        self,
        pdf_path: Union[str, Path],
        max_pages: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Execute tool call.

        Args:
            pdf_path: Path to PDF.
            max_pages: Optional maximum pages to extract.

        Returns:
            Standardized agent observation dictionary.
        """
        try:
            results = self.extractor.extract_document(pdf_path, max_pages=max_pages)
            return {
                "status": "success",
                "tool": self.name,
                "total_pages": len(results),
                "extracted_documents": results,
                "error": None,
            }
        except Exception as e:
            logger.error(f"Tool execution failed in {self.name}: {e}")
            return {
                "status": "error",
                "tool": self.name,
                "total_pages": 0,
                "extracted_documents": [],
                "error": str(e),
            }

    def __call__(self, *args, **kwargs) -> Dict[str, Any]:
        return self.run(*args, **kwargs)
