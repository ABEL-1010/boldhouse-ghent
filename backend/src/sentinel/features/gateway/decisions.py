import asyncio
from datetime import UTC, datetime

from sentinel.features.events import Decision, DecisionSource


class NoPendingDecision(Exception):
    """There is no paused action with this event id (unknown, already decided, or timed out)."""


def _now() -> datetime:
    return datetime.now(UTC)


class PendingDecisions:
    """One future per paused event. The gateway awaits it; POST /decision resolves it."""

    def __init__(self) -> None:
        self._pending: dict[str, asyncio.Future[Decision]] = {}

    def is_pending(self, event_id: str) -> bool:
        return event_id in self._pending

    async def wait(self, event_id: str, timeout_seconds: float) -> Decision:
        future: asyncio.Future[Decision] = asyncio.get_running_loop().create_future()
        self._pending[event_id] = future
        try:
            return await asyncio.wait_for(future, timeout_seconds)
        except TimeoutError:
            # Fail-safe: silence is a deny, never an allow.
            return Decision(
                approve=False,
                reason=f"No human response within {timeout_seconds:g}s: fail-safe deny",
                source=DecisionSource.TIMEOUT,
                ts=_now(),
            )
        finally:
            self._pending.pop(event_id, None)

    def resolve(self, event_id: str, *, approve: bool, reason: str) -> Decision:
        future = self._pending.pop(event_id, None)
        if future is None or future.done():
            raise NoPendingDecision(event_id)
        decision = Decision(approve=approve, reason=reason, source=DecisionSource.HUMAN, ts=_now())
        future.set_result(decision)
        return decision
