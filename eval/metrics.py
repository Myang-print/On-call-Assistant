def recall_at_k(
    predictions: list[list[str]],
    relevant_doc_ids: list[list[str]],
    k: int,
) -> float:
    if not predictions:
        return 0.0

    hits = 0
    for predicted, relevant in zip(predictions, relevant_doc_ids):
        top_k = set(predicted[:k])
        if top_k.intersection(relevant):
            hits += 1

    return hits / len(predictions)


def mean_reciprocal_rank(
    predictions: list[list[str]],
    relevant_doc_ids: list[list[str]],
) -> float:
    if not predictions:
        return 0.0

    reciprocal_ranks: list[float] = []
    for predicted, relevant in zip(predictions, relevant_doc_ids):
        relevant_set = set(relevant)
        reciprocal_rank = 0.0
        for index, doc_id in enumerate(predicted, start=1):
            if doc_id in relevant_set:
                reciprocal_rank = 1 / index
                break
        reciprocal_ranks.append(reciprocal_rank)

    return sum(reciprocal_ranks) / len(predictions)
