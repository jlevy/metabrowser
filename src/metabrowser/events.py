"""Typed event model for the browser realtime-streaming surface.

Single source of truth for the event envelope, the discriminated
``StreamEvent`` union, and the SSE wire format. Both
``/api/events`` (inventory channel) and ``/api/tail`` (multiplexed
log-tail channel) emit through these types.

This module is pure types + small helpers — no I/O, no async, no
filesystem access. The walker in
:mod:`metabrowser.inventory` constructs ``FsEntry`` records
and emits ``FsChange`` ops; the route layer wraps them in
``EventEnvelope`` (id + event) and pushes through ``encode_sse``.

Invariants (verified by tests):

* ``RingBuffer`` overflow drops the oldest envelopes; ``Last-Event-ID``
  resume returns only envelopes strictly newer than the requested id.
* Envelope ids are monotonic per-process from 1 (so ``Last-Event-ID: 0``
  asks for the full buffer).
* Round-trip: ``encode_sse(envelope)`` emits a single SSE frame; the
  ``data:`` payload is a JSON object that fully describes the event,
  including its discriminator (``type`` field).
* For directory entries, ``total_files`` / ``total_size`` /
  ``newest_mtime_ns`` may be ``None`` while the walker has not yet
  finalized that directory; clients render skeleton cells in that
  case.
"""

from __future__ import annotations

import json
import os
from collections import deque
from dataclasses import asdict, dataclass
from typing import Any, Literal

from metabrowser.fs_paths import derive_ext

# ── Filesystem entries ──────────────────────────────────────────


@dataclass(slots=True, frozen=True)
class WriteToken:
    """Captured snapshot of the inventory's generation counter for a path.

    A producer that wants race-safety reads the counter at the moment it
    starts observing a path's filesystem state and writes the resulting
    entry with that token. If an :meth:`InventoryIndex.invalidate` bumps
    the counter before the write lands, the inventory drops the write
    rather than overwriting a fresher observation.

    Producers that just observed the filesystem **now** can leave
    ``FsEntry.write_token = None``; the inventory treats the write as a
    fresh observation and stamps it with the current generation at write
    time. The ``None`` vs ``WriteToken`` distinction is type-level so the
    contract is un-confusable — a default ``int`` field cannot be
    accidentally interpreted as "stale snapshot N".
    """

    generation: int


@dataclass(slots=True, frozen=True)
class FsEntry:
    """A single filesystem object — file or directory — as the
    inventory tracks it.

    Files always carry concrete ``size`` / ``mtime_ns``. Directories
    carry their immediate-child count via ``total_files`` (with the
    cumulative subtree count for the recent/tree decoration), but
    those aggregate fields are ``None`` while the walker is still
    finalizing the subtree below them. The walker writes the
    finalized values atomically (``dataclasses.replace``) once the
    subtree is complete.

    ``views`` is the ordered list of preview-pane view ids (see
    :mod:`metabrowser.file_kinds`); empty for dirs.
    ``labels`` is an open dict for run-state, pid-alive, errored,
    plugin badges; meaningful only for files.

    ``write_token`` carries a captured snapshot of the inventory's
    generation counter for race-safety; see :class:`WriteToken`.
    ``None`` means "freshly observed; stamp at write time"; a
    :class:`WriteToken` means the producer captured the counter at
    observation start and the inventory should drop the write if an
    invalidation has bumped the counter since.
    """

    path: str
    parent: str
    name: str
    type: Literal["file", "dir"]
    ext: str
    kind: str
    size: int
    mtime_ns: int
    mtime_hash: str
    active: bool
    views: tuple[str, ...] = ()
    labels: tuple[tuple[str, str], ...] = ()
    # dir aggregates — None while the walker has not yet finalized
    total_files: int | None = None
    total_size: int | None = None
    newest_mtime_ns: int | None = None
    gitignored: bool = False
    # walker bookkeeping (not part of the wire payload)
    write_token: WriteToken | None = None

    @classmethod
    def for_observed_file(
        cls,
        *,
        path: str,
        parent: str,
        name: str,
        size: int,
        mtime_ns: int,
        gitignored: bool = False,
        existing: FsEntry | None = None,
    ) -> FsEntry:
        """Build a freshly-observed file entry.

        Single construction point for the walker (boot scan +
        ``rewalk_subtree``) and the watcher (file-event handler).
        Both producers used to build entries by hand and diverged on
        ext derivation (the watcher used a simple last-dot suffix
        while the walker used the compound-tail heuristic in
        :func:`metabrowser.fs_paths.derive_ext`) — see the senior
        review of the file-watching layer.

        Carries forward ``active`` and ``labels`` from *existing* when
        provided so the watcher's modify path preserves run-state and
        plugin badges across edits. Leaves ``write_token=None`` so
        :meth:`InventoryIndex._store_walker_entry` stamps the entry
        with the current generation at write time.
        """

        return cls(
            path=path,
            parent=parent,
            name=name,
            type="file",
            ext=derive_ext(name),
            kind="file",
            size=size,
            mtime_ns=mtime_ns,
            mtime_hash="",
            active=existing.active if existing else False,
            views=existing.views if existing else (),
            labels=existing.labels if existing else (),
            gitignored=gitignored,
        )

    @classmethod
    def for_observed_dir(
        cls,
        *,
        path: str,
        parent: str,
        name: str,
        gitignored: bool = False,
    ) -> FsEntry:
        """Build a freshly-observed directory placeholder.

        Aggregates (``total_files`` / ``total_size`` /
        ``newest_mtime_ns``) stay ``None`` until the walker finalizes
        the subtree via post-order replacement.
        """

        return cls(
            path=path,
            parent=parent,
            name=name,
            type="dir",
            ext="",
            kind="dir",
            size=0,
            mtime_ns=0,
            mtime_hash="",
            active=False,
            gitignored=gitignored,
        )

    @classmethod
    def for_stat(
        cls,
        *,
        path: str,
        parent: str,
        name: str,
        stat: os.stat_result,
        gitignored: bool = False,
        existing: FsEntry | None = None,
    ) -> FsEntry:
        """Build a freshly-observed file entry from a ``stat_result``.

        Convenience wrapper for the watcher path where the producer
        already holds an ``os.stat_result``. Equivalent to
        :meth:`for_observed_file` but pulls ``size`` / ``mtime_ns``
        from the stat tuple.
        """

        return cls.for_observed_file(
            path=path,
            parent=parent,
            name=name,
            size=stat.st_size,
            mtime_ns=stat.st_mtime_ns,
            gitignored=gitignored,
            existing=existing,
        )


