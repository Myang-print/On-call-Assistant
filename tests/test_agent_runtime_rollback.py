import logging

from app.agent_runtime import run_deterministic_agent


logger = logging.getLogger(__name__)


def test_agent_rolls_back_to_v2_when_tool_failures_reach_max_step() -> None:
    tool_calls: list[str] = []

    def failing_read_file(filename: str) -> str:
        tool_calls.append(filename)
        raise RuntimeError("tool unavailable")

    def fallback_to_v2() -> dict[str, object]:
        return {"query": "fallback", "results": [{"id": "sop-001", "score": 1.0}]}

    result = run_deterministic_agent(
        max_step=2,
        tools={"readFile": failing_read_file},
        fallback_to_v2=fallback_to_v2,
    )

    logger.info("rollback_result=%s", result)
    assert result["status"] == "rolled_back_to_v2"
    assert tool_calls == ["manifest.json", "manifest.json"]
    assert result["rollback"] == {"query": "fallback", "results": [{"id": "sop-001", "score": 1.0}]}
    assert result["state"].step == 2
    assert [event["observation"]["ok"] for event in result["trace"]] == [False, False]
    assert result["trace"][0]["observation"]["error"] == "tool unavailable"


def test_agent_does_not_rollback_when_tool_succeeds_before_finish() -> None:
    fallback_called = False

    def successful_read_file(filename: str) -> str:
        return "manifest content"

    def fallback_to_v2() -> dict[str, object]:
        nonlocal fallback_called
        fallback_called = True
        return {"query": "fallback", "results": []}

    result = run_deterministic_agent(
        max_step=3,
        tools={"readFile": successful_read_file},
        fallback_to_v2=fallback_to_v2,
    )

    logger.info("non_rollback_result=%s", result)
    assert result["status"] == "finished"
    assert fallback_called is False
    assert "rollback" not in result
