"""SSE routes + lifespan hook for the inventory event plane.

This module owns:

* ``GET /api/events`` — global inventory SSE stream backed by
  :class:`metabrowser.inventory.InventoryIndex`. Emits an
  ``fs.snapshot`` on connect, then ``fs.change`` ops as the
  walker / watcher backends produce them. Heartbeat every 15 s.
  ``Last-Event-ID`` resume from the inventory's process-wide
  ring buffer.
* ``GET /api/index/progress`` — lightweight crawl status for the
  left-nav progress footer. Reads in-memory inventory counters
  only; never scans the tree or rebuilds suffix tallies.
* ``GET /api/index/meta`` — bundled summary of index status,
  suffix tally, and oldest/newest mtime; ETag-cacheable. Folds
  what the search spec called ``/api/index/status`` and
  ``/api/index/suffixes`` into one envelope.
* ``GET /api/capabilities`` — unified capability surface with
  filesystem-type-driven watcher status.
* :func:`build_lifespan` — Starlette lifespan context manager
  that bumps the asyncio default executor to 64 workers and
  spawns the eager ``InventoryIndex`` pre-warm without blocking
  HTTP bind.

Everything in this module is end-to-end testable via
``starlette.testclient.TestClient`` without opening a browser.
The ``aiter_sse_events`` helper at the bottom is the test-side
parser for the SSE wire format.

The endpoint, replay behavior, and encoder form the realtime event contract.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections import Counter
from collections.abc import AsyncIterator, Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from metabrowser.events import (
    EventEnvelope,
    FsChange,
    RingBuffer,
    StreamEvent,
    encode_heartbeat_comment,
    encode_sse,
)
from metabrowser.inventory import InventoryIndex
from metabrowser.inventory import (
    get_instance as get_inventory,
)
from metabrowser.paths_safe import _resolved_root_dir
from metabrowser.settings import (
    DEFAULT_EXECUTOR_WORKERS,
    INDEX_PROGRESS_UPDATE_FILES,
    SSE_BUS_INVENTORY_QUEUE_SIZE,
    SSE_HEARTBEAT_INTERVAL_S,
    SSE_PER_CONNECTION_QUEUE_SIZE,
    SSE_RING_BUFFER_CAPACITY,
)
from metabrowser.watch_backends import select_watch_mode

if TYPE_CHECKING:
    from starlette.applications import Starlette
    from starlette.requests import Request

LOG = logging.getLogger(__name__)


# Aliases kept so external test imports stay stable; authoritative
# values live in :mod:`metabrowser.settings`.
RING_BUFFER_CAPACITY = SSE_RING_BUFFER_CAPACITY
PER_CONNECTION_QUEUE_SIZE = SSE_PER_CONNECTION_QUEUE_SIZE
HEARTBEAT_INTERVAL_S = SSE_HEARTBEAT_INTERVAL_S

VALID_SCOPES: tuple[str, ...] = (
    "root-depth-2",
    "recent-top-N",
    "expanded-prefixes",
    "all-known",
)


# ── Lifespan hook ────────────────────────────────────────────


@asynccontextmanager  # pyright: ignore[reportDeprecated]
async def build_lifespan(
    *,
    root_provider: Callable[[], object] = lambda: None,
) -> AsyncIterator[None]:
    """Starlette lifespan that pre-warms ``InventoryIndex`` and
    raises the asyncio default executor's worker count.

    *root_provider* is a zero-arg callable returning the served
    root path; tests pass an in-place lambda, production wires it
    to ``paths_safe._resolved_root_dir``.

    On startup:
      1. ``loop.set_default_executor(ThreadPoolExecutor(64))`` so
         cache-served handlers don't queue behind slow stat-poll
         threads (default pool is min(32, cpus+4) ≈ 12).
      2. ``inventory.start(root)`` is called (idempotent). The walker
         must move synchronous filesystem setup off the event loop
         before doing real work so startup can bind immediately.

    On shutdown the walker task is cancelled cleanly.
    """

    loop = asyncio.get_running_loop()
    loop.set_default_executor(
        ThreadPoolExecutor(
            max_workers=DEFAULT_EXECUTOR_WORKERS,
            thread_name_prefix="metabrowser",
        )
    )

    inventory = get_inventory()
    root = root_provider()
    walker_task: asyncio.Task[None] | None = None
    active_task: asyncio.Task[None] | None = None
    watcher_task: asyncio.Task[None] | None = None
    if isinstance(root, Path):
        try:
            walker_task = inventory.start(root)
            LOG.info("inventory pre-warm started at %s", root)
        except Exception:
            # Never crash startup because the pre-warm fell over —
            # the lazy path can rebuild on first user action and
            # an unhealthy inventory shouldn't take down the
            # process.
            LOG.exception("inventory pre-warm failed to start")

        # The active-file tracker pushes fs.change ops into the
        # inventory whenever a tracked file's active state flips.
        try:
            from metabrowser.active_tracker import (
                run_active_tracker,
            )

            active_task = asyncio.create_task(
                run_active_tracker(root=root),
                name="metabrowser-active-tracker",
            )
        except Exception:
            LOG.exception("active tracker failed to start")
        # Spawn the filesystem watcher (native on local mounts,
        # polling on NFS / FUSE). Keeps the inventory in sync
        # with on-disk state without a Phase-4 writer event log.
        try:
            from metabrowser.watch_backends import (
                run_watcher,
            )

            watcher_task = asyncio.create_task(
                run_watcher(root=root),
                name="metabrowser-fs-watcher",
            )
        except Exception:
            LOG.exception("fs watcher failed to start")

    try:
        yield
    finally:
        for t in (walker_task, active_task, watcher_task):
            if t is not None and not t.done():
                t.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await t


# ── Process-wide ring buffer ──────────────────────────────────
#
# A single ring buffer per process. Wired into the inventory's
# subscriber queue: every event the inventory emits is also
# appended here, so Last-Event-ID resume can replay a short
# disconnect without bouncing the client back to a fresh
# snapshot.


class _EventBus:
    """Tee from the inventory's subscriber queue to the
    process-wide ring buffer + per-connection queues.

    One bus per process. Spawning the bus is the route layer's
    job — the first request to ``/api/events`` calls
    :func:`get_or_create_bus`, which lazily attaches the bus to
    the inventory and starts the relay task.
    """

    def __init__(self, inventory: InventoryIndex) -> None:
        self._inventory = inventory
        self._ring = RingBuffer(capacity=RING_BUFFER_CAPACITY)
        # The bus's subscription absorbs the full walker burst on
        # startup. Sized larger than DEFAULT_MAX_FILES so the
        # initial fan-out cannot drop the bus from the inventory's
        # subscriber set (which would silence live events for
        # every connection until process restart).
        self._inventory_queue = inventory.subscribe(max_queue=SSE_BUS_INVENTORY_QUEUE_SIZE)
        self._connections: set[asyncio.Queue[EventEnvelope]] = set()
        self._relay_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        async with self._lock:
            if self._relay_task is None or self._relay_task.done():
                self._relay_task = asyncio.create_task(
                    self._relay_loop(), name="metabrowser-events-bus"
                )

    async def _relay_loop(self) -> None:
        # A relay exception must not stop process-wide SSE delivery, and
        # inventory overflow can drop this subscriber queue. Back off after
        # crashes and periodically resubscribe when the queue is detached.
        backoff = 0.5
        while True:
            try:
                while True:
                    try:
                        event = await asyncio.wait_for(
                            self._inventory_queue.get(),
                            timeout=5.0,
                        )
                    except TimeoutError:
                        if not self._inventory.is_subscribed(self._inventory_queue):
                            LOG.warning("events bus: lost inventory subscription; resubscribing")
                            self._inventory_queue = self._inventory.subscribe(
                                max_queue=SSE_BUS_INVENTORY_QUEUE_SIZE,
                            )
                        continue
                    envelope = self._ring.append(event)
                    event_type = getattr(event, "type", type(event).__name__)
                    n_conns = len(self._connections)
                    dead: list[asyncio.Queue[EventEnvelope]] = []
                    for q in self._connections:
                        try:
                            q.put_nowait(envelope)
                        except asyncio.QueueFull:
                            dead.append(q)
                    for q in dead:
                        self._connections.discard(q)
                        LOG.warning("events bus: dropped slow connection")
                    LOG.debug(
                        "events bus: forwarded id=%d type=%s conns=%d dropped=%d",
                        envelope.id,
                        event_type,
                        n_conns,
                        len(dead),
                    )
                    backoff = 0.5
            except asyncio.CancelledError:
                raise
            except Exception:
                LOG.exception("events bus relay crashed; restarting in %.1fs", backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    def attach_connection(self) -> asyncio.Queue[EventEnvelope]:
        q: asyncio.Queue[EventEnvelope] = asyncio.Queue(maxsize=PER_CONNECTION_QUEUE_SIZE)
        self._connections.add(q)
        return q

    def detach_connection(self, q: asyncio.Queue[EventEnvelope]) -> None:
        self._connections.discard(q)

    def replay_since(self, last_event_id: int) -> list[EventEnvelope]:
        return self._ring.since(last_event_id)

    def latest_id(self) -> int:
        return self._ring.latest_id

    def connection_count(self) -> int:
        return len(self._connections)


class _BusSingleton:
    """Module-level holder for the process-wide event bus.
    Wrapping the slot in a class dodges basedpyright's
    constant-naming rule on lowercase mutable slots."""

    instance: _EventBus | None = None


async def get_or_create_bus() -> _EventBus:
    """Lazy bus accessor. The first ``/api/events`` connection
    creates the bus; subsequent connections share it."""

    if _BusSingleton.instance is None:
        _BusSingleton.instance = _EventBus(get_inventory())
    await _BusSingleton.instance.start()
    return _BusSingleton.instance


def reset_bus_for_tests() -> None:
    """Drop the module-level bus. Tests call this between cases
    to avoid one test's events leaking into another."""

    if _BusSingleton.instance is not None and _BusSingleton.instance._relay_task is not None:
        _BusSingleton.instance._relay_task.cancel()
    _BusSingleton.instance = None


