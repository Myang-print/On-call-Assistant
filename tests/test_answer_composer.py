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
    assert "请基于提供的SOP内容回答" in llm.prompts[0]
    assert "1. 问题判断" in llm.prompts[0]
    assert "2. 检查项（最多3条）" in llm.prompts[0]
    assert "3. 操作步骤（最多5步）" in llm.prompts[0]
    assert "4. 升级条件" in llm.prompts[0]
    assert "总长度不超过250字" in llm.prompts[0]
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


def test_llm_failure_trace_records_elapsed_time() -> None:
    class TimeoutLLM:
        timeout_seconds = 25.0
        max_tokens = 400

        def generate(self, prompt: str) -> str:
            raise TimeoutError("request timed out")

    result = AnswerComposer(TimeoutLLM()).compose(
        user_query="服务 OOM 了怎么办？",
        retrieved_docs=[
            {
                "filename": "sop-001.html",
                "title": "后端服务 On-Call SOP",
                "content": "查看JVM监控面板确认堆内存增长曲线。紧急情况下可先回滚到上一个稳定版本。",
            }
        ],
        sources=[{"filename": "sop-001.html", "title": "后端服务 On-Call SOP"}],
        trace=[],
    )

    failed_trace = next(item for item in result["answer_trace"] if item["event"] == "llm_call_failed")
    assert failed_trace["error_type"] == "TimeoutError"
    assert isinstance(failed_trace["elapsed_seconds"], float)
    assert failed_trace["elapsed_seconds"] >= 0
    assert failed_trace["prompt_chars"] > 0
    assert failed_trace["timeout_seconds"] == 25.0
    assert failed_trace["max_tokens"] == 400
    assert "request_started_at" in failed_trace
    assert "request_ended_at" in failed_trace


def test_llm_success_trace_records_raw_and_final_answer_lengths_and_finish_reason() -> None:
    class MetadataLLM:
        timeout_seconds = 30.0
        max_tokens = 120
        last_metadata: dict[str, object] = {}

        def generate(self, prompt: str) -> str:
            self.last_metadata = {
                "finish_reason": "length",
                "raw_llm_answer_chars": 8,
            }
            return "  自然语言回答  "

    result = AnswerComposer(MetadataLLM()).compose(
        user_query="服务 OOM 了怎么办？",
        retrieved_docs=[
            {
                "filename": "sop-001.html",
                "title": "后端服务 On-Call SOP",
                "content": "查看JVM监控面板确认堆内存增长曲线。",
            }
        ],
        sources=[{"filename": "sop-001.html", "title": "后端服务 On-Call SOP"}],
        trace=[],
    )

    success_trace = next(item for item in result["answer_trace"] if item["event"] == "llm_call_succeeded")
    assert success_trace["finish_reason"] == "length"
    assert success_trace["raw_llm_answer_chars"] == 8
    assert success_trace["final_answer_chars"] == len("自然语言回答")
    assert success_trace["answer_chars"] == len("自然语言回答")
    assert success_trace["timeout_seconds"] == 30.0
    assert success_trace["max_tokens"] == 120


def test_empty_llm_answer_with_length_finish_reason_reports_token_exhaustion() -> None:
    class EmptyLengthLLM:
        timeout_seconds = 30.0
        max_tokens = 400
        last_metadata = {
            "finish_reason": "length",
            "raw_llm_answer_chars": 0,
        }

        def generate(self, prompt: str) -> str:
            return ""

    result = AnswerComposer(EmptyLengthLLM()).compose(
        user_query="数据库主从延迟超过30秒怎么办？",
        retrieved_docs=[
            {
                "filename": "sop-002.html",
                "title": "数据库DBA On-Call SOP",
                "content": "主从复制延迟时检查复制线程状态、GTID差异和SHOW SLAVE STATUS输出。",
            }
        ],
        sources=[{"filename": "sop-002.html", "title": "数据库DBA On-Call SOP"}],
        trace=[],
    )

    rejection_trace = next(item for item in result["answer_trace"] if item["event"] == "llm_answer_rejected")
    assert rejection_trace["reason"] == "max_tokens_exhausted_before_visible_answer"
    assert rejection_trace["finish_reason"] == "length"
    assert rejection_trace["raw_llm_answer_chars"] == 0
    assert any(item.get("answer_mode") == "deterministic_fallback" for item in result["answer_trace"])


def test_prompt_uses_relevant_excerpts_instead_of_full_sop_content() -> None:
    llm = RecordingLLM("问题判断：根据 sop-001.html 处理 OOM。")
    irrelevant_block = "这是一段与告警无关的背景描述。" * 500
    relevant_sentence = "Java服务出现OutOfMemoryError时，检查最近是否有代码发布或配置变更。"

    result = AnswerComposer(llm).compose(
        user_query="服务 OOM 了怎么办？",
        retrieved_docs=[
            {
                "filename": "sop-001.html",
                "title": "后端服务 On-Call SOP",
                "content": f"{irrelevant_block}{relevant_sentence}",
            }
        ],
        sources=[{"filename": "sop-001.html", "title": "后端服务 On-Call SOP"}],
        trace=[],
    )

    prompt = llm.prompts[0]
    prompt_trace = next(item for item in result["answer_trace"] if item["event"] == "prompt_built")
    assert relevant_sentence in prompt
    assert len(prompt) < len(irrelevant_block)
    assert prompt_trace["prompt_strategy"] == "relevant_excerpts"
    assert prompt_trace["source_content_chars"] > prompt_trace["prompt_chars"]
    assert prompt_trace["excerpt_count"] >= 1


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
