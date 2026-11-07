import numpy as np
from numpy.typing import NDArray

# Risk is 0 up to the 95th percentile of held-out *normal* behaviour, and 1 beyond all of it.
NORMAL_PERCENTILE = 0.95


def calibrated_risk(score: float, reference: NDArray[np.float64]) -> float:
    """Map a raw anomaly score to 0..1 by its percentile among held-out normal scores.

    `reference` must be sorted ascending; higher scores mean more anomalous (Roadmap §5 Step 7c).
    """
    percentile = np.searchsorted(reference, score) / len(reference)
    risk = (percentile - NORMAL_PERCENTILE) / (1 - NORMAL_PERCENTILE)
    return float(min(max(risk, 0.0), 1.0))
