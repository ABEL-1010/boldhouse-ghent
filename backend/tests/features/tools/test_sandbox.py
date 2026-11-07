import os
from pathlib import Path

import pytest

from sentinel.features.tools.errors import SandboxViolation
from sentinel.features.tools.sandbox import display_path, resolve_in_workspace


def test_resolves_paths_inside_workspace(tmp_path: Path) -> None:
    resolved = resolve_in_workspace(tmp_path, "project/README.md")

    assert resolved == (tmp_path / "project" / "README.md").resolve()
    assert display_path(tmp_path, resolved) == "project/README.md"
    assert display_path(tmp_path, resolve_in_workspace(tmp_path, ".")) == "."


def test_inner_dotdot_that_stays_inside_is_allowed(tmp_path: Path) -> None:
    resolved = resolve_in_workspace(tmp_path, "project/../notes.md")

    assert resolved == (tmp_path / "notes.md").resolve()


@pytest.mark.parametrize(
    "path",
    [
        "../../etc/passwd",
        "..",
        "project/../../outside.txt",
        r"..\..\Windows\win.ini",
        "",
        "   ",
        "notes\x00.md",
    ],
)
def test_rejects_paths_that_escape_or_are_malformed(tmp_path: Path, path: str) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(SandboxViolation):
        resolve_in_workspace(workspace, path)


def test_rejects_absolute_paths_outside_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "secret.txt"

    with pytest.raises(SandboxViolation):
        resolve_in_workspace(workspace, str(outside))


def test_rejects_symlink_escape(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        os.symlink(outside, workspace / "link", target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks needs extra privileges on this OS")

    with pytest.raises(SandboxViolation):
        resolve_in_workspace(workspace, "link/file.txt")
