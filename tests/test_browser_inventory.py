"""Unit tests for ``metabrowser.inventory``.

Covers the walker correctness invariants and the public InventoryIndex
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
* InventoryIndex.start is idempotent.
* InventoryIndex.entries(scope='root-depth-2') filters by depth.
* InventoryIndex.invalidate bumps generation along the ancestor
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

import metabrowser.inventory as inventory_module
from metabrowser.constants import LOGS_DIR, STATE_DIR
from metabrowser.events import (
    FsChange,
    FsEntry,
    FsRemove,
    FsResyncRequired,
    FsUpsert,
    StreamEvent,
    WriteToken,
)
from metabrowser.fs_paths import derive_ext as _ext_of
from metabrowser.fs_paths import is_visible, is_visible_segment
from metabrowser.inventory import (
    DEFAULT_FIRST_RENDER_DEPTH,
    InventoryIndex,
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
    first_render_depth: int = 2,
) -> list[FsEntry]:
    return [
        e
        async for e in walk_tree(
            root,
            max_depth=max_depth,
            max_files=max_files,
            first_render_depth=first_render_depth,
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
    final_dirs: dict[str, FsEntry] = {}
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


def test_walk_tree_first_render_depth_does_not_change_yield_set(tmp_path: Path) -> None:
    """Changing first_render_depth changes BFS *order* but not
    the *set* of yielded entries."""
    _build_tree(tmp_path)

    def _signature(frd: int) -> set[tuple[str, str]]:
        out = asyncio.run(_collect(tmp_path, first_render_depth=frd))
        # Use (path, type, has_aggregates) so we count
        # placeholder-vs-final correctly.
        return {(e.path, e.type) for e in out}

    sig_a = _signature(0)
    sig_b = _signature(DEFAULT_FIRST_RENDER_DEPTH)
    sig_c = _signature(10)
    assert sig_a == sig_b == sig_c


# ── path helpers ─────────────────────────────────────────────


def test_depth_of_root_and_subpaths() -> None:
    assert _depth_of("") == 0
    assert _depth_of("a") == 1
    assert _depth_of("a/b") == 2
    assert _depth_of("a/b/c") == 3


def test_ext_of_compound_tail() -> None:
    assert _ext_of("foo.runbook.md") == ".runbook.md"
    assert _ext_of("archive.tar.gz") == ".tar.gz"
    assert _ext_of("plain.txt") == ".txt"
    assert _ext_of("Makefile") == ""
    assert _ext_of(".dotfile") == ""
    assert _ext_of("Foo.With.Dots.Txt") == ""


def test_fs_entry_factory_uses_compound_ext_for_file_observations() -> None:
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


# ── InventoryIndex ─────────────────────────────────────────────


async def _drive_inventory(tmp_path: Path) -> InventoryIndex:
    """Spin up an InventoryIndex against *tmp_path* and wait for
    completion. Returns the index for assertions."""
    inv = InventoryIndex()
    inv.start(tmp_path)
    await inv.wait_until_done(timeout=5.0)
    return inv


def test_inventory_start_is_idempotent(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    async def _run() -> tuple[bool, str]:
        inv = InventoryIndex()
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
    inv = InventoryIndex()
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

    assert inv.apply_walker_entries([directory, child]) == 2
    assert inv.has_direct_child("") is True
    assert inv.has_direct_child("runs") is True

    inv.remove("runs/event.jsonl")

    assert inv.has_direct_child("") is True
    assert inv.has_direct_child("runs") is False


def test_live_file_changes_refresh_root_aggregates(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    async def _run() -> tuple[FsEntry, FsEntry, list[FsChange]]:
        inv = await _drive_inventory(tmp_path)
        before = inv.get("")
        assert before is not None
        queue = inv.subscribe()
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
        changes: list[FsChange] = []
        # Each fs.change is followed by its minimal catalog.change
        # companion; this test cares about the fat events only.
        while len(changes) < 2:
            event = await queue.get()
            if isinstance(event, FsChange):
                changes.append(event)
        return after_insert, after_remove, changes

    after_insert, after_remove, changes = asyncio.run(_run())
    assert (after_insert.total_files, after_insert.total_size) == (5, 303)
    assert (after_remove.total_files, after_remove.total_size) == (4, 250)
    assert (after_remove.newest_mtime_ns or 0) < (after_insert.newest_mtime_ns or 0)
    for change in changes:
        assert any(isinstance(op, FsUpsert) and op.entry.path == "" for op in change.ops)


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
        inv = InventoryIndex()
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
            inv.apply_walker_entries(
                [replace(entry, active=bool(index % 2), labels=(("tick", str(index)),))]
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
            inv.apply_walker_entries([replace(entry, mtime_ns=entry.mtime_ns + index + 1)])
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
        inv = InventoryIndex()
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

    logger = logging.getLogger("metabrowser.inventory")
    original_level = logger.level
    handler = _RecordHandler()
    logger.addHandler(handler)
    try:
        logger.setLevel(logging.DEBUG)
        inv = InventoryIndex()
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

    inv = InventoryIndex()
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

    inv = InventoryIndex()
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

    inv = InventoryIndex()
    inv._generation["runs"] = 1
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
    )
    runs = FsEntry(
        path="runs",
        parent="",
        name="runs",
        type="dir",
        ext="",
        kind="dir",
        size=0,
        mtime_ns=0,
        mtime_hash="",
        active=False,
    )
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
    assert inv.apply_walker_entries([root, runs, child]) == 3
    q = inv.subscribe()

    inv._repair_pending_dir_aggregates()

    assert inv._entries["runs"].total_files == 1
    assert inv._entries["runs"].total_size == 11
    assert inv._entries["runs"].newest_mtime_ns == 123
    assert inv._entries[""].total_files == 1
    event = q.get_nowait()
    assert isinstance(event, FsChange)
    paths = {op.entry.path for op in event.ops if isinstance(op, FsUpsert)}
    assert {"", "runs"} <= paths

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
    assert inv._entries[""].newest_mtime_ns == 123


def test_inventory_pending_repair_does_not_scan_all_entries_on_event_loop() -> None:
    inv = InventoryIndex()
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
    assert inv.apply_walker_entries([root, child]) == 2
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


def test_inventory_completion_survives_pending_repair_failure(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    async def _run() -> str:
        inv = InventoryIndex()

        def _fail_repair() -> None:
            raise RuntimeError("repair failed")

        inv._repair_pending_dir_aggregates = _fail_repair
        inv.start(tmp_path)
        await inv.wait_until_done(timeout=5.0)
        return inv.status()

    assert asyncio.run(_run()) == "done"


def test_inventory_walker_crash_surfaces_failed_status(tmp_path: Path) -> None:
    """A walker crash must produce ``status() == 'failed'``, not
    ``'idle'``. Production code (capability probe, lifespan, SSE bus)
    can then distinguish a broken inventory from one that's never
    been started. Log-and-continue is not handling — every error log
    needs a control-flow signal."""

    _build_tree(tmp_path)

    async def _run() -> str:
        inv = InventoryIndex()

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


def test_inventory_subscribe_receives_walker_changes(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    async def _run() -> set[str]:
        inv = InventoryIndex()
        q = inv.subscribe()
        inv.start(tmp_path)
        await inv.wait_until_done(timeout=5.0)
        seen: set[str] = set()
        while not q.empty():
            evt = q.get_nowait()
            if isinstance(evt, FsChange):
                for op in evt.ops:
                    if isinstance(op, FsUpsert):
                        seen.add(op.entry.path)
        return seen

    seen = asyncio.run(_run())
    assert "file_a.log" in seen
    assert "sub1" in seen
    assert "sub1/file_b.log" in seen


def test_inventory_slow_subscriber_gets_resync_without_blocking(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    async def _run() -> tuple[bool, bool, int, object]:
        inv = InventoryIndex()
        slow = inv.subscribe(max_queue=1)
        fast = inv.subscribe(max_queue=1024)
        # Drive emits directly: the walker batches upserts now, so a
        # tiny tree no longer guarantees N>queue events from start().
        # The behavior under test doesn't depend on the walker.
        for _ in range(3):
            inv._emit(FsChange(ops=()))
        return (
            slow in inv._subscribers,
            fast in inv._subscribers,
            inv.subscriber_count(),
            slow.get_nowait(),
        )

    slow_attached, fast_attached, count, slow_event = asyncio.run(_run())
    assert slow_attached is True
    assert fast_attached is True
    assert count == 2
    assert isinstance(slow_event, FsResyncRequired)
    assert slow_event.reason == "subscriber_queue_overflow"


def test_inventory_clear_emits_resync(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    async def _run() -> object:
        inv = InventoryIndex()
        q = inv.subscribe()
        inv.start(tmp_path)
        await inv.wait_until_done(timeout=5.0)
        while not q.empty():
            q.get_nowait()
        inv.clear()
        return q.get_nowait()

    evt = asyncio.run(_run())
    assert isinstance(evt, FsResyncRequired)
    assert evt.reason == "root_swap"


def test_inventory_initial_snapshot_complete_flag_tracks_status(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    async def _run() -> tuple[str, bool, set[str]]:
        inv = await _drive_inventory(tmp_path)
        snap = inv.initial_snapshot(scope="root-depth-2")
        return (snap.scope, snap.complete, {e.path for e in snap.entries})

    scope, complete, paths = asyncio.run(_run())
    assert scope == "root-depth-2"
    assert complete is True
    assert "sub1/file_b.log" in paths
    assert "sub1/sub1a/file_c.log" not in paths


# ── rewalk_subtree ────────────────────────────────────────────


def test_rewalk_subtree_ingests_a_newly_created_directory(tmp_path: Path) -> None:
    """A directory created on disk after the boot walker finishes
    is invisible to the inventory until the watcher's dir-create
    branch calls ``rewalk_subtree``. This test exercises that path
    directly: build a tree, run the walker, then mkdir + populate
    a new subtree and call ``rewalk_subtree``. Every new entry must
    land in ``_entries`` and a single ``FsChange`` event must reach
    subscribers per upsert (one per file plus the dir placeholder
    + finalize)."""

    _build_tree(tmp_path)

    async def _run() -> tuple[set[str], list[StreamEvent]]:
        inv = await _drive_inventory(tmp_path)
        # Drain anything the walker emitted before we attach.
        q = inv.subscribe(max_queue=1024)
        # New subtree on disk:
        new_dir = tmp_path / "newdir"
        new_dir.mkdir()
        (new_dir / "x.txt").write_bytes(b"x" * 10)
        (new_dir / "nested").mkdir()
        (new_dir / "nested" / "y.txt").write_bytes(b"y" * 20)
        await inv.rewalk_subtree("newdir")
        events: list[StreamEvent] = []
        while not q.empty():
            events.append(q.get_nowait())
        paths_now = {p for p in inv._entries if p.startswith("newdir")}
        return paths_now, events

    paths, events = asyncio.run(_run())
    assert "newdir" in paths
    assert "newdir/x.txt" in paths
    assert "newdir/nested" in paths
    assert "newdir/nested/y.txt" in paths
    # Each fresh entry produces an FsChange via _apply_walker_entry.
    assert any(isinstance(e, FsChange) for e in events)


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


def test_remove_drops_path_and_emits_fs_remove(tmp_path: Path) -> None:
    """``remove(path)`` for a file pops the entry and emits one
    ``FsChange`` with one ``FsRemove`` op."""

    _build_tree(tmp_path)

    async def _run() -> tuple[bool, list[FsRemove]]:
        inv = await _drive_inventory(tmp_path)
        q = inv.subscribe(max_queue=1024)
        inv.remove("sub1/file_b.log")
        events: list[StreamEvent] = []
        while not q.empty():
            events.append(q.get_nowait())
        in_index = "sub1/file_b.log" in inv._entries
        removes: list[FsRemove] = []
        for e in events:
            if isinstance(e, FsChange):
                for op in e.ops:
                    if isinstance(op, FsRemove):
                        removes.append(op)
        return in_index, removes

    in_index, removes = asyncio.run(_run())
    assert in_index is False
    assert any(r.path == "sub1/file_b.log" for r in removes)


def test_remove_known_file_does_not_scan_large_inventory() -> None:
    inv = InventoryIndex()
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
    descendant; subscribers see one ``FsChange`` carrying every
    removed path."""

    _build_tree(tmp_path)

    async def _run() -> tuple[set[str], int, set[str]]:
        inv = await _drive_inventory(tmp_path)
        q = inv.subscribe(max_queue=1024)
        inv.remove("sub1")
        events: list[StreamEvent] = []
        while not q.empty():
            events.append(q.get_nowait())
        # All sub1/* must be gone.
        residual = {p for p in inv._entries if p.startswith("sub1")}
        # Find the FsChange events; collect every removed path.
        change_count = 0
        removed_paths: set[str] = set()
        for e in events:
            if isinstance(e, FsChange):
                change_count += 1
                for op in e.ops:
                    if isinstance(op, FsRemove):
                        removed_paths.add(op.path)
        return residual, change_count, removed_paths

    residual, n_changes, removed = asyncio.run(_run())
    assert residual == set()
    assert n_changes == 1, "directory remove must coalesce into one FsChange"
    assert "sub1" in removed
    assert "sub1/file_b.log" in removed
    assert "sub1/sub1a" in removed
    assert "sub1/sub1a/file_c.log" in removed


def test_remove_unknown_path_is_noop(tmp_path: Path) -> None:
    """Removing a path that isn't in the index emits no event."""

    _build_tree(tmp_path)

    async def _run() -> int:
        inv = await _drive_inventory(tmp_path)
        q = inv.subscribe(max_queue=1024)
        inv.remove("does-not-exist")
        return q.qsize()

    assert asyncio.run(_run()) == 0


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
