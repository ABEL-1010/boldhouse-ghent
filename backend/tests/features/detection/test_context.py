import pytest

from sentinel.features.detection import SessionContext
from sentinel.features.detection.context import call_target, destination_domain
from sentinel.features.events import ToolName


@pytest.mark.parametrize(
    ("target", "domain"),
    [
        ("team@ourcompany.be", "ourcompany.be"),
        ("Team@OurCompany.BE", "ourcompany.be"),
        ("https://collector.example/upload", "collector.example"),
        ("http://ourcompany.be@evil.example/", "evil.example"),
        ("not a destination", None),
        ("", None),
    ],
)
def test_destination_domain(target: str, domain: str | None) -> None:
    assert destination_domain(target) == domain


@pytest.mark.parametrize(
    ("target", "allowed"),
    [
        ("team@ourcompany.be", True),
        ("ops@mail.ourcompany.be", True),
        ("https://api.ourcompany.be/v1", True),
        ("backup@unknown-domain.xyz", False),
        ("x@ourcompany.be.evil.example", False),
        ("x@notourcompany.be", False),
        ("http://ourcompany.be@evil.example/", False),
        ("garbage", False),
    ],
)
def test_allowlist_matches_domain_and_subdomains_only(
    ctx: SessionContext, target: str, allowed: bool
) -> None:
    assert ctx.is_allowlisted(target) is allowed


def test_exists_is_sandboxed(ctx: SessionContext) -> None:
    assert ctx.exists("notes.md")
    assert not ctx.exists("missing.md")
    assert not ctx.exists("project")  # a directory is not a file
    assert not ctx.exists("../../etc/passwd")


def test_observe_counts_steps_and_successful_sensitive_reads(ctx: SessionContext) -> None:
    ctx.observe(ToolName.LIST_DIR, {}, ok=True, content="")
    ctx.observe(
        ToolName.READ_FILE, {"path": ".env"}, ok=False, content=""
    )  # failed: no data was exposed
    ctx.observe(ToolName.READ_FILE, {"path": "notes.md"}, ok=True, content="")
    ctx.observe(ToolName.READ_FILE, {"path": ".env"}, ok=True, content="")
    ctx.observe(ToolName.WRITE_FILE, {"path": "api_key.txt", "content": "x"}, ok=True, content="")

    assert ctx.steps_so_far == 5
    assert ctx.sensitive_reads == 1


def test_call_target_prefers_path_then_url_then_recipient() -> None:
    assert call_target({"path": "a.md", "url": "http://x"}) == "a.md"
    assert call_target({"url": "http://x", "to": "a@b.c"}) == "http://x"
    assert call_target({"to": "a@b.c"}) == "a@b.c"
    assert call_target({}) == ""
