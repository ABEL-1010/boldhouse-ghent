"""Sequence model: how surprising is this tool call, given the previous one? (Roadmap §5 Step 7d)

Catches unusual *orderings* (read secrets -> send email) even when each call looks fine alone.
"""

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from sentinel.features.events import ToolName

START_TOKEN = "<start>"


def call_token(tool: ToolName, *, sensitive: bool) -> str:
    """`read_file:S` for a sensitive call, `send_email:N` for a normal one."""
    return f"{tool.value}:{'S' if sensitive else 'N'}"


def token_from_features(tool: ToolName, features: dict[str, float]) -> str:
    # Sensitive = touches a sensitive target, or sends data out after secrets were read.
    sensitive = bool(features["sensitive_target"] or features["outbound_after_sensitive"])
    return call_token(tool, sensitive=sensitive)


@dataclass(frozen=True)
class MarkovModel:
    transitions: dict[str, dict[str, int]]
    vocabulary: frozenset[str]
    alpha: float = 1.0

    @classmethod
    def fit(cls, sequences: Iterable[Sequence[str]], alpha: float = 1.0) -> "MarkovModel":
        transitions: dict[str, dict[str, int]] = {}
        vocabulary: set[str] = set()
        for sequence in sequences:
            previous = START_TOKEN
            for token in sequence:
                row = transitions.setdefault(previous, {})
                row[token] = row.get(token, 0) + 1
                vocabulary.add(token)
                previous = token
        return cls(transitions, frozenset(vocabulary), alpha)

    def probability(self, previous: str, token: str) -> float:
        """Laplace-smoothed P(token | previous). One extra bucket keeps unseen tokens possible."""
        row = self.transitions.get(previous, {})
        buckets = len(self.vocabulary) + 1
        return (row.get(token, 0) + self.alpha) / (sum(row.values()) + self.alpha * buckets)

    def surprise(self, previous: str, token: str) -> float:
        return -math.log(self.probability(previous, token))
