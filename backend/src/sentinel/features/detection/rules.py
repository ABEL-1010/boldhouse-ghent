import posixpath
from typing import Any

from sentinel.features.detection.taint import TaintFinding
from sentinel.features.events import RuleId, ToolName


def _inside_tmp(path: str) -> bool:
    normalized = posixpath.normpath(path.replace("\\", "/")).lstrip("/")
    return normalized == "tmp" or normalized.startswith("tmp/")


def evaluate_rules(
    tool: ToolName, args: dict[str, Any], features: dict[str, float], taint: TaintFinding
) -> list[RuleId]:
    """Policy rules: explicit, explainable checks on top of the features (Roadmap §1)."""
    hits: list[RuleId] = []
    if tool is ToolName.READ_FILE and features["sensitive_target"]:
        hits.append(RuleId.SENSITIVE_READ)
    if features["unknown_destination"]:
        hits.append(RuleId.UNKNOWN_DESTINATION)
    # Cleaning up tmp/ is normal; destroying anything else is not.
    if features["destructive"] and not _inside_tmp(str(args.get("path", ""))):
        hits.append(RuleId.DESTRUCTIVE_OUTSIDE_TMP)
    if taint.honeytoken:
        hits.append(RuleId.HONEYTOKEN)
    return hits
