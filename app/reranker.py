from collections.abc import Sequence
from typing import Any


def deterministic_rerank(results: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(results, key=lambda result: (-float(result["score"]), str(result["id"])))
