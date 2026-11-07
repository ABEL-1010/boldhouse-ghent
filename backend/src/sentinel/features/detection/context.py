from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from sentinel.features.detection.patterns import SENSITIVE_TARGET
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

    def is_allowlisted(self, target: str) -> bool:
        domain = destination_domain(target)
        if domain is None:
            return False
        return any(domain == d or domain.endswith(f".{d}") for d in self.allowed_domains)

    def exists(self, path: str) -> bool:
        return file_exists_in_workspace(self.workspace, path)

    def observe(self, tool: ToolName, args: dict[str, Any], *, ok: bool) -> None:
        """Record a finished call. Only a successful sensitive read counts: no data, no risk."""
        self.steps_so_far += 1
        if tool is ToolName.READ_FILE and ok and SENSITIVE_TARGET.search(call_target(args)):
            self.sensitive_reads += 1
