import logging

from fastapi.testclient import TestClient

from app.main import app
from eval.evaluator import evaluate_retriever, load_golden_dataset


logger = logging.getLogger(__name__)


def _client() -> TestClient:
    return TestClient(app)


def _ids(response_json: dict[str, object]) -> list[str]:
    return [str(result["id"]) for result in response_json["results"]]


def test_v2_complete_pipeline_from_query_to_reranked_response() -> None:
    client = _client()

    response = client.get("/v2/search", params={"q": "服务器挂了"})

    body = response.json()
    logger.info("v2_pipeline_status=%s body=%s", response.status_code, body)
    assert response.status_code == 200
    assert body["query"] == "服务器挂了"
    assert {result["id"] for result in body["results"][:2]} == {"sop-001", "sop-004"}
    assert all(result["score_source"] == "hybrid score" for result in body["results"])
    ordered_pairs = [
        (float(result["score"]), str(result["id"]))
        for result in body["results"]
    ]
    assert ordered_pairs == sorted(ordered_pairs, key=lambda pair: (-pair[0], pair[1]))


def test_v1_and_v2_get_search_endpoints_remain_available() -> None:
    client = _client()

    v1_response = client.get("/v1/search", params={"q": "OOM"})
    v2_response = client.get("/v2/search", params={"q": "黑客攻击"})

    logger.info("v1_body=%s v2_body=%s", v1_response.json(), v2_response.json())
    assert v1_response.status_code == 200
    assert "sop-001" in _ids(v1_response.json())
    assert v2_response.status_code == 200
    assert _ids(v2_response.json())[0] == "sop-005"


def test_v1_post_document_api_is_not_implemented_and_fails_closed() -> None:
    client = _client()

    response = client.post("/v1/documents", json={"id": "empty", "html": ""})

    logger.info("v1_post_documents_status=%s body=%s", response.status_code, response.text)
    assert response.status_code == 404


def test_empty_missing_and_whitespace_queries_return_empty_results() -> None:
    client = _client()

    responses = [
        client.get("/v1/search", params={"q": ""}),
        client.get("/v1/search"),
        client.get("/v2/search", params={"q": ""}),
        client.get("/v2/search"),
        client.get("/v2/search", params={"q": "   "}),
    ]

    for response in responses:
        logger.info("empty_query_status=%s body=%s", response.status_code, response.json())
        assert response.status_code == 200
        assert response.json()["results"] == []


def test_special_symbol_boundary_queries_are_handled_without_error() -> None:
    client = _client()

    literal_ampersand_v1 = client.get("/v1/search?q=&")
    literal_ampersand_v2 = client.get("/v2/search?q=&")
    unknown_symbol_v2 = client.get("/v2/search", params={"q": "###"})

    logger.info(
        "amp_v1=%s amp_v2=%s unknown_v2=%s",
        literal_ampersand_v1.json(),
        literal_ampersand_v2.json(),
        unknown_symbol_v2.json(),
    )
    assert literal_ampersand_v1.status_code == 200
    assert literal_ampersand_v1.json()["query"] == "&"
    assert _ids(literal_ampersand_v1.json()) == ["sop-003", "sop-008", "sop-010"]
    assert literal_ampersand_v2.status_code == 200
    assert literal_ampersand_v2.json()["query"] == "&"
    assert set(_ids(literal_ampersand_v2.json())[:3]) == {"sop-003", "sop-008", "sop-010"}
    assert unknown_symbol_v2.status_code == 200
    assert unknown_symbol_v2.json()["results"] == []


def test_script_only_content_is_not_searchable_in_v1_or_v2() -> None:
    client = _client()

    v1_response = client.get("/v1/search", params={"q": "replication"})
    v2_response = client.get("/v2/search", params={"q": "replication"})

    logger.info("script_v1=%s script_v2=%s", v1_response.json(), v2_response.json())
    assert v1_response.status_code == 200
    assert v1_response.json()["results"] == []
    assert v2_response.status_code == 200
    assert v2_response.json()["results"] == []


def test_v2_golden_dataset_evaluation_reaches_current_acceptance_baseline() -> None:
    client = _client()
    dataset = load_golden_dataset()

    metrics = evaluate_retriever(
        dataset,
        lambda query: _ids(client.get("/v2/search", params={"q": query}).json()),
    )

    logger.info("v2_golden_dataset_metrics=%s", metrics)
    assert metrics == {"case_count": 12, "recall@5": 0.75, "mrr": 0.75}
