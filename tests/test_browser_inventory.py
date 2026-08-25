"""Unit tests for the Python inventory provider.

Covers the walker correctness invariants and the private PythonInventoryStore
surface:

* Walker yields every file/dir in the tree exactly once (files
  once, dirs twice — placeholder + final).
* Per-dir aggregates (``total_files`` / ``total_size`` /
  ``newest_mtime_ns``) match the reference walk after the dir
  finalizes.
* Post-order property: each parent dir is yielded in its
  finalized form *after* every descendant.
* Safety caps: ``max_files`` truncates correctly; the walker
  still finalizes the partial subtree it did walk.
* PythonInventoryStore.start is idempotent.
* PythonInventoryStore.entries(scope='root-depth-2') filters by depth.
* PythonInventoryStore.invalidate bumps generation along the ancestor
  chain.
* ``_apply_walker_entry`` accepts fresh observations (entries with
  ``write_token=None``) and stamps them with cur_gen on write;
  rejects only opt-in race-safety writes whose captured
  ``WriteToken`` is older than the current generation
  across invalidation races.
* Subscriber overflow requests a bounded resync rather than
  blocking the producer or silently losing updates.

Test convention follows the broader repo pattern: sync tests that
drive coroutines via ``asyncio.run``.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from pathlib import Path
from time import monotonic, sleep
from typing import Any

import metabrowser.inventory_engine.providers.python_inventory as inventory_module
from metabrowser.constants import LOGS_DIR, STATE_DIR
from metabrowser.events import (
    FsChange,
    FsEntry,
    FsUpsert,
    WriteToken,
)
from metabrowser.fs_paths import derive_ext as _ext_of
from metabrowser.fs_paths import is_visible, is_visible_segment
from metabrowser.inventory_engine.contract import (
    ChangeBatch,
    ChangeCursor,
    DiagnosticsQuery,
    InventoryConfig,
    InventoryEntry,
    ReadRequest,
)
from metabrowser.inventory_engine.providers.python_inventory import (
    _PythonInventoryStore as PythonInventoryStore,
)
from metabrowser.inventory_engine.providers.python_inventory import (
    walk_tree,
)
from metabrowser.walker import depth_of as _depth_of


class _SlowValuesEntries(dict[str, FsEntry]):
    def values(self) -> Any:
        sleep(0.1)
        return super().values()


class _ScanTrackingEntries(dict[str, FsEntry]):
    full_scan_requested = False

    def keys(self) -> Any:
        self.full_scan_requested = True
        return super().keys()


def _apply_entries(inv: PythonInventoryStore, entries: list[FsEntry]) -> int:
    """Drive the provider's retained-state path without a second public writer API."""

    stored = [
        applied for entry in entries if (applied := inv._store_walker_entry(entry)) is not None
    ]
    if stored:
        inv._emit(FsChange(ops=tuple(FsUpsert(entry=entry) for entry in stored)))
    return len(stored)


async def _checkpoint(inv: PythonInventoryStore) -> ChangeCursor:
    result = await inv.read(ReadRequest(queries=(DiagnosticsQuery(query_id="test-checkpoint"),)))
    return result.cursor


async def _changes_since(
    inv: PythonInventoryStore,
    after: ChangeCursor,
) -> list[ChangeBatch]:
    """Replay every provider invalidation through the current boundary."""

    current = await _checkpoint(inv)
    if current == after:
        return []
    stream = inv.changes(after=after)
    batches: list[ChangeBatch] = []
    try:
        while not batches or batches[-1].cursor.sequence < current.sequence:
            batches.append(await asyncio.wait_for(anext(stream), timeout=1.0))
    finally:
        await stream.aclose()
    return batches


def _build_tree(root: Path) -> None:
    """Make a small repeatable fixture under *root*::

    root/
      file_a.log     50 bytes
      sub1/
        file_b.log   100 bytes
        sub1a/
          file_c.log 25 bytes
      sub2/
        file_d.log   75 bytes
    """
    (root / "file_a.log").write_bytes(b"a" * 50)
    (root / "sub1").mkdir()
    (root / "sub1" / "file_b.log").write_bytes(b"b" * 100)
    (root / "sub1" / "sub1a").mkdir()
    (root / "sub1" / "sub1a" / "file_c.log").write_bytes(b"c" * 25)
    (root / "sub2").mkdir()
    (root / "sub2" / "file_d.log").write_bytes(b"d" * 75)


async def _collect(
    root: Path,
    *,
    max_depth: int = 20,
    max_files: int = 20_000,
) -> list[InventoryEntry]:
    return [
        e
        async for e in walk_tree(
            root,
            max_depth=max_depth,
            max_files=max_files,
        )
    ]


# ── walk_tree ──────────────────────────────────────────────────


def test_walk_tree_yields_every_path_at_least_once(tmp_path: Path) -> None:
    _build_tree(tmp_path)
    yielded = asyncio.run(_collect(tmp_path))
    paths = [e.path for e in yielded]
    # Files yielded once each; dirs yielded twice (placeholder + final).
    assert paths.count("file_a.log") == 1
    assert paths.count("sub1/file_b.log") == 1
    assert paths.count("sub1/sub1a/file_c.log") == 1
    assert paths.count("sub2/file_d.log") == 1
    assert paths.count("sub1") == 2
    assert paths.count("sub1/sub1a") == 2
    assert paths.count("sub2") == 2
    assert paths.count("") == 2  # root


