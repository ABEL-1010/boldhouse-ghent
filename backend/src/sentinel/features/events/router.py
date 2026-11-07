from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from sse_starlette import EventSourceResponse, ServerSentEvent

from sentinel.features.events.bus import EventBus

router = APIRouter(tags=["events"])

PING_SECONDS = 15


def get_event_bus(request: Request) -> EventBus:
    bus: EventBus = request.app.state.event_bus
    return bus


@router.get("/events")
async def stream_events(request: Request) -> EventSourceResponse:
    """SSE stream: history first, then live. Each message is a full SentinelEvent snapshot."""
    bus = get_event_bus(request)

    async def messages() -> AsyncIterator[ServerSentEvent]:
        async for message in bus.subscribe():
            yield ServerSentEvent(
                data=message.event.model_dump_json(),
                event=message.type.value,
                id=message.event.event_id,
            )

    return EventSourceResponse(messages(), ping=PING_SECONDS)
