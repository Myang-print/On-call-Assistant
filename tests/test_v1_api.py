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