# ── /api/events route ────────────────────────────────────────


_ScopeType = Literal["root-depth-2", "recent-top-N", "expanded-prefixes", "all-known"]


def _scope_from_query(request: Request) -> _ScopeType:
    raw = request.query_params.get("scope", "root-depth-2")
    if raw not in VALID_SCOPES:
        raw = "root-depth-2"
    return cast(_ScopeType, raw)


def _parse_last_event_id(request: Request) -> int | None:
    """Honour ``Last-Event-ID`` header (the EventSource API will
    set it after a reconnect). Returns None when the header is
    missing/invalid — the caller treats that as "fresh client" and
    skips replay, since the snapshot already carries current state.
    Replaying the ring buffer to a fresh connection floods it with
    redundant data and pushes live events to the tail of the
    per-connection queue."""

    raw = request.headers.get("Last-Event-ID", "")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _path_depth(path: str) -> int:
    if not path:
        return 0
    return path.count("/") + 1


def _change_path(op: object) -> str:
    entry = getattr(op, "entry", None)
    if entry is not None:
        return str(getattr(entry, "path", ""))
    return str(getattr(op, "path", ""))


def _filter_event_for_scope(event: StreamEvent, scope: _ScopeType) -> StreamEvent | None:
    """Apply the connection's scope to live events.

    A root-depth-2 connection receives only rows it can render, matching
    the scope of its initial snapshot.
    """

    if scope == "all-known":
        return event
    if isinstance(event, FsChange) and scope == "root-depth-2":
        ops = tuple(op for op in event.ops if _path_depth(_change_path(op)) <= 2)
        if not ops:
            return None
        return FsChange(ops=ops)
    return event


