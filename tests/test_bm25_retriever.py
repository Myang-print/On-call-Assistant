import logging

from app.bm25_retriever import bm25_rank
from app.models import Document


logger = logging.getLogger(__name__)


def test_bm25_rank_scores_repeated_relevant_terms_higher() -> None:
    # Verifies that BM25 rewards repeated relevant evidence instead of binary matching only.
    documents = [
        Document(
            doc_id="sop-002",
            raw_html="<html></html>",
            title="Database SOP",
            cleaned_text="数据库 主从延迟 主从延迟 慢查询 连接池",
        ),
        Document(
            doc_id="sop-001",
            raw_html="<html></html>",
            title="Backend SOP",
            cleaned_text="数据库 连接池",
        ),
    ]

    ranked = bm25_rank(documents, ["主从延迟", "数据库", "连接池"])

    logger.info("ranked=%s", ranked)
    assert ranked[0][0].doc_id == "sop-002"
    assert ranked[0][1] > ranked[1][1]


def test_bm25_rank_sorts_by_score_first_then_doc_id() -> None:
    # Equal-score ordering must be deterministic for repeatable API responses.
    documents = [
        Document(doc_id="sop-010", raw_html="", title="CDN SOP", cleaned_text="CDN"),
        Document(doc_id="sop-003", raw_html="", title="CDN SOP", cleaned_text="CDN"),
    ]

    ranked = bm25_rank(documents, ["CDN"])

    logger.info("ranked=%s", ranked)
    assert [document.doc_id for document, _score in ranked] == ["sop-003", "sop-010"]
