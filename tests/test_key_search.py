import logging

from fastapi.testclient import TestClient

from app.key_search import search_documents
from app.main import app
from app.models import Document


logger = logging.getLogger(__name__)


def test_search_scores_title_matches_with_weight_7_and_body_matches_with_weight_3() -> None:
    documents = [
        Document(
            doc_id="sop-002",
            raw_html="<html></html>",
            title="Database SOP",
            cleaned_text="OOM appears in body only.",
        ),
        Document(
            doc_id="sop-001",
            raw_html="<html></html>",
            title="OOM Backend SOP",
            cleaned_text="No body keyword here.",
        ),
    ]

    results = search_documents(documents, "OOM")

    logger.info("weighted_results=%s", results)
    assert [result["id"] for result in results] == ["sop-001", "sop-002"]
    assert results[0]["score"] == 7.0
    assert results[1]["score"] == 3.0


def test_search_adds_title_and_body_scores_and_sorts_ties_by_id() -> None:
    documents = [
        Document(
            doc_id="sop-010",
            raw_html="<html></html>",
            title="CDN Network SOP",
            cleaned_text="CDN body occurrence.",
        ),
        Document(
            doc_id="sop-003",
            raw_html="<html></html>",
            title="CDN Frontend SOP",
            cleaned_text="CDN body occurrence.",
        ),
        Document(
            doc_id="sop-001",
            raw_html="<html></html>",
            title="Backend SOP",
            cleaned_text="CDN body occurrence.",
        ),
    ]

    results = search_documents(documents, "CDN")

    logger.info("tie_sorted_results=%s", results)
    assert [result["id"] for result in results] == ["sop-003", "sop-010", "sop-001"]
    assert results[0]["score"] == 10.0
    assert results[1]["score"] == 10.0
    assert results[2]["score"] == 3.0


def test_search_returns_short_snippet_around_body_match() -> None:
    documents = [
        Document(
            doc_id="sop-001",
            raw_html="<html></html>",
            title="Backend SOP",
            cleaned_text="prefix " * 20 + "OOM failure handling steps " + "suffix " * 20,
        )
    ]

    results = search_documents(documents, "OOM")

    logger.info("snippet=%s", results[0]["snippet"])
    assert "OOM" in results[0]["snippet"]
    assert len(results[0]["snippet"]) <= 80


def test_search_returns_empty_list_for_empty_query() -> None:
    documents = [
        Document(
            doc_id="sop-001",
            raw_html="<html></html>",
            title="Backend SOP",
            cleaned_text="OOM.",
        )
    ]

    results = search_documents(documents, "")

    logger.info("empty_query_results=%s", results)
    assert results == []


def test_v1_search_endpoint_returns_real_loaded_documents_sorted() -> None:
    client = TestClient(app)

    response = client.get("/v1/search", params={"q": "CDN"})

    logger.info("status=%s body=%s", response.status_code, response.json())
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "CDN"
    result_ids = [result["id"] for result in body["results"]]
    assert result_ids[:2] == ["sop-010", "sop-003"]
    assert all("snippet" in result for result in body["results"])


def test_v1_search_endpoint_treats_literal_q_ampersand_as_ampersand_query() -> None:
    client = TestClient(app)

    response = client.get("/v1/search?q=&")

    logger.info("status=%s body=%s", response.status_code, response.json())
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "&"
    assert [result["id"] for result in body["results"]] == ["sop-003", "sop-008", "sop-010"]


def test_v1_search_oom_matches_actual_data_without_sop_003() -> None:
    client = TestClient(app)

    response = client.get("/v1/search", params={"q": "OOM"})

    logger.info("status=%s body=%s", response.status_code, response.json())
    assert response.status_code == 200
    result_ids = [result["id"] for result in response.json()["results"]]
    assert result_ids == ["sop-001", "sop-007"]
    assert "sop-003" not in result_ids
