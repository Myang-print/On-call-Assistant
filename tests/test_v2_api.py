import logging

from fastapi.testclient import TestClient

from app.main import app


logger = logging.getLogger(__name__)


def test_v2_search_server_down_ranks_backend_and_sre_near_top() -> None:
    # End-to-end guard for the required v2 semantic expansion + BM25 route behavior.
    client = TestClient(app)

    response = client.get("/v2/search", params={"q": "服务器挂了"})

    logger.info("server_down_body=%s", response.json())
    assert response.status_code == 200
    assert response.json()["results"][0]["score_source"] == "hybrid score"
    top2_ids = {result["id"] for result in response.json()["results"][:2]}
    assert top2_ids == {"sop-001", "sop-004"}


def test_v2_search_hacker_attack_ranks_security_first() -> None:
    client = TestClient(app)

    response = client.get("/v2/search", params={"q": "黑客攻击"})

    logger.info("hacker_attack_body=%s", response.json())
    assert response.status_code == 200
    assert response.json()["results"][0]["id"] == "sop-005"


def test_v2_search_machine_learning_model_issue_ranks_ai_first() -> None:
    client = TestClient(app)

    response = client.get("/v2/search", params={"q": "机器学习模型出问题"})

    logger.info("ml_model_issue_body=%s", response.json())
    assert response.status_code == 200
    assert response.json()["results"][0]["id"] == "sop-008"


def test_v2_search_returns_deterministically_reranked_results() -> None:
    client = TestClient(app)

    response = client.get("/v2/search", params={"q": "服务器挂了"})

    logger.info("v2_reranked_body=%s", response.json())
    assert response.status_code == 200
    ordered_pairs = [
        (float(result["score"]), str(result["id"]))
        for result in response.json()["results"]
    ]
    assert ordered_pairs == sorted(ordered_pairs, key=lambda pair: (-pair[0], pair[1]))
