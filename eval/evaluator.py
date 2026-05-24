import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from eval.metrics import mean_reciprocal_rank, recall_at_k


GOLDEN_DATASET_PATH = Path(__file__).with_name("golden_dataset.json")
GoldenCase = dict[str, Any]
Retriever = Callable[[str], list[str]]


def load_golden_dataset(path: Path = GOLDEN_DATASET_PATH) -> list[GoldenCase]:
    with path.open("r", encoding="utf-8") as dataset_file:
        dataset = json.load(dataset_file)

    return list(dataset)


def evaluate_retriever(dataset: list[GoldenCase], retriever: Retriever) -> dict[str, float | int]:
    # The current tests pass a temporary mock retriever; v2 search is not implemented here.
    predictions = [retriever(case["query"]) for case in dataset]
    relevant_doc_ids = [case["relevant_doc_ids"] for case in dataset]

    return {
        "case_count": len(dataset),
        "recall@5": recall_at_k(predictions, relevant_doc_ids, k=5),
        "mrr": mean_reciprocal_rank(predictions, relevant_doc_ids),
    }
