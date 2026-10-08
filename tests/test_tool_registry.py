"""tests/test_tool_registry.py
Unit tests for InsureMate Phase 6 Tool Registry.
Tests:
- Tool registration (canonical name)
- Tool registration with alias
- Tool discovery via list_tools()
- Unknown tool retrieval
- Unregister tool
- Schema generation
- Factory create_tool_registry()
- Validation of tool interface upon registration
"""

import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.base_tool import AgentTool
from tools.tool_registry import ToolRegistry, create_tool_registry


class DummyTool(AgentTool):
    name = "dummy_test_tool"
    description = "A dummy tool for unit testing."

    def execute(self, input_data):
        return {"success": True, "result": "dummy_ok"}


class AnotherDummyTool(AgentTool):
    name = "another_dummy_tool"
    description = "Another dummy tool."

    def execute(self, input_data):
        return {"success": True, "result": "another_ok"}


def test_tool_registration():
    """TEST 1: Tool registration with canonical name and alias."""
    registry = ToolRegistry()
    dummy = DummyTool()

    registry.register(dummy, alias="dummy_alias")
    assert registry.has("dummy_test_tool") is True
    assert registry.has("dummy_alias") is True
    assert registry.get("dummy_test_tool") is dummy
    assert registry.get("dummy_alias") is dummy
    assert len(registry) == 1


def test_tool_discovery():
    """TEST 2: Tool discovery via list_tools()."""
    registry = ToolRegistry()
    registry.register(DummyTool())
    registry.register(AnotherDummyTool())

    tools_list = registry.list_tools()
    assert len(tools_list) == 2
    names = [t["name"] for t in tools_list]
    assert "dummy_test_tool" in names
    assert "another_dummy_tool" in names

    dummy_meta = next(t for t in tools_list if t["name"] == "dummy_test_tool")
    assert dummy_meta["description"] == "A dummy tool for unit testing."


def test_unknown_tool_lookup():
    """TEST 4 (part): Querying non-existent tool returns None."""
    registry = ToolRegistry()
    assert registry.get("non_existent_tool") is None
    assert registry.has("non_existent_tool") is False


def test_unregister_tool():
    """Test removing tool and associated aliases."""
    registry = ToolRegistry()
    registry.register(DummyTool(), alias="dummy_alias")
    assert registry.has("dummy_test_tool") is True

    removed = registry.unregister("dummy_alias")
    assert removed is not None
    assert registry.has("dummy_test_tool") is False
    assert registry.has("dummy_alias") is False
    assert len(registry) == 0


def test_invalid_tool_registration():
    """Registering object without AgentTool interface raises TypeError."""
    registry = ToolRegistry()
    with pytest.raises(TypeError):
        registry.register("not_a_tool")


def test_create_tool_registry_factory():
    """Verify create_tool_registry factory registers all 4 core InsureMate tools."""
    registry = create_tool_registry()

    assert len(registry) == 4
    assert registry.has("document_extraction_tool") is True
    assert registry.has("qwen_vl_extraction_tool") is True  # Alias
    assert registry.has("document_validation_tool") is True
    assert registry.has("validity_checker_tool") is True
    assert registry.has("missing_document_tool") is True

    tools = registry.list_tools()
    names = [t["name"] for t in tools]
    assert "document_extraction_tool" in names
    assert "document_validation_tool" in names
    assert "validity_checker_tool" in names
    assert "missing_document_tool" in names


def test_schemas_generation():
    """Verify schemas generation returns valid function definitions."""
    registry = create_tool_registry()
    schemas = registry.get_schemas()
    assert len(schemas) == 4
    for s in schemas:
        assert s["type"] == "function"
        assert "name" in s["function"]
        assert "description" in s["function"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
