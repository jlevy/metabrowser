"""End-to-end tests for watcher → coordinator → SSE convergence."""

from __future__ import annotations

import asyncio
import shutil
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, cast

from watchfiles import Change

import metabrowser.events_route as evroute
from metabrowser.events import EventEnvelope, FsChange, FsRemove, FsUpsert
from metabrowser.events_route import _stream_events, parse_sse_frames
from metabrowser.inventory_engine.contract import EntryProjection, EntryQuery, ReadRequest
from metabrowser.watch_backends import _emit_for_path
from tests.inventory_harness import InventoryHarness, inventory_harness

_REFRESH_EVENT_TIMEOUT_S = 2.0


class _FakeQuery:
    def __init__(self, data: dict[str, str]) -> None:
        self._data = data

    def get(self, key: str, default: str = "") -> str:
        return self._data.get(key, default)


class _FakeHeaders:
    def __init__(self, data: dict[str, str]) -> None:
        self._data = {key.lower(): value for key, value in data.items()}

    def get(self, key: str, default: str = "") -> str:
        return self._data.get(key.lower(), default)


class _FakeRequest:
    def __init__(
        self,
        *,
        app: object,
        disconnect_after: int | None = None,
    ) -> None:
        self.query_params = _FakeQuery({})
        self.headers = _FakeHeaders({})
        self.app = app
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
            head, _, buffer = buffer.partition(b"\n\n")
            for record in parse_sse_frames(head + b"\n\n"):
                out.append(record)
                if len(out) >= max_records:
                    return out
    return out


def _build_tree(root: Path) -> None:
    (root / "file_a.log").write_bytes(b"a" * 50)
    (root / "sub1").mkdir()
    (root / "sub1" / "file_b.log").write_bytes(b"b" * 100)


async def _observe_refresh(
    harness: InventoryHarness,
    root: Path,
    target: Path,
    change: Change,
    *,
    expected_upserts: frozenset[str] = frozenset(),
    expected_removes: frozenset[str] = frozenset(),
) -> list[EventEnvelope]:
    queue = harness.bus.attach_connection()
    try:
        await _emit_for_path(
            harness.runtime.coordinator.refresh,
            root,
            str(target),
            change,
        )
        events: list[EventEnvelope] = []
        async with asyncio.timeout(_REFRESH_EVENT_TIMEOUT_S):
            while True:
                events.append(await queue.get())
                upserts = {
                    operation.entry.path
                    for envelope in events
                    if isinstance(envelope.event, FsChange)
                    for operation in envelope.event.ops
                    if isinstance(operation, FsUpsert)
                }
                removes = {
                    operation.path
                    for envelope in events
                    if isinstance(envelope.event, FsChange)
                    for operation in envelope.event.ops
                    if isinstance(operation, FsRemove)
                }
                if expected_upserts <= upserts and expected_removes <= removes:
                    while not queue.empty():
                        events.append(queue.get_nowait())
                    return events
    finally:
        harness.bus.detach_connection(queue)


def test_fresh_connect_no_replay_flood(tmp_path: Path) -> None:
    _build_tree(tmp_path)
    for index in range(20):
        directory = tmp_path / f"d{index}"
        directory.mkdir()
        (directory / "x.log").write_bytes(b"x")

    async def run() -> tuple[list[str], int]:
        async with inventory_harness(tmp_path) as harness:
            original = evroute.HEARTBEAT_INTERVAL_S
            try:
                evroute.HEARTBEAT_INTERVAL_S = 0.05  # type: ignore[assignment]
                request = _FakeRequest(app=harness.app, disconnect_after=1)
                records = await _drain_sse(_stream_events(cast(Any, request)), max_records=3)
            finally:
                evroute.HEARTBEAT_INTERVAL_S = original  # type: ignore[assignment]
            events = [record["event"] for record in records]
            return events, sum(event == "fs.change" for event in events)

    events, change_count = asyncio.run(run())
    assert events[0] == "fs.snapshot"
    assert change_count == 0


