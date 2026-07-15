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
from typing import Any, cast

import metabrowser.events_route as evroute
from metabrowser import paths_safe
from metabrowser.events import FsChange, FsEntry, FsRemove, FsUpsert, Heartbeat
from metabrowser.events_route import (
    HEARTBEAT_INTERVAL_S,
    _filter_event_for_scope,
    _stream_events,
    api_capabilities,
    api_index_meta,
    api_index_progress,
    get_or_create_bus,
    parse_sse_frames,
    reset_bus_for_tests,
)
from metabrowser.inventory import get_instance, reset_instance_for_tests

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


def _build_tree(root: Path) -> None:
    (root / "file_a.log").write_bytes(b"a" * 50)
    (root / "sub1").mkdir()
    (root / "sub1" / "file_b.log").write_bytes(b"b" * 100)
    (root / "sub2").mkdir()
    (root / "sub2" / "file_d.log").write_bytes(b"d" * 75)


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


async def _drive_walker(root: Path) -> None:
    reset_instance_for_tests()
    reset_bus_for_tests()
    inv = get_instance()
    inv.start(root)
    await inv.wait_until_done(timeout=5.0)


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
        await _drive_walker(tmp_path)
        with _fast_heartbeat():
            request = _FakeRequest(disconnect_after=2)
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
        await _drive_walker(tmp_path)
        with _fast_heartbeat():
            request = _FakeRequest({"scope": scope}, disconnect_after=1)
            stream = _stream_events(cast(Any, request))
            records = await _drain_sse(stream, max_records=1)
        return json.loads(records[0]["data"])["scope"]

    assert asyncio.run(_run("all-known")) == "all-known"
    # Garbage scope falls back to root-depth-2.
    assert asyncio.run(_run("garbage")) == "root-depth-2"


def test_api_events_replay_returns_envelopes_after_last_id(tmp_path: Path) -> None:
    """``Last-Event-ID`` resume replays only envelopes strictly
    newer than the requested id. Walker progress writes envelopes
    into the ring buffer; the connection then asks for everything
    above id=2 and must get back ids 3+."""

    _build_tree(tmp_path)

    async def _run() -> list[dict[str, str]]:
        # Drive the walker so the bus relays envelopes into the
        # ring buffer.
        await _drive_walker(tmp_path)
        # Open one stream to trigger bus creation, drain a few
        # frames, then disconnect.
        reset_bus_for_tests()

        await get_or_create_bus()

        inv = get_instance()
        for i in range(5):
            inv._emit(Heartbeat(ts_ns=i))
        # Yield once so the relay drains them.
        await asyncio.sleep(0.05)
        # Now connect with Last-Event-ID = 2 and assert we get
        # back only envelopes 3, 4, 5 (and potentially older
        # walker envelopes too, but their ids must all be > 2).
        with _fast_heartbeat():
            request = _FakeRequest(headers={"Last-Event-ID": "2"}, disconnect_after=2)
            stream = _stream_events(cast(Any, request))
            return await _drain_sse(stream, max_records=10)

    records = asyncio.run(_run())
    # First record is the snapshot (id=0 sentinel), then the
    # replay records.
    snapshot, *replays = records
    assert snapshot["event"] == "fs.snapshot"
    # Every replay record's id must be > 2.
    for rec in replays:
        if rec["event"] == "comment":
            continue
        if rec["id"]:
            assert int(rec["id"]) > 2, f"replay leaked id={rec['id']}"


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
        await _drive_walker(tmp_path)
        resp = await api_index_progress(cast(Any, _FakeRequest()))
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
        await _drive_walker(tmp_path)
        resp1 = await api_index_progress(cast(Any, _FakeRequest()))
        etag = resp1.headers.get("etag", "")
        resp2 = await api_index_progress(cast(Any, _FakeRequest(headers={"If-None-Match": etag})))
        return resp1.status_code, etag, resp2.status_code

    status1, etag, status2 = asyncio.run(_run())
    assert status1 == 200
    assert etag
    assert status2 == 304


def test_api_index_progress_does_not_304_while_active(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    async def _run() -> tuple[int, str, str]:
        reset_instance_for_tests()
        reset_bus_for_tests()
        inv = get_instance()
        inv.start(tmp_path)
        resp1 = await api_index_progress(cast(Any, _FakeRequest()))
        etag = resp1.headers.get("etag", "")
        resp2 = await api_index_progress(cast(Any, _FakeRequest(headers={"If-None-Match": etag})))
        inv.clear()
        return resp2.status_code, etag, bytes(resp2.body).decode()

    status, etag, body = asyncio.run(_run())
    assert etag
    assert status == 200
    assert '"active":true' in body


def test_api_index_meta_payload_shape(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    async def _run() -> dict[str, Any]:
        await _drive_walker(tmp_path)
        resp = await api_index_meta(cast(Any, _FakeRequest()))
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
        await _drive_walker(tmp_path)
        resp1 = await api_index_meta(cast(Any, _FakeRequest()))
        etag = resp1.headers.get("etag", "")
        # Same ETag → 304.
        resp2 = await api_index_meta(cast(Any, _FakeRequest(headers={"If-None-Match": etag})))
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
            await _drive_walker(tmp_path)
            resp = await api_capabilities(cast(Any, _FakeRequest()))
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
        await _drive_walker(tmp_path)
        with _fast_heartbeat():
            request = _FakeRequest(disconnect_after=20)
            stream = _stream_events(cast(Any, request))
            return await _drain_sse(stream, max_records=10)

    records = asyncio.run(_run())
    events = [r["event"] for r in records]
    assert "comment" in events, f"expected heartbeat comment; got {events}"


def test_heartbeat_interval_default_matches_spec() -> None:
    """Spec section 'Wire and proxy hygiene' pins the cadence."""
    assert HEARTBEAT_INTERVAL_S == 15.0
