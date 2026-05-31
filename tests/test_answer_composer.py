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
        "answer_trace": [
            {"stage": "answer_composer", "event": "llm_client_injected", "client_type": "RecordingLLM"},
            {
                "stage": "answer_composer",
                "event": "insufficient_evidence",
                "answer_mode": "insufficient_evidence",
            },
        ],
        "mode": "agent",
    }


def test_compose_calls_llm_with_retrieved_doc_prompt_when_docs_are_available() -> None:
    llm = RecordingLLM(
        "问题判断：这是基于 sop-001.html 的回答。建议查看JVM监控面板、检查最近发布、扩容Pod、必要时回滚并确认Xmx。"
    )

    result = AnswerComposer(llm).compose(
        user_query="服务 OOM 了怎么办？",
        retrieved_docs=[
            {
                "filename": "sop-001.html",
                "title": "后端服务 On-Call SOP",
                "content": (
                    "Java服务出现OutOfMemoryError时，Kubernetes会自动重启Pod。"
                    "值班人员需在重启后立即保存堆转储文件用于后续分析。"
                    "检查最近是否有代码发布或配置变更，查看JVM监控面板确认堆内存增长曲线。"
                    "如果是突发流量导致，需临时扩容Pod副本数。"
                    "紧急情况下可先回滚到上一个稳定版本。"
                    "OOM频繁发生时需检查JVM启动参数，确认Xmx设置是否合理。"
                ),
            }
        ],
        sources=[{"filename": "sop-001.html", "title": "后端服务 On-Call SOP"}],
        trace=[{"step": 0}],
    )

    logger.info("llm_answer=%s prompt=%s", result, llm.prompts)
    assert len(llm.prompts) == 1
    assert "你是 OnCall 问题分析助手" in llm.prompts[0]
    assert "只能使用 provided documents" in llm.prompts[0]
    assert "不允许编造来源" in llm.prompts[0]
    assert "服务 OOM 了怎么办？" in llm.prompts[0]
    assert "sop-001.html" in llm.prompts[0]
    assert "Java服务出现OutOfMemoryError时，Kubernetes会自动重启Pod" in llm.prompts[0]
    assert "紧急情况下可先回滚到上一个稳定版本" in llm.prompts[0]
    assert "查看JVM监控面板" in result["answer"]
    assert "回滚" in result["answer"]
    assert "sop-001.html" in result["answer"]
    assert any(item["event"] == "llm_call_succeeded" for item in result["answer_trace"])
    assert any(item.get("answer_mode") == "llm" for item in result["answer_trace"])


def test_compose_falls_back_to_deterministic_summary_when_llm_fails() -> None:
    class FailingLLM:
        def generate(self, prompt: str) -> str:
            raise RuntimeError("llm unavailable")

    result = AnswerComposer(FailingLLM()).compose(
        user_query="服务 OOM 了怎么办？",
        retrieved_docs=[
            {
                "filename": "sop-001.html",
                "title": "后端服务 On-Call SOP",
                "content": (
                    "检查最近是否有代码发布或配置变更，查看JVM监控面板确认堆内存增长曲线。"
                    "如果是突发流量导致，需临时扩容Pod副本数。"
                    "紧急情况下可先回滚到上一个稳定版本。"
                    "OOM频繁发生时需检查JVM启动参数，确认Xmx设置是否合理。"
                ),
            }
        ],
        sources=[{"filename": "sop-001.html", "title": "后端服务 On-Call SOP"}],
        trace=[{"step": 0}],
    )

    assert "查看JVM监控面板" in result["answer"]
    assert "回滚到上一个稳定版本" in result["answer"]
    assert "sop-001.html" in result["answer"]
    assert "见 sources" not in result["answer"]
    assert any(item["event"] == "llm_call_failed" for item in result["answer_trace"])
    assert any(item.get("answer_mode") == "deterministic_fallback" for item in result["answer_trace"])


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


def test_agent_api_can_return_llm_composed_answer_from_readfile_docs(monkeypatch) -> None:
    class PromptAwareLLM:
        def __init__(self) -> None:
            self.prompts: list[str] = []

        def generate(self, prompt: str) -> str:
            self.prompts.append(prompt)
            assert "filename: sop-001.html" in prompt
            assert "Java服务出现OutOfMemoryError" in prompt
            return "LLM回答：根据 sop-001.html，先确认内存曲线和最近发布，必要时扩容或回滚。"

    llm = PromptAwareLLM()
    monkeypatch.setattr("app.agent.AnswerComposer", lambda: AnswerComposer(llm))

    response = TestClient(app).post("/api/oncall/query", json={"query": "Java 服务内存爆了怎么处理？"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "LLM回答：根据 sop-001.html，先确认内存曲线和最近发布，必要时扩容或回滚。"
    assert llm.prompts
    assert payload["sources"]
    assert payload["trace"]
    assert any(item["event"] == "llm_call_succeeded" for item in payload["trace"])


def test_agent_oom_api_answer_contains_specific_sop_steps() -> None:
    response = TestClient(app).post("/api/oncall/query", json={"query": "服务 OOM 了怎么办？"})

    assert response.status_code == 200
    payload = response.json()
    assert "查看JVM监控面板" in payload["answer"]
    assert "检查最近是否有代码发布或配置变更" in payload["answer"]
    assert "临时扩容Pod副本数" in payload["answer"]
    assert "回滚到上一个稳定版本" in payload["answer"]
    assert "Xmx设置是否合理" in payload["answer"]
    assert "sop-001.html" in payload["answer"]
    assert "sop-007.html" in payload["answer"]
    assert "见 sources" not in payload["answer"]


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


def test_agent_does_not_use_side_channel_retrieval_when_runtime_has_no_docs(monkeypatch) -> None:
    class RecordingComposer:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def compose(self, user_query, retrieved_docs, sources, trace):
            self.calls.append(
                {
                    "retrieved_docs": retrieved_docs,
                    "sources": sources,
                    "trace": trace,
                }
            )
            return {
                "answer": "当前没有足够的 SOP 文档支持判断，请补充相关日志、错误信息或 SOP 文档。",
                "sources": sources,
                "trace": trace,
                "mode": "agent",
            }

    def runtime_without_evidence(**_: object):
        return {
            "status": "finished",
            "trace": [{"step": 0, "action": {"type": "readFile", "fname": "manifest.json"}, "observation": {"ok": True}}],
            "retrieved_docs": [],
            "sources": [],
        }

    def planner(_: str, __: str) -> PlannerResult:
        return PlannerResult(
            ok=True,
            retry=False,
            action={"action": "tool", "tool": "readFile", "args": {"fname": "manifest.json"}},
            error=None,
            trace=[],
        )

    composer = RecordingComposer()
    monkeypatch.setattr("app.agent.run_deterministic_agent", runtime_without_evidence)

    result = run_agent_once("服务 OOM 了怎么办？", planner=planner, answer_composer=composer)

    assert composer.calls[0]["retrieved_docs"] == []
    assert composer.calls[0]["sources"] == []
    assert result["sources"] == []


def test_oncall_api_uses_agent_composed_answer(monkeypatch) -> None:
    def fake_run_agent_once(query: str, **_: object):
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
