import shutil
import uuid
from pathlib import Path

from app import llm_client
from app.llm_client import MoonshotLLMClient, select_llm_client


def test_select_moonshot_client_loads_project_env_and_strips_quotes(monkeypatch) -> None:
    tmp_dir = Path(f".pytest-local-env-test-{uuid.uuid4().hex}")
    tmp_dir.mkdir()
    monkeypatch.chdir(tmp_dir)
    monkeypatch.delenv("ONCALL_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
    monkeypatch.delenv("MOONSHOT_BASE_URL", raising=False)
    monkeypatch.delenv("MOONSHOT_MODEL", raising=False)
    monkeypatch.delenv("MOONSHOT_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("MOONSHOT_MAX_TOKENS", raising=False)
    monkeypatch.setattr(llm_client, "_DOTENV_LOADED", False)
    try:
        Path(".env").write_text(
            "\n".join(
                [
                    "ONCALL_LLM_PROVIDER=moonshot",
                    "MOONSHOT_BASE_URL=https://api.moonshot.cn/v1",
                    "MOONSHOT_MODEL=kimi-k2.6",
                    "MOONSHOT_TIMEOUT_SECONDS=120",
                    "MOONSHOT_MAX_TOKENS=700",
                    "MOONSHOT_THINKING=enabled",
                    "MOONSHOT_API_KEY=“sk-test-key”",
                ]
            ),
            encoding="utf-8",
        )

        client = select_llm_client()

        assert isinstance(client, MoonshotLLMClient)
        assert client.api_key == "sk-test-key"
        assert client.base_url == "https://api.moonshot.cn/v1"
        assert client.model == "kimi-k2.6"
        assert client.timeout == 120.0
        assert client.max_tokens == 700
        assert client.thinking == "enabled"
    finally:
        monkeypatch.chdir("..")
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_select_moonshot_client_defaults_to_short_oncall_output_budget(monkeypatch) -> None:
    monkeypatch.setattr(llm_client, "_DOTENV_LOADED", True)
    monkeypatch.setenv("ONCALL_LLM_PROVIDER", "moonshot")
    monkeypatch.setenv("MOONSHOT_API_KEY", "sk-test-key")
    monkeypatch.delenv("MOONSHOT_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("MOONSHOT_MAX_TOKENS", raising=False)
    monkeypatch.delenv("MOONSHOT_THINKING", raising=False)

    client = select_llm_client()

    assert isinstance(client, MoonshotLLMClient)
    assert client.timeout == 90.0
    assert client.max_tokens == 1200
    assert client.thinking == "disabled"


def test_moonshot_client_uses_openai_sdk_compatible_chat_completion() -> None:
    captured: dict[str, object] = {}

    def client_factory(api_key, base_url, timeout):
        captured["api_key"] = api_key
        captured["base_url"] = base_url
        captured["timeout"] = timeout
        return FakeOpenAIClient(captured, response="自然语言回复")

    client = MoonshotLLMClient(
        api_key="sk-test-key",
        base_url="https://api.moonshot.cn/v1",
        model="kimi-k2.6",
        timeout=12.0,
        max_tokens=345,
        thinking="enabled",
        client_factory=client_factory,
    )

    answer = client.complete("你好")

    assert answer == "自然语言回复"
    assert captured["api_key"] == "sk-test-key"
    assert captured["base_url"] == "https://api.moonshot.cn/v1"
    assert captured["timeout"] == 12.0
    assert captured["model"] == "kimi-k2.6"
    assert captured["messages"] == [{"role": "user", "content": "你好"}]
    assert captured["temperature"] == 1
    assert captured["max_tokens"] == 345
    assert "extra_body" not in captured


def test_moonshot_client_disables_thinking_for_short_oncall_answers_by_default() -> None:
    captured: dict[str, object] = {}
    client = MoonshotLLMClient(
        api_key="sk-test-key",
        base_url="https://api.moonshot.cn/v1",
        model="kimi-k2.6",
        timeout=12.0,
        max_tokens=1200,
        client_factory=lambda api_key, base_url, timeout: FakeOpenAIClient(captured, response="自然语言回复"),
    )

    answer = client.complete("你好")

    assert answer == "自然语言回复"
    assert captured["extra_body"] == {"thinking": {"type": "disabled"}}
    assert "temperature" not in captured


def test_moonshot_client_exposes_completion_metadata() -> None:
    captured: dict[str, object] = {}
    client = MoonshotLLMClient(
        api_key="sk-test-key",
        base_url="https://api.moonshot.cn/v1",
        model="kimi-k2.6",
        timeout=12.0,
        max_tokens=345,
        thinking="enabled",
        client_factory=lambda api_key, base_url, timeout: FakeOpenAIClient(
            captured,
            response="自然语言回复",
            finish_reason="length",
        ),
    )

    completion = client.complete_with_metadata("你好")

    assert completion.content == "自然语言回复"
    assert completion.finish_reason == "length"
    assert completion.raw_answer_chars == 6


class FakeOpenAIClient:
    def __init__(self, captured: dict[str, object], response: str, finish_reason: str = "stop") -> None:
        self.chat = FakeChat(captured, response, finish_reason)


class FakeChat:
    def __init__(self, captured: dict[str, object], response: str, finish_reason: str) -> None:
        self.completions = FakeCompletions(captured, response, finish_reason)


class FakeCompletions:
    def __init__(self, captured: dict[str, object], response: str, finish_reason: str) -> None:
        self._captured = captured
        self._response = response
        self._finish_reason = finish_reason

    def create(self, model, messages, max_tokens, temperature=None, extra_body=None):
        self._captured["model"] = model
        self._captured["messages"] = messages
        if temperature is not None:
            self._captured["temperature"] = temperature
        if extra_body is not None:
            self._captured["extra_body"] = extra_body
        self._captured["max_tokens"] = max_tokens
        return FakeCompletion(self._response, self._finish_reason)


class FakeCompletion:
    def __init__(self, content: str, finish_reason: str) -> None:
        self.choices = [FakeChoice(content, finish_reason)]


class FakeChoice:
    def __init__(self, content: str, finish_reason: str) -> None:
        self.message = FakeMessage(content)
        self.finish_reason = finish_reason


class FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content
