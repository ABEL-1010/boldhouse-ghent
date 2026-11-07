"""Mocked outbound tools. Nothing leaves the laptop: every "send" is appended to outbox.jsonl."""

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from sentinel.features.events import ToolName
from sentinel.features.tools.errors import ToolError

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _append(outbox_path: Path, tool: ToolName, payload: dict[str, Any]) -> None:
    record = {"ts": datetime.now(UTC).isoformat(), "tool": tool.value, **payload}
    outbox_path.parent.mkdir(parents=True, exist_ok=True)
    with outbox_path.open("a", encoding="utf-8", newline="\n") as outbox:
        outbox.write(json.dumps(record, ensure_ascii=False) + "\n")


def send_email(outbox_path: Path, to: str, subject: str, body: str) -> str:
    if not EMAIL_PATTERN.match(to):
        raise ToolError(f"Invalid email address: '{to}'.")
    _append(outbox_path, ToolName.SEND_EMAIL, {"to": to, "subject": subject, "body": body})
    return f"Email sent to {to}."


def http_post(outbox_path: Path, url: str, data: str) -> str:
    try:
        parsed = httpx.URL(url)
    except httpx.InvalidURL as exc:
        raise ToolError(f"Invalid URL: '{url}'.") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.host:
        raise ToolError(f"Invalid URL: '{url}'. Use an http(s) URL.")
    _append(outbox_path, ToolName.HTTP_POST, {"url": url, "data": data})
    return f"POST {url} -> 200 OK."
