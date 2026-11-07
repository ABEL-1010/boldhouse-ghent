import asyncio
import itertools
from collections.abc import Callable
from datetime import UTC, datetime

from sentinel.features.detection import SessionContext
from sentinel.features.events import (
    Action,
    Decision,
    DecisionSource,
    EventBus,
    SentinelEvent,
    StreamEventType,
    ToolResult,
)
from sentinel.features.gateway.decisions import NoPendingDecision, PendingDecisions
from sentinel.features.gateway.schemas import (
    MIN_APPROVAL_REASON_CHARS,
    DecisionRequest,
    ToolRequest,
    ToolResponse,
)
from sentinel.features.gateway.scoring import Scorer, ScoringInput
from sentinel.features.tools import ToolService

PREVIEW_CHARS = 200
DEFAULT_DENY_REASON = "Denied by human reviewer"


class ApprovalReasonRequired(Exception):
    """Approving needs a written reason, so humans can't rubber-stamp."""


class GatewayService:
    """Sits between the agent and its tools: score → publish → (pause) → run → publish."""

    def __init__(
        self,
        *,
        tools: ToolService,
        scorer: Scorer,
        bus: EventBus,
        decision_timeout_seconds: float,
        new_context: Callable[[], SessionContext],
    ) -> None:
        self._tools = tools
        self._scorer = scorer
        self._bus = bus
        self._decision_timeout = decision_timeout_seconds
        self._decisions = PendingDecisions()
        self._event_numbers = itertools.count(1)
        self._new_context = new_context
        self._contexts: dict[str, SessionContext] = {}

    async def handle(self, request: ToolRequest) -> ToolResponse:
        context = self._contexts.setdefault(request.session_id, self._new_context())
        step = context.steps_so_far + 1
        score = self._scorer.score(
            ScoringInput(request.session_id, step, request.tool, dict(request.args), context)
        )
        event = SentinelEvent(
            event_id=f"evt_{next(self._event_numbers):04d}",
            session_id=request.session_id,
            step=step,
            ts=datetime.now(UTC),
            tool=request.tool,
            args=request.args,
            signals=score.signals,
            risk=score.risk,
            action=score.action,
        )
        self._bus.publish(StreamEventType.CREATED, event)

        if event.action is Action.PAUSE:
            decision = await self._await_decision(event)
            event = self._update(event, StreamEventType.DECIDED, decision=decision)
            if not decision.approve:
                content = f"Blocked by Sentinel: {decision.reason}"
                self._complete(event, ok=False, content=content)
                return ToolResponse(
                    ok=False, content=content, event_id=event.event_id, action=event.action
                )

        outcome = await self._tools.run(request.tool, request.args)
        self._complete(event, ok=outcome.ok, content=outcome.content)
        return ToolResponse(
            ok=outcome.ok, content=outcome.content, event_id=event.event_id, action=event.action
        )

    def decide(self, event_id: str, request: DecisionRequest) -> Decision:
        """Resolve a paused action. Raises NoPendingDecision or ApprovalReasonRequired."""
        if not self._decisions.is_pending(event_id):
            # Checked first so an unknown id isn't reported as a missing reason.
            raise NoPendingDecision(event_id)
        reason = request.reason.strip()
        if request.approve and len(reason) < MIN_APPROVAL_REASON_CHARS:
            raise ApprovalReasonRequired(
                f"Explain why you approve this action (min {MIN_APPROVAL_REASON_CHARS} chars)."
            )
        return self._decisions.resolve(
            event_id, approve=request.approve, reason=reason or DEFAULT_DENY_REASON
        )

    async def _await_decision(self, event: SentinelEvent) -> Decision:
        try:
            return await self._decisions.wait(event.event_id, self._decision_timeout)
        except asyncio.CancelledError:
            # The agent hung up while waiting: record a deny so the dashboard isn't left hanging.
            decision = Decision(
                approve=False,
                reason="Agent disconnected before a decision: fail-safe deny",
                source=DecisionSource.TIMEOUT,
                ts=datetime.now(UTC),
            )
            decided = self._update(event, StreamEventType.DECIDED, decision=decision)
            self._complete(decided, ok=False, content=f"Blocked by Sentinel: {decision.reason}")
            raise

    def _complete(self, event: SentinelEvent, *, ok: bool, content: str) -> None:
        self._contexts[event.session_id].observe(event.tool, event.args, ok=ok)
        result = ToolResult(ok=ok, preview=content[:PREVIEW_CHARS])
        self._update(event, StreamEventType.COMPLETED, result=result)

    def _update(
        self, event: SentinelEvent, type_: StreamEventType, **changes: object
    ) -> SentinelEvent:
        updated = event.model_copy(update=changes)
        self._bus.publish(type_, updated)
        return updated
