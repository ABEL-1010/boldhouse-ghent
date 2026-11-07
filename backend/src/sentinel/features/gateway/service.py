import asyncio
import itertools
from collections.abc import Callable
from datetime import UTC, datetime

from sentinel.features.detection import Scorer, ScoringInput, SessionContext
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
from sentinel.features.judge import Judge
from sentinel.features.tools import ToolService

PREVIEW_CHARS = 200
DEFAULT_DENY_REASON = "Denied by human reviewer"
JUDGED_ACTIONS = frozenset({Action.FLAG, Action.PAUSE})


class ApprovalReasonRequired(Exception):
    """Approving needs a written reason, so humans can't rubber-stamp."""


class GatewayService:
    """Sits between the agent and its tools: score → publish → (pause) → run → publish.

    Each event has one latest snapshot; every update starts from it, so information that arrives
    out of band (the judge's explanation) is never lost by a later decided/completed update.
    """

    def __init__(
        self,
        *,
        tools: ToolService,
        scorer: Scorer,
        bus: EventBus,
        decision_timeout_seconds: float,
        new_context: Callable[[], SessionContext],
        judge: Judge | None = None,
    ) -> None:
        self._tools = tools
        self._scorer = scorer
        self._bus = bus
        self._decision_timeout = decision_timeout_seconds
        self._decisions = PendingDecisions()
        self._event_numbers = itertools.count(1)
        self._new_context = new_context
        self._contexts: dict[str, SessionContext] = {}
        self._judge = judge
        self._latest: dict[str, SentinelEvent] = {}
        self._judge_tasks: set[asyncio.Task[None]] = set()

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
        event_id = event.event_id
        self._latest[event_id] = event
        self._bus.publish(StreamEventType.CREATED, event)
        if self._judge is not None and event.action in JUDGED_ACTIONS:
            self._start_judge(event)

        if event.action is Action.PAUSE:
            decision = await self._await_decision(event_id)
            self._update(event_id, StreamEventType.DECIDED, decision=decision)
            if not decision.approve:
                content = f"Blocked by Sentinel: {decision.reason}"
                self._complete(event_id, ok=False, content=content)
                return ToolResponse(
                    ok=False, content=content, event_id=event_id, action=event.action
                )

        outcome = await self._tools.run(request.tool, request.args)
        self._complete(event_id, ok=outcome.ok, content=outcome.content)
        return ToolResponse(
            ok=outcome.ok, content=outcome.content, event_id=event_id, action=event.action
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

    async def aclose(self) -> None:
        """Cancel explanations still in flight (on shutdown)."""
        for task in self._judge_tasks:
            task.cancel()
        await asyncio.gather(*self._judge_tasks, return_exceptions=True)

    def _start_judge(self, event: SentinelEvent) -> None:
        # Runs alongside the PAUSE wait; the decision never waits for (or depends on) the judge.
        task = asyncio.create_task(self._explain(event))
        self._judge_tasks.add(task)
        task.add_done_callback(self._judge_tasks.discard)

    async def _explain(self, event: SentinelEvent) -> None:
        assert self._judge is not None
        explanation = await self._judge.explain(event)
        if explanation is not None:
            self._update(event.event_id, StreamEventType.EXPLAINED, explanation=explanation)

    async def _await_decision(self, event_id: str) -> Decision:
        try:
            return await self._decisions.wait(event_id, self._decision_timeout)
        except asyncio.CancelledError:
            # The agent hung up while waiting: record a deny so the dashboard isn't left hanging.
            decision = Decision(
                approve=False,
                reason="Agent disconnected before a decision: fail-safe deny",
                source=DecisionSource.TIMEOUT,
                ts=datetime.now(UTC),
            )
            self._update(event_id, StreamEventType.DECIDED, decision=decision)
            self._complete(event_id, ok=False, content=f"Blocked by Sentinel: {decision.reason}")
            raise

    def _complete(self, event_id: str, *, ok: bool, content: str) -> None:
        event = self._latest[event_id]
        self._contexts[event.session_id].observe(event.tool, event.args, ok=ok, content=content)
        result = ToolResult(ok=ok, preview=content[:PREVIEW_CHARS])
        self._update(event_id, StreamEventType.COMPLETED, result=result)

    def _update(self, event_id: str, type_: StreamEventType, **changes: object) -> SentinelEvent:
        updated = self._latest[event_id].model_copy(update=changes)
        self._latest[event_id] = updated
        self._bus.publish(type_, updated)
        return updated
