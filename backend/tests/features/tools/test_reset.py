from pathlib import Path

import pytest

from sentinel.features.tools import reset_sandbox


def test_reset_restores_seed_and_clears_outbox(tmp_path: Path) -> None:
    seed, runtime, outbox = tmp_path / "seed", tmp_path / "runtime", tmp_path / "outbox.jsonl"
    (seed / "tmp").mkdir(parents=True)
    (seed / "notes.md").write_text("original")
    (seed / "tmp" / "a.txt").write_text("a")
    reset_sandbox(seed, runtime, outbox)
    (runtime / "notes.md").write_text("changed by agent")
    (runtime / "tmp" / "a.txt").unlink()
    (runtime / "new.md").write_text("new")
    outbox.write_text('{"tool": "send_email"}\n')

    reset_sandbox(seed, runtime, outbox)

    assert (runtime / "notes.md").read_text() == "original"
    assert (runtime / "tmp" / "a.txt").exists()
    assert not (runtime / "new.md").exists()
    assert outbox.read_text() == ""
    assert (seed / "notes.md").read_text() == "original"


def test_reset_refuses_to_use_seed_as_runtime(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    seed.mkdir()

    with pytest.raises(ValueError, match="must differ"):
        reset_sandbox(seed, seed, tmp_path / "outbox.jsonl")
    assert seed.exists()
