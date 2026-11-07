import shutil
from pathlib import Path

from sentinel.core.config import get_settings


def reset_sandbox(seed_workspace: Path, runtime_workspace: Path, outbox_path: Path) -> None:
    """Replace the runtime workspace with a fresh copy of the seed and empty the outbox."""
    if runtime_workspace.resolve() == seed_workspace.resolve():
        raise ValueError("Runtime workspace must differ from the seed; refusing to delete it.")
    if runtime_workspace.exists():
        shutil.rmtree(runtime_workspace)
    shutil.copytree(seed_workspace, runtime_workspace)
    outbox_path.parent.mkdir(parents=True, exist_ok=True)
    outbox_path.write_text("", encoding="utf-8")


def main() -> None:
    settings = get_settings()
    reset_sandbox(settings.seed_workspace, settings.runtime_workspace, settings.outbox_path)
    print(f"Sandbox reset: {settings.runtime_workspace} (outbox cleared)")
