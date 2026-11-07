import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass

from sentinel.features.events.schemas import SentinelEvent, StreamEventType


@dataclass(frozen=True)
class StreamMessage:
    type: StreamEventType
    event: SentinelEvent


class EventBus:
    """In-memory fan-out of event snapshots, with an ordered history for late subscribers.

    A new subscriber first receives the full history, then live messages, so a dashboard that
    connects mid-session (or reconnects) rebuilds exactly the same state.
    """

    def __init__(self) -> None:
        self._history: list[StreamMessage] = []
        self._subscribers: set[asyncio.Queue[StreamMessage | None]] = set()
        self._closed = False

    @property
    def history(self) -> tuple[StreamMessage, ...]:
        return tuple(self._history)

    def publish(self, type_: StreamEventType, event: SentinelEvent) -> None:
        message = StreamMessage(type_, event)
        self._history.append(message)
        for queue in self._subscribers:
            queue.put_nowait(message)

    async def subscribe(self) -> AsyncIterator[StreamMessage]:
        queue: asyncio.Queue[StreamMessage | None] = asyncio.Queue()
        # No await between snapshot and registration, so no message can be missed or duplicated.
        backlog = list(self._history)
        if not self._closed:
            self._subscribers.add(queue)
        try:
            for message in backlog:
                yield message
            while not self._closed:
                message = await queue.get()
                if message is None:
                    return
                yield message
        finally:
            self._subscribers.discard(queue)

    def close(self) -> None:
        """End all live subscriptions (on shutdown, so open SSE streams don't block it)."""
        self._closed = True
        for queue in self._subscribers:
            queue.put_nowait(None)
