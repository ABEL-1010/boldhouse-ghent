import asyncio
import logging
from typing import Any, Protocol

import anthropic

from sentinel.core.config import Settings
from sentinel.features.events import Explanation, SentinelEvent
from sentinel.features.judge.prompt import SYSTEM_PROMPT, build_user_message

logger = logging.getLogger("sentinel.judge")

TIMEOUT_SECONDS = 15.0
# Room for adaptive thinking plus a short JSON answer.
MAX_TOKENS = 4_000


class Judge(Protocol):
    async def explain(self, event: SentinelEvent) -> Explanation | None: ...


class ClaudeJudge:
    """Plain-language explanation of a flagged action. Advisory only: never decides anything."""

    def __init__(self, client: Any, model: str, timeout_seconds: float = TIMEOUT_SECONDS) -> None:
        # `client` is an AsyncAnthropic (typed loosely so tests can pass a fake).
        self._client = client
        self._model = model
        self._timeout = timeout_seconds

    async def explain(self, event: SentinelEvent) -> Explanation | None:
        try:
            response = await asyncio.wait_for(
                self._client.messages.parse(
                    model=self._model,
                    max_tokens=MAX_TOKENS,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": build_user_message(event)}],
                    output_format=Explanation,
                ),
                self._timeout,
            )
        # Advisory boundary: whatever goes wrong (timeout, API error, bad output), the gateway
        # carries on unchanged and the dashboard simply shows no assessment.
        except Exception as exc:  # noqa: BLE001
            logger.warning("Judge failed for %s: %s", event.event_id, type(exc).__name__)
            return None
        explanation = getattr(response, "parsed_output", None)
        if response.stop_reason == "refusal" or not isinstance(explanation, Explanation):
            logger.warning(
                "Judge gave no usable answer for %s (%s)", event.event_id, response.stop_reason
            )
            return None
        return explanation


def build_judge(settings: Settings) -> Judge | None:
    if not settings.judge_model:
        logger.warning("JUDGE_MODEL is empty: flagged actions get no Claude explanation.")
        return None
    key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else None
    client = anthropic.AsyncAnthropic(api_key=key) if key else anthropic.AsyncAnthropic()
    logger.info("Claude explanations enabled (%s, advisory only).", settings.judge_model)
    return ClaudeJudge(client, settings.judge_model)
