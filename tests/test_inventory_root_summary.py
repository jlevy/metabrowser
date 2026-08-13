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

from metabrowser.events import FsEntry
from metabrowser.file_type_filters import FILTER_TYPE_PRESETS
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


def test_extension_tally_keeps_tracked_and_ignored_apart(tmp_path: Path) -> None:
    """The nav's type menu cannot tally from the Quick File catalog,
    which drops gitignored entries: with those rows visible in the
    tree, every count would be short."""

    (tmp_path / ".git").mkdir()
    (tmp_path / ".gitignore").write_text("build/\n")
    (tmp_path / "a.py").write_text("x")
    (tmp_path / "b.py").write_text("x")
    (tmp_path / "c.md").write_text("x")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "vendor.py").write_text("x")
    (tmp_path / "build" / "bundle.js").write_text("x")

    index = _index_for(tmp_path)
    try:
        rows = {row[0]: (row[1], row[2]) for row in index.extension_tally()}
        ordered = [row[0] for row in index.extension_tally()]
    finally:
        index.clear()

    assert rows[".py"] == (2, 1)
    assert rows[".md"] == (1, 0)
    # An extension that exists only under an ignored path is still
    # reported, so the menu can drop it when those rows are hidden
    # rather than pretend it was never there.
    assert rows[".js"] == (0, 1)
    # Ranked by total frequency, then alphabetically for stability.
    assert ordered[0] == ".py"
    assert ordered[1:] == [".js", ".md"]


def test_extension_tally_respects_its_limit(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    for i in range(12):
        (tmp_path / f"f{i}.e{i}").write_text("x")

    index = _index_for(tmp_path)
    try:
        rows = index.extension_tally(limit=5)
    finally:
        index.clear()

    assert len(rows) == 5


def test_file_type_tallies_match_preset_filter_semantics(tmp_path: Path) -> None:
    """Aggregate counts include extensions and whole filenames, split
    by the same ignored-file state as the extension rows."""

    (tmp_path / ".git").mkdir()
    (tmp_path / ".gitignore").write_text("build/\n")
    (tmp_path / "README").write_text("docs without an extension")
    (tmp_path / "guide.md").write_text("docs")
    (tmp_path / "app.py").write_text("code")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "LICENSE").write_text("ignored docs")
    (tmp_path / "build" / "vendor.py").write_text("ignored code")
    (tmp_path / "build" / "records.json").write_text("ignored data")

    index = _index_for(tmp_path)
    try:
        extensions, presets = index.file_type_tallies(
            [(preset["id"], preset["values"]) for preset in FILTER_TYPE_PRESETS]
        )
    finally:
        index.clear()

    extension_rows = {row[0]: (row[1], row[2]) for row in extensions}
    preset_rows = {row[0]: (row[1], row[2]) for row in presets}
    assert extension_rows[".md"] == (1, 0)
    assert extension_rows[".py"] == (1, 1)
    assert preset_rows == {
        "docs": (2, 1),
        "code": (1, 1),
        "data": (0, 1),
    }


def test_navigation_tallies_count_each_recency_window_from_one_snapshot() -> None:
    now_ns = 10_000_000_000_000
    second_ns = 1_000_000_000
    entries = [
        FsEntry.for_observed_file(
            path="live.py",
            parent="",
            name="live.py",
            size=1,
            mtime_ns=now_ns - 10 * second_ns,
        ),
        FsEntry.for_observed_file(
            path="hour-boundary.py",
            parent="",
            name="hour-boundary.py",
            size=1,
            mtime_ns=now_ns - 3_600 * second_ns,
        ),
        FsEntry.for_observed_file(
            path="ignored.log",
            parent="",
            name="ignored.log",
            size=1,
            mtime_ns=now_ns - 1_800 * second_ns,
            gitignored=True,
        ),
        FsEntry.for_observed_file(
            path="older.md",
            parent="",
            name="older.md",
            size=1,
            mtime_ns=now_ns - 7_200 * second_ns,
        ),
    ]

    index = InventoryIndex()
    _summary, _extensions, _presets, recency = index.navigation_tallies(
        [],
        [("live", 90.0), ("1h", 3_600.0), ("24h", 86_400.0)],
        now_ns=now_ns,
        entries=entries,
    )

    assert recency == [
        ["live", 1, 0],
        ["1h", 2, 1],
        ["24h", 3, 1],
    ]


def test_root_summary_is_zero_for_an_empty_root(tmp_path: Path) -> None:
    index = _index_for(tmp_path)
    try:
        summary = index.root_summary()
    finally:
        index.clear()

    assert summary == {"files": 0, "size": 0, "ignored_files": 0, "ignored_size": 0}
