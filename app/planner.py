import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.llm_client import LLMClient as SelectedLLMClient
from app.llm_client import select_llm_client
from app.schemas import ToolAction


SYSTEM_PROMPT = """
ROLE:
You are a deterministic On-Call Assistant agent.

STATE:
Use a bounded runtime with trace recording and max_step safety.

TOOL_REGISTRY:
readFile(fname): read one explicit filename from data/.

OUTPUT FORMAT:
Return JSON with action, tool, and args. The planner must not execute tools.

EXAMPLE:
{"action":"tool","tool":"readFile","args":{"fname":"manifest.json"}}
"""


@dataclass(frozen=True)
class PlannerResult:
    ok: bool
    retry: bool
    action: dict[str, Any] | None
    error: str | None
    trace: list[dict[str, str]]
    operation: dict[str, Any] | None = None


LLMCallable = Callable[[str], str]


def plan_with_llm(
    system_prompt: str,
    user_prompt: str,
    llm_client: LLMCallable | SelectedLLMClient | None = None,
) -> PlannerResult:
    selected_client = llm_client or select_llm_client()
    prompt = f"{system_prompt}\n\n{user_prompt}"
    if callable(selected_client):
        response = selected_client(prompt)
    else:
        response = selected_client.complete(prompt)
    return parse_planner_response(response)


def parse_planner_response(response: str) -> PlannerResult:
    # Planner trace is intentionally local to this module; agent/runtime build their own traces.
    if not response.strip():
        return _failure("blank planner response", "blank_response")

    try:
        payload = json.loads(response)
    except json.JSONDecodeError:
        return _failure("invalid planner json", "invalid_json")

    if not isinstance(payload, dict):
        return _failure("invalid planner schema", "invalid_schema")
    if "readFile" in payload:
        return _failure("planner must not call tools directly", "direct_tool_call_rejected")
    if "action" not in payload:
        return _failure("missing planner action", "missing_action")
    if payload.get("action") != "tool":
        return _failure("invalid planner schema", "invalid_schema")
    if not isinstance(payload.get("tool"), str):
        return _failure("invalid planner schema", "invalid_schema")
    args = payload.get("args")
    if not isinstance(args, dict):
        return _failure("invalid planner schema", "invalid_schema")
    if not isinstance(args.get("fname"), str):
        return _failure("invalid planner schema", "invalid_schema")

    operation = ToolAction(tool=payload["tool"], args=args).to_json_dict()
    return PlannerResult(
        ok=True,
        retry=False,
        action=payload,
        error=None,
        trace=[{"stage": "planner", "event": "valid_action"}],
        operation=operation,
    )


def _failure(error: str, event: str) -> PlannerResult:
    return PlannerResult(
        ok=False,
        retry=True,
        action=None,
        error=error,
        trace=[{"stage": "planner", "event": event}],
    )
