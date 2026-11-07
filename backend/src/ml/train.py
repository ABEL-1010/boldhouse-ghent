"""Train the ML layers: `uv run sentinel-train` -> models/sentinel.joblib (Roadmap §5 Step 7b-d).

Unsupervised: only benign traces are used. The model learns "normal", so it can flag attacks it
has never seen. Held-out benign sessions calibrate risk; fresh benign sessions (a different seed)
give an honest false-positive estimate.
"""

import argparse
import asyncio
from collections import defaultdict
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from sklearn.ensemble import IsolationForest

from ml.generate_traces import generate
from ml.traces import TraceRecord, read_traces
from sentinel.core.config import Settings, get_settings
from sentinel.features.detection import (
    FEATURE_NAMES,
    START_TOKEN,
    DetectionModel,
    MarkovModel,
    combine,
    token_from_features,
)
from sentinel.features.events import Action, ToolName

FOREST_TREES = 300
RANDOM_STATE = 42
FRESH_SEED_OFFSET = 1000


def feature_matrix(records: list[TraceRecord]) -> NDArray[np.float64]:
    return np.array([[r.features[name] for name in FEATURE_NAMES] for r in records])


def by_session(records: list[TraceRecord]) -> list[list[TraceRecord]]:
    sessions: dict[str, list[TraceRecord]] = defaultdict(list)
    for record in records:
        sessions[record.session_id].append(record)
    return [sorted(calls, key=lambda r: r.step) for calls in sessions.values()]


def token_sequences(records: list[TraceRecord]) -> list[list[str]]:
    return [
        [token_from_features(ToolName(r.tool), r.features) for r in calls]
        for calls in by_session(records)
    ]


def transitions(sequences: list[list[str]]) -> list[tuple[str, str]]:
    return [
        pair
        for sequence in sequences
        for pair in zip([START_TOKEN, *sequence], sequence, strict=False)
    ]


def train(records: list[TraceRecord]) -> DetectionModel:
    train_set = [r for r in records if r.split == "train"]
    holdout = [r for r in records if r.split == "holdout"]
    if not train_set or not holdout:
        raise ValueError("Need both train and holdout sessions; generate more traces.")

    forest = IsolationForest(
        n_estimators=FOREST_TREES, contamination="auto", random_state=RANDOM_STATE
    ).fit(feature_matrix(train_set))
    forest_reference = np.sort(-forest.score_samples(feature_matrix(holdout)))

    markov = MarkovModel.fit(token_sequences(train_set))
    markov_reference = np.sort(
        [markov.surprise(prev, tok) for prev, tok in transitions(token_sequences(holdout))]
    )
    sessions = len({r.session_id for r in records})
    return DetectionModel(
        forest=forest,
        forest_reference=forest_reference,
        markov=markov,
        markov_reference=markov_reference,
        feature_names=FEATURE_NAMES,
        info={
            "summary": f"{len(train_set)} train / {len(holdout)} holdout calls, "
            f"{sessions} sessions",
            "train_calls": len(train_set),
            "holdout_calls": len(holdout),
        },
    )


@dataclass(frozen=True)
class AlertBudget:
    calls: int
    flags: int
    pauses: int

    def line(self, label: str) -> str:
        per_100 = 100 * self.pauses / self.calls
        return (
            f"  {label:<22} {self.calls:>4} calls  FLAG {self.flags:>3}  "
            f"PAUSE {self.pauses:>3}  ({per_100:.1f} PAUSEs per 100 normal calls)"
        )


def alert_budget(model: DetectionModel, records: list[TraceRecord]) -> AlertBudget:
    """ML-only actions on benign calls (benign traces hit no rules, so this is the ML's share)."""
    actions = []
    for sequence_records in by_session(records):
        previous = START_TOKEN
        for r in sequence_records:
            token = token_from_features(ToolName(r.tool), r.features)
            ml, markov = model.ml_risk(r.features), model.markov_risk(previous, token)
            actions.append(combine([], False, round(ml, 2), round(markov, 2))[1])
            previous = token
    return AlertBudget(
        calls=len(actions),
        flags=actions.count(Action.FLAG),
        pauses=actions.count(Action.PAUSE),
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="sentinel-train", description=__doc__)
    parser.add_argument("--fresh-sessions", type=int, default=100)
    args = parser.parse_args(argv)
    settings: Settings = get_settings()
    if not settings.traces_path.is_file():
        raise SystemExit(f"No traces at {settings.traces_path}. Run: uv run sentinel-traces")

    records = read_traces(settings.traces_path)
    model = train(records)
    model.save(settings.model_path)
    print(f"Saved {settings.model_path} ({model.info['summary']})")

    fresh = asyncio.run(generate(args.fresh_sessions, seed=FRESH_SEED_OFFSET, settings=settings))
    print("Alert budget on benign calls (ML layers only):")
    print(
        alert_budget(model, [r for r in records if r.split == "holdout"]).line(
            "holdout (calibration)"
        )
    )
    print(alert_budget(model, fresh).line("fresh benign sessions"))
