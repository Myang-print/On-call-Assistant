import re
import time
from datetime import datetime, timezone
from typing import Any, Protocol

from app.llm_client import DeterministicLLMClient
from app.llm_client import LLMClient as SelectedLLMClient
from app.llm_client import select_llm_client


INSUFFICIENT_EVIDENCE_ANSWER = "当前没有足够的 SOP 文档支持判断，请补充相关日志、错误信息或 SOP 文档。"


class AnswerLLMClient(Protocol):
    def generate(self, prompt: str) -> str:
        ...


class DeterministicAnswerLLMClient:
    def generate(self, prompt: str) -> str:
        return prompt


class CompleteToGenerateAdapter:
    def __init__(self, llm_client: SelectedLLMClient) -> None:
        self._llm_client = llm_client
        self.last_metadata: dict[str, Any] = {}
        self.timeout_seconds = getattr(llm_client, "timeout", None)
        self.max_tokens = getattr(llm_client, "max_tokens", None)

    def generate(self, prompt: str) -> str:
        if hasattr(self._llm_client, "complete_with_metadata"):
            completion = self._llm_client.complete_with_metadata(prompt)
            self.last_metadata = {
                "finish_reason": getattr(completion, "finish_reason", None),
                "raw_llm_answer_chars": getattr(completion, "raw_answer_chars", len(completion.content)),
            }
            return completion.content
        return self._llm_client.complete(prompt)


class AnswerComposer:
    def __init__(self, llm_client: AnswerLLMClient | None = None) -> None:
        if llm_client is not None:
            self._llm_client = llm_client
            self._init_trace = [
                {
                    "stage": "answer_composer",
                    "event": "llm_client_injected",
                    "client_type": type(llm_client).__name__,
                }
            ]
        else:
            self._llm_client, self._init_trace = _default_answer_llm_client()

    def compose(
        self,
        user_query: str,
        retrieved_docs: list[dict[str, Any]],
        sources: list[dict[str, Any]],
        trace: list[dict[str, Any]],
    ) -> dict[str, Any]:
        answer_trace = list(self._init_trace)
        if not retrieved_docs:
            answer_trace.append(
                {
                    "stage": "answer_composer",
                    "event": "insufficient_evidence",
                    "answer_mode": "insufficient_evidence",
                }
            )
            return {
                "answer": INSUFFICIENT_EVIDENCE_ANSWER,
                "sources": [],
                "trace": trace,
                "answer_trace": answer_trace,
                "mode": "agent",
            }

        prompt, prompt_metadata = _build_answer_prompt(user_query, retrieved_docs, sources)
        answer_trace.append(
            {
                "stage": "answer_composer",
                "event": "prompt_built",
                **prompt_metadata,
            }
        )
        answer, generation_trace = _generate_llm_answer(self._llm_client, prompt, prompt_metadata)
        answer_trace.extend(generation_trace)
        if not answer:
            answer = _compose_deterministic_answer(user_query, retrieved_docs, sources)
            answer_trace.append(
                {
                    "stage": "answer_composer",
                    "event": "deterministic_fallback",
                    "answer_mode": "deterministic_fallback",
                }
            )
        return {
            "answer": answer,
            "sources": sources,
            "trace": trace,
            "answer_trace": answer_trace,
            "mode": "agent",
        }


def _default_answer_llm_client() -> tuple[AnswerLLMClient | None, list[dict[str, Any]]]:
    try:
        selected_client = select_llm_client()
    except ValueError as error:
        return None, [
            {
                "stage": "answer_composer",
                "event": "llm_client_unavailable",
                "error_type": type(error).__name__,
                "error": _safe_error_message(error),
            }
        ]
    if isinstance(selected_client, DeterministicLLMClient):
        return None, [
            {
                "stage": "answer_composer",
                "event": "llm_client_disabled",
                "provider": "deterministic",
            }
        ]
    adapter = CompleteToGenerateAdapter(selected_client)
    client_trace: dict[str, Any] = {
        "stage": "answer_composer",
        "event": "llm_client_created",
        "client_type": type(selected_client).__name__,
    }
    if hasattr(selected_client, "timeout"):
        client_trace["timeout_seconds"] = getattr(selected_client, "timeout")
    if hasattr(selected_client, "max_tokens"):
        client_trace["max_tokens"] = getattr(selected_client, "max_tokens")
    if hasattr(selected_client, "thinking"):
        client_trace["thinking"] = getattr(selected_client, "thinking")
    return adapter, [client_trace]