def test_touch_existing_file_emits_upsert_and_projection_invalidate(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    async def run() -> tuple[set[str], set[str]]:
        async with inventory_harness(tmp_path) as harness:
            target = tmp_path / "file_a.log"
            target.write_bytes(b"a" * 75)
            envelopes = await _observe_refresh(
                harness,
                tmp_path,
                target,
                Change.modified,
                expected_upserts=frozenset({"file_a.log"}),
            )
            event_types = {envelope.event.type for envelope in envelopes}
            upserts = {
                operation.entry.path
                for envelope in envelopes
                if isinstance(envelope.event, FsChange)
                for operation in envelope.event.ops
                if isinstance(operation, FsUpsert)
            }
            return upserts, event_types

    upserts, event_types = asyncio.run(run())
    assert "file_a.log" in upserts
    assert "fs.change" in event_types
    assert "projection.invalidate" in event_types


def test_mkdir_with_files_reconciles_subtree_and_root_totals(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    async def run() -> tuple[set[str], tuple[int | None, int | None]]:
        async with inventory_harness(tmp_path) as harness:
            new_dir = tmp_path / "newdir"
            new_dir.mkdir()
            (new_dir / "x.txt").write_bytes(b"x" * 10)
            (new_dir / "nested").mkdir()
            (new_dir / "nested" / "y.txt").write_bytes(b"y" * 20)
            envelopes = await _observe_refresh(
                harness,
                tmp_path,
                new_dir,
                Change.added,
                expected_upserts=frozenset(
                    {"", "newdir", "newdir/x.txt", "newdir/nested", "newdir/nested/y.txt"}
                ),
            )
            upserts = {
                operation.entry.path
                for envelope in envelopes
                if isinstance(envelope.event, FsChange)
                for operation in envelope.event.ops
                if isinstance(operation, FsUpsert)
            }
            read = await harness.runtime.coordinator.read(
                ReadRequest(queries=(EntryQuery(query_id="root", path=""),))
            )
            projection = read.result.projection("root")
            assert isinstance(projection, EntryProjection)
            assert projection.entry is not None
            return upserts, (
                projection.entry.total_files,
                projection.entry.total_size,
            )

    upserts, root_totals = asyncio.run(run())
    assert {"", "newdir", "newdir/x.txt", "newdir/nested", "newdir/nested/y.txt"} <= upserts
    assert root_totals == (4, 180)


def test_rm_file_emits_remove_and_updates_root(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    async def run() -> tuple[set[str], tuple[int | None, int | None]]:
        async with inventory_harness(tmp_path) as harness:
            target = tmp_path / "file_a.log"
            target.unlink()
            envelopes = await _observe_refresh(
                harness,
                tmp_path,
                target,
                Change.deleted,
                expected_removes=frozenset({"file_a.log"}),
            )
            removed = {
                operation.path
                for envelope in envelopes
                if isinstance(envelope.event, FsChange)
                for operation in envelope.event.ops
                if isinstance(operation, FsRemove)
            }
            read = await harness.runtime.coordinator.read(
                ReadRequest(queries=(EntryQuery(query_id="root", path=""),))
            )
            projection = read.result.projection("root")
            assert isinstance(projection, EntryProjection)
            assert projection.entry is not None
            return removed, (
                projection.entry.total_files,
                projection.entry.total_size,
            )

    removed, root_totals = asyncio.run(run())
    assert "file_a.log" in removed
    assert root_totals == (1, 100)


def test_rm_directory_coalesces_descendant_removals(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    async def run() -> tuple[int, set[str]]:
        async with inventory_harness(tmp_path) as harness:
            target = tmp_path / "sub1"
            shutil.rmtree(target)
            envelopes = await _observe_refresh(
                harness,
                tmp_path,
                target,
                Change.deleted,
                expected_removes=frozenset({"sub1", "sub1/file_b.log"}),
            )
            changes = [
                envelope.event
                for envelope in envelopes
                if isinstance(envelope.event, FsChange)
                and any(isinstance(operation, FsRemove) for operation in envelope.event.ops)
            ]
            removed = {
                operation.path
                for change in changes
                for operation in change.ops
                if isinstance(operation, FsRemove)
            }
            return len(changes), removed

    change_count, removed = asyncio.run(run())
    assert change_count == 1
    assert {"sub1", "sub1/file_b.log"} <= removed
