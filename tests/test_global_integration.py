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


def test_uploaded_html_document_does_not_pollute_v3_tool_evidence_chain() -> None:
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
    assert "当前没有足够的 SOP 文档支持判断" in body["answer"]
    assert "final-v3-upload-sop" not in [item.get("id") for item in body["sources"]]


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
    assert "查看JVM监控面板" in payload["answer"]
    assert "检查最近是否有代码发布或配置变更" in payload["answer"]
    assert "回滚到上一个稳定版本" in payload["answer"]
    assert "sop-001.html" in payload["answer"]
    assert "见 sources" not in payload["answer"]
    assert payload["sources"]
    assert payload["sources"][0]["id"] == "sop-001"
    successful_reads = {
        item["action"]["fname"]
        for item in payload["trace"]
        if item.get("action", {}).get("type") == "readFile"
        and item.get("observation", {}).get("ok") is True
        and item.get("observation", {}).get("accepted_as_source") is True
    }
    assert successful_reads
    for source in payload["sources"]:
        assert source["filename"] in successful_reads


def test_v3_api_trace_uses_call_stack_order(monkeypatch) -> None:
    def fake_run_agent_once(query: str, **_: object):
        return {
            "ok": True,
            "answer": "问题判断：根据已读取 SOP 回答。",
            "sources": [{"filename": "sop-001.html", "title": "后端服务 On-Call SOP"}],
            "trace": [
                {"stage": "agent", "event": "tool_allowed"},
                {"stage": "answer_composer", "event": "llm_client_created"},
                {"stage": "answer_composer", "event": "prompt_built"},
                {"stage": "answer_composer", "event": "llm_call_succeeded"},
            ],
            "runtime": {
                "status": "finished",
                "trace": [
                    {
                        "step": 0,
                        "action": {"type": "readFile", "fname": "manifest.json"},
                        "observation": {"ok": True, "accepted_as_source": False},
                    },
                    {
                        "step": 1,
                        "action": {"type": "readFile", "fname": "sop-001.html"},
                        "observation": {"ok": True, "accepted_as_source": True},
                    },
                    {
                        "step": 2,
                        "action": {"type": "finish"},
                        "observation": {"ok": True},
                    },
                ],
            },
        }

    monkeypatch.setattr("app.api.run_agent_once", fake_run_agent_once)
    client = TestClient(app)

    response = client.post("/api/oncall/query", json={"query": "服务 OOM 了怎么办？"})

    assert response.status_code == 200
    events = response.json()["trace"]
    tool_allowed_index = next(i for i, item in enumerate(events) if item.get("event") == "tool_allowed")
    readfile_index = next(i for i, item in enumerate(events) if item.get("action", {}).get("type") == "readFile")
    llm_start_index = next(i for i, item in enumerate(events) if item.get("event") == "llm_client_created")
    assert tool_allowed_index < readfile_index < llm_start_index


def test_v3_api_keeps_v3_evidence_when_answer_llm_fails(monkeypatch) -> None:
    class FailingAnswerComposer:
        def compose(self, user_query, retrieved_docs, sources, trace):
            return {
                "answer": "问题判断：LLM失败后仍使用V3证据链回答。",
                "sources": sources,
                "trace": trace,
                "answer_trace": [
                    {
                        "stage": "answer_composer",
                        "event": "llm_call_failed",
                        "error_type": "TimeoutError",
                        "error": "request timed out",
                        "fallback_layer": "v3_evidence",
                    }
                ],
                "mode": "agent",
            }

    monkeypatch.setattr("app.agent.AnswerComposer", FailingAnswerComposer)
    client = TestClient(app)

    response = client.post("/api/oncall/query", json={"query": "服务 OOM 了怎么办？"})

    assert response.status_code == 200
    payload = response.json()
    assert "回退到 v2" not in payload["answer"]
    assert payload["sources"]
    assert all(item.get("source_layer") != "v2_fallback" for item in payload["sources"])
    assert any(item.get("event") == "llm_call_failed" for item in payload["trace"])
    assert not any(item.get("rollback") == "v2" for item in payload["trace"])


def test_v3_api_returns_insufficient_evidence_for_unrelated_noise_query() -> None:
    client = TestClient(app)

    response = client.post("/api/oncall/query", json={"query": "1+1=?"})

    assert response.status_code == 200
    payload = response.json()
    assert "当前没有足够的 SOP 文档支持判断" in payload["answer"]
    assert payload["sources"] == []
    assert not any(
        item.get("observation", {}).get("accepted_as_source") is True
        for item in payload["trace"]
    )


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
    assert all(item["source_layer"] == "v2_fallback" for item in payload["sources"])
    assert payload["trace"][0]["event"] == "agent_exception"
    assert payload["trace"][0]["error_type"] == "RuntimeError"
    assert payload["trace"][0]["rollback"] == "v2"


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
    assert payload["sources"][0]["source_layer"] == "v2_fallback"
    assert payload["trace"][0]["event"] == "planner_failed"
    assert payload["trace"][1]["event"] == "agent_failed"
