from typing import Any

import pytest
from anthropic.types import Message

from agent import AgentRun, ToolCall, run_agent
from sentinel.features.tools import ToolOutcome


def message(stop_reason: str, *blocks: dict[str, Any]) -> Message:
    return Message.model_validate(
        {
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "model": "test-model",
            "content": list(blocks),
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }
    )


def text(value: str) -> dict[str, Any]:
    return {"type": "text", "text": value}


def tool_use(block_id: str, name: str, **args: Any) -> dict[str, Any]:
    return {"type": "tool_use", "id": block_id, "name": name, "input": args}


class FakeMessages:
    def __init__(self, responses: list[Message]) -> None:
        self._responses = responses
        self.requests: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Message:
        # Snapshot messages: the loop keeps appending to the same list.
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        return self._responses[len(self.requests) - 1]


class FakeClient:
    def __init__(self, *responses: Message) -> None:
        self.messages = FakeMessages(list(responses))


class FakeExecutor:
    def __init__(self, outcomes: dict[str, ToolOutcome] | None = None) -> None:
        self.outcomes = outcomes or {}
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    async def execute(self, session_id: str, tool: str, args: dict[str, Any]) -> ToolOutcome:
        self.calls.append((session_id, tool, args))
        return self.outcomes.get(tool, ToolOutcome(ok=True, content=f"{tool} done"))


async def run(client: FakeClient, executor: FakeExecutor, **kwargs: Any) -> AgentRun:
    return await run_agent(
        "Summarize notes.md",
        client=client,  # type: ignore[arg-type]
        model="test-model",
        executor=executor,
        session_id="s_test",
        **kwargs,
    )


@pytest.mark.anyio
async def test_runs_tools_until_end_turn() -> None:
    client = FakeClient(
        message("tool_use", text("Reading."), tool_use("tu_1", "read_file", path="notes.md")),
        message("end_turn", text("Summary written.")),
    )
    executor = FakeExecutor()
    seen: list[ToolCall] = []

    result = await run(client, executor, on_tool_call=seen.append)

    assert result.stop_reason == "end_turn"
    assert result.final_text == "Summary written."
    assert result.turns == 2
    assert executor.calls == [("s_test", "read_file", {"path": "notes.md"})]
    assert (
        seen
        == result.tool_calls
        == [ToolCall(1, "read_file", {"path": "notes.md"}, True, "read_file done")]
    )
    second = client.messages.requests[1]["messages"]
    assert [m["role"] for m in second] == ["user", "assistant", "user"]
    assert second[2]["content"] == [
        {
            "type": "tool_result",
            "tool_use_id": "tu_1",
            "content": "read_file done",
            "is_error": False,
        }
    ]


@pytest.mark.anyio
async def test_sends_model_system_tools_and_task() -> None:
    client = FakeClient(message("end_turn", text("hi")))

    await run(client, FakeExecutor(), system="custom system")

    request = client.messages.requests[0]
    assert request["model"] == "test-model"
    assert request["system"] == "custom system"
    assert request["max_tokens"] == 16_000
    assert len(request["tools"]) == 7
    assert request["messages"] == [{"role": "user", "content": "Summarize notes.md"}]


@pytest.mark.anyio
async def test_failed_tool_is_returned_as_error_result() -> None:
    client = FakeClient(
        message("tool_use", tool_use("tu_1", "read_file", path="../../etc/passwd")),
        message("end_turn", text("Could not read it.")),
    )
    blocked = ToolOutcome(ok=False, content="Access denied: outside the workspace.")

    result = await run(client, FakeExecutor({"read_file": blocked}))

    [tool_result] = client.messages.requests[1]["messages"][2]["content"]
    assert tool_result["is_error"] is True
    assert tool_result["content"] == "Access denied: outside the workspace."
    assert result.tool_calls[0].ok is False


@pytest.mark.anyio
async def test_all_tool_calls_of_a_turn_go_back_in_one_message_in_order() -> None:
    client = FakeClient(
        message(
            "tool_use",
            tool_use("tu_1", "list_dir"),
            tool_use("tu_2", "read_file", path="notes.md"),
            tool_use("tu_3", "fetch_url", url="http://localhost:8001/news1.html"),
        ),
        message("end_turn", text("done")),
    )
    executor = FakeExecutor()

    result = await run(client, executor)

    assert [call[1] for call in executor.calls] == ["list_dir", "read_file", "fetch_url"]
    assert [c.step for c in result.tool_calls] == [1, 2, 3]
    results = client.messages.requests[1]["messages"][2]["content"]
    assert [r["tool_use_id"] for r in results] == ["tu_1", "tu_2", "tu_3"]


@pytest.mark.anyio
@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
async def test_never_runs_tools_when_stopped_for_another_reason(stop_reason: str) -> None:
    # A max_tokens stop can carry a truncated tool_use block; it must not be executed.
    client = FakeClient(message(stop_reason, tool_use("tu_1", "send_email", to="x@y.z")))
    executor = FakeExecutor()

    result = await run(client, executor)

    assert result.stop_reason == stop_reason
    assert executor.calls == []


@pytest.mark.anyio
async def test_stops_after_max_turns() -> None:
    looping = message("tool_use", tool_use("tu_1", "list_dir"))
    client = FakeClient(looping, looping, looping)
    executor = FakeExecutor()

    result = await run(client, executor, max_turns=3)

    assert result.stop_reason == "max_turns"
    assert result.turns == 3
    assert len(client.messages.requests) == 3
    assert len(executor.calls) == 3


@pytest.mark.anyio
async def test_pause_turn_is_resumed() -> None:
    client = FakeClient(message("pause_turn", text("working")), message("end_turn", text("done")))

    result = await run(client, FakeExecutor())

    assert result.stop_reason == "end_turn"
    assert len(client.messages.requests) == 2
