"""End-to-end tests for the inventory event-plane routes.

Drives the routes via duck-typed Request objects (matches the
broader repo pattern in ``test_browser_v2.py`` — keeps httpx out
of the test dep tree). Covers:

* ``/api/events`` emits an ``fs.snapshot`` on connect with the
  requested scope, then live ``fs.change`` ops as the walker
  proceeds; heartbeat comments arrive on the configured cadence
  when the producer is quiet.
* ``/api/index/progress`` returns the lightweight crawl counter
  used by the nav footer.
* ``/api/index/meta`` returns status, file/dir counts, mtime
  range, and the suffix tally; ETag round-trips via 304 when
  nothing finalized between polls.
* ``/api/capabilities`` returns the unified shape with the polling
  placeholder for ``backends`` and real values for
  ``index`` and ``events``.
* SSE wire hygiene: ``Content-Type``, ``Cache-Control``,
  ``X-Accel-Buffering`` headers are present.
* ``parse_sse_frames`` round-trips the wire format for tests.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

import metabrowser.events_route as evroute
from metabrowser import paths_safe
from metabrowser.events import (
    FsChange,
    FsEntry,
    FsRemove,
    FsResyncRequired,
    FsUpsert,
    Heartbeat,
)
from metabrowser.events_route import (
    HEARTBEAT_INTERVAL_S,
    _filter_event_for_scope,
    _stream_events,
    api_capabilities,
    api_index_meta,
    api_index_progress,
    api_pending_tally_diagnostic,
    parse_sse_frames,
)
from metabrowser.inventory_engine.contract import (
    InventoryConfig,
    ObservationKind,
    RefreshObservation,
    RefreshRequest,
)
from tests.inventory_harness import inventory_harness

# ── Fake request plumbing ──────────────────────────────────────


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
    def __init__(
        self,
        query: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        *,
        disconnect_after: int | None = None,
        body: bytes = b"",
        body_chunks: list[bytes] | None = None,
        app: object | None = None,
    ) -> None:
        self.query_params = _FakeQuery(query or {})
        self.headers = _FakeHeaders(headers or {})
        self._is_disconnected_call_count = 0
        self._disconnect_after = disconnect_after
        self._body = body
        self._body_chunks = body_chunks
        self.streamed_chunks = 0
        self.app = app

    async def body(self) -> bytes:
        return self._body

    async def stream(self) -> AsyncIterator[bytes]:
        chunks = self._body_chunks if self._body_chunks is not None else [self._body]
        for chunk in chunks:
            self.streamed_chunks += 1
            yield chunk

    async def is_disconnected(self) -> bool:
        self._is_disconnected_call_count += 1
        return bool(
            self._disconnect_after is not None
            and self._is_disconnected_call_count > self._disconnect_after
        )


def _build_tree(root: Path) -> None:
    (root / "file_a.log").write_bytes(b"a" * 50)
    (root / "sub1").mkdir()
    (root / "sub1" / "file_b.log").write_bytes(b"b" * 100)
    (root / "sub2").mkdir()
    (root / "sub2" / "file_d.log").write_bytes(b"d" * 75)


def test_lifespan_propagates_required_inventory_open_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_open(_self: object, _root: Path) -> None:
        raise RuntimeError("open failure sentinel")

    monkeypatch.setattr(evroute.InventoryRuntime, "open", fail_open)
    app = SimpleNamespace(state=SimpleNamespace())

    async def run() -> None:
        async with evroute.build_lifespan(
            app=cast(Any, app),
            root_provider=lambda: tmp_path,
        ):
            raise AssertionError("lifespan must not yield after a failed inventory open")

    with pytest.raises(RuntimeError, match="open failure sentinel"):
        asyncio.run(run())


async def _drain_sse(stream: AsyncIterator[bytes], *, max_records: int) -> list[dict[str, str]]:
    """Pull from *stream* until *max_records* records have been
    parsed or the stream ends. Wraps each chunk through
    ``parse_sse_frames`` once a terminator arrives."""

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
    # Stream ended; flush any buffered partial record.
    if buffer.strip():
        for record in parse_sse_frames(buffer + b"\n\n"):
            out.append(record)
    return out


class _FastHeartbeat:
    """Context manager that lowers HEARTBEAT_INTERVAL_S so tests
    don't wait 15 s for the queue-empty path. Restored on exit."""

    def __init__(self, seconds: float = 0.05) -> None:
        self._seconds = seconds
        self._original: float = 0.0

    def __enter__(self) -> None:

        self._original = evroute.HEARTBEAT_INTERVAL_S
        evroute.HEARTBEAT_INTERVAL_S = self._seconds  # type: ignore[assignment]

    def __exit__(self, *_a: object) -> None:

        evroute.HEARTBEAT_INTERVAL_S = self._original  # type: ignore[assignment]


