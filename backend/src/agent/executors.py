from typing import Any, Protocol

import httpx

from sentinel.features.tools import ToolOutcome, ToolService

# Longer than the gateway's 90 s human-decision window, so a PAUSE never times out client-side.
GATEWAY_TIMEOUT_SECONDS = 120.0


class GatewayUnavailable(Exception):
    """Sentinel could not be reached. The run stops instead of silently running unprotected."""


class ToolExecutor(Protocol):
    async def execute(self, session_id: str, tool: str, args: dict[str, Any]) -> ToolOutcome: ...


class GatewayExecutor:
    """Default: every tool call goes through Sentinel's POST /tool."""

    def __init__(self, base_url: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._base_url = base_url
        self._transport = transport

    async def execute(self, session_id: str, tool: str, args: dict[str, Any]) -> ToolOutcome:
        payload = {"session_id": session_id, "tool": tool, "args": args}
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url, transport=self._transport, timeout=GATEWAY_TIMEOUT_SECONDS
            ) as client:
                response = await client.post("/tool", json=payload)
        except httpx.TransportError as exc:
            raise GatewayUnavailable(
                f"Sentinel gateway unreachable at {self._base_url} ({type(exc).__name__})"
            ) from exc
        if response.is_error:
            return ToolOutcome(
                ok=False, content=f"Sentinel gateway error: HTTP {response.status_code}."
            )
        return ToolOutcome.model_validate(response.json())


class UnprotectedExecutor:
    """Runs tools directly, with no Sentinel in between. Baseline and demo use only."""

    def __init__(self, service: ToolService) -> None:
        self._service = service

    async def execute(self, session_id: str, tool: str, args: dict[str, Any]) -> ToolOutcome:
        return await self._service.run(tool, args)
