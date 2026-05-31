import re
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

    def generate(self, prompt: str) -> str:
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

        prompt = _build_answer_prompt(user_query, retrieved_docs, sources)
        answer_trace.append(
            {
                "stage": "answer_composer",
                "event": "prompt_built",
                "retrieved_doc_count": len(retrieved_docs),
                "source_count": len(sources),
                "prompt_chars": len(prompt),
            }
        )
        answer, generation_trace = _generate_llm_answer(self._llm_client, prompt)
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
    return adapter, [
        {
            "stage": "answer_composer",
            "event": "llm_client_created",
            "client_type": type(selected_client).__name__,
        }
    ]


def _generate_llm_answer(llm_client: AnswerLLMClient | None, prompt: str) -> tuple[str, list[dict[str, Any]]]:
    if llm_client is None:
        return "", [
            {
                "stage": "answer_composer",
                "event": "llm_call_skipped",
                "reason": "no_llm_client",
            }
        ]
    try:
        trace = [
            {
                "stage": "answer_composer",
                "event": "llm_call_started",
                "client_type": type(llm_client).__name__,
            }
        ]
        answer = llm_client.generate(prompt).strip()
    except Exception as error:
        return "", [
            {
                "stage": "answer_composer",
                "event": "llm_call_failed",
                "error_type": type(error).__name__,
                "error": _safe_error_message(error),
            }
        ]
    if not answer or "runtime status" in answer:
        trace.append(
            {
                "stage": "answer_composer",
                "event": "llm_answer_rejected",
                "reason": "empty_or_runtime_status",
            }
        )
        return "", trace
    trace.append(
        {
            "stage": "answer_composer",
            "event": "llm_call_succeeded",
            "answer_mode": "llm",
            "answer_chars": len(answer),
        }
    )
    return answer, trace


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
) -> str:
    documents_text = "\n\n".join(_format_document(document) for document in retrieved_docs)
    sources_text = "\n".join(
        f"- filename: {source.get('filename', '')}; title: {source.get('title', '')}"
        for source in sources
    )
    return f"""
你是 OnCall 问题分析助手。
只能使用 provided documents 回答用户问题。
不允许编造来源。
不输出工具调用过程。
不输出 runtime status。
如果证据不足，明确说明缺失信息。

回答必须包含：
- 问题判断
- 优先检查项
- 建议操作
- 不确定项
- 引用来源

user_query:
{user_query}

provided documents:
{documents_text}

provided sources:
{sources_text}
""".strip()


def _format_document(document: dict[str, Any]) -> str:
    content = document.get("content")
    if content is None:
        content = document.get("cleaned_text", "")
    return (
        f"filename: {document.get('filename', '')}\n"
        f"title: {document.get('title', '')}\n"
        f"content:\n{content}"
    )
