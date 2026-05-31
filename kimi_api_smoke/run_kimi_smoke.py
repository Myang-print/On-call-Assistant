import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOTENV_PATH = PROJECT_ROOT / ".env"

SYSTEM_PROMPT = (
    "你是 Kimi，由 Moonshot AI 提供的人工智能助手，你更擅长中文和英文的对话。"
    "你会为用户提供安全，有帮助，准确的回答。"
    "Moonshot AI 为专有名词，不可翻译成其他语言。"
)


def main() -> int:
    load_project_env()

    try:
        from openai import OpenAI
    except ImportError:
        print('OpenAI SDK is not installed. Run: pip install --upgrade "openai>=1.0"')
        return 2

    api_key = os.getenv("MOONSHOT_API_KEY", "").strip()
    base_url = os.getenv("MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1").strip()
    model = os.getenv("MOONSHOT_MODEL", "kimi-k2.6").strip()

    print(f"base_url={base_url}")
    print(f"model={model}")
    print(f"env_file={DOTENV_PATH}")
    print(f"env_file_exists={DOTENV_PATH.exists()}")
    print(f"key_present={bool(api_key)}")
    print(f"key_length={len(api_key)}")

    if not api_key:
        print("MOONSHOT_API_KEY is required.")
        return 2

    client = OpenAI(api_key=api_key, base_url=base_url)

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "你好，我叫李雷，1+1等于多少？"},
            ],
            temperature=1,
        )
    except Exception as error:
        print(f"request_ok=False")
        print(f"error_type={type(error).__name__}")
        print(f"error={_safe_error(error)}")
        return 1

    answer = completion.choices[0].message.content
    print("request_ok=True")
    print("assistant_response:")
    print(answer)
    return 0


def load_project_env() -> None:
    if not DOTENV_PATH.exists() or not DOTENV_PATH.is_file():
        return
    for raw_line in DOTENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = strip_env_quotes(value.strip())


def strip_env_quotes(value: str) -> str:
    return value.strip().strip("\"'“”‘’")


def _safe_error(error: Exception) -> str:
    message = str(error).replace("\n", " ")
    if len(message) > 500:
        return message[:500] + "..."
    return message


if __name__ == "__main__":
    raise SystemExit(main())
