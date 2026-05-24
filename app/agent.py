from collections.abc import Callable
from typing import Any

from app.agent_runtime import run_deterministic_agent
from app.planner import SYSTEM_PROMPT as SYSTEM_STATE
from app.planner import PlannerResult, plan_with_llm
from app.tool_registry import TOOL_REGISTRY


Planner = Callable[[str, str], PlannerResult]


def run_agent_once(
    user_prompt: str,
    planner: Planner | None = None,
    max_step: int = 3,
) -> dict[str, Any]:
    # Agent trace records only agent-level decisions; planner/runtime traces stay in their modules.
    planner_result = _call_planner(user_prompt, planner)
    if not planner_result.ok:
        return {
            "ok": False,
            "retry": planner_result.retry,
            "error": planner_result.error,
            "trace": [{"stage": "agent", "event": "planner_failed", "error": planner_result.error}],
        }

    action = planner_result.operation or planner_result.action or {}
    tool_name = action.get("tool")
    if tool_name not in TOOL_REGISTRY:
        return {
            "ok": False,
            "retry": True,
            "error": "planner requested unavailable tool",
            "trace": [{"stage": "agent", "event": "unavailable_tool", "tool": str(tool_name)}],
        }

    runtime_result = run_deterministic_agent(max_step=max_step)
    return {
        "ok": True,
        "retry": False,
        "tool": tool_name,
        "trace": [{"stage": "agent", "event": "tool_allowed", "tool": tool_name}],
        "runtime": runtime_result,
    }


def _call_planner(user_prompt: str, planner: Planner | None) -> PlannerResult:
    if planner is not None:
        return planner(SYSTEM_STATE, user_prompt)

    return plan_with_llm(
        SYSTEM_STATE,
        user_prompt,
    )
