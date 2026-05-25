from typing import Any, Protocol


INSUFFICIENT_EVIDENCE_ANSWER = "当前没有足够的 SOP 文档支持判断，请补充相关日志、错误信息或 SOP 文档。"


class AnswerLLMClient(Protocol):
    def generate(self, prompt: str) -> str:
        ...


class DeterministicAnswerLLMClient:
    def generate(self, prompt: str) -> str:
        return (
            "问题判断：已根据提供的 SOP 文档整理可执行的 on-call 判断。\n"
            "优先检查项：先核对告警、最近变更、关键服务状态和相关资源指标。\n"
            "建议操作：按引用 SOP 中的步骤逐项排查，必要时升级到对应值班团队。\n"
            "不确定项：如果缺少日志、时间窗口或影响范围，需要继续补充证据。\n"
            "引用来源：见 sources。"
        )


class AnswerComposer:
    def __init__(self, llm_client: AnswerLLMClient | None = None) -> None:
        self._llm_client = llm_client or DeterministicAnswerLLMClient()

    def compose(
        self,
        user_query: str,
        retrieved_docs: list[dict[str, Any]],
        sources: list[dict[str, Any]],
        trace: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not retrieved_docs:
            return {
                "answer": INSUFFICIENT_EVIDENCE_ANSWER,
                "sources": [],
                "trace": trace,
                "mode": "agent",
            }

        prompt = _build_answer_prompt(user_query, retrieved_docs, sources)
        answer = self._llm_client.generate(prompt)
        return {
            "answer": answer,
            "sources": sources,
            "trace": trace,
            "mode": "agent",
        }


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
