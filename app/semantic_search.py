import json
from pathlib import Path

from app.bm25_retriever import bm25_rank
from app.models import Document


SNIPPET_MAX_LENGTH = 80


def load_domain_dictionary(path: Path) -> dict[str, list[str]]:
    with path.open("r", encoding="utf-8") as dictionary_file:
        dictionary = json.load(dictionary_file)

    return {str(query): [str(term) for term in terms] for query, terms in dictionary.items()}


def expand_query(query: str, dictionary: dict[str, list[str]]) -> list[str]:
    normalized_query = query.strip()
    if not normalized_query:
        return []

    # Preserve the original query as the first term for exact-match compatibility.
    expanded_terms = [normalized_query]
    for term in dictionary.get(normalized_query, []):
        if term not in expanded_terms:
            expanded_terms.append(term)

    return expanded_terms


def semantic_search_documents(
    documents: list[Document],
    query: str,
    dictionary: dict[str, list[str]],
) -> list[dict[str, object]]:
    expanded_terms = expand_query(query, dictionary)
    if not expanded_terms:
        return []

    # Semantic expansion supplies candidate terms; BM25 owns v2 scoring and ranking.
    return [
        {
            "id": document.doc_id,
            "title": document.title,
            "snippet": _make_snippet(document.cleaned_text, expanded_terms),
            "score": score,
        }
        for document, score in bm25_rank(documents, expanded_terms)
    ]


def _make_snippet(text: str, expanded_terms: list[str]) -> str:
    if len(text) <= SNIPPET_MAX_LENGTH:
        return text

    text_folded = text.casefold()
    match_indexes = [
        text_folded.find(term.casefold())
        for term in expanded_terms
        if text_folded.find(term.casefold()) != -1
    ]
    if not match_indexes:
        return text[:SNIPPET_MAX_LENGTH]

    # Use the earliest expanded-term match so snippets expose why a document was retrieved.
    match_index = min(match_indexes)
    half_window = SNIPPET_MAX_LENGTH // 2
    start = max(0, match_index - half_window)
    end = min(len(text), start + SNIPPET_MAX_LENGTH)
    start = max(0, end - SNIPPET_MAX_LENGTH)
    return text[start:end]
