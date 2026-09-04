"""Filesystem walker for the browser inventory.

Single home for the BFS scanner used by the Python provider's discovery and subtree
refresh paths. It emits provider-neutral observations, so tests can drive ``walk_tree``
directly with ``async for`` without constructing a retained index.

Walker semantics (verified by tests in
``metabrowser/tests/test_browser_inventory.py``):

* **Strict level-order BFS.** Every directory at depth N is scanned
  before any at depth N+1, so the layers the nav tree shows — and the
  ones a reader expands first — are complete long before the deep
  tail, and a request landing early in the boot scan finds them
  already populated.
* **Post-order finalize.** A directory's ``InventoryEntry`` is replaced with
  populated ``total_files`` / ``total_size`` / ``newest_mtime_ns``
  only after every descendant has been walked.
* **Safety caps.** ``max_files`` truncates the scan; the walker still
  finalizes the partial subtree it did walk so ``status=truncated``
  exposes usable aggregates instead of nulls.
* **Visibility + extension** go through
  :mod:`metabrowser.fs_paths` so the walker and the watcher cannot
  diverge on either rule.
"""

from __future__ import annotations

import asyncio
import logging
import os
import stat as stat_module
from collections import deque
from collections.abc import AsyncIterator, Callable, Collection
from dataclasses import replace
from pathlib import Path
from threading import Event

from metabrowser.fs_paths import is_visible
from metabrowser.inventory_engine.contract import InventoryEntry
from metabrowser.settings import (
    INVENTORY_MAX_DEPTH,
    INVENTORY_MAX_FILES,
    INVENTORY_REFRESH_TTL_S,
    INVENTORY_WALKER_EMIT_BATCH,
)
from metabrowser.tree import build_gitignore_check

LOG = logging.getLogger(__name__)

# Re-export the walker tunables. Authoritative defaults live in
# :mod:`metabrowser.settings`; these names exist so callers
# (the Python provider and tests) can reference them without reaching into
# settings directly.
DEFAULT_MAX_DEPTH = INVENTORY_MAX_DEPTH
DEFAULT_MAX_FILES = INVENTORY_MAX_FILES
DEFAULT_REFRESH_TTL_S = INVENTORY_REFRESH_TTL_S
WALKER_EMIT_BATCH = INVENTORY_WALKER_EMIT_BATCH


# ── Path conventions ────────────────────────────────────────────


def rel_path(root: Path, abs_path: Path) -> str:
    """Convert *abs_path* to a forward-slash relative path from
    *root*. The served root itself maps to ``""``. Subpaths use
    POSIX separators on every platform; the wire format is the
    same on Linux, macOS, and Windows so the client can treat path
    strings as opaque ids without OS-specific normalization."""

    try:
        rel = abs_path.relative_to(root)
    except ValueError:
        # Walker should never pass a path outside *root*; the
        # defensive fallback keeps a stray path from killing the
        # walker and stranding the index in "scanning" forever.
        return abs_path.as_posix()
    return "" if str(rel) == "." else rel.as_posix()


def depth_of(rel: str) -> int:
    """Depth of *rel* under the served root. ``""`` is depth 0;
    ``"a"`` is depth 1; ``"a/b"`` is depth 2."""

    if not rel:
        return 0
    return rel.count("/") + 1


# ── Gitignore checker setup ─────────────────────────────────────


def build_gitignore_check_for(
    root: Path,
    *,
    cancel_event: Event | None = None,
) -> Callable[[Path, bool], bool] | None:
    """Build the gitignore checker the walker uses to populate
    ``InventoryEntry.gitignored``. Returns ``None`` when the served root
    isn't inside a git repo (no patterns to match), so the walker
    skips the per-entry call.
    """

    try:
        checker, git_root = build_gitignore_check(root, cancel_event=cancel_event)
    except Exception:
        LOG.exception("walker: failed to build gitignore check for %s", root)
        return None
    if git_root is None:
        return None
    return checker


# ── Internal scandir ────────────────────────────────────────────


class _ScanItem:
    """A single visible entry from one directory's scan. Carries
    ``size`` / ``mtime_ns`` for leaf entries (from ``DirEntry.stat``) so
    the walker doesn't re-stat. For dirs, only ``name`` / ``abs_path``
    / ``is_dir`` matter; size/mtime are populated via the
    aggregate-rollup path."""

    __slots__ = ("abs_path", "is_dir", "is_symlink", "mtime_ns", "name", "size")

    def __init__(
        self,
        name: str,
        abs_path: Path,
        is_dir: bool,
        is_symlink: bool,
        size: int,
        mtime_ns: int,
    ) -> None:
        self.name = name
        self.abs_path = abs_path
        self.is_dir = is_dir
        self.is_symlink = is_symlink
        self.size = size
        self.mtime_ns = mtime_ns


