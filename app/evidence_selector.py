import re
from typing import Any


SAFE_HTML_FILENAME = re.compile(r"^[A-Za-z0-9_-]+\.html$")
ASCII_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
QUERY_ALIASES = [
    (("oom", "内存", "内存泄漏"), ("OOM", "后端服务", "后端")),
    (("主从", "延迟", "数据库"), ("主从延迟", "数据库", "DBA")),
    (("入侵", "黑客", "攻击", "安全"), ("信息安全", "安全", "SOP-005")),
    (("推荐", "质量下降", "模型", "算法"), ("AI", "算法", "模型服务故障处理指南", "GPU", "SOP-008")),
    (("p0", "故障"), ("故障处理指南", "SRE", "后端服务", "基础设施")),
    (("cdn",), ("CDN", "网络", "前端")),
]


def select_sop_filenames(
    query: str,
    manifest: list[dict[str, Any]],
    limit: int = 3,
) -> list[str]:
    terms = _query_terms(query, manifest)
    scored: list[tuple[float, str]] = []

    for entry in manifest:
        filename = str(entry.get("filename", ""))
        if not _is_safe_html_filename(filename):
            continue

        score = _score_entry(entry, terms)
        if score > 0:
            scored.append((score, filename))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [filename for _, filename in scored[:limit]]


def _query_terms(query: str, manifest: list[dict[str, Any]]) -> list[str]:
    folded_query = query.casefold()
    terms = [query.strip()]
    terms.extend(ASCII_TOKEN_PATTERN.findall(query))

    for entry in manifest:
        for keyword in _entry_keywords(entry):
            if keyword.casefold() in folded_query:
                terms.append(keyword)

    for triggers, expansions in QUERY_ALIASES:
        if any(trigger.casefold() in folded_query for trigger in triggers):
            terms.extend(expansions)

    return _deduplicate_terms(term for term in terms if term)


def _score_entry(entry: dict[str, Any], terms: list[str]) -> float:
    title = str(entry.get("title", ""))
    doc_id = str(entry.get("doc_id", ""))
    filename = str(entry.get("filename", ""))
    keywords = _entry_keywords(entry)
    folded_keywords = [keyword.casefold() for keyword in keywords]
    score = 0.0

    for term in terms:
        folded = term.casefold()
        if not folded:
            continue
        if folded in title.casefold():
            score += 4.0
        if folded in {doc_id.casefold(), filename.casefold()}:
            score += 3.0
        if folded in folded_keywords:
            score += 6.0
        elif any(folded in keyword for keyword in folded_keywords):
            score += 2.0

    return score


def _entry_keywords(entry: dict[str, Any]) -> list[str]:
    keywords = entry.get("keywords", [])
    if not isinstance(keywords, list):
        return []
    return [str(keyword) for keyword in keywords if str(keyword)]


def _is_safe_html_filename(filename: str) -> bool:
    return bool(SAFE_HTML_FILENAME.fullmatch(filename))


def _deduplicate_terms(terms: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for term in terms:
        folded = str(term).casefold()
        if folded in seen:
            continue
        seen.add(folded)
        result.append(str(term))
    return result
