import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from sentinel.features.events import (
    Action,
    Decision,
    DecisionSource,
    Explanation,
    RuleId,
    SentinelEvent,
    ToolName,
    ToolResult,
    Verdict,
)

EXAMPLE_PATH = Path(__file__).resolve().parents[4] / "docs" / "contract" / "event.example.json"


@pytest.fixture
def example() -> dict[str, Any]:
    return json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))


def test_roadmap_example_parses(example: dict[str, Any]) -> None:
    event = SentinelEvent.model_validate(example)

    assert event.tool is ToolName.SEND_EMAIL
    assert event.action is Action.PAUSE
    assert event.signals.rules == [RuleId.UNKNOWN_DESTINATION]
    assert event.explanation is None and event.decision is None and event.result is None


def test_json_round_trip_keeps_utc_z_timestamp(example: dict[str, Any]) -> None:
    event = SentinelEvent.model_validate(example)

    dumped = event.model_dump(mode="json")

    assert dumped == example
    assert dumped["ts"] == "2026-11-21T14:03:11Z"


def test_lifecycle_update_produces_new_snapshot(example: dict[str, Any]) -> None:
    created = SentinelEvent.model_validate(example)
    decided = created.model_copy(
        update={
            "explanation": Explanation(
                verdict=Verdict.MALICIOUS,
                explanation="Secret data read from .env is being emailed to an unknown domain.",
                what_to_check="Did the user ask to send credentials anywhere?",
            ),
            "decision": Decision(
                approve=False,
                reason="No human response: fail-safe deny",
                source=DecisionSource.TIMEOUT,
                ts=datetime(2026, 11, 21, 14, 4, 41, tzinfo=UTC),
            ),
            "result": ToolResult(ok=False, preview="Blocked by Sentinel"),
        }
    )

    assert created.decision is None
    assert decided.decision is not None and decided.decision.source is DecisionSource.TIMEOUT
    assert SentinelEvent.model_validate(decided.model_dump(mode="json")) == decided


def test_events_are_immutable(example: dict[str, Any]) -> None:
    event = SentinelEvent.model_validate(example)

    with pytest.raises(ValidationError):
        event.risk = 0.1  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("tool", "rm_rf"),
        ("action", "BLOCK"),
        ("risk", 1.5),
        ("risk", -0.1),
        ("step", -1),
        ("event_id", "0042"),
        ("session_id", "session 7"),
        ("ts", "2026-11-21T14:03:11"),  # naive timestamps are ambiguous
        ("unexpected_field", "x"),
    ],
)
def test_rejects_invalid_top_level_fields(example: dict[str, Any], field: str, value: Any) -> None:
    with pytest.raises(ValidationError):
        SentinelEvent.model_validate({**example, field: value})


@pytest.mark.parametrize(
    "signals",
    [
        {"rules": ["made_up_rule"]},
        {"ml_risk": 1.01},
        {"markov_risk": -0.5},
    ],
)
def test_rejects_invalid_signals(example: dict[str, Any], signals: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        SentinelEvent.model_validate({**example, "signals": {**example["signals"], **signals}})


def test_result_preview_is_capped_at_200_chars() -> None:
    with pytest.raises(ValidationError):
        ToolResult(ok=True, preview="x" * 201)
