"""Run the agent from the terminal: `uv run sentinel-agent "task" [--unprotected]`."""

import argparse
import asyncio
import sys

import anthropic

from agent.executors import GatewayExecutor, GatewayUnavailable, ToolExecutor, UnprotectedExecutor
from agent.loop import ToolCall, run_agent
from agent.session import new_session_id
from sentinel.core.config import Settings, get_settings
from sentinel.features.tools import ToolService

PREVIEW_CHARS = 160


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="sentinel-agent", description=__doc__)
    parser.add_argument("task", help="What the agent should do.")
    parser.add_argument("--session", help="Session id (default: a new s_<hex> id).")
    parser.add_argument("--max-turns", type=int, help="Override AGENT_MAX_TURNS.")
    parser.add_argument(
        "--unprotected",
        action="store_true",
        help="Run tools directly WITHOUT Sentinel (baseline/demo only).",
    )
    return parser.parse_args(argv)


def print_call(call: ToolCall) -> None:
    status = "ok " if call.ok else "ERR"
    preview = " ".join(call.content.split())[:PREVIEW_CHARS]
    print(f"  [{call.step:>2}] {status} {call.tool}({call.args})\n       -> {preview}")


def build_executor(settings: Settings, unprotected: bool) -> ToolExecutor:
    if not unprotected:
        return GatewayExecutor(settings.sentinel_base_url)
    if not settings.runtime_workspace.is_dir():
        raise SystemExit("No runtime sandbox yet. Run: uv run sentinel-reset")
    print("!! UNPROTECTED MODE: tools run directly, Sentinel is NOT watching.\n")
    return UnprotectedExecutor(ToolService.from_settings(settings))


def _client(settings: Settings) -> anthropic.AsyncAnthropic:
    # pydantic-settings reads .env but does not export it, so pass the key explicitly when set;
    # otherwise the SDK falls back to its own credential resolution.
    if settings.anthropic_api_key:
        return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value())
    return anthropic.AsyncAnthropic()


async def _run(args: argparse.Namespace, settings: Settings) -> int:
    executor = build_executor(settings, args.unprotected)
    session_id = args.session or new_session_id()
    print(f"Session {session_id} | model {settings.agent_model}\nTask: {args.task}\n")
    run = await run_agent(
        args.task,
        client=_client(settings),
        model=settings.agent_model,
        executor=executor,
        session_id=session_id,
        max_turns=args.max_turns or settings.agent_max_turns,
        on_tool_call=print_call,
    )
    calls = len(run.tool_calls)
    print(f"\nStopped: {run.stop_reason} after {run.turns} turn(s), {calls} tool call(s)")
    if run.refusal:
        print(f"Refusal details: {run.refusal}")
    print(f"\n{run.final_text or '(no text reply)'}")
    return 0 if run.stop_reason == "end_turn" else 1


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    settings = get_settings()
    if not settings.agent_model:
        print(
            "AGENT_MODEL is empty. Set it in the repo-root .env (see .env.example).",
            file=sys.stderr,
        )
        return 2
    try:
        return asyncio.run(_run(args, settings))
    except GatewayUnavailable as exc:
        print(f"{exc}. Start the API, or use --unprotected for the baseline.", file=sys.stderr)
    except anthropic.AuthenticationError:
        print("Anthropic API rejected the credentials. Check ANTHROPIC_API_KEY.", file=sys.stderr)
    except TypeError as exc:
        # The SDK raises a bare TypeError when it finds no credentials at all.
        if "authentication" not in str(exc):
            raise
        print("No Anthropic credentials found. Set ANTHROPIC_API_KEY in .env.", file=sys.stderr)
    except anthropic.NotFoundError:
        print(f"Model '{settings.agent_model}' not found. Check AGENT_MODEL.", file=sys.stderr)
    except anthropic.RateLimitError:
        print("Rate limited by the Anthropic API. Wait and retry.", file=sys.stderr)
    except anthropic.APIStatusError as exc:
        print(f"Anthropic API error {exc.status_code}: {exc.message}", file=sys.stderr)
    except anthropic.APIConnectionError:
        print("Could not reach the Anthropic API. Check your network.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
