"""Demo a scripted attack: `uv run sentinel-redteam A1 [--unprotected] [--delay 1.5]`.

The agent is SCRIPTED (not Claude). Its calls go through the real Sentinel gateway, so the
dashboard shows real FLAG / PAUSE events and waits for a real human decision.
"""

import argparse
import asyncio
import sys
from typing import Any

from agent.cli import build_executor, print_call
from agent.executors import GatewayUnavailable, ToolExecutor
from agent.loop import run_agent
from agent.redteam import SCENARIOS, ScriptedModel
from agent.session import new_session_id
from sentinel.core.config import get_settings
from sentinel.features.detection import load_honeytokens
from sentinel.features.tools import ToolOutcome

DECISION_HINT = (
    "Paused actions wait for a human: decide in the dashboard, or with\n"
    "  curl -X POST localhost:8000/decision/<event_id> -H 'content-type: application/json' "
    '-d \'{"approve": false, "reason": "..."}\'\n'
    "  (event ids: curl -N localhost:8000/events)"
)


class PacedExecutor:
    """Waits before each call so an audience can follow along on the dashboard."""

    def __init__(self, inner: ToolExecutor, delay_seconds: float) -> None:
        self._inner = inner
        self._delay = delay_seconds

    async def execute(self, session_id: str, tool: str, args: dict[str, Any]) -> ToolOutcome:
        await asyncio.sleep(self._delay)
        return await self._inner.execute(session_id, tool, args)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="sentinel-redteam", description=__doc__)
    parser.add_argument("scenario", nargs="?", choices=sorted(SCENARIOS), help="Scenario id.")
    parser.add_argument("--list", action="store_true", help="List the scenarios.")
    parser.add_argument("--unprotected", action="store_true", help="Run WITHOUT Sentinel.")
    parser.add_argument("--delay", type=float, default=0.0, help="Seconds before each call.")
    parser.add_argument("--session", help="Session id (default: a new s_<hex> id).")
    args = parser.parse_args(argv)
    if not args.list and not args.scenario:
        parser.error("give a scenario id, or --list")
    return args


def _report_outbox(outbox_text: str) -> None:
    settings = get_settings()
    leaked = sorted(t for t in load_honeytokens(settings.honeytokens_path) if t in outbox_text)
    messages = len(outbox_text.splitlines())
    print(f"\nOutbox now holds {messages} sent message(s); honeytokens leaked: {len(leaked)}")
    for token in leaked:
        print(f"  !! {token}")


async def _run(args: argparse.Namespace) -> int:
    settings = get_settings()
    scenario = SCENARIOS[args.scenario]
    executor = build_executor(settings, args.unprotected)
    if args.delay > 0:
        executor = PacedExecutor(executor, args.delay)
    session_id = args.session or new_session_id()
    outbox_before = (
        settings.outbox_path.read_text(encoding="utf-8") if settings.outbox_path.is_file() else ""
    )
    print("== SCRIPTED RED-TEAM AGENT (not Claude) ==")
    print(f"{scenario.id}: {scenario.title}\nSession {session_id} | Task: {scenario.task}\n")
    if not args.unprotected:
        print(DECISION_HINT + "\n")

    run = await run_agent(
        scenario.task,
        client=ScriptedModel(scenario),  # type: ignore[arg-type]
        model="scripted-redteam",
        executor=executor,
        session_id=session_id,
        on_tool_call=print_call,
    )
    print(f"\nAgent: {run.final_text}")
    if args.unprotected and settings.outbox_path.is_file():
        _report_outbox(settings.outbox_path.read_text(encoding="utf-8")[len(outbox_before) :])
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.list:
        for scenario in SCENARIOS.values():
            print(f"{scenario.id}  {scenario.title}")
        return 0
    try:
        return asyncio.run(_run(args))
    except GatewayUnavailable as exc:
        print(f"{exc}. Start the API, or use --unprotected for the baseline.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
