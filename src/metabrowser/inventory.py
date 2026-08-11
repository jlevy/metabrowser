"""Process-wide inventory of filesystem state for the browser.

``InventoryIndex`` is the single source of truth for file/directory
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

* **BFS for queueing.** First-render-depth (``DEFAULT_FIRST_RENDER_DEPTH``)
  directories are scanned before deeper ones, so a request landing
  ~500 ms into boot finds the visible part of the tree already
  populated.
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
import time
from collections.abc import Collection, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Literal

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
from metabrowser.walker import (
    DEFAULT_FIRST_RENDER_DEPTH,
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

LOG = logging.getLogger(__name__)


IndexStatus = Literal["idle", "scanning", "done", "truncated", "failed"]


# ── InventoryIndex ──────────────────────────────────────────────


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
        first_render_depth: int = DEFAULT_FIRST_RENDER_DEPTH,
    ) -> None:
        self._root: Path | None = None
        self._entries: dict[str, FsEntry] = {}
        self._direct_child_counts: dict[str, int] = {}
        self._child_mtime_heaps: dict[str, list[tuple[int, str]]] = {}
        self._recorded_child_mtimes: dict[str, tuple[str, int]] = {}
        self._pending_dirs: set[str] = set()
        self._descendant_file_counts: dict[str, int] = {}
        self._descendant_file_sizes: dict[str, int] = {}
        self._walker_dir_generations: dict[str, int] = {}
        self._generation: dict[str, int] = {}
        self._subscribers: set[asyncio.Queue[StreamEvent]] = set()
        self._walker_task: asyncio.Task[None] | None = None
        self._done_event: asyncio.Event = asyncio.Event()
        self._status: IndexStatus = "idle"
        self._max_files = max_files
        self._max_depth = max_depth
        self._first_render_depth = first_render_depth
        self._files_indexed = 0
        self._started_at_ns: int = 0
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
        self._entries.clear()
        self._direct_child_counts.clear()
        self._child_mtime_heaps.clear()
        self._recorded_child_mtimes.clear()
        self._pending_dirs.clear()
        self._descendant_file_counts.clear()
        self._descendant_file_sizes.clear()
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

    def root_summary(self) -> dict[str, int]:
        """Whole-index file counts and bytes, split by gitignore status.

        The per-directory ``total_files`` / ``total_size`` aggregates
        are gitignore-blind, and they have to stay that way: a folder's
        size is its size. But the nav header wants to say how much of
        the tree is tracked versus ignored, and summing top-level
        children cannot answer that — ignored files nested under
        tracked directories would be counted as tracked.

        One pass over the entries is the honest way to get it. This runs
        per ``/api/tree`` request (once per page load, not per
        keystroke), so an O(entries) scan is affordable where a second
        set of incremental accumulators would not be worth the
        invalidation surface.
        """

        files = size = ignored_files = ignored_size = 0
        for entry in self._entries.values():
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

    def file_type_tallies(
        self,
        presets: Sequence[tuple[str, Collection[str]]],
        limit: int = 200,
    ) -> tuple[list[list[object]], list[list[object]]]:
        """Return extension and aggregate-preset rows in one index pass.

        Both shapes are ``[key, tracked_files, ignored_files]``. Dotted
        preset tokens match the indexed logical extension; other tokens
        match a complete filename case-insensitively. A file is counted
        at most once per preset.
        """

        extension_counts: dict[str, list[int]] = {}
        preset_counts = {preset_id: [0, 0] for preset_id, _values in presets}
        normalized_presets = [
            (
                preset_id,
                frozenset(value.lower() for value in values if value.startswith(".")),
                frozenset(value.lower() for value in values if not value.startswith(".")),
            )
            for preset_id, values in presets
        ]
        for entry in self._entries.values():
            if entry.type != "file":
                continue
            ignored_index = 1 if entry.gitignored else 0
            if entry.ext:
                row = extension_counts.get(entry.ext)
                if row is None:
                    row = [0, 0]
                    extension_counts[entry.ext] = row
                row[ignored_index] += 1

            name = entry.name.lower()
            ext = entry.ext.lower()
            for preset_id, extensions, names in normalized_presets:
                if ext in extensions or name in names:
                    preset_counts[preset_id][ignored_index] += 1

        ranked = sorted(
            extension_counts.items(),
            key=lambda item: (-(item[1][0] + item[1][1]), item[0]),
        )
        extension_rows: list[list[object]] = [
            [ext, counts[0], counts[1]] for ext, counts in ranked[:limit]
        ]
        preset_rows: list[list[object]] = [
            [preset_id, counts[0], counts[1]] for preset_id, counts in preset_counts.items()
        ]
        return extension_rows, preset_rows

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
        previous_subtree = self._entries.get(rel)
        if not rel:
            # The whole-root re-walk is what start() does; refuse to
            # avoid two walkers writing into the index simultaneously.
            return
        target = self._root / rel
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
        root_resolved = self._root.resolve()
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
        gi_check = await asyncio.to_thread(_build_gitignore_check_for, self._root)
        async for entry in walk_tree(
            target_resolved,
            max_depth=self._max_depth,
            max_files=self._max_files,
            first_render_depth=self._first_render_depth,
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
            if previous_subtree is not None:
                if previous_subtree.type == "file":
                    previous_files = 1
                    previous_size = previous_subtree.size
                else:
                    previous_files = previous_subtree.total_files or 0
                    previous_size = previous_subtree.total_size or 0
            current_files = current_subtree.total_files or 0
            current_size = current_subtree.total_size or 0
            aggregate_updates = self._update_ancestor_aggregates(
                parent=current_subtree.parent,
                delta_files=current_files - previous_files,
                delta_size=current_size - previous_size,
            )
            if aggregate_updates:
                self._emit(FsChange(ops=tuple(FsUpsert(entry=e) for e in aggregate_updates)))

    def remove(self, path: str) -> None:
        """Remove *path* and every descendant from the index. Emits
        one ``FsChange`` event whose ops cover every removed path so
        subscribers can drop the corresponding rows in a single
        batch. Idempotent: removing a path that isn't in the index
        is a no-op.

        For files this drops one entry. For directories it walks
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
        if target.type == "file":
            removed = [path]
        else:
            prefix = path + "/"
            removed = [
                cur for cur in list(self._entries.keys()) if cur == path or cur.startswith(prefix)
            ]
        removed_entries = [self._entries[cur] for cur in removed]
        removed_files = [entry for entry in removed_entries if entry.type == "file"]
        outer_parent = target.parent
        for cur in removed:
            entry = self._entries.pop(cur, None)
            if entry is not None:
                if entry.type == "file":
                    self._files_indexed -= 1
                    self._adjust_descendant_file_aggregates(
                        parent=entry.parent,
                        delta_files=-1,
                        delta_size=-entry.size,
                    )
                else:
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
        )
        ops: list[FsChangeOp] = [FsRemove(path=cur) for cur in removed]
        ops.extend(FsUpsert(entry=entry) for entry in aggregate_updates)
        self._emit(FsChange(ops=tuple(ops)))

    # ── Subscriptions ───────────────────────────────────────

    def subscribe(self, *, max_queue: int = 1024) -> asyncio.Queue[StreamEvent]:
        """Register a per-connection queue and return it. The route
        layer calls ``Queue.get()`` to pull events into the SSE
        stream.

        Slow consumers are bounded: when the queue fills, the
        connection is dropped (``unsubscribe`` is called and the
        SSE handler closes the response). EventSource auto-reconnect
        then drives a fresh scoped snapshot. We never emit
        ``fs.resync_required`` for slow consumers — that event is
        reserved for server restart / root swap.
        """

        q: asyncio.Queue[StreamEvent] = asyncio.Queue(maxsize=max_queue)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[StreamEvent]) -> None:
        self._subscribers.discard(q)

    def is_subscribed(self, q: asyncio.Queue[StreamEvent]) -> bool:
        """True iff *q* is currently in the subscriber set. Becomes
        False after ``_emit`` drops a slow consumer; the bus relay
        polls this so it can resubscribe instead of waiting forever
        on a dead queue."""
        return q in self._subscribers

    def subscriber_count(self) -> int:
        return len(self._subscribers)

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
        gi_check = await asyncio.to_thread(_build_gitignore_check_for, root)
        try:
            async for entry in walk_tree(
                root,
                max_depth=self._max_depth,
                max_files=self._max_files,
                first_render_depth=self._first_render_depth,
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
                newest_mtime_ns=newest_mtime,
                mtime_ns=newest_mtime,
                write_token=WriteToken(self._generation.get(path, 0)),
            )
            self._entries[path] = repaired
            self._pending_dirs.discard(path)
            self._record_child_mtime(repaired)
            repaired_count += 1
            batch.append(repaired)
            if len(batch) >= WALKER_EMIT_BATCH:
                self._emit(FsChange(ops=tuple(FsUpsert(entry=e) for e in batch)))
                batch.clear()
        if batch:
            self._emit(FsChange(ops=tuple(FsUpsert(entry=e) for e in batch)))
        LOG.info("inventory repaired %d pending dir aggregate(s)", repaired_count)

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
            # write and let the next observer pass refresh. A
            # sustained stream of dropped writes points at a producer
            # that's holding stale tokens — surface at WARNING.
            LOG.warning(
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
        if existing is None:
            self._add_direct_child(entry)
        elif existing.parent != entry.parent:
            self._remove_direct_child(existing)
            self._add_direct_child(entry)
        self._entries[entry.path] = entry
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
                updated = replace(
                    existing,
                    total_files=max(0, existing.total_files + delta_files),
                    total_size=max(0, existing.total_size + delta_size),
                    newest_mtime_ns=newest_mtime_ns,
                    write_token=WriteToken(self._generation.get(cursor, 0)),
                )
                self._entries[cursor] = updated
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
        """Push *event* to every subscriber. Slow consumers are
        dropped — full queue means we close that connection rather
        than block the producer.

        Every ``fs.change`` also emits a minimal ``catalog.change``
        companion here, at the single choke point all producers
        share, so the Quick File catalog receives complete deltas on
        any stream scope (scope filtering only narrows ``fs.change``).
        """

        dead: list[asyncio.Queue[StreamEvent]] = []
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._subscribers.discard(q)
            LOG.warning("dropped slow subscriber; queue full at %d", q.maxsize)
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
    "DEFAULT_FIRST_RENDER_DEPTH",
    "DEFAULT_MAX_DEPTH",
    "DEFAULT_MAX_FILES",
    "DEFAULT_REFRESH_TTL_S",
    "IndexStatus",
    "InventoryIndex",
    "get_instance",
    "reset_instance_for_tests",
    "walk_tree",
]
