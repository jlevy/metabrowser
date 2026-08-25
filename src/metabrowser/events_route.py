"""SSE routes + lifespan hook for the inventory event plane.

This module owns:

* ``GET /api/events`` — global inventory SSE stream backed by the
  application-owned inventory coordinator. Emits an ``fs.snapshot`` on
  connect, then projects provider invalidations into ``fs.change`` ops.
  Heartbeat every 15 s. Reconnects receive a new coherent snapshot boundary;
  pre-snapshot deltas are never replayed after it.
* ``GET /api/index/progress`` — lightweight crawl status for the
  left-nav progress footer. Reads in-memory inventory counters
  only; never scans the tree or rebuilds suffix tallies.
* ``POST /api/diagnostics/pending-tallies`` — bounded client/server state
  captured when a rendered directory total remains unresolved.
* ``GET /api/index/meta`` — bundled summary of index status,
  suffix tally, and oldest/newest mtime; ETag-cacheable. Folds
  what the search spec called ``/api/index/status`` and
  ``/api/index/suffixes`` into one envelope.
* ``GET /api/capabilities`` — unified capability surface with
  filesystem-type-driven watcher status.
* :func:`build_lifespan` — Starlette lifespan context manager
  that bumps the asyncio default executor to 64 workers and opens the
  selected inventory provider without blocking HTTP bind.

Everything in this module is end-to-end testable via
``starlette.testclient.TestClient`` without opening a browser.
The ``aiter_sse_events`` helper at the bottom is the test-side
parser for the SSE wire format.

The endpoint, snapshot handoff, and encoder form the realtime event contract.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncIterator, Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from metabrowser.active_tracker import run_active_tracker
from metabrowser.events import (
    CapabilityUpdate,
    CatalogChange,
    CatalogUpsert,
    EventEnvelope,
    FsChange,
    FsEntry,
    FsRemove,
    FsResyncRequired,
    FsSnapshot,
    FsUpsert,
    ProjectionInvalidate,
    RingBuffer,
    StreamEvent,
    encode_heartbeat_comment,
    encode_sse,
)
from metabrowser.http_caching import (
    build_scoped_etag,
    etag_headers,
    matches_if_none_match,
)
from metabrowser.inventory_engine.contract import (
    CatalogProjection,
    CatalogQuery,
    CatalogRecord,
    DiagnosticsProjection,
    DiagnosticsQuery,
    DirectoryProjection,
    DirectoryQuery,
    EngineVersion,
    EntryPresence,
    EntryProjection,
    EntryQuery,
    EntryType,
    IndexState,
    InventoryConfig,
    LifecyclePhase,
    NavigationProjection,
    NavigationQuery,
    QueryKind,
    ReadRequest,
    VersionUnavailableError,
)
from metabrowser.inventory_engine.coordinator import (
    DecoratedInventoryEntry,
    HostChange,
    HostCursor,
    HostVersion,
    InventoryConsistencyError,
    InventoryCoordinator,
)
from metabrowser.inventory_engine.runtime import (
    InventoryRuntime,
    default_inventory_config,
    inventory_provider_from_environment,
)
from metabrowser.inventory_engine.tree_page_assembly import assemble_tree_pages
from metabrowser.settings import (
    DEFAULT_EXECUTOR_WORKERS,
    INDEX_PROGRESS_UPDATE_FILES,
    INVENTORY_TREE_PAGE_ROWS,
    PENDING_TALLY_DIAGNOSTIC_MAX_BODY_BYTES,
    PENDING_TALLY_DIAGNOSTIC_SAMPLE_LIMIT,
    SSE_HEARTBEAT_INTERVAL_S,
    SSE_PER_CONNECTION_QUEUE_SIZE,
    SSE_RING_BUFFER_CAPACITY,
)

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
    app: Starlette,
    root_provider: Callable[[], object] = lambda: None,
) -> AsyncIterator[None]:
    """Own one runtime and stop host observation tasks before its provider."""

    loop = asyncio.get_running_loop()
    loop.set_default_executor(
        ThreadPoolExecutor(
            max_workers=DEFAULT_EXECUTOR_WORKERS,
            thread_name_prefix="metabrowser",
        )
    )

    config = default_inventory_config()
    runtime = InventoryRuntime(
        provider=inventory_provider_from_environment(),
        config=config,
    )
    app.state.inventory_runtime = runtime
    app.state.inventory_event_bus = None
    root = root_provider()
    active_task: asyncio.Task[None] | None = None
    bus: _EventBus | None = None
    try:
        if isinstance(root, Path):
            await runtime.open(root)
            LOG.debug("inventory opened at %s", root)
            cursor, _version, _state = await runtime.coordinator.checkpoint()
            bus = _EventBus(runtime.coordinator, config=config)
            app.state.inventory_event_bus = bus
            await bus.start(after=cursor)
            active_task = asyncio.create_task(
                run_active_tracker(
                    coordinator=runtime.coordinator,
                    config=config,
                    root=root,
                ),
                name="metabrowser-active-tracker",
            )
        yield
    finally:
        for t in (active_task,):
            if t is not None and not t.done():
                t.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await t
        if bus is not None:
            await bus.close()
        await runtime.close()


# ── Process-wide ring buffer ──────────────────────────────────
#
# A single ring buffer per process assigns ordered ids and retains short-window
# diagnostics. A reconnect starts from a fresh coherent snapshot, not an older
# ring suffix.


def _wire_entry(entry: DecoratedInventoryEntry) -> FsEntry:
    """Join provider facts and host decorations into the existing SSE record."""

    facts = entry.facts
    entry_type = facts.type.value
    return FsEntry(
        path=facts.path,
        parent=facts.parent,
        name=facts.name,
        type=entry_type,
        ext=facts.ext,
        kind="file" if entry_type == "file" else entry_type,
        size=facts.size,
        mtime_ns=facts.mtime_ns,
        mtime_hash="",
        active=entry.decoration.active,
        views=entry.decoration.views,
        labels=entry.decoration.labels,
        total_files=facts.total_files,
        total_size=facts.total_size,
        unignored_files=facts.unignored_files,
        unignored_size=facts.unignored_size,
        newest_mtime_ns=facts.newest_mtime_ns,
        empty=facts.empty,
        gitignored=facts.gitignored,
    )


def _catalog_change(change: FsChange) -> CatalogChange | None:
    """Derive the Quick File delta from one host-projected filesystem change."""

    upserts: list[CatalogUpsert] = []
    removes: list[str] = []
    remove_files: list[str] = []
    for operation in change.ops:
        if isinstance(operation, FsRemove):
            removes.append(operation.path)
        elif operation.entry.type == "file":
            if operation.entry.gitignored:
                remove_files.append(operation.entry.path)
            else:
                upserts.append(CatalogUpsert(p=operation.entry.path, e=operation.entry.ext))
    if not upserts and not removes and not remove_files:
        return None
    return CatalogChange(
        upserts=tuple(upserts),
        removes=tuple(removes),
        remove_files=tuple(remove_files),
    )


class _EventBus:
    """Project coordinator invalidations into the stable browser event wire."""

    def __init__(self, coordinator: InventoryCoordinator, *, config: InventoryConfig) -> None:
        self._coordinator = coordinator
        self._config = config
        self._ring = RingBuffer(capacity=RING_BUFFER_CAPACITY)
        self._connections: dict[asyncio.Queue[EventEnvelope], HostVersion | None] = {}
        self._relay_task: asyncio.Task[None] | None = None
        self._after: HostCursor | None = None
        self._lock = asyncio.Lock()

    async def start(self, *, after: HostCursor) -> None:
        """Start once from an explicit captured coordinator cursor."""

        async with self._lock:
            if self._relay_task is not None and not self._relay_task.done():
                return
            self._after = after
            self._relay_task = asyncio.create_task(
                self._relay_loop(), name="metabrowser-events-bus"
            )

    async def close(self) -> None:
        """Cancel and join the coordinator relay."""

        async with self._lock:
            task = self._relay_task
            self._relay_task = None
            if task is not None and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    async def _read_snapshot(self, scope: _ScopeType) -> tuple[FsSnapshot, HostVersion]:
        """Assemble one lossless snapshot from version-pinned bounded pages."""

        max_depth = 2 if scope == "root-depth-2" else self._config.max_depth
        assembly = await assemble_tree_pages(
            self._coordinator,
            page_query=DirectoryQuery(
                query_id="snapshot-tree",
                path="",
                max_depth=max_depth,
                max_rows=INVENTORY_TREE_PAGE_ROWS,
            ),
            companion_queries=(EntryQuery(query_id="snapshot-root", path=""),),
        )
        return (
            FsSnapshot(
                scope=scope,
                entries=tuple(_wire_entry(entry) for entry in assembly.decorated_entries.values()),
                complete=assembly.final_read.result.state.coverage.complete,
            ),
            assembly.final_read.version,
        )

    async def snapshot(self, scope: _ScopeType) -> FsSnapshot:
        """Build one scoped initial snapshot without attaching a browser."""

        snapshot, _version = await self._read_snapshot(scope)
        return snapshot

    async def snapshot_and_attach(
        self,
        scope: _ScopeType,
    ) -> tuple[FsSnapshot, asyncio.Queue[EventEnvelope]]:
        """Attach after a coherent snapshot with no stale-delta or delivery gap."""

        async with self._lock:
            snapshot, version = await self._read_snapshot(scope)
            queue: asyncio.Queue[EventEnvelope] = asyncio.Queue(maxsize=PER_CONNECTION_QUEUE_SIZE)
            self._connections[queue] = version
            return snapshot, queue

    def publish(self, event: StreamEvent) -> None:
        """Publish a host-owned non-inventory event in the same SSE ordering."""

        self._forward_event(event)

    @staticmethod
    def _replace_with_resync(
        queue: asyncio.Queue[EventEnvelope],
        envelope: EventEnvelope,
        *,
        reason: str,
    ) -> None:
        while True:
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        event = envelope.event
        if not isinstance(event, FsResyncRequired) or event.reason != reason:
            envelope = EventEnvelope(
                id=envelope.id,
                event=FsResyncRequired(reason=reason),
            )
        queue.put_nowait(envelope)

    async def _relay_loop(self) -> None:
        # A relay exception must not stop application-wide SSE delivery. Resume
        # from the last successfully projected host cursor after a short backoff.
        backoff = 0.5
        while True:
            try:
                async for change in self._coordinator.changes(after=self._after):
                    async with self._lock:
                        await self._project_change(change)
                    self._after = change.cursor
                    backoff = 0.5
            except asyncio.CancelledError:
                raise
            except Exception:
                LOG.exception("events bus relay crashed; restarting in %.1fs", backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    async def _project_change(self, change: HostChange) -> None:
        # A fresh SSE connection always starts with a coherent snapshot. Until
        # a browser is attached, projecting every discovery batch would perform
        # provider reads and build wire records that nobody can consume. Keep
        # the coordinator cursor current and begin projection only once a
        # connection can receive the result.
        if not self._connections:
            return
        if not any(
            floor is None or not self._change_is_covered(change, floor)
            for floor in self._connections.values()
        ):
            return
        if change.reset or change.all_dirty:
            self._forward_event(
                FsResyncRequired(
                    reason="coordinator_reset" if change.reset else "inventory_all_dirty"
                ),
                change=change,
            )
            return
        if not change.dirty_paths:
            if QueryKind.DIAGNOSTICS in change.dirty_queries:
                await self._project_capability_change(change)
            return

        if change.facts_changed:
            for path in change.dirty_paths:
                self._forward_event(
                    ProjectionInvalidate(path=path, projection="*"),
                    change=change,
                )

        queries = tuple(
            EntryQuery(query_id=f"change-{index}", path=path)
            for index, path in enumerate(change.dirty_paths)
        )
        read = await self._coordinator.read(ReadRequest(queries=queries))
        ops: list[FsUpsert | FsRemove] = []
        for query, path in zip(queries, change.dirty_paths, strict=True):
            projection = read.result.projection(query.query_id)
            if not isinstance(projection, EntryProjection):
                raise TypeError("an entry query returned a non-entry projection")
            if projection.presence is EntryPresence.UNKNOWN:
                self._forward_event(
                    FsResyncRequired(reason="inventory_presence_unknown"),
                    change=change,
                )
                return
            decorated = read.entries.get(path)
            if decorated is None:
                ops.append(FsRemove(path=path))
            else:
                ops.append(FsUpsert(entry=_wire_entry(decorated)))
        if not ops:
            return
        fs_change = FsChange(ops=tuple(ops))
        self._forward_event(fs_change, change=change)
        if QueryKind.CATALOG in change.dirty_queries:
            catalog = _catalog_change(fs_change)
            if catalog is not None:
                self._forward_event(catalog, change=change)
        if QueryKind.DIAGNOSTICS in change.dirty_queries:
            await self._project_capability_change(change)

    async def _project_capability_change(self, change: HostChange) -> None:
        read = await self._coordinator.read(
            ReadRequest(queries=(DiagnosticsQuery(query_id="capability-change"),))
        )
        diagnostic = read.result.projection("capability-change")
        if not isinstance(diagnostic, DiagnosticsProjection):
            raise TypeError("the capability read returned the wrong projection")
        diagnostics = diagnostic.payload
        state = read.result.state
        truncated = not state.coverage.complete and any(
            issue.code.value == "resource_budget" for issue in state.issues
        )
        self._forward_event(
            CapabilityUpdate(
                backends=(
                    {
                        "kind": "fs-watch",
                        "mode": diagnostics.watch_mode,
                        "state": diagnostics.watch_state,
                        "reason": diagnostics.watch_reason,
                    },
                ),
                index={
                    "complete": state.coverage.complete,
                    "truncated": truncated,
                    "indexed_files": diagnostics.files_indexed,
                    "max_files": self._config.max_files,
                    "status": _status_from_phase(
                        state.phase,
                        complete=state.coverage.complete,
                        truncated=truncated,
                    ),
                },
                events={},
            ),
            change=change,
        )

    @staticmethod
    def _change_is_covered(change: HostChange, floor: HostVersion) -> bool:
        engine = change.version.engine
        return (
            engine.session == floor.engine.session
            and engine.sequence <= floor.engine.sequence
            and change.version.overlay_revision <= floor.overlay_revision
        )

    def _eligible_connections(
        self,
        change: HostChange | None,
    ) -> tuple[asyncio.Queue[EventEnvelope], ...]:
        if change is None:
            return tuple(self._connections)
        eligible: list[asyncio.Queue[EventEnvelope]] = []
        for queue, floor in self._connections.items():
            if floor is not None and self._change_is_covered(change, floor):
                continue
            eligible.append(queue)
            if floor is not None:
                self._connections[queue] = None
        return tuple(eligible)

    def _forward_event(
        self,
        event: StreamEvent,
        *,
        change: HostChange | None = None,
    ) -> None:
        envelope = self._ring.append(event)
        event_type = getattr(event, "type", type(event).__name__)
        eligible = self._eligible_connections(change)
        n_conns = len(eligible)
        if isinstance(event, FsResyncRequired):
            for queue in eligible:
                self._replace_with_resync(queue, envelope, reason=event.reason)
                self._connections.pop(queue, None)
            LOG.debug(
                "events bus: requested fresh snapshots reason=%s conns=%d",
                event.reason,
                n_conns,
            )
            return
        dead: list[asyncio.Queue[EventEnvelope]] = []
        for queue in eligible:
            try:
                queue.put_nowait(envelope)
            except asyncio.QueueFull:
                dead.append(queue)
        for queue in dead:
            self._replace_with_resync(
                queue,
                envelope,
                reason="connection_queue_overflow",
            )
            self._connections.pop(queue, None)
        if dead:
            LOG.warning(
                "events bus: refreshing %d slow browser connection(s) after queue overflow",
                len(dead),
            )
        LOG.debug(
            "events bus: forwarded id=%d type=%s conns=%d refreshed=%d",
            envelope.id,
            event_type,
            n_conns,
            len(dead),
        )

    def attach_connection(self) -> asyncio.Queue[EventEnvelope]:
        q: asyncio.Queue[EventEnvelope] = asyncio.Queue(maxsize=PER_CONNECTION_QUEUE_SIZE)
        self._connections[q] = None
        return q

    def detach_connection(self, q: asyncio.Queue[EventEnvelope]) -> None:
        self._connections.pop(q, None)

    def latest_id(self) -> int:
        return self._ring.latest_id

    def connection_count(self) -> int:
        return len(self._connections)


# ── /api/events route ────────────────────────────────────────


_ScopeType = Literal["root-depth-2", "recent-top-N", "expanded-prefixes", "all-known"]


def _runtime_for(request: Request) -> InventoryRuntime:
    runtime = getattr(request.app.state, "inventory_runtime", None)
    if not isinstance(runtime, InventoryRuntime):
        raise RuntimeError("the application inventory runtime is not available")
    return runtime


def _event_bus_for(request: Request) -> _EventBus:
    bus = getattr(request.app.state, "inventory_event_bus", None)
    if not isinstance(bus, _EventBus):
        raise RuntimeError("the application inventory event bus is not available")
    return bus


def _scope_from_query(request: Request) -> _ScopeType:
    raw = request.query_params.get("scope", "root-depth-2")
    if raw not in VALID_SCOPES:
        raw = "root-depth-2"
    return cast(_ScopeType, raw)


def _parse_last_event_id(request: Request) -> int | None:
    """Parse the EventSource resume id for restart-window diagnostics.

    Every connection receives a new coherent snapshot, so the id is not used to
    replay pre-snapshot deltas.
    """

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

    bus = _event_bus_for(request)
    scope = _scope_from_query(request)
    last_id = _parse_last_event_id(request)
    snap, queue = await bus.snapshot_and_attach(scope)
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
        # A snapshot is a local reset boundary rather than a ring event, so its
        # sentinel id stays outside the live event-id sequence.
        snap_envelope = EventEnvelope(id=0, event=snap)
        yield encode_sse(snap_envelope)

        # 2) Resume: the coherent snapshot is the new reset boundary. Replaying
        # pre-snapshot deltas after it can regress browser state, so a reconnect
        # resumes from the queue atomically attached to that boundary.
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

        # 3) Live: pull from the atomically attached queue with a
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
                if isinstance(envelope.event, FsResyncRequired):
                    LOG.debug(
                        "sse: ending stream for fresh snapshot client=%s reason=%s",
                        client_str,
                        envelope.event.reason,
                    )
                    return
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
    provider: str
    contract: str
    watch_mode: str
    watch_state: str
    watch_reason: str


@dataclass(slots=True, frozen=True)
class IndexProgressEnvelope:
    """Small crawl-progress envelope for frequent UI polling."""

    status: str
    indexed_files: int
    max_files: int
    truncated: bool
    complete: bool
    active: bool
    provider: str
    contract: str


def _status_from_phase(
    phase: LifecyclePhase,
    *,
    complete: bool,
    truncated: bool,
) -> str:
    if truncated:
        return "truncated"
    if phase is LifecyclePhase.FAILED:
        return "failed"
    if phase is LifecyclePhase.STOPPED:
        return "idle"
    if complete:
        return "done"
    return "scanning"


async def _read_index_progress(
    runtime: InventoryRuntime,
) -> tuple[IndexProgressEnvelope, str]:
    coordinated = await runtime.coordinator.read(
        ReadRequest(queries=(DiagnosticsQuery(query_id="progress"),))
    )
    diagnostic = coordinated.result.projection("progress")
    if not isinstance(diagnostic, DiagnosticsProjection):
        raise TypeError("the progress read returned the wrong projection")
    diagnostics = diagnostic.payload
    state = coordinated.result.state
    truncated = not state.coverage.complete and any(
        issue.code.value == "resource_budget" for issue in state.issues
    )
    status = _status_from_phase(
        state.phase,
        complete=state.coverage.complete,
        truncated=truncated,
    )
    engine = coordinated.version.engine
    return IndexProgressEnvelope(
        status=status,
        indexed_files=diagnostics.files_indexed,
        max_files=runtime.config.max_files,
        truncated=truncated,
        complete=state.coverage.complete or truncated,
        active=state.phase
        in {
            LifecyclePhase.OPENING_CACHE,
            LifecyclePhase.DISCOVERING,
            LifecyclePhase.RECONCILING,
        },
        provider=diagnostics.provider,
        contract=diagnostics.contract,
    ), engine.session


def _progress_etag(progress: IndexProgressEnvelope) -> str:
    # While scanning, expose coarse buckets so the browser can poll
    # cheaply without receiving a 200 for every discovered file.
    count_key = (
        progress.indexed_files // INDEX_PROGRESS_UPDATE_FILES
        if progress.active
        else progress.indexed_files
    )
    return build_scoped_etag(f"{progress.status}-{count_key}")


async def _read_index_meta(
    runtime: InventoryRuntime,
    *,
    suffix_limit: int = 64,
) -> tuple[IndexMeta, str]:
    """Read the metadata envelope from one coherent provider boundary."""

    coordinated = await runtime.coordinator.read(
        ReadRequest(
            queries=(
                NavigationQuery(
                    query_id="meta-navigation",
                    max_rows=max(1, suffix_limit),
                ),
                DiagnosticsQuery(query_id="meta-diagnostics"),
            )
        )
    )
    navigation = coordinated.result.projection("meta-navigation")
    diagnostic = coordinated.result.projection("meta-diagnostics")
    if not isinstance(navigation, NavigationProjection) or not isinstance(
        diagnostic, DiagnosticsProjection
    ):
        raise TypeError("the metadata read returned the wrong projections")

    payload = navigation.payload
    diagnostics = diagnostic.payload
    summary = payload["summary"]
    files = summary["files"] + summary["ignored_files"]
    dirs = diagnostics.directories_indexed
    oldest = payload["oldest_mtime_ns"]
    newest = payload["newest_mtime_ns"]
    suffixes: list[dict[str, int | str]] = []
    if suffix_limit > 0:
        for row in payload["extensions"][:suffix_limit]:
            if len(row) < 3:
                continue
            ext, tracked, ignored = row[:3]
            if isinstance(ext, str) and isinstance(tracked, int) and isinstance(ignored, int):
                suffixes.append({"ext": ext, "count": tracked + ignored})
    state = coordinated.result.state
    truncated = not state.coverage.complete and any(
        issue.code.value == "resource_budget" for issue in state.issues
    )
    status = _status_from_phase(
        state.phase,
        complete=state.coverage.complete,
        truncated=truncated,
    )
    engine = coordinated.version.engine
    return IndexMeta(
        status=status,
        indexed_files=files,
        indexed_dirs=dirs,
        max_files=runtime.config.max_files,
        truncated=truncated,
        complete=state.coverage.complete or truncated,
        oldest_mtime_ns=oldest,
        newest_mtime_ns=newest,
        suffixes=suffixes,
        provider=diagnostics.provider,
        contract=diagnostics.contract,
        watch_mode=diagnostics.watch_mode,
        watch_state=diagnostics.watch_state,
        watch_reason=diagnostics.watch_reason,
    ), build_scoped_etag(
        f"index-meta-{engine.session}-{engine.sequence}-{engine.scope_fingerprint}-"
        f"{engine.semantic_fingerprint}-{suffix_limit}"
    )


async def api_index_progress(request: Request) -> Response:
    """JSON crawl-progress envelope for the nav footer.

    Unlike ``/api/index/meta``, this path does not walk known entries
    for suffix or directory summaries. It reads the inventory's
    counters directly so polling remains cheap while the tree is still
    filling.
    """

    progress, session = await _read_index_progress(_runtime_for(request))
    etag = build_scoped_etag(f"{session}-{_progress_etag(progress)}")
    if not progress.active and matches_if_none_match(request, etag):
        return Response(status_code=304, headers={"ETag": etag})
    body = json.dumps(asdict(progress), separators=(",", ":")).encode()
    return Response(
        body,
        media_type="application/json",
        headers=etag_headers(etag),
    )


def _pending_tally_paths(payload: dict[str, object]) -> list[str]:
    pending = payload.get("pending")
    if not isinstance(pending, dict):
        return []
    sample = pending.get("sample")
    if not isinstance(sample, list):
        return []
    paths: list[str] = []
    for item in sample[:PENDING_TALLY_DIAGNOSTIC_SAMPLE_LIMIT]:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        if isinstance(path, str) and path:
            paths.append(path)
    return paths


async def api_pending_tally_diagnostic(request: Request) -> JSONResponse:
    """Correlate a client-side pending-tally warning with server state."""

    content_length = request.headers.get("content-length", "")
    try:
        if content_length and int(content_length) > PENDING_TALLY_DIAGNOSTIC_MAX_BODY_BYTES:
            return JSONResponse({"error": "Diagnostic payload too large"}, status_code=413)
    except ValueError:
        return JSONResponse({"error": "Invalid Content-Length"}, status_code=400)

    body_parts: list[bytes] = []
    body_size = 0
    async for chunk in request.stream():
        body_size += len(chunk)
        if body_size > PENDING_TALLY_DIAGNOSTIC_MAX_BODY_BYTES:
            return JSONResponse({"error": "Diagnostic payload too large"}, status_code=413)
        if chunk:
            body_parts.append(chunk)
    body = b"".join(body_parts)
    try:
        decoded = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JSONResponse({"error": "Invalid diagnostic payload"}, status_code=400)
    if not isinstance(decoded, dict):
        return JSONResponse({"error": "Invalid diagnostic payload"}, status_code=400)

    payload = cast(dict[str, object], decoded)
    raw_id = payload.get("diagnostic_id")
    diagnostic_id = (
        "".join(char if char.isalnum() or char in "-_.:" else "_" for char in raw_id)[:128]
        if isinstance(raw_id, str)
        else "pending-tally-unknown"
    )
    runtime = _runtime_for(request)
    requested_paths = _pending_tally_paths(payload)
    queries: list[EntryQuery | DirectoryQuery | DiagnosticsQuery] = [
        DiagnosticsQuery(query_id="pending-diagnostics")
    ]
    for index, path in enumerate(requested_paths):
        queries.extend(
            (
                EntryQuery(query_id=f"pending-entry-{index}", path=path),
                DirectoryQuery(
                    query_id=f"pending-children-{index}",
                    path=path,
                    max_depth=1,
                    max_rows=runtime.config.max_files,
                ),
            )
        )
    coordinated = await runtime.coordinator.read(ReadRequest(queries=tuple(queries)))
    diagnostic = coordinated.result.projection("pending-diagnostics")
    if not isinstance(diagnostic, DiagnosticsProjection):
        raise TypeError("the pending-tally read returned the wrong projection")
    diagnostics = diagnostic.payload
    path_state: list[dict[str, object]] = []
    for index, path in enumerate(requested_paths):
        entry_projection = coordinated.result.projection(f"pending-entry-{index}")
        children_projection = coordinated.result.projection(f"pending-children-{index}")
        if not isinstance(entry_projection, EntryProjection) or not isinstance(
            children_projection, DirectoryProjection
        ):
            raise TypeError("the pending-tally path read returned the wrong projection")
        entry = entry_projection.entry
        path_state.append(
            {
                "path": path,
                "known": entry_projection.presence is EntryPresence.PRESENT,
                "pending": bool(
                    entry is not None
                    and entry.type is EntryType.DIRECTORY
                    and entry.total_files is None
                ),
                "generation": 0,
                "direct_children": len(children_projection.entries),
                "descendant_files": entry.total_files if entry is not None else None,
                "descendant_size": entry.total_size if entry is not None else None,
                "descendant_leaves": entry.total_files if entry is not None else None,
                "type": entry.type.value if entry is not None else None,
                "total_files": entry.total_files if entry is not None else None,
                "total_size": entry.total_size if entry is not None else None,
                "newest_mtime_ns": entry.newest_mtime_ns if entry is not None else None,
                "empty": entry.empty if entry is not None else None,
                "write_generation": 0,
            }
        )
    state = coordinated.result.state
    truncated = not state.coverage.complete and any(
        issue.code.value == "resource_budget" for issue in state.issues
    )
    status = _status_from_phase(
        state.phase,
        complete=state.coverage.complete,
        truncated=truncated,
    )
    inventory_state: dict[str, object] = {
        "status": status,
        "walker_task": (
            "active"
            if state.phase
            in {
                LifecyclePhase.OPENING_CACHE,
                LifecyclePhase.DISCOVERING,
                LifecyclePhase.RECONCILING,
            }
            else status
        ),
        "provider": diagnostics.provider,
        "contract": diagnostics.contract,
        "version": coordinated.version.engine.sequence,
        "requested_paths": path_state,
    }
    bus = getattr(request.app.state, "inventory_event_bus", None)
    event_state: dict[str, object] = {
        "bus_started": isinstance(bus, _EventBus),
        "connections": bus.connection_count() if isinstance(bus, _EventBus) else 0,
        "latest_event_id": bus.latest_id() if isinstance(bus, _EventBus) else 0,
    }
    response_payload = {
        "diagnostic_id": diagnostic_id,
        "inventory": inventory_state,
        "events": event_state,
    }
    LOG.warning(
        "pending folder tallies diagnostic id=%s client=%s server=%s",
        diagnostic_id,
        json.dumps(payload, separators=(",", ":"), sort_keys=True),
        json.dumps(response_payload, separators=(",", ":"), sort_keys=True),
    )
    return JSONResponse(response_payload)


# Last encoded catalog body, keyed by its ETag. Holds at most one entry: the
# revision moves on every indexed change, so older bodies are dead weight and
# a full catalog is the largest payload the server produces.
_CATALOG_BODY_CACHE: dict[str, bytes] = {}
# A moving provider gets bounded retries before the route reports version churn.
_CATALOG_ASSEMBLY_ATTEMPTS = 3


def _catalog_status(state: IndexState) -> str:
    truncated = not state.coverage.complete and any(
        issue.code.value == "resource_budget" for issue in state.issues
    )
    return _status_from_phase(
        state.phase,
        complete=state.coverage.complete,
        truncated=truncated,
    )


def _catalog_etag(engine: EngineVersion) -> str:
    return build_scoped_etag(
        f"catalog-{engine.session}-{engine.sequence}-{engine.scope_fingerprint}-"
        f"{engine.semantic_fingerprint}"
    )


async def _catalog_checkpoint(runtime: InventoryRuntime) -> str:
    """Read the current catalog identity without traversing catalog records."""

    coordinated = await runtime.coordinator.read(ReadRequest())
    engine = coordinated.version.engine
    return _catalog_etag(engine)


def _encode_catalog(
    pages: tuple[tuple[CatalogRecord, ...], ...],
    status: str,
    revision: int,
) -> bytes:
    """Build the wire envelope and encode it. Runs in a worker thread, so it
    must touch only the immutable provider pages, never the live index."""

    envelope = {
        "complete": status in ("done", "truncated"),
        "truncated": status == "truncated",
        "revision": revision,
        "files": [
            {"p": record.path, "e": record.logical_extension} for page in pages for record in page
        ],
    }
    return json.dumps(envelope, separators=(",", ":")).encode()


async def _read_catalog(
    runtime: InventoryRuntime,
) -> tuple[tuple[tuple[CatalogRecord, ...], ...], str, int, str]:
    """Assemble the complete bounded catalog from one engine version."""

    # The provider retains at most this many entries, so the complete file catalog
    # cannot exceed this bound. Asking for that bound lets the Python provider answer
    # in one scan instead of rescanning and resorting the same index for each 50k page.
    # The continuation loop remains part of the application contract for a provider
    # whose own semantic scope can return more than one bounded page.
    page_size = runtime.config.max_files
    last_version_error: VersionUnavailableError | None = None
    for _attempt in range(_CATALOG_ASSEMBLY_ATTEMPTS):
        pages: list[tuple[CatalogRecord, ...]] = []
        after: str | None = None
        pinned: EngineVersion | None = None
        expected_total: int | None = None
        previous_remaining: int | None = None
        seen_cursors: set[str] = set()
        returned_rows = 0
        try:
            while True:
                coordinated = await runtime.coordinator.read(
                    ReadRequest(
                        queries=(
                            CatalogQuery(
                                query_id="catalog",
                                max_rows=page_size,
                                after=after,
                            ),
                        ),
                        at_version=pinned,
                    )
                )
                projection = coordinated.result.projection("catalog")
                if not isinstance(projection, CatalogProjection):
                    raise TypeError("the catalog read returned the wrong projection")
                if len(projection.records) > page_size:
                    raise InventoryConsistencyError("a catalog page exceeded its row bound")
                if pinned is None:
                    pinned = coordinated.version.engine
                    expected_total = projection.total_matches
                    if expected_total != len(projection.records) + projection.remaining_rows:
                        raise InventoryConsistencyError(
                            "the first catalog page did not conserve total_matches"
                        )
                elif coordinated.version.engine != pinned:
                    raise InventoryConsistencyError(
                        "a version-pinned catalog page changed engine version"
                    )
                if projection.total_matches != expected_total:
                    raise InventoryConsistencyError(
                        "catalog pages changed total_matches within one version"
                    )
                if previous_remaining is not None and previous_remaining != (
                    len(projection.records) + projection.remaining_rows
                ):
                    raise InventoryConsistencyError(
                        "catalog pages did not conserve the exact remaining row count"
                    )
                pages.append(projection.records)
                returned_rows += len(projection.records)
                after = projection.next_page
                if after is None:
                    if returned_rows != expected_total:
                        raise InventoryConsistencyError(
                            "catalog page assembly did not return total_matches rows"
                        )
                    state = coordinated.result.state
                    status = _catalog_status(state)
                    engine = coordinated.version.engine
                    etag = _catalog_etag(engine)
                    return tuple(pages), status, engine.sequence, etag
                if after in seen_cursors:
                    raise InventoryConsistencyError("catalog page cursor did not advance")
                seen_cursors.add(after)
                previous_remaining = projection.remaining_rows
        except VersionUnavailableError as error:
            last_version_error = error
            continue
    if last_version_error is None:
        raise InventoryConsistencyError("catalog assembly exhausted without a version failure")
    raise VersionUnavailableError(
        f"inventory changed during {_CATALOG_ASSEMBLY_ATTEMPTS} bounded catalog attempts"
    ) from last_version_error


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

    runtime = _runtime_for(request)
    checkpoint_etag = await _catalog_checkpoint(runtime)
    if matches_if_none_match(request, checkpoint_etag):
        return Response(status_code=304, headers={"ETag": checkpoint_etag})
    cached = _CATALOG_BODY_CACHE.get(checkpoint_etag)
    if cached is not None:
        return Response(
            cached,
            media_type="application/json",
            headers=etag_headers(checkpoint_etag),
        )

    pages, status, revision, etag = await _read_catalog(runtime)
    if matches_if_none_match(request, etag):
        return Response(status_code=304, headers={"ETag": etag})
    cached = _CATALOG_BODY_CACHE.get(etag)
    if cached is not None:
        return Response(cached, media_type="application/json", headers=etag_headers(etag))
    body = await asyncio.to_thread(_encode_catalog, pages, status, revision)
    # Reconnect storms and multiple tabs re-request the same revision; the
    # ETag turns most of those into 304s, but a client without the ETag (a
    # fresh tab) would otherwise pay the full encode again.
    _CATALOG_BODY_CACHE.clear()
    _CATALOG_BODY_CACHE[etag] = body
    return Response(
        body,
        media_type="application/json",
        headers=etag_headers(etag),
    )


async def api_index_meta(request: Request) -> Response:
    """JSON envelope. ETag is the inventory's status + indexed
    file count + walker generation, so a 304 is cheap when
    nothing has finalized since the last poll."""

    meta, etag = await _read_index_meta(_runtime_for(request))
    body = json.dumps(asdict(meta), separators=(",", ":")).encode()
    if matches_if_none_match(request, etag):
        return Response(status_code=304, headers={"ETag": etag})
    return Response(
        body,
        media_type="application/json",
        headers=etag_headers(etag),
    )


# ── /api/capabilities ────────────────────────────────────────


async def api_capabilities(request: Request) -> JSONResponse:
    """Return the selected provider's reported observation capability."""

    runtime = _runtime_for(request)
    meta, _etag = await _read_index_meta(runtime, suffix_limit=0)

    reported_mode = meta.watch_mode
    mode = reported_mode if reported_mode in {"native", "polling"} else "polling"
    backends_payload = [
        {
            "prefix": ".",
            "mode": mode,
            "reason": meta.watch_reason or "provider-did-not-report-observation-mode",
            "state": meta.watch_state or "unknown",
        }
    ]

    has_native = any(b["mode"] == "native" for b in backends_payload)
    watch_running = meta.watch_state == "running"
    if meta.complete and has_native and watch_running:
        stream_status, stream_reason = "live", "inventory-done+watchfiles-native"
    elif meta.watch_state == "failed":
        stream_status, stream_reason = "polling", "inventory-watch-failed"
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
            "provider": meta.provider,
            "contract": meta.contract,
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
            Route(
                "/api/diagnostics/pending-tallies",
                api_pending_tally_diagnostic,
                methods=["POST"],
            ),
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
