from fastapi.testclient import TestClient

from app.main import app


def test_global_v1_and_v2_routes_remain_available() -> None:
    client = TestClient(app)

    v1_response = client.get("/v1/search", params={"q": "OOM"})
    v2_response = client.get("/v2/search", params={"q": "服务器挂了"})

    assert v1_response.status_code == 200
    assert v1_response.json()["results"][0]["id"] == "sop-001"
    assert v2_response.status_code == 200
    assert {item["id"] for item in v2_response.json()["results"][:2]} == {"sop-001", "sop-004"}


def test_v3_api_returns_natural_language_answer_for_frontend() -> None:
    client = TestClient(app)

    response = client.post("/api/oncall/query", json={"query": "服务 OOM 了怎么办？"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"]
    assert "runtime status" not in payload["answer"]
    assert isinstance(payload["trace"], list)
    assert isinstance(payload["sources"], list)


def test_v3_api_composes_answer_from_retrieved_sop_documents() -> None:
    client = TestClient(app)

    response = client.post("/api/oncall/query", json={"query": "服务 OOM 了怎么办？"})

    assert response.status_code == 200
    payload = response.json()
    assert "当前没有足够的 SOP 文档支持判断" not in payload["answer"]
    assert "runtime status" not in payload["answer"]
    assert payload["sources"]
    assert payload["sources"][0]["id"] == "sop-001"


def test_v3_api_rolls_back_to_v2_when_agent_raises(monkeypatch) -> None:
    def broken_agent(_: str):
        raise RuntimeError("agent unavailable")

    monkeypatch.setattr("app.api.run_agent_once", broken_agent)
    client = TestClient(app)

    response = client.post("/api/oncall/query", json={"query": "服务器挂了"})

    assert response.status_code == 200
    payload = response.json()
    assert "回退到 v2" in payload["answer"]
    assert payload["sources"]
    assert {item["id"] for item in payload["sources"][:2]} == {"sop-001", "sop-004"}
    assert payload["trace"][0]["event"] == "agent_exception"


def test_v3_api_rolls_back_to_v2_when_agent_returns_failure(monkeypatch) -> None:
    def failed_agent(_: str):
        return {"ok": False, "error": "planner failed", "trace": [{"stage": "agent", "event": "planner_failed"}]}

    monkeypatch.setattr("app.api.run_agent_once", failed_agent)
    client = TestClient(app)

    response = client.post("/api/oncall/query", json={"query": "黑客攻击"})

    assert response.status_code == 200
    payload = response.json()
    assert "回退到 v2" in payload["answer"]
    assert payload["sources"][0]["id"] == "sop-005"
    assert payload["trace"][0]["event"] == "agent_failed"