def _fast_heartbeat(seconds: float = 0.05) -> _FastHeartbeat:
    return _FastHeartbeat(seconds)


# ── /api/events ────────────────────────────────────────────────


def test_api_events_emits_snapshot_on_connect(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    async def _run() -> tuple[list[dict[str, str]], dict[str, Any]]:
        async with inventory_harness(tmp_path) as harness:
            with _fast_heartbeat():
                request = _FakeRequest(disconnect_after=2, app=harness.app)
                stream = _stream_events(cast(Any, request))
                records = await _drain_sse(stream, max_records=2)
        snapshot_payload = json.loads(records[0]["data"])
        return records, snapshot_payload

    records, snapshot = asyncio.run(_run())
    assert records[0]["event"] == "fs.snapshot"
    assert records[0]["id"] == "0"
    assert snapshot["scope"] == "root-depth-2"
    assert snapshot["complete"] is True
    paths = {e["path"] for e in snapshot["entries"]}
    assert "sub1" in paths
    assert "sub1/file_b.log" in paths


def test_api_events_scope_query_param_drives_snapshot_scope(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    async def _run(scope: str) -> str:
        async with inventory_harness(tmp_path) as harness:
            with _fast_heartbeat():
                request = _FakeRequest({"scope": scope}, disconnect_after=1, app=harness.app)
                stream = _stream_events(cast(Any, request))
                records = await _drain_sse(stream, max_records=1)
        return json.loads(records[0]["data"])["scope"]

    assert asyncio.run(_run("all-known")) == "all-known"
    # Garbage scope falls back to root-depth-2.
    assert asyncio.run(_run("garbage")) == "root-depth-2"


def test_all_known_snapshot_pages_directory_heavy_scope_losslessly(tmp_path: Path) -> None:
    for index in range(7):
        (tmp_path / f"directory-{index}").mkdir()

    async def run() -> set[str]:
        async with inventory_harness(
            tmp_path,
            config=InventoryConfig(max_files=1, watch_mode="off"),
        ) as harness:
            snapshot = await harness.bus.snapshot("all-known")
            return {entry.path for entry in snapshot.entries}

    assert asyncio.run(run()) == {"", *(f"directory-{index}" for index in range(7))}


def test_snapshot_handoff_drops_a_change_already_covered_by_the_snapshot(
    tmp_path: Path,
) -> None:
    target = tmp_path / "recreated.txt"
    target.write_text("old", encoding="utf-8")

    async def run() -> tuple[set[str], bool]:
        async with inventory_harness(tmp_path) as harness:
            await harness.bus.close()
            before, _version, _state = await harness.runtime.coordinator.checkpoint()
            target.unlink()
            await harness.runtime.coordinator.refresh(
                RefreshRequest(
                    observations=(
                        RefreshObservation(
                            path="recreated.txt",
                            kind=ObservationKind.DELETED,
                        ),
                    )
                )
            )
            changes = harness.runtime.coordinator.changes(after=before)
            for _attempt in range(4):
                stale = await asyncio.wait_for(anext(changes), timeout=1.0)
                if "recreated.txt" in stale.dirty_paths:
                    break
            else:
                raise AssertionError("delete refresh did not emit its path")
            await changes.aclose()

            target.write_text("new", encoding="utf-8")
            await harness.runtime.coordinator.refresh(
                RefreshRequest(
                    observations=(
                        RefreshObservation(
                            path="recreated.txt",
                            kind=ObservationKind.CREATED,
                        ),
                    )
                )
            )
            snapshot, queue = await harness.bus.snapshot_and_attach("all-known")
            await harness.bus._project_change(stale)
            return {entry.path for entry in snapshot.entries}, queue.empty()

    snapshot_paths, queue_is_empty = asyncio.run(run())
    assert "recreated.txt" in snapshot_paths
    assert queue_is_empty


def test_api_events_snapshot_supersedes_preconnect_ring_entries(tmp_path: Path) -> None:
    """A reconnect never applies a pre-snapshot ring suffix afterward."""

    _build_tree(tmp_path)

    async def _run() -> list[dict[str, str]]:
        async with inventory_harness(tmp_path) as harness:
            for i in range(5):
                harness.bus.publish(Heartbeat(ts_ns=i))
            with _fast_heartbeat():
                request = _FakeRequest(
                    headers={"Last-Event-ID": "2"},
                    disconnect_after=2,
                    app=harness.app,
                )
                stream = _stream_events(cast(Any, request))
                return await _drain_sse(stream, max_records=10)

    records = asyncio.run(_run())
    snapshot, *later = records
    assert snapshot["event"] == "fs.snapshot"
    assert all(record["event"] != "heartbeat" for record in later)


def test_event_bus_overflow_restarts_slow_connection(tmp_path: Path) -> None:
    async def _run() -> tuple[int, object]:
        original_size = evroute.PER_CONNECTION_QUEUE_SIZE
        evroute.PER_CONNECTION_QUEUE_SIZE = 1
        try:
            async with inventory_harness(tmp_path) as harness:
                queue = harness.bus.attach_connection()
                harness.bus.publish(Heartbeat(ts_ns=1))
                harness.bus.publish(Heartbeat(ts_ns=2))
                return harness.bus.connection_count(), queue.get_nowait().event
        finally:
            evroute.PER_CONNECTION_QUEUE_SIZE = original_size

    connection_count, event = asyncio.run(_run())
    assert connection_count == 0
    assert isinstance(event, FsResyncRequired)
    assert event.reason == "connection_queue_overflow"


def test_event_bus_defers_provider_projection_until_a_browser_connects(
    tmp_path: Path,
) -> None:
    async def _run() -> tuple[int, object]:
        async with inventory_harness(tmp_path) as harness:
            await harness.bus.close()
            first_cursor, _version, _state = await harness.runtime.coordinator.checkpoint()
            first = tmp_path / "first.txt"
            first.write_text("first", encoding="utf-8")
            await harness.runtime.coordinator.refresh(
                RefreshRequest(
                    observations=(
                        RefreshObservation(
                            path="first.txt",
                            kind=ObservationKind.CREATED,
                        ),
                    )
                )
            )
            first_changes = harness.runtime.coordinator.changes(after=first_cursor)
            for _attempt in range(4):
                first_change = await asyncio.wait_for(anext(first_changes), timeout=1.0)
                if "first.txt" in first_change.dirty_paths:
                    break
            else:
                raise AssertionError("first refresh did not emit its path")
            await first_changes.aclose()
            await harness.bus._project_change(first_change)
            projected_without_browser = harness.bus.latest_id()

            queue = harness.bus.attach_connection()
            second_cursor, _version, _state = await harness.runtime.coordinator.checkpoint()
            second = tmp_path / "second.txt"
            second.write_text("second", encoding="utf-8")
            await harness.runtime.coordinator.refresh(
                RefreshRequest(
                    observations=(
                        RefreshObservation(
                            path="second.txt",
                            kind=ObservationKind.CREATED,
                        ),
                    )
                )
            )
            second_changes = harness.runtime.coordinator.changes(after=second_cursor)
            for _attempt in range(4):
                second_change = await asyncio.wait_for(anext(second_changes), timeout=1.0)
                if "second.txt" in second_change.dirty_paths:
                    break
            else:
                raise AssertionError("second refresh did not emit its path")
            await second_changes.aclose()
            await harness.bus._project_change(second_change)
            for _attempt in range(len(second_change.dirty_paths) + 2):
                connected = (await asyncio.wait_for(queue.get(), timeout=1.0)).event
                if isinstance(connected, FsChange):
                    break
            else:
                raise AssertionError("connected browser did not receive the filesystem change")
            return projected_without_browser, connected

    projected_without_browser, connected_event = asyncio.run(_run())
    assert projected_without_browser == 0
    assert isinstance(connected_event, FsChange)
    upserted = {
        operation.entry.path for operation in connected_event.ops if isinstance(operation, FsUpsert)
    }
    assert "second.txt" in upserted


def test_root_replacement_refreshes_connected_browsers(tmp_path: Path) -> None:
    async def _run() -> tuple[int, object]:
        old_root = tmp_path / "old"
        new_root = tmp_path / "new"
        old_root.mkdir()
        new_root.mkdir()
        async with inventory_harness(old_root) as harness:
            queue = harness.bus.attach_connection()
            await harness.runtime.replace_root(new_root)
            event = await asyncio.wait_for(queue.get(), timeout=1.0)
            return harness.bus.connection_count(), event.event

    connection_count, event = asyncio.run(_run())
    assert connection_count == 0
    assert isinstance(event, FsResyncRequired)
    assert event.reason == "coordinator_reset"


def test_resync_marker_ends_stream_after_delivery(tmp_path: Path) -> None:
    async def _run() -> tuple[str, bool]:
        async with inventory_harness(tmp_path) as harness:
            request = _FakeRequest(app=harness.app)
            stream = _stream_events(cast(Any, request))
            await anext(stream)
            harness.bus.publish(FsResyncRequired(reason="test_gap"))
            frame = await asyncio.wait_for(anext(stream), timeout=1.0)
            records = list(parse_sse_frames(frame))
            ended = False
            with _fast_heartbeat(0.01):
                try:
                    await asyncio.wait_for(anext(stream), timeout=1.0)
                except StopAsyncIteration:
                    ended = True
            return records[0]["event"], ended

    event_type, ended = asyncio.run(_run())
    assert event_type == "fs.resync_required"
    assert ended is True


def test_root_depth_scope_filters_live_fs_change_ops() -> None:
    def entry(path: str, parent: str, name: str) -> FsEntry:
        return FsEntry(
            path=path,
            parent=parent,
            name=name,
            type="file",
            ext=".log",
            kind="file",
            size=1,
            mtime_ns=1,
            mtime_hash="",
            active=False,
        )

    event = FsChange(
        ops=(
            FsUpsert(entry=entry("runs/local", "runs", "local")),
            FsUpsert(entry=entry("runs/local/deep.log", "runs/local", "deep.log")),
            FsRemove(path="runs/local/deeper/leaf.log"),
        )
    )

    filtered = _filter_event_for_scope(event, "root-depth-2")
    assert isinstance(filtered, FsChange)
    paths = [op.entry.path if isinstance(op, FsUpsert) else op.path for op in filtered.ops]
    assert paths == ["runs/local"]
    assert _filter_event_for_scope(event, "all-known") is event
    assert (
        _filter_event_for_scope(
            FsChange(ops=(FsRemove(path="runs/local/deeper/leaf.log"),)),
            "root-depth-2",
        )
        is None
    )


# ── /api/index/meta ────────────────────────────────────────────


def test_api_index_progress_payload_shape(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    async def _run() -> dict[str, Any]:
        async with inventory_harness(tmp_path) as harness:
            resp = await api_index_progress(cast(Any, _FakeRequest(app=harness.app)))
            return json.loads(bytes(resp.body))

    body = asyncio.run(_run())
    for field in (
        "status",
        "indexed_files",
        "max_files",
        "truncated",
        "complete",
        "active",
    ):
        assert field in body, f"missing field {field!r}"
    assert body["status"] in ("idle", "scanning", "done", "truncated")
    assert body["indexed_files"] == 3
    assert body["complete"] is True
    assert body["active"] is False


def test_api_index_progress_etag_round_trip(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    async def _run() -> tuple[int, str, int]:
        async with inventory_harness(tmp_path) as harness:
            resp1 = await api_index_progress(cast(Any, _FakeRequest(app=harness.app)))
            etag = resp1.headers.get("etag", "")
            resp2 = await api_index_progress(
                cast(
                    Any,
                    _FakeRequest(headers={"If-None-Match": etag}, app=harness.app),
                )
            )
            return resp1.status_code, etag, resp2.status_code

    status1, etag, status2 = asyncio.run(_run())
    assert status1 == 200
    assert etag
    assert status2 == 304


def test_api_index_progress_does_not_304_while_active(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    _build_tree(tmp_path)

    async def _run() -> tuple[int, str, str]:
        import metabrowser.inventory_engine.providers.python_inventory as python_provider

        release = asyncio.Event()

        async def blocked_walk(*_args: object, **_kwargs: object) -> AsyncIterator[object]:
            await release.wait()
            if False:
                yield object()

        monkeypatch.setattr(python_provider, "walk_tree", blocked_walk)
        async with inventory_harness(tmp_path, settle=False) as harness:
            resp1 = await api_index_progress(cast(Any, _FakeRequest(app=harness.app)))
            etag = resp1.headers.get("etag", "")
            resp2 = await api_index_progress(
                cast(
                    Any,
                    _FakeRequest(headers={"If-None-Match": etag}, app=harness.app),
                )
            )
            return resp2.status_code, etag, bytes(resp2.body).decode()

    status, etag, body = asyncio.run(_run())
    assert etag
    assert status == 200
    assert '"active":true' in body


def test_pending_tally_diagnostic_correlates_client_and_inventory_state(
    tmp_path: Path,
    caplog: Any,
) -> None:
    _build_tree(tmp_path)

    async def _run() -> dict[str, Any]:
        async with inventory_harness(tmp_path) as harness:
            payload = {
                "diagnostic_id": "pending-tally-test-1",
                "elapsed_ms": 5_100,
                "pending": {"sample": [{"path": "sub1"}]},
            }
            request = _FakeRequest(
                headers={"Content-Type": "application/json"},
                body=json.dumps(payload).encode(),
                app=harness.app,
            )
            response = await api_pending_tally_diagnostic(cast(Any, request))
            return json.loads(bytes(response.body))

    with caplog.at_level("WARNING", logger="metabrowser.events_route"):
        body = asyncio.run(_run())

    assert body["diagnostic_id"] == "pending-tally-test-1"
    assert body["inventory"]["status"] == "done"
    assert body["inventory"]["walker_task"] == "done"
    assert body["inventory"]["requested_paths"] == [
        {
            "path": "sub1",
            "known": True,
            "pending": False,
            "generation": 0,
            "direct_children": 1,
            "descendant_files": 1,
            "descendant_size": 100,
            "descendant_leaves": 1,
            "type": "dir",
            "total_files": 1,
            "total_size": 100,
            "newest_mtime_ns": body["inventory"]["requested_paths"][0]["newest_mtime_ns"],
            "empty": False,
            "write_generation": 0,
        }
    ]
    assert "pending-tally-test-1" in caplog.text
    assert '"elapsed_ms":5100' in caplog.text
    assert '"status":"done"' in caplog.text


def test_pending_tally_diagnostic_rejects_oversized_payload() -> None:
    request = _FakeRequest(
        headers={"Content-Length": "70000"},
        body=b"{}",
    )
    response = asyncio.run(api_pending_tally_diagnostic(cast(Any, request)))
    assert response.status_code == 413


def test_pending_tally_diagnostic_stops_reading_chunked_payload_at_limit() -> None:
    request = _FakeRequest(
        body_chunks=[b"a" * 40_000, b"b" * 30_000, b"must-not-be-read"],
    )

    response = asyncio.run(api_pending_tally_diagnostic(cast(Any, request)))

    assert response.status_code == 413
    assert request.streamed_chunks == 2


def test_api_index_meta_payload_shape(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    async def _run() -> dict[str, Any]:
        async with inventory_harness(tmp_path) as harness:
            resp = await api_index_meta(cast(Any, _FakeRequest(app=harness.app)))
            return json.loads(bytes(resp.body))

    body = asyncio.run(_run())
    for field in (
        "status",
        "indexed_files",
        "indexed_dirs",
        "max_files",
        "truncated",
        "complete",
        "oldest_mtime_ns",
        "newest_mtime_ns",
        "suffixes",
    ):
        assert field in body, f"missing field {field!r}"
    assert body["status"] in ("idle", "scanning", "done", "truncated")
    assert body["indexed_files"] == 3  # 3 files in fixture
    assert body["complete"] is True
    # The fixture uses .log so the suffix tally should reflect that.
    assert any(s["ext"] == ".log" and s["count"] == 3 for s in body["suffixes"])


def test_api_index_meta_etag_round_trip(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    async def _run() -> tuple[int, str, int]:
        async with inventory_harness(tmp_path) as harness:
            resp1 = await api_index_meta(cast(Any, _FakeRequest(app=harness.app)))
            etag = resp1.headers.get("etag", "")
            resp2 = await api_index_meta(
                cast(
                    Any,
                    _FakeRequest(headers={"If-None-Match": etag}, app=harness.app),
                )
            )
            return resp1.status_code, etag, resp2.status_code

    status1, etag, status2 = asyncio.run(_run())
    assert status1 == 200
    assert etag
    assert status2 == 304


# ── /api/capabilities ─────────────────────────────────────────


def test_api_capabilities_shape_with_fs_type_detection(tmp_path: Path) -> None:
    """``backends`` reports the real filesystem-type-driven mode
    (native vs polling). On the dev container the underlying
    fs may be ext4/tmpfs (native) or unrecognized (polling); we
    assert the shape is correct either way."""

    _build_tree(tmp_path)

    async def _run() -> dict[str, Any]:

        original = paths_safe._resolved_root_dir
        paths_safe._resolved_root_dir = lambda: tmp_path  # type: ignore[assignment]
        try:
            async with inventory_harness(tmp_path) as harness:
                resp = await api_capabilities(cast(Any, _FakeRequest(app=harness.app)))
        finally:
            paths_safe._resolved_root_dir = original  # type: ignore[assignment]
        return json.loads(bytes(resp.body))

    body = asyncio.run(_run())
    assert set(body.keys()) == {"backends", "index", "events"}
    assert len(body["backends"]) == 1
    assert body["backends"][0]["prefix"] == "."
    assert body["backends"][0]["mode"] in ("native", "polling")
    # Reason must be informative — either fs=<type>, fs-type-unknown,
    # or no-root-set / fs-type-detect-failed.
    assert body["backends"][0]["reason"]
    assert "indexed_files" in body["index"]
    assert body["events"]["stream"] in ("live", "polling")


# ── parse_sse_frames ─────────────────────────────────────────


def test_parse_sse_frames_round_trips_comment_and_data() -> None:
    blob = b': heartbeat\n\nevent: fs.change\nid: 7\ndata: {"a":1}\n\n'
    out = list(parse_sse_frames(blob))
    assert out[0] == {"event": "comment", "id": "", "data": "heartbeat"}
    assert out[1]["event"] == "fs.change"
    assert out[1]["id"] == "7"
    assert json.loads(out[1]["data"]) == {"a": 1}


# ── Heartbeat keepalive ───────────────────────────────────────


def test_api_events_heartbeat_arrives_when_producer_quiet(tmp_path: Path) -> None:
    """When no fs.change ops are produced for HEARTBEAT_INTERVAL_S,
    a comment frame arrives so proxies don't cull the connection."""

    _build_tree(tmp_path)

    async def _run() -> list[dict[str, str]]:
        async with inventory_harness(tmp_path) as harness:
            with _fast_heartbeat():
                request = _FakeRequest(disconnect_after=20, app=harness.app)
                stream = _stream_events(cast(Any, request))
                return await _drain_sse(stream, max_records=10)

    records = asyncio.run(_run())
    events = [r["event"] for r in records]
    assert "comment" in events, f"expected heartbeat comment; got {events}"


def test_heartbeat_interval_default_matches_spec() -> None:
    """Spec section 'Wire and proxy hygiene' pins the cadence."""
    assert HEARTBEAT_INTERVAL_S == 15.0
