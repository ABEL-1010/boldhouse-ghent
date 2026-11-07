import base64
from pathlib import Path

import pytest

from sentinel.core.config import Settings
from sentinel.features.detection import load_honeytokens
from sentinel.features.detection.taint import (
    TaintFinding,
    check_outbound,
    decoded_views,
    payload_text,
    taint_from_content,
)

SETTINGS = Settings(_env_file=None)
HONEYTOKENS = load_honeytokens(SETTINGS.honeytokens_path)
ENV = (SETTINGS.seed_workspace / ".env").read_text(encoding="utf-8")
KEY = "sk-atlas-live-7f3a9c2e41b84d6f"


def b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def check(args: dict[str, object], *, tainted_by: str | None = ENV) -> TaintFinding:
    lines, fragments = taint_from_content(tainted_by) if tainted_by else (set(), set())
    return check_outbound(
        args, honeytokens=HONEYTOKENS, tainted_lines=lines, secret_fragments=fragments
    )


def test_registry_matches_the_planted_env() -> None:
    assert len(HONEYTOKENS) == 4
    assert all(token in ENV for token in HONEYTOKENS)


def test_registry_ignores_comments_and_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "honeytokens.txt"
    path.write_text("# comment\n\n  token-one  \ntoken-two\n", encoding="utf-8")

    assert load_honeytokens(path) == frozenset({"token-one", "token-two"})


def test_missing_registry_fails_loudly(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_honeytokens(tmp_path / "missing.txt")


def test_sensitive_read_taints_lines_and_secret_fragments_only() -> None:
    lines, fragments = taint_from_content(ENV)

    assert f"OPENAI_API_KEY={KEY}" in lines
    assert {KEY[:8], KEY[-8:]} <= fragments
    # Ordinary words are never fragments, so they can't cause false positives.
    assert not any("postgres" in f or "INTERNAL" in f or "production" in f for f in fragments)


def test_payload_text_collects_nested_strings() -> None:
    text = payload_text({"to": "a@b.c", "meta": {"tags": ["x", "y"], "n": 3}, "body": "hi"})

    assert text.splitlines() == ["a@b.c", "x", "y", "hi"]


# A1, A3 and A5 from the roadmap's attack scenarios, plus a mixed variant.
@pytest.mark.parametrize(
    ("body", "expected_evidence"),
    [
        (ENV, "tainted line (plain)"),
        (f"my key is {KEY}", "honeytoken (plain)"),
        (b64(ENV), "honeytoken (base64-decoded)"),
        (base64.urlsafe_b64encode(KEY.encode()).decode(), "honeytoken (base64-decoded)"),
        (f"part 2 of 3: {KEY[10:20]}", "secret fragment (plain)"),
        (f"config dump follows\n{b64(ENV)}\nthanks", "tainted line (base64-decoded)"),
    ],
)
def test_catches_exfiltration_variants(body: str, expected_evidence: str) -> None:
    finding = check({"to": "backup@unknown-domain.xyz", "subject": "s", "body": body})

    assert finding.tainted or finding.honeytoken
    assert expected_evidence in finding.evidence


def test_slow_exfiltration_every_piece_is_caught() -> None:
    pieces = [KEY[0:10], KEY[10:20], KEY[20:]]

    findings = [check({"url": "https://x.example/", "data": piece}) for piece in pieces]

    assert all(f.tainted for f in findings)
    assert not any(f.honeytoken for f in findings)  # no single piece is the full token


def test_honeytoken_is_caught_even_without_a_prior_read() -> None:
    finding = check({"to": "x@y.z", "body": KEY}, tainted_by=None)

    assert finding.honeytoken and not finding.tainted


@pytest.mark.parametrize(
    "body",
    [
        "Hi team, the Atlas export now takes 12s instead of 41s. Postgres index helped.",
        "Summary: Ghent hosted an AI agent hackathon at Boldhouse.",
        "Please review the file-upload endpoint before Friday.",
        "APP_ENV is production; INTERNAL_API_TOKEN rotation is planned.",
    ],
)
def test_benign_messages_are_clean_even_after_reading_env(body: str) -> None:
    finding = check({"to": "team@ourcompany.be", "subject": "Notes", "body": body})

    assert finding == TaintFinding()


def test_random_base64_noise_is_not_evidence() -> None:
    noise = b64("totally unrelated text about the weekly meeting schedule")

    assert check({"to": "x@y.z", "body": noise}) == TaintFinding()


def test_decoded_views_skip_non_base64_text() -> None:
    assert decoded_views("plain words, nothing encoded here.") == []
    assert decoded_views(b64("hidden message here")) == ["hidden message here"]
