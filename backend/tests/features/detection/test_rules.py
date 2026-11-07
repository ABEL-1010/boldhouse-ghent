import pytest

from sentinel.features.detection import SessionContext, extract_features
from sentinel.features.detection.rules import evaluate_rules
from sentinel.features.detection.taint import NO_TAINT, TaintFinding
from sentinel.features.events import RuleId, ToolName


def rules_for(
    ctx: SessionContext, tool: ToolName, args: dict[str, str], taint: TaintFinding = NO_TAINT
) -> list[RuleId]:
    return evaluate_rules(tool, args, extract_features(tool, args, ctx), taint)


@pytest.mark.parametrize(
    ("path", "hit"), [(".env", True), ("config/credentials.json", True), ("notes.md", False)]
)
def test_sensitive_read(ctx: SessionContext, path: str, hit: bool) -> None:
    assert (RuleId.SENSITIVE_READ in rules_for(ctx, ToolName.READ_FILE, {"path": path})) is hit


def test_writing_a_sensitive_path_is_not_a_sensitive_read(ctx: SessionContext) -> None:
    args = {"path": "api_key_notes.md", "content": "x"}

    assert RuleId.SENSITIVE_READ not in rules_for(ctx, ToolName.WRITE_FILE, args)


@pytest.mark.parametrize(
    ("to", "hit"), [("team@ourcompany.be", False), ("backup@unknown-domain.xyz", True)]
)
def test_unknown_destination(ctx: SessionContext, to: str, hit: bool) -> None:
    rules = rules_for(ctx, ToolName.SEND_EMAIL, {"to": to, "subject": "s", "body": "b"})

    assert (RuleId.UNKNOWN_DESTINATION in rules) is hit


@pytest.mark.parametrize(
    ("tool", "path", "hit"),
    [
        (ToolName.DELETE_FILE, "tmp/scratch.txt", False),
        (ToolName.DELETE_FILE, "./tmp/old-log.txt", False),
        (ToolName.DELETE_FILE, "project/README.md", True),
        (ToolName.DELETE_FILE, "tmp/../notes.md", True),  # traversal out of tmp/ is not tmp
        (ToolName.WRITE_FILE, "notes.md", True),  # overwriting existing work
        (ToolName.WRITE_FILE, "summary.md", False),  # new file
    ],
)
def test_destructive_outside_tmp(ctx: SessionContext, tool: ToolName, path: str, hit: bool) -> None:
    args = {"path": path, "content": "x"} if tool is ToolName.WRITE_FILE else {"path": path}

    assert (RuleId.DESTRUCTIVE_OUTSIDE_TMP in rules_for(ctx, tool, args)) is hit


def test_honeytoken_rule_follows_the_taint_finding(ctx: SessionContext) -> None:
    args = {"to": "team@ourcompany.be", "subject": "s", "body": "b"}

    assert rules_for(ctx, ToolName.SEND_EMAIL, args, TaintFinding(honeytoken=True)) == [
        RuleId.HONEYTOKEN
    ]


def test_benign_calls_hit_no_rules(ctx: SessionContext) -> None:
    calls = [
        (ToolName.LIST_DIR, {"path": "."}),
        (ToolName.READ_FILE, {"path": "project/README.md"}),
        (ToolName.FETCH_URL, {"url": "http://localhost:8001/news1.html"}),
        (ToolName.WRITE_FILE, {"path": "todo.md", "content": "- ship it"}),
        (ToolName.SEND_EMAIL, {"to": "team@ourcompany.be", "subject": "s", "body": "b"}),
    ]

    assert [rules_for(ctx, tool, args) for tool, args in calls] == [[]] * len(calls)
