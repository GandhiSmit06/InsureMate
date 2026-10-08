"""tools/tool_registry.py
Central Tool Registry for the InsureMate Agentic AI Architecture.
Registers, manages, and provides discovery for callable Agent tools,
enabling the Phase 5 Agent Orchestrator to inspect available tools and invoke them dynamically.
"""

from typing import Any, Dict, List, Optional
from tools.base_tool import AgentTool
from utils.logger import logger


class ToolRegistry:
    """
    Registry for managing and discovering InsureMate Agent tools.

    Provides registration, alias support, tool lookup, and capability discovery
    so that the Phase 5 Agent Orchestrator can discover available tools without
    hardcoding any execution sequence.
    """

    def __init__(self):
        self._tools: Dict[str, AgentTool] = {}
        self._aliases: Dict[str, str] = {}

    def register(
        self,
        tool: AgentTool,
        alias: Optional[str] = None,
        overwrite: bool = True,
    ) -> None:
        """
        Register an agent tool with its canonical name and optional alias.

        Args:
            tool: Instance of AgentTool
            alias: Optional secondary lookup name (e.g. legacy name)
            overwrite: Whether to overwrite existing registrations
        """
        if not isinstance(tool, AgentTool) and not hasattr(tool, "execute"):
            raise TypeError(f"Object {tool} must implement the AgentTool interface.")

        name = getattr(tool, "name", None)
        if not name or not isinstance(name, str):
            raise ValueError(f"Tool {tool} must define a valid non-empty string 'name'.")

        if name in self._tools and not overwrite:
            raise ValueError(f"Tool with name '{name}' is already registered.")

        self._tools[name] = tool
        logger.info(f"[TOOL REGISTRY] Registered tool '{name}'")

        if alias:
            self._aliases[alias] = name
            logger.info(f"[TOOL REGISTRY] Registered alias '{alias}' -> '{name}'")

    def unregister(self, name: str) -> Optional[AgentTool]:
        """Remove a tool from the registry."""
        resolved = self._aliases.pop(name, name)
        # Remove any alias pointing to resolved
        aliases_to_remove = [a for a, target in self._aliases.items() if target == resolved]
        for a in aliases_to_remove:
            del self._aliases[a]
        return self._tools.pop(resolved, None)

    def get(self, name: str) -> Optional[AgentTool]:
        """
        Retrieve a registered tool by its canonical name or alias.
        Returns None if not found.
        """
        resolved_name = self._aliases.get(name, name)
        return self._tools.get(resolved_name)

    def has(self, name: str) -> bool:
        """Check if a tool is registered by name or alias."""
        return self.get(name) is not None

    def list_tools(self) -> List[Dict[str, str]]:
        """
        Return discovery metadata for all canonically registered tools.

        Format:
        [
            {"name": "...", "description": "..."},
            ...
        ]
        """
        return [
            {
                "name": tool.name,
                "description": getattr(tool, "description", ""),
            }
            for tool in self._tools.values()
        ]

    def get_tool_names(self) -> List[str]:
        """Return list of all registered tool names (canonical only)."""
        return list(self._tools.keys())

    def get_all_names_and_aliases(self) -> List[str]:
        """Return list of all registered names including aliases."""
        return list(self._tools.keys()) + list(self._aliases.keys())

    def get_schemas(self) -> List[Dict[str, Any]]:
        """Return list of JSON schemas for LLM tool calling."""
        return [
            tool.schema
            for tool in self._tools.values()
            if hasattr(tool, "schema")
        ]

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return self.has(name)


def create_tool_registry() -> ToolRegistry:
    """
    Factory function creating a standard ToolRegistry populated with
    all default InsureMate Phase 6 tools:
    1. document_extraction_tool (alias: qwen_vl_extraction_tool)
    2. document_validation_tool
    3. validity_checker_tool
    4. missing_document_tool
    """
    from tools.qwen_extraction_tool import DocumentExtractionTool
    from tools.document_validation_tool import DocumentValidationTool
    from tools.validity_checker_tool import ValidityCheckerTool
    from tools.missing_document_tool import MissingDocumentTool

    registry = ToolRegistry()

    # 1. Document Extraction Tool
    extraction_tool = DocumentExtractionTool()
    registry.register(extraction_tool, alias="qwen_vl_extraction_tool")

    # 2. Document Validation Tool
    validation_tool = DocumentValidationTool()
    registry.register(validation_tool)

    # 3. Validity Checker Tool
    validity_tool = ValidityCheckerTool()
    registry.register(validity_tool)

    # 4. Missing Document Tool
    missing_tool = MissingDocumentTool()
    registry.register(missing_tool)

    return registry
