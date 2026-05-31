from typing import Any


LATENCY_QUERIES = [
    "服务 OOM 了怎么办？",
    "数据库主从延迟超过30秒怎么处理？",
    "怀疑有人入侵了系统",
    "推荐结果质量下降了",
]


def collect_latency_runs(queries: list[str] | None = None) -> list[dict[str, Any]]:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    rows: list[dict[str, Any]] = []
    for query in queries or LATENCY_QUERIES:
        response = client.post("/api/oncall/query", json={"query": query})
        payload = response.json()
        rows.append(
            {
                "query": payload.get("query", query),
                "answer": payload.get("answer", ""),
                "trace": payload.get("trace", []),
            }
        )
    return rows


def summarize_latency_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [_row_from_run(run) for run in runs]
    case_count = len(rows)
    return {
        "case_count": case_count,
        "average_prompt_chars": _average(row["prompt_chars"] for row in rows),
        "average_answer_chars": _average(row["answer_chars"] for row in rows),
        "average_elapsed_seconds": _average(row["elapsed_seconds"] for row in rows),
        "success_rate": _rate(row["llm_success"] for row in rows),
        "fallback_rate": _rate(row["fallback_used"] for row in rows),
        "rows": rows,
    }


def format_latency_table(summary: dict[str, Any]) -> str:
    headers = ["query", "prompt_chars", "answer_chars", "elapsed_seconds", "llm_success", "fallback_used"]
    lines = [" | ".join(headers)]
    lines.append(" | ".join("---" for _ in headers))
    for row in summary.get("rows", []):
        if not isinstance(row, dict):
            continue
        lines.append(
            " | ".join(
                [
                    str(row.get("query", "")),
                    str(row.get("prompt_chars", 0)),
                    str(row.get("answer_chars", 0)),
                    str(row.get("elapsed_seconds", 0.0)),
                    str(row.get("llm_success", False)),
                    str(row.get("fallback_used", False)),
                ]
            )
        )
    lines.append("")
    lines.append(f"average_elapsed_seconds: {summary.get('average_elapsed_seconds', 0.0)}")
    lines.append(f"average_answer_chars: {summary.get('average_answer_chars', 0.0)}")
    lines.append(f"success_rate: {summary.get('success_rate', 0.0)}")
    lines.append(f"fallback_rate: {summary.get('fallback_rate', 0.0)}")
    return "\n".join(lines)


def _row_from_run(run: dict[str, Any]) -> dict[str, Any]:
    trace = run.get("trace", [])
    trace_items = trace if isinstance(trace, list) else []
    prompt_trace = _first_event(trace_items, "prompt_built")
    success_trace = _first_event(trace_items, "llm_call_succeeded")
    failure_trace = _first_event(trace_items, "llm_call_failed")
    generation_trace = success_trace or failure_trace
    fallback_used = _first_event(trace_items, "deterministic_fallback") is not None
    answer = str(run.get("answer", ""))
    return {
        "query": str(run.get("query", "")),
        "prompt_chars": _int_value(prompt_trace, "prompt_chars"),
        "answer_chars": _answer_chars(success_trace, answer),
        "elapsed_seconds": _float_value(generation_trace, "elapsed_seconds"),
        "llm_success": success_trace is not None,
        "fallback_used": fallback_used,
    }


def _first_event(trace_items: list[Any], event: str) -> dict[str, Any] | None:
    for item in trace_items:
        if isinstance(item, dict) and item.get("event") == event:
            return item
    return None


def _answer_chars(trace_item: dict[str, Any] | None, fallback_answer: str) -> int:
    if trace_item is not None:
        return _int_value(trace_item, "answer_chars")
    return len(fallback_answer)


def _int_value(item: dict[str, Any] | None, key: str) -> int:
    if item is None:
        return 0
    value = item.get(key, 0)
    return value if isinstance(value, int) else 0


def _float_value(item: dict[str, Any] | None, key: str) -> float:
    if item is None:
        return 0.0
    value = item.get(key, 0.0)
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _average(values: Any) -> float:
    numbers = list(values)
    if not numbers:
        return 0.0
    return sum(numbers) / len(numbers)


def _rate(values: Any) -> float:
    flags = list(values)
    if not flags:
        return 0.0
    return sum(1 for flag in flags if flag) / len(flags)


if __name__ == "__main__":
    print(format_latency_table(summarize_latency_runs(collect_latency_runs())))
