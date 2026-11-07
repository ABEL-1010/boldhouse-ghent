import httpx

from sentinel.features.tools.errors import SandboxViolation, ToolError

FETCH_TIMEOUT_SECONDS = 5.0
MAX_FETCH_CHARS = 100_000


def _ensure_allowed(url: str, base_url: str) -> httpx.URL:
    try:
        parsed = httpx.URL(url)
    except httpx.InvalidURL as exc:
        raise ToolError(f"Invalid URL: '{url}'.") from exc
    base = httpx.URL(base_url)
    # Compare parsed parts, not string prefixes: "http://localhost:8001@evil.com" has host evil.com.
    if (parsed.scheme, parsed.host, parsed.port) != (base.scheme, base.host, base.port):
        raise SandboxViolation(f"Access denied: only {base_url}/ can be fetched.")
    return parsed


async def fetch_url(
    url: str, base_url: str, transport: httpx.AsyncBaseTransport | None = None
) -> str:
    target = _ensure_allowed(url, base_url)
    try:
        # Redirects are not followed, so an allowed page can't bounce the agent elsewhere.
        async with httpx.AsyncClient(
            transport=transport, timeout=FETCH_TIMEOUT_SECONDS, follow_redirects=False
        ) as client:
            response = await client.get(target)
    except httpx.HTTPError as exc:
        raise ToolError(f"Could not fetch '{url}': {type(exc).__name__}.") from exc
    if response.status_code != 200:
        raise ToolError(f"Fetching '{url}' returned HTTP {response.status_code}.")
    text = response.text
    if len(text) > MAX_FETCH_CHARS:
        return text[:MAX_FETCH_CHARS] + f"\n[truncated: showing first {MAX_FETCH_CHARS} chars]"
    return text
