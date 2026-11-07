"""The seam between the gateway and detection. The gateway only knows this protocol."""

import logging
from dataclasses import dataclass
from typing import Any, Protocol

from sentinel.features.events import Action, Signals, ToolName

logger = logging.getLogger("sentinel.gateway")


@dataclass(frozen=True)
class ScoringInput:
    session_id: str
    step: int
    tool: ToolName
    args: dict[str, Any]


@dataclass(frozen=True)
class Score:
    signals: Signals
    risk: float
    action: Action


class Scorer(Protocol):
    def score(self, call: ScoringInput) -> Score: ...


class UnscoredScorer:
    """Explicit stand-in until detection exists: allows everything and says so loudly."""

    def __init__(self) -> None:
        logger.warning("Detection is NOT enabled: every tool call is ALLOWed with risk 0.")

    def score(self, call: ScoringInput) -> Score:
        return Score(signals=Signals(), risk=0.0, action=Action.ALLOW)