def _scandir_visible(
    dirpath: Path,
    hidden_allowlist: Collection[str] | None = None,
) -> list[_ScanItem]:
    """One ``os.scandir`` call, filtered to visible names, with
    one stat per file. Symlinks are not followed.

    This is the only place the walker touches the filesystem.
    Everything else in this module reads in-memory state.
    """
    items: list[_ScanItem] = []
    try:
        with os.scandir(dirpath) as it:
            for raw in it:
                if not is_visible(raw.name, hidden_allowlist):
                    continue
                try:
                    raw_is_symlink = raw.is_symlink()
                    raw_is_dir = raw.is_dir(follow_symlinks=False)
                except OSError:
                    continue
                if raw_is_dir:
                    items.append(
                        _ScanItem(
                            name=raw.name,
                            abs_path=Path(raw.path),
                            is_dir=True,
                            is_symlink=False,
                            size=0,
                            mtime_ns=0,
                        )
                    )
                else:
                    try:
                        st = raw.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    if not raw_is_symlink and not stat_module.S_ISREG(st.st_mode):
                        # The browser wire has no special-object kind. Exclude
                        # sockets, FIFOs, and devices instead of misrepresenting
                        # them as files.
                        continue
                    items.append(
                        _ScanItem(
                            name=raw.name,
                            abs_path=Path(raw.path),
                            is_dir=False,
                            is_symlink=raw_is_symlink,
                            size=st.st_size,
                            mtime_ns=st.st_mtime_ns,
                        )
                    )
    except PermissionError as exc:
        # Broad roots commonly contain OS-protected directories. Skipping one
        # is expected and already visible as a missing subtree in the browser.
        LOG.debug("walker: permission denied at %s: %s", dirpath, exc)
    except (FileNotFoundError, NotADirectoryError) as exc:
        # Watchers can invalidate a directory while the boot walk reaches it.
        LOG.debug("walker: directory disappeared at %s: %s", dirpath, exc)
    except OSError as exc:
        # Other scandir failures can indicate storage or filesystem trouble.
        LOG.warning("walker: scandir failed at %s: %s", dirpath, exc)
    # Dirs first, then by name — matches the existing tree.py
    # convention so /api/tree responses stay stable.
    items.sort(key=lambda it: (not it.is_dir, it.name))
    return items


# ── Walker ──────────────────────────────────────────────────────


