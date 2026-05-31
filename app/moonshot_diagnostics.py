import json
from collections.abc import Callable
from typing import Any

import httpx

from app.llm_client import MoonshotLLMClient, select_llm_client


Requester = Callable[[str, dict[str, Any], dict[str, str], float], dict[str, Any]]


def diagnose_moonshot_connectivity(requester: Requester | None = None) -> dict[str, Any]:
    try:
        selected_client = select_llm_client(provider="moonshot")
    except Exception as error:
        return {
            "ok": False,
            "stage": "config",
            "category": "configuration",
            "error_type": type(error).__name__,
            "error": _safe_error_message(error),
        }

    if not isinstance(selected_client, MoonshotLLMClient):
        return {
            "ok": False,
            "stage": "config",
            "category": "configuration",
            "error": f"unexpected client type: {type(selected_client).__name__}",
        }

    endpoint = selected_client.base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": selected_client.model,
        "messages": [{"role": "user", "content": "请只回复 ok，用于连通性诊断。"}],
        "temperature": 0,
    }
    headers = {
        "Authorization": f"Bearer {selected_client.api_key}",
        "Content-Type": "application/json",
    }
    result: dict[str, Any] = {
        "ok": False,
        "stage": "request",
        "provider": "moonshot",
        "client_type": type(selected_client).__name__,
        "base_url": selected_client.base_url,
        "endpoint": endpoint,
        "model": selected_client.model,
        "key_present": bool(selected_client.api_key),
        "key_length": len(selected_client.api_key),
        "request_dispatch": "started",
    }

    try:
        response_payload = (requester or _default_requester)(endpoint, payload, headers, selected_client.timeout)
    except Exception as error:
        result.update(_classify_error(error))
        return result

    content = _extract_content(response_payload)
    result.update(
        {
            "ok": True,
            "stage": "response",
            "category": "success",
            "request_dispatch": "completed",
            "response_chars": len(content),
            "response_preview": content[:80],
        }
    )
    return result


def _default_requester(
    endpoint: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: float,
) -> dict[str, Any]:
    with httpx.Client(timeout=timeout) as client:
        response = client.post(endpoint, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
    return data if isinstance(data, dict) else {}


def _classify_error(error: Exception) -> dict[str, Any]:
    if isinstance(error, httpx.HTTPStatusError):
        status_code = error.response.status_code
        return {
            "category": _http_status_category(status_code),
            "error_type": type(error).__name__,
            "status_code": status_code,
            "error": _safe_error_message(error),
        }
    if isinstance(error, (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.TimeoutException)):
        return {
            "category": "timeout",
            "error_type": type(error).__name__,
            "error": _safe_error_message(error),
        }
    if isinstance(error, httpx.ProxyError):
        return {
            "category": "proxy",
            "error_type": type(error).__name__,
            "error": _safe_error_message(error),
        }
    if isinstance(error, httpx.ConnectError):
        return {
            "category": _connect_error_category(error),
            "error_type": type(error).__name__,
            "error": _safe_error_message(error),
        }
    return {
        "category": "unknown",
        "error_type": type(error).__name__,
        "error": _safe_error_message(error),
    }


def _http_status_category(status_code: int) -> str:
    if status_code in {401, 403}:
        return "authentication"
    if status_code == 404:
        return "endpoint_or_model"
    if status_code == 429:
        return "rate_limit"
    if status_code >= 500:
        return "provider_error"
    return "http_error"


def _connect_error_category(error: Exception) -> str:
    message = str(error).casefold()
    if "getaddrinfo" in message or "name or service" in message or "dns" in message:
        return "dns_resolution"
    return "connection_error"


def _extract_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    return content if isinstance(content, str) else ""


def _safe_error_message(error: Exception) -> str:
    message = str(error).replace("\n", " ")
    if len(message) > 240:
        return message[:240] + "..."
    return message


if __name__ == "__main__":
    print(json.dumps(diagnose_moonshot_connectivity(), ensure_ascii=False, indent=2))