def _filter_envelope_for_scope(
    envelope: EventEnvelope,
    scope: _ScopeType,
) -> EventEnvelope | None:
    filtered = _filter_event_for_scope(envelope.event, scope)
    if filtered is None:
        return None
    if filtered is envelope.event:
        return envelope
    return EventEnvelope(id=envelope.id, event=filtered)


async def _stream_events(
    request: Request,
) -> AsyncIterator[bytes]:
    """Yield SSE frames for one /api/events connection."""

    bus = await get_or_create_bus()
    inventory = get_inventory()
    scope = _scope_from_query(request)
    last_id = _parse_last_event_id(request)
    queue = bus.attach_connection()
    client = getattr(request, "client", None)
    client_str = f"{client.host}:{client.port}" if client else "?"
    LOG.debug(
        "sse: attached client=%s scope=%s last_id=%s conns=%d",
        client_str,
        scope,
        last_id,
        bus.connection_count(),
    )

    try:
        # 1) On connect: emit the snapshot at the requested scope.
        snap = inventory.initial_snapshot(scope=scope)
        # The snapshot rides on the next available envelope id by
        # being the first thing the relay forwards after we're
        # attached. For deterministic id ordering we synthesize an
        # envelope locally for the snapshot using a sentinel id of
        # 0 — clients treat snapshot frames as a "reset point".
        snap_envelope = EventEnvelope(id=0, event=snap)
        yield encode_sse(snap_envelope)

        # 2) Resume: replay ring-buffer envelopes strictly newer than
        # the client's last-event-id. Skipped on fresh connects (no
        # Last-Event-ID header) — the snapshot above already carries
        # current state, and replaying the walker's startup burst on
        # every page load floods the per-connection queue and pushes
        # live events to its tail.
        if last_id is not None:
            latest = bus.latest_id()
            if last_id > latest:
                # Server restarted: client's last-known id is from a
                # previous process whose ring buffer is gone. The
                # snapshot above restores current state, while this
                # warning preserves the resume mismatch for diagnostics.
                LOG.warning(
                    "sse: out-of-window Last-Event-ID client=%s last_id=%d > latest=%d "
                    "(server restarted? client may need FsResyncRequired)",
                    client_str,
                    last_id,
                    latest,
                )
            else:
                replay = bus.replay_since(last_id)
                if replay and replay[0].id > last_id + 1:
                    # The resume window has scrolled out of the ring
                    # buffer; client has a gap it can't recover from
                    # without a fresh snapshot.
                    LOG.warning(
                        "sse: ring-buffer gap client=%s last_id=%d first_replay_id=%d "
                        "(buffer scrolled past; client needs re-snapshot)",
                        client_str,
                        last_id,
                        replay[0].id,
                    )
                for env in replay:
                    scoped = _filter_envelope_for_scope(env, scope)
                    if scoped is not None:
                        yield encode_sse(scoped)

        # 3) Live: pull from the per-connection queue with a
        # heartbeat fallback.
        while True:
            if await request.is_disconnected():
                break
            try:
                envelope = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL_S)
                scoped = _filter_envelope_for_scope(envelope, scope)
                if scoped is None:
                    continue
                yield encode_sse(scoped)
                LOG.debug(
                    "sse: yielded id=%d to client=%s",
                    envelope.id,
                    client_str,
                )
            except TimeoutError:
                yield encode_heartbeat_comment()
    finally:
        bus.detach_connection(queue)
        LOG.debug("sse: detached client=%s conns=%d", client_str, bus.connection_count())


