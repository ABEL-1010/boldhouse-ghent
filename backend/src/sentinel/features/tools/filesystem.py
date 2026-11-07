from pathlib import Path

from sentinel.features.tools.errors import ToolError
from sentinel.features.tools.sandbox import display_path, resolve_in_workspace

MAX_READ_BYTES = 64_000
MAX_WRITE_BYTES = 256_000


def read_file(workspace: Path, path: str) -> str:
    target = resolve_in_workspace(workspace, path)
    if not target.is_file():
        raise ToolError(f"File not found: '{path}'.")
    data = target.read_bytes()
    text = data[:MAX_READ_BYTES].decode("utf-8", errors="replace")
    if len(data) > MAX_READ_BYTES:
        text += f"\n[truncated: file is {len(data)} bytes, showing first {MAX_READ_BYTES}]"
    return text


def write_file(workspace: Path, path: str, content: str) -> str:
    target = resolve_in_workspace(workspace, path)
    data = content.encode("utf-8")
    if len(data) > MAX_WRITE_BYTES:
        raise ToolError(f"Content too large: {len(data)} bytes (max {MAX_WRITE_BYTES}).")
    if target.is_dir():
        raise ToolError(f"'{path}' is a directory.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return f"Wrote {len(data)} bytes to {display_path(workspace, target)}."


def delete_file(workspace: Path, path: str) -> str:
    target = resolve_in_workspace(workspace, path)
    if target.is_dir():
        raise ToolError(f"'{path}' is a directory; only files can be deleted.")
    if not target.is_file():
        raise ToolError(f"File not found: '{path}'.")
    target.unlink()
    return f"Deleted {display_path(workspace, target)}."


def list_dir(workspace: Path, path: str) -> str:
    target = resolve_in_workspace(workspace, path)
    if not target.is_dir():
        raise ToolError(f"Directory not found: '{path}'.")
    entries = sorted(
        f"{entry.name}/" if entry.is_dir() else entry.name for entry in target.iterdir()
    )
    header = f"Contents of {display_path(workspace, target)}:"
    return "\n".join([header, *entries]) if entries else f"{header}\n(empty)"
