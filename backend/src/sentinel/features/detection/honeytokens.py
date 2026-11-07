from pathlib import Path


def load_honeytokens(path: Path) -> frozenset[str]:
    """Read the honeytoken registry: one token per line; blank lines and # comments are ignored.

    A missing file raises instead of returning nothing: silently losing this control is worse
    than failing to start.
    """
    lines = (line.strip() for line in path.read_text(encoding="utf-8").splitlines())
    return frozenset(line for line in lines if line and not line.startswith("#"))
