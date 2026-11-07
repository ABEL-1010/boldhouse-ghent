"""Trace records: one JSON line per tool call, with the features Sentinel computed before it ran."""

import json
import zlib
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from sentinel.features.detection import Score, ScoringInput, extract_features
from sentinel.features.events import Action, Signals

Split = Literal["train", "holdout"]
HOLDOUT_BUCKETS = 5  # ~1 in 5 sessions (20%) held out for calibration


def split_for(session_id: str) -> Split:
    """Stable pseudo-random split by session id.

    Must not depend on the task: plans are assigned round-robin, so "every 5th session" would
    hold out only a few task types and calibration would never see the others.
    """
    bucket = zlib.crc32(session_id.encode()) % HOLDOUT_BUCKETS
    return "holdout" if bucket == 0 else "train"


@dataclass(frozen=True)
class TraceRecord:
    session_id: str
    task: str
    split: Split
    step: int
    tool: str
    args: dict[str, Any]
    ok: bool
    features: dict[str, float]


class RecordingScorer:
    """Captures the production feature vector for every call and always allows it.

    Running through the real gateway means context updates and features are exactly what
    serving computes, so training and serving cannot drift apart.
    """

    def __init__(self) -> None:
        self.features: dict[tuple[str, int], dict[str, float]] = {}

    def score(self, call: ScoringInput) -> Score:
        self.features[(call.session_id, call.step)] = extract_features(
            call.tool, call.args, call.context
        )
        return Score(signals=Signals(), risk=0.0, action=Action.ALLOW)


def write_traces(path: Path, records: Iterable[TraceRecord]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as out:
        for record in records:
            out.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
            count += 1
    return count


def read_traces(path: Path) -> list[TraceRecord]:
    with path.open(encoding="utf-8") as lines:
        return [TraceRecord(**json.loads(line)) for line in lines if line.strip()]
