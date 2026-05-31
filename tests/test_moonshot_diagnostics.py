import httpx

from app import llm_client
from app.moonshot_diagnostics import diagnose_moonshot_connectivity


def _set_moonshot_env(monkeypatch) -> None:
    monkeypatch.setattr(llm_client, "_DOTENV_LOADED", True)
    monkeypatch.setenv("MOONSHOT_API_KEY", "sk-test-key")
    monkeypatch.setenv("MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1")
    monkeypatch.setenv("MOONSHOT_MODEL", "kimi-k2.6")
    monkeypatch.delenv("MOONSHOT_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("MOONSHOT_MAX_TOKENS", raising=False)
    monkeypatch.delenv("MOONSHOT_THINKING", raising=False)


def test_moonshot_diagnostic_success_reports_endpoint_model_and_response(monkeypatch) -> None:
    _set_moonshot_env(monkeypatch)
    captured: dict[str, object] = {}

    def client_factory(api_key, base_url, timeout):
        captured["api_key"] = api_key
        captured["base_url"] = base_url
        captured["timeout"] = timeout
        return FakeOpenAIClient(captured, response="ok")

    result = diagnose_moonshot_connectivity(client_factory=client_factory)

    assert result["ok"] is True
    assert result["category"] == "success"
    assert result["client_type"] == "MoonshotLLMClient"
    assert result["endpoint"] == "https://api.moonshot.cn/v1/chat/completions"
    assert result["model"] == "kimi-k2.6"
    assert result["timeout_seconds"] == 90.0
    assert result["max_tokens"] == 1200
    assert result["thinking"] == "disabled"
    assert result["key_present"] is True
    assert "sk-test-key" not in str(result)
    assert captured["base_url"] == "https://api.moonshot.cn/v1"
    assert captured["model"] == "kimi-k2.6"
    assert captured["messages"] == [{"role": "user", "content": "请只回复 ok，用于连通性诊断。"}]
    assert captured["extra_body"] == {"thinking": {"type": "disabled"}}
    assert captured["max_tokens"] == 1200


def test_moonshot_diagnostic_reports_authentication_error(monkeypatch) -> None:
    _set_moonshot_env(monkeypatch)

    def client_factory(api_key, base_url, timeout):
        request = httpx.Request("POST", base_url)
        response = httpx.Response(401, request=request, text="bad key")
        return FakeOpenAIClient({}, error=httpx.HTTPStatusError("unauthorized", request=request, response=response))

    result = diagnose_moonshot_connectivity(client_factory=client_factory)

    assert result["ok"] is False
    assert result["category"] == "authentication"
    assert result["status_code"] == 401


def test_moonshot_diagnostic_reports_timeout(monkeypatch) -> None:
    _set_moonshot_env(monkeypatch)

    def client_factory(api_key, base_url, timeout):
        return FakeOpenAIClient({}, error=httpx.ConnectTimeout("timed out"))

    result = diagnose_moonshot_connectivity(client_factory=client_factory)

    assert result["ok"] is False
    assert result["category"] == "timeout"
    assert result["error_type"] == "ConnectTimeout"


def test_moonshot_diagnostic_reports_connection_error(monkeypatch) -> None:
    _set_moonshot_env(monkeypatch)

    def client_factory(api_key, base_url, timeout):
        return FakeOpenAIClient({}, error=httpx.ConnectError("[WinError 10061] target actively refused"))

    result = diagnose_moonshot_connectivity(client_factory=client_factory)

    assert result["ok"] is False
    assert result["category"] == "connection_error"
    assert result["error_type"] == "ConnectError"


def test_moonshot_diagnostic_reports_missing_key_without_request(monkeypatch) -> None:
    monkeypatch.setattr(llm_client, "_DOTENV_LOADED", True)
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)

    result = diagnose_moonshot_connectivity(client_factory=lambda **_: FakeOpenAIClient({}))

    assert result["ok"] is False
    assert result["stage"] == "config"
    assert result["category"] == "configuration"
    assert result["error_type"] == "ValueError"


class FakeOpenAIClient:
    def __init__(self, captured: dict[str, object], response: str = "ok", error: Exception | None = None) -> None:
        self.chat = FakeChat(captured, response, error)


class FakeChat:
    def __init__(self, captured: dict[str, object], response: str, error: Exception | None) -> None:
        self.completions = FakeCompletions(captured, response, error)


class FakeCompletions:
    def __init__(self, captured: dict[str, object], response: str, error: Exception | None) -> None:
        self._captured = captured
        self._response = response
        self._error = error

    def create(self, model, messages, max_tokens, temperature=None, extra_body=None):
        if self._error:
            raise self._error
        self._captured["model"] = model
        self._captured["messages"] = messages
        if temperature is not None:
            self._captured["temperature"] = temperature
        if extra_body is not None:
            self._captured["extra_body"] = extra_body
        self._captured["max_tokens"] = max_tokens
        return FakeCompletion(self._response)


class FakeCompletion:
    def __init__(self, content: str) -> None:
        self.choices = [FakeChoice(content)]


class FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = FakeMessage(content)


class FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content
