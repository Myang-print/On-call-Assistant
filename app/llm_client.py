import json
import os
from pathlib import Path
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.schemas import LLMObservation


_DOTENV_LOADED = False


class LLMClient(Protocol):
    def complete(self, prompt: str) -> str:
        ...


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
    timeout: float = 30.0

    def complete(self, prompt: str) -> str:
        endpoint = self.base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        return str(data["choices"][0]["message"]["content"])


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
