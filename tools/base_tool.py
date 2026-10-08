"""tools/base_tool.py
Base Tool Interface for the InsureMate Agentic AI Architecture.
Defines the standard contract that all Phase 6 tools must implement,
enabling dynamic discovery, validation, and invocation by the Phase 5 Agent Orchestrator.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from utils.logger import logger


class AgentTool(ABC):
    """
    Abstract Base Class for callable Agent Tools in InsureMate.

    Every tool provides:
    - name: Unique identifier for agent tool calling (e.g. 'document_validation_tool')
    - description: Concise natural language capability summary for LLM agent reasoning
    - execute: Core method taking structured input_data and returning a predictable dictionary
    """

    name: str = "base_agent_tool"
    description: str = "Abstract agent tool interface."

    @abstractmethod
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute tool operation with standardized input dictionary.

        Args:
            input_data: Tool-specific input dictionary (e.g., {'claim_id': '...', ...})

        Returns:
            Predictable structured dictionary containing tool results or structured errors.
        """
        raise NotImplementedError("Subclasses must implement execute(input_data).")

    @property
    def schema(self) -> Dict[str, Any]:
        """
        Optional JSON schema definition for LLM function/tool calling registration
        (compatible with OpenAI, Ollama, LangChain, and custom orchestrators).
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "input_data": {
                            "type": "object",
                            "description": "Input payload for tool execution.",
                        }
                    },
                },
            },
        }

    def validate_input(self, input_data: Any) -> Dict[str, Any]:
        """
        Validate and normalize input payload before execution.
        Subclasses may override to enforce domain-specific validation.
        """
        if input_data is None:
            return {}
        if not isinstance(input_data, dict):
            raise TypeError(
                f"Tool '{self.name}' expected input_data to be a dictionary, got {type(input_data).__name__}."
            )
        return input_data

    def to_dict(self) -> Dict[str, str]:
        """Return concise discovery metadata for agent planning."""
        return {
            "name": self.name,
            "description": self.description,
        }

    def __call__(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Callable convenience hook delegating to execute or run."""
        if args and isinstance(args[0], dict) and not kwargs:
            return self.execute(args[0])
        if hasattr(self, "run"):
            return getattr(self, "run")(*args, **kwargs)
        if kwargs and "input_data" in kwargs:
            return self.execute(kwargs["input_data"])
        return self.execute(kwargs)
