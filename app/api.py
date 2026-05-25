from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agent import run_agent_once


router = APIRouter()


class OnCallQueryRequest(BaseModel):
    query: str


class OnCallQueryResponse(BaseModel):
    query: str
    answer: str
    trace: list[dict[str, Any]]


@router.post("/api/oncall/query", response_model=OnCallQueryResponse)
def query_oncall_agent(payload: OnCallQueryRequest) -> dict[str, Any]:
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    result = run_agent_once(query)
    runtime = result.get("runtime") if isinstance(result, dict) else None
    trace = _collect_trace(result, runtime)

    if result.get("ok"):
        runtime_status = runtime.get("status", "unknown") if isinstance(runtime, dict) else "unknown"
        answer = f"OnCallAgent completed with runtime status: {runtime_status}."
    else:
        answer = f"OnCallAgent failed: {result.get('error', 'unknown error')}"

    return {
        "query": query,
        "answer": answer,
        "trace": trace,
    }


def _collect_trace(result: dict[str, Any], runtime: Any) -> list[dict[str, Any]]:
    trace: list[dict[str, Any]] = []
    agent_trace = result.get("trace", [])
    if isinstance(agent_trace, list):
        trace.extend(item for item in agent_trace if isinstance(item, dict))

    if isinstance(runtime, dict):
        runtime_trace = runtime.get("trace", [])
        if isinstance(runtime_trace, list):
            trace.extend(item for item in runtime_trace if isinstance(item, dict))

    return trace
