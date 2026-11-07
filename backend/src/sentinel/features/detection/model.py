"""The trained ML layers, as one artifact: Isolation Forest + Markov model + calibration data."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from numpy.typing import NDArray
from sklearn.ensemble import IsolationForest

from sentinel.features.detection.anomaly import calibrated_risk
from sentinel.features.detection.features import FEATURE_NAMES
from sentinel.features.detection.markov import MarkovModel


class StaleModel(Exception):
    """The model file was trained on a different feature set. Retrain it."""


def indicator_support(
    rows: list[dict[str, float]], names: tuple[str, ...]
) -> dict[str, frozenset[float]]:
    """Values seen in training for each 0/1 indicator feature.

    Continuous features (lengths, entropy, step) are left to the forest: real sessions routinely
    exceed the simulator's ranges there, which is not suspicious in itself.
    """
    support = {name: frozenset(row[name] for row in rows) for name in names}
    return {name: seen for name, seen in support.items() if seen <= {0.0, 1.0}}


@dataclass(frozen=True)
class DetectionModel:
    forest: IsolationForest
    forest_reference: NDArray[np.float64]  # sorted held-out anomaly scores (higher = stranger)
    markov: MarkovModel
    markov_reference: NDArray[np.float64]  # sorted held-out surprise values
    feature_names: tuple[str, ...]
    # Indicator feature -> values seen in normal training data (see indicator_support).
    seen_indicators: dict[str, frozenset[float]] = field(default_factory=dict)
    info: dict[str, Any] = field(default_factory=dict)

    def anomaly_score(self, features: dict[str, float]) -> float:
        row = np.array([[features[name] for name in self.feature_names]])
        return float(-self.forest.score_samples(row)[0])

    def out_of_support(self, features: dict[str, float]) -> list[str]:
        """Indicator signals with a value normal training data never had (e.g. a sensitive path).

        An Isolation Forest cannot split on a feature that was constant in training, so it is
        blind to exactly these never-seen signals; this check closes that gap.
        """
        return [name for name, seen in self.seen_indicators.items() if features[name] not in seen]

    def ml_risk(self, features: dict[str, float]) -> float:
        if self.out_of_support(features):
            return 1.0
        return calibrated_risk(self.anomaly_score(features), self.forest_reference)

    def markov_risk(self, previous: str, token: str) -> float:
        # A token normal traffic never produced (e.g. list_dir:S) is maximally surprising. Without
        # this, a never-seen *previous* state falls back to a uniform guess and scores low.
        if token not in self.markov.vocabulary:
            return 1.0
        return calibrated_risk(self.markov.surprise(previous, token), self.markov_reference)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)

    @staticmethod
    def load(path: Path) -> "DetectionModel":
        # joblib unpickles: only ever load model files this project produced itself.
        model = joblib.load(path)
        if not isinstance(model, DetectionModel):
            raise StaleModel(f"{path} does not contain a DetectionModel")
        if model.feature_names != FEATURE_NAMES or not getattr(model, "seen_indicators", None):
            raise StaleModel(f"{path} was trained on other features. Run: uv run sentinel-train")
        return model
