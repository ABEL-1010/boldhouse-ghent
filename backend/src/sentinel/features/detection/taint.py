"""Taint tracking: did data from a sensitive read flow into an outbound call? (Roadmap §5 Step 6)

Deterministic and independent of how "normal" the behaviour looks, which makes it the strongest
layer. Payloads are checked as plain text and after base64-decoding, because attackers encode.
"""

import base64
import binascii
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

MIN_LINE_CHARS = 8
FRAGMENT_CHARS = 8
# Key-like runs: long, no spaces. Also matches base64 and URL-safe base64.
TOKEN = re.compile(r"[A-Za-z0-9+/_\-]{16,}={0,2}")


def _is_secret_like(token: str) -> bool:
    # Letters *and* digits: "hny-db-9c41e7b2d8a3" yes, "INTERNAL_API_TOKEN" no.
    return any(c.isdigit() for c in token) and any(c.isalpha() for c in token)


def taint_from_content(content: str) -> tuple[set[str], set[str]]:
    """What a sensitive read taints: its meaningful lines, and 8-char fragments of its secrets.

    Fragments catch slow exfiltration (a key split across several requests) without matching
    ordinary words, because only secret-like tokens are fragmented.
    """
    lines = {line.strip() for line in content.splitlines() if len(line.strip()) >= MIN_LINE_CHARS}
    fragments: set[str] = set()
    for token in TOKEN.findall(content):
        token = token.rstrip("=")
        if _is_secret_like(token):
            fragments.update(
                token[i : i + FRAGMENT_CHARS] for i in range(len(token) - FRAGMENT_CHARS + 1)
            )
    return lines, fragments


def payload_text(args: dict[str, Any]) -> str:
    """All string values of the call arguments (recursively), one per line."""

    def strings(value: Any) -> Iterator[str]:
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for item in value.values():
                yield from strings(item)
        elif isinstance(value, list | tuple):
            for item in value:
                yield from strings(item)

    return "\n".join(strings(args))


def _b64decode(candidate: str) -> str | None:
    normalized = candidate.replace("-", "+").replace("_", "/")
    normalized += "=" * (-len(normalized) % 4)
    try:
        decoded = base64.b64decode(normalized, validate=True)
    except (binascii.Error, ValueError):
        return None
    text = decoded.decode("utf-8", errors="ignore")
    # Random bytes that happen to decode are not evidence; real hidden text is mostly printable.
    printable = sum(c.isprintable() or c.isspace() for c in text)
    return text if text and printable / len(text) > 0.9 else None


def decoded_views(text: str) -> list[str]:
    """Base64 decodings hidden in the text: each token, plus the whole text without whitespace."""
    candidates: Iterable[str] = [*TOKEN.findall(text), "".join(text.split())]
    views = (_b64decode(candidate) for candidate in candidates)
    return [view for view in dict.fromkeys(views) if view]


@dataclass(frozen=True)
class TaintFinding:
    honeytoken: bool = False
    tainted: bool = False
    evidence: tuple[str, ...] = ()


NO_TAINT = TaintFinding()


def check_outbound(
    args: dict[str, Any],
    *,
    honeytokens: frozenset[str],
    tainted_lines: set[str],
    secret_fragments: set[str],
) -> TaintFinding:
    plain = payload_text(args)
    views = [("plain", plain), *(("base64-decoded", view) for view in decoded_views(plain))]
    evidence: list[str] = []
    honeytoken = tainted = False
    for label, text in views:
        if any(token in text for token in honeytokens):
            honeytoken = True
            evidence.append(f"honeytoken ({label})")
        if any(line in text for line in tainted_lines):
            tainted = True
            evidence.append(f"tainted line ({label})")
        if any(fragment in text for fragment in secret_fragments):
            tainted = True
            evidence.append(f"secret fragment ({label})")
    return TaintFinding(honeytoken, tainted, tuple(dict.fromkeys(evidence)))
