import base64
import json
import math

import pytest

from sentinel.features.detection import FEATURE_NAMES, SessionContext, extract_features
from sentinel.features.detection.features import shannon_entropy
from sentinel.features.events import ToolName

HONEYTOKEN = "sk-atlas-live-7f3a9c2e41b84d6f"


def test_vector_has_fixed_names_and_order(ctx: SessionContext) -> None:
    features = extract_features(ToolName.LIST_DIR, {}, ctx)

    assert tuple(features) == FEATURE_NAMES
    assert len(FEATURE_NAMES) == 17
    assert all(isinstance(value, float) for value in features.values())


@pytest.mark.parametrize("tool", list(ToolName))
def test_tool_is_one_hot(ctx: SessionContext, tool: ToolName) -> None:
    features = extract_features(tool, {}, ctx)

    hot = [name for name in FEATURE_NAMES if name.startswith("tool_") and features[name] == 1.0]
    assert hot == [f"tool_{tool.value}"]


@pytest.mark.parametrize(
    ("path", "sensitive"),
    [(".env", 1.0), ("config/secrets.yaml", 1.0), ("API_KEY.txt", 1.0), ("notes.md", 0.0)],
)
def test_sensitive_target(ctx: SessionContext, path: str, sensitive: float) -> None:
    features = extract_features(ToolName.READ_FILE, {"path": path}, ctx)

    assert features["sensitive_target"] == sensitive


@pytest.mark.parametrize(
    ("tool", "args", "outbound", "unknown"),
    [
        (ToolName.SEND_EMAIL, {"to": "team@ourcompany.be"}, 1.0, 0.0),
        (ToolName.SEND_EMAIL, {"to": "backup@unknown-domain.xyz"}, 1.0, 1.0),
        (ToolName.HTTP_POST, {"url": "https://api.ourcompany.be/x"}, 1.0, 0.0),
        (ToolName.HTTP_POST, {"url": "https://collector.example/x"}, 1.0, 1.0),
        # fetch_url is not outbound: the sandbox limits it to the fake web, so no data leaves.
        (ToolName.FETCH_URL, {"url": "https://collector.example/x"}, 0.0, 0.0),
    ],
)
def test_outbound_and_unknown_destination(
    ctx: SessionContext, tool: ToolName, args: dict[str, str], outbound: float, unknown: float
) -> None:
    features = extract_features(tool, args, ctx)

    assert (features["outbound"], features["unknown_destination"]) == (outbound, unknown)


@pytest.mark.parametrize(
    ("tool", "args", "destructive"),
    [
        (ToolName.DELETE_FILE, {"path": "tmp/scratch.txt"}, 1.0),
        (ToolName.WRITE_FILE, {"path": "notes.md", "content": "overwritten"}, 1.0),
        (ToolName.WRITE_FILE, {"path": "summary.md", "content": "new file"}, 0.0),
        (ToolName.READ_FILE, {"path": "notes.md"}, 0.0),
    ],
)
def test_destructive(
    ctx: SessionContext, tool: ToolName, args: dict[str, str], destructive: float
) -> None:
    assert extract_features(tool, args, ctx)["destructive"] == destructive


def test_payload_size_and_entropy(ctx: SessionContext) -> None:
    args = {"path": "notes.md"}
    features = extract_features(ToolName.READ_FILE, args, ctx)

    blob = json.dumps(args, sort_keys=True)
    assert features["payload_log_len"] == pytest.approx(math.log1p(len(blob)))
    assert features["payload_entropy"] == pytest.approx(shannon_entropy(blob))


def test_shannon_entropy_reference_values() -> None:
    assert shannon_entropy("") == 0.0
    assert shannon_entropy("aaaa") == 0.0
    assert shannon_entropy("abab") == pytest.approx(1.0)
    assert shannon_entropy("abcd") == pytest.approx(2.0)


def test_encoded_payload_has_higher_entropy_than_prose(ctx: SessionContext) -> None:
    prose = {"to": "x@y.z", "body": "Hi team, here are the notes from this week. " * 3}
    encoded = {"to": "x@y.z", "body": base64.b64encode(HONEYTOKEN.encode() * 4).decode()}

    plain = extract_features(ToolName.SEND_EMAIL, prose, ctx)["payload_entropy"]
    b64 = extract_features(ToolName.SEND_EMAIL, encoded, ctx)["payload_entropy"]

    assert b64 > plain


def test_secret_pattern_catches_plain_keys_but_not_base64(ctx: SessionContext) -> None:
    plain = {"to": "x@y.z", "body": f"key={HONEYTOKEN}"}
    encoded = {"to": "x@y.z", "body": base64.b64encode(HONEYTOKEN.encode()).decode()}

    assert extract_features(ToolName.SEND_EMAIL, plain, ctx)["secret_pattern"] == 1.0
    # Known blind spot of this feature; the taint layer (Step 6) decodes base64.
    assert extract_features(ToolName.SEND_EMAIL, encoded, ctx)["secret_pattern"] == 0.0


@pytest.mark.parametrize(("steps", "scaled"), [(0, 0.0), (10, 0.5), (20, 1.0), (45, 1.0)])
def test_step_is_scaled_and_capped(ctx: SessionContext, steps: int, scaled: float) -> None:
    ctx.steps_so_far = steps

    assert extract_features(ToolName.LIST_DIR, {}, ctx)["step"] == scaled


def test_outbound_after_sensitive_read(ctx: SessionContext) -> None:
    email = {"to": "team@ourcompany.be", "subject": "s", "body": "b"}
    before = extract_features(ToolName.SEND_EMAIL, email, ctx)

    ctx.observe(ToolName.READ_FILE, {"path": ".env"}, ok=True, content="")
    after = extract_features(ToolName.SEND_EMAIL, email, ctx)
    read_after = extract_features(ToolName.READ_FILE, {"path": "notes.md"}, ctx)

    assert before["outbound_after_sensitive"] == 0.0
    assert after["outbound_after_sensitive"] == 1.0
    assert after["sensitive_reads_so_far"] == pytest.approx(1 / 5)
    assert read_after["outbound_after_sensitive"] == 0.0  # not outbound


def test_sensitive_reads_feature_is_capped(ctx: SessionContext) -> None:
    ctx.sensitive_reads = 12

    assert extract_features(ToolName.LIST_DIR, {}, ctx)["sensitive_reads_so_far"] == 1.0


def test_extraction_does_not_mutate_context(ctx: SessionContext) -> None:
    extract_features(ToolName.READ_FILE, {"path": ".env"}, ctx)

    assert (ctx.steps_so_far, ctx.sensitive_reads) == (0, 0)
