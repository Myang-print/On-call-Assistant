from typing import Any

from app.bm25_retriever import bm25_rank
from app.models import Document
from app.reranker import deterministic_rerank
from app.semantic_search import expand_query
from eval.metrics import mean_reciprocal_rank, recall_at_k


EMBEDDING_DISABLED_WEIGHTS = {"bm25": 0.7, "rule": 0.3, "embedding": 0.0}
EMBEDDING_DEFAULT_WEIGHTS = {"bm25": 0.5, "rule": 0.2, "embedding": 0.3}
SNIPPET_MAX_LENGTH = 80


def normalize_scores(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}

    min_score = min(scores.values())
    max_score = max(scores.values())
    if max_score == min_score:
        return {doc_id: 1.0 for doc_id in scores}

    return {
        doc_id: (score - min_score) / (max_score - min_score)
        for doc_id, score in scores.items()
    }


def hybrid_search_documents(
    documents: list[Document],
    query: str,
    dictionary: dict[str, list[str]],
    embedding_scores: dict[str, float] | None = None,
    weights: dict[str, float] | None = None,
) -> list[dict[str, object]]:
    expanded_terms = expand_query(query, dictionary)
    if not expanded_terms:
        return []

    embedding_available = embedding_scores is not None
    selected_weights = weights or (
        EMBEDDING_DEFAULT_WEIGHTS if embedding_available else EMBEDDING_DISABLED_WEIGHTS
    )
    bm25_scores = normalize_scores(_bm25_scores(documents, expanded_terms))
    rule_scores = normalize_scores(_rule_scores(documents, expanded_terms))
    normalized_embedding_scores = normalize_scores(embedding_scores or {})
    all_doc_ids = set(bm25_scores) | set(rule_scores) | set(normalized_embedding_scores)

    results: list[dict[str, object]] = []
    documents_by_id = {document.doc_id: document for document in documents}
    for doc_id in all_doc_ids:
        document = documents_by_id[doc_id]
        score = (
            selected_weights["bm25"] * bm25_scores.get(doc_id, 0.0)
            + selected_weights["rule"] * rule_scores.get(doc_id, 0.0)
            + selected_weights["embedding"] * normalized_embedding_scores.get(doc_id, 0.0)
        )
        if score > 0:
            results.append(
                {
                    "id": document.doc_id,
                    "title": document.title,
                    "snippet": document.cleaned_text[:SNIPPET_MAX_LENGTH],
                    "score": score,
                    "score_source": "hybrid score",
                    "weights": selected_weights,
                }
            )

    return deterministic_rerank(results)


def evaluate_hybrid_schemes(
    documents: list[Document],
    dictionary: dict[str, list[str]],
    dataset: list[dict[str, Any]],
    embedding_available: bool,
    embedding_scores_by_query: dict[str, dict[str, float]] | None = None,
) -> list[dict[str, Any]]:
    weights = EMBEDDING_DEFAULT_WEIGHTS if embedding_available else EMBEDDING_DISABLED_WEIGHTS
    predictions: list[list[str]] = []
    relevant_doc_ids: list[list[str]] = []
    for case in dataset:
        query = case["query"]
        embedding_scores = None
        if embedding_available and embedding_scores_by_query is not None:
            embedding_scores = embedding_scores_by_query.get(query, {})
        results = hybrid_search_documents(documents, query, dictionary, embedding_scores, weights)
        predictions.append([result["id"] for result in results])
        relevant_doc_ids.append(case["relevant_doc_ids"])

    return [
        {
            "weights": weights,
            "recall@5": recall_at_k(predictions, relevant_doc_ids, k=5),
            "mrr": mean_reciprocal_rank(predictions, relevant_doc_ids),
        }
    ]


def _bm25_scores(documents: list[Document], expanded_terms: list[str]) -> dict[str, float]:
    return {
        document.doc_id: score
        for document, score in bm25_rank(documents, expanded_terms)
    }


def _rule_scores(documents: list[Document], expanded_terms: list[str]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for document in documents:
        title = document.title.casefold()
        body = document.cleaned_text.casefold()
        score = 0.0
        for term in expanded_terms:
            folded_term = term.casefold()
            if folded_term in title:
                score += 7.0
            if folded_term in body:
                score += 3.0
        if score > 0:
            scores[document.doc_id] = score
    return scores
