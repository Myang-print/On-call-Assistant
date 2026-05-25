import logging

from app.agent import run_agent_once
from app.main import app
from app.answer_composer import AnswerComposer
from app.planner import PlannerResult
from fastapi.testclient import TestClient


logger = logging.getLogger(__name__)


class RecordingLLM:
    def __init__(self, response: str = "自然语言 on-call 建议") -> None:
        self.response = response
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


def test_compose_returns_insufficient_evidence_without_calling_llm() -> None:
    llm = RecordingLLM()
    trace = [{"step": 0, "event": "finish"}]

    result = AnswerComposer(llm).compose(
        user_query="服务 OOM 了怎么办？",
        retrieved_docs=[],
        sources=[{"filename": "sop-001.html", "title": "后端服务 On-Call SOP"}],
        trace=trace,
    )

    logger.info("empty_docs_answer=%s", result)
    assert llm.prompts == []
    assert result == {
        "answer": "当前没有足够的 SOP 文档支持判断，请补充相关日志、错误信息或 SOP 文档。",
        "sources": [],
        "trace": trace,
        "mode": "agent",
    }


def test_compose_calls_llm_generate_when_docs_are_available() -> None:
    llm = RecordingLLM("建议先检查容器内存和最近发布。")

    result = AnswerComposer(llm).compose(
        user_query="服务 OOM 了怎么办？",
        retrieved_docs=[
            {
                "filename": "sop-001.html",
                "title": "后端服务 On-Call SOP",
                "content": "OOM 排查：检查内存限制、GC、最近发布。",
            }
        ],
        sources=[{"filename": "sop-001.html", "title": "后端服务 On-Call SOP"}],
        trace=[{"step": 0}],
    )

    logger.info("llm_answer=%s prompt=%s", result, llm.prompts)
    assert len(llm.prompts) == 1
    assert "你是 OnCall 问题分析助手" in llm.prompts[0]
    assert "只能使用 provided documents" in llm.prompts[0]
    assert "服务 OOM 了怎么办？" in llm.prompts[0]
    assert result["answer"] == "建议先检查容器内存和最近发布。"


def test_compose_preserves_input_sources_and_trace() -> None:
    llm = RecordingLLM("请引用 sop-001。")
    sources = [{"filename": "sop-001.html", "title": "后端服务 On-Call SOP"}]
    trace = [{"step": 0, "action": {"type": "readFile"}}]

    result = AnswerComposer(llm).compose(
        user_query="OOM",
        retrieved_docs=[{"filename": "sop-001.html", "title": "后端服务 On-Call SOP", "cleaned_text": "OOM"}],
        sources=sources,
        trace=trace,
    )

    assert result["sources"] == sources
    assert result["sources"] is sources
    assert result["trace"] == trace
    assert result["trace"] is trace


def test_answer_is_not_runtime_status() -> None:
    llm = RecordingLLM("问题判断：可能是内存不足。")

    result = AnswerComposer(llm).compose(
        user_query="OOM",
        retrieved_docs=[{"filename": "sop-001.html", "title": "后端服务 On-Call SOP", "content": "OOM"}],
        sources=[{"filename": "sop-001.html", "title": "后端服务 On-Call SOP"}],
        trace=[],
    )

    assert result["answer"] != "OnCallAgent completed with runtime status: finished."
    assert "runtime status" not in result["answer"]


def test_agent_calls_answer_composer_after_runtime_finish() -> None:
    class RecordingComposer:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def compose(self, user_query, retrieved_docs, sources, trace):
            self.calls.append(
                {
                    "user_query": user_query,
                    "retrieved_docs": retrieved_docs,
                    "sources": sources,
                    "trace": trace,
                }
            )
            return {
                "answer": "问题判断：根据 SOP 给出建议。",
                "sources": sources,
                "trace": trace,
                "mode": "agent",
            }

    def planner(_: str, __: str) -> PlannerResult:
        return PlannerResult(
            ok=True,
            retry=False,
            action={"action": "tool", "tool": "readFile", "args": {"fname": "manifest.json"}},
            error=None,
            trace=[{"stage": "planner", "event": "valid_action"}],
        )

    composer = RecordingComposer()
    result = run_agent_once("服务 OOM 了怎么办？", planner=planner, answer_composer=composer)

    assert composer.calls
    assert composer.calls[0]["user_query"] == "服务 OOM 了怎么办？"
    assert composer.calls[0]["retrieved_docs"]
    assert composer.calls[0]["retrieved_docs"][0]["filename"] == "sop-001.html"
    assert result["answer"] == "问题判断：根据 SOP 给出建议。"
    assert result["sources"]
    assert result["sources"][0]["id"] == "sop-001"
    assert result["mode"] == "agent"


def test_oncall_api_uses_agent_composed_answer(monkeypatch) -> None:
    def fake_run_agent_once(query: str):
        return {
            "ok": True,
            "answer": "问题判断：根据 SOP 先检查内存限制。",
            "sources": [{"filename": "sop-001.html", "title": "后端服务 On-Call SOP"}],
            "trace": [{"stage": "agent", "event": "tool_allowed"}],
            "runtime": {"status": "finished", "trace": [{"step": 0}]},
        }

    monkeypatch.setattr("app.api.run_agent_once", fake_run_agent_once)

    response = TestClient(app).post("/api/oncall/query", json={"query": "服务 OOM 了怎么办？"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "问题判断：根据 SOP 先检查内存限制。"
    assert "runtime status" not in payload["answer"]
    assert payload["sources"] == [{"filename": "sop-001.html", "title": "后端服务 On-Call SOP"}]
