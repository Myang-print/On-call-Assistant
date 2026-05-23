from app.models import Document


TITLE_MATCH_WEIGHT = 7.0
BODY_MATCH_WEIGHT = 3.0
SNIPPET_MAX_LENGTH = 80


def search_documents(documents: list[Document], query: str) -> list[dict[str, object]]:
    normalized_query = query.strip()
    if not normalized_query:
        return []

    results: list[dict[str, object]] = []
    query_folded = normalized_query.casefold()

    for document in documents:
        title_matches = query_folded in document.title.casefold()
        body_matches = query_folded in document.cleaned_text.casefold()
        score = 0.0
        if title_matches:
            score += TITLE_MATCH_WEIGHT
        if body_matches:
            score += BODY_MATCH_WEIGHT

        if score > 0:
            results.append(
                {
                    "id": document.doc_id,
                    "title": document.title,
                    "snippet": _make_snippet(document.cleaned_text, normalized_query),
                    "score": score,
                }
            )

    return sorted(results, key=lambda result: (-float(result["score"]), str(result["id"])))


def _make_snippet(text: str, query: str) -> str:
    if len(text) <= SNIPPET_MAX_LENGTH:
        return text

    match_index = text.casefold().find(query.casefold())
    if match_index == -1:
        return text[:SNIPPET_MAX_LENGTH]

    half_window = SNIPPET_MAX_LENGTH // 2
    start = max(0, match_index - half_window)
    end = min(len(text), start + SNIPPET_MAX_LENGTH)
    start = max(0, end - SNIPPET_MAX_LENGTH)
    return text[start:end]
