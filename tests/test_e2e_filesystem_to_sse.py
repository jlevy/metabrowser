"""End-to-end tests for the live-update chain.

Drives the full producer chain in process — watcher → inventory →
SSE bus → SSE wire — and asserts that each filesystem mutation
produces the right ``fs.change`` / ``projection.invalidate`` event
on the wire. Locks in the contract that the
``metabrowser-realtime-debugging`` runbook depends on:

* mkdir + populate a new subtree → ``fs.change`` upserts for every
  new entry land on the wire (the watcher's dir branch calls
  ``rewalk_subtree``).
* rm a file → ``fs.change`` op=remove on the wire (the watcher's
  delete branch calls ``inventory.remove``, not ``invalidate``).
* rm -r a directory → one ``fs.change`` carrying op=remove for
  every removed descendant.
* touch a file → ``fs.change`` upsert + ``projection.invalidate``
  for the same path.
* Fresh SSE connect (no ``Last-Event-ID``) → snapshot only, zero
  ``fs.change`` from the walker's startup burst (locks in the
  replay-flood fix).

The watcher is exercised by calling ``_emit_for_path`` directly
with synthetic ``Change`` events; bypassing ``awatch`` keeps the
test fast and deterministic without losing coverage of the
producer logic that mattered (the dir / delete / file branches).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, cast

from watchfiles import Change

import metabrowser.events_route as evroute
from metabrowser.events import FsChange, FsRemove, FsUpsert
from metabrowser.events_route import (
    _stream_events,
    parse_sse_frames,
    reset_bus_for_tests,
)
from metabrowser.inventory import get_instance, reset_instance_for_tests
from metabrowser.watch_backends import _emit_for_path


class _FakeQuery:
    def __init__(self, data: dict[str, str]) -> None:
        self._data = data

    def get(self, key: str, default: str = "") -> str:
        return self._data.get(key, default)


class _FakeHeaders:
    def __init__(self, data: dict[str, str]) -> None:
        self._data = {k.lower(): v for k, v in data.items()}

    def get(self, key: str, default: str = "") -> str:
        return self._data.get(key.lower(), default)


class _FakeRequest:
    """Same shape as the FakeRequest in test_browser_events_route;
    duplicated locally so this test file doesn't reach across into
    its sibling's private fixtures."""

    def __init__(
        self,
        query: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        *,
        disconnect_after: int | None = None,
    ) -> None:
        self.query_params = _FakeQuery(query or {})
        self.headers = _FakeHeaders(headers or {})
        self._is_disconnected_call_count = 0
        self._disconnect_after = disconnect_after

    async def is_disconnected(self) -> bool:
        self._is_disconnected_call_count += 1
        return bool(
            self._disconnect_after is not None
            and self._is_disconnected_call_count > self._disconnect_after
        )


async def _drain_sse(stream: AsyncIterator[bytes], *, max_records: int) -> list[dict[str, str]]:
    buffer = b""
    out: list[dict[str, str]] = []
    async for chunk in stream:
        buffer += chunk
        while b"\n\n" in buffer:
            head, _, rest = buffer.partition(b"\n\n")
            buffer = rest
            for record in parse_sse_frames(head + b"\n\n"):
                out.append(record)
                if len(out) >= max_records:
                    return out
    if buffer.strip():
        for record in parse_sse_frames(buffer + b"\n\n"):
            out.append(record)
    return out


def _build_tree(root: Path) -> None:
    (root / "file_a.log").write_bytes(b"a" * 50)
    (root / "sub1").mkdir()
    (root / "sub1" / "file_b.log").write_bytes(b"b" * 100)


async def _drive_walker(root: Path) -> None:
    reset_instance_for_tests()
    reset_bus_for_tests()
    inv = get_instance()
    inv.start(root)
    await inv.wait_until_done(timeout=5.0)


# ── Replay-flood regression test ────────────────────────────────


def test_fresh_connect_no_replay_flood(tmp_path: Path) -> None:
    """A fresh ``EventSource`` connection (no ``Last-Event-ID``)
    receives ONLY the snapshot — not the entire walker startup
    burst. Pre-fix, the snapshot was followed by ~N ``fs.change``
    events that re-delivered every walker upsert, pushing live
    events to the tail of the per-connection queue."""

    _build_tree(tmp_path)
    # Add a few more subdirs so the walker emits at least one
    # batched fs.change event into the ring buffer.
    for i in range(20):
        d = tmp_path / f"d{i}"
        d.mkdir()
        (d / "x.log").write_bytes(b"x")

    async def _run() -> tuple[list[str], int]:
        await _drive_walker(tmp_path)

        original = evroute.HEARTBEAT_INTERVAL_S
        try:
            evroute.HEARTBEAT_INTERVAL_S = 0.05  # type: ignore[assignment]
            request = _FakeRequest(disconnect_after=1)
            stream = _stream_events(cast(Any, request))
            records = await _drain_sse(stream, max_records=3)
        finally:
            evroute.HEARTBEAT_INTERVAL_S = original  # type: ignore[assignment]

        events = [r["event"] for r in records]
        # Count any fs.change in the records (must be zero on a
        # fresh connect with no filesystem activity).
        n_changes = sum(1 for r in records if r["event"] == "fs.change")
        return events, n_changes

    events, n_changes = asyncio.run(_run())
    assert events[0] == "fs.snapshot", f"first event must be snapshot, got {events!r}"
    assert n_changes == 0, (
        f"fresh connect must not replay walker burst; got {n_changes} fs.change events. "
        "If this fails, _stream_events is replaying the ring buffer for clients with no "
        "Last-Event-ID — check _parse_last_event_id and the replay branch."
    )


