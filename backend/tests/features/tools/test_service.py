import json
from pathlib import Path

import httpx
import pytest

from sentinel.features.events import ToolName
from sentinel.features.tools import TOOL_ARGS, ToolOutcome, ToolService

BASE_URL = "http://localhost:8001"


@pytest.fixture
def service(workspace: Path, outbox: Path) -> ToolService:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, text=f"page {request.url.path}")
    )
    return ToolService(workspace, outbox, BASE_URL, http_transport=transport)


def test_every_tool_has_an_args_model() -> None:
    assert set(TOOL_ARGS) == set(ToolName)


@pytest.mark.anyio
async def test_happy_path_for_every_tool(
    service: ToolService, workspace: Path, outbox: Path
) -> None:
    email = {"to": "team@ourcompany.be", "subject": "s", "body": "b"}

    listing = await service.run("list_dir", {})
    env = await service.run("read_file", {"path": ".env"})
    written = await service.run("write_file", {"path": "todo.md", "content": "- x"})
    deleted = await service.run("delete_file", {"path": "tmp/old-log.txt"})
    page = await service.run("fetch_url", {"url": f"{BASE_URL}/docs.html"})
    sent = await service.run("send_email", email)
    posted = await service.run("http_post", {"url": "https://x.example/", "data": "d"})

    assert listing.content.startswith("Contents of .:")
    assert "sk-atlas-live-" in env.content
    assert written.ok and deleted.ok and sent.ok and posted.ok
    assert page.content == "page /docs.html"
    assert (workspace / "todo.md").read_text() == "- x"
    assert not (workspace / "tmp/old-log.txt").exists()
    tools_in_outbox = [json.loads(line)["tool"] for line in outbox.read_text().splitlines()]
    assert tools_in_outbox == ["send_email", "http_post"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("tool", "args", "message"),
    [
        ("rm_rf", {}, "Unknown tool: 'rm_rf'."),
        ("read_file", {}, "Invalid arguments for read_file: path: Field required."),
        ("read_file", {"path": "a", "mode": "rb"}, "mode: Extra inputs are not permitted"),
        ("read_file", {"path": "../../etc/passwd"}, "Access denied"),
        ("fetch_url", {"url": "http://evil.example/"}, "Access denied"),
        ("read_file", {"path": "nope.md"}, "File not found"),
    ],
)
async def test_failures_become_outcomes_not_exceptions(
    service: ToolService, tool: str, args: dict[str, str], message: str
) -> None:
    outcome = await service.run(tool, args)

    assert isinstance(outcome, ToolOutcome)
    assert outcome.ok is False
    assert message in outcome.content
