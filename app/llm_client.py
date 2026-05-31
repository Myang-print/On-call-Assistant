import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import Protocol

from app.schemas import LLMObservation


_DOTENV_LOADED = False


class LLMClient(Protocol):
    def complete(self, prompt: str) -> str:
        ...


@dataclass(frozen=True)
class LLMCompletion:
    content: str
    finish_reason: str | None
    raw_answer_chars: int


@dataclass(frozen=True)
class DeterministicLLMClient:
    default_filename: str = "manifest.json"

    def complete(self, prompt: str) -> str:
        response = LLMObservation.read_file(self.default_filename)
        return json.dumps(response.to_json_dict(), ensure_ascii=False)


@dataclass(frozen=True)
class CallableLLMClient:
    complete_fn: Callable[[str], str]

    def complete(self, prompt: str) -> str:
        return self.complete_fn(prompt)


@dataclass(frozen=True)
class MoonshotLLMClient:
    api_key: str
    base_url: str = "https://api.moonshot.cn/v1"
    model: str = "kimi-k2.6"
    timeout: float = 90.0
    max_tokens: int = 1200
    thinking: str = "disabled"
    client_factory: Callable[..., Any] | None = None

    def complete(self, prompt: str) -> str:
        return self.complete_with_metadata(prompt).content

    def complete_with_metadata(self, prompt: str) -> LLMCompletion:
        factory = self.client_factory or _openai_client_factory()
        client = factory(api_key=self.api_key, base_url=self.base_url, timeout=self.timeout)
        completion_args: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self.max_tokens,
        }
        if self.thinking == "disabled":
            completion_args["extra_body"] = {"thinking": {"type": "disabled"}}
        else:
            completion_args["temperature"] = 1
        completion = client.chat.completions.create(**completion_args)
        choice = completion.choices[0]
        content = str(choice.message.content)
        return LLMCompletion(
            content=content,
            finish_reason=getattr(choice, "finish_reason", None),
            raw_answer_chars=len(content),
        )


def select_llm_client(provider: str | None = None) -> LLMClient:
    selected_provider = (provider or _env("ONCALL_LLM_PROVIDER", "deterministic")).strip().casefold()
    if selected_provider == "deterministic":
        return DeterministicLLMClient()
    if selected_provider in {"moonshot", "kimi", "kimi-k2.6"}:
        api_key = _env("MOONSHOT_API_KEY", "").strip()
        if not api_key:
            raise ValueError("MOONSHOT_API_KEY is required for moonshot provider")
        return MoonshotLLMClient(
            api_key=api_key,
            base_url=_env("MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1"),
            model=_env("MOONSHOT_MODEL", "kimi-k2.6"),
            timeout=_env_float("MOONSHOT_TIMEOUT_SECONDS", 90.0),
            max_tokens=_env_int("MOONSHOT_MAX_TOKENS", 1200),
            thinking=_env_choice("MOONSHOT_THINKING", "disabled", {"enabled", "disabled"}),
        )
    raise ValueError(f"unsupported llm provider: {selected_provider}")


def _env(name: str, default: str = "") -> str:
    _load_dotenv_once()
    return _strip_env_quotes(os.getenv(name, default))


def _load_dotenv_once() -> None:
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    _DOTENV_LOADED = True
    env_path = Path(".env")
    if not env_path.exists() or not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = _strip_env_quotes(value.strip())


def _strip_env_quotes(value: str) -> str:
    return value.strip().strip("\"'“”‘’")


def _env_float(name: str, default: float) -> float:
    raw_value = _env(name, "")
    if not raw_value:
        return default
    try:
        value = float(raw_value)
    except ValueError:
        return default
    return value if value > 0 else default


def _env_int(name: str, default: int) -> int:
    raw_value = _env(name, "")
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        return default
    return value if value > 0 else default


def _env_choice(name: str, default: str, allowed: set[str]) -> str:
    value = _env(name, "").casefold()
    if not value:
        return default
    return value if value in allowed else default


def _openai_client_factory() -> Callable[..., Any]:
    try:
        from openai import OpenAI
    except ImportError as error:
        raise RuntimeError('OpenAI SDK is required for Moonshot. Run: pip install --upgrade "openai>=1.0"') from error
    return OpenAI
