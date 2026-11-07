"""Tool call -> fixed-order numeric feature vector (Roadmap §5 Step 5).

Computed *before* the call runs, from the call and the session context. The column order in
FEATURE_NAMES is part of the ML model's contract: append new features, never reorder.
"""

import json
import math
from collections import Counter
from typing import Any

from sentinel.features.detection.context import SessionContext, call_target
from sentinel.features.detection.patterns import OUTBOUND_TOOLS, SECRET_PATTERN, SENSITIVE_TARGET
from sentinel.features.events import ToolName

STEP_SCALE = 20
MAX_SENSITIVE_READS = 5

FEATURE_NAMES: tuple[str, ...] = (
    *(f"tool_{tool.value}" for tool in ToolName),
    "sensitive_target",
    "outbound",
    "unknown_destination",
    "destructive",
    "payload_log_len",
    "payload_entropy",
    "secret_pattern",
    "step",
    "sensitive_reads_so_far",
    "outbound_after_sensitive",
)


def shannon_entropy(text: str) -> float:
    """Bits per character. Encoded or random data (keys, base64) scores high."""
    if not text:
        return 0.0
    n = len(text)
    return -sum(count / n * math.log2(count / n) for count in Counter(text).values())


def extract_features(tool: ToolName, args: dict[str, Any], ctx: SessionContext) -> dict[str, float]:
    blob = json.dumps(args, sort_keys=True)
    target = call_target(args)
    outbound = tool in OUTBOUND_TOOLS
    features = {f"tool_{t.value}": float(tool is t) for t in ToolName}
    features.update(
        sensitive_target=float(bool(SENSITIVE_TARGET.search(target))),
        outbound=float(outbound),
        unknown_destination=float(outbound and not ctx.is_allowlisted(target)),
        destructive=float(
            tool is ToolName.DELETE_FILE or (tool is ToolName.WRITE_FILE and ctx.exists(target))
        ),
        payload_log_len=math.log1p(len(blob)),
        payload_entropy=shannon_entropy(blob),
        secret_pattern=float(bool(SECRET_PATTERN.search(blob))),
        step=min(ctx.steps_so_far / STEP_SCALE, 1.0),
        sensitive_reads_so_far=min(ctx.sensitive_reads, MAX_SENSITIVE_READS) / MAX_SENSITIVE_READS,
        outbound_after_sensitive=float(outbound and ctx.sensitive_reads > 0),
    )
    return {name: features[name] for name in FEATURE_NAMES}
