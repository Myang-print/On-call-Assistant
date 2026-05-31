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
    monkeypatch.setattr(llm_client, "_DOTENV_LOADED", False)
    try:
        Path(".env").write_text(
            "\n".join(
                [
                    "ONCALL_LLM_PROVIDER=moonshot",
                    "MOONSHOT_BASE_URL=https://api.moonshot.cn/v1",
                    "MOONSHOT_MODEL=kimi-k2.6",
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
    finally:
        monkeypatch.chdir("..")
        shutil.rmtree(tmp_dir, ignore_errors=True)
