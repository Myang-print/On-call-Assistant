from collections.abc import Callable
from dataclasses import dataclass

from app.tool_runtime import readFile


@dataclass(frozen=True)
class ToolSpec:
    name: str
    function: Callable[[str], str]
    description: str
    parameters: dict[str, str]
    safety_constraints: tuple[str, ...]


READ_FILE_TOOL = ToolSpec(
    name="readFile",
    function=readFile,
    description="Read one explicit filename from the data directory.",
    parameters={"fname": "Explicit filename under data/."},
    safety_constraints=(
        "Reject empty filenames.",
        "Reject wildcard patterns.",
        "Reject path traversal and subpaths.",
        "Reject directory reads.",
        "Reject JSON files except manifest.json.",
    ),
)

TOOL_REGISTRY: dict[str, ToolSpec] = {READ_FILE_TOOL.name: READ_FILE_TOOL}


def list_tools() -> list[ToolSpec]:
    return list(TOOL_REGISTRY.values())


def get_tool(name: str) -> ToolSpec:
    return TOOL_REGISTRY[name]