def _generate_llm_answer(
    llm_client: AnswerLLMClient | None,
    prompt: str,
    prompt_metadata: dict[str, Any],
) -> tuple[str, list[dict[str, Any]]]:
    if llm_client is None:
        return "", [
            {
                "stage": "answer_composer",
                "event": "llm_call_skipped",
                "reason": "no_llm_client",
            }
        ]
    started_at = _utc_now_iso()
    started_perf = time.perf_counter()
    trace = [
        {
            "stage": "answer_composer",
            "event": "llm_call_started",
            "client_type": type(llm_client).__name__,
            "request_started_at": started_at,
            **_llm_request_diagnostics(llm_client, prompt_metadata),
        }
    ]
    try:
        answer = llm_client.generate(prompt).strip()
    except Exception as error:
        elapsed_seconds = _elapsed_seconds(started_perf)
        trace.append(
            {
                "stage": "answer_composer",
                "event": "llm_call_failed",
                "error_type": type(error).__name__,
                "error": _safe_error_message(error),
                "request_started_at": started_at,
                "request_ended_at": _utc_now_iso(),
                "elapsed_seconds": elapsed_seconds,
                **_llm_request_diagnostics(llm_client, prompt_metadata),
            }
        )
        return "", [
            *trace,
        ]
    elapsed_seconds = _elapsed_seconds(started_perf)
    if not answer or "runtime status" in answer:
        trace.append(
            {
                "stage": "answer_composer",
                "event": "llm_answer_rejected",
                "reason": _answer_rejection_reason(llm_client, answer),
                "request_started_at": started_at,
                "request_ended_at": _utc_now_iso(),
                "elapsed_seconds": elapsed_seconds,
                **_llm_request_diagnostics(llm_client, prompt_metadata),
                **_llm_completion_diagnostics(llm_client, answer),
            }
        )
        return "", trace
    trace.append(
        {
            "stage": "answer_composer",
            "event": "llm_call_succeeded",
            "answer_mode": "llm",
            "answer_chars": len(answer),
            "final_answer_chars": len(answer),
            "request_started_at": started_at,
            "request_ended_at": _utc_now_iso(),
            "elapsed_seconds": elapsed_seconds,
            **_llm_request_diagnostics(llm_client, prompt_metadata),
            **_llm_completion_diagnostics(llm_client, answer),
        }
    )
    return answer, trace


def _answer_rejection_reason(llm_client: AnswerLLMClient, answer: str) -> str:
    metadata = getattr(llm_client, "last_metadata", {})
    if not answer and isinstance(metadata, dict) and metadata.get("finish_reason") == "length":
        return "max_tokens_exhausted_before_visible_answer"
    if not answer:
        return "empty_answer"
    return "runtime_status"


def _llm_request_diagnostics(llm_client: AnswerLLMClient, prompt_metadata: dict[str, Any]) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {
        "prompt_chars": prompt_metadata.get("prompt_chars", 0),
    }
    if hasattr(llm_client, "timeout_seconds"):
        diagnostics["timeout_seconds"] = getattr(llm_client, "timeout_seconds")
    if hasattr(llm_client, "max_tokens"):
        diagnostics["max_tokens"] = getattr(llm_client, "max_tokens")
    return diagnostics


def _llm_completion_diagnostics(llm_client: AnswerLLMClient, answer: str) -> dict[str, Any]:
    metadata = getattr(llm_client, "last_metadata", {})
    diagnostics: dict[str, Any] = {
        "raw_llm_answer_chars": len(answer),
    }
    if isinstance(metadata, dict):
        if metadata.get("finish_reason") is not None:
            diagnostics["finish_reason"] = metadata.get("finish_reason")
        if metadata.get("raw_llm_answer_chars") is not None:
            diagnostics["raw_llm_answer_chars"] = metadata.get("raw_llm_answer_chars")
    return diagnostics


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _elapsed_seconds(started_perf: float) -> float:
    return round(time.perf_counter() - started_perf, 3)


