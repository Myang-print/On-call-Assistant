import math
from collections import Counter

from app.models import Document


K1 = 1.5
B = 0.75


def bm25_rank(documents: list[Document], terms: list[str]) -> list[tuple[Document, float]]:
    # BM25 is scoped to v2 retrieval; v1 deterministic scoring remains untouched.
    normalized_terms = [term.casefold() for term in terms if term.strip()]
    if not normalized_terms or not documents:
        return []

    # Document length is based on matched domain terms, keeping this retriever dictionary-driven.
    document_term_counts = [_count_terms(document, normalized_terms) for document in documents]
    document_lengths = [sum(term_counts.values()) for term_counts in document_term_counts]
    average_document_length = sum(document_lengths) / len(document_lengths)
    document_frequencies = {
        term: sum(1 for term_counts in document_term_counts if term_counts.get(term, 0) > 0)
        for term in normalized_terms
    }

    ranked: list[tuple[Document, float]] = []
    for document, term_counts, document_length in zip(
        documents,
        document_term_counts,
        document_lengths,
    ):
        score = 0.0
        for term in normalized_terms:
            frequency = term_counts.get(term, 0)
            if frequency == 0:
                continue

            score += _idf(len(documents), document_frequencies[term]) * _term_score(
                frequency,
                document_length,
                average_document_length,
            )

        if score > 0:
            ranked.append((document, score))

    # Score is the primary ordering contract; doc_id makes ties deterministic.
    return sorted(ranked, key=lambda item: (-item[1], item[0].doc_id))


def _count_terms(document: Document, terms: list[str]) -> Counter[str]:
    title = document.title.casefold()
    body = document.cleaned_text.casefold()
    counts: Counter[str] = Counter()

    for term in terms:
        # Title occurrences carry extra weight without changing the BM25 formula itself.
        counts[term] += title.count(term) * 2
        counts[term] += body.count(term)

    return counts


def _idf(document_count: int, document_frequency: int) -> float:
    # Standard smoothed IDF avoids negative scores for common terms in the small SOP corpus.
    return math.log(1 + (document_count - document_frequency + 0.5) / (document_frequency + 0.5))


def _term_score(
    frequency: int,
    document_length: int,
    average_document_length: float,
) -> float:
    if average_document_length == 0:
        return 0.0

    denominator = frequency + K1 * (1 - B + B * document_length / average_document_length)
    return frequency * (K1 + 1) / denominator
