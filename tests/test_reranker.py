import logging

from app.documents import DocumentStore
from app.hybrid_search import hybrid_search_documents
from app.reranker import deterministic_rerank
from app.semantic_search import load_domain_dictionary
from app.settings import DATA_DIR


logger = logging.getLogger(__name__)


def test_deterministic_reranker_orders_by_score_desc_then_id() -> None:
    results = [
        {"id": "sop-010", "score": 0.8},
        {"id": "sop-004", "score": 0.9},
        {"id": "sop-001", "score": 0.9},
    ]

    reranked = deterministic_rerank(results)

    logger.info("reranked_results=%s", reranked)
    assert [result["id"] for result in reranked] == ["sop-001", "sop-004", "sop-010"]


def test_deterministic_reranker_does_not_mutate_input_order() -> None:
    results = [
        {"id": "sop-002", "score": 1.0},
        {"id": "sop-001", "score": 1.0},
    ]

    reranked = deterministic_rerank(results)

    logger.info("original_results=%s reranked_results=%s", results, reranked)
    assert [result["id"] for result in results] == ["sop-002", "sop-001"]
    assert [result["id"] for result in reranked] == ["sop-001", "sop-002"]


def test_hybrid_search_returns_deterministically_reranked_results() -> None:
    documents = DocumentStore.from_data_dir().all()
    dictionary = load_domain_dictionary(DATA_DIR / "domain_dictionary.json")

    results = hybrid_search_documents(documents, "服务器挂了", dictionary)

    logger.info("hybrid_reranked_results=%s", results[:5])
    ordered_pairs = [(float(result["score"]), str(result["id"])) for result in results]
    assert ordered_pairs == sorted(ordered_pairs, key=lambda pair: (-pair[0], pair[1]))
