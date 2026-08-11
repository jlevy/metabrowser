"""Unit tests for ``metabrowser.events``.

Pins the wire-format and ring-buffer invariants the streaming spec
relies on:

* ``RingBuffer`` overflow drops the oldest envelope and ids stay
  monotonic across the drop.
* ``RingBuffer.since(last_id)`` returns only envelopes strictly
  newer than ``last_id``; a ``last_id`` below the buffer's head
  surfaces as a gap (first returned id > last_id + 1).
* ``encode_sse`` emits a single SSE frame with the expected
  ``event:`` / ``id:`` / ``data:`` lines and a JSON payload that
  carries the ``type`` discriminator.
* Each ``StreamEvent`` variant round-trips through ``encode_sse``
  and ``json.loads`` without losing fields.
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace

from metabrowser.events import (
    CapabilityUpdate,
    FileAppend,
    FileClosed,
    FileCoalesced,
    FileRotate,
    FileTruncate,
    FsChange,
    FsEntry,
    FsRemove,
    FsResyncRequired,
    FsSnapshot,
    FsUpsert,
    Heartbeat,
    ParserReset,
    ProjectionInvalidate,
    ProjectionUpdate,
    RingBuffer,
    encode_heartbeat_comment,
    encode_sse,
)


def _make_file_entry(path: str = "a/b/c.log", size: int = 100) -> FsEntry:
    return FsEntry(
        path=path,
        parent="/".join(path.split("/")[:-1]),
        name=path.split("/")[-1],
        type="file",
        ext=".log",
        kind="file",
        size=size,
        mtime_ns=1_000_000_000,
        mtime_hash="abc",
        active=False,
    )


def _make_dir_entry(
    path: str = "a", *, total_files: int | None = None, has_children: bool | None = None
) -> FsEntry:
    return FsEntry(
        path=path,
        parent="",
        name=path.split("/")[-1],
        type="dir",
        ext="",
        kind="dir",
        size=0,
        mtime_ns=0,
        mtime_hash="",
        active=False,
        total_files=total_files,
        total_size=0 if total_files is not None else None,
        newest_mtime_ns=0 if total_files is not None else None,
        has_children=has_children,
    )


# ── RingBuffer ──────────────────────────────────────────────────


def test_ring_buffer_capacity_required_positive() -> None:
    try:
        RingBuffer(0)
    except ValueError:
        return
    raise AssertionError("expected ValueError for capacity=0")


def test_ring_buffer_ids_monotonic_from_one() -> None:
    rb = RingBuffer(capacity=4)
    e1 = rb.append(Heartbeat(ts_ns=1))
    e2 = rb.append(Heartbeat(ts_ns=2))
    e3 = rb.append(Heartbeat(ts_ns=3))
    assert (e1.id, e2.id, e3.id) == (1, 2, 3)
    assert rb.latest_id == 3


def test_ring_buffer_overflow_drops_oldest_ids_keep_climbing() -> None:
    rb = RingBuffer(capacity=3)
    envelopes = [rb.append(Heartbeat(ts_ns=i)) for i in range(5)]
    # ids never reset
    assert [e.id for e in envelopes] == [1, 2, 3, 4, 5]
    # Buffer holds last 3
    remaining = rb.since(0)
    assert [e.id for e in remaining] == [3, 4, 5]
    assert rb.latest_id == 5


def test_ring_buffer_since_caught_up_returns_empty() -> None:
    rb = RingBuffer(capacity=3)
    rb.append(Heartbeat(ts_ns=1))
    rb.append(Heartbeat(ts_ns=2))
    assert rb.since(rb.latest_id) == []


def test_ring_buffer_since_returns_only_newer() -> None:
    rb = RingBuffer(capacity=10)
    for i in range(5):
        rb.append(Heartbeat(ts_ns=i))
    out = rb.since(2)
    assert [e.id for e in out] == [3, 4, 5]


def test_ring_buffer_since_below_head_signals_gap() -> None:
    rb = RingBuffer(capacity=3)
    for i in range(5):
        rb.append(Heartbeat(ts_ns=i))
    # head id is 3; client asking for last_id=0 should receive 3,4,5
    # and the caller can detect the gap because first.id (3) > 0 + 1.
    out = rb.since(0)
    assert [e.id for e in out] == [3, 4, 5]
    assert out[0].id != 1  # gap signal — head scrolled out


# ── encode_sse — frame format ──────────────────────────────────


def test_encode_sse_frame_shape_and_payload() -> None:
    rb = RingBuffer(capacity=4)
    env = rb.append(Heartbeat(ts_ns=42))
    frame = encode_sse(env).decode("utf-8")
    # exactly one event/id/data triple, terminated by a blank line
    assert frame.endswith("\n\n")
    lines = frame.rstrip("\n").split("\n")
    assert lines[0] == "event: heartbeat"
    assert lines[1] == f"id: {env.id}"
    assert lines[2].startswith("data: ")
    payload = json.loads(lines[2][len("data: ") :])
    assert payload == {"ts_ns": 42, "type": "heartbeat"}


def test_encode_heartbeat_comment_minimal_keepalive() -> None:
    out = encode_heartbeat_comment()
    assert out == b": heartbeat\n\n"


# ── Round-trip per event variant ────────────────────────────────


from typing import Any

from metabrowser.events import StreamEvent


def _round_trip(event: StreamEvent) -> dict[str, Any]:
    rb = RingBuffer(capacity=2)
    env = rb.append(event)
    frame = encode_sse(env).decode("utf-8")
    data_line = next(line for line in frame.split("\n") if line.startswith("data: "))
    return json.loads(data_line[len("data: ") :])


def test_round_trip_fs_snapshot() -> None:
    snap = FsSnapshot(
        scope="root-depth-2",
        entries=(
            _make_dir_entry("a", total_files=3, has_children=True),
            _make_file_entry("a/b.log", 50),
        ),
        complete=False,
    )
    out = _round_trip(snap)
    assert out["type"] == "fs.snapshot"
    assert out["scope"] == "root-depth-2"
    assert out["complete"] is False
    assert len(out["entries"]) == 2
    # FsEntry inner fields preserved
    assert out["entries"][0]["path"] == "a"
    assert out["entries"][0]["total_files"] == 3
    assert out["entries"][0]["has_children"] is True
    assert out["entries"][1]["size"] == 50


def test_round_trip_fs_change_with_upsert_and_remove() -> None:
    change = FsChange(
        ops=(
            FsUpsert(entry=_make_file_entry("a/b.log", 99)),
            FsRemove(path="a/c.log"),
        )
    )
    out = _round_trip(change)
    assert out["type"] == "fs.change"
    assert len(out["ops"]) == 2
    assert out["ops"][0]["op"] == "upsert"
    assert out["ops"][0]["entry"]["path"] == "a/b.log"
    assert out["ops"][1] == {"path": "a/c.log", "op": "remove"}


def test_round_trip_fs_resync_required() -> None:
    out = _round_trip(FsResyncRequired(reason="root_swap"))
    assert out == {"reason": "root_swap", "type": "fs.resync_required"}


def test_round_trip_capability_update() -> None:
    cap = CapabilityUpdate(
        backends=({"prefix": ".", "mode": "polling", "reason": "fs=nfs"},),
        index={"complete": True, "indexed_files": 4231, "max_files": 20000},
        events={"stream": "live", "reason": "watchfiles+app-log"},
    )
    out = _round_trip(cap)
    assert out["type"] == "capability.update"
    assert out["backends"][0]["mode"] == "polling"
    assert out["index"]["indexed_files"] == 4231


def test_round_trip_projection_events() -> None:
    inv = _round_trip(ProjectionInvalidate(path="a/b.jsonl", projection="charts"))
    assert inv == {"path": "a/b.jsonl", "projection": "charts", "type": "projection.invalidate"}
    upd = _round_trip(
        ProjectionUpdate(
            path="a/b.jsonl",
            projection="charts",
            payload={"series": [1, 2, 3]},
        )
    )
    assert upd["type"] == "projection.update"
    assert upd["payload"] == {"series": [1, 2, 3]}


def test_round_trip_tail_events() -> None:
    out = _round_trip(FileAppend(path="a.log", from_offset=0, to_offset=128, bytes_b64="aGk="))
    assert out["type"] == "file.append"
    assert (out["from_offset"], out["to_offset"]) == (0, 128)
    assert out["bytes_b64"] == "aGk="
    assert _round_trip(FileTruncate(path="a.log", new_size=0))["type"] == "file.truncate"
    assert _round_trip(FileRotate(path="a.log", new_inode=42))["type"] == "file.rotate"
    assert _round_trip(FileClosed(path="a.log"))["type"] == "file.closed"
    coalesced = _round_trip(FileCoalesced(path="a.log", dropped_count=15))
    assert coalesced == {"path": "a.log", "dropped_count": 15, "type": "file.coalesced"}
    reset = _round_trip(ParserReset(path="a.log", reason="memory_budget"))
    assert reset["type"] == "parser.reset"


def test_fs_entry_dir_aggregates_default_to_none() -> None:
    """Walker emits placeholder dirs with None aggregates so the
    client renders skeleton cells. Keep that default explicit."""
    e = _make_dir_entry("d")
    assert e.total_files is None
    assert e.total_size is None
    assert e.newest_mtime_ns is None


def test_fs_entry_is_frozen_for_safe_replace() -> None:
    """FsEntry is frozen: walker writes via dataclasses.replace,
    not in-place mutation. This is what makes generation-counter
    races safe."""

    e = _make_dir_entry("d")
    e2 = replace(e, total_files=5, total_size=100)
    assert e.total_files is None  # original unchanged
    assert e2.total_files == 5
    # ``setattr`` round-trip dodges the static analyzer so the
    # runtime check actually executes; the frozen-ness is a runtime
    # contract, not a typing one.
    try:
        setattr(e, "total_files", 99)  # noqa: B010
    except FrozenInstanceError:
        return
    raise AssertionError("expected FrozenInstanceError on direct mutation")
