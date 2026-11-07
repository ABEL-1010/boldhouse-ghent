import asyncio
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from sentinel.core.config import Settings
from sentinel.features.events import Action, EventBus, Signals, StreamEventType
from sentinel.features.gateway import Score, ScoringInput
from sentinel.features.tools import ToolService, reset_sandbox
from sentinel.main import create_app

SETTINGS = Settings(_env_file=None)


class RuleScorer:
    """Test scorer: PAUSE for the tools in `pause`, ALLOW otherwise."""

    def __init__(self, pause: set[str] | None = None) -> None:
        self.pause = pause or set()
        self.calls: list[ScoringInput] = []
        # (steps_so_far, sensitive_reads) at scoring time; the context object itself mutates.
        self.context_seen: list[tuple[int, int]] = []

    def score(self, call: ScoringInput) -> Score:
        self.calls.append(call)
        self.context_seen.append((call.context.steps_so_far, call.context.sensitive_reads))
        if call.tool in self.pause:
            return Score(Signals(taint=True, ml_risk=0.97), risk=1.0, action=Action.PAUSE)
        return Score(Signals(), risk=0.0, action=Action.ALLOW)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    runtime = tmp_path / "workspace"
    reset_sandbox(SETTINGS.seed_workspace, runtime, tmp_path / "outbox.jsonl")
    return runtime


@pytest.fixture
def outbox(tmp_path: Path) -> Path:
    return tmp_path / "outbox.jsonl"


@pytest.fixture
def scorer() -> RuleScorer:
    return RuleScorer(pause={"send_email"})


@pytest.fixture
def make_app(workspace: Path, outbox: Path, scorer: RuleScorer) -> Callable[..., FastAPI]:
    def build(decision_timeout_seconds: float = 5.0) -> FastAPI:
        settings = Settings(_env_file=None, decision_timeout_seconds=decision_timeout_seconds)
        tools = ToolService(workspace, outbox, "http://localhost:8001")
        return create_app(settings, scorer=scorer, tools=tools)

    return build


@pytest.fixture
async def client(make_app: Callable[..., FastAPI]) -> AsyncIterator[httpx.AsyncClient]:
    app = make_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://sentinel") as http:
        http.app = app  # type: ignore[attr-defined]
        yield http


def bus_of(http: httpx.AsyncClient) -> EventBus:
    bus: EventBus = http.app.state.event_bus  # type: ignore[attr-defined]
    return bus


async def wait_for_pause(http: httpx.AsyncClient, timeout: float = 2.0) -> str:
    """Wait until the gateway has published a PAUSE event and return its id."""
    async with asyncio.timeout(timeout):
        while True:
            for message in bus_of(http).history:
                if message.type is StreamEventType.CREATED and message.event.action is Action.PAUSE:
                    return message.event.event_id
            await asyncio.sleep(0.005)
