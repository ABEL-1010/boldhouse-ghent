"""Guards docs/contract/event.schema.json against drifting from the Pydantic models.

After an intentional contract change, regenerate the file with:
    UPDATE_CONTRACT=1 uv run pytest tests/features/events
"""

import json
import os
from pathlib import Path

from sentinel.features.events import SentinelEvent

SCHEMA_PATH = Path(__file__).resolve().parents[4] / "docs" / "contract" / "event.schema.json"


def test_committed_json_schema_matches_models() -> None:
    expected = json.dumps(SentinelEvent.model_json_schema(), indent=2) + "\n"

    if os.environ.get("UPDATE_CONTRACT") == "1":
        SCHEMA_PATH.write_text(expected, encoding="utf-8", newline="\n")

    assert SCHEMA_PATH.exists(), "Missing contract file; run with UPDATE_CONTRACT=1"
    assert SCHEMA_PATH.read_text(encoding="utf-8") == expected, (
        "Event contract changed. Run with UPDATE_CONTRACT=1, "
        "then update frontend/src/lib/events/types.ts"
    )
