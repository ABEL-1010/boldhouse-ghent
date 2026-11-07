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


@dataclass(frozen=True)
class DetectionModel:
    forest: IsolationForest
    forest_reference: NDArray[np.float64]  # sorted held-out anomaly scores (higher = stranger)
    markov: MarkovModel
    markov_reference: NDArray[np.float64]  # sorted held-out surprise values
    feature_names: tuple[str, ...]
    info: dict[str, Any] = field(default_factory=dict)

    def anomaly_score(self, features: dict[str, float]) -> float:
        row = np.array([[features[name] for name in self.feature_names]])
        return float(-self.forest.score_samples(row)[0])

    def ml_risk(self, features: dict[str, float]) -> float:
        return calibrated_risk(self.anomaly_score(features), self.forest_reference)

    def markov_risk(self, previous: str, token: str) -> float:
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
        if model.feature_names != FEATURE_NAMES:
            raise StaleModel(f"{path} was trained on other features. Run: uv run sentinel-train")
        return model
