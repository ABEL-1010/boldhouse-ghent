import asyncio
from collections import Counter
from pathlib import Path

import pytest

from ml.generate_traces import generate, main
from ml.simulator import BENIGN_PLANS
from ml.traces import TraceRecord, read_traces, split_for, write_traces
from sentinel.core.config import Settings
from sentinel.features.detection import FEATURE_NAMES

SETTINGS = Settings(_env_file=None)


@pytest.fixture(scope="module")
def records() -> list[TraceRecord]:
    return asyncio.run(generate(sessions=45, seed=3, settings=SETTINGS))


def test_every_benign_plan_runs_and_produces_calls(records: list[TraceRecord]) -> None:
    tasks = Counter(r.task for r in records if r.step == 1)

    assert set(tasks) == set(BENIGN_PLANS)
    assert all(count == 3 for count in tasks.values())  # round-robin: 45 sessions / 15 plans


def test_records_carry_production_feature_vectors(records: list[TraceRecord]) -> None:
    assert all(tuple(r.features) == FEATURE_NAMES for r in records)
    by_session: dict[str, list[int]] = {}
    for r in records:
        by_session.setdefault(r.session_id, []).append(r.step)
    assert all(steps == list(range(1, len(steps) + 1)) for steps in by_session.values())


def test_benign_traces_contain_no_attack_behaviour(records: list[TraceRecord]) -> None:
    for name in ("sensitive_target", "unknown_destination", "secret_pattern"):
        assert all(r.features[name] == 0.0 for r in records), name
    destructive = [r for r in records if r.features["destructive"]]
    assert destructive and all(r.args["path"].startswith("tmp/") for r in destructive)


def test_tools_really_ran(records: list[TraceRecord]) -> None:
    fetched = [r for r in records if r.tool == "fetch_url"]

    assert fetched and all(r.ok for r in fetched)  # the in-process fake web served the pages
    assert sum(not r.ok for r in records) < len(records) * 0.1  # only occasional stumbles


def test_about_twenty_percent_of_sessions_are_held_out() -> None:
    splits = Counter(split_for(f"s_sim{index:04d}") for index in range(1000))

    assert 0.17 < splits["holdout"] / 1000 < 0.23


def test_holdout_covers_every_task() -> None:
    # Regression: an index-based split held out only 3 of the 15 round-robin task types.
    records = asyncio.run(generate(sessions=200, seed=7, settings=SETTINGS))

    holdout_tasks = {r.task for r in records if r.split == "holdout"}
    assert holdout_tasks == set(BENIGN_PLANS)


def test_generation_is_deterministic() -> None:
    first = asyncio.run(generate(sessions=10, seed=11, settings=SETTINGS))
    second = asyncio.run(generate(sessions=10, seed=11, settings=SETTINGS))

    assert first == second


def test_traces_round_trip_through_jsonl(records: list[TraceRecord], tmp_path: Path) -> None:
    path = tmp_path / "traces.jsonl"

    assert write_traces(path, records) == len(records)
    assert read_traces(path) == records


def test_cli_writes_traces(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "traces.jsonl"

    main(["--sessions", "5", "--out", str(out)])

    assert len(read_traces(out)) > 5
    assert "from 5 sessions" in capsys.readouterr().out
