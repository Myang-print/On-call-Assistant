import logging

from app.documents import DocumentStore
from app.hybrid_search import (
    EMBEDDING_DEFAULT_WEIGHTS,
    EMBEDDING_DISABLED_WEIGHTS,
    evaluate_hybrid_schemes,
    hybrid_search_documents,
    normalize_scores,
)
from app.settings import DATA_DIR
from app.semantic_search import load_domain_dictionary
from eval.evaluator import load_golden_dataset


logger = logging.getLogger(__name__)


def test_normalize_scores_maps_values_to_zero_one_range() -> None:
    normalized = normalize_scores({"sop-001": 2.0, "sop-002": 4.0, "sop-003": 4.0})

    logger.info("normalized_scores=%s", normalized)
    assert normalized == {"sop-001": 0.0, "sop-002": 1.0, "sop-003": 1.0}


def test_fixed_hybrid_weight_parameters_are_recorded() -> None:
    assert EMBEDDING_DISABLED_WEIGHTS == {"bm25": 0.7, "rule": 0.3, "embedding": 0.0}
    assert EMBEDDING_DEFAULT_WEIGHTS == {"bm25": 0.5, "rule": 0.2, "embedding": 0.3}


def test_evaluate_hybrid_schemes_records_embedding_disabled_weight_result() -> None:
    documents = DocumentStore.from_data_dir().all()
    dictionary = load_domain_dictionary(DATA_DIR / "domain_dictionary.json")
    dataset = load_golden_dataset()

    evaluations = evaluate_hybrid_schemes(
        documents,
        dictionary,
        dataset,
        embedding_available=False,
    )

    logger.info("fallback_evaluations=%s", evaluations)
    assert [evaluation["weights"] for evaluation in evaluations] == [EMBEDDING_DISABLED_WEIGHTS]
    assert all("recall@5" in evaluation and "mrr" in evaluation for evaluation in evaluations)


def test_embedding_disabled_evaluation_never_requires_embedding_scores() -> None:
    documents = DocumentStore.from_data_dir().all()
    dictionary = load_domain_dictionary(DATA_DIR / "domain_dictionary.json")
    dataset = load_golden_dataset()

    evaluations = evaluate_hybrid_schemes(
        documents,
        dictionary,
        dataset,
        embedding_available=False,
        embedding_scores_by_query={"黑客攻击": {"sop-005": 1.0}},
    )

    logger.info("embedding_disabled_evaluations=%s", evaluations)
    assert all(evaluation["weights"]["embedding"] == 0.0 for evaluation in evaluations)


def test_hybrid_search_uses_default_embedding_success_weights() -> None:
    documents = DocumentStore.from_data_dir().all()
    dictionary = load_domain_dictionary(DATA_DIR / "domain_dictionary.json")
    embedding_scores = {document.doc_id: 0.0 for document in documents}
    embedding_scores["sop-005"] = 1.0

    results = hybrid_search_documents(
        documents,
        "黑客攻击",
        dictionary,
        embedding_scores=embedding_scores,
    )

    logger.info("hybrid_embedding_results=%s", results[:3])
    assert results[0]["id"] == "sop-005"
    assert results[0]["score_source"] == "hybrid score"
    assert results[0]["weights"] == EMBEDDING_DEFAULT_WEIGHTS


def test_hybrid_search_matches_required_v2_table_when_embedding_is_unavailable() -> None:
    documents = DocumentStore.from_data_dir().all()
    dictionary = load_domain_dictionary(DATA_DIR / "domain_dictionary.json")

    server_results = hybrid_search_documents(documents, "服务器挂了", dictionary)
    security_results = hybrid_search_documents(documents, "黑客攻击", dictionary)
    ai_results = hybrid_search_documents(documents, "机器学习模型出问题", dictionary)

    logger.info(
        "server=%s security=%s ai=%s",
        server_results[:3],
        security_results[:3],
        ai_results[:3],
    )
    assert {result["id"] for result in server_results[:2]} == {"sop-001", "sop-004"}
    assert security_results[0]["id"] == "sop-005"
    assert ai_results[0]["id"] == "sop-008"
