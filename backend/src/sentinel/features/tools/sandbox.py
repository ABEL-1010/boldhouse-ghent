from pathlib import Path

from sentinel.features.tools.errors import SandboxViolation


def resolve_in_workspace(workspace: Path, path: str) -> Path:
    """Resolve `path` against the workspace and refuse anything that lands outside it.

    `resolve()` collapses `..` and follows symlinks, so traversal, absolute paths and
    symlink escapes all end up outside the root and are rejected.
    """
    if not path.strip() or "\x00" in path:
        raise SandboxViolation("Path must be a non-empty relative path.")
    root = workspace.resolve()
    candidate = (root / path).resolve()
    if not candidate.is_relative_to(root):
        raise SandboxViolation(f"Access denied: '{path}' is outside the workspace.")
    return candidate


def display_path(workspace: Path, resolved: Path) -> str:
    relative = resolved.relative_to(workspace.resolve()).as_posix()
    return relative or "."