async def api_events(request: Request) -> Response:
    """Streaming SSE response. Wire-hygiene headers explicit per
    the spec (``X-Accel-Buffering: no``,
    ``Cache-Control: no-cache``,
    ``Content-Type: text/event-stream``). Gzip is disabled by
    leaving the response body uncompressed and emitting a
    response-level header that the gzip middleware honours
    (skipping ``text/event-stream``)."""

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return StreamingResponse(_stream_events(request), headers=headers)


# ── /api/index/meta ──────────────────────────────────────────


@dataclass(slots=True, frozen=True)
class IndexMeta:
    """One-shot summary of the inventory's current state.

    Folds what the search-spec called ``/api/index/status`` and
    ``/api/index/suffixes`` into one envelope so the filter UI
    only fetches once on focus.
    """

    status: str
    indexed_files: int
    indexed_dirs: int
    max_files: int
    truncated: bool
    complete: bool
    oldest_mtime_ns: int
    newest_mtime_ns: int
    suffixes: list[dict[str, int | str]]


@dataclass(slots=True, frozen=True)
class IndexProgress:
    """Small crawl-progress envelope for frequent UI polling."""

    status: str
    indexed_files: int
    max_files: int
    truncated: bool
    complete: bool
    active: bool


def _build_index_progress(inventory: InventoryIndex) -> IndexProgress:
    status = inventory.status()
    complete = status in ("done", "truncated")
    truncated = status == "truncated"
    return IndexProgress(
        status=status,
        indexed_files=inventory.files_indexed(),
        max_files=inventory.max_files(),
        truncated=truncated,
        complete=complete,
        active=status == "scanning",
    )


def _progress_etag(progress: IndexProgress) -> str:
    # While scanning, expose coarse buckets so the browser can poll
    # cheaply without receiving a 200 for every discovered file.
    count_key = (
        progress.indexed_files // INDEX_PROGRESS_UPDATE_FILES
        if progress.active
        else progress.indexed_files
    )
    return f'"{progress.status}-{count_key}"'


