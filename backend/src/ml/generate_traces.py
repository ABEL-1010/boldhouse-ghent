"""Generate benign traces for free: `uv run sentinel-traces [--sessions 200] [--seed 7]`.

Each session gets its own throwaway sandbox and runs one benign plan through the real gateway,
real tools and the real fake web (in-process, no servers, no API calls).
"""

import argparse
import asyncio
import random
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import httpx

from fakeweb.main import create_app as create_fakeweb
from ml.simulator import BENIGN_PLANS, WEB, SimSession
from ml.traces import RecordingScorer, TraceRecord, split_for, write_traces
from sentinel.core.config import Settings, get_settings
from sentinel.features.detection import SessionContext
from sentinel.features.events import EventBus
from sentinel.features.gateway import GatewayService, ToolRequest, ToolResponse
from sentinel.features.tools import ToolService, reset_sandbox


async def run_session(
    index: int, task: str, rng: random.Random, settings: Settings, root: Path
) -> list[TraceRecord]:
    session_id = f"s_sim{index:04d}"
    workspace, outbox = root / session_id / "workspace", root / session_id / "outbox.jsonl"
    reset_sandbox(settings.seed_workspace, workspace, outbox)
    web = httpx.ASGITransport(app=create_fakeweb(settings.web_dir))
    tools = ToolService(workspace, outbox, WEB, http_transport=web)
    scorer = RecordingScorer()
    allowed = frozenset(d.lower() for d in settings.sentinel_allowed_domains)
    gateway = GatewayService(
        tools=tools,
        scorer=scorer,
        bus=EventBus(),
        decision_timeout_seconds=1.0,
        new_context=lambda: SessionContext(workspace, allowed),
    )
    records: list[TraceRecord] = []

    async def call(tool: str, **args: Any) -> ToolResponse:
        response = await gateway.handle(ToolRequest(session_id=session_id, tool=tool, args=args))
        step = len(records) + 1
        records.append(
            TraceRecord(
                session_id=session_id,
                task=task,
                split=split_for(session_id),
                step=step,
                tool=tool,
                args=args,
                ok=response.ok,
                features=scorer.features[(session_id, step)],
            )
        )
        return response

    await BENIGN_PLANS[task](SimSession(rng, call))
    return records


async def generate(sessions: int, seed: int, settings: Settings) -> list[TraceRecord]:
    rng = random.Random(seed)
    tasks = list(BENIGN_PLANS)
    records: list[TraceRecord] = []
    with tempfile.TemporaryDirectory(prefix="sentinel-traces-") as tmp:
        for index in range(sessions):
            # Round-robin over plans (offset by the seed) keeps every task equally represented.
            task = tasks[(index + seed) % len(tasks)]
            records += await run_session(
                index, task, random.Random(rng.random()), settings, Path(tmp)
            )
    return records


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="sentinel-traces", description=__doc__)
    parser.add_argument("--sessions", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", type=Path, help="Default: models/traces.jsonl")
    args = parser.parse_args(argv)
    settings = get_settings()
    out = args.out or settings.traces_path

    records = asyncio.run(generate(args.sessions, args.seed, settings))
    write_traces(out, records)
    splits = Counter(r.split for r in records)
    tools = Counter(r.tool for r in records)
    print(f"Wrote {len(records)} calls from {args.sessions} sessions to {out}")
    print(f"  split: {dict(splits)}  failed calls: {sum(not r.ok for r in records)}")
    print(f"  tools: {dict(tools.most_common())}")
