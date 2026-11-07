"""The Sentinel event contract: the one shape shared by gateway, audit log, SSE and dashboard.

An event is created when a tool call is scored and then updated as it moves through its
lifecycle. Every SSE message carries the *full* event snapshot; the SSE event name
(`StreamEventType`) says what changed, so clients simply replace the event by `event_id`.
"""

from enum import StrEnum
from typing import Annotated, Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

RiskScore = Annotated[float, Field(ge=0.0, le=1.0)]


class ContractModel(BaseModel):
    # Frozen: lifecycle updates produce a new snapshot via model_copy(update=...).
    model_config = ConfigDict(extra="forbid", frozen=True)


class ToolName(StrEnum):
    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    DELETE_FILE = "delete_file"
    LIST_DIR = "list_dir"
    FETCH_URL = "fetch_url"
    SEND_EMAIL = "send_email"
    HTTP_POST = "http_post"


class RuleId(StrEnum):
    SENSITIVE_READ = "sensitive_read"
    UNKNOWN_DESTINATION = "unknown_destination"
    DESTRUCTIVE_OUTSIDE_TMP = "destructive_outside_tmp"
    HONEYTOKEN = "honeytoken"


class Action(StrEnum):
    ALLOW = "ALLOW"
    FLAG = "FLAG"
    PAUSE = "PAUSE"


class Verdict(StrEnum):
    BENIGN = "benign"
    SUSPICIOUS = "suspicious"
    MALICIOUS = "malicious"


class DecisionSource(StrEnum):
    HUMAN = "human"
    TIMEOUT = "timeout"


class StreamEventType(StrEnum):
    """SSE event name: which part of the event changed in this snapshot."""

    CREATED = "created"
    EXPLAINED = "explained"
    DECIDED = "decided"
    COMPLETED = "completed"


class Signals(ContractModel):
    rules: list[RuleId] = Field(default_factory=list)
    taint: bool = False
    ml_risk: RiskScore = 0.0
    markov_risk: RiskScore = 0.0


class Explanation(ContractModel):
    """Advisory output of the Claude judge. It never changes risk or action."""

    verdict: Verdict
    explanation: str
    what_to_check: str


class Decision(ContractModel):
    approve: bool
    reason: str
    source: DecisionSource
    ts: AwareDatetime


class ToolResult(ContractModel):
    ok: bool
    preview: str = Field(max_length=200)


class SentinelEvent(ContractModel):
    event_id: str = Field(pattern=r"^evt_[A-Za-z0-9]+$")
    session_id: str = Field(pattern=r"^s_[A-Za-z0-9]+$")
    step: int = Field(ge=0)
    ts: AwareDatetime
    tool: ToolName
    args: dict[str, Any]
    signals: Signals
    risk: RiskScore
    action: Action
    explanation: Explanation | None = None
    decision: Decision | None = None
    result: ToolResult | None = None
