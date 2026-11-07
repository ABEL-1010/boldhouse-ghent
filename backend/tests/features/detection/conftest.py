from pathlib import Path

import pytest

from sentinel.core.config import Settings
from sentinel.features.detection import SessionContext
from sentinel.features.tools import reset_sandbox


@pytest.fixture
def ctx(tmp_path: Path) -> SessionContext:
    workspace = tmp_path / "workspace"
    reset_sandbox(Settings(_env_file=None).seed_workspace, workspace, tmp_path / "outbox.jsonl")
    return SessionContext(workspace=workspace, allowed_domains=frozenset({"ourcompany.be"}))
