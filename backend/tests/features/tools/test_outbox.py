import json
from pathlib import Path

import pytest

from sentinel.features.tools import outbox as outbox_tools
from sentinel.features.tools.errors import ToolError


def read_records(outbox: Path) -> list[dict[str, str]]:
    return [json.loads(line) for line in outbox.read_text(encoding="utf-8").splitlines()]


def test_send_email_is_recorded_not_sent(outbox: Path) -> None:
    message = outbox_tools.send_email(outbox, "team@ourcompany.be", "Notes", "Week 46 notes")

    assert message == "Email sent to team@ourcompany.be."
    [record] = read_records(outbox)
    assert record["tool"] == "send_email"
    assert record["to"] == "team@ourcompany.be"
    assert record["body"] == "Week 46 notes"
    assert record["ts"].endswith("+00:00")


def test_http_post_is_recorded_not_sent(outbox: Path) -> None:
    outbox_tools.http_post(outbox, "https://collector.example/upload", '{"k": 1}')
    outbox_tools.http_post(outbox, "http://other.example/", "second")

    records = read_records(outbox)
    assert [r["url"] for r in records] == [
        "https://collector.example/upload",
        "http://other.example/",
    ]
    assert records[0]["data"] == '{"k": 1}'


@pytest.mark.parametrize("to", ["not-an-email", "a@b", "two@@ourcompany.be", "a b@ourcompany.be"])
def test_send_email_rejects_invalid_addresses(outbox: Path, to: str) -> None:
    with pytest.raises(ToolError, match="Invalid email"):
        outbox_tools.send_email(outbox, to, "s", "b")
    assert not outbox.exists()


@pytest.mark.parametrize("url", ["ftp://files.example/x", "not a url", "http://"])
def test_http_post_rejects_invalid_urls(outbox: Path, url: str) -> None:
    with pytest.raises(ToolError, match="Invalid URL"):
        outbox_tools.http_post(outbox, url, "data")
    assert not outbox.exists()
