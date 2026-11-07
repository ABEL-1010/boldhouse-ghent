import json
from pathlib import Path

import httpx
import pytest

from agent import GatewayExecutor, GatewayUnavailable, UnprotectedExecutor
from sentinel.core.config import Settings
from sentinel.features.tools import ToolOutcome, ToolService, reset_sandbox

GATEWAY = "http://127.0.0.1:8000"


@pytest.mark.anyio
async def test_gateway_executor_posts_call_and_parses_outcome() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"ok": True, "content": "file text"})

    executor = GatewayExecutor(GATEWAY, transport=httpx.MockTransport(handler))

    outcome = await executor.execute("s_1", "read_file", {"path": "notes.md"})

    assert outcome == ToolOutcome(ok=True, content="file text")
    assert str(seen[0].url) == f"{GATEWAY}/tool"
    assert json.loads(seen[0].content) == {
        "session_id": "s_1",
        "tool": "read_file",
        "args": {"path": "notes.md"},
    }


@pytest.mark.anyio
@pytest.mark.parametrize("status", [400, 500])
async def test_gateway_http_error_becomes_failed_outcome(status: int) -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(status))

    outcome = await GatewayExecutor(GATEWAY, transport=transport).execute("s_1", "list_dir", {})

    assert outcome == ToolOutcome(ok=False, content=f"Sentinel gateway error: HTTP {status}.")


@pytest.mark.anyio
async def test_unreachable_gateway_fails_closed() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    executor = GatewayExecutor(GATEWAY, transport=httpx.MockTransport(refuse))

    with pytest.raises(GatewayUnavailable, match="unreachable"):
        await executor.execute("s_1", "list_dir", {})


@pytest.mark.anyio
async def test_unprotected_executor_runs_tools_directly(tmp_path: Path) -> None:
    workspace, outbox = tmp_path / "workspace", tmp_path / "outbox.jsonl"
    reset_sandbox(Settings(_env_file=None).seed_workspace, workspace, outbox)
    executor = UnprotectedExecutor(ToolService(workspace, outbox, "http://localhost:8001"))

    outcome = await executor.execute("s_1", "read_file", {"path": ".env"})

    assert outcome.ok
    assert "sk-atlas-live-" in outcome.content
