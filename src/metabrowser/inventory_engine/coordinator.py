"""Provider-neutral inventory lifecycle and host-state composition.

The coordinator is the sole application owner of an opened inventory handle. It
serializes root replacement with reads and host-overlay updates, converts provider
changes into one bounded resumable host stream, and joins sparse decorations only onto
entries returned by a query.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from collections import deque
from collections.abc import AsyncGenerator, Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

from metabrowser.inventory_engine.contract import (
    MAX_CHANGE_PATHS,
    CatalogProjection,
    ChangeBatch,
    ChangeCursor,
    DirectoryProjection,
    EngineVersion,
    EntryProjection,
    FilteredTreeProjection,
    IndexState,
    InventoryBackend,
    InventoryClosedError,
    InventoryConfig,
    InventoryContractError,
    InventoryEntry,
    InventoryHandle,
    PriorityRequest,
    QueryKind,
    ReadRequest,
    ReadResult,
    RecentProjection,
    RefreshReceipt,
    RefreshRequest,
    WorkCounters,
)
from metabrowser.inventory_engine.overlay import (
    EMPTY_DECORATION,
    InventoryDecoration,
    InventoryDecorationPatch,
    InventoryOverlay,
)

LOG = logging.getLogger(__name__)

_DECORATED_QUERY_KINDS = frozenset(
    {
        QueryKind.ENTRY,
        QueryKind.DIRECTORY,
        QueryKind.FILTERED_TREE,
        QueryKind.RECENT,
    }
)


class InventoryNotOpenError(InventoryContractError):
    """The coordinator has not opened its first served root."""


class InventoryConsistencyError(InventoryContractError):
    """A provider returned mutually inconsistent values in one coherent read."""


def _require_same_provider_identity(
    current: EngineVersion,
    observed: EngineVersion,
) -> None:
    """Reject identity drift from one opened provider handle."""

    if observed.session != current.session:
        raise InventoryConsistencyError("an opened inventory handle changed provider session")
    if (
        observed.scope_fingerprint != current.scope_fingerprint
        or observed.semantic_fingerprint != current.semantic_fingerprint
    ):
        raise InventoryConsistencyError("an opened inventory handle changed provider fingerprints")


@dataclass(frozen=True, slots=True)
class HostVersion:
    """Cache identity for provider facts plus host-owned decorations."""

    engine: EngineVersion
    overlay_revision: int

    def __post_init__(self) -> None:
        if self.overlay_revision < 0:
            raise ValueError("overlay_revision must be nonnegative")


@dataclass(frozen=True, slots=True)
class HostCursor:
    """Resume point in one coordinator root session's ordered change stream."""

    session: str
    sequence: int

    def __post_init__(self) -> None:
        if not self.session:
            raise ValueError("session must not be empty")
        if self.sequence < 0:
            raise ValueError("sequence must be nonnegative")


@dataclass(frozen=True, slots=True)
class DecoratedInventoryEntry:
    """One provider entry paired with its Metabrowser-owned decoration."""

    facts: InventoryEntry
    decoration: InventoryDecoration = field(default_factory=InventoryDecoration)


@dataclass(frozen=True, slots=True)
class CoordinatedRead:
    """One provider read joined with one sparse-overlay observation boundary."""

    result: ReadResult
    version: HostVersion
    cursor: HostCursor
    entries: Mapping[str, DecoratedInventoryEntry]
    decorations: Mapping[str, InventoryDecoration]

    def __post_init__(self) -> None:
        if self.version.engine != self.result.version:
            raise ValueError("host and provider versions must describe the same read")
        if any(path != entry.facts.path for path, entry in self.entries.items()):
            raise ValueError("decorated-entry keys must match provider paths")


class InventoryReadSession:
    """Serialize a bounded multi-read assembly at one host observation boundary."""

    def __init__(self, coordinator: InventoryCoordinator, handle: InventoryHandle) -> None:
        self._coordinator = coordinator
        self._handle = handle
        self._active = True

    async def read(
        self,
        request: ReadRequest,
        *,
        include_catalog_decorations: bool = False,
    ) -> CoordinatedRead:
        """Read while root changes, overlay writes, and host publication are paused."""

        if not self._active:
            raise RuntimeError("the inventory read session is no longer active")
        result = await _drain_provider_operation_on_cancel(self._handle.read(request))
        if self._handle is not self._coordinator._handle:
            raise InventoryConsistencyError("the served root changed during a read session")
        return self._coordinator._compose_read_locked(
            result,
            include_catalog_decorations=include_catalog_decorations,
        )

    def _finish(self) -> None:
        self._active = False


