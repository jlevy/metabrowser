"""Spike fdu inventory provider against Metabrowser's current (Checkpoint 2B) contract.

This is measurement code, not the production provider. It maps every contract item
that fdu 0.6.0 answers natively onto one coherent native read, and falls back to the
Python reference oracle over a temporary flat image only for the query kinds fdu has no
projection for yet. Every fallback is counted by :mod:`probe`, which names the fdu
addition that would remove it.

What it never does: walk the filesystem in Python, shell out to the fdu command, keep
an image across native versions, or fabricate a value fdu does not report. A semantic
fdu cannot express is a typed ``InventoryContractError`` and a probe count.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import threading
import time
from collections import OrderedDict
from collections.abc import AsyncGenerator, Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path
from typing import Any, cast

from fdu import opened as fdu
from probe import AdapterProbe

from metabrowser.fs_paths import derive_ext
from metabrowser.fs_record import FsEntry
from metabrowser.inventory_engine.contract import (
    MAX_CHANGE_PATHS,
    MAX_INVENTORY_ISSUES,
    MAX_ISSUE_DETAIL_BYTES,
    BoundaryMetrics,
    CatalogProjection,
    CatalogQuery,
    CatalogRecord,
    ChangeBatch,
    ChangeCursor,
    ChangeStreamBusyError,
    CountKind,
    CountResult,
    Coverage,
    CoverageReason,
    DiagnosticsProjection,
    DiagnosticsQuery,
    DirectoryProjection,
    DirectoryQuery,
    EngineVersion,
    EntryPresence,
    EntryProjection,
    EntryQuery,
    EntryType,
    FilteredTreeQuery,
    Freshness,
    GroupedTreeQuery,
    IndexProgress,
    IndexState,
    InventoryClosedError,
    InventoryConfig,
    InventoryContractError,
    InventoryEntry,
    InventoryIssue,
    IssueCode,
    LifecyclePhase,
    NavigationQuery,
    PriorityRequest,
    ProjectionResult,
    ProviderDiagnostics,
    QueryKind,
    QueryLimitProjection,
    ReadQuery,
    ReadRequest,
    ReadResult,
    RecentQuery,
    RefreshReceipt,
    RefreshRequest,
    RollupQuery,
    SourceKind,
    VersionUnavailableError,
    WorkCounters,
    canonical_inventory_path,
    inventory_scope_fingerprint,
    native_inventory_path,
)
from metabrowser.inventory_engine.providers.python_inventory import _PythonInventoryStore

LOG = logging.getLogger("metabrowser.inventory_engine.providers.fdu_spike")

PROVIDER_ID = "fdu"
_CONTRACT_ID = "inventory-provider-v1"
# fdu 0.6.0 refuses a page limit outside 1..=4096 (`OpenedIndexLimitError`), so both the
# temporary fallback image and any Metabrowser page larger than this are assembled from
# several native pages at one pinned version.
NATIVE_MAX_PAGE_ROWS = 4_096
_MATERIALIZE_PAGE_ROWS = NATIVE_MAX_PAGE_ROWS
_MATERIALIZE_PAGE_WORK = 1_000_000
# The 2A spike measured iterator cancellation joining within this poll interval.
_CHANGE_POLL_SECONDS = 0.25
# Bounded attempts for an unpinned read whose follow-up native read found the version
# moved; a pinned read raises VersionUnavailableError instead of retrying.
_READ_ATTEMPTS = 4
# Handle-local continuation ledger: fdu's own continuation table holds 128 records, so
# twice that is enough to never be the tighter bound.
_LEDGER_CAPACITY = 256
# Rows per native page when probing a file-less directory for symlink leaves.
_EMPTY_PROBE_ROWS = 256
_EMPTY_PROBE_PAGES = 64
# How often the discovery monitor checks native state to emit the walker-complete record
# the serving benchmark reads (the Python walker logs it from inside its own loop).
_DISCOVERY_MONITOR_SECONDS = 0.02
# fdu budgets its journal in bytes and refuses less than 64 KiB; Metabrowser states
# replay capacity in batches. There is no exact translation, so the spike scales the
# batch count by a 4 KiB allowance and clamps at fdu's floor.
_JOURNAL_BYTES_PER_BATCH = 4_096
_MIN_JOURNAL_BYTES = 64 * 1024

_TRUTHY = {"1", "true", "yes", "on"}


def _env_flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in _TRUTHY


# One exact native version's flat image may be reused by later fallback reads at that
# same version (the Python provider memoizes per revision in the same way). Off means
# every fallback read rematerializes. Neither mode keeps an image across versions.
IMAGE_MEMO = _env_flag("FDU_SPIKE_IMAGE_MEMO", True)
# Compare fdu's logical extension with Metabrowser's derive_ext for every converted file.
VERIFY_EXTENSIONS = _env_flag("FDU_SPIKE_VERIFY_EXT", False)

_ENTRY_TYPES = {
    fdu.EntryKind.FILE: EntryType.FILE,
    fdu.EntryKind.DIR: EntryType.DIRECTORY,
    fdu.EntryKind.SYMLINK: EntryType.SYMLINK,
}
_PHASES = {phase.value: LifecyclePhase(phase.value) for phase in fdu.LifecyclePhase}
_COVERAGE_REASONS = {reason.value: CoverageReason(reason.value) for reason in fdu.CoverageReason}
_FALLBACK_KINDS = (
    FilteredTreeQuery,
    GroupedTreeQuery,
    RollupQuery,
    NavigationQuery,
    RecentQuery,
)
_ALL_DATA_QUERIES = frozenset(QueryKind)
_DATA_DOMAINS = frozenset(
    {
        fdu.ImpactDomain.TOPOLOGY,
        fdu.ImpactDomain.METADATA,
        fdu.ImpactDomain.CLASSIFICATION,
        fdu.ImpactDomain.AGGREGATES,
        fdu.ImpactDomain.CONTENT,
    }
)


class _VersionMoved(Exception):
    """A follow-up native read at the first read's version found it gone."""


def downlevel_registry(document: str, probe: AdapterProbe) -> str:
    """Present a schema-5 registry to fdu 0.6.0, which reads schema 3 and 4.

    Schema 5 adds one family field, the presentation-only ``chroma_ratio``. fdu's
    registry fingerprint never retains presentation (``hue``, ``lightness_rank``, and
    so on), so removing that field changes no classification and no identity fdu would
    compute from a native schema-5 parser. Any other difference still reaches fdu's
    parser and fails open as a typed error.
    """

    if not re.search(r"(?m)^schema_version = 5$", document):
        return document
    removed = len(re.findall(r"(?m)^chroma_ratio = [0-9.]+\n", document))
    result = re.sub(r"(?m)^chroma_ratio = [0-9.]+\n", "", document)
    result = re.sub(r"(?m)^schema_version = 5$", "schema_version = 4", result, count=1)
    probe.fallback("registry_downlevel", materialized_rows=removed)
    return result


