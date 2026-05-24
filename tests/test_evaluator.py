import json
import logging
from pathlib import Path

from eval.evaluator import evaluate_retriever, load_golden_dataset
from eval.metrics import mean_reciprocal_rank, recall_at_k


logger = logging.getLogger(__name__)


def test_golden_dataset_contains_required_v2_queries() -> None:
    dataset = load_golden_dataset()
    queries = {case["query"] for case in dataset}

    logger.info("golden_queries=%s", sorted(queries))
    assert len(dataset) == 12
    assert {"服务器挂了", "黑客攻击", "机器学习模型出问题"}.issubset(queries)


def test_golden_dataset_covers_required_case_categories() -> None:
    dataset = load_golden_dataset(Path("eval/golden_dataset.json"))
    category_counts: dict[str, int] = {}
    multi_document_cases = 0
    for case in dataset:
        category_counts[case["category"]] = category_counts.get(case["category"], 0) + 1
        if len(case["relevant_doc_ids"]) > 1:
            multi_document_cases += 1

    logger.info("category_counts=%s multi_document_cases=%s", category_counts, multi_document_cases)
    assert category_counts == {
        "normal": 5,
        "synonym": 3,
        "boundary": 2,
        "multi_document": 2,
    }
    assert multi_document_cases >= 2


def test_recall_at_5_counts_query_hit_when_any_relevant_doc_is_in_top_5() -> None:
    predictions = [
        ["sop-999", "sop-001", "sop-010"],
        ["sop-001", "sop-002", "sop-003", "sop-004", "sop-005"],
        ["sop-003", "sop-004", "sop-005", "sop-006", "sop-007", "sop-008"],
    ]
    relevant = [
        ["sop-001", "sop-004"],
        ["sop-008"],
        ["sop-008"],
    ]

    score = recall_at_k(predictions, relevant, k=5)

    logger.info("recall_at_5=%s", score)
    assert score == 1 / 3


def test_mrr_uses_first_relevant_rank_per_query() -> None:
    predictions = [
        ["sop-999", "sop-001", "sop-004"],
        ["sop-005", "sop-001"],
        ["sop-003", "sop-004"],
    ]
    relevant = [
        ["sop-001", "sop-004"],
        ["sop-005"],
        ["sop-008"],
    ]

    score = mean_reciprocal_rank(predictions, relevant)

    logger.info("mrr=%s", score)
    assert score == (1 / 2 + 1 + 0) / 3


def test_evaluator_uses_temp_mock_retriever_and_reports_metrics() -> None:
    dataset = [
        {"query": "服务器挂了", "relevant_doc_ids": ["sop-001", "sop-004"]},
        {"query": "黑客攻击", "relevant_doc_ids": ["sop-005"]},
        {"query": "机器学习模型出问题", "relevant_doc_ids": ["sop-008"]},
    ]

    def temp_mock_retriever(query: str) -> list[str]:
        # Temporary mock behavior for evaluator verification only.
        mapping = {
            "服务器挂了": ["sop-004", "sop-001"],
            "黑客攻击": ["sop-001", "sop-002", "sop-003", "sop-004", "sop-005"],
            "机器学习模型出问题": ["sop-001", "sop-002", "sop-003", "sop-004", "sop-005"],
        }
        return mapping[query]

    result = evaluate_retriever(dataset, temp_mock_retriever)

    logger.info("evaluation_result=%s", json.dumps(result, ensure_ascii=False))
    assert result == {
        "case_count": 3,
        "recall@5": 2 / 3,
        "mrr": (1 + 1 / 5 + 0) / 3,
    }