async def walk_tree(
    root: Path,
    *,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_files: int = DEFAULT_MAX_FILES,
    gitignore_check: Callable[[Path, bool], bool] | None = None,
    hidden_allowlist: Collection[str] | None = None,
) -> AsyncIterator[InventoryEntry]:
    """BFS the filesystem rooted at *root*; yield ``InventoryEntry``
    records as the tree is discovered and as directories finalize.

    Yield order:

    1. Root placeholder dir entry (``total_*=None``).
    2. For each BFS-visited dir, per immediate child:
       * file: a single yield with concrete ``size`` /
         ``mtime_ns``.
       * dir: a placeholder yield (``total_*=None``); the dir is
         then enqueued for its own BFS scan.
    3. As BFS sweeps deeper, terminal dirs finalize and yield
       their aggregate-populated form. Aggregates propagate up
       the parent chain; the root yields its finalized form last.

    The queue is strict FIFO, so discovery runs in level order and
    shallow directories always finalize before deeper ones.

    *gitignore_check* is the same callable produced by
    ``tree.build_gitignore_check`` — when provided, the walker sets
    ``InventoryEntry.gitignored`` on every yielded entry (file and dir) so
    the response layer reads the flag straight off the index instead
    of re-deriving on every request. Callers that don't have a
    checker handy (tests, file-system scopes outside a git repo)
    pass None and entries land with ``gitignored=False``.

    Tests drive this with ``async for entry in walk_tree(...): ...``
    and can interrupt by breaking out of the loop. The generator
    cleans up on close.
    """

    if max_depth <= 0 or max_files <= 0:
        return

    def _gi(abs_path: Path, is_dir: bool) -> bool:
        if gitignore_check is None:
            return False
        try:
            return bool(gitignore_check(abs_path, is_dir))
        except Exception:
            return False

    # Track "this rel_path's ancestor chain has a gitignored dir."
    # Children of a gitignored dir inherit the flag without re-running
    # the pathspec match — at 500k files with a 3k-pattern .gitignore,
    # the per-entry call dominates walker time. Inheritance means we
    # only call _gi for paths whose ancestors aren't already ignored,
    # which collapses the cost back to the un-ignored frontier.
    gitignored_dir: dict[str, bool] = {}

    files_indexed = 0
    truncated = False

    # Per-dir bookkeeping for post-order finalize.
    # ``pending`` counts subdirs yet to finalize; when it hits 0 the
    # dir is ready to emit aggregates.
    pending: dict[str, int] = {}
    parent_of: dict[str, str] = {}
    # Per-dir running aggregates. Files contribute (1, size, mtime_ns)
    # at scan time; subdirs contribute their finalized totals when
    # they themselves finalize.
    accum_files: dict[str, int] = {}
    accum_size: dict[str, int] = {}
    accum_unignored_files: dict[str, int] = {}
    accum_unignored_size: dict[str, int] = {}
    accum_newest: dict[str, int] = {}
    # Placeholder entries we'll need to replace at finalize-time.
    placeholders: dict[str, InventoryEntry] = {}

    # BFS queue: (abs_path, rel_path, depth)
    queue: deque[tuple[Path, str, int]] = deque()

    # Seed the root.
    root_rel = ""
    pending[root_rel] = 0
    parent_of[root_rel] = ""
    accum_files[root_rel] = 0
    accum_size[root_rel] = 0
    accum_unignored_files[root_rel] = 0
    accum_unignored_size[root_rel] = 0
    accum_newest[root_rel] = 0

    root_gitignored = _gi(root, True)
    gitignored_dir[root_rel] = root_gitignored
    root_entry = InventoryEntry.for_observed_dir(
        path=root_rel,
        parent="",
        name=root.name,
        gitignored=root_gitignored,
    )
    placeholders[root_rel] = root_entry
    yield root_entry
    queue.append((root, root_rel, 0))

    def _maybe_finalize(rel: str) -> list[InventoryEntry]:
        """Walk up from *rel* finalizing every dir whose
        ``pending`` counter has reached 0. Each finalize bumps the
        parent's accumulators and decrements the parent's pending
        counter; cascade until we hit a dir that still has
        children outstanding (or until we finalize the root).

        Returns the chain of finalized entries in finalize order
        (deepest first; root last). The caller yields them.
        """
        finalized: list[InventoryEntry] = []
        cursor = rel
        while cursor in pending and pending[cursor] == 0:
            ph = placeholders.get(cursor)
            if ph is None:
                # Should never happen — placeholder is set before
                # the dir is scanned. Defensive bail-out.
                break
            tf = accum_files[cursor]
            ts = accum_size[cursor]
            uf = accum_unignored_files[cursor]
            us = accum_unignored_size[cursor]
            nm = accum_newest[cursor]
            final = replace(
                ph,
                total_files=tf,
                total_size=ts,
                unignored_files=uf,
                unignored_size=us,
                newest_mtime_ns=nm,
                mtime_ns=nm,
            )
            finalized.append(final)

            # Propagate up.
            del pending[cursor]
            placeholders.pop(cursor, None)
            parent = parent_of.get(cursor, "")
            if cursor == "" or parent == cursor:
                # We just finalized root; stop walking.
                break
            accum_files[parent] = accum_files.get(parent, 0) + tf
            accum_size[parent] = accum_size.get(parent, 0) + ts
            accum_unignored_files[parent] = accum_unignored_files.get(parent, 0) + uf
            accum_unignored_size[parent] = accum_unignored_size.get(parent, 0) + us
            if nm > accum_newest.get(parent, 0):
                accum_newest[parent] = nm
            pending[parent] = pending.get(parent, 0) - 1
            cursor = parent
        return finalized

    while queue:
        if truncated:
            # Cap reached. Force-finalize every scanned dir with its
            # current accumulators, deepest-first so cascades reach
            # root. Partially-walked subtrees thus show usable totals
            # instead of null skeletons. Dirs queued but never
            # scanned stay as placeholders; the SPA will lazy-fetch
            # them on expand.
            for finalize_rel in sorted(pending, key=lambda p: (-p.count("/"), p)):
                if finalize_rel not in pending:
                    continue  # already finalized via cascade
                pending[finalize_rel] = 0
                chain = _maybe_finalize(finalize_rel)
                for entry in chain:
                    yield entry
            queue.clear()
            break

        abs_path, rel_path_cur, depth = queue.popleft()

        if depth >= max_depth:
            # Treat at-depth dirs as terminal — record 0 children
            # so the post-order finalize can complete the parent
            # chain without waiting forever.
            chain = _maybe_finalize(rel_path_cur)
            for entry in chain:
                yield entry
            continue

        # Read directory in a worker thread; blocking call.
        try:
            child_entries = await asyncio.to_thread(
                _scandir_visible,
                abs_path,
                hidden_allowlist,
            )
        except OSError as exc:
            LOG.debug("walk_tree scandir failed for %s: %s", abs_path, exc)
            child_entries = []

        # Count subdirs first so ``pending`` is set before we yield
        # any subdir placeholders (otherwise a tight cap could let
        # the parent finalize before its subdirs are queued).
        subdir_count = sum(1 for ce in child_entries if ce.is_dir)
        pending[rel_path_cur] = subdir_count

        for ce in child_entries:
            if files_indexed >= max_files:
                truncated = True
                break

            child_rel = f"{rel_path_cur}/{ce.name}" if rel_path_cur else ce.name

            parent_ignored = gitignored_dir.get(rel_path_cur, False)
            if ce.is_dir:
                # Inherit from parent: every dir under a gitignored
                # parent is gitignored without a per-entry pathspec
                # match. Only un-ignored subtrees pay the per-entry
                # cost — collapses walker time on a typical repo
                # (where most of the file count sits in
                # node_modules / __pycache__ / runs / etc.).
                child_gi = parent_ignored or _gi(ce.abs_path, True)
                gitignored_dir[child_rel] = child_gi
                placeholder = InventoryEntry.for_observed_dir(
                    path=child_rel,
                    parent=rel_path_cur,
                    name=ce.name,
                    gitignored=child_gi,
                )
                placeholders[child_rel] = placeholder
                parent_of[child_rel] = rel_path_cur
                accum_files[child_rel] = 0
                accum_size[child_rel] = 0
                accum_unignored_files[child_rel] = 0
                accum_unignored_size[child_rel] = 0
                accum_newest[child_rel] = 0
                yield placeholder
                # Strict FIFO, so the queue drains in level order: every
                # directory at depth N is scanned before any at depth N+1.
                # Pushing shallow directories to the front instead would make
                # this band depth-first — the walker would follow one level-1
                # directory all the way down before looking at its siblings,
                # leaving the rest of the first level (the part the nav tree
                # shows, and the part a reader expands first) unscanned for
                # most of the crawl.
                queue.append((ce.abs_path, child_rel, depth + 1))
            elif ce.is_symlink:
                link_gi = parent_ignored or _gi(ce.abs_path, False)
                yield InventoryEntry.for_observed_symlink(
                    path=child_rel,
                    parent=rel_path_cur,
                    name=ce.name,
                    size=ce.size,
                    mtime_ns=ce.mtime_ns,
                    gitignored=link_gi,
                )
            else:
                files_indexed += 1
                # Files inherit gitignored from parent the same way dirs do.
                file_gi = parent_ignored or _gi(ce.abs_path, False)
                file_entry = InventoryEntry.for_observed_file(
                    path=child_rel,
                    parent=rel_path_cur,
                    name=ce.name,
                    size=ce.size,
                    mtime_ns=ce.mtime_ns,
                    gitignored=file_gi,
                )
                yield file_entry
                accum_files[rel_path_cur] = accum_files.get(rel_path_cur, 0) + 1
                accum_size[rel_path_cur] = accum_size.get(rel_path_cur, 0) + ce.size
                if not file_gi:
                    accum_unignored_files[rel_path_cur] = (
                        accum_unignored_files.get(rel_path_cur, 0) + 1
                    )
                    accum_unignored_size[rel_path_cur] = (
                        accum_unignored_size.get(rel_path_cur, 0) + ce.size
                    )
                if ce.mtime_ns > accum_newest.get(rel_path_cur, 0):
                    accum_newest[rel_path_cur] = ce.mtime_ns

        if truncated:
            # Mark the rest of the tree as "no more children
            # coming" so post-order finalize can flush.
            pending[rel_path_cur] = 0

        # If this dir had no subdirs (or hit truncation), finalize
        # the chain now.
        if pending.get(rel_path_cur, 0) == 0:
            chain = _maybe_finalize(rel_path_cur)
            for entry in chain:
                yield entry


__all__ = [
    "DEFAULT_MAX_DEPTH",
    "DEFAULT_MAX_FILES",
    "DEFAULT_REFRESH_TTL_S",
    "WALKER_EMIT_BATCH",
    "build_gitignore_check_for",
    "depth_of",
    "rel_path",
    "walk_tree",
]
