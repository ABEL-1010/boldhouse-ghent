from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from sentinel.features.detection.markov import START_TOKEN, call_token
from sentinel.features.detection.patterns import OUTBOUND_TOOLS, SENSITIVE_TARGET
from sentinel.features.detection.taint import taint_from_content
from sentinel.features.events import ToolName
from sentinel.features.tools import file_exists_in_workspace


def call_target(args: dict[str, Any]) -> str:
    """The thing a call acts on: a path, a URL or an email recipient."""
    return str(args.get("path") or args.get("url") or args.get("to") or "")


def destination_domain(target: str) -> str | None:
    """Domain of an email address or URL, lowercased. None if there is none."""
    if "://" not in target and "@" in target:
        return target.rsplit("@", 1)[1].strip().lower() or None
    try:
        host = urlsplit(target).hostname
    except ValueError:
        return None
    return host.lower() if host else None


@dataclass
class SessionContext:
    """What Sentinel knows about one agent session so far. Updated after every call."""

    workspace: Path
    allowed_domains: frozenset[str]
    steps_so_far: int = 0
    sensitive_reads: int = 0
    tainted_lines: set[str] = field(default_factory=set)
    secret_fragments: set[str] = field(default_factory=set)
    last_token: str = START_TOKEN

    def is_allowlisted(self, target: str) -> bool:
        domain = destination_domain(target)
        if domain is None:
            return False
        return any(domain == d or domain.endswith(f".{d}") for d in self.allowed_domains)

    def exists(self, path: str) -> bool:
        return file_exists_in_workspace(self.workspace, path)

    def observe(self, tool: ToolName, args: dict[str, Any], *, ok: bool, content: str) -> None:
        """Record a finished call. Only a successful sensitive read counts: no data, no risk."""
        self.steps_so_far += 1
        sensitive_target = bool(SENSITIVE_TARGET.search(call_target(args)))
        # Same definition as markov.token_from_features, from the state *before* this call.
        self.last_token = call_token(
            tool,
            sensitive=sensitive_target or (tool in OUTBOUND_TOOLS and self.sensitive_reads > 0),
        )
        if tool is ToolName.READ_FILE and ok and sensitive_target:
            self.sensitive_reads += 1
            lines, fragments = taint_from_content(content)
            self.tainted_lines |= lines
            self.secret_fragments |= fragments
