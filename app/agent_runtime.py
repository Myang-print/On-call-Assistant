from dataclasses import dataclass, field
from collections.abc import Callable
import json
from pathlib import Path
import time
from typing import Any

from app.evidence_selector import select_sop_filenames
from app.html_parser import parse_html_document
from app.tool_registry import get_tool


@dataclass
class AgentState:
    max_step: int
    step: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)
    planner_retry_limit: int = 2
    tool_call_limit: int = 1
    query: str = ""
    pending_filenames: list[str] = field(default_factory=list)
    manifest_entries: list[dict[str, Any]] = field(default_factory=list)
    retrieved_docs: list[dict[str, Any]] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)


def select_action(state: AgentState) -> dict[str, str]:
    if state.step == 0:
        return {"type": "readFile", "fname": "manifest.json"}
    if (
        state.history
        and state.history[-1]["action"].get("fname") == "manifest.json"
        and not state.history[-1]["observation"]["ok"]
    ):
        return {"type": "readFile", "fname": "manifest.json"}
    if state.pending_filenames:
        return {"type": "readFile", "fname": state.pending_filenames[0]}
    return {"type": "finish", "message": "deterministic runtime complete"}


ToolMap = dict[str, Callable[[str], str]]
FallbackToV2 = Callable[[], dict[str, Any]]


def run_deterministic_agent(
    max_step: int,
    query: str = "",
    tools: ToolMap | None = None,
    fallback_to_v2: FallbackToV2 | None = None,
    planner_retry_limit: int = 2,
    tool_call_limit: int = 1,
    tool_timeout_seconds: float | None = None,
) -> dict[str, Any]:
    state = AgentState(
        max_step=max_step,
        planner_retry_limit=planner_retry_limit,
        tool_call_limit=tool_call_limit,
        query=query,
    )
    trace: list[dict[str, Any]] = []

    while state.step < state.max_step:
        action = select_action(state)
        observation = _execute_action(
            action,
            tools=tools,
            tool_call_limit=state.tool_call_limit,
            tool_timeout_seconds=tool_timeout_seconds,
        )
        content = observation.pop("_content", None)
        _record_successful_content(state, action, observation, content)
        event = {
            "step": state.step,
            "action": action,
            "observation": observation,
        }
        state.history.append(event)
        trace.append(event)
        state.step += 1
        if action["type"] == "finish":
            return {
                "status": "finished",
                "state": state,
                "trace": trace,
                "retrieved_docs": state.retrieved_docs,
                "sources": state.sources,
            }
        _consume_pending_filename(state, action)
        if observation["ok"]:
            continue

    if trace and not trace[-1]["observation"]["ok"]:
        rollback = _rollback_to_v2(fallback_to_v2)
        return {
            "status": "rolled_back_to_v2",
            "state": state,
            "trace": trace,
            "retrieved_docs": state.retrieved_docs,
            "sources": state.sources,
            "rollback": rollback,
        }

    return {
        "status": "max_step_reached",
        "state": state,
        "trace": trace,
        "retrieved_docs": state.retrieved_docs,
        "sources": state.sources,
    }


def _execute_action(
    action: dict[str, str],
    tools: ToolMap | None = None,
    tool_call_limit: int = 1,
    tool_timeout_seconds: float | None = None,
) -> dict[str, Any]:
    if action["type"] == "readFile":
        tool_name = "readFile"
        tool_function = tools[tool_name] if tools and tool_name in tools else get_tool(tool_name).function
        attempts = max(1, tool_call_limit)
        last_error = ""
        for attempt in range(1, attempts + 1):
            started_at = time.monotonic()
            try:
                content = tool_function(action["fname"])
                elapsed_seconds = time.monotonic() - started_at
                if tool_timeout_seconds is not None and elapsed_seconds > tool_timeout_seconds:
                    last_error = "tool timeout"
                    break
                return {
                    "ok": True,
                    "tool": tool_name,
                    "bytes": len(content.encode("utf-8")),
                    "attempt": attempt,
                    "_content": content,
                }
            except Exception as error:
                last_error = str(error)
        return {
            "ok": False,
            "tool": tool_name,
            "error": last_error,
            "attempts": attempts,
        }
    if action["type"] == "finish":
        return {"ok": True, "message": action["message"]}
    return {"ok": False, "error": "unknown action"}


def _rollback_to_v2(fallback_to_v2: FallbackToV2 | None) -> dict[str, Any]:
    if fallback_to_v2 is not None:
        return fallback_to_v2()
    return {
        "query": "",
        "results": [],
        "source": "v2_fallback_unconfigured",
    }


def _record_successful_content(
    state: AgentState,
    action: dict[str, str],
    observation: dict[str, Any],
    content: str | None,
) -> None:
    if not observation["ok"] or action["type"] != "readFile" or content is None:
        return

    filename = action["fname"]
    if filename == "manifest.json":
        _record_manifest_selection(state, content)
        return

    entry = _manifest_entry_for_filename(state, filename)
    if entry is None:
        observation["accepted_as_source"] = False
        return

    document = parse_html_document(doc_id=Path(filename).stem, raw_html=content)
    if document.title != str(entry.get("title", "")):
        observation["accepted_as_source"] = False
        return

    observation["accepted_as_source"] = True
    state.retrieved_docs.append(
        {
            "filename": filename,
            "title": document.title,
            "content": document.cleaned_text,
            "cleaned_text": document.cleaned_text,
        }
    )
    state.sources.append(
        {
            "id": document.doc_id,
            "filename": filename,
            "title": document.title,
            "snippet": document.cleaned_text[:80],
            "score": 1.0,
        }
    )


def _record_manifest_selection(state: AgentState, content: str) -> None:
    if not state.query:
        return
    manifest = json.loads(content)
    if not isinstance(manifest, list):
        return
    state.manifest_entries = [entry for entry in manifest if isinstance(entry, dict)]
    state.pending_filenames = select_sop_filenames(state.query, state.manifest_entries)


def _manifest_entry_for_filename(state: AgentState, filename: str) -> dict[str, Any] | None:
    for entry in state.manifest_entries:
        if entry.get("filename") == filename:
            return entry
    return None


def _consume_pending_filename(state: AgentState, action: dict[str, str]) -> None:
    if action["type"] != "readFile" or not state.pending_filenames:
        return
    if state.pending_filenames[0] == action["fname"]:
        state.pending_filenames.pop(0)