@dataclass(frozen=True, slots=True)
class HostChange:
    """Bounded invalidation in the coordinator's host ordering."""

    cursor: HostCursor
    version: HostVersion
    state: IndexState
    dirty_paths: tuple[str, ...] = ()
    dirty_queries: frozenset[QueryKind] = frozenset()
    all_dirty: bool = False
    reset: bool = False
    facts_changed: bool = False
    work: WorkCounters = field(default_factory=WorkCounters)

    def __post_init__(self) -> None:
        if self.all_dirty and self.dirty_paths:
            raise ValueError("all_dirty replaces individual dirty paths")
        if self.reset and (self.all_dirty or self.dirty_paths or self.dirty_queries):
            raise ValueError("reset replaces dirty paths and projections")
        if len(self.dirty_paths) > MAX_CHANGE_PATHS:
            raise ValueError(f"a host change accepts at most {MAX_CHANGE_PATHS} dirty paths")
        if len(self.dirty_paths) != len(set(self.dirty_paths)):
            raise ValueError("host-change dirty paths must be unique")


type InvalidationListener = Callable[[HostChange], None]


def _sum_work(items: tuple[WorkCounters, ...]) -> WorkCounters:
    return WorkCounters(
        observations=sum(item.observations for item in items),
        unchanged=sum(item.unchanged for item in items),
        stale=sum(item.stale for item in items),
        resource_refused=sum(item.resource_refused for item in items),
        rows_visited=sum(item.rows_visited for item in items),
        rows_returned=sum(item.rows_returned for item in items),
        maintained_index_work=sum(item.maintained_index_work for item in items),
        commits_visited=sum(item.commits_visited for item in items),
        commits_returned=sum(item.commits_returned for item in items),
        directories_read=sum(item.directories_read for item in items),
        entries_visited=sum(item.entries_visited for item in items),
        files_visited=sum(item.files_visited for item in items),
        bytes_visited=sum(item.bytes_visited for item in items),
    )


def _reset_from(change: HostChange) -> HostChange:
    return HostChange(
        cursor=change.cursor,
        version=change.version,
        state=change.state,
        reset=True,
        facts_changed=change.facts_changed,
        work=change.work,
    )


def _provider_reset_from(batch: ChangeBatch) -> ChangeBatch:
    return ChangeBatch(
        cursor=batch.cursor,
        version=batch.version,
        state=batch.state,
        reset=True,
        work=batch.work,
    )


async def _drain_provider_operation_on_cancel[T](operation: Awaitable[T]) -> T:
    """Keep a cancelled caller accounted for until provider work has stopped."""

    task = asyncio.ensure_future(operation)
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:
            LOG.debug(
                "inventory provider operation failed while its cancelled caller drained it",
                exc_info=True,
            )
        raise


