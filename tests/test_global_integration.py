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


def test_uploaded_html_document_is_searchable_by_v1_and_v2() -> None:
    client = TestClient(app)
    payload = {
        "id": "final-upload-sop",
        "html": (
            "<html><head><title>Final Upload SOP</title></head>"
            "<body><p>final-upload-token final-semantic-token</p></body></html>"
        ),
    }

    create_response = client.post("/v1/documents", json=payload)
    v1_response = client.get("/v1/search", params={"q": "final-upload-token"})
    v2_response = client.get("/v2/search", params={"q": "final-semantic-token"})

    assert create_response.status_code == 201
    assert create_response.json() == {"id": "final-upload-sop", "title": "Final Upload SOP"}
    assert "final-upload-sop" in [item["id"] for item in v1_response.json()["results"]]
    assert "final-upload-sop" in [item["id"] for item in v2_response.json()["results"]]


def test_uploaded_html_document_is_visible_to_v3_agent() -> None:
    client = TestClient(app)
    payload = {
        "id": "final-v3-upload-sop",
        "html": (
            "<html><head><title>Final V3 Upload SOP</title></head>"
            "<body><p>final-v3-upload-token requires escalation owner validation.</p></body></html>"
        ),
    }

    create_response = client.post("/v1/documents", json=payload)
    response = client.post("/api/oncall/query", json={"query": "final-v3-upload-token 怎么处理"})

    assert create_response.status_code == 201
    assert response.status_code == 200
    body = response.json()
    assert "当前没有足够的 SOP 文档支持判断" not in body["answer"]
    assert "final-v3-upload-sop" in [item["id"] for item in body["sources"]]


def test_document_upload_rejects_bad_name_and_bad_document() -> None:
    client = TestClient(app)

    bad_name = client.post(
        "/v1/documents",
        json={"id": "../bad", "html": "<html><body>bad-name-token</body></html>"},
    )
    bad_document = client.post(
        "/v1/documents",
        json={"id": "bad-document", "html": "plain text without html tags"},
    )

    assert bad_name.status_code == 400
    assert bad_document.status_code == 400


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
    def broken_agent(_: str, **__: object):
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
    def failed_agent(_: str, **__: object):
        return {"ok": False, "error": "planner failed", "trace": [{"stage": "agent", "event": "planner_failed"}]}

    monkeypatch.setattr("app.api.run_agent_once", failed_agent)
    client = TestClient(app)

    response = client.post("/api/oncall/query", json={"query": "黑客攻击"})

    assert response.status_code == 200
    payload = response.json()
    assert "回退到 v2" in payload["answer"]
    assert payload["sources"][0]["id"] == "sop-005"
    assert payload["trace"][0]["event"] == "agent_failed"
