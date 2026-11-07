import asyncio
import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from sentinel.features.events import Action, DecisionSource, StreamEventType

from .conftest import RuleScorer, bus_of, wait_for_pause

EMAIL = {"to": "backup@unknown-domain.xyz", "subject": "config backup", "body": "secrets"}


def tool_call(tool: str, session: str = "s_test", **args: str) -> dict[str, object]:
    return {"session_id": session, "tool": tool, "args": args}


@pytest.mark.anyio
async def test_allowed_call_runs_and_streams_created_then_completed(
    client: httpx.AsyncClient, scorer: RuleScorer
) -> None:
    response = await client.post("/tool", json=tool_call("read_file", path="notes.md"))

    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is True and "Team notes" in body["content"]
    assert body["action"] == "ALLOW" and body["event_id"] == "evt_0001"
    types = [m.type for m in bus_of(client).history]
    assert types == [StreamEventType.CREATED, StreamEventType.COMPLETED]
    completed = bus_of(client).history[-1].event
    assert completed.result is not None and completed.result.ok
    assert completed.result.preview == body["content"][:200]
    assert scorer.calls[0].step == 1 and scorer.calls[0].tool == "read_file"


@pytest.mark.anyio
async def test_steps_count_per_session(client: httpx.AsyncClient) -> None:
    await client.post("/tool", json=tool_call("list_dir", session="s_a"))
    await client.post("/tool", json=tool_call("list_dir", session="s_a"))
    await client.post("/tool", json=tool_call("list_dir", session="s_b"))

    created = [m.event for m in bus_of(client).history if m.type is StreamEventType.CREATED]
    assert [(e.session_id, e.step) for e in created] == [("s_a", 1), ("s_a", 2), ("s_b", 1)]


@pytest.mark.anyio
async def test_tool_failures_are_recorded_not_raised(client: httpx.AsyncClient) -> None:
    response = await client.post("/tool", json=tool_call("read_file", path="../../etc/passwd"))

    assert response.status_code == 200
    assert response.json()["ok"] is False
    result = bus_of(client).history[-1].event.result
    assert result is not None and result.ok is False and "Access denied" in result.preview


@pytest.mark.anyio
async def test_paused_call_runs_only_after_human_approval(
    client: httpx.AsyncClient, outbox: Path
) -> None:
    pending = asyncio.create_task(client.post("/tool", json=tool_call("send_email", **EMAIL)))
    event_id = await wait_for_pause(client)
    assert not outbox.read_text(), "nothing may be sent while the action is paused"

    decision = await client.post(
        f"/decision/{event_id}", json={"approve": True, "reason": "User asked for this backup."}
    )
    response = await pending

    assert decision.status_code == 200
    assert decision.json()["decision"]["source"] == "human"
    assert response.json()["ok"] is True
    assert json.loads(outbox.read_text())["to"] == "backup@unknown-domain.xyz"
    types = [m.type for m in bus_of(client).history]
    assert types == [StreamEventType.CREATED, StreamEventType.DECIDED, StreamEventType.COMPLETED]
    final = bus_of(client).history[-1].event
    assert final.decision is not None and final.decision.approve
    assert final.result is not None and final.result.ok


@pytest.mark.anyio
async def test_denied_call_never_runs(client: httpx.AsyncClient, outbox: Path) -> None:
    pending = asyncio.create_task(client.post("/tool", json=tool_call("send_email", **EMAIL)))
    event_id = await wait_for_pause(client)

    await client.post(f"/decision/{event_id}", json={"approve": False, "reason": "Exfiltration."})
    response = await pending

    assert response.json() == {
        "ok": False,
        "content": "Blocked by Sentinel: Exfiltration.",
        "event_id": event_id,
        "action": "PAUSE",
    }
    assert outbox.read_text() == ""
    final = bus_of(client).history[-1].event
    assert final.result is not None and final.result.ok is False


@pytest.mark.anyio
async def test_deny_without_reason_gets_default_reason(client: httpx.AsyncClient) -> None:
    pending = asyncio.create_task(client.post("/tool", json=tool_call("send_email", **EMAIL)))
    event_id = await wait_for_pause(client)

    decision = await client.post(f"/decision/{event_id}", json={"approve": False})
    await pending

    assert decision.json()["decision"]["reason"] == "Denied by human reviewer"


