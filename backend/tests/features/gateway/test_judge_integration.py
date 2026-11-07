"""The judge is advisory: it explains FLAG/PAUSE events and never changes what happens."""

import asyncio
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from sentinel.core.config import Settings
from sentinel.features.events import (
    EventBus,
    Explanation,
    SentinelEvent,
    StreamEventType,
    Verdict,
)
from sentinel.features.tools import ToolService
from sentinel.main import create_app

from .conftest import RuleScorer, wait_for_pause

EMAIL = {"to": "backup@unknown-domain.xyz", "subject": "s", "body": "secrets"}


class FakeJudge:
    """Answers after `delay`; says 'benign' to prove its verdict changes nothing."""

    def __init__(self, delay: float = 0.0, verdict: Verdict = Verdict.BENIGN) -> None:
        self.delay, self.verdict = delay, verdict
        self.seen: list[str] = []

    async def explain(self, event: SentinelEvent) -> Explanation | None:
        self.seen.append(event.event_id)
        await asyncio.sleep(self.delay)
        return Explanation(
            verdict=self.verdict, explanation="Looks fine.", what_to_check="Nothing."
        )


def build(workspace: Path, outbox: Path, scorer: RuleScorer, judge: FakeJudge) -> FastAPI:
    tools = ToolService(workspace, outbox, "http://localhost:8001")
    settings = Settings(_env_file=None, decision_timeout_seconds=0.5)
    return create_app(settings, scorer=scorer, tools=tools, explainer=judge)


async def call(app: FastAPI, tool: str, **args: str) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://sentinel"
    ) as http:
        return await http.post("/tool", json={"session_id": "s_j", "tool": tool, "args": args})


def history(app: FastAPI) -> list[tuple[StreamEventType, SentinelEvent]]:
    bus: EventBus = app.state.event_bus
    return [(m.type, m.event) for m in bus.history]


@pytest.mark.anyio
async def test_explanation_arrives_while_paused_and_survives_later_updates(
    workspace: Path, outbox: Path, scorer: RuleScorer
) -> None:
    app = build(workspace, outbox, scorer, FakeJudge(delay=0.01))

    response = await call(app, "send_email", **EMAIL)  # nobody decides: fail-safe deny

    types = [t for t, _ in history(app)]
    assert types == [
        StreamEventType.CREATED,
        StreamEventType.EXPLAINED,
        StreamEventType.DECIDED,
        StreamEventType.COMPLETED,
    ]
    final = history(app)[-1][1]
    assert final.explanation is not None and final.explanation.explanation == "Looks fine."
    assert final.decision is not None and final.result is not None
    # A 'benign' verdict changed nothing: still paused, still denied, nothing sent.
    assert response.json()["ok"] is False and final.action.value == "PAUSE"
    assert outbox.read_text() == ""


@pytest.mark.anyio
async def test_late_explanation_is_merged_into_the_finished_event(
    workspace: Path,
    outbox: Path,
    scorer: RuleScorer,
) -> None:
    judge = FakeJudge(delay=0.05)
    app = build(workspace, outbox, scorer, judge)
    pending = asyncio.create_task(call(app, "send_email", **EMAIL))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://sentinel"
    ) as http:
        http.app = app  # type: ignore[attr-defined]
        event_id = await wait_for_pause(http)
        await http.post(f"/decision/{event_id}", json={"approve": False, "reason": "No."})
    await pending
    await asyncio.sleep(0.1)  # the judge answers after the event already completed

    last_type, last = history(app)[-1]
    assert last_type is StreamEventType.EXPLAINED
    assert last.decision is not None and last.decision.reason == "No."
    assert last.result is not None and last.explanation is not None


@pytest.mark.anyio
async def test_only_flag_and_pause_are_explained(
    workspace: Path, outbox: Path, scorer: RuleScorer
) -> None:
    judge = FakeJudge()
    app = build(workspace, outbox, scorer, judge)

    await call(app, "list_dir")
    await call(app, "read_file", path="notes.md")

    assert judge.seen == []
    assert StreamEventType.EXPLAINED not in [t for t, _ in history(app)]


@pytest.mark.anyio
async def test_a_slow_judge_never_delays_the_decision(
    workspace: Path, outbox: Path, scorer: RuleScorer
) -> None:
    app = build(workspace, outbox, scorer, FakeJudge(delay=30))

    response = await asyncio.wait_for(call(app, "send_email", **EMAIL), timeout=3)

    assert "fail-safe deny" in response.json()["content"]
    await app.state.gateway.aclose()  # cancels the still-running explanation cleanly
