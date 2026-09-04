"""Disposable exact-wheel adapter for the fdu/MetaBrowser contract spike.

This is measurement code, not the production provider.  It intentionally materializes
the native flat projection and delegates MetaBrowser query projection to the current
Python oracle.  Every such operation is counted by :mod:`probe` so the experiment can
name the work that a durable native API must eliminate.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import threading
import time
from collections.abc import AsyncGenerator, Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from functools import partial
from pathlib import Path, PurePosixPath
from typing import Any

from fdu import opened as fdu
from probe import AdapterProbe, ReadObservation

from metabrowser.events import FsEntry
from metabrowser.fs_paths import derive_ext
from metabrowser.inventory_engine.contract import (
    CatalogQuery,
    ChangeBatch,
    ChangeCursor,
    Coverage,
    CoverageReason,
    DiagnosticsProjection,
    DirectoryQuery,
    EngineVersion,
    FilteredTreeQuery,
    Freshness,
    IndexProgress,
    IndexState,
    InventoryClosedError,
    InventoryConfig,
    InventoryContractError,
    InventoryIssue,
    IssueCode,
    LifecyclePhase,
    NavigationQuery,
    PriorityRequest,
    ProjectionResult,
    ProviderDiagnostics,
    QueryKind,
    ReadRequest,
    ReadResult,
    RecentQuery,
    RefreshReceipt,
    RefreshRequest,
    RollupQuery,
    SourceKind,
    VersionUnavailableError,
    WorkCounters,
    inventory_scope_fingerprint,
)
from metabrowser.inventory_engine.providers.python_inventory import _PythonInventoryStore

_CONTRACT_ID = "inventory-provider-v1"
_NATIVE_PAGE_ROWS = 4_096
_NATIVE_PAGE_WORK = 1_000_000
_CHANGE_POLL_SECONDS = 0.25
_MAX_ISSUE_DETAIL_BYTES = 4_096


def _bounded_detail(value: str) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= _MAX_ISSUE_DETAIL_BYTES:
        return value
    suffix = b"..."
    prefix = encoded[: _MAX_ISSUE_DETAIL_BYTES - len(suffix)].decode("utf-8", errors="ignore")
    return f"{prefix}{suffix.decode()}"


def _translate_native_call[T](function: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    try:
        return function(*args, **kwargs)
    except fdu.OpenedIndexClosedError as error:
        raise InventoryClosedError(str(error)) from error
    except (
        fdu.VersionUnavailableError,
        fdu.ContinuationUnavailableError,
        fdu.ChangeCursorUnavailableError,
    ) as error:
        raise VersionUnavailableError(str(error)) from error
    except fdu.OpenedIndexError as error:
        raise InventoryContractError(str(error)) from error


def _combine_semantics(version: fdu.EngineVersion, registry_fingerprint: str) -> str:
    components = (
        ("ignore_rules", str(version.semantics.ignore_rules_fingerprint)),
        ("metabrowser_registry", registry_fingerprint),
        ("reducers", str(version.semantics.reducers_fingerprint)),
        ("type_rules", str(version.semantics.type_rules_fingerprint)),
    )
    payload = json.dumps(sorted(components), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sum_work(left: WorkCounters, right: WorkCounters) -> WorkCounters:
    cpu_time_ns: int | None
    if left.cpu_time_ns is None or right.cpu_time_ns is None:
        cpu_time_ns = None
    else:
        cpu_time_ns = left.cpu_time_ns + right.cpu_time_ns
    return WorkCounters(
        entries_visited=left.entries_visited + right.entries_visited,
        directories_visited=left.directories_visited + right.directories_visited,
        rows_returned=left.rows_returned + right.rows_returned,
        bytes_copied=left.bytes_copied + right.bytes_copied,
        lock_wait_ns=left.lock_wait_ns + right.lock_wait_ns,
        cpu_time_ns=cpu_time_ns,
        wall_time_ns=left.wall_time_ns + right.wall_time_ns,
    )


def _query_cost_shape(
    request: ReadRequest,
    entries: Sequence[FsEntry],
) -> tuple[int, int, int]:
    graph_queries = sum(
        isinstance(query, (DirectoryQuery, FilteredTreeQuery, RollupQuery))
        for query in request.queries
    )
    child_buckets = len({entry.parent for entry in entries}) if graph_queries else 0
    full_sorts = sum(
        isinstance(query, (DirectoryQuery, FilteredTreeQuery, RecentQuery, CatalogQuery))
        for query in request.queries
    )
    aggregate_passes = sum(
        isinstance(query, (FilteredTreeQuery, RollupQuery, NavigationQuery, RecentQuery))
        for query in request.queries
    )
    return child_buckets, full_sorts, aggregate_passes


class FduSpikeHandle:
    """Unchanged-contract experiment over one installed-wheel ``OpenedIndex``."""

    def __init__(
        self,
        *,
        root: Path,
        config: InventoryConfig,
        index: fdu.OpenedIndex,
        initial: fdu.ReadResponse,
        probe: AdapterProbe,
    ) -> None:
        self._root = root
        self._config = config
        self._index = index
        self._probe = probe
        self._scope_fingerprint = inventory_scope_fingerprint(config)
        self._semantic_fingerprint = _combine_semantics(
            initial.version, config.registry_fingerprint
        )
        self._native_session = initial.version.session
        self._native_identity = initial.version
        self._version_lock = threading.Lock()
        self._lifecycle_lock = threading.Lock()
        self._changes_active = False
        self._closing = False
        self._closed = False
        self._close_task: asyncio.Task[None] | None = None
        self._poll_executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="metabrowser-fdu-spike-poll",
        )
        self._work_lock = threading.Lock()
        self._read_requests = 0
        self._cumulative_work = WorkCounters(cpu_time_ns=0)

    def _remember(self, version: fdu.EngineVersion) -> None:
        if version.session != self._native_session:
            raise InventoryContractError("fdu changed session identity without reopening")
        with self._version_lock:
            self._native_identity = version

    def _native_expected(self, version: EngineVersion | None) -> fdu.EngineVersion | None:
        if version is None:
            return None
        expected = self._to_version(self._native_identity)
        if (
            version.session != expected.session
            or version.scope_fingerprint != expected.scope_fingerprint
            or version.semantic_fingerprint != expected.semantic_fingerprint
        ):
            raise VersionUnavailableError("the requested version belongs to another scope")
        with self._version_lock:
            identity = self._native_identity
        return replace(identity, sequence=version.sequence)

    def _to_version(self, version: fdu.EngineVersion) -> EngineVersion:
        return EngineVersion(
            session=f"fdu:{version.session:016x}",
            sequence=version.sequence,
            scope_fingerprint=self._scope_fingerprint,
            semantic_fingerprint=self._semantic_fingerprint,
        )

    def _relative_path(self, value: Path | None) -> str | None:
        if value is None:
            return None
        if value.is_absolute():
            try:
                value = value.relative_to(self._root)
            except ValueError as error:
                raise InventoryContractError(
                    "fdu returned an issue outside the opened root"
                ) from error
        portable = value.as_posix()
        return "" if portable == "." else portable

    def _issues(self, diagnostics: fdu.ReadDiagnostics) -> tuple[InventoryIssue, ...]:
        issue_codes = {
            fdu.IssueKind.PERMISSION: IssueCode.PERMISSION_DENIED,
            fdu.IssueKind.DISAPPEARED: IssueCode.DISAPPEARED,
            fdu.IssueKind.INVALID_METADATA: IssueCode.INVALID_METADATA,
            fdu.IssueKind.RESOURCE_BUDGET: IssueCode.RESOURCE_BUDGET,
            fdu.IssueKind.OBSERVATION_GAP: IssueCode.WATCHER_GAP,
            fdu.IssueKind.PROVIDER_FAILURE: IssueCode.PROVIDER_FAILURE,
        }
        return tuple(
            InventoryIssue(
                code=issue_codes[issue.kind],
                detail=_bounded_detail(issue.message),
                path=self._relative_path(issue.path),
                transient=issue.kind in {fdu.IssueKind.DISAPPEARED, fdu.IssueKind.OBSERVATION_GAP},
            )
            for issue in diagnostics.issues
        )

    def _state(
        self,
        state: fdu.OpenedState,
        diagnostics: fdu.ReadDiagnostics | None,
    ) -> IndexState:
        phases = {
            fdu.LifecyclePhase.DISCOVERING: LifecyclePhase.DISCOVERING,
            fdu.LifecyclePhase.RECONCILING: LifecyclePhase.RECONCILING,
            fdu.LifecyclePhase.READY: LifecyclePhase.READY,
            fdu.LifecyclePhase.WATCHING: LifecyclePhase.WATCHING,
            fdu.LifecyclePhase.STOPPED: LifecyclePhase.STOPPED,
            fdu.LifecyclePhase.FAILED: LifecyclePhase.FAILED,
        }
        coverage_reasons = {
            fdu.CoverageReason.BUILDING: CoverageReason.BUILDING,
            fdu.CoverageReason.BUDGET: CoverageReason.BUDGET,
            fdu.CoverageReason.CANCELLED: CoverageReason.CANCELLED,
            fdu.CoverageReason.INACCESSIBLE: CoverageReason.INACCESSIBLE,
            fdu.CoverageReason.FAILED: CoverageReason.FAILED,
        }
        sources = {
            fdu.ValueSource.SCANNED: SourceKind.SCANNED,
            fdu.ValueSource.REVALIDATED: SourceKind.REVALIDATED,
            fdu.ValueSource.JOURNAL_SCOPED: SourceKind.JOURNAL_SCOPED,
            fdu.ValueSource.CACHED: SourceKind.CACHED,
        }
        if diagnostics is None and (state.issues.retained or state.issues.omitted):
            raise InventoryContractError(
                "fdu state reported issues without a coherent diagnostic projection"
            )
        if state.issues.omitted:
            raise InventoryContractError(
                "the unchanged MetaBrowser state cannot represent omitted fdu issues"
            )
        return IndexState(
            phase=phases[state.phase],
            coverage=Coverage(
                complete=state.coverage.kind is fdu.CoverageKind.COMPLETE,
                reason=(
                    coverage_reasons[state.coverage.reason]
                    if state.coverage.reason is not None
                    else None
                ),
            ),
            freshness=Freshness(state.freshness.value),
            source=sources[state.source],
            progress=IndexProgress(
                entries_observed=state.progress.files_retained,
                directories_observed=state.progress.directories_complete,
            ),
            issues=self._issues(diagnostics) if diagnostics is not None else (),
        )

    def _entry(self, entry: fdu.Entry) -> FsEntry:
        if entry.portable_path is None:
            raise InventoryContractError("MetaBrowser cannot represent a non-portable fdu path")
        path = entry.portable_path
        if path == ".":
            path = ""
        depth = len(PurePosixPath(path).parts) if path else 0
        if depth > self._config.max_depth:
            raise InventoryContractError(
                "the unchanged MetaBrowser max_depth scope cannot be represented by the "
                "Phase 2 live fdu scope"
            )
        parent, separator, name = path.rpartition("/")
        if not separator:
            parent = ""
            name = path if path else self._root.name
        if entry.kind is fdu.EntryKind.OTHER:
            raise InventoryContractError("MetaBrowser cannot represent special fdu entries")
        entry_type = entry.kind.value
        rollup = entry.rollup
        return FsEntry(
            path=path,
            parent=parent,
            name=name,
            type=entry_type,
            ext=derive_ext(name) if entry.kind is fdu.EntryKind.FILE else "",
            kind=entry_type,
            size=entry.attrs.size if entry.kind is not fdu.EntryKind.DIR else 0,
            mtime_ns=entry.attrs.mtime_ns if entry.kind is not fdu.EntryKind.DIR else 0,
            mtime_hash="",
            active=False,
            total_files=rollup.all.files if rollup is not None else None,
            total_size=rollup.all.bytes if rollup is not None else None,
            unignored_files=rollup.unignored.files if rollup is not None else None,
            unignored_size=rollup.unignored.bytes if rollup is not None else None,
            newest_mtime_ns=rollup.all.newest_mtime_ns if rollup is not None else None,
            empty=(rollup.all.files == 0)
            if rollup is not None and entry.children_complete
            else None,
            gitignored=entry.ignored,
        )

    def _converted_entries(self, entries: Sequence[fdu.Entry]) -> tuple[FsEntry, ...]:
        converted = tuple(self._entry(entry) for entry in entries)
        symlink_ancestors: set[str] = set()
        for entry in converted:
            if entry.type != "symlink":
                continue
            ancestor = entry.parent
            while True:
                symlink_ancestors.add(ancestor)
                if not ancestor:
                    break
                ancestor = ancestor.rpartition("/")[0]
        return tuple(
            replace(entry, empty=False)
            if entry.type == "dir" and entry.empty is True and entry.path in symlink_ancestors
            else entry
            for entry in converted
        )

    @staticmethod
    def _native_work(responses: Sequence[fdu.ReadResponse]) -> tuple[int, int]:
        rows_visited = sum(response.work.rows_visited for response in responses)
        directories_read = sum(response.work.directories_read for response in responses)
        return rows_visited, directories_read

    def _read_native(
        self,
        expected: fdu.EngineVersion | None,
        *,
        materialize: bool,
    ) -> tuple[fdu.ReadResponse, tuple[fdu.Entry, ...], fdu.ReadDiagnostics, int, int, int]:
        page = fdu.Page(limit=_NATIVE_PAGE_ROWS, max_work=_NATIVE_PAGE_WORK)
        projections: tuple[fdu.Projection, ...]
        if materialize:
            projections = (
                fdu.Lookup(""),
                fdu.Flat(shape=fdu.RowShape.FULL, page=page),
                fdu.Diagnostics(),
            )
        else:
            projections = (fdu.Diagnostics(),)
        first = _translate_native_call(self._index.read, *projections, expected=expected)
        self._remember(first.version)
        responses = [first]
        rows: list[fdu.Entry] = []
        root: fdu.Entry | None = None
        diagnostics: fdu.ReadDiagnostics | None = None
        continuation: fdu.Continuation | None = None
        for result in first.results:
            if isinstance(result, fdu.LookupResult) and result.value.value is not None:
                root = result.value.value
            elif isinstance(result, fdu.FlatResult):
                rows.extend(result.value.rows)
                continuation = result.value.next
                if result.value.portable_issue is not None:
                    raise InventoryContractError("fdu omitted paths MetaBrowser cannot represent")
            elif isinstance(result, fdu.DiagnosticsResult):
                diagnostics = result.value
            elif isinstance(result, fdu.LimitResult):
                raise InventoryContractError(
                    f"fdu materialization exceeded its {result.projection.value} work bound"
                )
        native_pages = int(materialize)
        while continuation is not None:
            current = _translate_native_call(
                self._index.read,
                fdu.Continue(continuation=continuation, page=page),
                expected=first.version,
            )
            responses.append(current)
            self._remember(current.version)
            result = current.results[0]
            if isinstance(result, fdu.LimitResult):
                raise InventoryContractError(
                    f"fdu continuation exceeded its {result.projection.value} work bound"
                )
            if not isinstance(result, fdu.FlatResult):
                raise InventoryContractError("fdu continuation changed projection kind")
            if result.value.portable_issue is not None:
                raise InventoryContractError("fdu omitted paths MetaBrowser cannot represent")
            rows.extend(result.value.rows)
            continuation = result.value.next
            native_pages += 1
        if diagnostics is None:
            raise InventoryContractError("fdu did not return requested diagnostics")
        if root is not None:
            rows.insert(0, root)
        rows_visited, directories_read = self._native_work(responses)
        return (
            first,
            tuple(rows),
            diagnostics,
            len(responses),
            native_pages,
            rows_visited + directories_read,
        )

    def _project_sync(
        self,
        request: ReadRequest,
        entries: tuple[FsEntry, ...],
    ) -> ReadResult:
        store = _PythonInventoryStore(config=self._config)
        store._root = self._root
        store._entries = {entry.path: entry for entry in entries}
        children: dict[str, dict[str, FsEntry]] = {}
        for entry in entries:
            if entry.path:
                children.setdefault(entry.parent, {})[entry.path] = entry
        store._children_index = children
        store._files_indexed = sum(entry.type == "file" for entry in entries)
        store._directories_indexed = sum(entry.type == "dir" for entry in entries)
        store._status = "done"
        return store._read_snapshot_sync(ReadRequest(queries=request.queries))

    def _diagnostics(self, state: fdu.OpenedState, work: WorkCounters) -> ProviderDiagnostics:
        watch_mode = self._config.watch_mode
        if watch_mode == "off":
            watch_state = "off"
            watch_reason = "disabled"
        elif state.phase is fdu.LifecyclePhase.WATCHING:
            watch_state = "watching"
            watch_reason = "native"
        elif state.phase is fdu.LifecyclePhase.FAILED:
            watch_state = "failed"
            watch_reason = "provider_failure"
        else:
            watch_state = "starting"
            watch_reason = "discovery"
        with self._work_lock:
            self._read_requests += 1
            self._cumulative_work = _sum_work(self._cumulative_work, work)
            read_requests = self._read_requests
            cumulative = self._cumulative_work
        return ProviderDiagnostics(
            provider="fdu-spike",
            contract=_CONTRACT_ID,
            files_indexed=state.progress.files_retained,
            directories_indexed=max(0, state.progress.directories_complete - 1),
            watch_mode=watch_mode,
            watch_state=watch_state,
            watch_reason=watch_reason,
            read_requests=read_requests,
            cumulative_work=cumulative,
        )

    async def read(self, request: ReadRequest) -> ReadResult:
        wall_started = time.monotonic_ns()
        cpu_started = time.process_time_ns()
        expected = self._native_expected(request.at_version)
        materialize = bool(request.queries)
        (
            first,
            native_entries,
            diagnostics,
            native_calls,
            native_pages,
            native_work,
        ) = await asyncio.to_thread(
            self._read_native,
            expected,
            materialize=materialize,
        )
        if materialize:
            entries = self._converted_entries(native_entries)
            projected = await asyncio.to_thread(self._project_sync, request, entries)
        else:
            entries = ()
            projected = ReadResult(
                version=self._to_version(first.version),
                cursor=self._to_version(first.version).cursor,
                state=self._state(first.state, diagnostics),
                projections=(),
                work=WorkCounters(),
            )
        wall_time_ns = time.monotonic_ns() - wall_started
        cpu_time_ns = time.process_time_ns() - cpu_started
        path_bytes = sum(len(entry.path.encode("utf-8")) for entry in entries)
        work = WorkCounters(
            entries_visited=native_work + projected.work.entries_visited,
            directories_visited=projected.work.directories_visited,
            rows_returned=projected.work.rows_returned,
            bytes_copied=path_bytes,
            lock_wait_ns=projected.work.lock_wait_ns,
            cpu_time_ns=cpu_time_ns,
            wall_time_ns=wall_time_ns,
        )
        provider_diagnostics = self._diagnostics(first.state, work)
        projections: tuple[ProjectionResult, ...] = tuple(
            replace(projection, payload=provider_diagnostics)
            if isinstance(projection, DiagnosticsProjection)
            else projection
            for projection in projected.projections
        )
        version = self._to_version(first.version)
        result = ReadResult(
            version=version,
            cursor=version.cursor,
            state=self._state(first.state, diagnostics),
            projections=projections,
            work=work,
        )
        child_sorts, full_sorts, aggregate_passes = _query_cost_shape(request, entries)
        self._probe.record_read(
            ReadObservation(
                query_kinds=tuple(query.kind.value for query in request.queries),
                native_calls=native_calls,
                native_pages=native_pages,
                materialized_rows=len(entries),
                materialized_path_bytes=path_bytes,
                child_bucket_sorts=child_sorts,
                full_result_sorts=full_sorts,
                aggregate_passes=aggregate_passes,
                rows_returned=work.rows_returned,
                wall_time_ns=wall_time_ns,
                cpu_time_ns=cpu_time_ns,
            )
        )
        return result

    def changes(self, *, after: ChangeCursor | None) -> AsyncGenerator[ChangeBatch, None]:
        return self._changes(after=after)

    async def _changes(self, *, after: ChangeCursor | None) -> AsyncGenerator[ChangeBatch, None]:
        with self._lifecycle_lock:
            if self._changes_active:
                raise InventoryContractError("one fdu handle permits one active change iterator")
            if self._closing or self._closed:
                raise InventoryClosedError("the fdu inventory handle is closed")
            self._changes_active = True
        try:
            if after is None:
                try:
                    initial = await asyncio.to_thread(
                        _translate_native_call,
                        self._index.read,
                        fdu.Diagnostics(),
                    )
                except InventoryClosedError:
                    with self._lifecycle_lock:
                        if self._closing or self._closed:
                            return
                    raise
                self._remember(initial.version)
                cursor = initial.version
            else:
                cursor = self._native_expected(
                    EngineVersion(
                        session=after.session,
                        sequence=after.sequence,
                        scope_fingerprint=self._scope_fingerprint,
                        semantic_fingerprint=self._semantic_fingerprint,
                    )
                )
                if cursor is None:
                    raise AssertionError("a non-null cursor must map to a native version")
            loop = asyncio.get_running_loop()
            while True:
                with self._lifecycle_lock:
                    if self._closing or self._closed:
                        return
                poll_future = loop.run_in_executor(
                    self._poll_executor,
                    partial(
                        _translate_native_call,
                        self._index.changes,
                        cursor,
                        timeout=_CHANGE_POLL_SECONDS,
                    ),
                )
                try:
                    poll = await asyncio.shield(poll_future)
                except asyncio.CancelledError:
                    await poll_future
                    raise
                self._probe.record_change_poll()
                self._remember(poll.version)
                cursor = poll.cursor
                if poll.outcome.kind is fdu.ChangeOutcomeKind.IDLE:
                    continue
                diagnostics: fdu.ReadDiagnostics | None = None
                if poll.state.issues.retained or poll.state.issues.omitted:
                    try:
                        diagnostics_response = await asyncio.to_thread(
                            _translate_native_call,
                            self._index.read,
                            fdu.Diagnostics(),
                            expected=poll.version,
                        )
                    except InventoryClosedError:
                        with self._lifecycle_lock:
                            if self._closing or self._closed:
                                return
                        raise
                    except VersionUnavailableError as unavailable:
                        current = await asyncio.to_thread(
                            _translate_native_call,
                            self._index.read,
                            fdu.Diagnostics(),
                        )
                        self._remember(current.version)
                        current_diagnostics = current.results[0]
                        if not isinstance(current_diagnostics, fdu.DiagnosticsResult):
                            raise InventoryContractError(
                                "fdu did not return requested diagnostics"
                            ) from unavailable
                        cursor = current.version
                        current_version = self._to_version(current.version)
                        yield ChangeBatch(
                            cursor=current_version.cursor,
                            version=current_version,
                            state=self._state(current.state, current_diagnostics.value),
                            reset=True,
                        )
                        continue
                    diagnostics_result = diagnostics_response.results[0]
                    if not isinstance(diagnostics_result, fdu.DiagnosticsResult):
                        raise InventoryContractError("fdu did not return requested diagnostics")
                    diagnostics = diagnostics_result.value
                version = self._to_version(poll.version)
                if poll.outcome.kind is fdu.ChangeOutcomeKind.RESET:
                    yield ChangeBatch(
                        cursor=version.cursor,
                        version=version,
                        state=self._state(poll.state, diagnostics),
                        reset=True,
                    )
                    continue
                impact = poll.outcome.impact
                if impact is None:
                    raise InventoryContractError("fdu change outcome omitted its impact")
                paths = tuple(
                    path
                    for path in (self._relative_path(path) for path in impact.dirty_paths)
                    if path is not None
                )
                data_domains = {
                    fdu.ImpactDomain.TOPOLOGY,
                    fdu.ImpactDomain.METADATA,
                    fdu.ImpactDomain.CLASSIFICATION,
                    fdu.ImpactDomain.AGGREGATES,
                    fdu.ImpactDomain.CONTENT,
                }
                dirty_queries: set[QueryKind] = set()
                if data_domains.intersection(impact.domains):
                    dirty_queries.update(QueryKind)
                    dirty_queries.discard(QueryKind.DIAGNOSTICS)
                if fdu.ImpactDomain.STATE in impact.domains:
                    dirty_queries.add(QueryKind.DIAGNOSTICS)
                yield ChangeBatch(
                    cursor=version.cursor,
                    version=version,
                    state=self._state(poll.state, diagnostics),
                    dirty_paths=() if impact.all_dirty else paths,
                    dirty_queries=frozenset(dirty_queries),
                    all_dirty=impact.all_dirty,
                )
        finally:
            with self._lifecycle_lock:
                self._changes_active = False

    async def refresh(self, request: RefreshRequest) -> RefreshReceipt:
        self._probe.record_refresh()
        receipt = await asyncio.to_thread(
            _translate_native_call,
            self._index.refresh,
            request.paths,
        )
        self._remember(receipt.version)
        accepted = {self._relative_path(path) or "" for path in receipt.accepted}
        rejected = {self._relative_path(rejection.path) or "" for rejection in receipt.rejected}
        return RefreshReceipt(
            version=self._to_version(receipt.version),
            accepted_paths=tuple(path for path in request.paths if path in accepted),
            rejected_paths=tuple(path for path in request.paths if path in rejected),
        )

    async def prioritize(self, request: PriorityRequest) -> None:
        self._probe.record_priority()
        await asyncio.to_thread(
            _translate_native_call,
            self._index.prioritize,
            request.paths,
        )

    async def close(self) -> None:
        task = self._close_task
        if task is None:
            with self._lifecycle_lock:
                self._closing = True
            task = asyncio.create_task(self._close_owned(), name="metabrowser-fdu-spike-close")
            self._close_task = task
        await asyncio.shield(task)

    async def _close_owned(self) -> None:
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(
                self._poll_executor,
                partial(_translate_native_call, self._index.close),
            )
        finally:
            self._poll_executor.shutdown(wait=True, cancel_futures=False)
            with self._lifecycle_lock:
                self._closed = True
                self._closing = False


class FduSpikeBackend:
    """Construct disposable handles without registering a shipping provider."""

    def __init__(self, *, probe: AdapterProbe | None = None) -> None:
        self.probe = probe if probe is not None else AdapterProbe()

    async def open(self, root: Path, config: InventoryConfig) -> FduSpikeHandle:
        if config.watch_mode == "poll":
            raise InventoryContractError(
                "the exact fdu wheel has no polling observer; the spike will not fake one"
            )
        canonical_root = await asyncio.to_thread(root.resolve)
        options = fdu.OpenedOptions(
            follow_symlinks=False,
            one_filesystem=False,
            prune_hidden=True,
            hidden_allow=config.hidden_allowlist,
            exclude_special=True,
            max_files=config.max_files,
            observe=config.watch_mode != "off",
            journal_capacity=config.change_queue_size,
        )
        index = await asyncio.to_thread(
            _translate_native_call,
            fdu.OpenedIndex.open,
            canonical_root,
            options,
        )
        try:
            initial = await asyncio.to_thread(
                _translate_native_call,
                index.read,
                fdu.Diagnostics(),
            )
        except BaseException as open_error:
            try:
                await asyncio.to_thread(_translate_native_call, index.close)
            except BaseException as close_error:
                raise BaseExceptionGroup(
                    "fdu spike open and cleanup both failed",
                    (open_error, close_error),
                ) from None
            raise
        return FduSpikeHandle(
            root=canonical_root,
            config=config,
            index=index,
            initial=initial,
            probe=self.probe,
        )


__all__ = ["FduSpikeBackend", "FduSpikeHandle"]
