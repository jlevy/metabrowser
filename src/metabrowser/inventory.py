"""Process-wide inventory of filesystem state for the browser.

``InventoryIndex`` is the single source of truth for filesystem-entry
metadata in the browser process. The server lifespan eagerly populates
it, ``/api/tree`` and ``/api/activity`` read from it, and writes emit
``fs.change`` events on a single shared SSE channel so the client
fills in skeleton cells without manual reload.

There is exactly one walker task per process. Concurrent
``/api/tree`` requests do **not** trigger walks — they read whatever
is currently in the index and return ``None`` for fields the walker
has not yet finalized. The boot lifespan hook calls
``InventoryIndex.start(root)`` once; the call is idempotent.

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
``InventoryIndex`` object so tests can drive it directly with
``async for``.
"""

from __future__ import annotations

import asyncio
import heapq
import logging
import threading
import time
from collections.abc import Collection, Iterator, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Literal

from metabrowser.cancellable_thread import run_cancellable_thread
from metabrowser.events import (
    CapabilityUpdate,
    CatalogChange,
    CatalogUpsert,
    FsChange,
    FsChangeOp,
    FsEntry,
    FsRemove,
    FsResyncRequired,
    FsSnapshot,
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
from metabrowser.wire_models import NavigationTallies, RollupResult

LOG = logging.getLogger(__name__)

_SUBSCRIBER_OVERFLOW_LOG_INTERVAL_NS = 30_000_000_000
# Unit conversion for comparing second-based filter windows with inventory mtimes.
_NANOSECONDS_PER_SECOND = 1_000_000_000


IndexStatus = Literal["idle", "scanning", "done", "truncated", "failed"]


# ── InventoryIndex ──────────────────────────────────────────────


class _ChildrenView(Mapping[str, "Sequence[FsEntry]"]):
    """Read-through view of ``InventoryIndex._children_index``.

    A rollup visits only the directories whose aggregates are missing, so
    copying every bucket up front is wasted work. Each lookup instead takes
    the index lock and copies just that directory's children, which keeps the
    walker's writes from resizing a bucket mid-iteration.
    """

    __slots__ = ("_index",)

    def __init__(self, index: InventoryIndex) -> None:
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


class InventoryIndex:
    """Process-wide singleton holding the live filesystem
    inventory.

    Every consumer reads from this object. The walker writes into
    it. Per-path generation counters serialize concurrent
    invalidations against in-flight walker writes.

    This is the only stateful object in the inventory plane. Walker and
    watcher observations pass through it so reads and subscriber events
    share one ordered view of each path.
    """

    def __init__(
        self,
        *,
        max_files: int = DEFAULT_MAX_FILES,
        max_depth: int = DEFAULT_MAX_DEPTH,
    ) -> None:
        self._root: Path | None = None
        self._entries: dict[str, FsEntry] = {}
        self._rollup_cache_lock = threading.Lock()
        self._rollup_generation = 0
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
        self._subscribers: set[asyncio.Queue[StreamEvent]] = set()
        self._walker_task: asyncio.Task[None] | None = None
        self._done_event: asyncio.Event = asyncio.Event()
        self._status: IndexStatus = "idle"
        self._max_files = max_files
        self._max_depth = max_depth
        self._files_indexed = 0
        self._started_at_ns: int = 0
        self._subscriber_overflows_since_log = 0
        self._subscriber_overflow_last_log_ns = 0
        # Monotonic per process, bumped on every emitted
        # ``catalog.change`` and on ``clear()``. Not reset on root
        # swap so ``/api/catalog`` ETags never repeat within a
        # process lifetime.
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
        self._status = "scanning"
        self._done_event.clear()
        self._files_indexed = 0
        self._started_at_ns = time.monotonic_ns()
        self._walker_task = asyncio.create_task(
            self._run_walker(root), name="metabrowser-inventory-walker"
        )
        return self._walker_task

    def clear(self) -> None:
        """Drop all state and stop the walker. Called by
        ``paths_safe.register_root_callback`` on root swap; a
        subsequent ``start()`` against the new root rebuilds.

        Emits ``fs.resync_required`` to all subscribers so open
        clients know to drop their FileStore state.
        """

        if self._walker_task is not None and not self._walker_task.done():
            self._walker_task.cancel()
        self._walker_task = None
        with self._rollup_cache_lock:
            self._entries.clear()
            self._rollup_generation += 1
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
        self._files_indexed = 0
        self._status = "idle"
        self._done_event.clear()
        self._catalog_revision += 1
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
        for entry in snapshot:
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
    ) -> NavigationTallies:
        """
        Return root, file-type, and cumulative recency tallies in one index pass.

        Every row is ``[key, tracked_files, ignored_files]``. Keeping the two
        populations separate lets the browser use the same snapshot when the user
        changes whether gitignored files are shown.
        """

        snapshot = self.entries(scope="all-known") if entries is None else entries
        current_ns = time.time_ns() if now_ns is None else now_ns
        recency_cutoffs = [
            (key, current_ns - int(seconds * _NANOSECONDS_PER_SECOND))
            for key, seconds in recency_windows
        ]
        files = size = ignored_files = ignored_size = 0
        extension_counts: dict[str, list[int]] = {}
        canonical_extension_counts: dict[str, list[int]] = {}
        family_counts: dict[str, list[int]] = {}
        preset_counts: dict[str, list[int]] = {}
        recency_counts: dict[str, list[int]] = {key: [0, 0] for key, _cutoff in recency_cutoffs}
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

            for window_key, cutoff_ns in recency_cutoffs:
                if entry.mtime_ns >= cutoff_ns:
                    recency_counts[window_key][ignored_index] += 1

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
        recency_rows: list[list[object]] = [
            [window_key, counts[0], counts[1]] for window_key, counts in recency_counts.items()
        ]
        registry = load_file_type_registry()
        return {
            "summary": summary,
            "file_type_registry": {
                "schema_version": registry.schema_version,
                "revision": registry.revision,
                "fingerprint": registry.fingerprint,
            },
            "extensions": extension_rows,
            "canonical_extensions": canonical_rows,
            "type_families": family_rows,
            "type_presets": preset_rows,
            "recency_tallies": recency_rows,
        }

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
        # Work on a private copy of the memo. ``build_rollup`` runs in a worker
        # thread while the walker keeps mutating the index on the event loop,
        # so writing the shared memo in place would let an aggregate computed
        # from this snapshot land *after* a newer write evicted it, leaving a
        # tally that is wrong and never corrects itself. Copying costs one
        # reference per cached directory and keeps the shared memo untouched
        # until the guarded merge below.
        memo = self._subtree_aggregates_copy()
        result = build_rollup(
            entries,
            children_by_parent,
            path,
            options,
            ancestor_gitignored=self._ancestor_gitignored(path, entries),
            aggregates=memo,
        )
        self._merge_subtree_aggregates(memo, snapshot_epoch)
        return result

    def _subtree_aggregates_copy(self) -> SubtreeAggregateCache:
        """Snapshot the shared aggregate memo for one rollup pass."""

        with self._rollup_cache_lock:
            return dict(self._subtree_aggregates)

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
            self._entries[entry.path] = entry
            self._rollup_generation += 1
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
                self._rollup_generation += 1
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

    async def rewalk_subtree(self, rel: str) -> None:
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
        gi_check = await run_cancellable_thread(
            lambda cancel_event: _build_gitignore_check_for(
                root,
                cancel_event=cancel_event,
            )
        )
        async for entry in walk_tree(
            target_resolved,
            max_depth=self._max_depth,
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
            rebased = replace(entry, path=rebased_path, parent=rebased_parent)
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
                    self._files_indexed -= 1
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

    # ── Subscriptions ───────────────────────────────────────

    def subscribe(self, *, max_queue: int = 1024) -> asyncio.Queue[StreamEvent]:
        """Register a per-connection queue and return it. The route
        layer calls ``Queue.get()`` to pull events into the SSE
        stream.

        Slow consumers remain bounded. When a queue fills, its stale
        backlog is replaced with ``fs.resync_required`` so the route
        layer can force a fresh scoped snapshot without silently
        losing live updates.
        """

        q: asyncio.Queue[StreamEvent] = asyncio.Queue(maxsize=max_queue)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[StreamEvent]) -> None:
        self._subscribers.discard(q)

    def is_subscribed(self, q: asyncio.Queue[StreamEvent]) -> bool:
        """True iff *q* is currently in the subscriber set."""
        return q in self._subscribers

    def subscriber_count(self) -> int:
        return len(self._subscribers)

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
            "subscribers": len(self._subscribers),
            "catalog_revision": self._catalog_revision,
            "walker_task": walker_state,
            "requested_paths": requested,
        }

    def initial_snapshot(self, scope: str = "root-depth-2") -> FsSnapshot:
        """Build the on-connect snapshot. Tuple form (FsSnapshot
        wants an immutable ``entries`` field) so callers can pass
        directly through ``encode_sse``."""

        if scope not in ("root-depth-2", "recent-top-N", "expanded-prefixes", "all-known"):
            raise ValueError(f"unknown scope: {scope!r}")
        entries = tuple(self.entries(scope))  # type: ignore[arg-type]
        complete = self._status in ("done", "truncated")
        return FsSnapshot(scope=scope, entries=entries, complete=complete)  # type: ignore[arg-type]

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
        try:
            gi_check = await run_cancellable_thread(
                lambda cancel_event: _build_gitignore_check_for(
                    root,
                    cancel_event=cancel_event,
                )
            )
            async for entry in walk_tree(
                root,
                max_depth=self._max_depth,
                max_files=self._max_files,
                gitignore_check=gi_check,
            ):
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
                if stored is None:
                    continue
                batch.append(stored)
                if len(batch) >= WALKER_EMIT_BATCH:
                    self._emit(FsChange(ops=tuple(FsUpsert(entry=e) for e in batch)))
                    batch.clear()
            if batch:
                self._emit(FsChange(ops=tuple(FsUpsert(entry=e) for e in batch)))
                batch.clear()
        except asyncio.CancelledError:
            self._status = "idle"
            raise
        except Exception:
            # A walker crash is distinct from "never started". A
            # ``status()`` of ``failed`` lets capability probes and
            # the SSE bus surface the broken state instead of
            # silently returning an empty inventory forever. The
            # exception is logged with full traceback (lifespan
            # caught a separate path).
            LOG.exception("inventory walker crashed")
            self._status = "failed"
            self._done_event.set()
            return

        is_truncated = self._files_indexed >= self._max_files
        if not is_truncated:
            try:
                self._repair_pending_dir_aggregates()
            except Exception:
                LOG.exception("inventory repair of pending dir aggregates failed")
        self._status = "truncated" if is_truncated else "done"
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
            "inventory walker complete: status=%s files=%d entries=%d elapsed=%dms",
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
        if entry.type == "file" and (existing is None or existing.type != "file"):
            self._files_indexed += 1
        elif entry.type != "file" and existing is not None and existing.type == "file":
            self._files_indexed -= 1
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

    def apply_walker_entries(self, entries: list[FsEntry]) -> int:
        """Apply a batch of fresh observations and emit one
        ``fs.change`` covering every successful write.

        The active_tracker poll path produces N ops per tick (one per
        active file). Without batching, every op would fan out as its
        own ``fs.change`` through the ring buffer and every SSE
        subscriber — pushing slow consumers toward the queue-full
        drop path during normal operation. Returns the count of
        entries actually stored (stale captured tokens are dropped
        silently per the standard contract).
        """

        stored: list[FsEntry] = []
        for entry in entries:
            applied = self._store_walker_entry(entry)
            if applied is not None:
                stored.append(applied)
        if stored:
            self._emit(FsChange(ops=tuple(FsUpsert(entry=e) for e in stored)))
        return len(stored)

    def emit_event(self, event: StreamEvent) -> None:
        """Public emit hook for non-fs producers (e.g. the watcher
        emitting ``ProjectionInvalidate`` after a file modify). The
        inventory itself doesn't need to update its state — this
        just relays to subscribers via the same bus path
        ``_apply_walker_entry`` uses."""

        self._emit(event)

    def _emit(self, event: StreamEvent) -> None:
        """Push *event* to every subscriber without blocking.

        A full queue cannot preserve an ordered delta stream. Replace
        its stale backlog with a resync marker so the consumer repairs
        from an authoritative snapshot while memory stays bounded.

        Every ``fs.change`` also emits a minimal ``catalog.change``
        companion here, at the single choke point all producers
        share, so the Quick File catalog receives complete deltas on
        any stream scope (scope filtering only narrows ``fs.change``).
        """

        overflowed = 0
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                while True:
                    try:
                        q.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                resync = (
                    event
                    if isinstance(event, FsResyncRequired)
                    else FsResyncRequired(reason="subscriber_queue_overflow")
                )
                q.put_nowait(resync)
                overflowed += 1
        if overflowed:
            self._subscriber_overflows_since_log += overflowed
            now_ns = time.monotonic_ns()
            if (
                self._subscriber_overflow_last_log_ns == 0
                or now_ns - self._subscriber_overflow_last_log_ns
                >= _SUBSCRIBER_OVERFLOW_LOG_INTERVAL_NS
            ):
                LOG.warning(
                    "inventory subscriber backlog overflowed; requested resync for "
                    "%d subscriber(s)",
                    self._subscriber_overflows_since_log,
                )
                self._subscriber_overflows_since_log = 0
                self._subscriber_overflow_last_log_ns = now_ns
        if isinstance(event, FsChange):
            companion = _derive_catalog_change(event)
            if companion is not None:
                self._catalog_revision += 1
                self._emit(companion)


