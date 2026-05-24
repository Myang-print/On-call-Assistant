from dataclasses import dataclass, field
from collections.abc import Callable
from typing import Any

from app.tool_registry import get_tool


@dataclass
class AgentState:
    max_step: int
    step: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)


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
) -> dict[str, Any]:
    state = AgentState(max_step=max_step)
    trace: list[dict[str, Any]] = []

    while state.step < state.max_step:
        action = select_action(state)
        observation = _execute_action(action, tools)
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
        rollback = fallback_to_v2() if fallback_to_v2 is not None else {}
        return {
            "status": "rolled_back_to_v2",
            "state": state,
            "trace": trace,
            "rollback": rollback,
        }

    return {"status": "max_step_reached", "state": state, "trace": trace}


def _execute_action(action: dict[str, str], tools: ToolMap | None = None) -> dict[str, Any]:
    if action["type"] == "readFile":
        tool_name = "readFile"
        tool_function = tools[tool_name] if tools and tool_name in tools else get_tool(tool_name).function
        try:
            content = tool_function(action["fname"])
            return {
                "ok": True,
                "tool": tool_name,
                "bytes": len(content.encode("utf-8")),
            }
        except Exception as error:
            return {
                "ok": False,
                "tool": tool_name,
                "error": str(error),
            }
    if action["type"] == "finish":
        return {"ok": True, "message": action["message"]}
    return {"ok": False, "error": "unknown action"}
