"""Tracked-versus-ignored tally behind the nav header.

The per-directory ``total_files`` / ``total_size`` aggregates are
gitignore-blind by design, so the split cannot be derived by summing
top-level children: ignored files nested under tracked directories
would be counted as tracked. These tests pin that distinction, because
an approximate split presented as exact is worse than no split.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from metabrowser.inventory import InventoryIndex


def _index_for(root: Path) -> InventoryIndex:
    async def _walk() -> InventoryIndex:
        index = InventoryIndex()
        index.start(root)
        await index.wait_until_done(timeout=10.0)
        return index

    return asyncio.run(_walk())


def test_root_summary_splits_tracked_from_ignored(tmp_path: Path) -> None:
    # build_gitignore_check walks up for the enclosing .git dir; a bare
    # marker is enough to make this root behave like a repository.
    (tmp_path / ".git").mkdir()
    (tmp_path / ".gitignore").write_text("build/\n*.log\n")
    (tmp_path / "keep.py").write_text("x" * 100)
    (tmp_path / "notes.md").write_text("y" * 50)
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "out.bin").write_text("z" * 1000)
    (tmp_path / "run.log").write_text("w" * 10)

    index = _index_for(tmp_path)
    try:
        summary = index.root_summary()
    finally:
        index.clear()

    # Dotfiles (.git, .gitignore) are not indexed at all, so the
    # tracked side is just the two ordinary files.
    assert summary["files"] == 2
    assert summary["size"] == 150
    assert summary["ignored_files"] == 2
    assert summary["ignored_size"] == 1010


def test_root_summary_counts_ignored_nested_under_tracked_dirs(tmp_path: Path) -> None:
    """The case that makes summing top-level children wrong: a tracked
    directory holding an ignored file."""

    (tmp_path / ".git").mkdir()
    (tmp_path / ".gitignore").write_text("*.log\n")
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "mod.py").write_text("a" * 20)
    (pkg / "debug.log").write_text("b" * 500)

    index = _index_for(tmp_path)
    try:
        summary = index.root_summary()
        # pkg's own total_files still counts both — a folder's size is
        # its size — which is exactly why the split needs its own pass.
        entry = index.get("pkg")
    finally:
        index.clear()

    assert summary["ignored_files"] == 1
    assert summary["ignored_size"] == 500
    assert entry is not None
    assert entry.total_files == 2


def test_root_summary_is_zero_for_an_empty_root(tmp_path: Path) -> None:
    index = _index_for(tmp_path)
    try:
        summary = index.root_summary()
    finally:
        index.clear()

    assert summary == {"files": 0, "size": 0, "ignored_files": 0, "ignored_size": 0}
