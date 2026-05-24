import logging

from app.agent import SYSTEM_STATE, run_agent_once
from app.planner import PlannerResult


logger = logging.getLogger(__name__)


def test_system_state_contains_required_sections_and_example() -> None:
    logger.info("system_state=%s", SYSTEM_STATE)
    assert "ROLE" in SYSTEM_STATE
    assert "STATE" in SYSTEM_STATE
    assert "TOOL_REGISTRY" in SYSTEM_STATE
    assert "OUTPUT FORMAT" in SYSTEM_STATE
    assert "EXAMPLE" in SYSTEM_STATE
    assert "readFile" in SYSTEM_STATE


def test_agent_rejects_unregistered_planner_tool_and_requests_retry() -> None:
    def planner(_: str, __: str) -> PlannerResult:
        return PlannerResult(
            ok=True,
            retry=False,
            action={"action": "tool", "tool": "deleteFile", "args": {"fname": "manifest.json"}},
            error=None,
            trace=[{"stage": "planner", "event": "valid_action"}],
        )

    result = run_agent_once("read manifest", planner=planner)

    logger.info("unregistered_tool_agent_result=%s", result)
    assert result["ok"] is False
    assert result["retry"] is True
    assert result["error"] == "planner requested unavailable tool"
    assert result["trace"] == [{"stage": "agent", "event": "unavailable_tool", "tool": "deleteFile"}]


def test_agent_propagates_planner_failure_and_requests_retry() -> None:
    def planner(_: str, __: str) -> PlannerResult:
        return PlannerResult(
            ok=False,
            retry=True,
            action=None,
            error="invalid planner json",
            trace=[{"stage": "planner", "event": "invalid_json"}],
        )

    result = run_agent_once("read manifest", planner=planner)

    logger.info("planner_failure_agent_result=%s", result)
    assert result == {
        "ok": False,
        "retry": True,
        "error": "invalid planner json",
        "trace": [{"stage": "agent", "event": "planner_failed", "error": "invalid planner json"}],
    }


def test_agent_read_file_pipeline_is_stable() -> None:
    def planner(_: str, __: str) -> PlannerResult:
        return PlannerResult(
            ok=True,
            retry=False,
            action={"action": "tool", "tool": "readFile", "args": {"fname": "manifest.json"}},
            error=None,
            trace=[{"stage": "planner", "event": "valid_action"}],
        )

    result = run_agent_once("read manifest", planner=planner)

    logger.info("agent_read_file_result=%s", result)
    assert result["ok"] is True
    assert result["retry"] is False
    assert result["tool"] == "readFile"
    assert result["trace"] == [{"stage": "agent", "event": "tool_allowed", "tool": "readFile"}]
    assert result["runtime"]["status"] == "finished"
    assert result["runtime"]["trace"][0]["action"] == {"type": "readFile", "fname": "manifest.json"}
