import math

import pytest

from sentinel.features.detection import START_TOKEN, MarkovModel, SessionContext, extract_features
from sentinel.features.detection.markov import call_token, token_from_features
from sentinel.features.events import ToolName

SEQUENCES = [
    ["list_dir:N", "read_file:N", "write_file:N"],
    ["list_dir:N", "read_file:N", "send_email:N"],
    ["fetch_url:N", "write_file:N"],
]


def test_tokens_mark_sensitive_calls() -> None:
    assert call_token(ToolName.READ_FILE, sensitive=True) == "read_file:S"
    assert call_token(ToolName.SEND_EMAIL, sensitive=False) == "send_email:N"


def test_probabilities_follow_counts_with_laplace_smoothing() -> None:
    model = MarkovModel.fit(SEQUENCES)

    # After list_dir:N: read_file:N seen 2/2 times. Vocabulary 5 tokens + 1 unseen bucket.
    assert model.probability("list_dir:N", "read_file:N") == pytest.approx((2 + 1) / (2 + 6))
    assert model.probability("list_dir:N", "send_email:S") == pytest.approx(1 / 8)
    assert model.probability(START_TOKEN, "list_dir:N") == pytest.approx((2 + 1) / (3 + 6))


def test_unseen_transitions_are_more_surprising() -> None:
    model = MarkovModel.fit(SEQUENCES)

    usual = model.surprise("list_dir:N", "read_file:N")
    secret_then_send = model.surprise("read_file:S", "send_email:S")

    assert secret_then_send > usual
    assert secret_then_send == pytest.approx(-math.log(1 / 6))  # unknown previous token


def test_context_token_matches_feature_token(ctx: SessionContext) -> None:
    """Serving uses ctx.last_token; training uses token_from_features. They must agree."""
    env = (ctx.workspace / ".env").read_text(encoding="utf-8")
    calls = [
        (ToolName.LIST_DIR, {"path": "."}, ""),
        (ToolName.READ_FILE, {"path": ".env"}, env),
        (ToolName.SEND_EMAIL, {"to": "team@ourcompany.be", "subject": "s", "body": "b"}, ""),
        (ToolName.READ_FILE, {"path": "notes.md"}, "notes"),
    ]
    for tool, args, content in calls:
        expected = token_from_features(tool, extract_features(tool, args, ctx))
        ctx.observe(tool, args, ok=True, content=content)
        assert ctx.last_token == expected
    assert ctx.last_token == "read_file:N"
