import math
import os
from functools import lru_cache
from typing import Protocol

from app.models import Document
from app.semantic_search import semantic_search_documents


BGE_M3_MODEL_NAME = "BAAI/bge-m3"
EMBEDDING_ENABLED_ENV = "ONCALL_ENABLE_EMBEDDING"
SNIPPET_MAX_LENGTH = 80


class EmbeddingModel(Protocol):
    def encode(self, texts: list[str]) -> list[list[float]]:
        ...


def embedding_search_with_fallback(
    documents: list[Document],
    query: str,
    dictionary: dict[str, list[str]],
    model: EmbeddingModel | None = None,
    embedding_enabled: bool | None = None,
) -> list[dict[str, object]]:
    enabled = is_embedding_enabled() if embedding_enabled is None else embedding_enabled
    if model is None and not enabled:
        return semantic_search_documents(documents, query, dictionary)

    try:
        embedding_model = model if model is not None else _load_default_embedding_model()
        return rank_documents_by_embeddings(documents, query, embedding_model)
    except Exception:
        return semantic_search_documents(documents, query, dictionary)


def is_embedding_enabled() -> bool:
    return os.getenv(EMBEDDING_ENABLED_ENV, "").casefold() in {"1", "true", "yes", "on"}


def rank_documents_by_embeddings(
    documents: list[Document],
    query: str,
    model: EmbeddingModel,
) -> list[dict[str, object]]:
    normalized_query = query.strip()
    if not normalized_query:
        return []

    texts = [normalized_query] + [_document_embedding_text(document) for document in documents]
    embeddings = model.encode(texts)
    query_embedding = embeddings[0]
    document_embeddings = embeddings[1:]

    results: list[dict[str, object]] = []
    for document, document_embedding in zip(documents, document_embeddings):
        score = _cosine_similarity(query_embedding, document_embedding)
        if score > 0:
            results.append(
                {
                    "id": document.doc_id,
                    "title": document.title,
                    "snippet": _make_snippet(document.cleaned_text),
                    "score": score,
                }
            )

    return sorted(results, key=lambda result: (-float(result["score"]), str(result["id"])))


@lru_cache(maxsize=1)
def _load_default_embedding_model() -> EmbeddingModel:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(BGE_M3_MODEL_NAME)


def _document_embedding_text(document: Document) -> str:
    return f"{document.title}\n{document.cleaned_text}"


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    dot_product = sum(left_value * right_value for left_value, right_value in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0

    return dot_product / (left_norm * right_norm)


def _make_snippet(text: str) -> str:
    return text[:SNIPPET_MAX_LENGTH]
