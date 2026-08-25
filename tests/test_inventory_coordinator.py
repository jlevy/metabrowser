"""Contract tests for the application-owned inventory coordinator."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import AsyncIterator
from pathlib import Path
from typing import cast

import pytest

from metabrowser.inventory_engine.contract import (
    CatalogProjection,
    CatalogQuery,
    CatalogRecord,
    ChangeBatch,
    ChangeCursor,
    Coverage,
    DiagnosticsProjection,
    DiagnosticsQuery,
    DirectoryProjection,
    DirectoryQuery,
    EngineVersion,
    EntryPresence,
    EntryProjection,
    EntryQuery,
    Freshness,
    IndexState,
    InventoryBackend,
    InventoryClosedError,
    InventoryConfig,
    InventoryEntry,
    InventoryHandle,
    LifecyclePhase,
    PriorityRequest,
    QueryKind,
    ReadRequest,
    ReadResult,
    RefreshObservation,
    RefreshReceipt,
    RefreshRequest,
    SourceKind,
    WorkCounters,
)
from metabrowser.inventory_engine.coordinator import (
    HostCursor,
    InventoryCoordinator,
)
from metabrowser.inventory_engine.factory import (
    InventoryProvider,
    create_inventory_backend,
)
from metabrowser.inventory_engine.overlay import InventoryDecoration
from metabrowser.inventory_engine.providers.python_inventory import PythonInventoryBackend


def _state() -> IndexState:
    return IndexState(
        phase=LifecyclePhase.WATCHING,
        coverage=Coverage(complete=True),
        freshness=Freshness.FRESH,
        source=SourceKind.SCANNED,
    )


class _FakeHandle:
    def __init__(self, *, root: Path, config: InventoryConfig, events: list[str]) -> None:
        self.root = root
        self.config = config
        self.events = events
        self.session = f"engine-{root.name}"
        self.sequence = 0
        self.entries: dict[str, InventoryEntry] = {}
        self.history: list[ChangeBatch] = []
        self.subscribers: set[asyncio.Queue[ChangeBatch | None]] = set()
        self.closed = False
        self.close_count = 0
        self.refreshes: list[RefreshRequest] = []
        self.priorities: list[PriorityRequest] = []
        self.read_gate: asyncio.Event | None = None
        self.read_started = asyncio.Event()
        self.concurrent_reads_started = asyncio.Event()
        self.active_reads = 0
        self.max_active_reads = 0

    def version(self) -> EngineVersion:
        return EngineVersion(
            session=self.session,
            sequence=self.sequence,
            scope_fingerprint=f"scope-{self.root.name}",
            semantic_fingerprint=self.config.registry_fingerprint,
        )

    def cursor(self) -> ChangeCursor:
        return ChangeCursor(session=self.session, sequence=self.sequence)

    async def read(self, request: ReadRequest) -> ReadResult:
        should_gate = self.read_gate is not None and any(
            not isinstance(query, DiagnosticsQuery) for query in request.queries
        )
        if should_gate:
            self.active_reads += 1
            self.read_started.set()
            self.max_active_reads = max(self.max_active_reads, self.active_reads)
            if self.active_reads >= 2:
                self.concurrent_reads_started.set()
        try:
            if should_gate:
                await cast(asyncio.Event, self.read_gate).wait()
            projections = []
            for query in request.queries:
                if isinstance(query, DiagnosticsQuery):
                    projections.append(
                        DiagnosticsProjection(query_id=query.query_id, counters={"fake": True})
                    )
                elif isinstance(query, EntryQuery):
                    entry = self.entries.get(query.path)
                    projections.append(
                        EntryProjection(
                            query_id=query.query_id,
                            presence=(
                                EntryPresence.PRESENT if entry is not None else EntryPresence.ABSENT
                            ),
                            entry=entry,
                        )
                    )
                elif isinstance(query, DirectoryQuery):
                    projections.append(
                        DirectoryProjection(
                            query_id=query.query_id,
                            entries=tuple(self.entries.values()),
                        )
                    )
                elif isinstance(query, CatalogQuery):
                    records = tuple(
                        CatalogRecord(
                            path=entry.path,
                            logical_extension=entry.logical_extension,
                            size=entry.size,
                            mtime_ns=entry.mtime_ns,
                        )
                        for entry in self.entries.values()
                        if entry.type.value == "file"
                    )
                    projections.append(
                        CatalogProjection(
                            query_id=query.query_id,
                            records=records,
                            total_matches=len(records),
                        )
                    )
                else:
                    raise AssertionError(f"unsupported fake query: {query!r}")
            return ReadResult(
                version=self.version(),
                cursor=self.cursor(),
                state=_state(),
                projections=tuple(projections),
                work=WorkCounters(rows_returned=len(projections)),
            )
        finally:
            if should_gate:
                self.active_reads -= 1

    def changes(self, *, after: ChangeCursor | None) -> AsyncIterator[ChangeBatch]:
        return self._changes(after=after)

    async def _changes(self, *, after: ChangeCursor | None) -> AsyncIterator[ChangeBatch]:
        queue: asyncio.Queue[ChangeBatch | None] = asyncio.Queue()
        self.subscribers.add(queue)
        try:
            sequence = after.sequence if after is not None and after.session == self.session else -1
            for batch in self.history:
                if batch.cursor.sequence > sequence:
                    yield batch
            while True:
                batch = await queue.get()
                if batch is None:
                    return
                yield batch
        finally:
            self.subscribers.discard(queue)

    def emit(
        self,
        *,
        dirty_paths: tuple[str, ...] = (),
        dirty_queries: frozenset[QueryKind] = frozenset(),
        reset: bool = False,
        work: WorkCounters = WorkCounters(),
    ) -> ChangeBatch:
        self.sequence += 1
        batch = ChangeBatch(
            cursor=self.cursor(),
            version=self.version(),
            state=_state(),
            dirty_paths=() if reset else dirty_paths,
            dirty_queries=frozenset() if reset else dirty_queries,
            reset=reset,
            work=work,
        )
        self.history.append(batch)
        for queue in tuple(self.subscribers):
            queue.put_nowait(batch)
        return batch

    async def refresh(self, request: RefreshRequest) -> RefreshReceipt:
        self.refreshes.append(request)
        return RefreshReceipt(accepted_paths=request.paths)

    async def prioritize(self, request: PriorityRequest) -> None:
        self.priorities.append(request)

    async def close(self) -> None:
        self.close_count += 1
        if self.closed:
            return
        self.closed = True
        self.events.append(f"close:{self.root.name}")
        for queue in tuple(self.subscribers):
            queue.put_nowait(None)


class _FakeBackend:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.handles: list[_FakeHandle] = []

    async def open(self, root: Path, config: InventoryConfig) -> InventoryHandle:
        self.events.append(f"open:{root.name}")
        handle = _FakeHandle(root=root, config=config, events=self.events)
        self.handles.append(handle)
        return handle


def _coordinator(
    backend: _FakeBackend,
    *,
    queue_size: int = 8,
) -> InventoryCoordinator:
    return InventoryCoordinator(
        backend=cast(InventoryBackend, backend),
        config=InventoryConfig(
            registry_fingerprint="test-registry",
            change_queue_size=queue_size,
        ),
    )


def test_factory_is_sealed_to_the_real_python_provider() -> None:
    backend = create_inventory_backend(InventoryProvider.PYTHON)
    assert isinstance(backend, PythonInventoryBackend)
    assert isinstance(backend, InventoryBackend)
    with pytest.raises(ValueError, match="unknown inventory provider"):
        create_inventory_backend("fdu")

    source = inspect.getsource(__import__("metabrowser.inventory_engine.factory", fromlist=["*"]))
    assert "FduInventory" not in source


def test_coordinator_opens_one_handle_and_closes_before_root_replacement(
    tmp_path: Path,
) -> None:
    async def _run() -> tuple[_FakeBackend, InventoryCoordinator]:
        first = tmp_path / "first"
        second = tmp_path / "second"
        first.mkdir()
        second.mkdir()
        backend = _FakeBackend()
        coordinator = _coordinator(backend)

        await coordinator.open(first)
        await coordinator.open(first)
        assert len(backend.handles) == 1
        await coordinator.replace_root(second)
        assert backend.events == ["open:first", "close:first", "open:second"]
        assert backend.handles[0].close_count == 1

        await coordinator.close()
        await coordinator.close()
        return backend, coordinator

    backend, coordinator = asyncio.run(_run())
    assert backend.events == ["open:first", "close:first", "open:second", "close:second"]
    assert backend.handles[1].close_count == 1
    with pytest.raises(InventoryClosedError):
        asyncio.run(coordinator.read(ReadRequest(queries=(DiagnosticsQuery(query_id="state"),))))


def test_reads_run_concurrently_and_root_replacement_waits_for_them(tmp_path: Path) -> None:
    async def _run() -> None:
        first = tmp_path / "first"
        second = tmp_path / "second"
        first.mkdir()
        second.mkdir()
        backend = _FakeBackend()
        coordinator = _coordinator(backend)
        await coordinator.open(first)
        handle = backend.handles[0]
        handle.read_gate = asyncio.Event()
        request = ReadRequest(queries=(DirectoryQuery(query_id="tree"),))

        first_read = asyncio.create_task(coordinator.read(request))
        second_read = asyncio.create_task(coordinator.read(request))
        await asyncio.wait_for(handle.concurrent_reads_started.wait(), timeout=1)
        replacement = asyncio.create_task(coordinator.replace_root(second))
        await asyncio.sleep(0)
        assert handle.max_active_reads == 2
        assert backend.events == ["open:first"]

        handle.read_gate.set()
        await asyncio.gather(first_read, second_read)
        await replacement
        assert backend.events == ["open:first", "close:first", "open:second"]
        await coordinator.close()

    asyncio.run(_run())


def test_cancelled_read_drains_before_root_replacement_closes_handle(tmp_path: Path) -> None:
    async def _run() -> None:
        first = tmp_path / "first"
        second = tmp_path / "second"
        first.mkdir()
        second.mkdir()
        backend = _FakeBackend()
        coordinator = _coordinator(backend)
        await coordinator.open(first)
        handle = backend.handles[0]
        handle.read_gate = asyncio.Event()

        read = asyncio.create_task(
            coordinator.read(ReadRequest(queries=(DirectoryQuery(query_id="tree"),)))
        )
        await asyncio.wait_for(handle.read_started.wait(), timeout=1)
        read.cancel()
        replacement = asyncio.create_task(coordinator.replace_root(second))
        await asyncio.sleep(0)

        assert not read.done()
        assert not replacement.done()
        assert backend.events == ["open:first"]

        handle.read_gate.set()
        with pytest.raises(asyncio.CancelledError):
            await read
        await replacement
        assert backend.events == ["open:first", "close:first", "open:second"]
        await coordinator.close()

    asyncio.run(_run())


def test_coherent_read_joins_only_returned_overlay_entries_without_changing_facts(
    tmp_path: Path,
) -> None:
    async def _run() -> None:
        backend = _FakeBackend()
        coordinator = _coordinator(backend)
        await coordinator.open(tmp_path)
        handle = backend.handles[0]
        handle.entries["logs/a.jsonl"] = InventoryEntry.for_observed_file(
            path="logs/a.jsonl",
            parent="logs",
            name="a.jsonl",
            size=41,
            mtime_ns=9,
        )
        handle.entries["logs/b.jsonl"] = InventoryEntry.for_observed_file(
            path="logs/b.jsonl",
            parent="logs",
            name="b.jsonl",
            size=7,
            mtime_ns=10,
        )
        engine_before = handle.version()
        overlay_version = await coordinator.replace_decorations(
            {
                "logs/a.jsonl": InventoryDecoration(
                    active=True,
                    views=("source",),
                    labels=(("pid_alive", "1"),),
                ),
                "logs/b.jsonl": InventoryDecoration(active=True),
            }
        )
        read = await coordinator.read(
            ReadRequest(queries=(EntryQuery(query_id="a", path="logs/a.jsonl"),))
        )

        assert read.result.version == engine_before
        assert overlay_version.engine == engine_before
        assert read.version.overlay_revision == overlay_version.overlay_revision
        assert tuple(read.entries) == ("logs/a.jsonl",)
        returned = read.entries["logs/a.jsonl"]
        assert returned.facts.size == 41
        assert returned.decoration.active is True
        assert returned.decoration.labels == (("pid_alive", "1"),)
        assert handle.sequence == 0

        before_cursor, before_version, _state_value = await coordinator.checkpoint()
        no_op_version = await coordinator.replace_decoration("logs/a.jsonl", returned.decoration)
        after_cursor, after_version, _state_value = await coordinator.checkpoint()
        assert no_op_version == before_version == after_version
        assert after_cursor == before_cursor
        await coordinator.close()

    asyncio.run(_run())


def test_catalog_decorations_are_joined_only_when_requested(tmp_path: Path) -> None:
    async def _run() -> None:
        backend = _FakeBackend()
        coordinator = _coordinator(backend)
        await coordinator.open(tmp_path)
        handle = backend.handles[0]
        path = "logs/a.jsonl"
        handle.entries[path] = InventoryEntry.for_observed_file(
            path=path,
            parent="logs",
            name="a.jsonl",
            size=41,
            mtime_ns=9,
        )
        await coordinator.replace_decoration(path, InventoryDecoration(active=True))
        request = ReadRequest(queries=(CatalogQuery(query_id="catalog", max_rows=10),))

        bulk = await coordinator.read(request)
        activity = await coordinator.read(request, include_catalog_decorations=True)

        assert bulk.decorations == {}
        assert activity.decorations[path].active
        await coordinator.close()

    asyncio.run(_run())


def test_provider_changes_are_coalesced_and_reset_dominates(tmp_path: Path) -> None:
    async def _run() -> None:
        backend = _FakeBackend()
        coordinator = _coordinator(backend)
        await coordinator.open(tmp_path)
        handle = backend.handles[0]
        cursor, _version, _state_value = await coordinator.checkpoint()
        observed = []
        coordinator.add_invalidation_listener(observed.append)
        changes = coordinator.changes(after=cursor)

        first_change = asyncio.ensure_future(anext(changes))
        await asyncio.sleep(0)
        handle.emit(
            dirty_paths=("a",),
            dirty_queries=frozenset({QueryKind.ENTRY}),
            work=WorkCounters(entries_visited=1, cpu_time_ns=1),
        )
        handle.emit(
            dirty_paths=("b",),
            dirty_queries=frozenset({QueryKind.DIRECTORY}),
            work=WorkCounters(entries_visited=2, cpu_time_ns=2),
        )
        handle.emit(
            dirty_paths=("a", "c"),
            work=WorkCounters(entries_visited=3, cpu_time_ns=3),
        )
        merged = await asyncio.wait_for(first_change, timeout=1)
        assert merged.dirty_paths == ("a", "b", "c")
        assert merged.facts_changed is True
        assert merged.dirty_queries == frozenset({QueryKind.ENTRY, QueryKind.DIRECTORY})
        assert merged.version.engine.sequence == 3
        assert merged.work.entries_visited == 6
        assert merged.work.cpu_time_ns == 6
        assert observed[-1] == merged

        absent_cpu_change = asyncio.ensure_future(anext(changes))
        await asyncio.sleep(0)
        handle.emit(dirty_paths=("d",), work=WorkCounters(cpu_time_ns=4))
        handle.emit(dirty_paths=("e",), work=WorkCounters())
        merged_with_absent_cpu = await asyncio.wait_for(absent_cpu_change, timeout=1)
        assert merged_with_absent_cpu.work.cpu_time_ns is None

        reset_change = asyncio.ensure_future(anext(changes))
        handle.emit(dirty_paths=("before-reset",))
        handle.emit(reset=True)
        reset = await asyncio.wait_for(reset_change, timeout=1)
        assert reset.reset is True
        assert reset.dirty_paths == ()
        assert reset.dirty_queries == frozenset()
        await changes.aclose()
        await coordinator.close()

    asyncio.run(_run())


def test_host_resume_overflow_and_history_expiry_return_reset(tmp_path: Path) -> None:
    async def _run() -> None:
        backend = _FakeBackend()
        coordinator = _coordinator(backend, queue_size=1)
        await coordinator.open(tmp_path)
        cursor, _version, _state_value = await coordinator.checkpoint()
        changes = coordinator.changes(after=cursor)

        first_task = asyncio.ensure_future(anext(changes))
        await asyncio.sleep(0)
        await coordinator.replace_decoration("a", InventoryDecoration(active=True))
        first = await asyncio.wait_for(first_task, timeout=1)
        assert first.reset is False
        assert first.facts_changed is False

        await coordinator.replace_decoration("b", InventoryDecoration(active=True))
        await coordinator.replace_decoration("c", InventoryDecoration(active=True))
        overflow = await asyncio.wait_for(anext(changes), timeout=1)
        assert overflow.reset is True

        wrong_session = coordinator.changes(after=HostCursor(session="old-root", sequence=99))
        wrong_reset = await asyncio.wait_for(anext(wrong_session), timeout=1)
        assert wrong_reset.reset is True
        await wrong_session.aclose()

        expired = coordinator.changes(after=cursor)
        expired_reset = await asyncio.wait_for(anext(expired), timeout=1)
        assert expired_reset.reset is True
        await expired.aclose()
        await changes.aclose()
        await coordinator.close()

    asyncio.run(_run())


def test_old_root_changes_cannot_publish_and_close_ends_subscriptions(
    tmp_path: Path,
) -> None:
    async def _run() -> None:
        first = tmp_path / "first"
        second = tmp_path / "second"
        first.mkdir()
        second.mkdir()
        backend = _FakeBackend()
        coordinator = _coordinator(backend)
        await coordinator.open(first)
        old_handle = backend.handles[0]
        observed = []
        coordinator.add_invalidation_listener(observed.append)

        await coordinator.replace_root(second)
        assert len(observed) == 1
        assert observed[0].reset is True
        old_handle.emit(dirty_paths=("must-not-leak",))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert len(observed) == 1

        cursor, _version, _state_value = await coordinator.checkpoint()
        changes = coordinator.changes(after=cursor)
        pending = asyncio.ensure_future(anext(changes))
        await asyncio.sleep(0)
        await coordinator.close()
        with pytest.raises(StopAsyncIteration):
            await pending

    asyncio.run(_run())


def test_refresh_and_priority_are_provider_neutral(tmp_path: Path) -> None:
    async def _run() -> None:
        backend = _FakeBackend()
        coordinator = _coordinator(backend)
        await coordinator.open(tmp_path)
        handle = backend.handles[0]
        refresh = RefreshRequest(observations=(RefreshObservation(path="a"),))
        priority = PriorityRequest(paths=("b",), max_depth=3)
        receipt = await coordinator.refresh(refresh)
        await coordinator.prioritize(priority)
        assert receipt == RefreshReceipt(accepted_paths=("a",))
        assert handle.refreshes == [refresh]
        assert handle.priorities == [priority]
        await coordinator.close()

    asyncio.run(_run())