# ── fs.change ops ───────────────────────────────────────────────
#
# The discriminated union below is the unit of change in the
# inventory plane. Producers (watch backends, app-log backend,
# reconciliation) push ops into the shared queue; the inventory
# consumer batches ops and emits an ``FsChange`` event per drain.


@dataclass(slots=True, frozen=True)
class FsUpsert:
    entry: FsEntry
    op: Literal["upsert"] = "upsert"


@dataclass(slots=True, frozen=True)
class FsRemove:
    path: str
    op: Literal["remove"] = "remove"


FsChangeOp = FsUpsert | FsRemove


# ── StreamEvent union ───────────────────────────────────────────
#
# Each event type carries a string ``type`` discriminator that
# matches the SSE ``event:`` field, plus the JSON payload shape.
# Type-checkers can narrow the union via the ``type`` literal.


@dataclass(slots=True, frozen=True)
class FsSnapshot:
    """Initial-connect dump of inventory state at a chosen scope."""

    scope: Literal["root-depth-2", "recent-top-N", "expanded-prefixes", "all-known"]
    entries: tuple[FsEntry, ...]
    complete: bool
    type: Literal["fs.snapshot"] = "fs.snapshot"


@dataclass(slots=True, frozen=True)
class FsChange:
    """Batched delta applied since the last snapshot or change."""

    ops: tuple[FsChangeOp, ...]
    type: Literal["fs.change"] = "fs.change"


@dataclass(slots=True, frozen=True)
class FsResyncRequired:
    """Server-restart signal. Client drops state and re-subscribes
    at the same scope it was previously on. NOT emitted for
    slow-consumer disconnects — those force a per-connection close
    and rely on EventSource auto-reconnect to drive a fresh
    snapshot."""

    reason: str
    type: Literal["fs.resync_required"] = "fs.resync_required"


@dataclass(slots=True, frozen=True)
class CapabilityUpdate:
    """Per-mount or global capability change (a watcher demoted to
    polling, the index hitting truncation, etc.). Phase 5 wires
    this for real; Phase 1 emits a single placeholder."""

    backends: tuple[dict[str, str], ...]
    index: dict[str, Any]
    events: dict[str, str]
    type: Literal["capability.update"] = "capability.update"


@dataclass(slots=True, frozen=True)
class ProjectionInvalidate:
    """A derived view (chart, jsonl summary) is now stale for
    *path*. Phase 1 defines the type; producers wire it as the
    ``MtimeCache`` invalidations are folded in."""

    path: str
    projection: str
    type: Literal["projection.invalidate"] = "projection.invalidate"


@dataclass(slots=True, frozen=True)
class ProjectionUpdate:
    """A derived view's new payload is ready. Carries enough for the
    client to swap the rendered view without a refetch."""

    path: str
    projection: str
    payload: dict[str, Any]
    type: Literal["projection.update"] = "projection.update"


@dataclass(slots=True, frozen=True)
class Heartbeat:
    """Empty frame on a 15 s cadence. Keeps proxies / load
    balancers from culling idle SSE connections; client ignores."""

    ts_ns: int
    type: Literal["heartbeat"] = "heartbeat"


# ── tail events (Phase 6 producers; encoder must round-trip today) ──


@dataclass(slots=True, frozen=True)
class FileAppend:
    path: str
    from_offset: int
    to_offset: int
    bytes_b64: str
    type: Literal["file.append"] = "file.append"


@dataclass(slots=True, frozen=True)
class FileTruncate:
    path: str
    new_size: int
    type: Literal["file.truncate"] = "file.truncate"


@dataclass(slots=True, frozen=True)
class FileRotate:
    path: str
    new_inode: int
    type: Literal["file.rotate"] = "file.rotate"