def _safe_error_message(error: Exception) -> str:
    message = str(error)
    if len(message) > 240:
        message = message[:240] + "..."
    return message.replace("\n", " ")


def moonshot_answer_client() -> AnswerLLMClient:
    return CompleteToGenerateAdapter(select_llm_client(provider="moonshot"))


def _compose_deterministic_answer(
    user_query: str,
    retrieved_docs: list[dict[str, Any]],
    sources: list[dict[str, Any]],
) -> str:
    evidence = _collect_relevant_evidence(user_query, retrieved_docs)
    filenames = [str(source.get("filename", "")) for source in sources if source.get("filename")]
    source_lines = [
        f"- {source.get('filename', '')}: {source.get('title', '')}"
        for source in sources
        if source.get("filename")
    ]

    if not evidence:
        evidence = _fallback_evidence(retrieved_docs)
    actions = _action_evidence(user_query, evidence)

    return "\n".join(
        [
            f"问题判断：根据 {', '.join(filenames)}，当前问题可按已读取 SOP 进行排查。",
            "优先检查项：",
            *_format_bullets(evidence[:5]),
            "建议操作：",
            *_format_bullets(actions),
            "不确定项：如果缺少日志、时间窗口、影响范围或最近变更记录，需要先补齐这些证据再扩大处置。",
            "引用来源：",
            *source_lines,
        ]
    )


def _collect_relevant_evidence(user_query: str, retrieved_docs: list[dict[str, Any]]) -> list[str]:
    terms = _query_terms(user_query)
    scored: list[tuple[int, int, str]] = []
    order = 0
    for document in retrieved_docs:
        content = str(document.get("content") or document.get("cleaned_text") or "")
        for sentence in _split_sentences(content):
            score = _score_sentence(sentence, terms)
            if score > 0:
                scored.append((score, -order, sentence))
            order += 1
    scored.sort(reverse=True)
    return _deduplicate_sentence(sentence for _, __, sentence in scored)


def _query_terms(user_query: str) -> list[str]:
    folded = user_query.casefold()
    terms = re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*|[\u4e00-\u9fff]{2,}", user_query)
    if "oom" in folded or "内存" in user_query:
        terms.extend(["OOM", "OutOfMemoryError", "内存", "堆内存", "JVM", "Xmx", "Pod", "Kubernetes", "扩容", "回滚", "发布", "配置变更"])
    if "主从" in user_query or "延迟" in user_query:
        terms.extend(["主从延迟", "数据库", "复制", "延迟", "DBA", "慢查询"])
    if "入侵" in user_query or "黑客" in user_query or "攻击" in user_query:
        terms.extend(["安全", "入侵", "DDoS", "封禁", "隔离", "漏洞"])
    if "推荐" in user_query or "质量下降" in user_query:
        terms.extend(["模型", "推荐", "质量", "GPU", "算法", "特征", "回滚"])
    return _deduplicate_sentence(term for term in terms if len(term) >= 2)


def _score_sentence(sentence: str, terms: list[str]) -> int:
    folded_sentence = sentence.casefold()
    score = 0
    for term in terms:
        if term.casefold() in folded_sentence:
            score += 1
    if any(word in sentence for word in ["首先", "检查", "确认", "查看", "保存", "扩容", "回滚", "降级", "升级", "立即"]):
        score += 2
    return score