def _translate[T](function: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
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


def _bounded_detail(value: str) -> str:
    value = value or "fdu reported an issue without detail"
    encoded = value.encode("utf-8")
    if len(encoded) <= MAX_ISSUE_DETAIL_BYTES:
        return value
    return encoded[: MAX_ISSUE_DETAIL_BYTES - 3].decode("utf-8", errors="ignore") + "..."


def _work(native: fdu.Work) -> WorkCounters:
    return WorkCounters(**{name: getattr(native, name) for name in WorkCounters.__dataclass_fields__})


def _sum_work(left: WorkCounters, right: WorkCounters) -> WorkCounters:
    return WorkCounters(
        **{
            name: getattr(left, name) + getattr(right, name)
            for name in WorkCounters.__dataclass_fields__
        }
    )


def _sum_metrics(left: BoundaryMetrics, right: BoundaryMetrics) -> BoundaryMetrics:
    cpu = (
        None
        if left.cpu_time_ns is None or right.cpu_time_ns is None
        else left.cpu_time_ns + right.cpu_time_ns
    )
    return BoundaryMetrics(
        bytes_copied=left.bytes_copied + right.bytes_copied,
        lock_wait_ns=left.lock_wait_ns + right.lock_wait_ns,
        cpu_time_ns=cpu,
        wall_time_ns=left.wall_time_ns + right.wall_time_ns,
    )


def _combine_semantics(version: fdu.EngineVersion) -> str:
    """Hash fdu's three native semantic identities in the canonical pair form."""

    components = (
        ("schema", "fdu-semantics-v1"),
        ("ignore_rules", str(version.semantics.ignore_rules_fingerprint)),
        ("reducers", str(version.semantics.reducers_fingerprint)),
        ("type_rules", str(version.semantics.type_rules_fingerprint)),
    )
    payload = json.dumps(sorted(components), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _native_path(path: str) -> str | None:
    return native_inventory_path(path)


@dataclass(frozen=True, slots=True)
class _LedgerEntry:
    identity: tuple[object, ...]
    emitted: int
    count: CountResult | None = None


@dataclass(slots=True)
class _Image:
    """A temporary flat image of one exact native version, for fallback queries only."""

    session: int
    sequence: int
    entries: dict[str, FsEntry]
    files: int
    directories: int
    complete: bool
    native_calls: int
    native_pages: int
    path_bytes: int


class FduInventoryHandle:
    """One opened fdu root behind Metabrowser's ``InventoryHandle`` protocol."""

    def __init__(
        self,
        *,
        root: Path,
        config: InventoryConfig,
        index: fdu.OpenedIndex,
        initial: fdu.ReadResponse,
        probe: AdapterProbe,
        opened_ns: int,
    ) -> None:
        self._root = root
        self._config = config
        self._index = index
        self._probe = probe
        self._scope_fingerprint = inventory_scope_fingerprint(config)
        self._semantic_fingerprint = _combine_semantics(initial.version)
        self._native_session = initial.version.session
        self._session = f"fdu:{initial.version.session:016x}"
        self._native_identity = initial.version
        self._version_lock = threading.Lock()
        self._lifecycle_lock = threading.Lock()
        self._changes_active = False
        self._closing = False
        self._closed = False
        self._close_task: asyncio.Task[None] | None = None
        self._poll_executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="metabrowser-fdu-spike-poll"
        )
        self._work_lock = threading.Lock()
        self._read_requests = 0
        self._cumulative_work = WorkCounters()
        self._cumulative_metrics = BoundaryMetrics(cpu_time_ns=0)
        self._ledger: OrderedDict[str, _LedgerEntry] = OrderedDict()
        self._ledger_lock = threading.Lock()
        # The Python reference oracle, used only as a projection function over a
        # temporary image for the query kinds fdu has no projection for.
        self._oracle = _PythonInventoryStore(config=config)
        self._oracle._root = root
        self._oracle._session = self._session
        self._oracle_lock = threading.Lock()
        self._image: _Image | None = None
        self._directories_indexed = 0
        self._opened_ns = opened_ns
        self._monitor_stop = threading.Event()
        self._monitor = threading.Thread(
            target=self._monitor_discovery,
            name="metabrowser-fdu-spike-discovery-monitor",
            daemon=True,
        )
        self._monitor.start()

    # Identity and state translation ---------------------------------------------------

    def _remember(self, version: fdu.EngineVersion) -> None:
        if version.session != self._native_session:
            raise InventoryContractError("fdu changed session identity without reopening")
        if _combine_semantics(version) != self._semantic_fingerprint:
            self._probe.typed_failure("semantic_identity_moved")
            raise InventoryContractError("fdu changed semantic identity within one session")
        with self._version_lock:
            self._native_identity = version

    def _to_version(self, version: fdu.EngineVersion) -> EngineVersion:
        return EngineVersion(
            session=self._session,
            sequence=version.sequence,
            scope_fingerprint=self._scope_fingerprint,
            semantic_fingerprint=self._semantic_fingerprint,
        )

    def _native_expected(self, version: EngineVersion | None) -> fdu.EngineVersion | None:
        if version is None:
            return None
        if (
            version.session != self._session
            or version.scope_fingerprint != self._scope_fingerprint
            or version.semantic_fingerprint != self._semantic_fingerprint
        ):
            raise VersionUnavailableError("the requested version belongs to another fdu session")
        with self._version_lock:
            identity = self._native_identity
        return replace(identity, sequence=version.sequence)

    def _canonical(self, value: Path | None) -> str | None:
        if value is None:
            return None
        if value.is_absolute():
            try:
                value = value.relative_to(self._root)
            except ValueError:
                return None
        text = os.fsdecode(value)
        if text in {"", "."}:
            return ""
        return canonical_inventory_path(text.replace(os.sep, "/"))

    def _issues(self, diagnostics: fdu.ReadDiagnostics | None) -> tuple[InventoryIssue, ...]:
        if diagnostics is None:
            return ()
        issues = [
            InventoryIssue(
                code=IssueCode(issue.kind.value),
                detail=_bounded_detail(issue.message),
                path=self._canonical(issue.path),
                transient=issue.kind
                in {fdu.IssueKind.DISAPPEARED, fdu.IssueKind.OBSERVATION_GAP},
            )
            for issue in diagnostics.issues[:MAX_INVENTORY_ISSUES]
        ]
        return tuple(issues)

    def _state(
        self, state: fdu.OpenedState, diagnostics: fdu.ReadDiagnostics | None
    ) -> IndexState:
        issues = self._issues(diagnostics)
        if state.issues.omitted and issues:
            # The contract has no omitted count; summarize in the last retained record.
            last = issues[-1]
            issues = (
                *issues[:-1],
                replace(
                    last,
                    detail=_bounded_detail(
                        f"{last.detail} (+{state.issues.omitted} further issues omitted by fdu)"
                    ),
                ),
            )
        return IndexState(
            phase=_PHASES[state.phase.value],
            coverage=Coverage(
                complete=state.coverage.kind is fdu.CoverageKind.COMPLETE,
                reason=(
                    _COVERAGE_REASONS[state.coverage.reason.value]
                    if state.coverage.reason is not None
                    else None
                ),
            ),
            freshness=Freshness(state.freshness.value),
            source=SourceKind(state.source.value),
            progress=IndexProgress(
                entries_observed=state.progress.files_retained,
                directories_observed=state.progress.directories_complete,
            ),
            issues=issues,
        )

    def _watch_facts(self, state: fdu.OpenedState) -> tuple[str, str, str]:
        if self._config.watch_mode == "off":
            return "off", "off", "disabled"
        if state.phase is fdu.LifecyclePhase.STOPPED:
            if state.coverage.reason is fdu.CoverageReason.BUDGET:
                return "native", "off", "resource_budget"
            return "native", "off", "stopped"
        if state.phase is fdu.LifecyclePhase.FAILED:
            return "native", "failed", "provider_failure"
        if state.phase is fdu.LifecyclePhase.WATCHING:
            return "native", "watching", "native"
        if state.phase is fdu.LifecyclePhase.READY:
            return "native", "failed", "observer_stopped"
        return "native", "starting", "discovery"

    # Entry conversion ---------------------------------------------------------------

    def _extension(self, entry: fdu.Entry, name: str) -> str:
        classification = entry.classification
        native = (
            classification.logical_extension
            if classification is not None and classification.logical_extension is not None
            else ""
        )
        if VERIFY_EXTENSIONS:
            self._probe.extension(entry.portable_path, native, derive_ext(name))
        return native

    def _contract_entry(
        self, entry: fdu.Entry, *, complete: bool, empty: bool | None = None
    ) -> InventoryEntry:
        path = entry.portable_path
        parent, separator, name = path.rpartition("/")
        if not separator:
            parent = ""
            name = path if path else self._root.name
        entry_type = _ENTRY_TYPES.get(entry.kind)
        if entry_type is None:
            self._probe.typed_failure("special_entry")
            raise InventoryContractError("fdu returned a special entry the contract excludes")
        if entry_type is EntryType.FILE:
            return InventoryEntry(
                path=path,
                parent=parent,
                name=name,
                type=entry_type,
                ext=self._extension(entry, name),
                size=entry.attrs.size,
                mtime_ns=entry.attrs.mtime_ns,
                gitignored=entry.ignored,
            )
        if entry_type is EntryType.SYMLINK:
            return InventoryEntry(
                path=path,
                parent=parent,
                name=name,
                type=entry_type,
                ext="",
                size=entry.attrs.size,
                mtime_ns=entry.attrs.mtime_ns,
                gitignored=entry.ignored,
            )
        rollup = entry.rollup
        if not complete or rollup is None:
            return InventoryEntry(
                path=path,
                parent=parent,
                name=name,
                type=entry_type,
                ext="",
                size=0,
                mtime_ns=0,
                gitignored=entry.ignored,
            )
        newest = rollup.all.newest_mtime_ns or 0
        return InventoryEntry(
            path=path,
            parent=parent,
            name=name,
            type=entry_type,
            ext="",
            size=0,
            mtime_ns=newest,
            gitignored=entry.ignored,
            total_files=rollup.all.files,
            total_size=rollup.all.bytes,
            unignored_files=rollup.unignored.files,
            unignored_size=rollup.unignored.bytes,
            newest_mtime_ns=newest,
            empty=(False if rollup.all.files else empty),
        )

    def _fs_entry(self, entry: fdu.Entry, *, complete: bool) -> FsEntry:
        contract = self._contract_entry(entry, complete=complete, empty=True)
        kind = contract.type.value
        return FsEntry(
            contract.path,
            contract.parent,
            contract.name,
            cast("Any", kind),
            contract.ext,
            kind,
            contract.size,
            contract.mtime_ns,
            "",
            False,
            (),
            (),
            contract.total_files,
            contract.total_size,
            contract.unignored_files,
            contract.unignored_size,
            contract.newest_mtime_ns,
            contract.empty,
            contract.gitignored,
        )

    # Continuation tokens --------------------------------------------------------------

    def _token(self, kind: str, continuation: fdu.Continuation) -> str:
        return f"fdu.{kind}.{continuation.session:x}.{continuation.ordinal:x}"

    def _decode(self, kind: str, token: str) -> fdu.Continuation:
        parts = token.split(".")
        if len(parts) != 4 or parts[0] != "fdu" or parts[1] != kind:
            raise VersionUnavailableError(f"the {kind} continuation is not an fdu page token")
        try:
            session = int(parts[2], 16)
            ordinal = int(parts[3], 16)
        except ValueError as error:
            raise VersionUnavailableError(f"the {kind} continuation is malformed") from error
        return fdu.Continuation(session=session, ordinal=ordinal)

    def _ledger_put(
        self,
        token: str,
        identity: tuple[object, ...],
        emitted: int,
        count: CountResult | None = None,
    ) -> None:
        with self._ledger_lock:
            self._ledger[token] = _LedgerEntry(identity=identity, emitted=emitted, count=count)
            while len(self._ledger) > _LEDGER_CAPACITY:
                self._ledger.popitem(last=False)

    def _ledger_take(self, token: str, identity: tuple[object, ...]) -> _LedgerEntry:
        with self._ledger_lock:
            entry = self._ledger.get(token)
            if entry is None or entry.identity != identity:
                raise VersionUnavailableError(
                    "the continuation is unavailable or belongs to a different query"
                )
            return entry

    def _ledger_consume(self, token: str) -> None:
        with self._ledger_lock:
            self._ledger.pop(token, None)

    # Native projection planning --------------------------------------------------------

    @staticmethod
    def _directory_identity(query: DirectoryQuery) -> tuple[object, ...]:
        return ("directory", query.path, query.max_depth, query.include_ignored)

    @staticmethod
    def _catalog_identity(query: CatalogQuery) -> tuple[object, ...]:
        return (
            "catalog",
            query.include_ignored,
            query.terminal_extensions,
            query.ancestor_names,
            query.size_less_than,
            query.count_cap,
        )

    @staticmethod
    def _catalog_selection(query: CatalogQuery) -> fdu.EntrySelection:
        return fdu.EntrySelection(
            query=fdu.Selection(kinds=(fdu.EntryKind.FILE,)),
            max_size=None if query.size_less_than is None else query.size_less_than - 1,
            exclude_ignored=not query.include_ignored,
            terminal_extensions=query.terminal_extensions,
            ancestor_names=query.ancestor_names,
        )

    # Reads ---------------------------------------------------------------------------

    async def read(self, request: ReadRequest) -> ReadResult:
        self._ensure_open()
        return await asyncio.to_thread(self._read_sync, request)

    def _ensure_open(self) -> None:
        with self._lifecycle_lock:
            if self._closed or self._closing:
                raise InventoryClosedError("the fdu inventory handle is closed")

    def _read_sync(self, request: ReadRequest) -> ReadResult:
        wall_started = time.monotonic_ns()
        cpu_started = time.thread_time_ns()
        attempts = 1 if request.at_version is not None else _READ_ATTEMPTS
        for attempt in range(attempts):
            try:
                result = self._read_once(request)
            except _VersionMoved as moved:
                if request.at_version is not None or attempt + 1 == attempts:
                    raise VersionUnavailableError(
                        "the fdu version moved during a coherent read"
                    ) from moved
                self._probe.count("read_retries")
                continue
            metrics = _sum_metrics(
                result.metrics,
                BoundaryMetrics(
                    cpu_time_ns=time.thread_time_ns() - cpu_started,
                    wall_time_ns=time.monotonic_ns() - wall_started,
                ),
            )
            metrics = replace(
                metrics,
                cpu_time_ns=time.thread_time_ns() - cpu_started,
                wall_time_ns=time.monotonic_ns() - wall_started,
            )
            with self._work_lock:
                self._read_requests += 1
                self._cumulative_work = _sum_work(self._cumulative_work, result.work)
                self._cumulative_metrics = _sum_metrics(self._cumulative_metrics, metrics)
            return replace(result, metrics=metrics)
        raise AssertionError("unreachable")  # pragma: no cover

    def _checkpoint(self, expected: fdu.EngineVersion | None) -> ReadResult:
        response = _translate(self._index.state)
        self._remember(response.version)
        if expected is not None and response.version.sequence != expected.sequence:
            raise VersionUnavailableError("the requested fdu version is no longer current")
        diagnostics: fdu.ReadDiagnostics | None = None
        if response.state.issues.retained or response.state.issues.omitted:
            try:
                follow = _translate(self._index.read, fdu.Diagnostics(), expected=response.version)
            except VersionUnavailableError as error:
                raise _VersionMoved() from error
            first = follow.results[0]
            if isinstance(first, fdu.DiagnosticsResult):
                diagnostics = first.value
        version = self._to_version(response.version)
        return ReadResult(
            version=version,
            cursor=version.cursor,
            state=self._state(response.state, diagnostics),
            projections=(),
            work=_work(response.work),
        )

    def _read_once(self, request: ReadRequest) -> ReadResult:
        expected = self._native_expected(request.at_version)
        if not request.queries:
            return self._checkpoint(expected)

        projections: list[fdu.Projection] = []
        # (query, native index of main projection, native index of aggregate or -1)
        plan: list[tuple[ReadQuery, int, int]] = []
        fallback_queries: list[ReadQuery] = []
        for query in request.queries:
            if isinstance(query, EntryQuery):
                native = _native_path(query.path)
                if native is None:
                    plan.append((query, -1, -1))
                    continue
                plan.append((query, len(projections), -1))
                projections.append(fdu.Lookup(native))
            elif isinstance(query, DirectoryQuery):
                page = fdu.Page(
                    limit=min(query.max_rows, NATIVE_MAX_PAGE_ROWS), max_work=query.max_work
                )
                if query.after is not None:
                    self._ledger_take(query.after, self._directory_identity(query))
                    plan.append((query, len(projections), -1))
                    projections.append(
                        fdu.Continue(continuation=self._decode("tree", query.after), page=page)
                    )
                else:
                    native = _native_path(query.path)
                    if native is None:
                        plan.append((query, -1, -1))
                        continue
                    plan.append((query, len(projections), -1))
                    projections.append(
                        fdu.Tree(
                            path=native,
                            page=page,
                            depth=query.max_depth,
                            include_ignored=query.include_ignored,
                        )
                    )
            elif isinstance(query, CatalogQuery):
                page = fdu.Page(
                    limit=min(query.max_rows, NATIVE_MAX_PAGE_ROWS), max_work=query.max_work
                )
                selection = self._catalog_selection(query)
                main_index = len(projections)
                if query.after is not None:
                    self._ledger_take(query.after, self._catalog_identity(query))
                    projections.append(
                        fdu.Continue(continuation=self._decode("flat", query.after), page=page)
                    )
                else:
                    projections.append(
                        fdu.Flat(selection=selection, shape=fdu.RowShape.COMPACT, page=page)
                    )
                aggregate_index = -1
                if query.after is None:
                    # A continued page reuses the first page's count from the ledger, as
                    # the Python oracle reuses its memo: recounting would rescan the whole
                    # selection under the page's work bound.
                    aggregate_index = len(projections)
                    projections.append(
                        fdu.Aggregate(
                            selection=selection,
                            count_cap=query.count_cap,
                            max_work=query.max_work,
                        )
                    )
                plan.append((query, main_index, aggregate_index))
            elif isinstance(query, DiagnosticsQuery):
                plan.append((query, -1, -1))
            elif isinstance(query, _FALLBACK_KINDS):
                plan.append((query, -1, -1))
                fallback_queries.append(query)
            else:  # pragma: no cover - the algebra is closed
                raise InventoryContractError(f"unsupported query {type(query).__name__}")
        # Helper projections cost native work, so they ride along only when a fallback
        # (entry count, root record) or a diagnostics query needs them. A read whose state
        # carries issues fetches them in a follow-up read at the same version.
        needs_helpers = bool(fallback_queries) or any(
            isinstance(query, DiagnosticsQuery) for query in request.queries
        )
        root_index = diagnostics_index = -1
        if needs_helpers:
            root_index = len(projections)
            projections.append(fdu.Lookup(""))
            diagnostics_index = len(projections)
            projections.append(fdu.Diagnostics())

        native_started = time.monotonic_ns()
        first = _translate(self._index.read, *projections, expected=expected)
        native_wall = time.monotonic_ns() - native_started
        self._remember(first.version)
        version = first.version
        complete = first.state.coverage.kind is fdu.CoverageKind.COMPLETE
        diagnostics: fdu.ReadDiagnostics | None = None
        root_entry: fdu.Entry | None = None
        if needs_helpers:
            diagnostics_result = first.results[diagnostics_index]
            if isinstance(diagnostics_result, fdu.DiagnosticsResult):
                diagnostics = diagnostics_result.value
            root_result = first.results[root_index]
            if isinstance(root_result, fdu.LookupResult):
                root_entry = root_result.value.value
        elif first.state.issues.retained or first.state.issues.omitted:
            try:
                follow = _translate(self._index.read, fdu.Diagnostics(), expected=version)
            except VersionUnavailableError as error:
                raise _VersionMoved() from error
            follow_result = follow.results[0]
            if isinstance(follow_result, fdu.DiagnosticsResult):
                diagnostics = follow_result.value
        if root_entry is not None and root_entry.rollup is not None:
            self._directories_indexed = root_entry.rollup.all.dirs
        state = self._state(first.state, diagnostics)
        work = _work(first.work)
        metrics = BoundaryMetrics()
        results: dict[str, ProjectionResult] = {}

        for query, main_index, aggregate_index in plan:
            if isinstance(query, EntryQuery):
                results[query.query_id] = self._entry_projection(
                    query, first.results[main_index] if main_index >= 0 else None, complete
                )
                self._probe.native("entry", rows_returned=1, wall_time_ns=native_wall)
            elif isinstance(query, DirectoryQuery):
                results[query.query_id], extra = self._directory_projection(
                    query,
                    first.results[main_index] if main_index >= 0 else None,
                    complete=complete,
                    version=version,
                )
                work = _sum_work(work, extra)
            elif isinstance(query, CatalogQuery):
                results[query.query_id], extra = self._catalog_projection(
                    query,
                    first.results[main_index],
                    first.results[aggregate_index] if aggregate_index >= 0 else None,
                    version=version,
                )
                work = _sum_work(work, extra)

        if fallback_queries:
            fallback_results, fallback_work, fallback_metrics = self._fallback(
                fallback_queries,
                version=version,
                total_entries=diagnostics.entries if diagnostics is not None else 0,
                complete=complete,
                root_entry=root_entry,
                first=first,
                at_version=request.at_version,
            )
            results.update(fallback_results)
            work = _sum_work(work, fallback_work)
            metrics = _sum_metrics(metrics, fallback_metrics)

        for query in request.queries:
            if isinstance(query, DiagnosticsQuery):
                results[query.query_id] = DiagnosticsProjection(
                    query_id=query.query_id, payload=self._diagnostics(first.state)
                )

        translated = self._to_version(version)
        return ReadResult(
            version=translated,
            cursor=translated.cursor,
            state=state,
            projections=tuple(results[query.query_id] for query in request.queries),
            work=work,
            metrics=metrics,
        )

    def _entry_projection(
        self, query: EntryQuery, result: fdu.ProjectionResult | None, complete: bool
    ) -> EntryProjection:
        if result is None:
            presence = EntryPresence.ABSENT if complete else EntryPresence.UNKNOWN
            return EntryProjection(query_id=query.query_id, presence=presence, entry=None)
        if not isinstance(result, fdu.LookupResult):
            raise InventoryContractError("fdu answered a lookup with another projection")
        knowledge = result.value
        if knowledge.kind is fdu.KnowledgeKind.PRESENT and knowledge.value is not None:
            entry = self._contract_entry(knowledge.value, complete=complete)
            if entry.type is EntryType.DIRECTORY and entry.empty is None and complete:
                entry = replace(entry, empty=not self._has_leaf(entry.path, None))
            return EntryProjection(
                query_id=query.query_id, presence=EntryPresence.PRESENT, entry=entry
            )
        presence = (
            EntryPresence.ABSENT
            if knowledge.kind is fdu.KnowledgeKind.ABSENT
            else EntryPresence.UNKNOWN
        )
        return EntryProjection(query_id=query.query_id, presence=presence, entry=None)

    def _has_leaf(self, path: str, version: fdu.EngineVersion | None) -> bool:
        """Whether a file-less directory holds a symlink leaf (fdu counts files only)."""

        native = _native_path(path)
        if native is None:
            return False
        started = time.monotonic_ns()
        cpu = time.thread_time_ns()
        with self._version_lock:
            expected = version or self._native_identity
        calls = 0
        rows_seen = 0
        found = False
        projection: fdu.Projection = fdu.Tree(
            path=native,
            page=fdu.Page(limit=_EMPTY_PROBE_ROWS, max_work=_MATERIALIZE_PAGE_WORK),
            depth=fdu.Bound.ALL,
        )
        for _page in range(_EMPTY_PROBE_PAGES):
            calls += 1
            try:
                response = _translate(self._index.read, projection, expected=expected)
            except VersionUnavailableError as error:
                raise _VersionMoved() from error
            result = response.results[0]
            if not isinstance(result, fdu.TreeResult) or result.value.value is None:
                break
            page = result.value.value
            rows_seen += len(page.rows)
            if any(row.kind is not fdu.EntryKind.DIR for row in page.rows):
                found = True
                break
            if page.next is None:
                break
            projection = fdu.Continue(
                continuation=page.next,
                page=fdu.Page(limit=_EMPTY_PROBE_ROWS, max_work=_MATERIALIZE_PAGE_WORK),
            )
        else:
            self._probe.typed_failure("empty_probe_unbounded")
            raise InventoryContractError("the empty probe exceeded its page bound")
        self._probe.fallback(
            "directory_empty_probe",
            native_calls=calls,
            native_pages=calls,
            materialized_rows=rows_seen,
            wall_time_ns=time.monotonic_ns() - started,
            cpu_time_ns=time.thread_time_ns() - cpu,
        )
        return found

    def _chain(
        self,
        kind: str,
        rows: list[fdu.Entry],
        continuation: fdu.Continuation | None,
        *,
        max_rows: int,
        max_work: int,
        version: fdu.EngineVersion,
    ) -> tuple[fdu.Continuation | None, WorkCounters]:
        """Fill a Metabrowser page larger than fdu's native page bound at one version."""

        extra = WorkCounters()
        calls = 0
        started = time.monotonic_ns()
        while continuation is not None and len(rows) < max_rows:
            calls += 1
            projection = fdu.Continue(
                continuation=continuation,
                page=fdu.Page(
                    limit=min(max_rows - len(rows), NATIVE_MAX_PAGE_ROWS), max_work=max_work
                ),
            )
            try:
                response = _translate(self._index.read, projection, expected=version)
            except VersionUnavailableError as error:
                raise _VersionMoved() from error
            extra = _sum_work(extra, _work(response.work))
            result = response.results[0]
            if isinstance(result, fdu.TreeResult) and result.value.value is not None:
                rows.extend(result.value.value.rows)
                continuation = result.value.value.next
            elif isinstance(result, fdu.FlatResult):
                rows.extend(result.value.rows)
                continuation = result.value.next
            else:
                self._probe.typed_failure(f"{kind}_chain_refused")
                raise _VersionMoved()
        if calls:
            self._probe.fallback(
                "page_chaining",
                native_calls=calls,
                native_pages=calls,
                rows_returned=len(rows),
                wall_time_ns=time.monotonic_ns() - started,
            )
        return continuation, extra

    def _directory_projection(
        self,
        query: DirectoryQuery,
        result: fdu.ProjectionResult | None,
        *,
        complete: bool,
        version: fdu.EngineVersion,
    ) -> tuple[ProjectionResult, WorkCounters]:
        none = WorkCounters()
        if query.after is not None:
            self._ledger_consume(query.after)
        if result is None:
            return DirectoryProjection(query_id=query.query_id, entries=()), none
        if isinstance(result, fdu.LimitResult):
            if query.after is not None:
                # fdu restores an underfunded continuation; keep the ledger entry too.
                self._ledger_put(query.after, self._directory_identity(query), 0)
            return QueryLimitProjection(
                query_id=query.query_id,
                query_kind=QueryKind.DIRECTORY,
                max_work=query.max_work,
                rows_visited=min(result.rows_visited, query.max_work),
            ), none
        if isinstance(result, fdu.RefusedResult):
            if result.reason is fdu.RefusalReason.NOT_A_DIRECTORY:
                return DirectoryProjection(query_id=query.query_id, entries=()), none
            raise VersionUnavailableError(f"fdu refused the directory page: {result.reason.value}")
        if not isinstance(result, fdu.TreeResult):
            raise InventoryContractError("fdu answered a tree with another projection")
        knowledge = result.value
        if knowledge.value is None:
            return DirectoryProjection(query_id=query.query_id, entries=()), none
        page = knowledge.value
        rows = list(page.rows)
        continuation, extra = self._chain(
            "tree",
            rows,
            page.next,
            max_rows=query.max_rows,
            max_work=query.max_work,
            version=version,
        )
        entries: list[InventoryEntry] = []
        for row in rows:
            entry = self._contract_entry(row, complete=complete)
            if entry.type is EntryType.DIRECTORY and complete and entry.empty is None:
                entry = replace(entry, empty=not self._has_leaf(entry.path, version))
            entries.append(entry)
        next_page: str | None = None
        if continuation is not None:
            next_page = self._token("tree", continuation)
            self._ledger_put(next_page, self._directory_identity(query), 0)
        self._probe.native("directory", rows_returned=len(entries), wall_time_ns=0)
        return DirectoryProjection(
            query_id=query.query_id, entries=tuple(entries), next_page=next_page
        ), extra

    def _catalog_projection(
        self,
        query: CatalogQuery,
        result: fdu.ProjectionResult,
        aggregate: fdu.ProjectionResult | None,
        *,
        version: fdu.EngineVersion,
    ) -> tuple[ProjectionResult, WorkCounters]:
        none = WorkCounters()
        emitted_before = 0
        carried: CountResult | None = None
        if query.after is not None:
            ledger = self._ledger_take(query.after, self._catalog_identity(query))
            emitted_before = ledger.emitted
            carried = ledger.count
        if isinstance(result, fdu.LimitResult):
            return QueryLimitProjection(
                query_id=query.query_id,
                query_kind=QueryKind.CATALOG,
                max_work=query.max_work,
                rows_visited=min(result.rows_visited, query.max_work),
            ), none
        if isinstance(result, fdu.RefusedResult):
            raise VersionUnavailableError(f"fdu refused the catalog page: {result.reason.value}")
        if not isinstance(result, fdu.FlatResult):
            raise InventoryContractError("fdu answered a catalog with another projection")
        if isinstance(aggregate, fdu.LimitResult):
            return QueryLimitProjection(
                query_id=query.query_id,
                query_kind=QueryKind.CATALOG,
                max_work=query.max_work,
                rows_visited=min(aggregate.rows_visited, query.max_work),
            ), none
        if aggregate is not None and not isinstance(aggregate, fdu.AggregateResult):
            raise InventoryContractError("fdu answered a catalog count with another projection")
        if query.after is not None:
            self._ledger_consume(query.after)
        rows = list(result.value.rows)
        continuation, extra = self._chain(
            "flat",
            rows,
            result.value.next,
            max_rows=query.max_rows,
            max_work=query.max_work,
            version=version,
        )
        records = tuple(
            CatalogRecord(
                path=row.portable_path,
                logical_extension=self._extension(row, row.portable_path.rpartition("/")[2]),
                size=row.attrs.size,
                mtime_ns=row.attrs.mtime_ns,
            )
            for row in rows
        )
        emitted = emitted_before + len(records)
        if aggregate is not None:
            native_count = aggregate.value
            first_count = CountResult(
                CountKind.EXACT
                if native_count.kind is fdu.CountKind.EXACT
                else CountKind.AT_LEAST,
                native_count.value,
            )
        elif carried is not None:
            first_count = carried
            self._probe.fallback("catalog_offset_ledger", rows_returned=len(records))
        else:  # pragma: no cover - a ledger entry always carries the first count
            raise VersionUnavailableError("the catalog continuation lost its count")
        if first_count.kind is CountKind.EXACT:
            total = first_count
        else:
            total = CountResult(CountKind.AT_LEAST, max(first_count.value, emitted))
        next_page: str | None = None
        if continuation is not None:
            next_page = self._token("flat", continuation)
            self._ledger_put(next_page, self._catalog_identity(query), emitted, first_count)
        self._probe.native("catalog", rows_returned=len(records), wall_time_ns=0)
        return CatalogProjection(
            query_id=query.query_id, records=records, total_matches=total, next_page=next_page
        ), extra

    # Temporary fallback ----------------------------------------------------------------

    def _materialize(
        self,
        version: fdu.EngineVersion,
        *,
        complete: bool,
        root_entry: fdu.Entry | None,
    ) -> tuple[_Image, bool]:
        cached = self._image
        if (
            IMAGE_MEMO
            and cached is not None
            and cached.session == version.session
            and cached.sequence == version.sequence
        ):
            return cached, True
        page = fdu.Page(limit=_MATERIALIZE_PAGE_ROWS, max_work=_MATERIALIZE_PAGE_WORK)
        projection: fdu.Projection = fdu.Flat(shape=fdu.RowShape.FULL, page=page)
        entries: dict[str, FsEntry] = {}
        if root_entry is not None:
            root = self._fs_entry(root_entry, complete=complete)
            entries[""] = root
        calls = 0
        path_bytes = 0
        files = 0
        directories = 0
        symlink_parents: set[str] = set()
        while True:
            calls += 1
            try:
                response = _translate(self._index.read, projection, expected=version)
            except VersionUnavailableError as error:
                raise _VersionMoved() from error
            result = response.results[0]
            if isinstance(result, fdu.LimitResult):
                self._probe.typed_failure("materialize_limit")
                raise InventoryContractError("fdu refused the fallback image page work bound")
            if isinstance(result, fdu.RefusedResult):
                raise _VersionMoved()
            if not isinstance(result, fdu.FlatResult):
                raise InventoryContractError("fdu answered the image page with another projection")
            for row in result.value.rows:
                entry = self._fs_entry(row, complete=complete)
                entries[entry.path] = entry
                path_bytes += len(entry.path.encode("utf-8"))
                if entry.type == "file":
                    files += 1
                elif entry.type == "dir":
                    directories += 1
                else:
                    symlink_parents.add(entry.parent)
            if result.value.next is None:
                break
            projection = fdu.Continue(continuation=result.value.next, page=page)
        if complete:
            # fdu's rollup counts files only; a directory holding only symlinks is not empty.
            ancestors: set[str] = set()
            for parent in symlink_parents:
                cursor = parent
                while cursor not in ancestors:
                    ancestors.add(cursor)
                    if not cursor:
                        break
                    cursor = cursor.rpartition("/")[0]
            for path in ancestors:
                existing = entries.get(path)
                if existing is not None and existing.empty:
                    entries[path] = replace(existing, empty=False)
        image = _Image(
            session=version.session,
            sequence=version.sequence,
            entries=entries,
            files=files,
            directories=directories,
            complete=complete,
            native_calls=calls,
            native_pages=calls,
            path_bytes=path_bytes,
        )
        self._image = image if IMAGE_MEMO else None
        return image, False

    def _load_oracle(self, image: _Image) -> None:
        oracle = self._oracle
        if (
            IMAGE_MEMO
            and oracle._entries is image.entries
            and oracle._rollup_generation == image.sequence
        ):
            return
        oracle._entries = image.entries
        oracle._children_index = {}
        oracle._files_indexed = image.files
        oracle._directories_indexed = image.directories
        oracle._status = "done" if image.complete else "scanning"
        with oracle._rollup_cache_lock:
            oracle._rollup_generation = image.sequence
        oracle._subtree_aggregates = {}
        oracle._aggregate_evicted_at = {}
        oracle._navigation_tally_memo = None
        oracle._navigation_read_memo = None

    def _fallback(
        self,
        queries: Sequence[ReadQuery],
        *,
        version: fdu.EngineVersion,
        total_entries: int,
        complete: bool,
        root_entry: fdu.Entry | None,
        first: fdu.ReadResponse,
        at_version: EngineVersion | None,
    ) -> tuple[dict[str, ProjectionResult], WorkCounters, BoundaryMetrics]:
        results: dict[str, ProjectionResult] = {}
        work = WorkCounters()
        metrics = BoundaryMetrics()
        pending: list[ReadQuery] = []
        for query in queries:
            max_work = cast("int", getattr(query, "max_work"))
            # The oracle visits every retained entry, so a bound below that is a typed
            # limit before any materialization, charged at the bound as Python charges it.
            if total_entries > max_work and not (
                isinstance(query, FilteredTreeQuery) and query.after is not None
            ):
                results[query.query_id] = QueryLimitProjection(
                    query_id=query.query_id,
                    query_kind=query.kind,
                    max_work=max_work,
                    rows_visited=max_work,
                )
                work = _sum_work(work, WorkCounters(rows_visited=max_work))
                continue
            pending.append(query)
        if not pending:
            return results, work, metrics
        with self._oracle_lock:
            started = time.monotonic_ns()
            cpu = time.thread_time_ns()
            image, reused = self._materialize(version, complete=complete, root_entry=root_entry)
            self._load_oracle(image)
            materialize_wall = time.monotonic_ns() - started
            materialize_cpu = time.thread_time_ns() - cpu
            oracle_version = self._oracle._version(image.sequence)
            for position, query in enumerate(pending):
                q_started = time.monotonic_ns()
                q_cpu = time.thread_time_ns()
                sub: ReadResult | None = None
                if isinstance(query, FilteredTreeQuery) and query.after is not None:
                    sub = self._oracle._read_cached_page_sync(
                        ReadRequest(queries=(query,), at_version=oracle_version)
                    )
                if sub is None:
                    sub = self._oracle._read_snapshot_sync(ReadRequest(queries=(query,)))
                projection = sub.projections[0]
                results[query.query_id] = projection
                work = _sum_work(work, sub.work)
                q_wall = time.monotonic_ns() - q_started
                q_cpu_ns = time.thread_time_ns() - q_cpu
                kind = query.kind.value
                self._probe.fallback(
                    kind,
                    native_calls=image.native_calls if position == 0 and not reused else 0,
                    native_pages=image.native_pages if position == 0 and not reused else 0,
                    materialized_rows=len(image.entries) if position == 0 and not reused else 0,
                    materialized_path_bytes=(
                        image.path_bytes if position == 0 and not reused else 0
                    ),
                    image_reuses=int(reused or position > 0),
                    child_bucket_builds=(
                        image.directories if isinstance(query, RollupQuery) else 0
                    ),
                    full_result_sorts=int(isinstance(query, (RecentQuery, FilteredTreeQuery))),
                    aggregate_passes=int(
                        isinstance(
                            query,
                            (RollupQuery, NavigationQuery, RecentQuery, FilteredTreeQuery),
                        )
                    )
                    + (len(query.groups) if isinstance(query, GroupedTreeQuery) else 0),
                    rows_returned=sub.work.rows_returned,
                    wall_time_ns=q_wall + (materialize_wall if position == 0 else 0),
                    cpu_time_ns=q_cpu_ns + (materialize_cpu if position == 0 else 0),
                )
            if not IMAGE_MEMO:
                self._oracle._entries = {}
            metrics = BoundaryMetrics(bytes_copied=0 if reused else image.path_bytes)
        del first, at_version
        return results, work, metrics

    def _diagnostics(self, state: fdu.OpenedState) -> ProviderDiagnostics:
        watch_mode, watch_state, watch_reason = self._watch_facts(state)
        with self._work_lock:
            read_requests = self._read_requests + 1
            work = self._cumulative_work
            metrics = self._cumulative_metrics
        return ProviderDiagnostics(
            provider=PROVIDER_ID,
            contract=_CONTRACT_ID,
            files_indexed=state.progress.files_retained,
            directories_indexed=self._directories_indexed,
            watch_mode=watch_mode,
            watch_state=watch_state,
            watch_reason=watch_reason,
            read_requests=read_requests,
            cumulative_work=work,
            cumulative_metrics=metrics,
        )

    # Changes -------------------------------------------------------------------------

    def changes(self, *, after: ChangeCursor | None) -> AsyncGenerator[ChangeBatch, None]:
        return self._changes(after=after)

    async def _changes(self, *, after: ChangeCursor | None) -> AsyncGenerator[ChangeBatch, None]:
        with self._lifecycle_lock:
            if self._closing or self._closed:
                raise InventoryClosedError("the fdu inventory handle is closed")
            if self._changes_active:
                raise ChangeStreamBusyError("one fdu handle permits one active change iterator")
            self._changes_active = True
        try:
            if after is None:
                initial = await asyncio.to_thread(_translate, self._index.state)
                self._remember(initial.version)
                cursor = initial.version
            else:
                if after.session != self._session:
                    raise VersionUnavailableError("the change cursor belongs to another session")
                with self._version_lock:
                    cursor = replace(self._native_identity, sequence=after.sequence)
            loop = asyncio.get_running_loop()
            while True:
                with self._lifecycle_lock:
                    if self._closing or self._closed:
                        return
                future = loop.run_in_executor(
                    self._poll_executor,
                    partial(_translate, self._index.changes, cursor, timeout=_CHANGE_POLL_SECONDS),
                )
                try:
                    poll = await asyncio.shield(future)
                except asyncio.CancelledError:
                    # Iterator-only cancellation joins the in-flight poll, never the handle.
                    try:
                        await future
                    except (InventoryContractError, VersionUnavailableError):
                        pass
                    raise
                except InventoryClosedError:
                    return
                except VersionUnavailableError:
                    # A foreign or future cursor: the consumer must reread from a reset.
                    current = await asyncio.to_thread(_translate, self._index.state)
                    self._remember(current.version)
                    cursor = current.version
                    translated = self._to_version(current.version)
                    self._probe.count("change_batches")
                    yield ChangeBatch(
                        cursor=translated.cursor,
                        version=translated,
                        state=self._state(current.state, None),
                        reset=True,
                    )
                    continue
                self._probe.count("change_polls")
                self._remember(poll.version)
                cursor = poll.cursor
                if poll.outcome.kind is fdu.ChangeOutcomeKind.IDLE:
                    continue
                batch = await asyncio.to_thread(self._batch, poll)
                if batch is None:
                    continue
                self._probe.count("change_batches")
                yield batch
        finally:
            with self._lifecycle_lock:
                self._changes_active = False

    def _batch(self, poll: fdu.ChangePoll) -> ChangeBatch | None:
        diagnostics: fdu.ReadDiagnostics | None = None
        if poll.state.issues.retained or poll.state.issues.omitted:
            try:
                follow = _translate(self._index.read, fdu.Diagnostics(), expected=poll.version)
                first = follow.results[0]
                if isinstance(first, fdu.DiagnosticsResult):
                    diagnostics = first.value
            except VersionUnavailableError:
                # The state moved on; the next poll carries it with its own diagnostics.
                diagnostics = None
        version = self._to_version(poll.version)
        state = self._state(poll.state, diagnostics)
        work = _work(poll.work)
        if poll.outcome.kind is fdu.ChangeOutcomeKind.RESET:
            return ChangeBatch(
                cursor=version.cursor, version=version, state=state, reset=True, work=work
            )
        impact = poll.outcome.impact
        if impact is None:
            raise InventoryContractError("fdu change outcome omitted its impact")
        paths: list[str] = []
        seen: set[str] = set()
        for native in impact.dirty_paths:
            canonical = self._canonical(native)
            if canonical is not None and canonical not in seen:
                seen.add(canonical)
                paths.append(canonical)
        removed_files: set[str] = set()
        non_file: list[str] = []
        for commit in poll.outcome.commits:
            for change in commit.changes:
                canonical = self._canonical(change.path)
                if canonical is None:
                    continue
                if (
                    change.kind is fdu.EffectiveChangeKind.REMOVED
                    and change.entry_kind is fdu.EntryKind.FILE
                ):
                    removed_files.add(canonical)
                elif (
                    change.kind is fdu.EffectiveChangeKind.INSERTED
                    and change.entry_kind in {fdu.EntryKind.DIR, fdu.EntryKind.SYMLINK}
                    and canonical in removed_files
                    and canonical not in non_file
                ):
                    non_file.append(canonical)
        all_dirty = impact.all_dirty or len(paths) > MAX_CHANGE_PATHS
        dirty_queries: set[QueryKind] = set()
        if _DATA_DOMAINS.intersection(impact.domains):
            dirty_queries.update(_ALL_DATA_QUERIES)
        if fdu.ImpactDomain.STATE in impact.domains:
            dirty_queries.add(QueryKind.DIAGNOSTICS)
        if not dirty_queries and not paths and not all_dirty:
            dirty_queries.add(QueryKind.DIAGNOSTICS)
        return ChangeBatch(
            cursor=version.cursor,
            version=version,
            state=state,
            dirty_paths=() if all_dirty else tuple(paths),
            non_file_paths=() if all_dirty else tuple(path for path in non_file if path in seen),
            dirty_queries=frozenset(dirty_queries),
            all_dirty=all_dirty,
            work=work,
        )

    # Commands ------------------------------------------------------------------------

    async def refresh(self, request: RefreshRequest) -> RefreshReceipt:
        self._ensure_open()
        self._probe.count("refreshes")
        natives: list[str] = []
        unrepresentable: list[str] = []
        for path in request.paths:
            native = _native_path(path)
            if native is None:
                unrepresentable.append(path)
            else:
                natives.append(native)
        try:
            receipt = await asyncio.to_thread(_translate, self._index.refresh, natives)
        except InventoryContractError as error:
            if not isinstance(error.__cause__, fdu.OpenedIndexStoppedError):
                raise
            state = await asyncio.to_thread(_translate, self._index.state)
            self._remember(state.version)
            self._probe.typed_failure("refresh_on_stopped_root")
            return RefreshReceipt(
                version=self._to_version(state.version),
                accepted_paths=(),
                rejected_paths=request.paths,
            )
        self._remember(receipt.version)
        accepted = {self._canonical(path) for path in receipt.accepted}
        rejected = {self._canonical(item.path) for item in receipt.rejected}
        rejected.update(unrepresentable)
        return RefreshReceipt(
            version=self._to_version(receipt.version),
            accepted_paths=tuple(path for path in request.paths if path in accepted),
            rejected_paths=tuple(
                path for path in request.paths if path in rejected and path not in accepted
            ),
        )

    async def prioritize(self, request: PriorityRequest) -> None:
        self._ensure_open()
        self._probe.count("priorities")
        natives = [native for native in map(_native_path, request.paths) if native is not None]
        try:
            await asyncio.to_thread(_translate, self._index.prioritize, natives)
        except InventoryContractError as error:
            if isinstance(error.__cause__, fdu.OpenedIndexStoppedError):
                return
            raise

    async def close(self) -> None:
        task = self._close_task
        if task is None:
            with self._lifecycle_lock:
                self._closing = True
            task = asyncio.create_task(self._close_owned(), name="metabrowser-fdu-spike-close")
            self._close_task = task
        await asyncio.shield(task)

    async def _close_owned(self) -> None:
        self._monitor_stop.set()
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(self._poll_executor, partial(_translate, self._index.close))
        finally:
            self._poll_executor.shutdown(wait=True, cancel_futures=False)
            await asyncio.to_thread(self._monitor.join, 2.0)
            self._image = None
            self._oracle._entries = {}
            with self._lifecycle_lock:
                self._closed = True
                self._closing = False

    # Discovery-complete record for the serving benchmark ------------------------------

    def _monitor_discovery(self) -> None:
        while not self._monitor_stop.wait(_DISCOVERY_MONITOR_SECONDS):
            try:
                response = self._index.state()
            except fdu.OpenedIndexError:
                return
            state = response.state
            if state.phase in {fdu.LifecyclePhase.DISCOVERING}:
                continue
            elapsed_ms = (time.monotonic_ns() - self._opened_ns) // 1_000_000
            if state.coverage.kind is fdu.CoverageKind.COMPLETE:
                status = "done"
            elif state.coverage.reason is fdu.CoverageReason.BUDGET:
                status = "truncated"
            elif state.phase is fdu.LifecyclePhase.FAILED:
                status = "failed"
            else:
                status = "cancelled"
            entries = 0
            try:
                diagnostics = self._index.read(fdu.Diagnostics())
                first = diagnostics.results[0]
                if isinstance(first, fdu.DiagnosticsResult):
                    entries = first.value.entries
            except fdu.OpenedIndexError:
                return
            LOG.info(
                "inventory walker complete: provider=%s contract=%s status=%s "
                "files=%d entries=%d elapsed=%dms",
                PROVIDER_ID,
                _CONTRACT_ID,
                status,
                state.progress.files_retained,
                entries,
                elapsed_ms,
            )
            return


class FduInventoryBackend:
    """Construct spike fdu handles without registering a shipping provider."""

    def __init__(self, *, probe: AdapterProbe | None = None) -> None:
        self.probe = probe if probe is not None else AdapterProbe()

    async def open(self, root: Path, config: InventoryConfig) -> FduInventoryHandle:
        if config.watch_mode == "poll":
            self.probe.typed_failure("watch_mode_poll")
            raise InventoryContractError(
                "fdu 0.6.0 has no polling observer; the spike will not fake one"
            )
        opened_ns = time.monotonic_ns()
        canonical_root = await asyncio.to_thread(root.resolve)
        options = fdu.OpenedOptions(
            follow_symlinks=config.follow_symlinks,
            one_filesystem=config.one_filesystem,
            prune_hidden=not config.include_hidden,
            hidden_allow=config.hidden_allowlist,
            exclude_special=True,
            max_files=config.budget.max_files,
            observe=config.watch_mode != "off",
            journal_capacity_bytes=max(
                _MIN_JOURNAL_BYTES, config.change_queue_size * _JOURNAL_BYTES_PER_BATCH
            ),
            type_rules=downlevel_registry(config.registry_document, self.probe),
        )
        index = await asyncio.to_thread(_translate, fdu.OpenedIndex.open, canonical_root, options)
        try:
            initial = await asyncio.to_thread(_translate, index.state)
        except BaseException as open_error:
            try:
                await asyncio.to_thread(_translate, index.close)
            except BaseException as close_error:
                raise BaseExceptionGroup(
                    "fdu spike open and cleanup both failed", (open_error, close_error)
                ) from None
            raise
        return FduInventoryHandle(
            root=canonical_root,
            config=config,
            index=index,
            initial=initial,
            probe=self.probe,
            opened_ns=opened_ns,
        )


__all__ = ["PROVIDER_ID", "FduInventoryBackend", "FduInventoryHandle", "downlevel_registry"]