def test_walk_tree_post_order_finalize(tmp_path: Path) -> None:
    """Each dir's finalized form (``total_files`` populated) is
    yielded AFTER every descendant has been yielded."""
    _build_tree(tmp_path)
    yielded = asyncio.run(_collect(tmp_path))

    # Index of each dir's finalized yield (the second occurrence
    # — the one with total_files populated).
    final_idx: dict[str, int] = {}
    for i, e in enumerate(yielded):
        if e.type == "dir" and e.total_files is not None:
            final_idx.setdefault(e.path, i)

    last_idx: dict[str, int] = {}
    for i, e in enumerate(yielded):
        last_idx[e.path] = i

    for dir_path, dir_idx in final_idx.items():
        for other_path, other_idx in last_idx.items():
            if other_path == dir_path:
                continue
            is_descendant = other_path.startswith(dir_path + "/") or (
                dir_path == "" and other_path != ""
            )
            if is_descendant:
                assert other_idx < dir_idx, (
                    f"{other_path!r} (last yield idx {other_idx}) is a descendant of "
                    f"{dir_path!r} (final yield idx {dir_idx}) but yielded after"
                )


def test_walk_tree_aggregates_match_reference(tmp_path: Path) -> None:
    """Finalized per-dir aggregates equal a straightforward
    reference walk over the same tree."""
    _build_tree(tmp_path)
    yielded = asyncio.run(_collect(tmp_path))
    final_dirs: dict[str, InventoryEntry] = {}
    for e in yielded:
        if e.type == "dir" and e.total_files is not None:
            final_dirs[e.path] = e

    def _ref(p: Path) -> tuple[int, int]:
        files = 0
        size = 0
        for child in p.rglob("*"):
            if child.is_file():
                files += 1
                size += child.stat().st_size
        return files, size

    for rel, entry in final_dirs.items():
        abs_path = tmp_path / rel if rel else tmp_path
        ref_files, ref_size = _ref(abs_path)
        assert entry.total_files == ref_files
        assert entry.total_size == ref_size


def test_walk_tree_max_files_truncates_and_still_finalizes(tmp_path: Path) -> None:
    _build_tree(tmp_path)
    yielded = asyncio.run(_collect(tmp_path, max_files=2, max_depth=10))
    file_yields = [e for e in yielded if e.type == "file"]
    assert len(file_yields) == 2  # cap respected
    final_dirs = [e for e in yielded if e.type == "dir" and e.total_files is not None]
    assert any(e.path == "" for e in final_dirs)  # root still finalized


def test_walk_tree_max_depth_zero_yields_nothing(tmp_path: Path) -> None:
    _build_tree(tmp_path)
    yielded = asyncio.run(_collect(tmp_path, max_depth=0))
    assert yielded == []


def test_walk_tree_skips_dotfiles_except_logs_state(tmp_path: Path) -> None:
    """Visibility filter matches the existing tree.py rule."""
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / "x").write_text("x")
    (tmp_path / ".logs").mkdir()
    (tmp_path / ".logs" / "a.log").write_text("a")
    (tmp_path / ".state").mkdir()
    (tmp_path / ".state" / "s.json").write_text("{}")
    (tmp_path / "visible.txt").write_text("v")

    yielded = asyncio.run(_collect(tmp_path))
    paths = {e.path for e in yielded}
    assert ".hidden" not in paths
    assert ".logs" in paths
    assert ".state" in paths
    assert "visible.txt" in paths


def test_walk_tree_discovers_strictly_in_level_order(tmp_path: Path) -> None:
    """Every directory at depth N is scanned before any at depth N+1.

    This is what makes the nav tree usable during a crawl: the shallow
    layers a reader sees and expands first are complete early, instead of
    the walker following one branch to the bottom before looking at its
    siblings. A wide, deep fixture makes the difference observable — a
    depth-first walker would emit ``wide0/d0/d0`` before ``wide9``.
    """

    for top in range(10):
        branch = tmp_path / f"wide{top}"
        (branch / "d0" / "d0").mkdir(parents=True)
        (branch / "d0" / "d0" / "leaf.txt").write_bytes(b"x")

    entries = asyncio.run(_collect(tmp_path))
    # Placeholders are emitted at discovery time; finalized dir entries come
    # later by design (post-order), so order is judged on first sighting.
    first_seen: list[str] = []
    for entry in entries:
        if entry.type == "dir" and entry.path not in first_seen:
            first_seen.append(entry.path)

    depths = [_depth_of(path) for path in first_seen]
    assert depths == sorted(depths), f"not level-order: {first_seen}"
    # And the whole first level really does precede the second.
    assert set(first_seen[1:11]) == {f"wide{i}" for i in range(10)}


# ── path helpers ─────────────────────────────────────────────


def test_depth_of_root_and_subpaths() -> None:
    assert _depth_of("") == 0
    assert _depth_of("a") == 1
    assert _depth_of("a/b") == 2
    assert _depth_of("a/b/c") == 3


def test_ext_of_bounded_compound_tail() -> None:
    assert _ext_of("foo.runbook.md") == ".runbook.md"
    assert _ext_of("archive.tar.gz") == ".tar.gz"
    assert _ext_of("bundle.js.map") == ".js.map"
    assert _ext_of("bundle.map") == ".map"
    assert _ext_of("bundle.umd.min.js.map") == ".js.map"
    assert _ext_of("types.d.ts.map") == ".ts.map"
    assert _ext_of("bundle.umd.min.js") == ".min.js"
    assert _ext_of("plain.txt") == ".txt"
    assert _ext_of("Makefile") == ""
    assert _ext_of(".dotfile") == ""
    assert _ext_of("Foo.With.Dots.Txt") == ".dots.txt"