class InventoryCoordinator:
    """Own and compose exactly one opened inventory handle at a time."""

    def __init__(
        self,
        *,
        backend: InventoryBackend,
        config: InventoryConfig,
        overlay: InventoryOverlay | None = None,
    ) -> None:
        self._backend = backend
        self._config = config
        self._overlay = overlay if overlay is not None else InventoryOverlay()
        self._lock = asyncio.Lock()
        self._condition = asyncio.Condition(self._lock)
        self._handle: InventoryHandle | None = None
        self._root: Path | None = None
        self._engine_version: EngineVersion | None = None
        self._engine_cursor: ChangeCursor | None = None
        self._state: IndexState | None = None
        self._relay_task: asyncio.Task[None] | None = None
        self._host_session: str | None = None
        self._host_sequence = 0
        self._history: deque[HostChange] = deque(maxlen=config.change_queue_size)
        self._subscribers: set[asyncio.Queue[HostChange | None]] = set()
        self._listeners: set[InvalidationListener] = set()
        self._active_operations = 0
        self._transitioning = False
        self._closed = False

    async def open(self, root: Path) -> HostVersion:
        """Open the first root, or atomically replace the currently served root."""

        canonical_root = await asyncio.to_thread(root.resolve)
        published: HostChange | None = None
        async with self._condition:
            await self._wait_for_transition_locked()
            self._ensure_not_closed_locked()
            if self._handle is not None and canonical_root == self._root:
                return self._current_host_version_locked()
            self._transitioning = True
            try:
                await self._wait_for_operations_locked()
                published = await self._replace_root_locked(canonical_root)
                version = published.version
            finally:
                self._transitioning = False
                self._condition.notify_all()
        self._notify_listeners(published)
        return version

    async def replace_root(self, root: Path) -> HostVersion:
        """Close the old root completely before making the replacement visible."""

        return await self.open(root)

    async def read(
        self,
        request: ReadRequest,
        *,
        include_catalog_decorations: bool = False,
    ) -> CoordinatedRead:
        """Run one coherent provider read and join requested host decorations.

        Entry-bearing projections always receive their sparse overlay. Catalog
        projections carry identities rather than entries, so their decorations are
        joined only for the activity tracker that consumes them. Bulk catalog delivery
        leaves this false and therefore performs no O(catalog) work on the event loop.
        """

        handle = await self._begin_operation()
        try:
            result = await _drain_provider_operation_on_cancel(handle.read(request))
            async with self._lock:
                if handle is not self._handle:
                    raise InventoryConsistencyError(
                        "the served root changed during a coordinated read"
                    )
                return self._compose_read_locked(
                    result,
                    include_catalog_decorations=include_catalog_decorations,
                )
        finally:
            await asyncio.shield(self._end_operation())

    @contextlib.asynccontextmanager
    async def read_session(self) -> AsyncGenerator[InventoryReadSession]:
        """Hold one host boundary across a bounded version-pinned page assembly.

        Provider mutation may still advance the native engine, so callers must pin
        pages to the first ``EngineVersion`` and retry on ``VersionUnavailableError``.
        The session prevents root replacement, overlay changes, and host-change
        publication from splitting the assembled response.
        """

        async with self._condition:
            await self._wait_for_transition_locked()
            handle = self._require_handle_locked()
            self._active_operations += 1
            session = InventoryReadSession(self, handle)
            try:
                yield session
            finally:
                session._finish()
                self._active_operations -= 1
                if self._active_operations < 0:
                    raise RuntimeError("inventory operation accounting underflow")
                if self._active_operations == 0:
                    self._condition.notify_all()

    async def refresh(self, request: RefreshRequest) -> RefreshReceipt:
        """Forward verified filesystem hints without exposing the provider."""

        handle = await self._begin_operation()
        try:
            receipt = await _drain_provider_operation_on_cancel(handle.refresh(request))
            receipt_paths = frozenset((*receipt.accepted_paths, *receipt.rejected_paths))
            if receipt_paths != frozenset(request.paths):
                raise InventoryConsistencyError(
                    "the provider refresh receipt did not account for every requested path"
                )
            async with self._lock:
                if handle is not self._handle:
                    raise InventoryConsistencyError(
                        "the served root changed during a coordinated refresh"
                    )
                current = self._require_engine_version_locked()
                _require_same_provider_identity(current, receipt.version)
            return receipt
        finally:
            await asyncio.shield(self._end_operation())

    async def prioritize(self, request: PriorityRequest) -> None:
        """Forward bounded interactive-priority hints to the opened handle."""

        handle = await self._begin_operation()
        try:
            await _drain_provider_operation_on_cancel(handle.prioritize(request))
        finally:
            await asyncio.shield(self._end_operation())

    async def replace_decoration(
        self,
        path: str,
        decoration: InventoryDecoration | None,
    ) -> HostVersion:
        """Replace one sparse decoration in host event order."""

        return await self.replace_decorations({path: decoration})

    async def replace_decorations(
        self,
        replacements: Mapping[str, InventoryDecoration | None],
    ) -> HostVersion:
        """Atomically update decorations and publish at most one host change."""

        published: HostChange | None
        async with self._condition:
            await self._wait_for_transition_locked()
            self._require_handle_locked()
            version, published = self._replace_decorations_locked(replacements)
        if published is not None:
            self._notify_listeners(published)
        return version

    async def patch_decorations(
        self,
        patches: Mapping[str, InventoryDecorationPatch],
    ) -> HostVersion:
        """Atomically merge feature-owned fields and publish one host change."""

        published: HostChange | None
        async with self._condition:
            await self._wait_for_transition_locked()
            self._require_handle_locked()
            before = self._overlay.snapshot(patches)
            replacements = {
                path: patch.apply(before.decorations.get(path, EMPTY_DECORATION))
                for path, patch in patches.items()
            }
            version, published = self._replace_decorations_locked(replacements)
        if published is not None:
            self._notify_listeners(published)
        return version

    def _replace_decorations_locked(
        self,
        replacements: Mapping[str, InventoryDecoration | None],
    ) -> tuple[HostVersion, HostChange | None]:
        before = self._overlay.snapshot(replacements)
        changed_paths = tuple(
            path
            for path, requested in replacements.items()
            if before.decorations.get(path, EMPTY_DECORATION)
            != (requested if requested is not None else EMPTY_DECORATION)
        )
        revision = self._overlay.replace_many(replacements)
        published: HostChange | None = None
        if changed_paths:
            all_dirty = len(changed_paths) > MAX_CHANGE_PATHS
            published = self._new_host_change_locked(
                version=HostVersion(
                    engine=self._require_engine_version_locked(),
                    overlay_revision=revision,
                ),
                state=self._require_state_locked(),
                dirty_paths=() if all_dirty else changed_paths,
                dirty_queries=_DECORATED_QUERY_KINDS,
                all_dirty=all_dirty,
            )
            self._publish_locked(published)
        return (
            HostVersion(
                engine=self._require_engine_version_locked(),
                overlay_revision=revision,
            ),
            published,
        )

    def changes(self, *, after: HostCursor | None) -> AsyncGenerator[HostChange]:
        """Yield resumable bounded host invalidations after *after*."""

        return self._changes(after=after)

    async def checkpoint(self) -> tuple[HostCursor, HostVersion, IndexState]:
        """Return the current host change checkpoint and diagnostic state."""

        async with self._condition:
            await self._wait_for_transition_locked()
            self._require_handle_locked()
            return (
                self._current_host_cursor_locked(),
                self._current_host_version_locked(),
                self._require_state_locked(),
            )

    def add_invalidation_listener(self, listener: InvalidationListener) -> Callable[[], None]:
        """Register a synchronous cache-invalidation listener.

        The returned callback removes the listener. Listener failures are isolated and
        logged so one response cache cannot stop inventory change delivery.
        """

        self._listeners.add(listener)

        def remove() -> None:
            self._listeners.discard(listener)

        return remove

    async def close(self) -> None:
        """Cancel and join all work, close the handle, and end subscriptions."""

        async with self._condition:
            if self._closed:
                return
            self._closed = True
            await self._wait_for_transition_locked()
            self._transitioning = True
            try:
                await self._wait_for_operations_locked()
                await self._stop_handle_locked()
                for queue in tuple(self._subscribers):
                    while not queue.empty():
                        queue.get_nowait()
                    queue.put_nowait(None)
                self._history.clear()
            finally:
                self._transitioning = False
                self._condition.notify_all()

    async def _replace_root_locked(self, root: Path) -> HostChange:
        await self._stop_handle_locked()
        self._overlay.clear()
        self._root = None
        self._engine_version = None
        self._engine_cursor = None
        self._state = None

        handle = await self._backend.open(root, self._config)
        try:
            initial = await handle.read(ReadRequest())
        except BaseException:
            await handle.close()
            raise

        self._handle = handle
        self._root = root
        self._engine_version = initial.version
        self._engine_cursor = initial.cursor
        self._state = initial.state
        self._host_session = uuid.uuid4().hex
        self._host_sequence = 0
        self._history.clear()
        published = self._new_host_change_locked(
            version=HostVersion(
                engine=initial.version,
                overlay_revision=self._overlay.snapshot().revision,
            ),
            state=initial.state,
            reset=True,
            facts_changed=True,
            work=initial.work,
        )
        self._publish_locked(published)
        self._relay_task = asyncio.create_task(
            self._run_change_relay(handle, initial.cursor),
            name="metabrowser-inventory-change-relay",
        )
        return published

    async def _stop_handle_locked(self) -> None:
        relay = self._relay_task
        self._relay_task = None
        if relay is not None and not relay.done():
            relay.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await relay
        elif relay is not None:
            try:
                relay.result()
            except asyncio.CancelledError:
                pass
            except Exception:
                # The running relay logs failures at ERROR before publishing its
                # recovery reset. Retrieval here is cleanup accounting only.
                LOG.debug("joined failed inventory change relay", exc_info=True)

        handle = self._handle
        self._handle = None
        if handle is not None:
            await handle.close()

    async def _run_change_relay(
        self,
        handle: InventoryHandle,
        after: ChangeCursor,
    ) -> None:
        queue: asyncio.Queue[ChangeBatch | None] = asyncio.Queue(
            maxsize=self._config.change_queue_size
        )
        try:
            async with asyncio.TaskGroup() as tasks:
                tasks.create_task(self._pump_provider_changes(handle, after, queue))
                tasks.create_task(
                    self._dispatch_provider_changes(
                        handle,
                        queue,
                        after_sequence=after.sequence,
                    )
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            LOG.exception("inventory provider change relay failed")
            await self._publish_relay_reset(handle)

    @staticmethod
    async def _pump_provider_changes(
        handle: InventoryHandle,
        after: ChangeCursor,
        queue: asyncio.Queue[ChangeBatch | None],
    ) -> None:
        completed = False
        try:
            async for batch in handle.changes(after=after):
                if queue.full():
                    while not queue.empty():
                        queue.get_nowait()
                    queue.put_nowait(_provider_reset_from(batch))
                else:
                    queue.put_nowait(batch)
            completed = True
        finally:
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait(None)
            else:
                await queue.put(None)
        if completed:
            raise RuntimeError("inventory provider change stream ended before handle close")

    async def _dispatch_provider_changes(
        self,
        handle: InventoryHandle,
        queue: asyncio.Queue[ChangeBatch | None],
        *,
        after_sequence: int,
    ) -> None:
        previous_sequence = after_sequence
        while True:
            first = await queue.get()
            if first is None:
                return
            await asyncio.sleep(0)
            batches = [first]
            ended = False
            while True:
                try:
                    batch = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                if batch is None:
                    ended = True
                    break
                batches.append(batch)
            for batch in batches:
                if batch.version.sequence <= previous_sequence:
                    raise InventoryConsistencyError(
                        "provider change batches must have strictly increasing sequences"
                    )
                previous_sequence = batch.version.sequence
            await self._publish_provider_batches(handle, tuple(batches))
            if ended:
                return

    async def _publish_provider_batches(
        self,
        handle: InventoryHandle,
        batches: tuple[ChangeBatch, ...],
    ) -> None:
        published: HostChange | None = None
        async with self._lock:
            if handle is not self._handle or self._closed:
                return
            current = self._require_engine_version_locked()
            for batch in batches:
                _require_same_provider_identity(current, batch.version)
            merged = self._merge_provider_batches(batches)
            if merged.version.sequence >= current.sequence:
                self._engine_version = merged.version
                self._engine_cursor = merged.cursor
                self._state = merged.state
            published = self._new_host_change_locked(
                version=self._current_host_version_locked(),
                state=self._require_state_locked(),
                dirty_paths=merged.dirty_paths,
                dirty_queries=merged.dirty_queries,
                all_dirty=merged.all_dirty,
                reset=merged.reset,
                facts_changed=bool(merged.dirty_paths) or merged.all_dirty or merged.reset,
                work=merged.work,
            )
            self._publish_locked(published)
        self._notify_listeners(published)

    async def _publish_relay_reset(self, handle: InventoryHandle) -> None:
        published: HostChange | None = None
        async with self._lock:
            if handle is not self._handle or self._closed:
                return
            published = self._new_host_change_locked(
                version=self._current_host_version_locked(),
                state=self._require_state_locked(),
                reset=True,
                facts_changed=True,
            )
            self._publish_locked(published)
        self._notify_listeners(published)

    @staticmethod
    def _merge_provider_batches(batches: tuple[ChangeBatch, ...]) -> ChangeBatch:
        if not batches:
            raise ValueError("at least one provider batch is required")
        latest = batches[-1]
        work = _sum_work(tuple(batch.work for batch in batches))
        if any(batch.reset for batch in batches):
            return ChangeBatch(
                cursor=latest.cursor,
                version=latest.version,
                state=latest.state,
                reset=True,
                work=work,
            )
        dirty_paths = tuple(dict.fromkeys(path for batch in batches for path in batch.dirty_paths))
        all_dirty = any(batch.all_dirty for batch in batches) or len(dirty_paths) > MAX_CHANGE_PATHS
        return ChangeBatch(
            cursor=latest.cursor,
            version=latest.version,
            state=latest.state,
            dirty_paths=() if all_dirty else dirty_paths,
            dirty_queries=frozenset(query for batch in batches for query in batch.dirty_queries),
            all_dirty=all_dirty,
            work=work,
        )

    async def _changes(self, *, after: HostCursor | None) -> AsyncGenerator[HostChange]:
        queue: asyncio.Queue[HostChange | None] = asyncio.Queue(
            maxsize=self._config.change_queue_size
        )
        async with self._condition:
            await self._wait_for_transition_locked()
            self._require_handle_locked()
            replay = self._replay_locked(after)
            self._subscribers.add(queue)
        try:
            for change in replay:
                yield change
            while True:
                change = await queue.get()
                if change is None:
                    return
                yield change
        finally:
            self._subscribers.discard(queue)

    def _replay_locked(self, after: HostCursor | None) -> tuple[HostChange, ...]:
        if after is None:
            return ()
        current = self._current_host_cursor_locked()
        if after.session != current.session or after.sequence > current.sequence:
            return (self._current_reset_locked(),)
        history = tuple(self._history)
        if history and after.sequence < history[0].cursor.sequence - 1:
            return (self._current_reset_locked(),)
        return tuple(change for change in history if change.cursor.sequence > after.sequence)

    def _current_reset_locked(self) -> HostChange:
        return HostChange(
            cursor=self._current_host_cursor_locked(),
            version=self._current_host_version_locked(),
            state=self._require_state_locked(),
            reset=True,
            facts_changed=True,
        )

    def _new_host_change_locked(
        self,
        *,
        version: HostVersion,
        state: IndexState,
        dirty_paths: tuple[str, ...] = (),
        dirty_queries: frozenset[QueryKind] = frozenset(),
        all_dirty: bool = False,
        reset: bool = False,
        facts_changed: bool = False,
        work: WorkCounters = WorkCounters(),
    ) -> HostChange:
        session = self._host_session
        if session is None:
            raise InventoryNotOpenError("the inventory coordinator is not open")
        self._host_sequence += 1
        return HostChange(
            cursor=HostCursor(session=session, sequence=self._host_sequence),
            version=version,
            state=state,
            dirty_paths=dirty_paths,
            dirty_queries=dirty_queries,
            all_dirty=all_dirty,
            reset=reset,
            facts_changed=facts_changed,
            work=work,
        )

    def _publish_locked(self, change: HostChange) -> None:
        self._history.append(change)
        for queue in tuple(self._subscribers):
            outgoing = change
            if change.reset or queue.full():
                while not queue.empty():
                    queue.get_nowait()
                outgoing = _reset_from(change)
            queue.put_nowait(outgoing)

    def _notify_listeners(self, change: HostChange) -> None:
        for listener in tuple(self._listeners):
            try:
                listener(change)
            except Exception:
                LOG.exception("inventory invalidation listener failed")

    def _observe_read_locked(self, result: ReadResult) -> None:
        current = self._engine_version
        if current is not None:
            _require_same_provider_identity(current, result.version)
        if current is None or result.version.sequence >= current.sequence:
            self._engine_version = result.version
            self._engine_cursor = result.cursor
            self._state = result.state

    def _compose_read_locked(
        self,
        result: ReadResult,
        *,
        include_catalog_decorations: bool,
    ) -> CoordinatedRead:
        """Join one provider result while the coordinator lock is held."""

        self._observe_read_locked(result)
        facts = self._returned_entries(result)
        returned_paths = self._returned_paths(
            result,
            facts,
            include_catalog=include_catalog_decorations,
        )
        overlay = self._overlay.snapshot(returned_paths)
        decorated = {
            path: DecoratedInventoryEntry(
                facts=entry,
                decoration=overlay.decorations.get(path, EMPTY_DECORATION),
            )
            for path, entry in facts.items()
        }
        return CoordinatedRead(
            result=result,
            version=HostVersion(
                engine=result.version,
                overlay_revision=overlay.revision,
            ),
            cursor=self._current_host_cursor_locked(),
            entries=MappingProxyType(decorated),
            decorations=overlay.decorations,
        )

    @staticmethod
    def _returned_entries(result: ReadResult) -> dict[str, InventoryEntry]:
        returned: dict[str, InventoryEntry] = {}
        for projection in result.projections:
            entries: tuple[InventoryEntry, ...]
            if isinstance(projection, EntryProjection):
                entries = (projection.entry,) if projection.entry is not None else ()
            elif isinstance(
                projection,
                (DirectoryProjection, FilteredTreeProjection, RecentProjection),
            ):
                entries = projection.entries
            else:
                continue
            for entry in entries:
                prior = returned.get(entry.path)
                if prior is not None and prior != entry:
                    raise InventoryConsistencyError(
                        f"provider returned conflicting entries for {entry.path!r}"
                    )
                returned[entry.path] = entry
        return returned

    @staticmethod
    def _returned_paths(
        result: ReadResult,
        entries: Mapping[str, InventoryEntry],
        *,
        include_catalog: bool,
    ) -> tuple[str, ...]:
        """Path identities returned by any projection at this read boundary."""

        paths = dict.fromkeys(entries)
        if include_catalog:
            for projection in result.projections:
                if isinstance(projection, CatalogProjection):
                    paths.update((record.path, None) for record in projection.records)
        return tuple(paths)

    def _current_host_version_locked(self) -> HostVersion:
        return HostVersion(
            engine=self._require_engine_version_locked(),
            overlay_revision=self._overlay.snapshot().revision,
        )

    def _current_host_cursor_locked(self) -> HostCursor:
        session = self._host_session
        if session is None:
            raise InventoryNotOpenError("the inventory coordinator is not open")
        return HostCursor(session=session, sequence=self._host_sequence)

    def _require_handle_locked(self) -> InventoryHandle:
        self._ensure_not_closed_locked()
        if self._handle is None:
            raise InventoryNotOpenError("the inventory coordinator is not open")
        return self._handle

    async def _begin_operation(self) -> InventoryHandle:
        async with self._condition:
            await self._wait_for_transition_locked()
            handle = self._require_handle_locked()
            self._active_operations += 1
            return handle

    async def _end_operation(self) -> None:
        async with self._condition:
            if self._active_operations <= 0:
                raise RuntimeError("inventory operation accounting underflow")
            self._active_operations -= 1
            if self._active_operations == 0:
                self._condition.notify_all()

    async def _wait_for_transition_locked(self) -> None:
        while self._transitioning:
            await self._condition.wait()

    async def _wait_for_operations_locked(self) -> None:
        while self._active_operations:
            await self._condition.wait()

    def _require_engine_version_locked(self) -> EngineVersion:
        if self._engine_version is None:
            raise InventoryNotOpenError("the inventory coordinator is not open")
        return self._engine_version

    def _require_state_locked(self) -> IndexState:
        if self._state is None:
            raise InventoryNotOpenError("the inventory coordinator is not open")
        return self._state

    def _ensure_not_closed_locked(self) -> None:
        if self._closed:
            raise InventoryClosedError("the inventory coordinator is closed")


__all__ = [
    "CoordinatedRead",
    "DecoratedInventoryEntry",
    "HostChange",
    "HostCursor",
    "HostVersion",
    "InvalidationListener",
    "InventoryConsistencyError",
    "InventoryCoordinator",
    "InventoryNotOpenError",
    "InventoryReadSession",
]
