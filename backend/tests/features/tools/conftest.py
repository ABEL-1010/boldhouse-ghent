from pathlib import Path

import pytest

from sentinel.core.config import Settings
from sentinel.features.tools import reset_sandbox

SEED_WORKSPACE = Settings(_env_file=None).seed_workspace


@pytest.fixture
def outbox(tmp_path: Path) -> Path:
    return tmp_path / "outbox.jsonl"


@pytest.fixture
def workspace(tmp_path: Path, outbox: Path) -> Path:
    """A fresh runtime copy of the real seed workspace, isolated per test."""
    runtime = tmp_path / "workspace"
    reset_sandbox(SEED_WORKSPACE, runtime, outbox)
    return runtime
