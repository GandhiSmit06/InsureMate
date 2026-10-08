"""tests/test_tool_executor.py
Unit tests for InsureMate Phase 6 Tool Executor.
Tests:
- Successful tool execution (TEST 3)
- Unknown tool handling (TEST 4)
- Invalid input handling (TEST 5)
- Tool failure handling (TEST 6)
- Standardized result format verification (TEST 7)
- Controlled retry capability
- Operational tool history recording
- ClaimState automatic updating
"""

import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.base_tool import AgentTool
from tools.claim_state import ClaimState
from tools.tool_executor import ToolExecutor
from tools.tool_registry import ToolRegistry


class SuccessTool(AgentTool):
    name = "success_tool"
    description = "Always succeeds."

    def execute(self, input_data):
        return {
            "success": True,
            "processed": input_data.get("val", 0) * 2,
        }


class FlakyTool(AgentTool):
    name = "flaky_tool"
    description = "Fails once, then succeeds on retry."

    def __init__(self):
        self.call_count = 0

    def execute(self, input_data):
        self.call_count += 1
        if self.call_count == 1:
            raise RuntimeError("Transient network timeout")
        return {"success": True, "call_count": self.call_count}


class AlwaysFailingTool(AgentTool):
    name = "failing_tool"
    description = "Always raises an exception."

    def execute(self, input_data):
        raise ValueError("Critical domain error")


@pytest.fixture
def executor_fixture():
    registry = ToolRegistry()
    registry.register(SuccessTool())
    registry.register(FlakyTool())
    registry.register(AlwaysFailingTool())
    return ToolExecutor(registry=registry)


def test_successful_tool_execution(executor_fixture):
    """TEST 3 & TEST 7: Successful tool execution returning standardized result."""
    executor = executor_fixture
    res = executor.execute("success_tool", {"val": 21})

    # TEST 7: Standardized format check
    assert res["success"] is True
    assert res["tool_name"] == "success_tool"
    assert res["error"] is None
    assert isinstance(res["result"], dict)
    assert res["result"]["processed"] == 42


def test_unknown_tool_execution(executor_fixture):
    """TEST 4: Calling unregistered tool returns standardized error without crashing."""
    executor = executor_fixture
    res = executor.execute("non_existent_tool", {"val": 10})

    assert res["success"] is False
    assert res["tool_name"] == "non_existent_tool"
    assert res["result"] is None
    assert res["error"] is not None
    assert res["error"]["type"] == "ToolNotFoundError"
    assert "not found in registry" in res["error"]["message"]


def test_invalid_input_handling(executor_fixture):
    """TEST 5: Non-dict input returns ToolValidationError."""
    executor = executor_fixture
    res = executor.execute("success_tool", input_data="invalid_string")  # type: ignore

    assert res["success"] is False
    assert res["tool_name"] == "success_tool"
    assert res["result"] is None
    assert res["error"]["type"] == "ToolValidationError"


def test_tool_failure_handling(executor_fixture):
    """TEST 6: Tool exception is safely captured in standardized error format."""
    executor = executor_fixture
    res = executor.execute("failing_tool", {"val": 1})

    assert res["success"] is False
    assert res["tool_name"] == "failing_tool"
    assert res["error"] is not None
    assert res["error"]["type"] == "ValueError"
    assert "Critical domain error" in res["error"]["message"]


def test_retry_support(executor_fixture):
    """Controlled retry successfully recovers when retry_count >= 1."""
    executor = executor_fixture

    # FlakyTool fails on call 1, succeeds on call 2
    res = executor.execute("flaky_tool", retry_count=1)

    assert res["success"] is True
    assert res["tool_name"] == "flaky_tool"
    assert res["result"]["call_count"] == 2


def test_retry_exhaustion():
    """Controlled retry exhausts and reports last error when attempts run out."""
    registry = ToolRegistry()
    registry.register(AlwaysFailingTool())
    executor = ToolExecutor(registry=registry)

    res = executor.execute("failing_tool", retry_count=2)
    assert res["success"] is False
    assert res["error"]["type"] == "ValueError"

    # Verify history recorded 2 retries attempted
    history = executor.get_history()
    assert len(history) == 1
    assert history[0]["retries_attempted"] == 2


def test_tool_history_recording(executor_fixture):
    """Verify concise operational history is tracked without hidden chain-of-thought."""
    executor = executor_fixture
    executor.execute("success_tool", {"val": 5})
    executor.execute("failing_tool")

    history = executor.get_history()
    assert len(history) == 2

    assert history[0]["tool_name"] == "success_tool"
    assert history[0]["status"] == "success"
    assert "timestamp" in history[0]
    assert "summary" in history[0]
    assert "duration_ms" in history[0]

    assert history[1]["tool_name"] == "failing_tool"
    assert history[1]["status"] == "failed"


def test_claim_state_integration(executor_fixture):
    """Verify shared ClaimState is updated automatically when passed to executor."""
    executor = executor_fixture
    state = ClaimState(claim_id="CLM-TEST-001")

    res = executor.execute("success_tool", {"val": 10}, state=state)
    assert res["success"] is True

    # State recorded history
    assert len(state.tool_history) == 1
    assert state.tool_history[0]["tool_name"] == "success_tool"
    assert state.tool_history[0]["status"] == "success"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
