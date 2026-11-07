import asyncio
import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from sentinel.core.config import Settings
from sentinel.features.events import (
    Action,
    EventBus,
    SentinelEvent,
    Signals,
    StreamEventType,
    StreamMessage,
)
from sentinel.main import create_app


def event(number: int) -> SentinelEvent:
    return SentinelEvent(
        event_id=f"evt_{number:04d}",
        session_id="s_1",
        step=number,
        ts=datetime(2026, 11, 21, 14, 0, number, tzinfo=UTC),
        tool="list_dir",
        args={},
        signals=Signals(),
        risk=0.0,
        action=Action.ALLOW,
    )


async def collect(bus: EventBus, into: list[StreamMessage]) -> None:
    async for message in bus.subscribe():
        into.append(message)


@pytest.mark.anyio
async def test_late_subscriber_gets_history_then_live_messages() -> None:
    bus = EventBus()
    bus.publish(StreamEventType.CREATED, event(1))
    received: list[StreamMessage] = []
    task = asyncio.create_task(collect(bus, received))
    await asyncio.sleep(0)

    bus.publish(StreamEventType.COMPLETED, event(1))
    bus.publish(StreamEventType.CREATED, event(2))
    await asyncio.sleep(0)
    bus.close()
    await asyncio.wait_for(task, 1)

    assert [(m.type, m.event.event_id) for m in received] == [
        (StreamEventType.CREATED, "evt_0001"),
        (StreamEventType.COMPLETED, "evt_0001"),
        (StreamEventType.CREATED, "evt_0002"),
    ]


@pytest.mark.anyio
async def test_every_subscriber_receives_every_message() -> None:
    bus = EventBus()
    first: list[StreamMessage] = []
    second: list[StreamMessage] = []
    tasks = [asyncio.create_task(collect(bus, first)), asyncio.create_task(collect(bus, second))]
    await asyncio.sleep(0)

    bus.publish(StreamEventType.CREATED, event(1))
    await asyncio.sleep(0)
    bus.close()
    await asyncio.wait_for(asyncio.gather(*tasks), 1)

    assert len(first) == len(second) == 1


@pytest.mark.anyio
async def test_subscribing_after_close_returns_history_and_ends() -> None:
    bus = EventBus()
    bus.publish(StreamEventType.CREATED, event(1))
    bus.close()
    received: list[StreamMessage] = []

    await asyncio.wait_for(collect(bus, received), 1)

    assert len(received) == 1


def test_sse_endpoint_streams_snapshots_with_event_names() -> None:
    app = create_app(Settings(_env_file=None))
    bus: EventBus = app.state.event_bus
    bus.publish(StreamEventType.CREATED, event(1))
    bus.publish(StreamEventType.COMPLETED, event(1))
    bus.close()  # ends the stream after the history, so the test can read it to the end

    with TestClient(app).stream("GET", "/events") as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        body = response.read().decode()

    frames = [frame for frame in body.replace("\r\n", "\n").split("\n\n") if "data:" in frame]
    parsed = [dict(line.split(": ", 1) for line in frame.splitlines()) for frame in frames]
    assert [frame["event"] for frame in parsed] == ["created", "completed"]
    assert [frame["id"] for frame in parsed] == ["evt_0001", "evt_0001"]
    assert SentinelEvent.model_validate(json.loads(parsed[0]["data"])) == event(1)
