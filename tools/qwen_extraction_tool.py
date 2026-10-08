"""tools/qwen_extraction_tool.py
Agent-ready callable tool wrapping Qwen-VL document processing & extraction.
Adheres to the Phase 6 AgentTool interface for integration with Phase 5 Agent Orchestrator.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from services.qwen_vl.extractor import QwenVLExtractor
from tools.base_tool import AgentTool
from utils.config import QwenConfig
from utils.logger import logger


class DocumentExtractionTool(AgentTool):
    """
    Callable Agent Tool: Document Extraction (Qwen-VL).
    Extracts structured insurance claim entities and classifications from PDF documents
    page-by-page using Qwen-VL vision understanding, strictly preserving 1-indexed page numbers.
    """

    name: str = "document_extraction_tool"
    description: str = (
        "Extracts structured insurance claim entities, policy clauses, and classifications "
        "from uploaded PDF documents page-by-page using Qwen-VL vision understanding, preserving 1-indexed page numbers."
    )

    def __init__(
        self,
        config: Optional[QwenConfig] = None,
        offline_mode: Optional[bool] = None,
    ):
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
                        "claim_id": {
                            "type": "string",
                            "description": "Unique identifier for the claim (optional).",
                        },
                        "documents": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of filesystem paths to insurance/claim PDF documents.",
                        },
                        "pdf_path": {
                            "type": "string",
                            "description": "Path to a single PDF document to extract.",
                        },
                        "max_pages": {
                            "type": "integer",
                            "description": "Optional upper limit on page count to process per document.",
                        },
                    },
                },
            },
        }

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Standard Phase 6 Tool Execution contract.

        Args:
            input_data: Dictionary containing:
                - 'claim_id': Optional claim identifier
                - 'documents': List of document paths (strings or Paths) OR
                - 'pdf_path': Single document path (string or Path)
                - 'max_pages': Optional integer page limit

        Returns:
            Standardized Phase 6 dictionary:
            {
                "success": bool,
                "claim_id": str,
                "extracted_data": {
                    "total_pages": int,
                    "extracted_documents": list[dict]
                },
                "documents_processed": list[str],
                "errors": list[str]
            }
        """
        input_data = self.validate_input(input_data)
        claim_id = str(input_data.get("claim_id") or "CLM-UNKNOWN")
        max_pages = input_data.get("max_pages")

        # Resolve target document paths
        docs_to_process: List[Union[str, Path]] = []
        if "documents" in input_data and input_data["documents"]:
            docs = input_data["documents"]
            if isinstance(docs, (list, tuple)):
                for d in docs:
                    if isinstance(d, dict) and "path" in d:
                        docs_to_process.append(d["path"])
                    else:
                        docs_to_process.append(d)
            elif isinstance(docs, (str, Path)):
                docs_to_process.append(docs)
        elif "pdf_path" in input_data and input_data["pdf_path"]:
            docs_to_process.append(input_data["pdf_path"])

        if not docs_to_process:
            return {
                "success": False,
                "claim_id": claim_id,
                "extracted_data": {"total_pages": 0, "extracted_documents": []},
                "documents_processed": [],
                "errors": ["No document paths provided for extraction. Specify 'documents' or 'pdf_path'."],
                "status": "error",
                "tool": self.name,
                "total_pages": 0,
                "extracted_documents": [],
                "error": "No document paths provided for extraction.",
            }

        all_extracted_docs: List[Dict[str, Any]] = []
        documents_processed: List[str] = []
        errors: List[str] = []

        for doc_target in docs_to_process:
            try:
                pages = self.extractor.extract_document(doc_target, max_pages=max_pages)
                all_extracted_docs.extend(pages)
                documents_processed.append(str(doc_target))
            except Exception as e:
                logger.error(f"Extraction error processing '{doc_target}': {e}")
                errors.append(f"Failed processing '{doc_target}': {e}")

        success = len(all_extracted_docs) > 0 and len(errors) == 0
        total_pages = len(all_extracted_docs)

        # If any succeeded even with partial failures
        if all_extracted_docs and errors:
            success = True

        result = {
            "success": success,
            "claim_id": claim_id,
            "extracted_data": {
                "total_pages": total_pages,
                "extracted_documents": all_extracted_docs,
            },
            "documents_processed": documents_processed,
            "errors": errors,
            # Backward-compatible keys for Phase 1/2/3/4 callers
            "status": "success" if success else "error",
            "tool": self.name,
            "total_pages": total_pages,
            "extracted_documents": all_extracted_docs,
            "error": errors[0] if errors and not success else None,
        }
        return result

    def run(
        self,
        pdf_path: Union[str, Path],
        max_pages: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Legacy interface preserving full backward compatibility for Phase 1-4 callers.
        """
        try:
            results = self.extractor.extract_document(pdf_path, max_pages=max_pages)
            return {
                "success": True,
                "status": "success",
                "tool": self.name,
                "total_pages": len(results),
                "extracted_documents": results,
                "extracted_data": {
                    "total_pages": len(results),
                    "extracted_documents": results,
                },
                "documents_processed": [str(pdf_path)],
                "errors": [],
                "error": None,
            }
        except Exception as e:
            logger.error(f"Tool execution failed in {self.name}: {e}")
            return {
                "success": False,
                "status": "error",
                "tool": self.name,
                "total_pages": 0,
                "extracted_documents": [],
                "extracted_data": {"total_pages": 0, "extracted_documents": []},
                "documents_processed": [],
                "errors": [str(e)],
                "error": str(e),
            }


# Backwards compatibility alias
QwenVLExtractionTool = DocumentExtractionTool