def _build_index_meta(inventory: InventoryIndex, *, suffix_limit: int = 64) -> IndexMeta:
    """Compute the meta envelope from the current index state.
    Cheap (linear in known entries); cached per-call by the
    handler via ETag rather than memoized here."""

    files = 0
    dirs = 0
    oldest = 0
    newest = 0
    suffix_counter: Counter[str] = Counter()
    for e in inventory.entries(scope="all-known"):
        if e.type == "file":
            files += 1
            if e.mtime_ns:
                if oldest == 0 or e.mtime_ns < oldest:
                    oldest = e.mtime_ns
                if e.mtime_ns > newest:
                    newest = e.mtime_ns
            suffix_counter[e.ext] += 1
        else:
            dirs += 1
    suffixes = [
        {"ext": ext, "count": count}
        for ext, count in suffix_counter.most_common(suffix_limit)
        if ext  # drop the empty-string bucket
    ]
    status = inventory.status()
    complete = status in ("done", "truncated")
    truncated = status == "truncated"
    return IndexMeta(
        status=status,
        indexed_files=files,
        indexed_dirs=dirs,
        max_files=inventory.max_files(),
        truncated=truncated,
        complete=complete,
        oldest_mtime_ns=oldest,
        newest_mtime_ns=newest,
        suffixes=suffixes,
    )


async def api_index_progress(request: Request) -> Response:
    """JSON crawl-progress envelope for the nav footer.

    Unlike ``/api/index/meta``, this path does not walk known entries
    for suffix or directory summaries. It reads the inventory's
    counters directly so polling remains cheap while the tree is still
    filling.
    """

    inventory = get_inventory()
    progress = _build_index_progress(inventory)
    etag = _progress_etag(progress)
    if not progress.active and request.headers.get("If-None-Match", "") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    body = json.dumps(asdict(progress), separators=(",", ":")).encode()
    return Response(
        body,
        media_type="application/json",
        headers={"ETag": etag, "Cache-Control": "no-cache"},
    )


# Last encoded catalog body, keyed by its ETag. Holds at most one entry: the
# revision moves on every indexed change, so older bodies are dead weight and
# a full catalog is the largest payload the server produces.
_CATALOG_BODY_CACHE: dict[str, bytes] = {}


def _encode_catalog(files: list[tuple[str, str]], status: str, revision: int) -> bytes:
    """Build the wire envelope and encode it. Runs in a worker thread, so it
    must touch only the private ``files`` snapshot, never the live index."""

    envelope = {
        "complete": status in ("done", "truncated"),
        "truncated": status == "truncated",
        "revision": revision,
        "files": [{"p": p, "e": e} for p, e in files],
    }
    return json.dumps(envelope, separators=(",", ":")).encode()


def _catalog_etag(inventory: InventoryIndex) -> str:
    return f'"{inventory.status()}-{inventory.catalog_revision()}"'


async def api_catalog(request: Request) -> Response:
    """One-shot Quick File catalog: every non-gitignored file at
    ``all-known`` scope in the minimal ``{p, e}`` shape.

    Bulk state rides a plain JSON response instead of the event
    stream because the gzip middleware compresses it (SSE frames are
    never compressed), the ETag makes refetch-after-reconnect a 304
    when nothing changed, and encoding runs off the event loop
    instead of as one synchronous dump inside the stream handler.
    Live updates arrive as ``catalog.change`` events on the existing
    stream; the pair converges without a shared transaction because
    ops are idempotent by path.
    """

    inventory = get_inventory()
    etag = _catalog_etag(inventory)
    if request.headers.get("If-None-Match", "") == etag:
        return Response(status_code=304, headers={"ETag": etag})

    cached = _CATALOG_BODY_CACHE.get(etag)
    if cached is not None:
        return Response(
            cached,
            media_type="application/json",
            headers={"ETag": etag, "Cache-Control": "no-cache"},
        )

    status = inventory.status()
    revision = inventory.catalog_revision()
    # One O(N) pass on the loop, and only one. catalog_files() returns a
    # private list of tuples, so it is a consistent point-in-time snapshot
    # that a worker may traverse without racing the live index — building the
    # wire dicts here as well would have doubled the on-loop cost, which at
    # the 100k design center and 500k cap stalls unrelated requests and the
    # event stream.
    files = inventory.catalog_files()
    body = await asyncio.to_thread(_encode_catalog, files, status, revision)
    # Reconnect storms and multiple tabs re-request the same revision; the
    # ETag turns most of those into 304s, but a client without the ETag (a
    # fresh tab) would otherwise pay the full encode again.
    _CATALOG_BODY_CACHE.clear()
    _CATALOG_BODY_CACHE[etag] = body
    return Response(
        body,
        media_type="application/json",
        headers={"ETag": etag, "Cache-Control": "no-cache"},
    )


