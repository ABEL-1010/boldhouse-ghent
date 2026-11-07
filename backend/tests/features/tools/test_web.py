import httpx
import pytest

from sentinel.features.tools import web
from sentinel.features.tools.errors import SandboxViolation, ToolError

BASE_URL = "http://localhost:8001"


class RecordingTransport(httpx.AsyncBaseTransport):
    def __init__(self, response: httpx.Response | Exception) -> None:
        self.response = response
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@pytest.mark.anyio
async def test_fetches_allowed_page() -> None:
    transport = RecordingTransport(httpx.Response(200, text="<h1>News</h1>"))

    body = await web.fetch_url(f"{BASE_URL}/news1.html", BASE_URL, transport)

    assert body == "<h1>News</h1>"
    assert str(transport.requests[0].url) == f"{BASE_URL}/news1.html"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "url",
    [
        "http://evil.example/steal",
        "https://localhost:8001/news1.html",
        "http://localhost:8002/news1.html",
        "http://localhost:8001@evil.example/",
        "http://127.0.0.1:8001/news1.html",
        "file:///etc/passwd",
    ],
)
async def test_rejects_urls_outside_fake_web_without_any_request(url: str) -> None:
    transport = RecordingTransport(httpx.Response(200, text="should not be reached"))

    with pytest.raises(SandboxViolation):
        await web.fetch_url(url, BASE_URL, transport)
    assert transport.requests == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("response", "message"),
    [
        (httpx.Response(404), "HTTP 404"),
        (httpx.Response(302, headers={"location": "http://evil.example/"}), "HTTP 302"),
        (httpx.ConnectError("refused"), "Could not fetch"),
    ],
)
async def test_failed_fetch_becomes_tool_error(
    response: httpx.Response | Exception, message: str
) -> None:
    with pytest.raises(ToolError, match=message):
        await web.fetch_url(f"{BASE_URL}/x.html", BASE_URL, RecordingTransport(response))


@pytest.mark.anyio
async def test_truncates_large_pages() -> None:
    transport = RecordingTransport(httpx.Response(200, text="a" * (web.MAX_FETCH_CHARS + 5)))

    body = await web.fetch_url(f"{BASE_URL}/big.html", BASE_URL, transport)

    assert body.endswith(f"[truncated: showing first {web.MAX_FETCH_CHARS} chars]")
