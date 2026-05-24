import logging

from fastapi.testclient import TestClient

from app.main import app


logger = logging.getLogger(__name__)


def test_v1_search_returns_expected_response_shape() -> None:
    client = TestClient(app)

    response = client.get("/v1/search", params={"q": "CDN"})

    logger.info("status=%s body=%s", response.status_code, response.json())
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "CDN"
    assert set(body["results"][0]) == {"id", "title", "snippet", "score"}


def test_v1_search_oom_uses_actual_fixture_content() -> None:
    client = TestClient(app)

    response = client.get("/v1/search", params={"q": "OOM"})

    logger.info("oom_body=%s", response.json())
    result_ids = [result["id"] for result in response.json()["results"]]
    assert "sop-001" in result_ids
    assert "sop-007" in result_ids
    assert "sop-003" not in result_ids


def test_v1_search_fault_returns_multiple_documents() -> None:
    client = TestClient(app)

    response = client.get("/v1/search", params={"q": "故障"})

    logger.info("fault_body=%s", response.json())
    assert response.status_code == 200
    assert len(response.json()["results"]) > 1


def test_v1_search_excludes_script_content() -> None:
    client = TestClient(app)

    response = client.get("/v1/search", params={"q": "replication"})

    logger.info("replication_body=%s", response.json())
    assert response.status_code == 200
    assert response.json()["results"] == []


def test_v1_search_cdn_orders_by_score_then_id() -> None:
    client = TestClient(app)

    response = client.get("/v1/search", params={"q": "CDN"})

    logger.info("cdn_body=%s", response.json())
    result_ids = [result["id"] for result in response.json()["results"]]
    assert result_ids[:2] == ["sop-010", "sop-003"]


def test_v1_search_literal_ampersand_boundary() -> None:
    client = TestClient(app)

    response = client.get("/v1/search?q=&")

    logger.info("ampersand_body=%s", response.json())
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "&"
    assert [result["id"] for result in body["results"]] == ["sop-003", "sop-008", "sop-010"]


def test_post_v1_documents_adds_document_and_returns_id_and_title() -> None:
    client = TestClient(app)
    doc_id = "round13-api-doc"
    html = (
        "<html><head><title>Round13 API SOP</title></head>"
        "<body><h1>Fallback Title</h1><p>round13-api-search-token round13-semantic-token</p></body></html>"
    )

    response = client.post("/v1/documents", json={"id": doc_id, "html": html})

    logger.info("post_document_body=%s", response.json())
    assert response.status_code == 201
    assert response.json() == {"id": doc_id, "title": "Round13 API SOP"}

    v1_response = client.get("/v1/search", params={"q": "round13-api-search-token"})
    v2_response = client.get("/v2/search", params={"q": "round13-semantic-token"})

    logger.info("post_document_v1=%s v2=%s", v1_response.json(), v2_response.json())
    assert doc_id in [result["id"] for result in v1_response.json()["results"]]
    assert doc_id in [result["id"] for result in v2_response.json()["results"]]


def test_post_v1_documents_rejects_empty_id_or_html() -> None:
    client = TestClient(app)

    empty_id = client.post("/v1/documents", json={"id": "", "html": "<html></html>"})
    empty_html = client.post("/v1/documents", json={"id": "empty-html", "html": ""})
    missing_html = client.post("/v1/documents", json={"id": "missing-html"})

    logger.info(
        "empty_id=%s empty_html=%s missing_html=%s",
        empty_id.status_code,
        empty_html.status_code,
        missing_html.status_code,
    )
    assert empty_id.status_code == 400
    assert empty_html.status_code == 400
    assert missing_html.status_code == 422


def test_post_v1_documents_rejects_duplicate_id() -> None:
    client = TestClient(app)
    doc_id = "round13-duplicate-doc"
    payload = {
        "id": doc_id,
        "html": "<html><head><title>Duplicate SOP</title></head><body>duplicate token</body></html>",
    }

    first_response = client.post("/v1/documents", json=payload)
    second_response = client.post("/v1/documents", json=payload)

    logger.info(
        "duplicate_first=%s duplicate_second=%s",
        first_response.status_code,
        second_response.status_code,
    )
    assert first_response.status_code == 201
    assert second_response.status_code == 409