async def api_index_meta(request: Request) -> Response:
    """JSON envelope. ETag is the inventory's status + indexed
    file count + walker generation, so a 304 is cheap when
    nothing has finalized since the last poll."""

    inventory = get_inventory()
    meta = _build_index_meta(inventory)
    body = json.dumps(asdict(meta), separators=(",", ":")).encode()
    etag = f'"{meta.status}-{meta.indexed_files}-{meta.indexed_dirs}"'
    if_none_match = request.headers.get("If-None-Match", "")
    if if_none_match and if_none_match == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return Response(
        body,
        media_type="application/json",
        headers={"ETag": etag, "Cache-Control": "no-cache"},
    )


# ── /api/capabilities ────────────────────────────────────────


async def api_capabilities(request: Request) -> JSONResponse:
    """Return capabilities with the filesystem-driven watcher mode.

    ``backends`` reports native versus polling mode via
    :func:`metabrowser.watch_backends.select_watch_mode`."""

    inventory = get_inventory()
    meta = _build_index_meta(inventory, suffix_limit=0)

    backends_payload: list[dict[str, str]]
    try:
        root = _resolved_root_dir()
        if str(root) and root != Path():
            mode, reason = select_watch_mode(root)
            backends_payload = [{"prefix": ".", "mode": mode, "reason": reason}]
        else:
            backends_payload = [{"prefix": ".", "mode": "polling", "reason": "no-root-set"}]
    except Exception:
        LOG.exception("capabilities: fs-type detection failed; reporting polling fallback")
        backends_payload = [{"prefix": ".", "mode": "polling", "reason": "fs-type-detect-failed"}]

    has_native = any(b["mode"] == "native" for b in backends_payload)
    if meta.complete and has_native:
        stream_status, stream_reason = "live", "inventory-done+watchfiles-native"
    elif not meta.complete:
        stream_status, stream_reason = "polling", "inventory-walker-active"
    else:
        stream_status, stream_reason = "polling", "inventory-done+polling-fallback"

    payload = {
        "backends": backends_payload,
        "index": {
            "complete": meta.complete,
            "indexed_files": meta.indexed_files,
            "max_files": meta.max_files,
            "truncated": meta.truncated,
        },
        "events": {
            "stream": stream_status,
            "reason": stream_reason,
        },
    }
    return JSONResponse(payload)


# ── Registration helper ──────────────────────────────────────


def add_inventory_routes(app: Starlette) -> None:
    """Register the inventory-plane routes onto an existing
    Starlette app. Called from
    :mod:`metabrowser.proc_browser` once at module-load
    time."""

    app.routes.extend(
        [
            Route("/api/events", api_events),
            Route("/api/catalog", api_catalog),
            Route("/api/index/progress", api_index_progress),
            Route("/api/index/meta", api_index_meta),
            Route("/api/capabilities", api_capabilities),
        ]
    )


# ── Test-only SSE parser ─────────────────────────────────────


def parse_sse_frames(blob: bytes | str) -> Iterator[dict[str, str]]:
    """Parse a chunk of SSE wire bytes into ``{event, id, data}``
    dicts. The browser's EventSource handles this natively;
    server-side tests use this helper to drain a streamed
    response.

    Comment frames (``: heartbeat\\n\\n``) are surfaced as a
    record with ``event="comment"`` so tests can assert
    heartbeat cadence without depending on the parser to silently
    eat them.
    """

    text = blob.decode("utf-8", errors="replace") if isinstance(blob, bytes) else blob
    for raw_record in text.split("\n\n"):
        record = raw_record.strip("\n")
        if not record:
            continue
        if record.startswith(":"):
            yield {"event": "comment", "id": "", "data": record.lstrip(": ")}
            continue
        out = {"event": "message", "id": "", "data": ""}
        data_lines: list[str] = []
        for line in record.split("\n"):
            if line.startswith("event: "):
                out["event"] = line[len("event: ") :]
            elif line.startswith("id: "):
                out["id"] = line[len("id: ") :]
            elif line.startswith("data: "):
                data_lines.append(line[len("data: ") :])
        out["data"] = "\n".join(data_lines)
        yield out
