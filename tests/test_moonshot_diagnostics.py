import httpx

from app import llm_client
from app.moonshot_diagnostics import diagnose_moonshot_connectivity


def _set_moonshot_env(monkeypatch) -> None:
    monkeypatch.setattr(llm_client, "_DOTENV_LOADED", True)
    monkeypatch.setenv("MOONSHOT_API_KEY", "sk-test-key")
    monkeypatch.setenv("MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1")
    monkeypatch.setenv("MOONSHOT_MODEL", "kimi-k2.6")


def test_moonshot_diagnostic_success_reports_endpoint_model_and_response(monkeypatch) -> None:
    _set_moonshot_env(monkeypatch)
    captured: dict[str, object] = {}

    def requester(endpoint, payload, headers, timeout):
        captured["endpoint"] = endpoint
        captured["payload"] = payload
        captured["headers"] = headers
        captured["timeout"] = timeout
        return {"choices": [{"message": {"content": "ok"}}]}

    result = diagnose_moonshot_connectivity(requester=requester)

    assert result["ok"] is True
    assert result["category"] == "success"
    assert result["client_type"] == "MoonshotLLMClient"
    assert result["endpoint"] == "https://api.moonshot.cn/v1/chat/completions"
    assert result["model"] == "kimi-k2.6"
    assert result["key_present"] is True
    assert "sk-test-key" not in str(result)
    assert captured["endpoint"] == "https://api.moonshot.cn/v1/chat/completions"
    assert "Authorization" in captured["headers"]


def test_moonshot_diagnostic_reports_authentication_error(monkeypatch) -> None:
    _set_moonshot_env(monkeypatch)

    def requester(endpoint, payload, headers, timeout):
        request = httpx.Request("POST", endpoint)
        response = httpx.Response(401, request=request, text="bad key")
        raise httpx.HTTPStatusError("unauthorized", request=request, response=response)

    result = diagnose_moonshot_connectivity(requester=requester)

    assert result["ok"] is False
    assert result["category"] == "authentication"
    assert result["status_code"] == 401


def test_moonshot_diagnostic_reports_timeout(monkeypatch) -> None:
    _set_moonshot_env(monkeypatch)

    def requester(endpoint, payload, headers, timeout):
        raise httpx.ConnectTimeout("timed out")

    result = diagnose_moonshot_connectivity(requester=requester)

    assert result["ok"] is False
    assert result["category"] == "timeout"
    assert result["error_type"] == "ConnectTimeout"


def test_moonshot_diagnostic_reports_connection_error(monkeypatch) -> None:
    _set_moonshot_env(monkeypatch)

    def requester(endpoint, payload, headers, timeout):
        raise httpx.ConnectError("[WinError 10061] target actively refused")

    result = diagnose_moonshot_connectivity(requester=requester)

    assert result["ok"] is False
    assert result["category"] == "connection_error"
    assert result["error_type"] == "ConnectError"


def test_moonshot_diagnostic_reports_missing_key_without_request(monkeypatch) -> None:
    monkeypatch.setattr(llm_client, "_DOTENV_LOADED", True)
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)

    result = diagnose_moonshot_connectivity(requester=lambda *_: {"choices": []})

    assert result["ok"] is False
    assert result["stage"] == "config"
    assert result["category"] == "configuration"
    assert result["error_type"] == "ValueError"
