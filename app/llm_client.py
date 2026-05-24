import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from app.schemas import LLMObservation


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


def select_llm_client(provider: str | None = None) -> LLMClient:
    selected_provider = (provider or os.getenv("ONCALL_LLM_PROVIDER", "deterministic")).strip().casefold()
    if selected_provider == "deterministic":
        return DeterministicLLMClient()
    raise ValueError(f"unsupported llm provider: {selected_provider}")
