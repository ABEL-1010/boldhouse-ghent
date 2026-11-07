from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from anthropic import AsyncAnthropic
from anthropic.types import Message, MessageParam, ToolResultBlockParam

from agent.executors import ToolExecutor
from agent.tool_definitions import build_tool_definitions

DEFAULT_SYSTEM = (
    "You are a helpful assistant that completes tasks in a workspace using the tools provided. "
    "File paths are relative to the workspace root. When the task is done, reply with a short "
    "summary of what you did."
)
MAX_TOKENS = 16_000


@dataclass(frozen=True)
class ToolCall:
    step: int
    tool: str
    args: dict[str, Any]
    ok: bool
    content: str


@dataclass(frozen=True)
class AgentRun:
    session_id: str
    stop_reason: str
    final_text: str
    turns: int
    tool_calls: list[ToolCall] = field(default_factory=list)


def _text_of(message: Message) -> str:
    return "\n".join(block.text for block in message.content if block.type == "text").strip()


async def run_agent(
    task: str,
    *,
    client: AsyncAnthropic,
    model: str,
    executor: ToolExecutor,
    session_id: str,
    system: str = DEFAULT_SYSTEM,
    max_turns: int = 15,
    on_tool_call: Callable[[ToolCall], None] | None = None,
) -> AgentRun:
    """Claude tool-use loop. Every tool call is executed by `executor`, never by the agent itself.

    Stops on any non-tool stop reason (end_turn, max_tokens, refusal, ...) without running a
    possibly truncated tool call, or after `max_turns` model calls.
    """
    tools = build_tool_definitions()
    messages: list[MessageParam] = [{"role": "user", "content": task}]
    calls: list[ToolCall] = []
    last_text = ""

    for turn in range(1, max_turns + 1):
        response = await client.messages.create(
            model=model, max_tokens=MAX_TOKENS, system=system, tools=tools, messages=messages
        )
        # Append the full content (not just text) so thinking blocks are passed back unchanged.
        messages.append({"role": "assistant", "content": response.content})
        last_text = _text_of(response) or last_text

        if response.stop_reason == "pause_turn":
            continue
        tool_uses = [block for block in response.content if block.type == "tool_use"]
        if response.stop_reason != "tool_use" or not tool_uses:
            return AgentRun(session_id, str(response.stop_reason), last_text, turn, calls)

        # Sequential on purpose: steps stay ordered for the sequence model, and a PAUSE on one
        # call holds back the rest of the turn.
        results: list[ToolResultBlockParam] = []
        for block in tool_uses:
            args = dict(block.input) if isinstance(block.input, dict) else {}
            outcome = await executor.execute(session_id, block.name, args)
            call = ToolCall(len(calls) + 1, block.name, args, outcome.ok, outcome.content)
            calls.append(call)
            if on_tool_call:
                on_tool_call(call)
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": outcome.content,
                    "is_error": not outcome.ok,
                }
            )
        # All results go back in a single user message.
        messages.append({"role": "user", "content": results})

    return AgentRun(session_id, "max_turns", last_text, max_turns, calls)