def test_fs_entry_factory_uses_bounded_compound_ext_for_file_observations() -> None:
    """Both the walker (boot scan / rewalk_subtree) and the watcher
    (file-event handler) construct entries via
    :meth:`FsEntry.for_observed_file` / :meth:`FsEntry.for_stat`. The
    factory derives ``ext`` through :func:`fs_paths.derive_ext`, so a
    file like ``foo.runbook.md`` gets ``.runbook.md`` regardless of
    which producer observed it. Pre-fix, the watcher used a simple
    last-dot suffix and silently miscategorized compound suffixes."""

    entry = FsEntry.for_observed_file(
        path="docs/foo.runbook.md",
        parent="docs",
        name="foo.runbook.md",
        size=42,
        mtime_ns=1234,
    )
    assert entry.ext == ".runbook.md"
    assert entry.type == "file"
    assert entry.kind == "file"
    assert entry.write_token is None
    # And the dir factory leaves ext empty + write_token unstamped.
    dir_entry = FsEntry.for_observed_dir(path="docs", parent="", name="docs")
    assert dir_entry.ext == ""
    assert dir_entry.type == "dir"
    assert dir_entry.write_token is None


def test_fs_entry_factory_carries_forward_active_and_labels() -> None:
    """The watcher's modify path passes ``existing`` so user-visible
    state (run-state, plugin badges) survives an edit. A regression
    that drops this carry-forward would silently clear active markers
    on every save."""

    existing = FsEntry(
        path="run.log",
        parent="",
        name="run.log",
        type="file",
        ext=".log",
        kind="file",
        size=100,
        mtime_ns=1000,
        mtime_hash="",
        active=True,
        labels=(("status", "running"), ("plugin", "example")),
    )
    next_entry = FsEntry.for_observed_file(
        path="run.log",
        parent="",
        name="run.log",
        size=200,
        mtime_ns=2000,
        existing=existing,
    )
    assert next_entry.active is True
    assert next_entry.labels == (("status", "running"), ("plugin", "example"))
    # And without existing, the carry-forward is empty.
    fresh = FsEntry.for_observed_file(
        path="run.log",
        parent="",
        name="run.log",
        size=200,
        mtime_ns=2000,
    )
    assert fresh.active is False
    assert fresh.labels == ()


def test_visibility_helpers_share_one_canonical_filter() -> None:
    """The walker filters per-name in ``_scandir_visible`` and the
    watcher filters per-segment in ``_emit_for_path``. Both must use
    the same definition of "visible" — diverging on the
    ``.logs``/``.state`` allowlist would let a watcher event slip
    past or block a legitimate walker scan."""

    # Per-name: ordinary names allowed; dotfiles blocked; allowlist passes.
    assert is_visible("docs")
    assert is_visible("README.md")
    assert not is_visible(".hidden")
    assert not is_visible(".cache")
    assert is_visible(LOGS_DIR)
    assert is_visible(STATE_DIR)
    # Per-segment: every component checked.
    assert is_visible_segment("")
    assert is_visible_segment("a/b/c")
    assert not is_visible_segment("a/.hidden/b")
    assert is_visible_segment(f"a/{LOGS_DIR}/c")
    # The two helpers agree on every individual segment.
    assert is_visible_segment("docs/README.md") == all(is_visible(s) for s in ["docs", "README.md"])


# Python inventory handle


async def _drive_inventory(tmp_path: Path) -> PythonInventoryStore:
    """Spin up a PythonInventoryStore against *tmp_path* and wait for
    completion. Returns the index for assertions."""
    inv = PythonInventoryStore()
    inv.start(tmp_path)
    await inv.wait_until_done(timeout=5.0)
    return inv


