import logging

from app.planner import PlannerResult, parse_planner_response, plan_with_llm


logger = logging.getLogger(__name__)


def test_planner_rejects_blank_response_and_requests_retry() -> None:
    result = parse_planner_response("   ")

    logger.info("blank_planner_result=%s", result)
    assert result == PlannerResult(
        ok=False,
        retry=True,
        action=None,
        error="blank planner response",
        trace=[{"stage": "planner", "event": "blank_response"}],
    )


def test_planner_rejects_invalid_json_and_requests_retry() -> None:
    result = parse_planner_response("{not-json")

    logger.info("invalid_json_planner_result=%s", result)
    assert result.ok is False
    assert result.retry is True
    assert result.action is None
    assert result.error == "invalid planner json"
    assert result.trace == [{"stage": "planner", "event": "invalid_json"}]


def test_planner_rejects_missing_action_and_requests_retry() -> None:
    result = parse_planner_response('{"tool":"readFile"}')

    logger.info("missing_fields_planner_result=%s", result)
    assert result.ok is False
    assert result.retry is True
    assert result.error == "missing planner action"
    assert result.trace == [{"stage": "planner", "event": "missing_action"}]


def test_planner_accepts_valid_tool_action_json() -> None:
    result = parse_planner_response('{"action":"tool","tool":"readFile","args":{"fname":"manifest.json"}}')

    logger.info("valid_planner_result=%s", result)
    assert result.ok is True
    assert result.retry is False
    assert result.action == {"action": "tool", "tool": "readFile", "args": {"fname": "manifest.json"}}
    assert result.trace == [{"stage": "planner", "event": "valid_action"}]


def test_planner_rejects_direct_tool_execution_shape() -> None:
    result = parse_planner_response('{"readFile":"sop-001.html"}')

    logger.info("direct_tool_planner_result=%s", result)
    assert result.ok is False
    assert result.retry is True
    assert result.error == "planner must not call tools directly"
    assert result.trace == [{"stage": "planner", "event": "direct_tool_call_rejected"}]


def test_plan_with_llm_calls_llm_and_validates_response() -> None:
    prompts: list[str] = []

    def fake_llm(prompt: str) -> str:
        prompts.append(prompt)
        return '{"action":"tool","tool":"readFile","args":{"fname":"manifest.json"}}'

    result = plan_with_llm("SYSTEM", "USER", fake_llm)

    logger.info("llm_prompts=%s result=%s", prompts, result)
    assert prompts == ["SYSTEM\n\nUSER"]
    assert result.ok is True
