from dataclasses import dataclass, field
from collections.abc import Callable
import time
from typing import Any

from app.tool_registry import get_tool


@dataclass
class AgentState:
    max_step: int
    step: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)
    planner_retry_limit: int = 2
    tool_call_limit: int = 1


def select_action(state: AgentState) -> dict[str, str]:
    if state.step == 0:
        return {"type": "readFile", "fname": "manifest.json"}
    if state.history and not state.history[-1]["observation"]["ok"]:
        return {"type": "readFile", "fname": "manifest.json"}
    return {"type": "finish", "message": "deterministic runtime complete"}


ToolMap = dict[str, Callable[[str], str]]
FallbackToV2 = Callable[[], dict[str, Any]]


def run_deterministic_agent(
    max_step: int,
    tools: ToolMap | None = None,
    fallback_to_v2: FallbackToV2 | None = None,
    planner_retry_limit: int = 2,
    tool_call_limit: int = 1,
    tool_timeout_seconds: float | None = None,
) -> dict[str, Any]:
    state = AgentState(
        max_step=max_step,
        planner_retry_limit=planner_retry_limit,
        tool_call_limit=tool_call_limit,
    )
    trace: list[dict[str, Any]] = []

    while state.step < state.max_step:
        action = select_action(state)
        observation = _execute_action(
            action,
            tools=tools,
            tool_call_limit=state.tool_call_limit,
            tool_timeout_seconds=tool_timeout_seconds,
        )
        event = {
            "step": state.step,
            "action": action,
            "observation": observation,
        }
        state.history.append(event)
        trace.append(event)
        state.step += 1
        if action["type"] == "finish":
            return {"status": "finished", "state": state, "trace": trace}
        if observation["ok"]:
            continue

    if trace and not trace[-1]["observation"]["ok"]:
        rollback = _rollback_to_v2(fallback_to_v2)
        return {
            "status": "rolled_back_to_v2",
            "state": state,
            "trace": trace,
            "rollback": rollback,
        }

    return {"status": "max_step_reached", "state": state, "trace": trace}


def _execute_action(
    action: dict[str, str],
    tools: ToolMap | None = None,
    tool_call_limit: int = 1,
    tool_timeout_seconds: float | None = None,
) -> dict[str, Any]:
    if action["type"] == "readFile":
        tool_name = "readFile"
        tool_function = tools[tool_name] if tools and tool_name in tools else get_tool(tool_name).function
        attempts = max(1, tool_call_limit)
        last_error = ""
        for attempt in range(1, attempts + 1):
            started_at = time.monotonic()
            try:
                content = tool_function(action["fname"])
                elapsed_seconds = time.monotonic() - started_at
                if tool_timeout_seconds is not None and elapsed_seconds > tool_timeout_seconds:
                    last_error = "tool timeout"
                    break
                return {
                    "ok": True,
                    "tool": tool_name,
                    "bytes": len(content.encode("utf-8")),
                    "attempt": attempt,
                }
            except Exception as error:
                last_error = str(error)
        return {
            "ok": False,
            "tool": tool_name,
            "error": last_error,
            "attempts": attempts,
        }
    if action["type"] == "finish":
        return {"ok": True, "message": action["message"]}
    return {"ok": False, "error": "unknown action"}


def _rollback_to_v2(fallback_to_v2: FallbackToV2 | None) -> dict[str, Any]:
    if fallback_to_v2 is not None:
        return fallback_to_v2()
    return {
        "query": "",
        "results": [],
        "source": "v2_fallback_unconfigured",
    }