def _derive_catalog_change(change: FsChange) -> CatalogChange | None:
    """The minimal Quick File companion for one ``fs.change`` batch.

    Non-gitignored file upserts shrink to ``{p, e}``; a gitignored
    file upsert becomes a catalog remove so ignore-state flips
    converge; directory upserts are dropped (the catalog holds files
    only — the client removes a directory's descendants itself on a
    remove op). Returns ``None`` when nothing catalog-relevant
    remains so no empty event reaches the wire.
    """

    upserts: list[CatalogUpsert] = []
    removes: list[str] = []
    for op in change.ops:
        if isinstance(op, FsRemove):
            removes.append(op.path)
            continue
        entry = op.entry
        if entry.type != "file":
            continue
        if entry.gitignored:
            removes.append(entry.path)
        else:
            upserts.append(CatalogUpsert(p=entry.path, e=entry.ext))
    if not upserts and not removes:
        return None
    return CatalogChange(upserts=tuple(upserts), removes=tuple(removes))


# ── Process-wide singleton ──────────────────────────────────────


class _Singleton:
    """Module-level holder for the process-wide instance. Wrapping
    the slot in a class dodges basedpyright's constant-naming
    convention without making the slot itself look mutable at the
    module surface."""

    instance: InventoryIndex | None = None


def get_instance() -> InventoryIndex:
    """Lazy-initialize the process-wide ``InventoryIndex``.
    The lifespan hook is the only production caller that should invoke
    ``start()``; other callers read via ``get()``, ``entries()``, or
    ``subscribe()``.
    """

    if _Singleton.instance is None:
        _Singleton.instance = InventoryIndex()
    return _Singleton.instance


def reset_instance_for_tests() -> None:
    """Drop the module-level singleton. Tests use this to force a
    fresh instance per test; production code never calls it."""

    if _Singleton.instance is not None:
        _Singleton.instance.clear()
    _Singleton.instance = None


# Re-export the non-trivial helpers used by tests and inventory consumers.
__all__ = [
    "DEFAULT_MAX_DEPTH",
    "DEFAULT_MAX_FILES",
    "DEFAULT_REFRESH_TTL_S",
    "IndexStatus",
    "InventoryIndex",
    "get_instance",
    "reset_instance_for_tests",
    "walk_tree",
]
