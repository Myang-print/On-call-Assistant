from collections.abc import Callable
import re
from typing import Any, Protocol

from app.agent_runtime import run_deterministic_agent
from app.answer_composer import AnswerComposer
from app.documents import DocumentStore
from app.hybrid_search import hybrid_search_documents
from app.key_search import search_documents
from app.planner import SYSTEM_PROMPT as SYSTEM_STATE
from app.planner import PlannerResult, plan_with_llm
from app.semantic_search import load_domain_dictionary
from app.settings import DATA_DIR
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
    max_step: int = 3,
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
    return {
        "ok": True,
        "retry": False,
        "tool": tool_name,
        "trace": [{"stage": "agent", "event": "tool_allowed", "tool": tool_name}],
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

    active_documents = documents if documents is not None else DocumentStore.from_data_dir().all()
    sources = _rank_agent_sources(active_documents, user_prompt)
    documents_by_id = {document.doc_id: document for document in active_documents}
    retrieved_docs: list[dict[str, Any]] = []
    for source in sources:
        document = documents_by_id.get(str(source.get("id", "")))
        if document is None:
            continue
        retrieved_docs.append(
            {
                "filename": f"{document.doc_id}.html",
                "title": document.title,
                "content": document.cleaned_text,
                "cleaned_text": document.cleaned_text,
            }
        )
    return retrieved_docs, sources


def _rank_agent_sources(documents: list[Any], user_prompt: str) -> list[dict[str, Any]]:
    dictionary = load_domain_dictionary(DATA_DIR / "domain_dictionary.json")
    results = hybrid_search_documents(documents, user_prompt, dictionary)
    if not results:
        results = _keyword_evidence_search(documents, user_prompt)
    return [dict(result) for result in results[:5]]


def _keyword_evidence_search(documents: list[Any], user_prompt: str) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for term in _agent_query_terms(user_prompt):
        for result in search_documents(documents, term):
            doc_id = str(result["id"])
            current = merged.get(doc_id)
            if current is None or float(result["score"]) > float(current["score"]):
                merged[doc_id] = dict(result)
    return sorted(merged.values(), key=lambda result: (-float(result["score"]), str(result["id"])))


def _agent_query_terms(user_prompt: str) -> list[str]:
    folded = user_prompt.casefold()
    terms = [user_prompt.strip()]
    terms.extend(re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*", user_prompt))
    if "oom" in folded or "内存" in user_prompt:
        terms.append("OOM")
    if "主从" in user_prompt or "延迟" in user_prompt:
        terms.append("主从延迟")
    if "入侵" in user_prompt or "黑客" in user_prompt or "攻击" in user_prompt:
        terms.append("入侵")
    if "推荐" in user_prompt or "质量下降" in user_prompt:
        terms.append("推荐")
    if "p0" in folded or "故障" in user_prompt:
        terms.append("故障")
    if "cdn" in folded:
        terms.append("CDN")
    return [term for index, term in enumerate(terms) if term and term not in terms[:index]]
