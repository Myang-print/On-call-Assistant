from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.agent import run_agent_once
from app.documents import DocumentStore
from app.hybrid_search import hybrid_search_documents
from app.semantic_search import load_domain_dictionary
from app.settings import DATA_DIR


router = APIRouter()


class OnCallQueryRequest(BaseModel):
    query: str


class OnCallQueryResponse(BaseModel):
    query: str
    answer: str
    sources: list[dict[str, Any]]
    trace: list[dict[str, Any]]


@router.post("/api/oncall/query", response_model=OnCallQueryResponse)
def query_oncall_agent(payload: OnCallQueryRequest, request: Request) -> dict[str, Any]:
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    try:
        result = run_agent_once(query, documents=_active_documents(request))
    except Exception as error:
        return _rollback_to_v2_response(query, error)

    runtime = result.get("runtime") if isinstance(result, dict) else None
    trace = _collect_trace(result, runtime)

    if result.get("ok"):
        runtime_status = runtime.get("status", "unknown") if isinstance(runtime, dict) else "unknown"
        answer = result.get("answer") or f"OnCallAgent completed with runtime status: {runtime_status}."
    else:
        return _rollback_to_v2_response(
            query,
            RuntimeError(str(result.get("error", "unknown error"))),
            event="agent_failed",
            extra_trace=result.get("trace", []) if isinstance(result.get("trace", []), list) else [],
        )

    return {
        "query": query,
        "answer": answer,
        "sources": result.get("sources", []) if isinstance(result.get("sources", []), list) else [],
        "trace": trace,
    }


def _rollback_to_v2_response(
    query: str,
    error: Exception,
    event: str = "agent_exception",
    extra_trace: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    documents = DocumentStore.from_data_dir().all()
    domain_dictionary = load_domain_dictionary(DATA_DIR / "domain_dictionary.json")
    results = [
        {
            **dict(result),
            "source_layer": "v2_fallback",
            "fallback": True,
        }
        for result in hybrid_search_documents(documents, query, domain_dictionary)
    ]
    top = ", ".join(str(item.get("id", "source")) for item in results[:3]) or "无匹配文档"
    return {
        "query": query,
        "answer": f"Agent 运行异常，已回退到 v2 检索结果。优先查看：{top}。",
        "sources": results,
        "trace": [
            *(extra_trace or []),
            {
                "stage": "api",
                "event": event,
                "error_type": type(error).__name__,
                "error": str(error),
                "rollback": "v2",
            }
        ],
    }


def _collect_trace(result: dict[str, Any], runtime: Any) -> list[dict[str, Any]]:
    trace: list[dict[str, Any]] = []
    agent_trace = result.get("trace", [])
    answer_trace: list[dict[str, Any]] = []
    if isinstance(agent_trace, list):
        for item in agent_trace:
            if not isinstance(item, dict):
                continue
            if item.get("stage") == "answer_composer":
                answer_trace.append(item)
            else:
                trace.append(item)

    if isinstance(runtime, dict):
        runtime_trace = runtime.get("trace", [])
        if isinstance(runtime_trace, list):
            trace.extend(item for item in runtime_trace if isinstance(item, dict))

    trace.extend(answer_trace)
    return trace


def _active_documents(request: Request) -> list[Any] | None:
    store = getattr(request.app.state, "document_store", None)
    if store is None or not hasattr(store, "all"):
        return None
    return store.all()