def _split_sentences(content: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", content).strip()
    parts = re.split(r"(?<=[。！？；])\s*", normalized)
    return [part.strip() for part in parts if part.strip()]


def _action_evidence(user_query: str, evidence: list[str]) -> list[str]:
    action_words = ["检查", "查看", "保存", "扩容", "回滚", "降级", "升级", "确认", "分析"]
    actions = [sentence for sentence in evidence if any(word in sentence for word in action_words)]
    critical_actions = _critical_action_coverage(user_query, evidence)
    merged = _deduplicate_sentence([*critical_actions, *actions])
    return merged[:7] if merged else evidence[:5]


def _critical_action_coverage(user_query: str, evidence: list[str]) -> list[str]:
    folded = user_query.casefold()
    if "oom" not in folded and "内存" not in user_query:
        return []

    keyword_groups = [
        ["JVM监控面板", "堆内存", "内存增长曲线"],
        ["代码发布", "配置变更", "最近是否有"],
        ["扩容", "Pod副本数"],
        ["回滚", "稳定版本"],
        ["Xmx", "启动参数"],
    ]
    covered: list[str] = []
    for keywords in keyword_groups:
        matches = [
            (sum(1 for keyword in keywords if keyword in sentence), -index, sentence)
            for index, sentence in enumerate(evidence)
            if any(keyword in sentence for keyword in keywords)
        ]
        match = max(matches)[2] if matches else None
        if match:
            covered.append(match)
    return _deduplicate_sentence(covered)


def _fallback_evidence(retrieved_docs: list[dict[str, Any]]) -> list[str]:
    sentences: list[str] = []
    for document in retrieved_docs:
        content = str(document.get("content") or document.get("cleaned_text") or "")
        sentences.extend(_split_sentences(content)[:3])
    return _deduplicate_sentence(sentences)[:5]


def _format_bullets(items: list[str]) -> list[str]:
    if not items:
        return ["- 已读取 SOP，但没有抽取到足够具体的处置步骤。"]
    return [f"- {item}" for item in items]


def _deduplicate_sentence(items: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        value = str(item).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _build_answer_prompt(
    user_query: str,
    retrieved_docs: list[dict[str, Any]],
    sources: list[dict[str, Any]],
) -> tuple[str, dict[str, Any]]:
    documents_text, excerpt_metadata = _format_relevant_documents(user_query, retrieved_docs)
    sources_text = "\n".join(
        f"- filename: {source.get('filename', '')}; title: {source.get('title', '')}"
        for source in sources
    )
    prompt = f"""
你是 OnCall 问题分析助手。
请基于提供的SOP内容回答。
只能使用 provided documents 回答用户问题。
不允许编造来源。
不输出工具调用过程。
不输出 runtime status。
如果证据不足，明确说明缺失信息。
必须把 provided documents 中的具体事实转写进回答，例如指标、命令、回滚、扩容、隔离、升级或排查条件。

输出格式：

1. 问题判断
2. 检查项（最多3条）
3. 操作步骤（最多5步）
4. 升级条件

总长度不超过250字。

user_query:
{user_query}

provided documents:
{documents_text}

provided sources:
{sources_text}
""".strip()
    return prompt, {
        "retrieved_doc_count": len(retrieved_docs),
        "source_count": len(sources),
        "prompt_chars": len(prompt),
        "source_content_chars": excerpt_metadata["source_content_chars"],
        "excerpt_count": excerpt_metadata["excerpt_count"],
        "prompt_strategy": "relevant_excerpts",
    }


def _format_relevant_documents(user_query: str, retrieved_docs: list[dict[str, Any]]) -> tuple[str, dict[str, int]]:
    source_content_chars = 0
    excerpt_count = 0
    formatted_documents: list[str] = []
    for document in retrieved_docs:
        content = _document_content(document)
        source_content_chars += len(content)
        excerpts = _document_relevant_excerpts(user_query, content)
        excerpt_count += len(excerpts)
        formatted_documents.append(_format_document(document, excerpts))
    return "\n\n".join(formatted_documents), {
        "source_content_chars": source_content_chars,
        "excerpt_count": excerpt_count,
    }


def _document_content(document: dict[str, Any]) -> str:
    content = document.get("content")
    if content is None:
        content = document.get("cleaned_text", "")
    return str(content)


def _document_relevant_excerpts(user_query: str, content: str, max_excerpts: int = 8) -> list[str]:
    sentences = _split_sentences(content)
    terms = _query_terms(user_query)
    scored: list[tuple[int, int, str]] = []
    for index, sentence in enumerate(sentences):
        score = _score_sentence(sentence, terms)
        if score > 0:
            scored.append((score, -index, sentence))
    scored.sort(reverse=True)
    excerpts = _deduplicate_sentence(sentence for _, __, sentence in scored[:max_excerpts])
    if excerpts:
        return excerpts
    return _deduplicate_sentence(sentences[:3])


def _format_document(document: dict[str, Any], excerpts: list[str]) -> str:
    return (
        f"filename: {document.get('filename', '')}\n"
        f"title: {document.get('title', '')}\n"
        "relevant_content:\n"
        + "\n".join(f"- {excerpt}" for excerpt in excerpts)
    )