@dataclass(slots=True, frozen=True)
class FileClosed:
    path: str
    type: Literal["file.closed"] = "file.closed"


@dataclass(slots=True, frozen=True)
class FileCoalesced:
    """Per-path token-bucket dropped or merged events for one
    drain. One marker per drain; carries the dropped/merged count
    so the client can show ``[N events coalesced]`` markers."""

    path: str
    dropped_count: int
    type: Literal["file.coalesced"] = "file.coalesced"


@dataclass(slots=True, frozen=True)
class ParserReset:
    """``JsonlTailer`` parser state was force-flushed (memory
    budget breach, process restart). Subscribers should treat as a
    fresh adapter detect from the current cursor, not a silent gap."""

    path: str
    reason: str
    type: Literal["parser.reset"] = "parser.reset"


StreamEvent = (
    FsSnapshot
    | FsChange
    | FsResyncRequired
    | CapabilityUpdate
    | ProjectionInvalidate
    | ProjectionUpdate
    | Heartbeat
    | FileAppend
    | FileTruncate
    | FileRotate
    | FileClosed
    | FileCoalesced
    | ParserReset
)


# ── envelope + ring buffer ──────────────────────────────────────


@dataclass(slots=True, frozen=True)
class EventEnvelope:
    """SSE envelope: monotonic id + the event payload. The id is
    what the client echoes via ``Last-Event-ID`` after a
    disconnect."""

    id: int
    event: StreamEvent


class RingBuffer:
    """Bounded fifo of ``EventEnvelope`` for short-disconnect
    resume.

    Capacity is a soft contract: the buffer holds at most
    ``capacity`` envelopes; oldest are dropped on append once full.
    Ids are monotonic from 1 across the process lifetime — they do
    NOT wrap when the deque does.

    This class is single-process and not thread-safe; callers
    serialize on the inventory's consumer loop.
    """

    __slots__ = ("_buf", "_next_id")

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError(f"RingBuffer capacity must be > 0, got {capacity}")
        self._buf: deque[EventEnvelope] = deque(maxlen=capacity)
        self._next_id: int = 1

    @property
    def capacity(self) -> int:
        return self._buf.maxlen or 0

    @property
    def latest_id(self) -> int:
        """Highest-numbered envelope id that has ever been
        appended. Useful for ``Last-Event-ID`` resume tests; not
        the same as the highest id currently in the buffer (the
        head id may have been dropped)."""
        return self._next_id - 1

    def append(self, event: StreamEvent) -> EventEnvelope:
        envelope = EventEnvelope(id=self._next_id, event=event)
        self._next_id += 1
        self._buf.append(envelope)
        return envelope

    def since(self, last_event_id: int) -> list[EventEnvelope]:
        """Return all buffered envelopes strictly newer than
        ``last_event_id``, in append order.

        Returns an empty list when the requested id is at or above
        the latest id (client is caught up). When the requested id
        is below the buffer's head — i.e., the resume window has
        scrolled out of the ring — returns the full buffer
        contents. Callers detect this case by comparing the first
        returned envelope's id against ``last_event_id + 1``; a
        gap means a fresh snapshot is required.
        """
        if last_event_id >= self.latest_id:
            return []
        return [env for env in self._buf if env.id > last_event_id]


# ── SSE wire format ─────────────────────────────────────────────


def _wire_dict_factory(items: list[tuple[str, Any]]) -> dict[str, Any]:
    """`asdict` dict factory that drops walker-internal bookkeeping.

    ``FsEntry.write_token`` is producer-side race-safety state, never
    part of the client contract; without this filter bare ``asdict``
    would leak it (as ``null`` or ``{"generation": N}``) into every
    entry on the wire. Applied to every dataclass in the tree, so the
    key is stripped wherever it appears.
    """
    return {key: value for key, value in items if key != "write_token"}


def _event_to_dict(event: StreamEvent) -> dict[str, Any]:
    """Serialize an event to a JSON-compatible dict.

    ``dataclasses.asdict`` recursively converts nested dataclasses,
    so an ``FsChange`` with nested ``FsUpsert(entry=FsEntry(...))``
    flattens to the right shape. Tuples become lists; that's fine
    on the wire. ``write_token`` is filtered out (see
    :func:`_wire_dict_factory`).
    """
    return asdict(event, dict_factory=_wire_dict_factory)


def encode_sse(envelope: EventEnvelope) -> bytes:
    """Encode one envelope as a single SSE frame.

    Format::

        event: <type>
        id: <id>
        data: <json>
        \\n

    Frame ends with the blank line that the SSE protocol uses as
    record separator; one frame per call.
    """
    payload = json.dumps(_event_to_dict(envelope.event), separators=(",", ":"))
    return (f"event: {envelope.event.type}\nid: {envelope.id}\ndata: {payload}\n\n").encode()


def encode_heartbeat_comment() -> bytes:
    """Heartbeat comment frame — no event type, just a colon
    comment that proxies tolerate. Cheaper than a full envelope
    when we just need to keep the connection alive."""
    return b": heartbeat\n\n"
