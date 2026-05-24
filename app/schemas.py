from dataclasses import dataclass
from typing import Any, Literal


PlannerActionType = Literal["tool"]
ToolName = Literal["readFile"]
ObservationStatus = Literal["ok", "retry"]


@dataclass(frozen=True)
class ToolAction:
    tool: ToolName
    args: dict[str, str]

    def to_json_dict(self) -> dict[str, Any]:
        return {"tool": self.tool, "args": dict(self.args)}


@dataclass(frozen=True)
class LLMObservation:
    action: PlannerActionType
    tool: ToolName
    args: dict[str, str]

    @classmethod
    def read_file(cls, fname: str) -> "LLMObservation":
        return cls(action="tool", tool="readFile", args={"fname": fname})

    def to_json_dict(self) -> dict[str, Any]:
        return {"action": self.action, "tool": self.tool, "args": dict(self.args)}


LLM_OBSERVATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["action", "tool", "args"],
    "properties": {
        "action": {"const": "tool"},
        "tool": {"enum": ["readFile"]},
        "args": {
            "type": "object",
            "required": ["fname"],
            "properties": {"fname": {"type": "string"}},
        },
    },
}

TOOL_ACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["tool", "args"],
    "properties": {
        "tool": {"enum": ["readFile"]},
        "args": {
            "type": "object",
            "required": ["fname"],
            "properties": {"fname": {"type": "string"}},
        },
    },
}

# Backward-compatible names for earlier deterministic tests and callers.
ToolCall = ToolAction
LLMPlannerResponse = LLMObservation
LLM_RESPONSE_SCHEMA = LLM_OBSERVATION_SCHEMA
TOOL_TRANSPORT_SCHEMA = TOOL_ACTION_SCHEMA
