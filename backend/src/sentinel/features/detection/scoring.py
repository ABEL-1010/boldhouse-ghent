"""Combine all detection signals into one risk score and action (Roadmap §5 Step 8)."""

import logging
from dataclasses import dataclass
from typing import Any, Protocol

from sentinel.features.detection.context import SessionContext
from sentinel.features.detection.features import extract_features
from sentinel.features.detection.markov import token_from_features
from sentinel.features.detection.model import DetectionModel
from sentinel.features.detection.patterns import OUTBOUND_TOOLS
from sentinel.features.detection.rules import evaluate_rules
from sentinel.features.detection.taint import NO_TAINT, check_outbound
from sentinel.features.events import Action, RuleId, Signals, ToolName

logger = logging.getLogger("sentinel.detection")

RULE_RISK: dict[RuleId, float] = {
    RuleId.SENSITIVE_READ: 0.5,
    RuleId.UNKNOWN_DESTINATION: 0.7,
    RuleId.DESTRUCTIVE_OUTSIDE_TMP: 0.8,
    RuleId.HONEYTOKEN: 1.0,
}
FLAG_THRESHOLD = 0.5
PAUSE_THRESHOLD = 0.8
ML_WEIGHT = 0.6
MARKOV_WEIGHT = 0.4


@dataclass(frozen=True)
class ScoringInput:
    session_id: str
    step: int
    tool: ToolName
    args: dict[str, Any]
    # State *before* this call; detection reads it, only the gateway updates it.
    context: SessionContext


@dataclass(frozen=True)
class Score:
    signals: Signals
    risk: float
    action: Action


class Scorer(Protocol):
    def score(self, call: ScoringInput) -> Score: ...


def combine(
    rule_hits: list[RuleId], taint_hit: bool, ml_risk: float, markov_risk: float
) -> tuple[float, Action]:
    """Taint or a honeytoken always pauses; otherwise the strongest of rules and ML wins."""
    if taint_hit or RuleId.HONEYTOKEN in rule_hits:
        return 1.0, Action.PAUSE
    rule_risk = max((RULE_RISK[rule] for rule in rule_hits), default=0.0)
    risk = round(max(rule_risk, ML_WEIGHT * ml_risk + MARKOV_WEIGHT * markov_risk), 2)
    if risk >= PAUSE_THRESHOLD:
        return risk, Action.PAUSE
    if risk >= FLAG_THRESHOLD:
        return risk, Action.FLAG
    return risk, Action.ALLOW


class SentinelScorer:
    """Rules + taint + honeytokens, plus the ML layers (Isolation Forest, Markov) when trained."""

    def __init__(self, honeytokens: frozenset[str], model: DetectionModel | None = None) -> None:
        self._honeytokens = honeytokens
        self._model = model
        if model is None:
            logger.warning(
                "No ML model loaded: scoring with rules + taint only (%d honeytokens). "
                "Train one with: uv run sentinel-traces && uv run sentinel-train",
                len(honeytokens),
            )
        else:
            logger.info(
                "Scoring with rules + taint (%d honeytokens) + ML (%s).",
                len(honeytokens),
                model.info.get("summary", "trained model"),
            )

    def score(self, call: ScoringInput) -> Score:
        ctx = call.context
        features = extract_features(call.tool, call.args, ctx)
        taint = (
            check_outbound(
                call.args,
                honeytokens=self._honeytokens,
                tainted_lines=ctx.tainted_lines,
                secret_fragments=ctx.secret_fragments,
            )
            if call.tool in OUTBOUND_TOOLS
            else NO_TAINT
        )
        rules = evaluate_rules(call.tool, call.args, features, taint)
        ml_risk = markov_risk = 0.0
        unseen: list[str] = []
        if self._model is not None:
            unseen = self._model.out_of_support(features)
            ml_risk = round(self._model.ml_risk(features), 2)
            token = token_from_features(call.tool, features)
            markov_risk = round(self._model.markov_risk(ctx.last_token, token), 2)
        risk, action = combine(rules, taint.tainted, ml_risk, markov_risk)
        if action is not Action.ALLOW:
            logger.info(
                "%s %s step %d: %s risk=%.2f rules=%s taint=%s ml=%.2f markov=%.2f unseen=%s",
                call.session_id,
                call.tool.value,
                call.step,
                action.value,
                risk,
                [rule.value for rule in rules],
                list(taint.evidence),
                ml_risk,
                markov_risk,
                unseen,
            )
        return Score(
            signals=Signals(
                rules=rules,
                taint=taint.tainted or taint.honeytoken,
                ml_risk=ml_risk,
                markov_risk=markov_risk,
            ),
            risk=risk,
            action=action,
        )
