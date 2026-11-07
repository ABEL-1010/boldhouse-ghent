from pathlib import Path

import pytest

from sentinel.features.tools import filesystem
from sentinel.features.tools.errors import ToolError


def test_read_file_returns_content(workspace: Path) -> None:
    assert "Team notes" in filesystem.read_file(workspace, "notes.md")


def test_read_file_truncates_large_files(workspace: Path) -> None:
    (workspace / "big.txt").write_text("x" * (filesystem.MAX_READ_BYTES + 10))

    text = filesystem.read_file(workspace, "big.txt")

    assert text.startswith("x" * 100)
    assert "[truncated" in text


@pytest.mark.parametrize("path", ["missing.md", "project"])
def test_read_file_rejects_missing_files_and_directories(workspace: Path, path: str) -> None:
    with pytest.raises(ToolError, match="File not found"):
        filesystem.read_file(workspace, path)


def test_write_file_creates_parent_directories(workspace: Path) -> None:
    message = filesystem.write_file(workspace, "reports/week46/summary.md", "# Summary")

    assert message == "Wrote 9 bytes to reports/week46/summary.md."
    assert (workspace / "reports/week46/summary.md").read_text() == "# Summary"


def test_write_file_overwrites_existing_file(workspace: Path) -> None:
    filesystem.write_file(workspace, "notes.md", "replaced")

    assert filesystem.read_file(workspace, "notes.md") == "replaced"


def test_write_file_rejects_directories_and_oversized_content(workspace: Path) -> None:
    with pytest.raises(ToolError, match="is a directory"):
        filesystem.write_file(workspace, "project", "x")
    with pytest.raises(ToolError, match="too large"):
        filesystem.write_file(workspace, "big.txt", "x" * (filesystem.MAX_WRITE_BYTES + 1))


def test_delete_file_removes_file(workspace: Path) -> None:
    assert filesystem.delete_file(workspace, "tmp/scratch.txt") == "Deleted tmp/scratch.txt."
    assert not (workspace / "tmp/scratch.txt").exists()


def test_delete_file_rejects_directories_and_missing_files(workspace: Path) -> None:
    with pytest.raises(ToolError, match="only files can be deleted"):
        filesystem.delete_file(workspace, "tmp")
    with pytest.raises(ToolError, match="File not found"):
        filesystem.delete_file(workspace, "nope.txt")


def test_list_dir_shows_hidden_files_and_marks_directories(workspace: Path) -> None:
    listing = filesystem.list_dir(workspace, ".")

    assert listing.splitlines() == ["Contents of .:", ".env", "notes.md", "project/", "tmp/"]


def test_list_dir_handles_empty_and_missing_directories(workspace: Path) -> None:
    (workspace / "empty").mkdir()

    assert filesystem.list_dir(workspace, "empty") == "Contents of empty:\n(empty)"
    with pytest.raises(ToolError, match="Directory not found"):
        filesystem.list_dir(workspace, "notes.md")