@pytest.mark.anyio
@pytest.mark.parametrize("reason", ["", "ok", "   fine     "])
async def test_approval_requires_a_real_reason(client: httpx.AsyncClient, reason: str) -> None:
    pending = asyncio.create_task(client.post("/tool", json=tool_call("send_email", **EMAIL)))
    event_id = await wait_for_pause(client)

    rejected = await client.post(f"/decision/{event_id}", json={"approve": True, "reason": reason})

    assert rejected.status_code == 400
    assert "min 10 chars" in rejected.json()["detail"]
    # The action is still pending; a proper decision still goes through.
    await client.post(f"/decision/{event_id}", json={"approve": False, "reason": "No."})
    assert (await pending).json()["ok"] is False


@pytest.mark.anyio
async def test_unknown_or_already_decided_id_is_404(client: httpx.AsyncClient) -> None:
    assert (await client.post("/decision/evt_9999", json={"approve": False})).status_code == 404

    pending = asyncio.create_task(client.post("/tool", json=tool_call("send_email", **EMAIL)))
    event_id = await wait_for_pause(client)
    await client.post(f"/decision/{event_id}", json={"approve": False})
    await pending

    again = await client.post(f"/decision/{event_id}", json={"approve": True, "reason": "x" * 20})
    assert again.status_code == 404


@pytest.mark.anyio
async def test_no_human_response_is_a_fail_safe_deny(
    make_app: Callable[..., FastAPI], outbox: Path
) -> None:
    app = make_app(decision_timeout_seconds=0.05)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://sentinel") as http:
        response = await http.post("/tool", json=tool_call("send_email", **EMAIL))

    assert response.json()["ok"] is False
    assert "fail-safe deny" in response.json()["content"]
    assert outbox.read_text() == ""
    decided = app.state.event_bus.history[1].event
    assert decided.decision.source is DecisionSource.TIMEOUT
    assert decided.decision.approve is False


@pytest.mark.anyio
async def test_rejects_unknown_tools_and_bad_session_ids(client: httpx.AsyncClient) -> None:
    unknown = await client.post("/tool", json=tool_call("rm_rf"))
    bad_session = await client.post("/tool", json=tool_call("list_dir", session="not valid"))

    assert unknown.status_code == bad_session.status_code == 422
    assert bus_of(client).history == ()


@pytest.mark.anyio
async def test_events_are_full_snapshots(client: httpx.AsyncClient) -> None:
    pending = asyncio.create_task(client.post("/tool", json=tool_call("send_email", **EMAIL)))
    event_id = await wait_for_pause(client)
    await client.post(f"/decision/{event_id}", json={"approve": False, "reason": "No."})
    await pending

    created, decided, completed = (m.event for m in bus_of(client).history)
    assert created.action is decided.action is completed.action is Action.PAUSE
    assert created.decision is None and created.result is None
    assert decided.decision is not None and decided.result is None
    assert completed.decision == decided.decision and completed.result is not None
    assert created.args == completed.args == EMAIL


@pytest.mark.anyio
async def test_agent_disconnect_while_paused_is_recorded_as_deny(
    client: httpx.AsyncClient, outbox: Path
) -> None:
    pending = asyncio.create_task(client.post("/tool", json=tool_call("send_email", **EMAIL)))
    await wait_for_pause(client)

    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending

    types = [m.type for m in bus_of(client).history]
    assert types == [StreamEventType.CREATED, StreamEventType.DECIDED, StreamEventType.COMPLETED]
    final = bus_of(client).history[-1].event
    assert final.decision is not None and "disconnected" in final.decision.reason
    assert final.result is not None and final.result.ok is False
    assert outbox.read_text() == ""


@pytest.mark.anyio
async def test_scorer_sees_session_context_before_each_call(
    client: httpx.AsyncClient, scorer: RuleScorer
) -> None:
    await client.post("/tool", json=tool_call("read_file", path=".env"))
    await client.post("/tool", json=tool_call("read_file", path="notes.md"))
    await client.post("/tool", json=tool_call("list_dir", session="s_other"))
    pending = asyncio.create_task(client.post("/tool", json=tool_call("send_email", **EMAIL)))
    event_id = await wait_for_pause(client)
    await client.post(f"/decision/{event_id}", json={"approve": False, "reason": "No."})
    await pending

    # The .env read counts only once it has succeeded; each session has its own context.
    assert scorer.context_seen == [(0, 0), (1, 1), (0, 0), (2, 1)]
    assert [c.step for c in scorer.calls] == [1, 2, 1, 3]