def test_inventory_start_is_idempotent(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    async def _run() -> tuple[bool, str]:
        inv = PythonInventoryStore()
        task1 = inv.start(tmp_path)
        task2 = inv.start(tmp_path)
        await inv.wait_until_done(timeout=5.0)
        return task1 is task2, inv.status()

    same, status = asyncio.run(_run())
    assert same is True
    assert status in ("done", "truncated")


def test_inventory_entries_root_depth_2_filter(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    async def _run() -> tuple[set[str], set[str]]:
        inv = await _drive_inventory(tmp_path)
        return (
            {e.path for e in inv.entries(scope="root-depth-2")},
            {e.path for e in inv.entries(scope="all-known")},
        )

    shallow, deep = asyncio.run(_run())
    assert "sub1/sub1a" in deep
    assert "sub1/sub1a/file_c.log" in deep
    assert "sub1/file_b.log" in shallow
    assert "sub1/sub1a/file_c.log" not in shallow


def test_inventory_files_indexed_counter(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    async def _run() -> int:
        inv = await _drive_inventory(tmp_path)
        return inv.files_indexed()

    assert asyncio.run(_run()) == 4


def test_inventory_direct_child_index_tracks_stores_and_removals() -> None:
    inv = PythonInventoryStore()
    directory = FsEntry(
        path="runs",
        parent="",
        name="runs",
        type="dir",
        ext="",
        kind="directory",
        size=0,
        mtime_ns=0,
        mtime_hash="",
        active=False,
    )
    child = FsEntry(
        path="runs/event.jsonl",
        parent="runs",
        name="event.jsonl",
        type="file",
        ext="jsonl",
        kind="file",
        size=10,
        mtime_ns=0,
        mtime_hash="",
        active=False,
    )

    assert _apply_entries(inv, [directory, child]) == 2
    assert inv.has_direct_child("") is True
    assert inv.has_direct_child("runs") is True

    inv.remove("runs/event.jsonl")

    assert inv.has_direct_child("") is True
    assert inv.has_direct_child("runs") is False


def test_live_empty_state_tracks_subtree_leaves_separately_from_file_totals() -> None:
    inv = PythonInventoryStore()
    root = FsEntry(
        path="",
        parent="",
        name="root",
        type="dir",
        ext="",
        kind="dir",
        size=0,
        mtime_ns=0,
        mtime_hash="",
        active=False,
        total_files=0,
        total_size=0,
        newest_mtime_ns=0,
    )
    assert _apply_entries(inv, [root]) == 1
    indexed_root = inv.get("")
    assert indexed_root is not None
    assert indexed_root.empty is True

    inv.apply_live_entry(
        FsEntry(
            path="nested",
            parent="",
            name="nested",
            type="dir",
            ext="",
            kind="dir",
            size=0,
            mtime_ns=0,
            mtime_hash="",
            active=False,
            total_files=0,
            total_size=0,
            newest_mtime_ns=0,
        )
    )
    with_empty_subfolder = inv.get("")
    assert with_empty_subfolder is not None
    assert with_empty_subfolder.total_files == 0
    assert with_empty_subfolder.empty is True

    inv.apply_live_entry(
        FsEntry.for_observed_symlink(
            path="nested/shortcut",
            parent="nested",
            name="shortcut",
            size=8,
            mtime_ns=1,
        )
    )
    with_link = inv.get("")
    assert with_link is not None
    assert with_link.total_files == 0
    assert with_link.empty is False
    nested_with_link = inv.get("nested")
    assert nested_with_link is not None
    assert nested_with_link.empty is False

    inv.remove("nested/shortcut")
    without_link = inv.get("")
    assert without_link is not None
    assert without_link.total_files == 0
    assert without_link.empty is True
    nested_without_link = inv.get("nested")
    assert nested_without_link is not None
    assert nested_without_link.empty is True


def test_live_file_changes_refresh_root_aggregates(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    async def _run() -> tuple[FsEntry, FsEntry, list[ChangeBatch]]:
        inv = await _drive_inventory(tmp_path)
        before = inv.get("")
        assert before is not None
        cursor = await _checkpoint(inv)
        live = FsEntry(
            path="live.txt",
            parent="",
            name="live.txt",
            type="file",
            ext="txt",
            kind="file",
            size=53,
            mtime_ns=before.newest_mtime_ns + 1 if before.newest_mtime_ns else 1,
            mtime_hash="",
            active=False,
        )
        inv.apply_live_entry(live)
        after_insert = inv.get("")
        assert after_insert is not None
        inv.remove("live.txt")
        after_remove = inv.get("")
        assert after_remove is not None
        changes = await _changes_since(inv, cursor)
        return after_insert, after_remove, changes

    after_insert, after_remove, changes = asyncio.run(_run())
    assert (after_insert.total_files, after_insert.total_size) == (5, 303)
    assert (after_insert.unignored_files, after_insert.unignored_size) == (5, 303)
    assert (after_remove.total_files, after_remove.total_size) == (4, 250)
    assert (after_remove.unignored_files, after_remove.unignored_size) == (4, 250)
    assert (after_remove.newest_mtime_ns or 0) < (after_insert.newest_mtime_ns or 0)
    for change in changes:
        assert "" in change.dirty_paths


def test_live_ignore_state_flip_updates_only_unignored_ancestor_totals(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    async def _run() -> tuple[FsEntry, FsEntry, FsEntry]:
        inv = await _drive_inventory(tmp_path)
        file_entry = inv.get("file_a.log")
        assert file_entry is not None
        before = inv.get("")
        assert before is not None
        inv.apply_live_entry(replace(file_entry, gitignored=True))
        ignored = inv.get("")
        assert ignored is not None
        inv.apply_live_entry(replace(file_entry, gitignored=False))
        restored = inv.get("")
        assert restored is not None
        return before, ignored, restored

    before, ignored, restored = asyncio.run(_run())
    assert (ignored.total_files, ignored.total_size) == (before.total_files, before.total_size)
    assert ignored.unignored_files == (before.unignored_files or 0) - 1
    assert ignored.unignored_size == (before.unignored_size or 0) - len(b"a" * 50)
    assert (restored.unignored_files, restored.unignored_size) == (
        before.unignored_files,
        before.unignored_size,
    )


def test_live_change_during_boot_invalidates_stale_directory_finalization(
    tmp_path: Path, monkeypatch
) -> None:
    walker_paused = asyncio.Event()
    resume_walker = asyncio.Event()
    root_placeholder = FsEntry.for_observed_dir(path="", parent="", name=tmp_path.name)
    old_file = FsEntry(
        path="old.txt",
        parent="",
        name="old.txt",
        type="file",
        ext="txt",
        kind="file",
        size=10,
        mtime_ns=10,
        mtime_hash="",
        active=False,
    )

    async def _walk(*_args, **_kwargs):
        yield root_placeholder
        yield old_file
        walker_paused.set()
        await resume_walker.wait()
        yield replace(
            root_placeholder,
            total_files=1,
            total_size=10,
            newest_mtime_ns=10,
            mtime_ns=10,
        )

    monkeypatch.setattr(inventory_module, "walk_tree", _walk)

    async def _run() -> tuple[int | None, int | None]:
        inv = PythonInventoryStore()
        inv.start(tmp_path)
        await walker_paused.wait()
        inv.invalidate("live.txt")
        inv.apply_live_entry(
            FsEntry(
                path="live.txt",
                parent="",
                name="live.txt",
                type="file",
                ext="txt",
                kind="file",
                size=20,
                mtime_ns=20,
                mtime_hash="",
                active=False,
            )
        )
        resume_walker.set()
        await inv.wait_until_done(timeout=2.0)
        root = inv.get("")
        assert root is not None
        return root.total_files, root.total_size

    assert asyncio.run(_run()) == (2, 30)


def test_unchanged_mtime_upserts_do_not_grow_child_heaps(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    async def _run() -> tuple[int, int]:
        inv = await _drive_inventory(tmp_path)
        entry = inv.get("file_a.log")
        assert entry is not None
        before = sum(len(heap) for heap in inv._child_mtime_heaps.values())
        for index in range(100):
            _apply_entries(
                inv, [replace(entry, active=bool(index % 2), labels=(("tick", str(index)),))]
            )
        after = sum(len(heap) for heap in inv._child_mtime_heaps.values())
        return before, after

    before, after = asyncio.run(_run())
    assert after == before


def test_changing_mtime_upserts_periodically_compact_child_heaps(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    async def _run() -> int:
        inv = await _drive_inventory(tmp_path)
        entry = inv.get("file_a.log")
        assert entry is not None
        for index in range(200):
            _apply_entries(inv, [replace(entry, mtime_ns=entry.mtime_ns + index + 1)])
        return len(inv._child_mtime_heaps[""])

    heap_size = asyncio.run(_run())
    assert heap_size <= 64


def test_inventory_invalidate_bumps_ancestor_generations(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    async def _run() -> dict[str, int]:
        inv = await _drive_inventory(tmp_path)
        inv.invalidate("sub1/sub1a")
        return dict(inv._generation)

    gens = asyncio.run(_run())
    assert gens.get("", 0) >= 1
    assert gens.get("sub1", 0) >= 1
    assert gens.get("sub1/sub1a", 0) >= 1
    # Sibling NOT on the chain unchanged.
    assert gens.get("sub2", 0) == 0


def test_inventory_apply_walker_entry_drops_stale_writes() -> None:
    """``_apply_walker_entry`` rejects entries whose captured
    ``write_token`` is older than the current generation. The
    race-safe invalidation contract — the opt-in path where a
    producer called :meth:`capture_write_token` before its
    observation and the counter bumped before the write landed."""

    async def _run() -> bool:
        inv = PythonInventoryStore()
        inv._generation["sub/x"] = 5
        stale = FsEntry(
            path="sub/x",
            parent="sub",
            name="x",
            type="file",
            ext="",
            kind="file",
            size=10,
            mtime_ns=0,
            mtime_hash="",
            active=False,
            write_token=WriteToken(2),
        )
        inv._apply_walker_entry(stale)
        return "sub/x" in inv._entries

    assert asyncio.run(_run()) is False


def test_inventory_stale_walker_write_is_debug_diagnostic() -> None:
    """Expected generation races must not surface as operator warnings."""

    class _RecordHandler(logging.Handler):
        def __init__(self) -> None:
            super().__init__(level=logging.DEBUG)
            self.records: list[logging.LogRecord] = []

        def emit(self, record: logging.LogRecord) -> None:
            self.records.append(record)

    logger = logging.getLogger("metabrowser.inventory_engine.providers.python_inventory")
    original_level = logger.level
    handler = _RecordHandler()
    logger.addHandler(handler)
    try:
        logger.setLevel(logging.DEBUG)
        inv = PythonInventoryStore()
        inv._generation["sub/x"] = 5
        inv._apply_walker_entry(
            FsEntry(
                path="sub/x",
                parent="sub",
                name="x",
                type="file",
                ext="",
                kind="file",
                size=10,
                mtime_ns=0,
                mtime_hash="",
                active=False,
                write_token=WriteToken(2),
            )
        )
    finally:
        logger.setLevel(original_level)
        logger.removeHandler(handler)

    records = [
        record for record in handler.records if "dropped stale walker write" in record.getMessage()
    ]
    assert len(records) == 1
    assert records[0].levelno == logging.DEBUG


def test_inventory_apply_walker_entry_accepts_fresh_observation_after_invalidate() -> None:
    """``write_token=None`` is the 'freshly observed' sentinel — the
    producer (walker / watcher / active_tracker) read the filesystem
    right now and ``_store_walker_entry`` stamps the entry with the
    current generation on write. Prior
    to the type-level fix, ``generation`` was an int field defaulting
    to 0, and every producer's default-stamped entry was dropped as
    stale after any invalidate (7,659 dropped writes / 0 live updates
    in the field repro)."""

    inv = PythonInventoryStore()
    # Simulate a prior invalidate on this path (e.g. caused by an
    # inventory.remove() earlier in the session).
    inv._generation["sub/x"] = 3
    fresh = FsEntry(
        path="sub/x",
        parent="sub",
        name="x",
        type="file",
        ext="",
        kind="file",
        size=42,
        mtime_ns=1234,
        mtime_hash="",
        active=False,
        # write_token=None — the dataclass default; producer didn't stamp.
    )
    inv._apply_walker_entry(fresh)
    stored = inv._entries.get("sub/x")
    assert stored is not None, "fresh observation must be accepted after invalidate"
    # The entry was stamped with the current generation on write.
    assert stored.write_token == WriteToken(3)
    assert stored.size == 42


def test_inventory_apply_walker_entry_accepts_caller_stamped_current_gen() -> None:
    """A producer that opts into race-safety via
    :meth:`capture_write_token` before its observation gets the
    entry through when the captured generation is still current.
    This is the path that ``_repair_pending_dir_aggregates`` uses
    to restamp finalized dir aggregates."""

    inv = PythonInventoryStore()
    inv._generation["sub/x"] = 4
    stamped = FsEntry(
        path="sub/x",
        parent="sub",
        name="x",
        type="file",
        ext="",
        kind="file",
        size=1,
        mtime_ns=0,
        mtime_hash="",
        active=False,
        write_token=inv.capture_write_token("sub/x"),
    )
    inv._apply_walker_entry(stamped)
    assert inv._entries.get("sub/x") is not None


def test_inventory_rewalk_subtree_lands_after_prior_invalidate(tmp_path: Path) -> None:
    """End-to-end: build a subtree, invalidate an ancestor (as
    happens whenever an earlier ``remove()`` ran), call
    ``rewalk_subtree``, and assert the enumerated entries are NOT
    silently dropped. Pre-fix this produced 0 entries in
    ``inv._entries`` for the subtree because every walker entry
    arrived with the dataclass-default ``generation=0`` and lost the
    ``0 < cur_gen`` check."""

    _build_tree(tmp_path)

    async def _run() -> dict[str, FsEntry]:
        inv = await _drive_inventory(tmp_path)
        # Drop the subtree we're about to rewalk so we can prove
        # rewalk re-populates it (and to mirror the field repro
        # shape: remove() bumps the generation as a side effect).
        inv.remove("sub1")
        assert inv._generation.get("sub1", 0) >= 1, "remove() must bump generation"
        assert "sub1" not in inv._entries
        # The bug pre-fix: every walker entry arrived unstamped and
        # was dropped against cur_gen>=1. With the type-level fix
        # (write_token=None on fresh observations), the entries land
        # and the inventory stamps them with the current generation.
        (tmp_path / "sub1").mkdir(exist_ok=True)
        (tmp_path / "sub1" / "file_b.log").write_bytes(b"b" * 100)
        (tmp_path / "sub1" / "sub1a").mkdir(exist_ok=True)
        (tmp_path / "sub1" / "sub1a" / "file_c.log").write_bytes(b"c" * 25)
        await inv.rewalk_subtree("sub1")
        return dict(inv._entries)

    entries = asyncio.run(_run())
    # Every fresh observation under sub1 should have landed.
    assert "sub1" in entries
    assert "sub1/file_b.log" in entries
    assert "sub1/sub1a" in entries
    assert "sub1/sub1a/file_c.log" in entries
    # And each one carries the post-invalidate generation, NOT None.
    for path in ("sub1", "sub1/file_b.log", "sub1/sub1a/file_c.log"):
        token = entries[path].write_token
        assert token is not None and token.generation >= 1, (
            f"entry {path!r} must be stamped with cur_gen, got write_token={token}"
        )


def test_inventory_repair_pending_dir_aggregates_after_stale_finalize() -> None:
    """An uncapped boot walk can lose a final dir aggregate if a
    watcher invalidates that ancestor while the walk is running.
    Completion repairs those placeholders from known file entries
    so ``status=done`` never leaves the tree showing pending
    tallies."""

    async def _run() -> tuple[PythonInventoryStore, tuple[str, ...]]:
        inv = PythonInventoryStore()
        inv._generation["runs"] = 1
        root = FsEntry.for_observed_dir(path="", parent="", name="root")
        runs = FsEntry.for_observed_dir(path="runs", parent="", name="runs")
        child = FsEntry(
            path="runs/a.txt",
            parent="runs",
            name="a.txt",
            type="file",
            ext=".txt",
            kind="text",
            size=11,
            mtime_ns=123,
            mtime_hash="",
            active=False,
        )
        assert _apply_entries(inv, [root, runs, child]) == 3
        cursor = await _checkpoint(inv)
        inv._repair_pending_dir_aggregates()
        changes = await _changes_since(inv, cursor)
        inv.apply_live_entry(
            FsEntry(
                path="older.txt",
                parent="",
                name="older.txt",
                type="file",
                ext=".txt",
                kind="text",
                size=1,
                mtime_ns=1,
                mtime_hash="",
                active=False,
            )
        )
        return inv, changes[-1].dirty_paths

    inv, paths = asyncio.run(_run())
    assert inv._entries["runs"].total_files == 1
    assert inv._entries["runs"].total_size == 11
    assert inv._entries["runs"].newest_mtime_ns == 123
    assert inv._entries[""].total_files == 2
    assert {"", "runs"} <= set(paths)
    assert inv._entries[""].newest_mtime_ns == 123


def test_inventory_pending_repair_does_not_scan_all_entries_on_event_loop() -> None:
    inv = PythonInventoryStore()
    root = FsEntry.for_observed_dir(path="", parent="", name="root")
    child = FsEntry(
        path="event.jsonl",
        parent="",
        name="event.jsonl",
        type="file",
        ext=".jsonl",
        kind="unknown-jsonl",
        size=10,
        mtime_ns=123,
        mtime_hash="",
        active=False,
    )
    assert _apply_entries(inv, [root, child]) == 2
    inv._entries = _SlowValuesEntries(inv._entries)

    async def _run() -> float:
        ticked_at = 0.0

        async def _tick() -> None:
            nonlocal ticked_at
            await asyncio.sleep(0.01)
            ticked_at = monotonic()

        started_at = monotonic()
        ticker = asyncio.create_task(_tick())
        inv._repair_pending_dir_aggregates()
        await ticker
        return ticked_at - started_at

    assert asyncio.run(_run()) < 0.05


def test_inventory_pending_repair_failure_surfaces_failed_status(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    async def _run() -> str:
        inv = PythonInventoryStore()

        def _fail_repair() -> None:
            raise RuntimeError("repair failed")

        inv._repair_pending_dir_aggregates = _fail_repair
        inv.start(tmp_path)
        await inv.wait_until_done(timeout=5.0)
        return inv.status()

    assert asyncio.run(_run()) == "failed"


def test_inventory_walker_crash_surfaces_failed_status(tmp_path: Path) -> None:
    """A walker crash must produce ``status() == 'failed'``, not
    ``'idle'``. Production code (capability probe, lifespan, SSE bus)
    can then distinguish a broken inventory from one that's never
    been started. Log-and-continue is not handling — every error log
    needs a control-flow signal."""

    _build_tree(tmp_path)

    async def _run() -> str:
        inv = PythonInventoryStore()

        # Force the walker coroutine to raise after the inventory has
        # been started by monkey-patching the internal apply call.
        original = inv._store_walker_entry

        def _explode(entry: FsEntry) -> FsEntry | None:
            raise RuntimeError("simulated walker crash")

        inv._store_walker_entry = _explode  # type: ignore[method-assign]
        inv.start(tmp_path)
        try:
            await inv.wait_until_done(timeout=5.0)
        finally:
            inv._store_walker_entry = original  # type: ignore[method-assign]
        return inv.status()

    assert asyncio.run(_run()) == "failed"


def test_inventory_change_stream_replays_walker_dirty_paths(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    async def _run() -> set[str]:
        inv = PythonInventoryStore()
        cursor = await _checkpoint(inv)
        stream = inv.changes(after=cursor)
        first = asyncio.ensure_future(anext(stream))
        await asyncio.sleep(0)
        inv.start(tmp_path)
        await inv.wait_until_done(timeout=5.0)
        current = await _checkpoint(inv)
        batches = [await first]
        while batches[-1].cursor.sequence < current.sequence:
            batches.append(await asyncio.wait_for(anext(stream), timeout=1.0))
        await stream.aclose()
        return {path for batch in batches for path in batch.dirty_paths}

    seen = asyncio.run(_run())
    assert "file_a.log" in seen
    assert "sub1" in seen
    assert "sub1/file_b.log" in seen


def test_inventory_slow_change_consumer_gets_bounded_reset() -> None:
    async def _run() -> ChangeBatch:
        inv = PythonInventoryStore(config=InventoryConfig(change_queue_size=1))
        cursor = await _checkpoint(inv)
        stream = inv.changes(after=cursor)
        first = asyncio.ensure_future(anext(stream))
        await asyncio.sleep(0)
        for index in range(3):
            inv.apply_live_entry(
                FsEntry.for_observed_file(
                    path=f"{index}.txt",
                    parent="",
                    name=f"{index}.txt",
                    size=1,
                    mtime_ns=index + 1,
                )
            )
        reset = await first
        await stream.aclose()
        return reset

    assert asyncio.run(_run()).reset


def test_inventory_clear_records_provider_reset(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    async def _run() -> ChangeBatch:
        inv = PythonInventoryStore()
        inv.start(tmp_path)
        await inv.wait_until_done(timeout=5.0)
        cursor = await _checkpoint(inv)
        inv.clear()
        return (await _changes_since(inv, cursor))[-1]

    assert asyncio.run(_run()).reset


def test_concurrent_close_callers_join_the_same_shutdown() -> None:
    async def _run() -> None:
        inventory = PythonInventoryStore()
        cancellation_seen = asyncio.Event()
        release = asyncio.Event()

        async def stubborn_walker() -> None:
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancellation_seen.set()
                await release.wait()

        inventory._walker_task = asyncio.create_task(stubborn_walker())
        first = asyncio.create_task(inventory.close())
        await asyncio.wait_for(cancellation_seen.wait(), timeout=1)
        second = asyncio.create_task(inventory.close())
        await asyncio.sleep(0)
        assert not first.done()
        assert not second.done()

        release.set()
        await asyncio.gather(first, second)

    asyncio.run(_run())


# ── rewalk_subtree ────────────────────────────────────────────


def test_rewalk_subtree_ingests_a_newly_created_directory(tmp_path: Path) -> None:
    """A directory created on disk after the boot walker finishes
    is invisible to the inventory until the watcher's dir-create
    branch calls ``rewalk_subtree``. This test exercises that path
    directly: build a tree, run the walker, then mkdir + populate
    a new subtree and call ``rewalk_subtree``. Every new entry must
    land in ``_entries`` and provider invalidations must name the changed
    subtree."""

    _build_tree(tmp_path)

    async def _run() -> tuple[set[str], list[ChangeBatch]]:
        inv = await _drive_inventory(tmp_path)
        cursor = await _checkpoint(inv)
        # New subtree on disk:
        new_dir = tmp_path / "newdir"
        new_dir.mkdir()
        (new_dir / "x.txt").write_bytes(b"x" * 10)
        (new_dir / "nested").mkdir()
        (new_dir / "nested" / "y.txt").write_bytes(b"y" * 20)
        await inv.rewalk_subtree("newdir")
        paths_now = {p for p in inv._entries if p.startswith("newdir")}
        return paths_now, await _changes_since(inv, cursor)

    paths, events = asyncio.run(_run())
    assert "newdir" in paths
    assert "newdir/x.txt" in paths
    assert "newdir/nested" in paths
    assert "newdir/nested/y.txt" in paths
    assert any(path.startswith("newdir") for batch in events for path in batch.dirty_paths)


def test_rewalk_subtree_refuses_root_and_missing_paths(tmp_path: Path) -> None:
    """``rewalk_subtree('')`` is a no-op (it would race the boot
    walker), and pointing at a non-existent subpath is also a
    no-op (don't blow up)."""

    _build_tree(tmp_path)

    async def _run() -> tuple[int, int]:
        inv = await _drive_inventory(tmp_path)
        before = len(inv._entries)
        await inv.rewalk_subtree("")  # refused
        await inv.rewalk_subtree("does-not-exist")  # silent no-op
        after = len(inv._entries)
        return before, after

    before, after = asyncio.run(_run())
    assert before == after


def test_rewalk_subtree_replaces_file_without_double_counting_root(tmp_path: Path) -> None:
    replacement = tmp_path / "replacement"
    replacement.write_bytes(b"old-file")

    async def _run() -> tuple[FsEntry, FsEntry, FsEntry]:
        inv = await _drive_inventory(tmp_path)
        root_before = inv.get("")
        assert root_before is not None

        replacement.unlink()
        replacement.mkdir()
        (replacement / "child.txt").write_bytes(b"new-child-data")
        await inv.rewalk_subtree("replacement")

        root_after = inv.get("")
        subtree = inv.get("replacement")
        assert root_after is not None
        assert subtree is not None
        return root_before, root_after, subtree

    root_before, root_after, subtree = asyncio.run(_run())
    assert subtree.type == "dir"
    assert subtree.total_files == 1
    assert root_after.total_files == root_before.total_files
    assert root_before.total_size is not None
    assert root_after.total_size is not None
    assert root_after.total_size == root_before.total_size - len(b"old-file") + len(
        b"new-child-data"
    )


# ── remove ────────────────────────────────────────────────────


def test_remove_drops_path_and_invalidates_it(tmp_path: Path) -> None:
    """``remove(path)`` drops a file and names it in the provider change."""

    _build_tree(tmp_path)

    async def _run() -> tuple[bool, tuple[str, ...]]:
        inv = await _drive_inventory(tmp_path)
        cursor = await _checkpoint(inv)
        inv.remove("sub1/file_b.log")
        in_index = "sub1/file_b.log" in inv._entries
        changes = await _changes_since(inv, cursor)
        return in_index, changes[-1].dirty_paths

    in_index, dirty_paths = asyncio.run(_run())
    assert in_index is False
    assert "sub1/file_b.log" in dirty_paths


def test_remove_known_file_does_not_scan_large_inventory() -> None:
    inv = PythonInventoryStore()
    target = FsEntry(
        path="target.txt",
        parent="",
        name="target.txt",
        type="file",
        ext=".txt",
        kind="text",
        size=1,
        mtime_ns=1,
        mtime_hash="",
        active=False,
    )
    filler = replace(target, path="unrelated.txt", name="unrelated.txt")
    large_entry_count = 20_000
    entries = _ScanTrackingEntries(
        {f"unrelated/{index}.txt": filler for index in range(large_entry_count)}
    )
    entries[target.path] = target
    inv._entries = entries
    inv._files_indexed = len(entries)

    inv.remove(target.path)

    assert target.path not in inv._entries
    assert entries.full_scan_requested is False


def test_remove_directory_drops_descendants_in_one_event(tmp_path: Path) -> None:
    """``remove(path)`` for a dir drops the dir AND every
    descendant; consumers see one change carrying every removed path."""

    _build_tree(tmp_path)

    async def _run() -> tuple[set[str], list[ChangeBatch]]:
        inv = await _drive_inventory(tmp_path)
        cursor = await _checkpoint(inv)
        inv.remove("sub1")
        residual = {p for p in inv._entries if p.startswith("sub1")}
        return residual, await _changes_since(inv, cursor)

    residual, changes = asyncio.run(_run())
    removed = set(changes[0].dirty_paths)
    assert residual == set()
    assert len(changes) == 1, "directory remove must coalesce into one provider change"
    assert "sub1" in removed
    assert "sub1/file_b.log" in removed
    assert "sub1/sub1a" in removed
    assert "sub1/sub1a/file_c.log" in removed


def test_remove_unknown_path_is_noop(tmp_path: Path) -> None:
    """Removing a path that isn't in the index emits no event."""

    _build_tree(tmp_path)

    async def _run() -> bool:
        inv = await _drive_inventory(tmp_path)
        before = await _checkpoint(inv)
        inv.remove("does-not-exist")
        return before == await _checkpoint(inv)

    assert asyncio.run(_run())


# ── walker populates FsEntry.gitignored ───────────────────────


def test_walker_populates_gitignored_on_files_and_dirs(tmp_path: Path) -> None:
    """The walker reads the gitignore checker once at start and
    sets ``FsEntry.gitignored`` on every yielded entry (files and
    dirs both). This lets the response layer drop its per-request
    pathspec calls."""

    # Set up a real git repo so build_gitignore_check returns
    # something (it short-circuits when git_root is None).
    (tmp_path / ".git").mkdir()
    (tmp_path / ".gitignore").write_text("*.pyc\n__pycache__/\n", encoding="utf-8")
    (tmp_path / "main.py").write_bytes(b"x")
    (tmp_path / "main.pyc").write_bytes(b"x")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "cached.pyc").write_bytes(b"x")
    (tmp_path / "__pycache__" / "cached.py").write_bytes(b"x")

    async def _run() -> dict[str, bool]:
        inv = await _drive_inventory(tmp_path)
        return {p: e.gitignored for p, e in inv._entries.items()}

    flags = asyncio.run(_run())
    assert flags["main.py"] is False
    assert flags["main.pyc"] is True
    assert flags["__pycache__"] is True, (
        "directory gitignore must propagate via FsEntry.gitignored "
        "so recent.py can compose `gitignored_dirs` from inventory reads"
    )


def test_walker_finalizes_unignored_directory_aggregates(tmp_path: Path) -> None:
    """Final directory entries carry both all-file and tracked totals.

    Folder views can therefore paint stable totals from the live inventory
    without waiting for a second rollup request or scanning descendants in the
    browser.
    """

    (tmp_path / ".git").mkdir()
    (tmp_path / ".gitignore").write_text("ignored/\n*.log\n", encoding="utf-8")
    (tmp_path / "kept.py").write_bytes(b"abc")
    (tmp_path / "debug.log").write_bytes(b"12345")
    ignored = tmp_path / "ignored"
    ignored.mkdir()
    (ignored / "bundle.js").write_bytes(b"1234567")

    async def _run() -> tuple[FsEntry, FsEntry]:
        inv = await _drive_inventory(tmp_path)
        return inv._entries[""], inv._entries["ignored"]

    root, ignored_dir = asyncio.run(_run())
    assert (root.total_files, root.total_size) == (3, 15)
    assert (root.unignored_files, root.unignored_size) == (1, 3)
    assert (ignored_dir.total_files, ignored_dir.total_size) == (1, 7)
    assert (ignored_dir.unignored_files, ignored_dir.unignored_size) == (0, 0)
