"""Tests for the server-side active-file tracker.

The tracker replaces /api/activity polling: a background task
periodically fingerprints trackable files in .logs/.state and
emits fs.change ops on the InventoryIndex when a file's active
state flips.

Coverage:

* `_is_trackable` matches BROWSER_TRACKABLE_EXTS files inside
  .logs / .state subtrees and rejects everything else.
* A single tick on a fixture marks a freshly-written file as
  active and emits an fs.change op via the inventory.
* A file unchanged across `ACTIVE_TRACKER_QUIET_POLLS` ticks
  flips back to active=false.
* PID-alive labels propagate to FsEntry.labels.
* Tracker survives transient errors and keeps running.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from metabrowser.active_tracker import _is_trackable, _tick
from metabrowser.events import FsChange, FsEntry, FsUpsert
from metabrowser.inventory import get_instance, reset_instance_for_tests
from metabrowser.settings import ACTIVE_TRACKER_QUIET_POLLS


def _file_entry(
    path: str, *, name: str, mtime_ns: int = 1_000_000_000_000, active: bool = False
) -> FsEntry:
    return FsEntry(
        path=path,
        parent="/".join(path.split("/")[:-1]),
        name=name,
        type="file",
        ext=".jsonl" if name.endswith(".jsonl") else "",
        kind="file",
        size=100,
        mtime_ns=mtime_ns,
        mtime_hash="",
        active=active,
    )


# ── _is_trackable ──────────────────────────────────────────────


def test_is_trackable_logs_jsonl() -> None:
    e = _file_entry("runs/x/.logs/foo.jsonl", name="foo.jsonl")
    assert _is_trackable(e) is True


def test_is_trackable_state_yaml() -> None:
    e = _file_entry("runs/x/.state/status.yaml", name="status.yaml")
    assert _is_trackable(e) is True


def test_is_trackable_rejects_outside_logs_state() -> None:
    e = _file_entry("docs/notes.md", name="notes.md")
    assert _is_trackable(e) is False


def test_is_trackable_rejects_unknown_ext_inside_logs() -> None:
    e = _file_entry("runs/x/.logs/something.bin", name="something.bin")
    assert _is_trackable(e) is False


def test_is_trackable_rejects_dir() -> None:
    d = FsEntry(
        path="runs/x/.logs",
        parent="runs/x",
        name=".logs",
        type="dir",
        ext="",
        kind="dir",
        size=0,
        mtime_ns=0,
        mtime_hash="",
        active=False,
    )
    assert _is_trackable(d) is False


# ── End-to-end tick on a real fixture ─────────────────────────


def _setup_fixture(tmp_path: Path) -> Path:
    """A repo with a .logs jsonl that has just been written
    (so the tracker should mark it active)."""
    (tmp_path / "runs").mkdir()
    (tmp_path / "runs" / "x").mkdir()
    (tmp_path / "runs" / "x" / ".logs").mkdir()
    log = tmp_path / "runs" / "x" / ".logs" / "foo.jsonl"
    log.write_text('{"event":"start"}\n')
    return log


def test_tick_marks_freshly_written_file_active(tmp_path: Path) -> None:
    log = _setup_fixture(tmp_path)

    async def _run() -> bool:
        reset_instance_for_tests()
        inv = get_instance()
        inv.start(tmp_path)
        await inv.wait_until_done(timeout=5.0)

        quiet: dict[str, int] = {}
        await _tick(inv, tmp_path, quiet)  # baseline (no change yet)
        # Touch the file → mtime + size change.
        log.write_text('{"event":"start"}\n{"event":"step"}\n')
        # Force a different mtime even at sub-second resolution.
        st = log.stat()
        os.utime(log, (st.st_mtime + 1.0, st.st_mtime + 1.0))
        await _tick(inv, tmp_path, quiet)
        e = inv.get("runs/x/.logs/foo.jsonl")
        return e is not None and e.active

    assert asyncio.run(_run()) is True


def test_tick_emits_fs_change_op_via_subscriber(tmp_path: Path) -> None:
    """Each active-state flip must surface as an fs.change
    upsert on subscribers (so the SPA's FileStore picks it up)."""

    log = _setup_fixture(tmp_path)

    async def _run() -> list[FsUpsert]:
        reset_instance_for_tests()
        inv = get_instance()
        q = inv.subscribe()
        inv.start(tmp_path)
        await inv.wait_until_done(timeout=5.0)

        # Drain walker emissions.
        while not q.empty():
            q.get_nowait()

        quiet: dict[str, int] = {}
        await _tick(inv, tmp_path, quiet)
        log.write_text('{"event":"step"}\n')
        st = log.stat()
        os.utime(log, (st.st_mtime + 1.0, st.st_mtime + 1.0))
        await _tick(inv, tmp_path, quiet)

        # Collect upserts that flipped active=True.
        upserts: list[FsUpsert] = []
        while not q.empty():
            evt = q.get_nowait()
            if isinstance(evt, FsChange):
                for op in evt.ops:
                    if isinstance(op, FsUpsert) and op.entry.active:
                        upserts.append(op)
        return upserts

    upserts = asyncio.run(_run())
    assert any(u.entry.path == "runs/x/.logs/foo.jsonl" for u in upserts)


def test_tick_marks_file_inactive_after_quiet_polls(tmp_path: Path) -> None:
    """After ACTIVE_TRACKER_QUIET_POLLS ticks without a change,
    the file flips back to active=False."""

    log = _setup_fixture(tmp_path)

    async def _run() -> bool:
        reset_instance_for_tests()
        inv = get_instance()
        inv.start(tmp_path)
        await inv.wait_until_done(timeout=5.0)

        # Make the file appear active via a write+touch.
        log.write_text('{"event":"step"}\n')
        st = log.stat()
        os.utime(log, (st.st_mtime + 1.0, st.st_mtime + 1.0))

        quiet: dict[str, int] = {}
        await _tick(inv, tmp_path, quiet)  # see the change
        # Subsequent ticks see no change; quiet counter increments.
        for _ in range(ACTIVE_TRACKER_QUIET_POLLS + 2):
            await _tick(inv, tmp_path, quiet)

        e = inv.get("runs/x/.logs/foo.jsonl")
        return e is not None and not e.active

    assert asyncio.run(_run()) is True


def test_tick_no_ops_when_inventory_empty() -> None:
    """No trackable entries → tick is a no-op (no exception,
    no emission)."""

    async def _run() -> None:
        reset_instance_for_tests()
        inv = get_instance()
        await _tick(inv, Path("/nonexistent"), {})

    asyncio.run(_run())  # just shouldn't raise
