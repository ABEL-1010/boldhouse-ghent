from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from sentinel.features.events import Action, Decision, ToolName

MIN_APPROVAL_REASON_CHARS = 10


class ToolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(pattern=r"^s_[A-Za-z0-9]+$")
    tool: ToolName
    args: dict[str, Any] = Field(default_factory=dict)


class ToolResponse(BaseModel):
    ok: bool
    content: str
    event_id: str
    action: Action


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approve: bool
    reason: str = ""


class DecisionResponse(BaseModel):
    ok: bool
    decision: Decision