# ── Filesystem-to-wire chain ────────────────────────────────────


def test_touch_existing_file_emits_upsert_and_projection_invalidate(tmp_path: Path) -> None:
    """A file modify event (the watcher's regular path) emits one
    ``fs.change`` with one upsert AND a ``projection.invalidate``
    event for the same path."""

    _build_tree(tmp_path)

    async def _run() -> tuple[set[str], list[str]]:
        await _drive_walker(tmp_path)
        inv = get_instance()
        sub_q = inv.subscribe(max_queue=1024)

        # Modify the file on disk; drive the watcher's emit path
        # directly to skip awatch's polling/coalescing latency.
        target = tmp_path / "file_a.log"
        target.write_bytes(b"a" * 75)
        await _emit_for_path(inv, tmp_path, str(target), Change.modified)

        events: list[str] = []
        upsert_paths: set[str] = set()
        while not sub_q.empty():
            evt = sub_q.get_nowait()
            events.append(getattr(evt, "type", type(evt).__name__))
            if isinstance(evt, FsChange):
                for op in evt.ops:
                    if isinstance(op, FsUpsert):
                        upsert_paths.add(op.entry.path)
        return upsert_paths, events

    upserts, events = asyncio.run(_run())
    assert "file_a.log" in upserts
    assert "fs.change" in events
    assert "projection.invalidate" in events, (
        "watcher's file branch must call inventory.emit_event("
        "ProjectionInvalidate(...)) so client-side caches stay in step"
    )


def test_mkdir_with_files_runs_rewalk_and_emits_upserts(tmp_path: Path) -> None:
    """The watcher's ``is_dir()`` branch calls
    ``inventory.rewalk_subtree(rel)``, which walks the new subtree
    and produces an ``fs.change`` upsert for every entry. This
    locks in the watcher → rewalk → inventory chain."""

    _build_tree(tmp_path)

    async def _run() -> set[str]:
        await _drive_walker(tmp_path)
        inv = get_instance()

        new_dir = tmp_path / "newdir"
        new_dir.mkdir()
        (new_dir / "x.txt").write_bytes(b"x" * 10)
        (new_dir / "nested").mkdir()
        (new_dir / "nested" / "y.txt").write_bytes(b"y" * 20)

        sub_q = inv.subscribe(max_queue=1024)
        await _emit_for_path(inv, tmp_path, str(new_dir), Change.added)

        upsert_paths: set[str] = set()
        while not sub_q.empty():
            evt = sub_q.get_nowait()
            if isinstance(evt, FsChange):
                for op in evt.ops:
                    if isinstance(op, FsUpsert):
                        upsert_paths.add(op.entry.path)
        return upsert_paths

    upserts = asyncio.run(_run())
    assert "newdir" in upserts
    assert "newdir/x.txt" in upserts
    assert "newdir/nested" in upserts
    assert "newdir/nested/y.txt" in upserts


def test_rm_file_emits_fs_remove(tmp_path: Path) -> None:
    """The watcher's ``Change.deleted`` branch calls
    ``inventory.remove(rel)`` which emits an ``fs.change`` op with
    one ``FsRemove`` for the deleted path."""

    _build_tree(tmp_path)

    async def _run() -> tuple[set[str], bool]:
        await _drive_walker(tmp_path)
        inv = get_instance()

        target = tmp_path / "file_a.log"
        target.unlink()
        sub_q = inv.subscribe(max_queue=1024)
        await _emit_for_path(inv, tmp_path, str(target), Change.deleted)

        removed: set[str] = set()
        while not sub_q.empty():
            evt = sub_q.get_nowait()
            if isinstance(evt, FsChange):
                for op in evt.ops:
                    if isinstance(op, FsRemove):
                        removed.add(op.path)
        in_index = "file_a.log" in inv._entries
        return removed, in_index

    removed, in_index = asyncio.run(_run())
    assert "file_a.log" in removed
    assert in_index is False


def test_rm_directory_coalesces_descendants_into_one_fs_change(tmp_path: Path) -> None:
    """``rm -r dir`` arrives as a single ``Change.deleted`` for the
    directory; the watcher's delete branch calls
    ``inventory.remove`` which removes every descendant from the
    index AND emits one ``fs.change`` whose ops cover every
    removed path. One event, not N."""

    _build_tree(tmp_path)

    async def _run() -> tuple[int, set[str]]:
        await _drive_walker(tmp_path)
        inv = get_instance()

        target = tmp_path / "sub1"
        # Filesystem already mutated; the watcher's delete branch
        # doesn't stat the path, it just looks up the inventory
        # entry. Real-world the rm has already happened by the
        # time the event fires.
        sub_q = inv.subscribe(max_queue=1024)
        await _emit_for_path(inv, tmp_path, str(target), Change.deleted)

        n_changes = 0
        removed: set[str] = set()
        while not sub_q.empty():
            evt = sub_q.get_nowait()
            # Only count fs.change events that carry a remove op.
            if (
                isinstance(evt, FsChange)
                and evt.ops
                and any(isinstance(op, FsRemove) for op in evt.ops)
            ):
                n_changes += 1
                for op in evt.ops:
                    if isinstance(op, FsRemove):
                        removed.add(op.path)
        return n_changes, removed

    n_changes, removed = asyncio.run(_run())
    assert n_changes == 1, "directory remove must coalesce into one fs.change"
    assert "sub1" in removed
    assert "sub1/file_b.log" in removed
