from collections.abc import Callable
from typing import Any, Protocol

from app.agent_runtime import run_deterministic_agent
from app.answer_composer import AnswerComposer
from app.planner import SYSTEM_PROMPT as SYSTEM_STATE
from app.planner import PlannerResult, plan_with_llm
from app.tool_registry import TOOL_REGISTRY


Planner = Callable[[str, str], PlannerResult]


class Composer(Protocol):
    def compose(
        self,
        user_query: str,
        retrieved_docs: list[dict[str, Any]],
        sources: list[dict[str, Any]],
        trace: list[dict[str, Any]],
    ) -> dict[str, Any]:
        ...


def run_agent_once(
    user_prompt: str,
    planner: Planner | None = None,
    max_step: int = 6,
    answer_composer: Composer | None = None,
    documents: list[Any] | None = None,
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

    runtime_result = run_deterministic_agent(max_step=max_step, query=user_prompt)
    retrieved_docs, sources = _retrieve_evidence_for_query(user_prompt, runtime_result, documents)
    composed_answer = (answer_composer or AnswerComposer()).compose(
        user_query=user_prompt,
        retrieved_docs=retrieved_docs,
        sources=sources,
        trace=_extract_runtime_trace(runtime_result),
    )
    answer_trace = composed_answer.get("answer_trace", [])
    agent_trace = [{"stage": "agent", "event": "tool_allowed", "tool": tool_name}]
    if isinstance(answer_trace, list):
        agent_trace.extend(item for item in answer_trace if isinstance(item, dict))
    return {
        "ok": True,
        "retry": False,
        "tool": tool_name,
        "trace": agent_trace,
        "runtime": runtime_result,
        "answer": composed_answer["answer"],
        "sources": composed_answer["sources"],
        "mode": composed_answer["mode"],
    }


def _call_planner(user_prompt: str, planner: Planner | None) -> PlannerResult:
    if planner is not None:
        return planner(SYSTEM_STATE, user_prompt)

    return plan_with_llm(
        SYSTEM_STATE,
        user_prompt,
    )


def _extract_retrieved_docs(runtime_result: dict[str, Any]) -> list[dict[str, Any]]:
    retrieved_docs = runtime_result.get("retrieved_docs", [])
    return retrieved_docs if isinstance(retrieved_docs, list) else []


def _extract_sources(runtime_result: dict[str, Any]) -> list[dict[str, Any]]:
    sources = runtime_result.get("sources", [])
    return sources if isinstance(sources, list) else []


def _extract_runtime_trace(runtime_result: dict[str, Any]) -> list[dict[str, Any]]:
    trace = runtime_result.get("trace", [])
    return trace if isinstance(trace, list) else []


def _retrieve_evidence_for_query(
    user_prompt: str,
    runtime_result: dict[str, Any],
    documents: list[Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    runtime_docs = _extract_retrieved_docs(runtime_result)
    runtime_sources = _extract_sources(runtime_result)
    if runtime_docs:
        return runtime_docs, runtime_sources

    return [], []
