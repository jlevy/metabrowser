"""Python reference provider for filesystem inventory and rollups.

``PythonInventoryHandle`` is the retained owner of filesystem-entry
metadata in the browser process. The server lifespan eagerly populates
it, ``/api/tree`` and ``/api/activity`` read from it, and writes emit
``fs.change`` events on a single shared SSE channel so the client
fills in skeleton cells without manual reload.

There is at most one discovery task per opened handle. Concurrent
``/api/tree`` requests do **not** trigger walks — they read whatever
is currently in the index and return ``None`` for fields the walker
has not yet finalized. The boot lifespan hook calls
``PythonInventoryHandle.start(root)`` once; the call is idempotent.

The inventory contract covers cold start, subtree invalidation, and realtime updates.

Walker semantics (verified by tests):

* **Strict level-order BFS.** Every directory at depth N is scanned
  before any at depth N+1, so the layers the nav tree shows — and the
  ones a reader expands first — are complete long before the deep
  tail, and a request landing early in the boot scan finds them
  already populated.
* **Post-order finalize.** A directory's ``FsEntry`` is replaced with
  populated ``total_files`` / ``total_size`` / ``newest_mtime_ns``
  only after every descendant has been walked. Implementation:
  per-directory ``pending_children_count`` decrements as children
  finalize; when it hits zero, the directory finalizes and
  decrements its own parent.
* **Generation counters.** Invalidation walks the ancestor chain
  and bumps each path's generation. The walker only writes a
  result if the generation it started with is still current; stale
  writes lose. This makes invalidation race-free without locks.
* **Safety caps.** ``max_files`` (default 500 000) and ``max_depth``
  (default 20). Hitting either flips ``status`` to ``"truncated"``;
  the walker stops emission past the cap.

The :func:`walk_tree` generator is decoupled from the
``PythonInventoryHandle`` object so tests can drive it directly with
``async for``.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import heapq
import itertools
import logging
import stat as stat_module
import threading
import time
import uuid
from array import array
from bisect import bisect_left
from collections import ChainMap, deque
from collections.abc import AsyncGenerator, Callable, Collection, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Literal

from metabrowser.cancellable_thread import run_cancellable_thread
from metabrowser.events import (
    CapabilityUpdate,
    FsChange,
    FsChangeOp,
    FsEntry,
    FsRemove,
    FsResyncRequired,
    FsUpsert,
    StreamEvent,
    WriteToken,
)
from metabrowser.file_type_filters import (
    canonical_extension,
    category_for_file,
    family_for_extension,
)
from metabrowser.file_type_registry import load_file_type_registry
from metabrowser.inventory_engine.contract import (
    MAX_CHANGE_PATHS,
    CatalogProjection,
    CatalogQuery,
    CatalogRecord,
    ChangeBatch,
    ChangeCursor,
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
    FilteredTreeProjection,
    FilteredTreeQuery,
    Freshness,
    IndexProgress,
    IndexState,
    InventoryClosedError,
    InventoryConfig,
    InventoryEntry,
    InventoryIssue,
    IssueCode,
    LifecyclePhase,
    MetadataProjection,
    MetadataQuery,
    NavigationProjection,
    NavigationQuery,
    ObservationKind,
    PriorityRequest,
    ProjectionResult,
    QueryKind,
    ReadQuery,
    ReadRequest,
    ReadResult,
    RecentProjection,
    RecentQuery,
    RefreshObservation,
    RefreshReceipt,
    RefreshRequest,
    RollupProjection,
    RollupQuery,
    SourceKind,
    VersionUnavailableError,
    WorkCounters,
)
from metabrowser.inventory_rollup import (
    RollupOptions,
    RollupRank,
    SubtreeAggregateCache,
    build_rollup,
)
from metabrowser.settings import (
    ROLLUP_FILE_TYPE_FILENAME_LIMIT,
    ROLLUP_FILE_TYPE_REMAINING_LIMIT,
    ROLLUP_MAX_NODES,
)
from metabrowser.walker import (
    DEFAULT_MAX_DEPTH,
    DEFAULT_MAX_FILES,
    DEFAULT_REFRESH_TTL_S,
    WALKER_EMIT_BATCH,
    walk_tree,
)
from metabrowser.walker import (
    build_gitignore_check_for as _build_gitignore_check_for,
)
from metabrowser.walker import (
    depth_of as _depth_of,
)
from metabrowser.watch_backends import WatcherStatus, WatchMode, run_watcher
from metabrowser.wire_models import (
    FileTypeRegistryIdentity,
    NavigationTallies,
    RollupResult,
)

LOG = logging.getLogger(__name__)

# Unit conversion for comparing second-based filter windows with inventory mtimes.
_NANOSECONDS_PER_SECOND = 1_000_000_000
# The first exact v0.7 release comparison found one 928.9 ms tally pass on a
# 123,658-file corpus and a 291.7 ms unrelated-request delay. At that cold-tail
# rate, 2,048 entries are about 15 ms of work. A one-microsecond timer-backed
# pause releases the GIL and prevents the worker from immediately reacquiring
# it, keeping the request loop independent of the interpreter's ordinary
# thread-switch interval.
_NAVIGATION_TALLY_COOPERATIVE_YIELD_BATCH = 2_048
_NAVIGATION_TALLY_COOPERATIVE_YIELD_S = 0.000_001
# The exact installed-build browser comparison in exp-014 measured a 1 ms
# `/api/tree` handler queued for 33-37 ms while the startup walker applied a
# wide directory without suspending. Yield four times inside each 256-entry
# delivery batch so request tasks run independently of directory width.
_WALKER_COOPERATIVE_YIELD_BATCH = 64
_NAVIGATION_TALLY_REFRESH_FLOOR_S = 0.5
_CONTRACT_ID = "inventory-provider-v1"


# Rollup revisions come from one process-wide sequence rather than a
# per-instance counter. The revision is what an /api/rollup ETag is keyed on,
# so it must never repeat for different content within a process: two handles
# must not hand out the same tag for different trees.
_ROLLUP_REVISIONS = itertools.count(1)


IndexStatus = Literal["idle", "scanning", "done", "truncated", "failed"]


@dataclass(frozen=True, slots=True)
class _NavigationTallyBase:
    """The clock-independent half of the navigation tallies, plus sorted mtimes.

    Everything here is a pure function of the index entries, so it can be
    memoized on the index revision with no time term. The mtimes are kept
    sorted and typed rather than as row counts, because that is what lets a
    recency window be answered by a binary search instead of another pass:
    the answer to "how many files are newer than this cutoff" is the length
    minus the insertion point.

    ``array("q")`` rather than a list: at the half-million-entry cap two lists
    of Python ints cost tens of megabytes where two int64 arrays cost about
    eight.
    """

    summary: dict[str, int]
    file_type_registry: FileTypeRegistryIdentity
    extensions: list[list[object]]
    canonical_extensions: list[list[object]]
    type_families: list[list[object]]
    type_presets: list[list[object]]
    tracked_mtimes: array[int]
    ignored_mtimes: array[int]
    oldest_mtime_ns: int
    newest_mtime_ns: int


# ── PythonInventoryHandle ──────────────────────────────────────


class _ChildrenView(Mapping[str, "Sequence[FsEntry]"]):
    """Read-through view of ``PythonInventoryHandle._children_index``.

    A rollup visits only the directories whose aggregates are missing, so
    copying every bucket up front is wasted work. Each lookup instead takes
    the index lock and copies just that directory's children, which keeps the
    walker's writes from resizing a bucket mid-iteration.
    """

    __slots__ = ("_index",)

    def __init__(self, index: PythonInventoryHandle) -> None:
        self._index = index

    def __getitem__(self, parent: str) -> Sequence[FsEntry]:
        with self._index._rollup_cache_lock:
            bucket = self._index._children_index.get(parent)
            if bucket is None:
                raise KeyError(parent)
            return tuple(bucket.values())

    def get(  # type: ignore[override]
        self,
        parent: str,
        default: Sequence[FsEntry] = (),
    ) -> Sequence[FsEntry]:
        with self._index._rollup_cache_lock:
            bucket = self._index._children_index.get(parent)
            return tuple(bucket.values()) if bucket is not None else default

    def __iter__(self) -> Iterator[str]:
        with self._index._rollup_cache_lock:
            return iter(tuple(self._index._children_index))

    def __len__(self) -> int:
        return len(self._index._children_index)


def _with_recency(
    base: _NavigationTallyBase,
    recency_windows: Sequence[tuple[str, float]],
    current_ns: int,
) -> NavigationTallies:
    """Add the clock-dependent rows to a memoized base.

    Each window is one binary search per population rather than a pass over
    the index: the mtimes are sorted ascending, so everything at or after the
    cutoff's insertion point is inside the window.

    The row lists from *base* are shared rather than copied. Every consumer
    treats them as read-only -- they are serialized straight to JSON -- and
    copying them per request would reintroduce a cost proportional to the
    index, which is the thing being removed.
    """

    rows: list[list[object]] = []
    for window_key, seconds in recency_windows:
        cutoff_ns = current_ns - int(seconds * _NANOSECONDS_PER_SECOND)
        tracked = len(base.tracked_mtimes) - bisect_left(base.tracked_mtimes, cutoff_ns)
        ignored = len(base.ignored_mtimes) - bisect_left(base.ignored_mtimes, cutoff_ns)
        rows.append([window_key, tracked, ignored])
    return {
        "summary": base.summary,
        "file_type_registry": base.file_type_registry,
        "extensions": base.extensions,
        "canonical_extensions": base.canonical_extensions,
        "type_families": base.type_families,
        "type_presets": base.type_presets,
        "recency_tallies": rows,
        "oldest_mtime_ns": base.oldest_mtime_ns,
        "newest_mtime_ns": base.newest_mtime_ns,
    }


# The navigation tally memo's key: the index revision it was computed at, the
# row cap, and the caller's preset shape. Only the last two identify *what* was
# computed -- the revision says when, and the staleness bound reads it from the
# clock instead, because during a walk the revision moves on every write.
_NavigationTallyKey = tuple[int, int, tuple[tuple[str, tuple[str, ...]], ...]]
_NavigationReadShape = tuple[
    str,
    str,
    str,
    int,
    tuple[tuple[str, tuple[str, ...]], ...],
    tuple[tuple[str, float], ...],
]


@dataclass(frozen=True, slots=True)
class _NavigationReadMemo:
    """One coherent root-summary read retained across moving revisions."""

    shape: _NavigationReadShape
    version: EngineVersion
    cursor: ChangeCursor
    state: IndexState
    projections: tuple[ProjectionResult, ...]
    base: _NavigationTallyBase
    computed_at: float
    compute_cost_s: float


@dataclass(frozen=True, slots=True)
class _ReadImage:
    """One immutable entry and state image captured under the writer lock."""

    entries: tuple[FsEntry, ...]
    total_entries: int
    entries_visited: int
    directories_visited: int
    version: EngineVersion
    cursor: ChangeCursor
    state: IndexState
    diagnostics: dict[str, int | float | str | bool | None]
    rollup_aggregates: SubtreeAggregateCache
    rollup_epoch: int
    rollup_passes: int


def _scope_fingerprint(config: InventoryConfig) -> str:
    semantic = (
        config.max_entries,
        config.max_depth,
        config.hidden_allowlist,
        config.follow_symlinks,
        config.stay_on_filesystem,
    )
    return hashlib.sha256(repr(semantic).encode()).hexdigest()[:24]


def _semantic_entry(entry: FsEntry) -> InventoryEntry:
    """Drop Python-engine bookkeeping and host decorations at the boundary."""

    return InventoryEntry(
        path=entry.path,
        parent=entry.parent,
        name=entry.name,
        type=EntryType(entry.type),
        ext=entry.ext,
        size=entry.size,
        mtime_ns=entry.mtime_ns,
        gitignored=entry.gitignored,
        total_files=entry.total_files,
        total_size=entry.total_size,
        unignored_files=entry.unignored_files,
        unignored_size=entry.unignored_size,
        newest_mtime_ns=entry.newest_mtime_ns,
        empty=entry.empty,
    )


def _internal_entry(entry: InventoryEntry | FsEntry) -> FsEntry:
    """Adapt a semantic walker observation to the transitional retained record."""

    if isinstance(entry, FsEntry):
        return entry
    if entry.type is EntryType.OTHER:
        raise ValueError("the Python walker cannot retain special objects yet")
    entry_type = entry.type.value
    return FsEntry(
        path=entry.path,
        parent=entry.parent,
        name=entry.name,
        type=entry_type,
        ext=entry.ext,
        kind=entry_type if entry_type != "file" else "file",
        size=entry.size,
        mtime_ns=entry.mtime_ns,
        mtime_hash="",
        active=False,
        total_files=entry.total_files,
        total_size=entry.total_size,
        unignored_files=entry.unignored_files,
        unignored_size=entry.unignored_size,
        newest_mtime_ns=entry.newest_mtime_ns,
        empty=entry.empty,
        gitignored=entry.gitignored,
    )


def _children_for(entries: Sequence[FsEntry]) -> dict[str, tuple[FsEntry, ...]]:
    mutable: dict[str, list[FsEntry]] = {}
    for entry in entries:
        if entry.path == entry.parent:
            continue
        mutable.setdefault(entry.parent, []).append(entry)
    return {
        parent: tuple(sorted(rows, key=lambda row: (row.type != "dir", row.name)))
        for parent, rows in mutable.items()
    }


def _directory_rows(
    children: Mapping[str, Sequence[FsEntry]],
    *,
    path: str,
    max_depth: int,
    include_ignored: bool,
) -> list[FsEntry]:
    rows: list[FsEntry] = []
    frontier = [path]
    for _depth in range(max_depth):
        next_frontier: list[str] = []
        for parent in frontier:
            for entry in children.get(parent, ()):
                if not include_ignored and entry.gitignored:
                    continue
                rows.append(entry)
                if entry.type == "dir":
                    next_frontier.append(entry.path)
        frontier = next_frontier
        if not frontier:
            break
    return rows


def _page_offset(after: str | None, total: int) -> int:
    if after is None:
        return 0
    try:
        offset = int(after)
    except ValueError as error:
        raise ValueError("page cursor must be a nonnegative integer") from error
    if offset < 0 or offset > total:
        raise ValueError("page cursor lies outside the result")
    return offset


def _catalog_entry_matches(entry: FsEntry, query: CatalogQuery) -> bool:
    """Apply catalog predicates before records cross the provider boundary."""

    if entry.type != "file" or (entry.gitignored and not query.include_ignored):
        return False
    if query.size_less_than is not None and entry.size >= query.size_less_than:
        return False
    if query.terminal_extensions:
        terminal = PurePosixPath(entry.name).suffix.lower()
        if terminal not in query.terminal_extensions:
            return False
    if query.ancestor_names:
        parts = PurePosixPath(entry.path).parts[:-1]
        if not any(name in parts for name in query.ancestor_names):
            return False
    return True


class PythonInventoryHandle:
    """Retained Python implementation for one opened filesystem root.

    Every consumer reads from this object. The walker writes into
    it. Per-path generation counters serialize concurrent
    invalidations against in-flight walker writes.

    This is the provider's only retained filesystem state. Walker and watcher
    observations pass through it so reads and change cursors share one ordered
    view of each path.
    """

    def __init__(
        self,
        *,
        max_files: int = DEFAULT_MAX_FILES,
        max_depth: int = DEFAULT_MAX_DEPTH,
        config: InventoryConfig | None = None,
    ) -> None:
        if config is None:
            config = InventoryConfig(max_entries=max_files, max_depth=max_depth)
        else:
            max_files = config.max_entries
            max_depth = config.max_depth
        self._config = config
        self._session = uuid.uuid4().hex
        self._scope_fingerprint = _scope_fingerprint(config)
        self._closed = False
        self._last_error: str | None = None
        self._root: Path | None = None
        self._entries: dict[str, FsEntry] = {}
        self._rollup_cache_lock = threading.Lock()
        self._work_lock = threading.Lock()
        self._work_totals = WorkCounters()
        self._read_requests = 0
        # Navigation tallies are one full pass over every file entry: 486ms at
        # 100k on the reference machine, and the root nav request is the first
        # one the browser makes. The pass is a pure function of the entries and
        # the clock, so it is memoized on the index revision rather than
        # recomputed per request.
        #
        # A dedicated lock, held across the computation. Not
        # ``_rollup_cache_lock``: the walker takes that on every write, and
        # holding it for half a second would stall the crawl. Held across the
        # pass rather than around the dict operations because that is what makes
        # simultaneous askers share one pass -- under the GIL, running the same
        # aggregation N times in parallel costs N times as much as running it
        # once, so serializing identical work loses nothing and saves N-1 of it.
        self._navigation_tally_lock = threading.Lock()
        # When the memoized tallies were computed, monotonic. During a walk the
        # revision they key on advances on every write, so revision equality can
        # never hold and age is the only usable freshness test.
        self._navigation_tally_at: float = 0.0
        # How long the last tally pass took, seconds. The staleness bound is
        # derived from this rather than fixed: the pass costs one visit per
        # entry, so what is affordable to repeat scales with the tree, and a
        # constant that is right at 10,000 files is wrong at a million.
        self._navigation_tally_cost_s: float = 0.0
        # One entry. A superseded revision can never be requested again, so
        # there is nothing to evict and nothing to bound.
        self._navigation_tally_memo: tuple[_NavigationTallyKey, _NavigationTallyBase] | None = None
        # The root-summary route bundles its root lookup with the navigation
        # projection. Retain that complete observation boundary so a cache hit can
        # return the older version honestly instead of pairing stale tallies with the
        # provider's current version and state.
        self._navigation_read_memo: _NavigationReadMemo | None = None
        self._rollup_generation = next(_ROLLUP_REVISIONS)
        # Per-directory subtree aggregates, retained across rollup requests.
        # Without this, every ``/api/rollup`` re-walked every file under the
        # requested path: measured at 580-720ms for a 100k-file root, and the
        # cost grows with the index, so a scanning root got slower with each
        # refresh until the client could never catch up. Writes evict the
        # changed path's ancestor chain (see ``_evict_subtree_aggregates``),
        # so a rollup during a scan recomputes only what actually moved.
        self._subtree_aggregates: SubtreeAggregateCache = {}
        # Monotonic eviction counter and the epoch each path was last evicted
        # at. Together they let a rollup pass that ran concurrently with the
        # walker publish only the aggregates the walker has not invalidated.
        self._aggregate_epoch = 0
        self._aggregate_evicted_at: dict[str, int] = {}
        # Rollup passes between _rollup_view and their merge. The eviction
        # epochs above are only consulted by a merge, so at zero they can go.
        self._rollup_passes_in_flight = 0
        # Parent path -> {child path: entry}, maintained on every write. The
        # rollup used to rebuild this grouping from a full copy of the index on
        # each request, which cost ~155ms at 100k entries and grew with the
        # index; keeping it incrementally lets a request read the few buckets
        # it actually visits instead.
        self._children_index: dict[str, dict[str, FsEntry]] = {}
        self._direct_child_counts: dict[str, int] = {}
        self._child_mtime_heaps: dict[str, list[tuple[int, str]]] = {}
        self._recorded_child_mtimes: dict[str, tuple[str, int]] = {}
        self._pending_dirs: set[str] = set()
        self._descendant_file_counts: dict[str, int] = {}
        self._descendant_file_sizes: dict[str, int] = {}
        self._descendant_unignored_file_counts: dict[str, int] = {}
        self._descendant_unignored_file_sizes: dict[str, int] = {}
        self._descendant_leaf_counts: dict[str, int] = {}
        self._walker_dir_generations: dict[str, int] = {}
        self._generation: dict[str, int] = {}
        self._change_history: deque[ChangeBatch] = deque()
        self._replay_floor_sequence = self._rollup_generation
        self._change_subscribers: set[asyncio.Queue[ChangeBatch | None]] = set()
        self._walker_task: asyncio.Task[None] | None = None
        self._watcher_task: asyncio.Task[None] | None = None
        self._watcher_mode = "off"
        self._watcher_state = "off"
        self._watcher_reason = "disabled"
        self._watcher_detail = ""
        self._priority_tasks: set[asyncio.Task[None]] = set()
        self._priority_paths: set[str] = set()
        self._done_event: asyncio.Event = asyncio.Event()
        self._status: IndexStatus = "idle"
        self._max_files = max_files
        self._max_depth = max_depth
        self._files_indexed = 0
        self._directories_indexed = 0
        self._started_at_ns: int = 0
        # Monotonic per handle, bumped on every catalog-relevant mutation and
        # on ``clear()``.
        self._catalog_revision = 0

    # ── Lifecycle ───────────────────────────────────────────

    def start(self, root: Path) -> asyncio.Task[None]:
        """Spawn the walker if not already running. Idempotent —
        a second call returns the existing task without spawning a
        new walker. The boot lifespan hook is the only caller in
        production; tests call this directly."""

        if self._walker_task is not None and not self._walker_task.done():
            return self._walker_task
        self._root = root
        with self._rollup_cache_lock:
            self._status = "scanning"
            self._rollup_generation = next(_ROLLUP_REVISIONS)
        self._done_event.clear()
        self._files_indexed = 0
        self._directories_indexed = 0
        self._started_at_ns = time.monotonic_ns()
        self._walker_task = asyncio.create_task(
            self._run_walker(root), name="metabrowser-inventory-walker"
        )
        return self._walker_task

    def start_watcher(self, root: Path) -> asyncio.Task[None] | None:
        """Start the provider-owned observation task once for this root."""

        if self._config.watch_mode == "off":
            return None
        if self._watcher_task is not None and not self._watcher_task.done():
            return self._watcher_task
        self._root = root
        mode: WatchMode | None = None
        if self._config.watch_mode == "native":
            mode = "native"
        elif self._config.watch_mode == "poll":
            mode = "polling"
        self._watcher_mode = mode or "auto"
        self._watcher_state = "starting"
        self._watcher_reason = "selecting"
        self._watcher_task = asyncio.create_task(
            run_watcher(
                root=root,
                refresh=self.refresh,
                on_status=self._observe_watcher_status,
                mode=mode,
            ),
            name="metabrowser-python-inventory-watcher",
        )
        return self._watcher_task

    def _observe_watcher_status(self, status: WatcherStatus) -> None:
        if (
            status.mode == self._watcher_mode
            and status.state == self._watcher_state
            and status.reason == self._watcher_reason
            and status.detail == self._watcher_detail
        ):
            return
        self._watcher_mode = status.mode
        self._watcher_state = status.state
        self._watcher_reason = status.reason
        self._watcher_detail = status.detail
        with self._rollup_cache_lock:
            self._rollup_generation = next(_ROLLUP_REVISIONS)
        self._record_provider_change(
            dirty_queries=frozenset({QueryKind.METADATA, QueryKind.DIAGNOSTICS})
        )

    def clear(self) -> None:
        """Drop all state and stop the walker. Called by
        ``paths_safe.register_root_callback`` on root swap; a
        subsequent ``start()`` against the new root rebuilds.

        Records a reset batch so coordinator consumers know to take a fresh
        snapshot.
        """

        if self._walker_task is not None and not self._walker_task.done():
            self._walker_task.cancel()
        self._walker_task = None
        if self._watcher_task is not None and not self._watcher_task.done():
            self._watcher_task.cancel()
        self._watcher_task = None
        with self._rollup_cache_lock:
            self._entries.clear()
            self._files_indexed = 0
            self._directories_indexed = 0
            self._status = "idle"
            self._rollup_generation = next(_ROLLUP_REVISIONS)
            self._children_index.clear()
            self._subtree_aggregates.clear()
            self._aggregate_evicted_at.clear()
            self._aggregate_epoch += 1
        self._direct_child_counts.clear()
        self._child_mtime_heaps.clear()
        self._recorded_child_mtimes.clear()
        self._pending_dirs.clear()
        self._descendant_file_counts.clear()
        self._descendant_file_sizes.clear()
        self._descendant_unignored_file_counts.clear()
        self._descendant_unignored_file_sizes.clear()
        self._descendant_leaf_counts.clear()
        self._walker_dir_generations.clear()
        self._generation.clear()
        self._done_event.clear()
        self._catalog_revision += 1
        with self._navigation_tally_lock:
            self._navigation_tally_at = 0.0
            self._navigation_tally_cost_s = 0.0
            self._navigation_tally_memo = None
            self._navigation_read_memo = None
        self._emit(FsResyncRequired(reason="root_swap"))

    async def wait_until_done(self, timeout: float | None = None) -> None:
        """Resolve when the walker completes (or hits truncation or
        failure). For tests; production code reads ``status()``
        instead. Raises ``asyncio.TimeoutError`` on timeout.
        Returning normally does NOT imply success — callers that need
        to distinguish must check ``status()`` for ``"failed"``."""

        if self._status in ("done", "truncated", "failed"):
            return
        await asyncio.wait_for(self._done_event.wait(), timeout)

    async def read(self, request: ReadRequest) -> ReadResult:
        """Answer a bundled request from one immutable entry image."""

        self._ensure_open()
        return await asyncio.to_thread(self._read_sync, request)

    def changes(self, *, after: ChangeCursor | None) -> AsyncGenerator[ChangeBatch, None]:
        """Yield resumable provider invalidations after *after*."""

        return self._changes(after=after)

    async def _changes(self, *, after: ChangeCursor | None) -> AsyncGenerator[ChangeBatch, None]:
        self._ensure_open()
        queue: asyncio.Queue[ChangeBatch | None] = asyncio.Queue(
            maxsize=self._config.change_queue_size
        )

        if after is not None and (
            after.session != self._session
            or after.sequence > self._rollup_generation
            or after.sequence < self._replay_floor_sequence
        ):
            replay = (self._reset_batch(),)
        else:
            history = tuple(self._change_history)
            sequence = after.sequence if after is not None else self._rollup_generation
            replay = tuple(batch for batch in history if batch.cursor.sequence > sequence)

        self._change_subscribers.add(queue)
        try:
            for batch in replay:
                yield batch
            while True:
                batch = await queue.get()
                if batch is None:
                    return
                yield batch
        finally:
            self._change_subscribers.discard(queue)

    async def refresh(self, request: RefreshRequest) -> RefreshReceipt:
        """Verify bounded path hints and feed observations through the delta path."""

        self._ensure_open()
        accepted: list[str] = []
        rejected: list[str] = []
        valid: list[RefreshObservation] = []
        for observation in request.observations:
            if self._valid_relative_path(observation.path):
                valid.append(observation)
            else:
                rejected.append(observation.path)
        if not valid:
            return RefreshReceipt(accepted_paths=(), rejected_paths=tuple(rejected))
        root = self._root
        if root is None:
            raise InventoryClosedError("the Python inventory handle has no open root")
        gitignore_check = await run_cancellable_thread(
            lambda cancel_event: _build_gitignore_check_for(
                root,
                cancel_event=cancel_event,
            )
        )
        for observation in valid:
            rel = observation.path
            await self._refresh_path(observation, gitignore_check=gitignore_check)
            accepted.append(rel)
        return RefreshReceipt(
            accepted_paths=tuple(accepted),
            rejected_paths=tuple(rejected),
        )

    async def prioritize(self, request: PriorityRequest) -> None:
        """Schedule bounded verification without delaying the interactive read path."""

        self._ensure_open()
        paths = tuple(
            rel
            for rel in request.paths
            if self._valid_relative_path(rel)
            and self.get(rel) is None
            and rel not in self._priority_paths
        )
        if not paths:
            return
        self._priority_paths.update(paths)
        task = asyncio.create_task(
            self._run_priority_refresh(paths, max_depth=request.max_depth),
            name="metabrowser-python-inventory-priority",
        )
        self._priority_tasks.add(task)
        task.add_done_callback(self._priority_finished)

    async def _run_priority_refresh(
        self,
        paths: tuple[str, ...],
        *,
        max_depth: int,
    ) -> None:
        try:
            root = self._root
            if root is None:
                return
            gitignore_check = await run_cancellable_thread(
                lambda cancel_event: _build_gitignore_check_for(
                    root,
                    cancel_event=cancel_event,
                )
            )
            for rel in paths:
                if self.get(rel) is None:
                    await self._refresh_path(
                        RefreshObservation(path=rel),
                        gitignore_check=gitignore_check,
                        max_depth=max_depth,
                    )
        finally:
            self._priority_paths.difference_update(paths)

    def _priority_finished(self, task: asyncio.Task[None]) -> None:
        self._priority_tasks.discard(task)
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            LOG.error("inventory priority refresh failed: %s", error)

    async def close(self) -> None:
        """Cancel and join discovery, then wake every change consumer."""

        if self._closed:
            return
        self._closed = True
        watcher_task = self._watcher_task
        if watcher_task is not None and not watcher_task.done():
            watcher_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await watcher_task
        self._watcher_task = None
        task = self._walker_task
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._walker_task = None
        priority_tasks = tuple(self._priority_tasks)
        for priority_task in priority_tasks:
            priority_task.cancel()
        if priority_tasks:
            await asyncio.gather(*priority_tasks, return_exceptions=True)
        self._priority_tasks.clear()
        self._priority_paths.clear()
        self._status = "idle"
        for queue in tuple(self._change_subscribers):
            while not queue.empty():
                queue.get_nowait()
            queue.put_nowait(None)

    def _ensure_open(self) -> None:
        if self._closed:
            raise InventoryClosedError("the Python inventory handle is closed")

    def _version(self, sequence: int) -> EngineVersion:
        return EngineVersion(
            session=self._session,
            sequence=sequence,
            scope_fingerprint=self._scope_fingerprint,
            registry_fingerprint=self._config.registry_fingerprint,
        )

    def _state_for(
        self,
        status: IndexStatus,
        *,
        entries_observed: int,
        files_indexed: int,
        directory_count: int,
    ) -> IndexState:
        issues: tuple[InventoryIssue, ...] = ()
        if status == "scanning":
            phase = LifecyclePhase.DISCOVERING
            coverage = Coverage(complete=False, reason=CoverageReason.BUILDING)
            freshness = Freshness.PARTIAL
        elif status == "done":
            phase = LifecyclePhase.WATCHING
            coverage = Coverage(complete=True)
            freshness = Freshness.FRESH
        elif status == "truncated":
            phase = LifecyclePhase.WATCHING
            coverage = Coverage(complete=False, reason=CoverageReason.BUDGET)
            freshness = Freshness.PARTIAL
            issues = (
                InventoryIssue(
                    code=IssueCode.RESOURCE_BUDGET,
                    detail="the retained-entry budget stopped discovery",
                ),
            )
        elif status == "failed":
            phase = LifecyclePhase.FAILED
            coverage = Coverage(complete=False, reason=CoverageReason.FAILED)
            freshness = Freshness.PARTIAL
            issues = (
                InventoryIssue(
                    code=IssueCode.PROVIDER_FAILURE,
                    detail=self._last_error or "the Python walker failed",
                ),
            )
        else:
            phase = LifecyclePhase.STOPPED
            coverage = Coverage(complete=False, reason=CoverageReason.CANCELLED)
            freshness = Freshness.STALE
        if self._watcher_state == "failed":
            if coverage.complete:
                coverage = Coverage(complete=False, reason=CoverageReason.WATCHER_GAP)
            freshness = Freshness.STALE
            issues += (
                InventoryIssue(
                    code=IssueCode.WATCHER_GAP,
                    detail=self._watcher_detail or "filesystem observation stopped",
                    transient=True,
                ),
            )
        return IndexState(
            phase=phase,
            coverage=coverage,
            freshness=freshness,
            source=SourceKind.SCANNED,
            progress=IndexProgress(
                entries_observed=entries_observed,
                directories_observed=directory_count,
            ),
            issues=issues,
        )

    def _capture_image(self, request: ReadRequest) -> _ReadImage:
        with self._work_lock:
            work_totals = self._work_totals
            read_requests = self._read_requests
        with self._rollup_cache_lock:
            sequence = self._rollup_generation
            version = self._version(sequence)
            if request.at_version is not None and request.at_version != version:
                raise VersionUnavailableError(
                    "the requested Python inventory version is no longer retained"
                )
            total_entries = len(self._entries)
            targeted = all(
                isinstance(
                    query,
                    (
                        EntryQuery,
                        DirectoryQuery,
                        CatalogQuery,
                        MetadataQuery,
                        DiagnosticsQuery,
                    ),
                )
                for query in request.queries
            )
            if targeted and any(isinstance(query, CatalogQuery) for query in request.queries):
                # Catalog predicates require a whole-index visit. Copy the immutable
                # image under the writer lock and perform filtering, sorting, and page
                # construction after releasing it. Filtering into a second dict here
                # held discovery writes for the duration of the full pass and then the
                # projection repeated the same predicates outside the lock.
                entries = tuple(self._entries.values())
                entries_visited = len(entries)
                directories_visited = sum(entry.type == "dir" for entry in entries)
            elif targeted:
                selected: dict[str, FsEntry] = {}
                entries_visited = 0
                directories_visited = 0
                for query in request.queries:
                    if isinstance(query, EntryQuery):
                        entries_visited += 1
                        entry = self._entries.get(query.path)
                        if entry is not None:
                            selected[entry.path] = entry
                            directories_visited += int(entry.type == "dir")
                    elif isinstance(query, DirectoryQuery):
                        frontier = [query.path]
                        for _depth in range(query.max_depth):
                            next_frontier: list[str] = []
                            for parent in frontier:
                                directories_visited += 1
                                bucket = self._children_index.get(parent, {})
                                for entry in bucket.values():
                                    entries_visited += 1
                                    if not query.include_ignored and entry.gitignored:
                                        continue
                                    selected[entry.path] = entry
                                    if entry.type == "dir":
                                        next_frontier.append(entry.path)
                            frontier = next_frontier
                            if not frontier:
                                break
                entries = tuple(selected.values())
            else:
                entries = tuple(self._entries.values())
                entries_visited = len(entries)
                directories_visited = sum(entry.type == "dir" for entry in entries)
            status = self._status
            files_indexed = self._files_indexed
            directory_count = self._directories_indexed
            pending_directories = len(self._pending_dirs)
            catalog_revision = self._catalog_revision
            rollup_passes = sum(isinstance(query, RollupQuery) for query in request.queries)
            rollup_aggregates = dict(self._subtree_aggregates) if rollup_passes else {}
            rollup_epoch = self._aggregate_epoch
            self._rollup_passes_in_flight += rollup_passes
        root = self._root
        state = self._state_for(
            status,
            entries_observed=total_entries,
            files_indexed=files_indexed,
            directory_count=directory_count,
        )
        elapsed_ms = (
            (time.monotonic_ns() - self._started_at_ns) // 1_000_000 if self._started_at_ns else 0
        )
        return _ReadImage(
            entries=entries,
            total_entries=total_entries,
            entries_visited=entries_visited,
            directories_visited=directories_visited,
            version=version,
            cursor=ChangeCursor(session=self._session, sequence=sequence),
            state=state,
            diagnostics={
                "provider": "python",
                "contract": _CONTRACT_ID,
                "root": str(root) if root is not None else "",
                "status": status,
                "elapsed_ms": elapsed_ms,
                "files_indexed": files_indexed,
                "directories_indexed": max(0, directory_count - 1),
                "entries": total_entries,
                "pending_dirs": pending_directories,
                "watch_mode": self._watcher_mode,
                "watch_state": self._watcher_state,
                "watch_reason": self._watcher_reason,
                "watch_detail": self._watcher_detail,
                "catalog_revision": catalog_revision,
                "version": sequence,
                "read_requests": read_requests,
                "work_entries_visited": work_totals.entries_visited,
                "work_directories_visited": work_totals.directories_visited,
                "work_rows_returned": work_totals.rows_returned,
                "work_bytes_copied": work_totals.bytes_copied,
                "work_lock_wait_ns": work_totals.lock_wait_ns,
                "work_cpu_time_ns": work_totals.cpu_time_ns,
                "work_wall_time_ns": work_totals.wall_time_ns,
            },
            rollup_aggregates=rollup_aggregates,
            rollup_epoch=rollup_epoch,
            rollup_passes=rollup_passes,
        )

    def _read_sync(self, request: ReadRequest) -> ReadResult:
        navigation_shape = self._navigation_read_shape(request)
        if navigation_shape is not None:
            return self._read_navigation_sync(request, navigation_shape)
        if any(isinstance(query, RollupQuery) for query in request.queries) and all(
            isinstance(query, (RollupQuery, DiagnosticsQuery)) for query in request.queries
        ):
            return self._read_rollup_sync(request)

        return self._read_snapshot_sync(request)

    def _read_snapshot_sync(self, request: ReadRequest) -> ReadResult:
        """Answer from one immutable image when a query needs broad traversal."""

        wall_started = time.monotonic_ns()
        cpu_started = time.thread_time_ns()
        image = self._capture_image(request)
        needs_entry_graph = any(
            isinstance(
                query,
                (
                    EntryQuery,
                    DirectoryQuery,
                    FilteredTreeQuery,
                    RollupQuery,
                    RecentQuery,
                ),
            )
            for query in request.queries
        )
        entries_by_path = (
            {entry.path: entry for entry in image.entries} if needs_entry_graph else {}
        )
        children = _children_for(image.entries) if needs_entry_graph else {}
        projections: list[ProjectionResult] = []
        rows_returned = 0
        remaining_rollup_passes = image.rollup_passes

        try:
            for query in request.queries:
                if isinstance(query, RollupQuery):
                    remaining_rollup_passes -= 1
                projection = self._project_query(
                    query,
                    image=image,
                    entries_by_path=entries_by_path,
                    children=children,
                )
                projections.append(projection)
                rows_returned += self._projection_rows(projection)
        finally:
            for _unused in range(remaining_rollup_passes):
                self._merge_subtree_aggregates({}, image.rollup_epoch)

        work = WorkCounters(
            entries_visited=image.entries_visited,
            directories_visited=image.directories_visited,
            rows_returned=rows_returned,
            cpu_time_ns=time.thread_time_ns() - cpu_started,
            wall_time_ns=time.monotonic_ns() - wall_started,
        )
        self._record_read_work(work)
        return ReadResult(
            version=image.version,
            cursor=image.cursor,
            state=image.state,
            projections=tuple(projections),
            work=work,
        )

    @staticmethod
    def _navigation_read_shape(request: ReadRequest) -> _NavigationReadShape | None:
        """The one bounded bundle polled while the root inventory is moving."""

        if len(request.queries) != 2:
            return None
        entry, navigation = request.queries
        if (
            not isinstance(entry, EntryQuery)
            or entry.path
            or not isinstance(navigation, NavigationQuery)
        ):
            return None
        return (
            entry.query_id,
            entry.path,
            navigation.query_id,
            navigation.max_rows,
            navigation.presets,
            navigation.recency_windows,
        )

    def _read_navigation_sync(
        self,
        request: ReadRequest,
        shape: _NavigationReadShape,
    ) -> ReadResult:
        """Reuse one coherent root-summary boundary before copying the index."""

        lock_started = time.monotonic_ns()
        with self._rollup_cache_lock:
            lock_wait_ns = time.monotonic_ns() - lock_started
            current_sequence = self._rollup_generation
            current_status = self._status
        now = time.monotonic()
        with self._navigation_tally_lock:
            memo = self._navigation_read_memo
            if memo is not None and memo.shape == shape:
                if request.at_version is not None:
                    reusable = request.at_version == memo.version
                elif memo.version.sequence == current_sequence:
                    reusable = True
                elif current_status == "scanning":
                    refresh_after = max(
                        _NAVIGATION_TALLY_REFRESH_FLOOR_S,
                        memo.compute_cost_s,
                    )
                    reusable = now - memo.computed_at <= refresh_after
                else:
                    # A finalized walk or a live mutation needs one exact refresh.
                    # Otherwise a single debounced browser request could consume a
                    # completed-but-stale summary and have no later event that asks
                    # again. The cost-aware concession exists only while discovery is
                    # already labelling every tally provisional.
                    reusable = False
            else:
                reusable = False

        if reusable and memo is not None:
            wall_started = time.monotonic_ns()
            cpu_started = time.thread_time_ns()
            navigation = request.queries[1]
            if not isinstance(navigation, NavigationQuery):  # pragma: no cover - shape proves it
                raise TypeError("the navigation cache received the wrong query shape")
            current_ns = time.time_ns() if navigation.as_of_ns is None else navigation.as_of_ns
            projections = tuple(
                NavigationProjection(
                    query_id=projection.query_id,
                    payload=_with_recency(
                        memo.base,
                        navigation.recency_windows,
                        current_ns,
                    ),
                )
                if isinstance(projection, NavigationProjection)
                else projection
                for projection in memo.projections
            )
            work = WorkCounters(
                rows_returned=sum(self._projection_rows(projection) for projection in projections),
                lock_wait_ns=lock_wait_ns,
                cpu_time_ns=time.thread_time_ns() - cpu_started,
                wall_time_ns=time.monotonic_ns() - wall_started,
            )
            self._record_read_work(work)
            return ReadResult(
                version=memo.version,
                cursor=memo.cursor,
                state=memo.state,
                projections=projections,
                work=work,
            )

        result = self._read_snapshot_sync(request)
        navigation = request.queries[1]
        if not isinstance(navigation, NavigationQuery):  # pragma: no cover - shape proves it
            raise TypeError("the navigation cache received the wrong query shape")
        expected_key: _NavigationTallyKey = (
            result.version.sequence,
            navigation.max_rows,
            tuple((preset_id, tuple(sorted(values))) for preset_id, values in navigation.presets),
        )
        with self._navigation_tally_lock:
            tally_memo = self._navigation_tally_memo
            existing = self._navigation_read_memo
            if (
                tally_memo is not None
                and tally_memo[0] == expected_key
                and (existing is None or existing.version.sequence <= result.version.sequence)
            ):
                self._navigation_read_memo = _NavigationReadMemo(
                    shape=shape,
                    version=result.version,
                    cursor=result.cursor,
                    state=result.state,
                    projections=result.projections,
                    base=tally_memo[1],
                    computed_at=self._navigation_tally_at,
                    compute_cost_s=self._navigation_tally_cost_s,
                )
        return result

    def _read_rollup_sync(self, request: ReadRequest) -> ReadResult:
        """Answer rollup bundles atomically without copying the whole index.

        The retained entry and child maps already have the lookup shape the
        reducer needs. A stable generation proves the optimistic reduction and
        its metadata came from one version. If discovery races the reduction,
        a pinned read reports that its version moved; an unpinned read falls
        back to the immutable-image path. The provider therefore avoids an
        O(index) copy for settled reads without holding the writer lock while
        it reduces a large tree.
        """

        wall_started = time.monotonic_ns()
        cpu_started = time.thread_time_ns()
        lock_started = time.monotonic_ns()
        with self._work_lock:
            work_totals = self._work_totals
            read_requests = self._read_requests
        with self._rollup_cache_lock:
            lock_wait_ns = time.monotonic_ns() - lock_started
            sequence = self._rollup_generation
            version = self._version(sequence)
            if request.at_version is not None and request.at_version != version:
                raise VersionUnavailableError(
                    "the requested Python inventory version is no longer retained"
                )
            total_entries = len(self._entries)
            status = self._status
            files_indexed = self._files_indexed
            directory_count = self._directories_indexed
            state = self._state_for(
                status,
                entries_observed=total_entries,
                files_indexed=files_indexed,
                directory_count=directory_count,
            )
            elapsed_ms = (
                (time.monotonic_ns() - self._started_at_ns) // 1_000_000
                if self._started_at_ns
                else 0
            )
            diagnostics: dict[str, int | float | str | bool | None] = {
                "provider": "python",
                "contract": _CONTRACT_ID,
                "root": str(self._root) if self._root is not None else "",
                "status": status,
                "elapsed_ms": elapsed_ms,
                "files_indexed": files_indexed,
                "directories_indexed": max(0, directory_count - 1),
                "entries": total_entries,
                "pending_dirs": len(self._pending_dirs),
                "watch_mode": self._watcher_mode,
                "watch_state": self._watcher_state,
                "watch_reason": self._watcher_reason,
                "watch_detail": self._watcher_detail,
                "catalog_revision": self._catalog_revision,
                "version": sequence,
                "read_requests": read_requests,
                "work_entries_visited": work_totals.entries_visited,
                "work_directories_visited": work_totals.directories_visited,
                "work_rows_returned": work_totals.rows_returned,
                "work_bytes_copied": work_totals.bytes_copied,
                "work_lock_wait_ns": work_totals.lock_wait_ns,
                "work_cpu_time_ns": work_totals.cpu_time_ns,
                "work_wall_time_ns": work_totals.wall_time_ns,
            }

        projections: list[ProjectionResult] = []
        for query in request.queries:
            if isinstance(query, DiagnosticsQuery):
                projections.append(
                    DiagnosticsProjection(
                        query_id=query.query_id,
                        counters=diagnostics,
                    )
                )
                continue
            if not isinstance(query, RollupQuery):
                raise TypeError("the rollup fast path received an unsupported query")
            payload = self.rollup(
                query.path,
                depth=query.max_depth,
                top=query.top,
                ext_top=query.extension_top,
                remaining_top=query.remaining_top,
                filename_top=query.filename_top,
                ext_rank=query.rank,
                max_nodes=query.max_nodes,
            )
            projections.append(RollupProjection(query_id=query.query_id, payload=payload))

        with self._rollup_cache_lock:
            stable = self._rollup_generation == sequence
        if not stable:
            if request.at_version is not None:
                raise VersionUnavailableError(
                    "the requested Python inventory version moved during the rollup read"
                )
            return self._read_snapshot_sync(request)

        work = WorkCounters(
            entries_visited=total_entries,
            directories_visited=directory_count,
            rows_returned=len(projections),
            lock_wait_ns=lock_wait_ns,
            cpu_time_ns=time.thread_time_ns() - cpu_started,
            wall_time_ns=time.monotonic_ns() - wall_started,
        )
        self._record_read_work(work)
        return ReadResult(
            version=version,
            cursor=ChangeCursor(session=self._session, sequence=sequence),
            state=state,
            projections=tuple(projections),
            work=work,
        )

    def _record_read_work(self, work: WorkCounters) -> None:
        with self._work_lock:
            current = self._work_totals
            self._work_totals = WorkCounters(
                entries_visited=current.entries_visited + work.entries_visited,
                directories_visited=current.directories_visited + work.directories_visited,
                rows_returned=current.rows_returned + work.rows_returned,
                bytes_copied=current.bytes_copied + work.bytes_copied,
                lock_wait_ns=current.lock_wait_ns + work.lock_wait_ns,
                cpu_time_ns=current.cpu_time_ns + work.cpu_time_ns,
                wall_time_ns=current.wall_time_ns + work.wall_time_ns,
            )
            self._read_requests += 1

    def _project_query(
        self,
        query: ReadQuery,
        *,
        image: _ReadImage,
        entries_by_path: Mapping[str, FsEntry],
        children: Mapping[str, Sequence[FsEntry]],
    ) -> ProjectionResult:
        if isinstance(query, EntryQuery):
            entry = entries_by_path.get(query.path)
            if entry is not None:
                return EntryProjection(
                    query_id=query.query_id,
                    presence=EntryPresence.PRESENT,
                    entry=_semantic_entry(entry),
                )
            presence = (
                EntryPresence.ABSENT if image.state.coverage.complete else EntryPresence.UNKNOWN
            )
            return EntryProjection(query_id=query.query_id, presence=presence, entry=None)
        if isinstance(query, DirectoryQuery):
            return self._directory_projection(query, children)
        if isinstance(query, FilteredTreeQuery):
            return self._filtered_tree_projection(query, image.entries, children)
        if isinstance(query, RollupQuery):
            options = RollupOptions(
                depth=query.max_depth,
                top=query.top,
                ext_top=query.extension_top,
                remaining_top=query.remaining_top,
                filename_top=query.filename_top,
                ext_rank=query.rank,
                max_nodes=query.max_nodes,
            )
            computed: SubtreeAggregateCache = {}
            try:
                payload = build_rollup(
                    entries_by_path,
                    children,
                    query.path,
                    options,
                    ancestor_gitignored=self._ancestor_gitignored(query.path, entries_by_path),
                    aggregates=ChainMap(computed, image.rollup_aggregates),
                )
            finally:
                self._merge_subtree_aggregates(computed, image.rollup_epoch)
            return RollupProjection(query_id=query.query_id, payload=payload)
        if isinstance(query, NavigationQuery):
            presets = tuple((name, values) for name, values in query.presets)
            payload = self.navigation_tallies(
                presets,
                query.recency_windows,
                query.max_rows,
                now_ns=query.as_of_ns,
                entries=image.entries,
                revision=image.version.sequence,
            )
            return NavigationProjection(query_id=query.query_id, payload=payload)
        if isinstance(query, RecentQuery):
            return self._recent_projection(query, image.entries, entries_by_path)
        if isinstance(query, CatalogQuery):
            records = sorted(
                (
                    CatalogRecord(
                        path=entry.path,
                        logical_extension=entry.ext,
                        size=entry.size,
                        mtime_ns=entry.mtime_ns,
                    )
                    for entry in image.entries
                    if _catalog_entry_matches(entry, query)
                ),
                key=lambda record: record.path,
            )
            offset = _page_offset(query.after, len(records))
            page = tuple(records[offset : offset + query.max_rows])
            next_offset = offset + len(page)
            return CatalogProjection(
                query_id=query.query_id,
                records=page,
                total_matches=len(records),
                next_page=str(next_offset) if next_offset < len(records) else None,
            )
        if isinstance(query, MetadataQuery):
            root = self._root
            if root is None:
                raise InventoryClosedError("the Python inventory handle has no open root")
            return MetadataProjection(
                query_id=query.query_id,
                provider="python",
                contract=_CONTRACT_ID,
                root=str(root),
            )
        return DiagnosticsProjection(
            query_id=query.query_id,
            counters=image.diagnostics,
        )

    def _directory_projection(
        self,
        query: DirectoryQuery,
        children: Mapping[str, Sequence[FsEntry]],
    ) -> DirectoryProjection:
        rows = _directory_rows(
            children,
            path=query.path,
            max_depth=query.max_depth,
            include_ignored=query.include_ignored,
        )
        offset = _page_offset(query.after, len(rows))
        page = rows[offset : offset + query.max_rows]
        next_offset = offset + len(page)
        return DirectoryProjection(
            query_id=query.query_id,
            entries=tuple(_semantic_entry(entry) for entry in page),
            next_page=str(next_offset) if next_offset < len(rows) else None,
            remaining_rows=len(rows) - next_offset,
        )

    def _filtered_tree_projection(
        self,
        query: FilteredTreeQuery,
        entries: Sequence[FsEntry],
        children: Mapping[str, Sequence[FsEntry]],
    ) -> FilteredTreeProjection:
        ignored_dirs = self._effective_ignored_directories(entries)
        matched: list[FsEntry] = []
        matching_files = 0
        matching_bytes = 0
        directory_totals: dict[str, list[int]] = {}
        prefix = f"{query.path}/" if query.path else ""
        for entry in entries:
            if entry.path == query.path or (prefix and not entry.path.startswith(prefix)):
                continue
            if not query.path and not entry.path:
                continue
            if entry.type == "dir":
                continue
            if not self._filter_matches(entry, query, ignored_dirs):
                continue
            matched.append(entry)
            if entry.type == "file":
                matching_files += 1
                matching_bytes += entry.size
            cursor = entry.parent
            while True:
                bucket = directory_totals.setdefault(cursor, [0, 0, 0])
                if entry.type == "file":
                    bucket[0] += 1
                    bucket[1] += entry.size
                bucket[2] = max(bucket[2], entry.mtime_ns)
                if cursor == query.path or not cursor:
                    break
                cursor = cursor.rpartition("/")[0]

        rows = _directory_rows(
            children,
            path=query.path,
            max_depth=query.max_depth,
            include_ignored=query.filter.include_ignored,
        )
        matched_paths = {entry.path for entry in matched}
        selected: list[InventoryEntry] = []
        for entry in rows:
            if entry.type == "dir":
                totals = directory_totals.get(entry.path)
                if totals is None:
                    continue
                selected.append(
                    replace(
                        _semantic_entry(entry),
                        total_files=totals[0],
                        total_size=totals[1],
                        newest_mtime_ns=totals[2] or None,
                        empty=False,
                    )
                )
            elif entry.path in matched_paths:
                selected.append(_semantic_entry(entry))
        offset = _page_offset(query.after, len(selected))
        page = selected[offset : offset + query.max_rows]
        next_offset = offset + len(page)
        return FilteredTreeProjection(
            query_id=query.query_id,
            entries=tuple(page),
            matching_leaves=len(matched),
            matching_files=matching_files,
            matching_bytes=matching_bytes,
            next_page=str(next_offset) if next_offset < len(selected) else None,
            remaining_rows=len(selected) - next_offset,
        )

    def _filter_matches(
        self,
        entry: FsEntry,
        query: FilteredTreeQuery,
        ignored_dirs: Mapping[str, bool],
    ) -> bool:
        selection = query.filter
        if not selection.include_ignored and (
            entry.gitignored or ignored_dirs.get(entry.parent, False)
        ):
            return False
        if entry.type == "symlink":
            return not (
                selection.extensions
                or selection.filenames
                or selection.type_families
                or selection.recency_seconds
                or selection.minimum_size
            )
        if selection.minimum_size is not None and entry.size < selection.minimum_size:
            return False
        if selection.recency_seconds is not None and selection.as_of_ns is not None:
            cutoff = selection.as_of_ns - int(selection.recency_seconds * _NANOSECONDS_PER_SECOND)
            if entry.mtime_ns < cutoff:
                return False
        if selection.extensions or selection.filenames:
            lowered_ext = entry.ext.lower()
            extension_match = any(
                lowered_ext == extension.lower()
                or (
                    family_for_extension(extension) is not None
                    and lowered_ext.endswith(extension.lower())
                )
                for extension in selection.extensions
            )
            filename_match = entry.name.lower() in {
                filename.lower() for filename in selection.filenames
            }
            if not extension_match and not filename_match:
                return False
        if selection.type_families:
            match = family_for_extension(entry.ext)
            if match is None or match.family.id not in selection.type_families:
                return False
        return True

    @staticmethod
    def _effective_ignored_directories(entries: Sequence[FsEntry]) -> dict[str, bool]:
        resolved: dict[str, bool] = {"": False}
        directories = sorted(
            (entry for entry in entries if entry.type == "dir" and entry.path),
            key=lambda entry: _depth_of(entry.path),
        )
        for entry in directories:
            resolved[entry.path] = entry.gitignored or resolved.get(entry.parent, False)
        return resolved

    def _recent_projection(
        self,
        query: RecentQuery,
        entries: Sequence[FsEntry],
        entries_by_path: Mapping[str, FsEntry],
    ) -> RecentProjection:
        cutoff = (
            query.as_of_ns - int(query.within_seconds * _NANOSECONDS_PER_SECOND)
            if query.within_seconds is not None
            else 0
        )
        matching = [
            entry
            for entry in entries
            if entry.type == "file"
            and entry.mtime_ns >= cutoff
            and (not query.prefix or entry.path.startswith(query.prefix))
            and (not query.extensions or entry.ext in query.extensions)
            and (query.include_ignored or not entry.gitignored)
        ]
        matching.sort(key=lambda entry: entry.mtime_ns, reverse=True)
        total = len(matching)
        if total > query.max_rows:
            capped = [entry for entry in matching if not entry.gitignored][: query.max_rows]
            if len(capped) < query.max_rows:
                capped.extend(entry for entry in matching if entry.gitignored)
                capped = capped[: query.max_rows]
            capped.sort(key=lambda entry: entry.mtime_ns, reverse=True)
        else:
            capped = matching
        ignored_directories: set[str] = set()
        for entry in capped:
            parts = entry.path.split("/")
            for index in range(1, len(parts)):
                ancestor = "/".join(parts[:index])
                candidate = entries_by_path.get(ancestor)
                if candidate is not None and candidate.gitignored:
                    ignored_directories.add(ancestor)
        return RecentProjection(
            query_id=query.query_id,
            entries=tuple(_semantic_entry(entry) for entry in capped),
            total_matches=total,
            truncated=total > len(capped),
            gitignored_directories=tuple(sorted(ignored_directories)),
        )

    @staticmethod
    def _projection_rows(projection: ProjectionResult) -> int:
        if isinstance(projection, (DirectoryProjection, FilteredTreeProjection)):
            return len(projection.entries)
        if isinstance(projection, RecentProjection):
            return len(projection.entries)
        if isinstance(projection, CatalogProjection):
            return len(projection.records)
        if isinstance(projection, EntryProjection):
            return int(projection.entry is not None)
        return 1

    def _valid_relative_path(self, rel: str) -> bool:
        path = PurePosixPath(rel)
        return (
            bool(rel)
            and "\\" not in rel
            and not path.is_absolute()
            and ".." not in path.parts
            and path.as_posix() == rel
        )

    async def _refresh_path(
        self,
        observation: RefreshObservation,
        *,
        gitignore_check: Callable[[Path, bool], bool] | None,
        max_depth: int | None = None,
    ) -> None:
        root = self._root
        if root is None:
            raise InventoryClosedError("the Python inventory handle has no open root")
        rel = observation.path
        target = root / rel
        existing = self.get(rel)
        self.invalidate(rel)
        try:
            stat_result = await asyncio.to_thread(target.lstat)
        except FileNotFoundError:
            self.remove(rel)
            return
        parent = rel.rpartition("/")[0]
        try:
            gitignored = bool(
                gitignore_check(target, stat_module.S_ISDIR(stat_result.st_mode))
                if gitignore_check is not None
                else False
            )
        except Exception:
            gitignored = existing.gitignored if existing is not None else False
        if stat_module.S_ISLNK(stat_result.st_mode):
            entry = FsEntry.for_observed_symlink(
                path=rel,
                parent=parent,
                name=target.name,
                size=stat_result.st_size,
                mtime_ns=stat_result.st_mtime_ns,
                gitignored=gitignored,
            )
            self.apply_live_entry(entry)
        elif stat_module.S_ISDIR(stat_result.st_mode):
            if observation.kind is ObservationKind.DELETED and existing is not None:
                self.remove(rel)
            await self.rewalk_subtree(
                rel,
                gitignore_check=gitignore_check,
                gitignore_prepared=True,
                max_depth=max_depth,
            )
        else:
            self.apply_live_entry(
                FsEntry.for_stat(
                    path=rel,
                    parent=parent,
                    name=target.name,
                    stat=stat_result,
                    gitignored=gitignored,
                    existing=existing,
                )
            )

    def _reset_batch(self) -> ChangeBatch:
        with self._rollup_cache_lock:
            sequence = self._rollup_generation
            entry_count = len(self._entries)
            directory_count = self._directories_indexed
            state = self._state_for(
                self._status,
                entries_observed=entry_count,
                files_indexed=self._files_indexed,
                directory_count=directory_count,
            )
        version = self._version(sequence)
        return ChangeBatch(
            cursor=ChangeCursor(session=self._session, sequence=sequence),
            version=version,
            state=state,
            reset=True,
        )

    # ── Reads ───────────────────────────────────────────────

    def status(self) -> IndexStatus:
        return self._status

    def get(self, path: str) -> FsEntry | None:
        return self._entries.get(path)

    def children_of(self, parent: str) -> tuple[FsEntry, ...]:
        """Direct children of *parent*, or an empty tuple.

        Served from the index maintained on write, so a caller that walks a
        subtree pays for that subtree rather than for the whole index. The
        served root is excluded from its own children.
        """

        with self._rollup_cache_lock:
            bucket = self._children_index.get(parent)
            return tuple(bucket.values()) if bucket is not None else ()

    def has_direct_child(self, path: str) -> bool:
        """Return whether *path* has a child already present in the index."""

        return self._direct_child_counts.get(path, 0) > 0

    def entries(
        self,
        scope: Literal[
            "root-depth-2", "recent-top-N", "expanded-prefixes", "all-known"
        ] = "all-known",
        *,
        max_depth: int | None = None,
    ) -> list[FsEntry]:
        """Snapshot of currently-known entries filtered by scope.

        ``root-depth-2`` returns entries at depth 0–2 (matches the
        default ``/api/tree`` first-paint).
        ``all-known`` returns everything currently in the index.
        ``recent-top-N`` and ``expanded-prefixes`` are accepted wire
        scopes that currently return the same complete snapshot as
        ``all-known``.
        """

        if scope == "all-known":
            base = list(self._entries.values())
        elif scope == "root-depth-2":
            depth_cap = 2 if max_depth is None else max_depth
            base = [e for e in self._entries.values() if _depth_of(e.path) <= depth_cap]
        elif scope in ("recent-top-N", "expanded-prefixes"):
            # These wire scopes currently request the complete snapshot.
            base = list(self._entries.values())
        else:  # pragma: no cover — type-checked at the boundary
            raise ValueError(f"unknown scope: {scope!r}")
        return base

    def files_indexed(self) -> int:
        return self._files_indexed

    def max_files(self) -> int:
        return self._max_files

    def catalog_revision(self) -> int:
        return self._catalog_revision

    def rollup_revision(self) -> int:
        """Counter that advances on every index write.

        A rollup response is a pure function of the index contents and the
        request's bounds, so an unchanged revision means an unchanged body.
        That is what lets ``/api/rollup`` answer a repeat request with a
        validator instead of re-aggregating and re-serializing the same
        answer. Advances constantly during a scan, which is correct: the
        answer really is changing then.
        """

        with self._rollup_cache_lock:
            return self._rollup_generation

    def catalog_files(self) -> list[tuple[str, str]]:
        """``(path, logical_ext)`` for every non-gitignored file in
        the index — the Quick File catalog universe. List-of-tuples
        rather than wire dicts so the route owns serialization and
        can run it off the event loop."""

        return [
            (e.path, e.ext) for e in self._entries.values() if e.type == "file" and not e.gitignored
        ]

    def root_summary(
        self,
        *,
        entries: Sequence[FsEntry] | None = None,
    ) -> dict[str, int]:
        """Whole-index file counts and bytes, split by gitignore status.

        The per-directory ``total_files`` / ``total_size`` aggregates
        are gitignore-blind, and they have to stay that way: a folder's
        size is its size. But the nav header wants to say how much of
        the tree is tracked versus ignored, and summing top-level
        children cannot answer that — ignored files nested under
        tracked directories would be counted as tracked.

        One pass over the entries is the honest way to get it. Navigation
        requests use :meth:`navigation_tallies` to perform the same calculation
        alongside filter counts; this focused method avoids doing that extra work for
        callers that need only the summary.
        """

        snapshot = self.entries(scope="all-known") if entries is None else entries
        files = size = ignored_files = ignored_size = 0
        for entry_index, entry in enumerate(snapshot):
            if entry_index > 0 and entry_index % _NAVIGATION_TALLY_COOPERATIVE_YIELD_BATCH == 0:
                time.sleep(_NAVIGATION_TALLY_COOPERATIVE_YIELD_S)
            if entry.type != "file":
                continue
            if entry.gitignored:
                ignored_files += 1
                ignored_size += entry.size or 0
            else:
                files += 1
                size += entry.size or 0
        return {
            "files": files,
            "size": size,
            "ignored_files": ignored_files,
            "ignored_size": ignored_size,
        }

    def navigation_tallies(
        self,
        presets: Sequence[tuple[str, Collection[str]]],
        recency_windows: Sequence[tuple[str, float]],
        limit: int = 200,
        *,
        now_ns: int | None = None,
        entries: Sequence[FsEntry] | None = None,
        revision: int | None = None,
    ) -> NavigationTallies:
        """
        Return root, file-type, and cumulative recency tallies in one index pass.

        Every row is ``[key, tracked_files, ignored_files]``. Keeping the two
        populations separate lets the browser use the same snapshot when the user
        changes whether gitignored files are shown.

        Pass *revision* -- the value :meth:`rollup_revision` reported when
        *entries* was snapshotted -- to memoize the result. The pass costs one
        visit per file entry, so on a settled index every root request would
        otherwise redo the same half-second of work, once per open tab. Omit it
        for a self-contained tally.
        """

        snapshot = self.entries(scope="all-known") if entries is None else entries
        current_ns = time.time_ns() if now_ns is None else now_ns
        if revision is None:
            base = self._compute_navigation_tallies(presets, limit, snapshot)
            return _with_recency(base, recency_windows, current_ns)
        # Everything the pass depends on, and nothing else. The bounds and the
        # preset definitions are caller-supplied, so they belong in the key
        # even though the server passes module constants: a key that assumed
        # them would hand a future second caller the first one's shape.
        #
        # No clock term, deliberately. An earlier version keyed on a rounded
        # second, which fails exactly where this is needed: at 400,000 entries
        # the pass takes about two seconds, so every request landed in a later
        # bucket than the one before it and the memo never hit. The recency
        # windows are the only clock-dependent part, and they are now answered
        # from sorted mtimes below rather than recomputed.
        key = (
            revision,
            limit,
            tuple((preset_id, tuple(sorted(values))) for preset_id, values in presets),
        )
        with self._navigation_tally_lock:
            memo = self._navigation_tally_memo
            if memo is not None and memo[0] == key:
                base = memo[1]
            else:
                started = time.monotonic()
                base = self._compute_navigation_tallies(presets, limit, snapshot)
                finished = time.monotonic()
                self._navigation_tally_memo = (key, base)
                self._navigation_tally_at = finished
                self._navigation_tally_cost_s = finished - started
        return _with_recency(base, recency_windows, current_ns)

    def navigation_tallies_fresh_within(
        self,
        presets: Sequence[tuple[str, Collection[str]]],
        recency_windows: Sequence[tuple[str, float]],
        limit: int,
        *,
        min_stale_s: float,
        now_ns: int | None = None,
    ) -> NavigationTallies | None:
        """The memoized tallies if they are still current, else None.

        Cheap enough for the event loop: a tuple compare and a clock read, no
        index pass and no snapshot. That is the point of having it separate --
        the caller can find out whether it needs to pay O(index) *before*
        paying the O(index) list copy that feeding the pass requires.

        Freshness is by age rather than by revision because during a walk
        ``rollup_revision`` advances on every write -- roughly ninety times a
        second at the emit batch size -- so a revision test can never hold
        while scanning, which is exactly when the pass is most expensive and
        most repeated. The numbers are already labelled provisional to the
        client (``tally_cache_status``), so serving them a beat stale says
        nothing new; recomputing them per request during a scan is what the
        client never asked for.

        The bound is *at least* ``min_stale_s`` and at least as long as the
        last pass took. Deriving it from the measured cost is what keeps it
        right across corpus sizes: the pass visits every entry, so a bound
        that is generous at ten thousand files starves the event loop at a
        million. Refusing to spend more than about half the time recomputing a
        number the client is already told is provisional is the rule; the
        constant is only the floor for a tree small enough that the pass is
        free.
        """

        key_presets = tuple((preset_id, tuple(sorted(values))) for preset_id, values in presets)
        with self._navigation_tally_lock:
            memo = self._navigation_tally_memo
            if memo is None:
                return None
            memo_key, base = memo
            # Everything after the revision is what this caller's shape has to
            # match; a different limit or preset set is a different question.
            if memo_key[1:] != (limit, key_presets):
                return None
            # An unchanged revision *proves* the memo current, so age has
            # nothing to add and must not gate it. Letting it do so killed this
            # fast path exactly where it should always hit: the timestamp is
            # written only when the pass runs, so once a walk finishes and the
            # revision stops moving, the memo aged past the bound and every
            # later poll missed forever -- each one then paying a full index
            # copy before discovering the revision had not moved after all.
            #
            # The bound is a concession to a revision that is *moving*, which
            # is the scan. It has no business deciding anything once the tree
            # has settled.
            if memo_key[0] != self._rollup_generation:
                bound = max(min_stale_s, self._navigation_tally_cost_s)
                if time.monotonic() - self._navigation_tally_at > bound:
                    return None
        current_ns = time.time_ns() if now_ns is None else now_ns
        return _with_recency(base, recency_windows, current_ns)

    def navigation_tallies_snapshotting(
        self,
        presets: Sequence[tuple[str, Collection[str]]],
        recency_windows: Sequence[tuple[str, float]],
        limit: int,
    ) -> NavigationTallies:
        """Take the index snapshot and compute the tallies, both off the loop.

        The snapshot is a list copy of every known entry -- 300,000 of them on
        the bench corpus -- so taking it in the caller means the event loop
        pays it even when the pass that needs it is about to be memoized away.
        Pairing the two here lets the route hand the whole cost to a thread.
        """

        # One lock covering both reads, for two reasons that happen to share a fix.
        #
        # This is the first call site that reads the index from a worker thread
        # rather than from the event loop, so the writers' lock was no longer
        # doing anything for this reader. Benign under the GIL today -- a
        # ``list(dict.values())`` does not tear -- and not benign on a
        # free-threaded build, which CI already exercises on 3.14.
        #
        # And the revision has to be read with the snapshot, not after it. The
        # walker can write in between, which keys the memo to a revision newer
        # than the contents it summarizes; if that lands on the walk's final
        # writes, the settled tree serves under-counted tallies from that memo
        # forever, because the revision never advances again to evict it. A
        # narrow window with a permanent consequence.
        with self._rollup_cache_lock:
            snapshot = list(self._entries.values())
            revision = self._rollup_generation
        return self.navigation_tallies(
            presets,
            recency_windows,
            limit,
            entries=snapshot,
            revision=revision,
        )

    def _compute_navigation_tallies(
        self,
        presets: Sequence[tuple[str, Collection[str]]],
        limit: int,
        snapshot: Sequence[FsEntry],
    ) -> _NavigationTallyBase:
        """One pass over *snapshot*, with nothing in it that depends on the clock.

        Recency is the only clock-dependent part, and bucketing it here would
        tie the whole result to the moment it was computed. Instead the pass
        collects sorted mtimes, which the caller searches per window. That
        keeps everything above memoizable on the index revision alone.
        """

        files = size = ignored_files = ignored_size = 0
        tracked_mtimes: array[int] = array("q")
        ignored_mtimes: array[int] = array("q")
        extension_counts: dict[str, list[int]] = {}
        canonical_extension_counts: dict[str, list[int]] = {}
        family_counts: dict[str, list[int]] = {}
        preset_counts: dict[str, list[int]] = {}
        normalized_presets: list[tuple[str, frozenset[str], frozenset[str]]] = []
        for preset_id, values in presets:
            extensions: set[str] = set()
            names: set[str] = set()
            for value in values:
                normalized = value.lower()
                (extensions if normalized.startswith(".") else names).add(normalized)
            preset_counts[preset_id] = [0, 0]
            normalized_presets.append((preset_id, frozenset(extensions), frozenset(names)))
        for entry in snapshot:
            if entry.type != "file":
                continue
            ignored_index = 1 if entry.gitignored else 0
            if entry.gitignored:
                ignored_files += 1
                ignored_size += entry.size or 0
            else:
                files += 1
                size += entry.size or 0

            ext = entry.ext.lower()
            if ext:
                row = extension_counts.get(ext)
                if row is None:
                    row = [0, 0]
                    extension_counts[ext] = row
                row[ignored_index] += 1

                canonical = canonical_extension(ext)
                canonical_row = canonical_extension_counts.setdefault(canonical, [0, 0])
                canonical_row[ignored_index] += 1

                family_match = family_for_extension(ext)
                if family_match is not None:
                    family_row = family_counts.setdefault(family_match.family.id, [0, 0])
                    family_row[ignored_index] += 1

            name = entry.name.lower()
            semantic_category = category_for_file(name, ext)
            for preset_id, preset_extensions, preset_names in normalized_presets:
                if (
                    preset_id == semantic_category
                    or ext in preset_extensions
                    or name in preset_names
                ):
                    preset_counts[preset_id][ignored_index] += 1

            (ignored_mtimes if entry.gitignored else tracked_mtimes).append(entry.mtime_ns)

        summary = {
            "files": files,
            "size": size,
            "ignored_files": ignored_files,
            "ignored_size": ignored_size,
        }
        ranked = sorted(
            extension_counts.items(),
            key=lambda item: (-(item[1][0] + item[1][1]), item[0]),
        )
        extension_rows: list[list[object]] = [
            [ext, counts[0], counts[1]] for ext, counts in ranked[:limit]
        ]
        canonical_ranked = sorted(
            canonical_extension_counts.items(),
            key=lambda item: (-(item[1][0] + item[1][1]), item[0]),
        )
        canonical_rows: list[list[object]] = [
            [ext, counts[0], counts[1]] for ext, counts in canonical_ranked[:limit]
        ]
        family_rows: list[list[object]] = [
            [family_id, counts[0], counts[1]]
            for family_id, counts in sorted(
                family_counts.items(),
                key=lambda item: (-(item[1][0] + item[1][1]), item[0]),
            )
        ]
        preset_rows: list[list[object]] = [
            [preset_id, counts[0], counts[1]] for preset_id, counts in preset_counts.items()
        ]
        registry = load_file_type_registry()
        tracked_mtimes = array("q", sorted(tracked_mtimes))
        ignored_mtimes = array("q", sorted(ignored_mtimes))
        oldest_mtime_ns = min(
            tracked_mtimes[0] if tracked_mtimes else 0,
            ignored_mtimes[0] if ignored_mtimes else 0,
        )
        if not tracked_mtimes:
            oldest_mtime_ns = ignored_mtimes[0] if ignored_mtimes else 0
        elif not ignored_mtimes:
            oldest_mtime_ns = tracked_mtimes[0]
        newest_mtime_ns = max(
            tracked_mtimes[-1] if tracked_mtimes else 0,
            ignored_mtimes[-1] if ignored_mtimes else 0,
        )
        return _NavigationTallyBase(
            summary=summary,
            file_type_registry={
                "schema_version": registry.schema_version,
                "revision": registry.revision,
                "fingerprint": registry.fingerprint,
            },
            extensions=extension_rows,
            canonical_extensions=canonical_rows,
            type_families=family_rows,
            type_presets=preset_rows,
            tracked_mtimes=tracked_mtimes,
            ignored_mtimes=ignored_mtimes,
            oldest_mtime_ns=oldest_mtime_ns,
            newest_mtime_ns=newest_mtime_ns,
        )

    def file_type_tallies(
        self,
        presets: Sequence[tuple[str, Collection[str]]],
        limit: int = 200,
        *,
        entries: Sequence[FsEntry] | None = None,
    ) -> tuple[list[list[object]], list[list[object]]]:
        """Return extension and aggregate-preset rows in one index pass.

        Both shapes are ``[key, tracked_files, ignored_files]``. Dotted
        preset tokens match the indexed logical extension; other tokens
        match a complete filename case-insensitively. A file is counted
        at most once per preset.
        """

        tallies = self.navigation_tallies(presets, (), limit=limit, entries=entries)
        return tallies["extensions"], tallies["type_presets"]

    def extension_tally(self, limit: int = 200) -> list[list[object]]:
        """``[ext, tracked_files, ignored_files]`` rows, most frequent first.

        The nav's extension filter cannot tally from the Quick File
        catalog: ``catalog_files`` drops gitignored entries by design
        (nobody wants to fuzzy-find into ``node_modules``), so a menu
        built from it undercounts every extension the tree still shows
        while gitignored rows are visible.

        Tracked and ignored are kept apart rather than summed so the
        menu can report whichever total matches the user's current
        gitignored setting instead of one that is wrong half the time.

        Bounded by ``limit`` on the way out; the tail of one-off
        extensions is exactly what a filter menu does not need.
        """

        rows, _presets = self.file_type_tallies((), limit=limit)
        return rows

    def rollup(
        self,
        path: str,
        *,
        depth: int,
        top: int,
        ext_top: int,
        remaining_top: int = ROLLUP_FILE_TYPE_REMAINING_LIMIT,
        filename_top: int = ROLLUP_FILE_TYPE_FILENAME_LIMIT,
        ext_rank: RollupRank = "bytes",
        max_nodes: int | None = None,
    ) -> RollupResult | None:
        """Return the bounded rollup for an indexed directory."""

        options = RollupOptions(
            depth=depth,
            top=top,
            ext_top=ext_top,
            remaining_top=remaining_top,
            filename_top=filename_top,
            ext_rank=ext_rank,
            max_nodes=ROLLUP_MAX_NODES if max_nodes is None else max_nodes,
        )
        entries, children_by_parent, snapshot_epoch = self._rollup_view()
        # Reads fall through to the shared memo; writes land in ``computed``.
        # ``build_rollup`` runs in a worker thread while the walker keeps
        # mutating the index on the event loop, so writing the shared memo in
        # place would let an aggregate computed here land *after* a newer
        # write evicted it, leaving a tally that is wrong and never corrects
        # itself. Keeping this pass's own results separate also means the
        # guarded merge below touches only what this pass actually computed
        # rather than everything already cached.
        computed: SubtreeAggregateCache = {}
        try:
            result = build_rollup(
                entries,
                children_by_parent,
                path,
                options,
                ancestor_gitignored=self._ancestor_gitignored(path, entries),
                aggregates=ChainMap(computed, self._subtree_aggregates),
            )
        except BaseException:
            # The pass is still counted in flight; retiring it here keeps a
            # failed rollup from pinning the eviction-epoch map forever.
            self._merge_subtree_aggregates({}, snapshot_epoch)
            raise
        self._merge_subtree_aggregates(computed, snapshot_epoch)
        return result

    def _merge_subtree_aggregates(
        self,
        memo: SubtreeAggregateCache,
        snapshot_epoch: int,
    ) -> None:
        """Publish aggregates from one rollup pass, dropping the stale ones.

        A directory is only republished when nothing has evicted it since
        *snapshot_epoch* — the epoch that was current when the pass took its
        entry snapshot. Anything evicted after that was computed from data the
        walker has already moved past, so it is discarded rather than cached.
        """

        with self._rollup_cache_lock:
            for directory_path, aggregate in memo.items():
                if self._aggregate_evicted_at.get(directory_path, 0) <= snapshot_epoch:
                    self._subtree_aggregates[directory_path] = aggregate
            self._rollup_passes_in_flight -= 1
            if self._rollup_passes_in_flight == 0:
                # The map only exists to let a merge refuse an aggregate the
                # walker has moved past. With no pass in flight there is no
                # merge left to consult it, so every epoch in it is now dead
                # weight. Without this it grows with every directory path seen
                # in the process lifetime rather than with the directory count,
                # and a long session over a churning tree (build outputs,
                # node_modules reinstalls, temp dirs) never gives any of it back.
                self._aggregate_evicted_at.clear()

    def _rollup_view(
        self,
    ) -> tuple[Mapping[str, FsEntry], Mapping[str, Sequence[FsEntry]], int]:
        """Return live read views of the index plus the current eviction epoch.

        Nothing is copied. ``build_rollup`` reads both mappings only by key,
        and a single ``dict`` lookup on string keys is atomic under the GIL,
        so the entry map is safe to read from the rollup worker thread while
        the walker keeps writing on the event loop. Child buckets are iterated
        rather than looked up, so those go through ``_ChildrenView``, which
        holds the index lock for the copy.

        Reading live means a rollup can observe writes that land mid-build.
        That is why the epoch returned here gates
        :meth:`_merge_subtree_aggregates`: any directory written since this
        moment is refused a cache entry, so only aggregates whose subtree
        provably did not move are retained.
        """

        with self._rollup_cache_lock:
            epoch = self._aggregate_epoch
            self._rollup_passes_in_flight += 1
        return self._entries, _ChildrenView(self), epoch

    def _evict_subtree_aggregates(self, path: str, *, is_dir: bool) -> None:
        """Drop the cached aggregate for *path* and every ancestor up to root.

        Caller must hold ``_rollup_cache_lock``.

        A directory's aggregate summarizes everything beneath it, so a write
        at *path* only invalidates *path* and its ancestors; sibling subtrees
        stay valid and are reused, which is what keeps a rollup during a scan
        proportional to what moved rather than to the whole index.

        Only directories are tracked. Eviction epochs are recorded even for a
        directory that holds no aggregate right now, because a rollup pass
        already in flight may be about to publish one, and the epoch is what
        tells the merge to refuse it. Files are skipped so the epoch map stays
        proportional to the directory count rather than the entry count.

        Cost is one chain walk per stored entry, bounded by ``INVENTORY_MAX_DEPTH``.
        """

        self._aggregate_epoch += 1
        epoch = self._aggregate_epoch
        if is_dir:
            self._subtree_aggregates.pop(path, None)
            self._aggregate_evicted_at[path] = epoch
        cursor = path
        while cursor:
            cursor = cursor.rpartition("/")[0]
            self._subtree_aggregates.pop(cursor, None)
            self._aggregate_evicted_at[cursor] = epoch
            if not cursor:
                return

    def _replace_index_entry(self, entry: FsEntry) -> None:
        """Store an entry and invalidate cached rollup topology atomically."""

        with self._rollup_cache_lock:
            existing = self._entries.get(entry.path)
            if entry.type == "file" and (existing is None or existing.type != "file"):
                self._files_indexed += 1
            elif entry.type != "file" and existing is not None and existing.type == "file":
                self._files_indexed -= 1
            if entry.type == "dir" and (existing is None or existing.type != "dir"):
                self._directories_indexed += 1
            elif entry.type != "dir" and existing is not None and existing.type == "dir":
                self._directories_indexed -= 1
            self._entries[entry.path] = entry
            self._rollup_generation = next(_ROLLUP_REVISIONS)
            # The served root is its own parent; listing it as its own child
            # would make subtree aggregation recurse forever.
            if entry.path != entry.parent:
                self._children_index.setdefault(entry.parent, {})[entry.path] = entry
            self._evict_subtree_aggregates(entry.path, is_dir=entry.type == "dir")

    def _pop_index_entry(self, path: str) -> FsEntry | None:
        """Remove an entry and invalidate cached rollup topology atomically."""

        with self._rollup_cache_lock:
            entry = self._entries.pop(path, None)
            if entry is not None:
                if entry.type == "file":
                    self._files_indexed -= 1
                elif entry.type == "dir":
                    self._directories_indexed -= 1
                self._rollup_generation = next(_ROLLUP_REVISIONS)
                siblings = self._children_index.get(entry.parent)
                if siblings is not None:
                    siblings.pop(path, None)
                    if not siblings:
                        del self._children_index[entry.parent]
                self._children_index.pop(path, None)
                self._evict_subtree_aggregates(path, is_dir=entry.type == "dir")
            return entry

    def _ancestor_gitignored(self, path: str, entries: Mapping[str, FsEntry]) -> bool:
        """Whether any strict ancestor of *path* carries the gitignore flag."""

        if not path:
            return False
        segments = path.split("/")
        prefix = ""
        for segment in segments[:-1]:
            prefix = f"{prefix}/{segment}" if prefix else segment
            ancestor = entries.get(prefix)
            if ancestor is not None and ancestor.gitignored:
                return True
        return False

    # ── Writes ──────────────────────────────────────────────

    def invalidate(self, path: str) -> None:
        """Bump the generation counter on *path* and every
        ancestor up to root. The walker (or a subsequent watcher
        op) only writes a result if the generation it started with
        matches the current one; stale writes are dropped on the
        floor. Cheap: an ancestor chain is at most ``MAX_DEPTH``
        entries.
        """

        cursor = path
        while True:
            self._generation[cursor] = self._generation.get(cursor, 0) + 1
            if not cursor:
                break
            slash = cursor.rfind("/")
            cursor = cursor[:slash] if slash >= 0 else ""

    async def rewalk_subtree(
        self,
        rel: str,
        *,
        gitignore_check: Callable[[Path, bool], bool] | None = None,
        gitignore_prepared: bool = False,
        max_depth: int | None = None,
    ) -> None:
        """Run ``walk_tree`` rooted at ``self._root / rel`` and apply
        each yielded entry through :meth:`_apply_walker_entry`. Used
        by the watcher to ingest a newly-created directory subtree
        without waiting for a process restart.

        Race-safety: walker entries arrive with
        ``write_token=None`` (fresh observation) and
        :meth:`_store_walker_entry` stamps them with the current
        generation at write time. Producers that need to detect a
        write-while-invalidating race opt in by reading
        :meth:`capture_write_token` before observing the filesystem
        and passing the token back on the resulting entry.

        Caller's responsibility: only point this at subtrees the
        watcher reported as created. Capping depth/file-count is
        shared with the boot walker — pointing this at a
        multi-million-file subtree will block the watcher's task
        until the walk hits the cap.
        """

        if self._root is None:
            return
        root = self._root
        previous_subtree = self._entries.get(rel)
        if not rel:
            # The whole-root re-walk is what start() does; refuse to
            # avoid two walkers writing into the index simultaneously.
            return
        target = root / rel
        try:
            target_resolved = target.resolve()
        except OSError:
            return

        # ── Containment + symlink safety ────────────────────────
        #
        # A rewalk must never escape the served root. ``rel`` is
        # joined onto the root and then ``resolve()``-d, which
        # collapses ``..`` and *follows symlinks*. Two failure modes
        # this guards against, both observed as a phantom subtree in
        # the nav (a directory appearing to contain a copy of itself
        # or of a sibling repo):
        #
        #   1. ``rel`` (or an ancestor of it) is a symlink that
        #      resolves *outside* the served root — e.g. an
        #      ``attic/foo`` link pointing at ``/repos/bar`` or back
        #      up to the root's own parent. Following it would graft
        #      a foreign tree into the inventory under ``rel``.
        #   2. ``rel``'s final component is a symlink to a directory.
        #      The boot walker records symlinks as *leaf* entries
        #      (``follow_symlinks=False``); descending into one here
        #      would diverge from the boot tree and, because the
        #      rebased entries keep the *resolved* target's basename
        #      as their ``name``, mislabel the grafted node.
        #
        # In both cases we refuse and warn rather than walk, so an
        # unexpected filesystem shape is visible in the logs instead
        # of silently corrupting the tree.
        root_resolved = root.resolve()
        if target_resolved != root_resolved and root_resolved not in target_resolved.parents:
            LOG.warning(
                "inventory: refusing rewalk of %r — resolves to %s, outside served root %s",
                rel,
                target_resolved,
                root_resolved,
            )
            return
        if target.is_symlink():
            LOG.warning(
                "inventory: refusing rewalk of symlinked dir %r -> %s "
                "(boot walker treats symlinks as leaf entries)",
                rel,
                target_resolved,
            )
            return
        if not target_resolved.is_dir():
            return
        # Verbose trace at DEBUG so a high log level (``--log-level debug``
        # / ``METABROWSER_LOG_LEVEL=DEBUG``) shows every rewalk target and
        # its resolved path, making symlink-following auditable.
        LOG.debug("inventory: rewalk_subtree rel=%s resolved=%s", rel, target_resolved)
        gi_check = gitignore_check
        if not gitignore_prepared:
            gi_check = await run_cancellable_thread(
                lambda cancel_event: _build_gitignore_check_for(
                    root,
                    cancel_event=cancel_event,
                )
            )
        async for entry in walk_tree(
            target_resolved,
            max_depth=(self._max_depth if max_depth is None else min(self._max_depth, max_depth)),
            max_files=self._max_files,
            gitignore_check=gi_check,
        ):
            # ``walk_tree`` yields paths relative to *target_resolved*,
            # not the served root. Re-key under the served root so
            # entries land at the right place in ``_entries``.
            if entry.path == "":
                rebased_path = rel
                rebased_parent = rel.rsplit("/", 1)[0] if "/" in rel else ""
                rebased_parent = rebased_parent if rebased_parent != rel else ""
            else:
                rebased_path = f"{rel}/{entry.path}"
                rebased_parent = f"{rel}/{entry.parent}" if entry.parent else rel
            rebased = _internal_entry(replace(entry, path=rebased_path, parent=rebased_parent))
            self._apply_walker_entry(rebased)

        current_subtree = self._entries.get(rel)
        if current_subtree is not None and current_subtree.type == "dir":
            previous_files = 0
            previous_size = 0
            previous_unignored_files = 0
            previous_unignored_size = 0
            if previous_subtree is not None:
                if previous_subtree.type == "file":
                    previous_files = 1
                    previous_size = previous_subtree.size
                    if not previous_subtree.gitignored:
                        previous_unignored_files = 1
                        previous_unignored_size = previous_subtree.size
                else:
                    previous_files = previous_subtree.total_files or 0
                    previous_size = previous_subtree.total_size or 0
                    previous_unignored_files = previous_subtree.unignored_files or 0
                    previous_unignored_size = previous_subtree.unignored_size or 0
            current_files = current_subtree.total_files or 0
            current_size = current_subtree.total_size or 0
            current_unignored_files = current_subtree.unignored_files or 0
            current_unignored_size = current_subtree.unignored_size or 0
            aggregate_updates = self._update_ancestor_aggregates(
                parent=current_subtree.parent,
                delta_files=current_files - previous_files,
                delta_size=current_size - previous_size,
                delta_unignored_files=current_unignored_files - previous_unignored_files,
                delta_unignored_size=current_unignored_size - previous_unignored_size,
            )
            if aggregate_updates:
                self._emit(FsChange(ops=tuple(FsUpsert(entry=e) for e in aggregate_updates)))

    def remove(self, path: str) -> None:
        """Remove *path* and every descendant from the index. Emits
        one ``FsChange`` event whose ops cover every removed path so
        subscribers can drop the corresponding rows in a single
        batch. Idempotent: removing a path that isn't in the index
        is a no-op.

        For files and symlinks this drops one entry. For directories it walks
        ``_entries`` for any path equal to ``{path}`` or under
        ``{path}/`` and drops them all. The order of ops in the
        emitted ``FsChange`` is unspecified — clients should treat
        each op independently.
        """

        if not path:
            # Refuse to remove the served root.
            return
        # The whole method runs synchronously: every inventory writer
        # (walker, rewalk_subtree, watcher, active_tracker) lives on
        # the same asyncio event loop and only yields at explicit
        # ``await`` points. No await happens here, so no other
        # coroutine can mutate ``_entries`` between the snapshot and
        # the pops. A producer that wants to land a write *across*
        # this region opts into race-safety via
        # :meth:`capture_write_token` — the bumped generation drops
        # any stale captured write that lands after the remove.
        target = self._entries.get(path)
        if target is None:
            return
        if target.type == "dir":
            prefix = path + "/"
            removed = [
                cur for cur in list(self._entries.keys()) if cur == path or cur.startswith(prefix)
            ]
        else:
            removed = [path]
        removed_entries = [self._entries[cur] for cur in removed]
        removed_files = [entry for entry in removed_entries if entry.type == "file"]
        removed_unignored_files = [entry for entry in removed_files if not entry.gitignored]
        outer_parent = target.parent
        for cur in removed:
            entry = self._pop_index_entry(cur)
            if entry is not None:
                if entry.type in ("file", "symlink"):
                    self._adjust_descendant_leaf_aggregates(
                        parent=entry.parent,
                        delta_leaves=-1,
                    )
                if entry.type == "file":
                    self._adjust_descendant_file_aggregates(
                        parent=entry.parent,
                        delta_files=-1,
                        delta_size=-entry.size,
                    )
                    if not entry.gitignored:
                        self._adjust_descendant_unignored_file_aggregates(
                            parent=entry.parent,
                            delta_files=-1,
                            delta_size=-entry.size,
                        )
                elif entry.type == "dir":
                    self._pending_dirs.discard(entry.path)
                    self._child_mtime_heaps.pop(entry.path, None)
                self._remove_direct_child(entry)
                self._recorded_child_mtimes.pop(entry.path, None)
            # Bump the generation so any in-flight walker write for
            # this path with a captured WriteToken is dropped on
            # store rather than resurrecting a removed entry.
            self.invalidate(cur)
        aggregate_updates = self._update_ancestor_aggregates(
            parent=outer_parent,
            delta_files=-len(removed_files),
            delta_size=-sum(entry.size for entry in removed_files),
            delta_unignored_files=-len(removed_unignored_files),
            delta_unignored_size=-sum(entry.size for entry in removed_unignored_files),
        )
        ops: list[FsChangeOp] = [FsRemove(path=cur) for cur in removed]
        ops.extend(FsUpsert(entry=entry) for entry in aggregate_updates)
        self._emit(FsChange(ops=tuple(ops)))

    def diagnostic_snapshot(
        self,
        paths: Sequence[str],
        *,
        sample_limit: int = 20,
    ) -> dict[str, object]:
        """Return bounded state for diagnosing unresolved directory totals.

        The client reports only rendered paths. Pairing those with the live
        inventory, generation, descendant aggregate, and walker state makes it
        possible to distinguish a server-side pending directory from a stale
        browser snapshot or a missed event-stream patch.
        """

        limit = max(0, sample_limit)
        walker = self._walker_task
        if walker is None:
            walker_state = "missing"
        elif walker.cancelled():
            walker_state = "cancelled"
        elif walker.done():
            walker_state = "done"
        else:
            walker_state = "running"

        elapsed_ms = 0
        if self._started_at_ns:
            elapsed_ms = (time.monotonic_ns() - self._started_at_ns) // 1_000_000

        requested: list[dict[str, object]] = []
        for path in list(paths)[:limit]:
            entry = self._entries.get(path)
            row: dict[str, object] = {
                "path": path,
                "known": entry is not None,
                "pending": path in self._pending_dirs,
                "generation": self._generation.get(path, 0),
                "direct_children": self._direct_child_counts.get(path, 0),
                "descendant_files": self._descendant_file_counts.get(path, 0),
                "descendant_size": self._descendant_file_sizes.get(path, 0),
                "descendant_leaves": self._descendant_leaf_counts.get(path, 0),
            }
            if entry is not None:
                row.update(
                    {
                        "type": entry.type,
                        "total_files": entry.total_files,
                        "total_size": entry.total_size,
                        "newest_mtime_ns": entry.newest_mtime_ns,
                        "empty": entry.empty,
                        "write_generation": (
                            entry.write_token.generation if entry.write_token is not None else None
                        ),
                    }
                )
            requested.append(row)

        return {
            "status": self._status,
            "elapsed_ms": elapsed_ms,
            "files_indexed": self._files_indexed,
            "entries": len(self._entries),
            "pending_dirs": len(self._pending_dirs),
            "pending_dir_sample": heapq.nsmallest(limit, self._pending_dirs),
            "catalog_revision": self._catalog_revision,
            "walker_task": walker_state,
            "requested_paths": requested,
        }

    # ── Internals ───────────────────────────────────────────

    async def _run_walker(self, root: Path) -> None:
        """Drive ``walk_tree`` and apply each yielded entry. On
        completion, set ``done_event`` so ``wait_until_done()``
        resolves.

        Walker upserts are batched into ``fs.change`` events with up
        to ``WALKER_EMIT_BATCH`` ops apiece. Per-entry emits would
        produce one event per file, overflowing every subscriber's
        queue on the initial scan.
        """

        batch: list[FsEntry] = []
        entries_since_yield = 0
        try:
            gi_check = await run_cancellable_thread(
                lambda cancel_event: _build_gitignore_check_for(
                    root,
                    cancel_event=cancel_event,
                )
            )
            async for observation in walk_tree(
                root,
                max_depth=self._max_depth,
                max_files=self._max_files,
                gitignore_check=gi_check,
            ):
                entry = _internal_entry(observation)
                if entry.type == "dir" and entry.total_files is None:
                    self._walker_dir_generations.setdefault(
                        entry.path, self._generation.get(entry.path, 0)
                    )
                elif entry.type == "dir":
                    observed_generation = self._walker_dir_generations.pop(
                        entry.path, self._generation.get(entry.path, 0)
                    )
                    entry = replace(entry, write_token=WriteToken(observed_generation))
                stored = self._store_walker_entry(entry)
                if stored is not None:
                    batch.append(stored)
                    if len(batch) >= WALKER_EMIT_BATCH:
                        self._emit(FsChange(ops=tuple(FsUpsert(entry=e) for e in batch)))
                        batch.clear()
                entries_since_yield += 1
                if entries_since_yield >= _WALKER_COOPERATIVE_YIELD_BATCH:
                    entries_since_yield = 0
                    await asyncio.sleep(0)
            if batch:
                self._emit(FsChange(ops=tuple(FsUpsert(entry=e) for e in batch)))
                batch.clear()
        except asyncio.CancelledError:
            self._status = "idle"
            raise
        except Exception as error:
            # A walker crash is distinct from "never started". A
            # ``status()`` of ``failed`` lets capability probes and
            # the SSE bus surface the broken state instead of
            # silently returning an empty inventory forever. The
            # exception is logged with full traceback (lifespan
            # caught a separate path).
            LOG.exception("inventory walker crashed")
            with self._rollup_cache_lock:
                self._last_error = f"{type(error).__name__}: {error}"
                self._status = "failed"
                self._rollup_generation = next(_ROLLUP_REVISIONS)
            self._done_event.set()
            self._record_provider_change(
                dirty_queries=frozenset({QueryKind.METADATA, QueryKind.DIAGNOSTICS})
            )
            return

        is_truncated = self._files_indexed >= self._max_files
        if not is_truncated:
            try:
                self._repair_pending_dir_aggregates()
            except Exception:
                LOG.exception("inventory repair of pending dir aggregates failed")
        with self._rollup_cache_lock:
            self._status = "truncated" if is_truncated else "done"
            self._rollup_generation = next(_ROLLUP_REVISIONS)
        self._done_event.set()
        # Push-based completion for stream clients: the Quick File
        # catalog converges through live ops, so all it needs at
        # walk end is the completeness flip — not a refetch.
        self._emit(
            CapabilityUpdate(
                backends=(),
                index={
                    "complete": True,
                    "truncated": is_truncated,
                    "indexed_files": self._files_indexed,
                    "max_files": self._max_files,
                    "status": self._status,
                },
                events={},
            )
        )
        elapsed_ms = (time.monotonic_ns() - self._started_at_ns) // 1_000_000
        LOG.info(
            "inventory walker complete: provider=python contract=%s status=%s "
            "files=%d entries=%d elapsed=%dms",
            _CONTRACT_ID,
            self._status,
            self._files_indexed,
            len(self._entries),
            elapsed_ms,
        )

    def _repair_pending_dir_aggregates(self) -> None:
        """Finalize any directory placeholders left by stale writes.

        Watcher invalidations can bump an ancestor generation while
        the boot walker is still running. That correctly rejects the
        stale final write, but after an uncapped walk the inventory
        already contains the descendant file entries needed to compute
        a useful aggregate. Rebuild those pending dir totals from the
        known files so ``status=done`` never exposes null tallies.

        Descendant counts and sizes are maintained as entries change, so
        completion visits only pending directories. Processing deepest
        paths first lets each repaired mtime feed its parent's child heap.
        """

        pending_dirs = sorted(self._pending_dirs, key=_depth_of, reverse=True)
        if not pending_dirs:
            return

        batch: list[FsEntry] = []
        repaired_count = 0
        for path in pending_dirs:
            existing = self._entries.get(path)
            if existing is None or existing.type != "dir" or existing.total_files is not None:
                self._pending_dirs.discard(path)
                continue
            newest_mtime = self._direct_child_newest(path)
            repaired = replace(
                existing,
                total_files=self._descendant_file_counts.get(path, 0),
                total_size=self._descendant_file_sizes.get(path, 0),
                unignored_files=self._descendant_unignored_file_counts.get(path, 0),
                unignored_size=self._descendant_unignored_file_sizes.get(path, 0),
                newest_mtime_ns=newest_mtime,
                empty=self._descendant_leaf_counts.get(path, 0) == 0,
                mtime_ns=newest_mtime,
                write_token=WriteToken(self._generation.get(path, 0)),
            )
            self._replace_index_entry(repaired)
            self._pending_dirs.discard(path)
            self._record_child_mtime(repaired)
            repaired_count += 1
            batch.append(repaired)
            if len(batch) >= WALKER_EMIT_BATCH:
                self._emit(FsChange(ops=tuple(FsUpsert(entry=e) for e in batch)))
                batch.clear()
        if batch:
            self._emit(FsChange(ops=tuple(FsUpsert(entry=e) for e in batch)))
        LOG.debug("inventory repaired %d pending dir aggregate(s)", repaired_count)

    def capture_write_token(self, path: str) -> WriteToken:
        """Capture the inventory's current generation counter for *path*.

        Producers that want race-safety call this before doing slow
        observation (stat, scandir, file hash) and pass the result on
        the resulting :class:`FsEntry`'s ``write_token`` field. If an
        :meth:`invalidate` bumps the counter before the write lands,
        :meth:`_store_walker_entry` drops the write.

        Producers that need no race-safety (the entry reflects the
        filesystem *now*) leave ``write_token=None``; the inventory
        stamps the entry at write time.
        """

        return WriteToken(self._generation.get(path, 0))

    def _store_walker_entry(self, entry: FsEntry) -> FsEntry | None:
        """Apply *entry* to in-memory state. Returns the canonical
        entry (with the latest generation stamped) for downstream
        emit, or ``None`` if a concurrent invalidation made it stale.

        Split from :meth:`_apply_walker_entry` so the walker can
        batch the resulting upserts into one ``fs.change`` event.

        Contract on ``entry.write_token``:

        * ``None`` — freshly observed: the producer (walker / watcher
          / active_tracker) read the filesystem right now and wants
          the inventory to stamp the entry with the current
          generation. Always accepted.
        * :class:`WriteToken(generation=N)` — captured snapshot: the
          producer called :meth:`capture_write_token` before its
          observation and is asking for race-safety. If an
          invalidation has bumped the counter to ``> N`` since,
          the write is dropped.

        The type-level discriminator distinguishes fresh observations from
        captured generations so an unstamped observation cannot be silently
        dropped.
        """

        cur_gen = self._generation.get(entry.path, 0)
        token = entry.write_token
        if token is not None and token.generation < cur_gen:
            # The producer captured the counter at observation start,
            # but an invalidation has bumped it since; drop the stale
            # write and let the next observer pass refresh. This is the
            # expected result of a watcher invalidation racing the boot walk,
            # so retain it for concurrency debugging without presenting
            # normal conflict resolution as a failure.
            LOG.debug(
                "inventory: dropped stale walker write path=%s token_gen=%d cur_gen=%d",
                entry.path,
                token.generation,
                cur_gen,
            )
            return None
        # Either token is None (fresh observation; stamp with cur_gen)
        # or token.generation >= cur_gen (captured snapshot still
        # current; restamp at the latest cur_gen so downstream
        # consumers see a uniform value).
        stamped_token = WriteToken(cur_gen)
        if entry.write_token != stamped_token:
            entry = replace(entry, write_token=stamped_token)
        existing = self._entries.get(entry.path)
        existing_leaf = (
            existing if existing is not None and existing.type in ("file", "symlink") else None
        )
        incoming_leaf = entry if entry.type in ("file", "symlink") else None
        if not (
            existing_leaf is not None
            and incoming_leaf is not None
            and existing_leaf.parent == incoming_leaf.parent
        ):
            if existing_leaf is not None:
                self._adjust_descendant_leaf_aggregates(
                    parent=existing_leaf.parent,
                    delta_leaves=-1,
                )
            if incoming_leaf is not None:
                self._adjust_descendant_leaf_aggregates(
                    parent=incoming_leaf.parent,
                    delta_leaves=1,
                )
        existing_file = existing if existing is not None and existing.type == "file" else None
        incoming_file = entry if entry.type == "file" else None
        if (
            existing_file is not None
            and incoming_file is not None
            and existing_file.parent == incoming_file.parent
        ):
            if existing_file.size != incoming_file.size:
                self._adjust_descendant_file_aggregates(
                    parent=incoming_file.parent,
                    delta_files=0,
                    delta_size=incoming_file.size - existing_file.size,
                )
        else:
            if existing_file is not None:
                self._adjust_descendant_file_aggregates(
                    parent=existing_file.parent,
                    delta_files=-1,
                    delta_size=-existing_file.size,
                )
            if incoming_file is not None:
                self._adjust_descendant_file_aggregates(
                    parent=incoming_file.parent,
                    delta_files=1,
                    delta_size=incoming_file.size,
                )
        existing_unignored_file = (
            existing_file if existing_file is not None and not existing_file.gitignored else None
        )
        incoming_unignored_file = (
            incoming_file if incoming_file is not None and not incoming_file.gitignored else None
        )
        if (
            existing_unignored_file is not None
            and incoming_unignored_file is not None
            and existing_unignored_file.parent == incoming_unignored_file.parent
        ):
            if existing_unignored_file.size != incoming_unignored_file.size:
                self._adjust_descendant_unignored_file_aggregates(
                    parent=incoming_unignored_file.parent,
                    delta_files=0,
                    delta_size=incoming_unignored_file.size - existing_unignored_file.size,
                )
        else:
            if existing_unignored_file is not None:
                self._adjust_descendant_unignored_file_aggregates(
                    parent=existing_unignored_file.parent,
                    delta_files=-1,
                    delta_size=-existing_unignored_file.size,
                )
            if incoming_unignored_file is not None:
                self._adjust_descendant_unignored_file_aggregates(
                    parent=incoming_unignored_file.parent,
                    delta_files=1,
                    delta_size=incoming_unignored_file.size,
                )
        if existing is None:
            self._add_direct_child(entry)
        elif existing.parent != entry.parent:
            self._remove_direct_child(existing)
            self._add_direct_child(entry)
        if entry.type == "dir" and entry.total_files is not None:
            entry = replace(entry, empty=self._descendant_leaf_counts.get(entry.path, 0) == 0)
        self._replace_index_entry(entry)
        if entry.type == "dir" and entry.total_files is None:
            self._pending_dirs.add(entry.path)
        else:
            self._pending_dirs.discard(entry.path)
        self._record_child_mtime(entry)
        return entry

    def apply_live_entry(self, entry: FsEntry) -> None:
        """Store a watcher observation and refresh finalized ancestor totals."""

        existing = self._entries.get(entry.path)
        stored = self._store_walker_entry(entry)
        if stored is None:
            return
        old_file = existing if existing is not None and existing.type == "file" else None
        new_file = stored if stored.type == "file" else None
        aggregate_updates = self._update_ancestor_aggregates(
            parent=stored.parent,
            delta_files=int(new_file is not None) - int(old_file is not None),
            delta_size=(new_file.size if new_file is not None else 0)
            - (old_file.size if old_file is not None else 0),
            delta_unignored_files=int(new_file is not None and not new_file.gitignored)
            - int(old_file is not None and not old_file.gitignored),
            delta_unignored_size=(
                new_file.size if new_file is not None and not new_file.gitignored else 0
            )
            - (old_file.size if old_file is not None and not old_file.gitignored else 0),
        )
        ops = [FsUpsert(entry=stored)]
        ops.extend(FsUpsert(entry=ancestor) for ancestor in aggregate_updates)
        self._emit(FsChange(ops=tuple(ops)))

    def _update_ancestor_aggregates(
        self,
        *,
        parent: str,
        delta_files: int,
        delta_size: int,
        delta_unignored_files: int,
        delta_unignored_size: int,
    ) -> list[FsEntry]:
        updates: list[FsEntry] = []
        cursor = parent
        while True:
            existing = self._entries.get(cursor)
            if (
                existing is not None
                and existing.type == "dir"
                and existing.total_files is not None
                and existing.total_size is not None
            ):
                newest_mtime_ns = self._direct_child_newest(cursor)
                current_unignored_files = (
                    existing.unignored_files
                    if existing.unignored_files is not None
                    else existing.total_files
                )
                current_unignored_size = (
                    existing.unignored_size
                    if existing.unignored_size is not None
                    else existing.total_size
                )
                updated = replace(
                    existing,
                    total_files=max(0, existing.total_files + delta_files),
                    total_size=max(0, existing.total_size + delta_size),
                    unignored_files=max(0, current_unignored_files + delta_unignored_files),
                    unignored_size=max(0, current_unignored_size + delta_unignored_size),
                    newest_mtime_ns=newest_mtime_ns,
                    empty=self._descendant_leaf_counts.get(cursor, 0) == 0,
                    write_token=WriteToken(self._generation.get(cursor, 0)),
                )
                self._replace_index_entry(updated)
                self._record_child_mtime(updated)
                updates.append(updated)
            if cursor == "":
                break
            cursor = cursor.rsplit("/", 1)[0] if "/" in cursor else ""
        return updates

    def _record_child_mtime(self, entry: FsEntry) -> None:
        if entry.path == entry.parent:
            return
        newest = entry.mtime_ns if entry.type == "file" else entry.newest_mtime_ns or 0
        recorded = (entry.parent, newest)
        if self._recorded_child_mtimes.get(entry.path) == recorded:
            return
        self._recorded_child_mtimes[entry.path] = recorded
        heap = self._child_mtime_heaps.setdefault(entry.parent, [])
        heapq.heappush(heap, (-newest, entry.path))
        # Heap entries are versioned implicitly by `_recorded_child_mtimes`.
        # Real mtime changes leave stale versions behind until they reach the
        # top, so compact occasionally to keep a frequently-written file from
        # growing this auxiliary index for the lifetime of the process.
        compact_after = max(64, self._direct_child_counts.get(entry.parent, 0) * 4)
        if len(heap) > compact_after:
            current: dict[str, tuple[int, str]] = {}
            for _negative_mtime, path in heap:
                recorded = self._recorded_child_mtimes.get(path)
                if recorded is not None and recorded[0] == entry.parent:
                    current[path] = (-recorded[1], path)
            heap[:] = current.values()
            heapq.heapify(heap)

    def _adjust_descendant_file_aggregates(
        self,
        *,
        parent: str,
        delta_files: int,
        delta_size: int,
    ) -> None:
        cursor = parent
        while True:
            file_count = self._descendant_file_counts.get(cursor, 0) + delta_files
            if file_count <= 0:
                self._descendant_file_counts.pop(cursor, None)
                self._descendant_file_sizes.pop(cursor, None)
            else:
                self._descendant_file_counts[cursor] = file_count
                self._descendant_file_sizes[cursor] = max(
                    0, self._descendant_file_sizes.get(cursor, 0) + delta_size
                )
            if cursor == "":
                break
            cursor = cursor.rsplit("/", 1)[0] if "/" in cursor else ""

    def _adjust_descendant_unignored_file_aggregates(
        self,
        *,
        parent: str,
        delta_files: int,
        delta_size: int,
    ) -> None:
        """Adjust tracked-file counts and sizes for every ancestor."""

        cursor = parent
        while True:
            file_count = self._descendant_unignored_file_counts.get(cursor, 0) + delta_files
            if file_count <= 0:
                self._descendant_unignored_file_counts.pop(cursor, None)
                self._descendant_unignored_file_sizes.pop(cursor, None)
            else:
                self._descendant_unignored_file_counts[cursor] = file_count
                self._descendant_unignored_file_sizes[cursor] = max(
                    0, self._descendant_unignored_file_sizes.get(cursor, 0) + delta_size
                )
            if cursor == "":
                break
            cursor = cursor.rsplit("/", 1)[0] if "/" in cursor else ""

    def _adjust_descendant_leaf_aggregates(self, *, parent: str, delta_leaves: int) -> None:
        """Adjust visible file-or-symlink leaf counts for every ancestor."""

        cursor = parent
        while True:
            leaf_count = self._descendant_leaf_counts.get(cursor, 0) + delta_leaves
            if leaf_count <= 0:
                self._descendant_leaf_counts.pop(cursor, None)
            else:
                self._descendant_leaf_counts[cursor] = leaf_count
            if cursor == "":
                break
            cursor = cursor.rsplit("/", 1)[0] if "/" in cursor else ""

    def _direct_child_newest(self, parent: str) -> int:
        heap = self._child_mtime_heaps.get(parent)
        if heap is None:
            return 0
        while heap:
            negative_mtime, path = heap[0]
            entry = self._entries.get(path)
            current_mtime = (
                entry.mtime_ns
                if entry is not None and entry.type == "file"
                else (entry.newest_mtime_ns or 0 if entry is not None else 0)
            )
            if (
                entry is not None
                and entry.parent == parent
                and current_mtime == -negative_mtime
                and self._recorded_child_mtimes.get(path) == (parent, current_mtime)
            ):
                return current_mtime
            heapq.heappop(heap)
        self._child_mtime_heaps.pop(parent, None)
        return 0

    def _add_direct_child(self, entry: FsEntry) -> None:
        if entry.path == entry.parent:
            return
        self._direct_child_counts[entry.parent] = self._direct_child_counts.get(entry.parent, 0) + 1

    def _remove_direct_child(self, entry: FsEntry) -> None:
        if entry.path == entry.parent:
            return
        count = self._direct_child_counts.get(entry.parent, 0)
        if count <= 1:
            self._direct_child_counts.pop(entry.parent, None)
        else:
            self._direct_child_counts[entry.parent] = count - 1

    def _apply_walker_entry(self, entry: FsEntry) -> None:
        """Single-entry path used by the watcher and other live
        producers. Writes the entry and emits one ``fs.change``."""

        stored = self._store_walker_entry(entry)
        if stored is not None:
            self._emit(FsChange(ops=(FsUpsert(entry=stored),)))

    def _emit(self, event: StreamEvent) -> None:
        """Translate an internal mutation into the provider change contract."""

        if isinstance(event, FsResyncRequired):
            self._record_provider_change(reset=True)
        elif isinstance(event, FsChange):
            self._catalog_revision += 1
            dirty_paths = tuple(
                dict.fromkeys(
                    op.path if isinstance(op, FsRemove) else op.entry.path for op in event.ops
                )
            )
            self._record_provider_change(
                dirty_paths=dirty_paths,
                dirty_queries=frozenset(
                    {
                        QueryKind.ENTRY,
                        QueryKind.DIRECTORY,
                        QueryKind.FILTERED_TREE,
                        QueryKind.ROLLUP,
                        QueryKind.NAVIGATION,
                        QueryKind.RECENT,
                        QueryKind.CATALOG,
                        QueryKind.DIAGNOSTICS,
                    }
                ),
            )
        elif isinstance(event, CapabilityUpdate):
            self._record_provider_change(
                dirty_queries=frozenset({QueryKind.METADATA, QueryKind.DIAGNOSTICS})
            )

    def _record_provider_change(
        self,
        *,
        dirty_paths: tuple[str, ...] = (),
        dirty_queries: frozenset[QueryKind] = frozenset(),
        reset: bool = False,
    ) -> None:
        """Translate one retained-state mutation into a bounded invalidation."""

        with self._rollup_cache_lock:
            sequence = self._rollup_generation
            entry_count = len(self._entries)
            directory_count = self._directories_indexed
            state = self._state_for(
                self._status,
                entries_observed=entry_count,
                files_indexed=self._files_indexed,
                directory_count=directory_count,
            )
        version = self._version(sequence)
        all_dirty = len(dirty_paths) > MAX_CHANGE_PATHS
        batch = ChangeBatch(
            cursor=ChangeCursor(session=self._session, sequence=sequence),
            version=version,
            state=state,
            dirty_paths=() if all_dirty or reset else dirty_paths,
            dirty_queries=frozenset() if reset else dirty_queries,
            all_dirty=all_dirty and not reset,
            reset=reset,
        )
        if len(self._change_history) >= self._config.change_queue_size:
            dropped = self._change_history.popleft()
            self._replay_floor_sequence = dropped.cursor.sequence
        self._change_history.append(batch)
        for queue in tuple(self._change_subscribers):
            try:
                queue.put_nowait(batch)
            except asyncio.QueueFull:
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait(self._reset_batch())


class PythonInventoryBackend:
    """Construct one Python reference-provider handle per served root."""

    def __init__(
        self,
        *,
        handle_factory: Callable[[InventoryConfig], PythonInventoryHandle] | None = None,
    ) -> None:
        self._handle_factory = handle_factory or self._default_handle

    @staticmethod
    def _default_handle(config: InventoryConfig) -> PythonInventoryHandle:
        return PythonInventoryHandle(config=config)

    async def open(
        self,
        root: Path,
        config: InventoryConfig,
    ) -> PythonInventoryHandle:
        canonical_root = await asyncio.to_thread(root.resolve)
        handle = self._handle_factory(config)
        handle.start_watcher(canonical_root)
        handle.start(canonical_root)
        return handle


# Re-export the non-trivial helpers used by tests and inventory consumers.
__all__ = [
    "DEFAULT_MAX_DEPTH",
    "DEFAULT_MAX_FILES",
    "DEFAULT_REFRESH_TTL_S",
    "IndexStatus",
    "PythonInventoryBackend",
    "PythonInventoryHandle",
    "walk_tree",
]
