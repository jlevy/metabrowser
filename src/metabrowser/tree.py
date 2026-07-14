"""Directory tree walker for the browser left pane.

Owns ``_dir_tree`` and the cluster of helpers that decide what to show
in the file tree (gitignore propagation, sentinel summaries for the
lazy-load boundary, emptiness flagging). All filesystem walks here use
``os.scandir`` rather than ``Path.iterdir`` + per-entry ``stat()``:
``DirEntry`` carries the dirent's d_type and a cached ``stat_result``,
which roughly halves the syscall count on big trees.

The module also owns the per-root ``.gitignore`` checker cache. Building
the checker walks every ``.gitignore`` in the enclosing git repo
(~hundreds of milliseconds on a large repo), so we cache it with a 30 s
TTL — a ``.gitignore`` edit becomes visible without a server restart but
the steady-state cost of repeated tree fetches stays at zero.
"""

from __future__ import annotations

import contextlib
import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from cachetools import TTLCache
from cachetools.func import ttl_cache
from funlog import log_calls

from metabrowser.fs_paths import is_visible as _is_visible
from metabrowser.gz_io import GZIP_SUFFIX, ArtifactPath
from metabrowser.ignore_filter import IgnoreMode, ignore_none, make_ignore_filter
from metabrowser.paths_safe import _rel_path, register_root_callback

LOG = logging.getLogger(__name__)

# ── Tunables ─────────────────────────────────────────────────────

DEFAULT_TREE_DEPTH = 2
MAX_TREE_DEPTH = 20
SENTINEL_SUMMARY_DEPTH = 3
# Sentinel-walk caches: each per-request walk on a large tree
# (e.g. ``runs/local/example-workload``, 290 top-level dirs)
# generates ~3k unique sentinel calls per cache. ``maxsize`` was
# previously 1024 — smaller than the working set, so entries got
# evicted before they could be hit. 16k covers comfortably larger
# trees at ~1.6 MB total cost across the three caches.
#
# ``ttl`` was previously 5 s, mirroring the activity-poll cadence,
# but human browsing patterns (read a file, think, click another)
# routinely exceed 5 s, so a TTL that short turned every "next click"
# into a fresh full scan. The cached values here are *aggregate*
# subtree metrics (total_files, total_size, newest_mtime); minute-
# scale staleness is fine — the activity poll handles the live
# indicator separately, and ``register_root_callback`` invalidates
# everything when the served root changes. 60 s keeps steady-state
# tree fetches near-free without making changes feel stale.
_SENTINEL_CACHE_MAXSIZE = 16384
_SENTINEL_CACHE_TTL = 60.0


# ── Caches ──────────────────────────────────────────────────────

# Cache of (checker, git_root) keyed by the served root. ``make_ignore_filter``
# walks every ``.gitignore`` in the entire git repo (~1.5 s on this codebase);
# the TTL keeps edits visible without forcing a restart, but needs to be long
# enough that idle expand interactions don't repeatedly pay the rebuild cost.
_IGNORE_CACHE = TTLCache[str, tuple[Any, Path | None]](maxsize=64, ttl=300.0)


# Folder-marker basenames declared by any loaded plugin's ``folder_marker``
# match rule. A directory whose direct children include any of these names
# gets a ``marker_basename`` field on its tree-row payload (one entry, picked
# stably when multiple markers coexist). Server startup calls
# ``set_folder_markers`` once after plugin discovery completes; tests can
# call it directly to inject markers into ``_dir_tree``.
_FOLDER_MARKERS: set[str] = set()


def set_folder_markers(markers: set[str]) -> None:
    """Replace the in-memory set of known folder markers. Idempotent; intended
    to be called once at server startup from
    ``metabrowser.plugin_loader.classify.collect_folder_markers``."""
    _FOLDER_MARKERS.clear()
    _FOLDER_MARKERS.update(markers)


def _marker_in_children(child_names: list[str]) -> str | None:
    """Return the first known folder marker present in *child_names*, or None.

    Picked by sorted name order so the choice is stable across runs even
    when two markers coexist in the same directory (rare; the spec calls
    this out as a collision case).
    """
    if not _FOLDER_MARKERS:
        return None
    for name in sorted(child_names):
        if name in _FOLDER_MARKERS:
            return name
    return None


def _scan_marker_basename(dirpath: Path) -> str | None:
    """Scan *dirpath* once for a known folder marker; return the matched basename.

    Used by the lazy-load sentinel branch in :func:`_dir_tree`, which never
    materializes its children. One ``os.scandir`` pass; bails out on the first
    match.
    """
    if not _FOLDER_MARKERS:
        return None
    try:
        with os.scandir(dirpath) as it:
            for entry in it:
                if entry.name in _FOLDER_MARKERS:
                    return entry.name
    except (PermissionError, OSError, FileNotFoundError, NotADirectoryError):
        return None
    return None


def _invalidate_caches() -> None:
    _IGNORE_CACHE.clear()
    _subtree_summary.cache_clear()
    _has_any_file.cache_clear()
    _has_any_nongitignored.cache_clear()


register_root_callback(_invalidate_caches)


# ── Git root + gitignore lookup ─────────────────────────────────


def _find_git_root(start: Path) -> Path | None:
    """Walk up from *start* looking for a ``.git`` marker; return the first hit."""
    try:
        cur = start.resolve()
    except OSError:
        return None
    for candidate in (cur, *cur.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


@log_calls(level="info", show_timing_only=True, if_slower_than=0.05)
def build_gitignore_check(root: Path) -> tuple[Any, Path | None]:
    """Return ``(check, git_root)`` where ``check(abs_path, is_dir) -> bool``.

    Looks for the enclosing git repo so that patterns in ``.gitignore`` files
    above ``root`` apply correctly. Paths are converted to git-root-relative
    strings before matching. Cached across requests.
    """
    key = str(root)
    cached = _IGNORE_CACHE.get(key)
    if cached is not None:
        return cached

    git_root = _find_git_root(root)
    base = make_ignore_filter(git_root, IgnoreMode.gitignore) if git_root else ignore_none
    if base is ignore_none or git_root is None:
        checker: Any = lambda abs_path, is_dir=False: False
    else:
        git_root_str = str(git_root)
        prefix_len = len(git_root_str) + 1

        def _check(abs_path: Path | str, is_dir: bool = False) -> bool:
            s = abs_path if isinstance(abs_path, str) else str(abs_path)
            if not s.startswith(git_root_str):
                return False
            rel = s[prefix_len:] if len(s) > prefix_len else ""
            return base(rel, is_dir=is_dir)

        checker = _check

    entry = (checker, git_root)
    _IGNORE_CACHE[key] = entry
    return entry


# ── Subtree aggregation ─────────────────────────────────────────


def _dir_stats(children: list[dict[str, Any]]) -> tuple[int, int, float]:
    """Compute total files, total size, and newest mtime from a tree's children."""
    total_files = 0
    total_size = 0
    newest_mtime = 0.0
    for child in children:
        if child["type"] == "dir":
            total_files += child.get("total_files", 0)
            total_size += child.get("total_size", 0)
            child_mtime = child.get("mtime", 0)
            newest_mtime = max(newest_mtime, child_mtime)
        else:
            total_files += 1
            total_size += child.get("size", 0)
            child_mtime = child.get("mtime", 0)
            newest_mtime = max(newest_mtime, child_mtime)
    return total_files, total_size, newest_mtime


def _subtree_is_empty(children: list[dict[str, Any]]) -> bool:
    """True iff *children* describe a subtree with no files anywhere.

    Uses the per-child ``empty`` flag so this works even when children are
    lazy-load sentinels (whose ``total_files`` is always 0 as a placeholder).
    """
    for c in children:
        if c["type"] == "file":
            return False
        if c["type"] == "dir" and not c.get("empty", False):
            return False
    return True


def _subtree_is_all_gitignored(children: list[dict[str, Any]]) -> bool:
    """True iff *children* is non-empty and every entry is gitignored."""
    if not children:
        return False
    return all(c.get("gitignored", False) for c in children)


# ── Sentinel summary walks (scandir-based) ──────────────────────


@ttl_cache(maxsize=_SENTINEL_CACHE_MAXSIZE, ttl=_SENTINEL_CACHE_TTL)
def _subtree_summary(dirpath: Path, max_depth: int = 20) -> tuple[int, int, float]:
    """Return ``(total_files, total_size, newest_mtime)`` for ``dirpath``.

    Single ``scandir`` walk that grabs size + mtime + d_type from one
    syscall per entry. Called only on the lazy-load boundary; cached
    for 5 s so repeat requests (page reload, multi-tab, expanding a
    sentinel moments after the root walk) don't redo the walk.
    """
    if max_depth <= 0:
        return 0, 0, 0.0
    return _scandir_subtree_summary(dirpath, max_depth)


def _scandir_subtree_summary(dirpath: Path, max_depth: int) -> tuple[int, int, float]:
    total_files = 0
    total_size = 0
    newest = 0.0
    try:
        with os.scandir(dirpath) as it:
            for entry in it:
                if not _is_visible(entry.name):
                    continue
                try:
                    if entry.is_dir(follow_symlinks=False):
                        sub_files, sub_size, sub_mtime = _scandir_subtree_summary(
                            Path(entry.path), max_depth - 1
                        )
                        total_files += sub_files
                        total_size += sub_size
                        if sub_mtime > newest:
                            newest = sub_mtime
                    else:
                        st = entry.stat(follow_symlinks=False)
                        total_files += 1
                        total_size += st.st_size
                        if st.st_mtime > newest:
                            newest = st.st_mtime
                except OSError:
                    continue
    except (PermissionError, OSError, FileNotFoundError, NotADirectoryError):
        return total_files, total_size, newest
    return total_files, total_size, newest


@ttl_cache(maxsize=_SENTINEL_CACHE_MAXSIZE, ttl=_SENTINEL_CACHE_TTL)
def _has_any_nongitignored(
    dirpath: Path,
    ignore_check: Callable[..., bool],
    max_depth: int = 20,
) -> bool:
    """True iff any non-gitignored visible content exists under ``dirpath``.

    Sentinel counterpart to :func:`_subtree_is_all_gitignored`: when the
    lazy boundary hides the children, we still want to flag the dir as
    gitignored if everything under it is. Files inherit their parent
    dir's ignore status and are not individually pattern-checked, so a
    gitignored dir's whole subtree is treated as gitignored without
    recursion, and any direct file in a non-gitignored dir counts as
    "real content". Early-exits.
    """
    if max_depth <= 0:
        return False
    try:
        with os.scandir(dirpath) as it:
            for entry in it:
                if not _is_visible(entry.name):
                    continue
                try:
                    if entry.is_dir(follow_symlinks=False):
                        if ignore_check(entry.path, is_dir=True):
                            continue
                        if _has_any_nongitignored(Path(entry.path), ignore_check, max_depth - 1):
                            return True
                    else:
                        return True
                except OSError:
                    continue
    except (PermissionError, OSError, FileNotFoundError, NotADirectoryError):
        return False
    return False


@ttl_cache(maxsize=_SENTINEL_CACHE_MAXSIZE, ttl=_SENTINEL_CACHE_TTL)
def _has_any_file(dirpath: Path, max_depth: int = 20) -> bool:
    """True iff any visible file exists anywhere under ``dirpath``."""
    if max_depth <= 0:
        return False
    try:
        with os.scandir(dirpath) as it:
            for entry in it:
                if not _is_visible(entry.name):
                    continue
                try:
                    if entry.is_file(follow_symlinks=False):
                        return True
                    if entry.is_dir(follow_symlinks=False) and _has_any_file(
                        Path(entry.path), max_depth - 1
                    ):
                        return True
                except OSError:
                    continue
    except (PermissionError, OSError, FileNotFoundError, NotADirectoryError):
        return False
    return False


def _has_visible_children(dirpath: Path) -> bool:
    """Return True if a directory has any visible children (non-dot or .logs/.state)."""
    try:
        with os.scandir(dirpath) as it:
            for entry in it:
                if _is_visible(entry.name):
                    return True
    except (PermissionError, OSError):
        pass
    return False


# ── Main tree walk ──────────────────────────────────────────────


def _dir_tree(
    dirpath: Path,
    max_depth: int = 20,
    *,
    remaining_depth: int | None = None,
    ignore_check: Callable[..., bool] | None = None,
    parent_ignored: bool = False,
) -> list[dict[str, Any]]:
    """Build a directory tree as a JSON-serializable list.

    When *remaining_depth* is provided (not None), directories at depth 0
    emit ``children: null`` with ``has_children: true`` instead of recursing.
    This enables lazy subtree loading on the client.

    Uses ``os.scandir`` and reuses ``DirEntry.stat()`` so each entry costs
    at most one stat syscall (vs three with ``Path.iterdir`` + ``is_dir`` +
    ``stat`` separately).
    """
    if ignore_check is None:
        ignore_check = lambda p, is_dir=False: False
    if max_depth <= 0:
        return []

    # Snapshot the dir contents (with cached stat from scandir's dirent).
    try:
        raw_entries: list[tuple[os.DirEntry[str], bool]] = []
        with os.scandir(dirpath) as it:
            for entry in it:
                if not _is_visible(entry.name):
                    continue
                try:
                    is_dir = entry.is_dir(follow_symlinks=False)
                except OSError:
                    continue
                raw_entries.append((entry, is_dir))
    except (PermissionError, OSError, FileNotFoundError, NotADirectoryError):
        return []

    # Sort: dirs first, then by name. Same convention as the previous
    # ``Path.iterdir + sorted`` pipeline.
    raw_entries.sort(key=lambda pair: (not pair[1], pair[0].name))

    entries: list[dict[str, Any]] = []
    for entry, is_dir in raw_entries:
        item_path = Path(entry.path)
        rel = _rel_path(entry.path)

        # Files inherit parent_ignored without per-file pattern check —
        # checking every file costs ~11s on a 55k-file tree. The edge case
        # we skip (a file matching e.g. ``*.pyc`` whose parent dir is NOT
        # ignored) is rare.
        if is_dir:
            ignored = parent_ignored or ignore_check(entry.path, is_dir=True)
        else:
            ignored = parent_ignored

        if is_dir:
            if remaining_depth is not None and remaining_depth <= 0:
                # Lazy-load sentinel.
                has_children = _has_visible_children(item_path)
                sub_files, sub_size, newest_mtime = _subtree_summary(
                    item_path, max_depth=SENTINEL_SUMMARY_DEPTH
                )
                is_empty = not _has_any_file(item_path)
                if (
                    not ignored
                    and not is_empty
                    and not _has_any_nongitignored(item_path, ignore_check)
                ):
                    ignored = True
                if newest_mtime == 0.0:
                    try:
                        newest_mtime = entry.stat(follow_symlinks=False).st_mtime
                    except OSError:
                        newest_mtime = 0.0
                sentinel: dict[str, Any] = {
                    "name": entry.name,
                    "path": rel,
                    "type": "dir",
                    "children": None,
                    "has_children": has_children,
                    "total_files": sub_files,
                    "total_size": sub_size,
                    "mtime": newest_mtime,
                }
                marker = _scan_marker_basename(item_path)
                if marker is not None:
                    sentinel["marker_basename"] = marker
                if ignored:
                    sentinel["gitignored"] = True
                if is_empty:
                    sentinel["empty"] = True
                entries.append(sentinel)
                continue

            next_depth = remaining_depth - 1 if remaining_depth is not None else None
            children = _dir_tree(
                item_path,
                max_depth - 1,
                remaining_depth=next_depth,
                ignore_check=ignore_check,
                parent_ignored=ignored,
            )
            total_files, total_size, newest_mtime = _dir_stats(children)
            is_empty = _subtree_is_empty(children)
            if not ignored and _subtree_is_all_gitignored(children):
                ignored = True
            if total_files == 0:
                with contextlib.suppress(OSError):
                    newest_mtime = entry.stat(follow_symlinks=False).st_mtime
            entry_dict: dict[str, Any] = {
                "name": entry.name,
                "path": rel,
                "type": "dir",
                "children": children,
                "total_files": total_files,
                "total_size": total_size,
                "mtime": newest_mtime,
            }
            marker = _marker_in_children([c["name"] for c in children])
            if marker is not None:
                entry_dict["marker_basename"] = marker
            if ignored:
                entry_dict["gitignored"] = True
            if is_empty:
                entry_dict["empty"] = True
            entries.append(entry_dict)
        else:
            try:
                st = entry.stat(follow_symlinks=False)
                size = st.st_size
                mtime = st.st_mtime
            except OSError:
                size = 0
                mtime = 0
            file_dict: dict[str, Any] = {
                "name": entry.name,
                "path": rel,
                "type": "file",
                "size": size,
                "mtime": mtime,
            }
            # Tag gzipped files with their logical (inner) extension so the
            # SPA's icon dispatch + .compression-badge overlay key off
            # the right type instead of seeing every one as the gzip suffix.
            if entry.name.lower().endswith(GZIP_SUFFIX):
                artifact = ArtifactPath(item_path)
                file_dict["logical_ext"] = artifact.logical_ext
                file_dict["compressed"] = True
                file_dict["compression"] = artifact.compression
            if ignored:
                file_dict["gitignored"] = True
            entries.append(file_dict)
    return entries


def _tree_depth_from_query(depth_str: str) -> int:
    """Parse a requested tree depth, keeping every tree response bounded."""
    if not depth_str:
        return DEFAULT_TREE_DEPTH
    try:
        depth = int(depth_str)
    except ValueError:
        return DEFAULT_TREE_DEPTH
    return max(0, min(depth, MAX_TREE_DEPTH))


# ── InventoryIndex-backed tree builder (P1.11) ─────────────────────
#
# When the InventoryIndex walker has populated entries, /api/tree
# can serve from memory in milliseconds rather than walking the
# filesystem. Cold-target budget: first-byte <500 ms on a 35k+
# file repo. The shape of the returned list matches `_dir_tree`'s
# output exactly, so the SPA renderer doesn't branch.
#
# When the index has NO data for a requested directory (e.g., the
# walker hasn't reached this subtree yet), we emit `null` aggregate
# fields and `has_children: true` so the client renders a skeleton
# row. Subsequent fs.change ops on /api/events will populate the
# cell in place.


def _build_inventory_tree(
    *,
    parent_rel: str,
    max_depth: int,
    root_abs: Path,
) -> list[dict[str, Any]]:
    """Recursive in-memory build of the tree shape for a subtree
    rooted at *parent_rel*. Reads only from
    ``InventoryIndex`` — no filesystem access.

    *parent_rel* is the relative path under the served root
    (``""`` for root, ``"sub1"`` for a top-level dir, etc).

    Returns a list of dicts shaped like ``_dir_tree``'s output:
    each entry carries ``name``, ``path``, ``type``, plus dir
    aggregates / file size+mtime. Aggregates that the walker has
    not yet finalized come through as JSON ``null``; the client
    renders them as skeleton cells and patches via
    ``fs.change`` ops on ``/api/events``.
    """

    # Deferred to break the tree → inventory → walker → tree cycle.
    from metabrowser.inventory import (
        get_instance as get_inventory,
    )

    if max_depth <= 0:
        return []

    inv = get_inventory()
    # Single O(N) parent→children scan, reused across every level
    # of the recursion. Without this, a depth-D request rescans the
    # full index D times; at 200k entries that's seconds of CPU.
    by_parent: dict[str, list[Any]] = {}
    for entry in inv.entries(scope="all-known"):
        by_parent.setdefault(entry.parent, []).append(entry)
    # ``parent_ignored`` carries forward "an ancestor was gitignored
    # so this whole subtree paints gray." Look the parent up in the
    # inventory; if we don't have an entry for it (stub or root),
    # fall back to False — the per-entry `entry.gitignored` field
    # written by the walker is the authoritative per-row signal.
    parent_entry = inv.get(parent_rel) if parent_rel else None
    parent_ignored = bool(parent_entry.gitignored) if parent_entry else False
    return _build_inventory_subtree(
        by_parent=by_parent,
        parent_rel=parent_rel,
        max_depth=max_depth,
        parent_ignored=parent_ignored,
        root_abs=root_abs,
    )


def _build_inventory_subtree(
    *,
    by_parent: dict[str, list[Any]],
    parent_rel: str,
    max_depth: int,
    parent_ignored: bool,
    root_abs: Path,
) -> list[dict[str, Any]]:
    if max_depth <= 0:
        return []
    # The root entry has parent == "" == its own path; skip it
    # so the root doesn't render as a sibling of its own children.
    siblings = sorted(
        (e for e in by_parent.get(parent_rel, []) if e.path != parent_rel),
        key=lambda e: (e.type != "dir", e.name),
    )
    out: list[dict[str, Any]] = []
    for entry in siblings:
        if entry.type == "dir":
            # Walker populates `entry.gitignored` once at index-write
            # time; response layer reads the flag straight off the
            # inventory. ``parent_ignored`` propagates down the
            # recursion so a subtree under a gitignored ancestor
            # paints gray even if its own path doesn't match.
            ignored = parent_ignored or entry.gitignored
            children: list[dict[str, Any]] | None
            if max_depth - 1 > 0:
                children = _build_inventory_subtree(
                    by_parent=by_parent,
                    parent_rel=entry.path,
                    max_depth=max_depth - 1,
                    parent_ignored=ignored,
                    root_abs=root_abs,
                )
            else:
                # Past the depth cap; emit a sentinel so the SPA
                # knows to lazy-load on click. has_children matches
                # the shape `_dir_tree` produces for sentinels.
                children = None
            # Aggregate dimming flags, matching _dir_tree semantics:
            # `empty` if subtree has zero files; `gitignored`
            # propagates up when every visible child is ignored.
            # ``total_files is None`` means "walker still finalizing" —
            # don't paint gray on a missing count, only on a finalized
            # zero. Conflating the two flashed every dir gray during
            # the initial inventory scan; an fs.change later filling
            # the count never cleared the class.
            is_empty = entry.total_files == 0
            if children is not None and not ignored and _subtree_is_all_gitignored(children):
                ignored = True
            # Use the inventory's actual child count for the
            # has_children flag. A finalized empty dir would
            # otherwise show a lazy-load spinner that resolves to
            # nothing, leaving the spinner spinning forever.
            inv_child_count = sum(1 for c in by_parent.get(entry.path, []) if c.path != entry.path)
            entry_dict: dict[str, Any] = {
                "name": entry.name,
                "path": entry.path,
                "type": "dir",
                # Aggregates: None pass-through. Wire format emits
                # JSON null for None; the client treats as
                # "skeleton cell, fill via fs.change".
                "total_files": entry.total_files,
                "total_size": entry.total_size,
                # Distinguish "walker still finalizing" (None → skeleton)
                # from "finalized, dir is genuinely empty" (0 → no age
                # text). The client renders the former as a pulsing
                # placeholder; the latter as nothing.
                "mtime": entry.newest_mtime_ns / 1_000_000_000.0
                if entry.newest_mtime_ns is not None
                else None,
                "has_children": inv_child_count > 0 if children is None else bool(children),
                "children": children,
            }
            if ignored:
                entry_dict["gitignored"] = True
            if is_empty:
                entry_dict["empty"] = True
            out.append(entry_dict)
        else:
            ignored = parent_ignored or entry.gitignored
            file_dict: dict[str, Any] = {
                "name": entry.name,
                "path": entry.path,
                "type": "file",
                "size": entry.size,
                "mtime": entry.mtime_ns / 1_000_000_000.0 if entry.mtime_ns else 0.0,
            }
            if entry.name.lower().endswith(GZIP_SUFFIX):
                artifact = ArtifactPath(root_abs / entry.path)
                file_dict["logical_ext"] = artifact.logical_ext
                file_dict["compressed"] = True
                file_dict["compression"] = artifact.compression
            if ignored:
                file_dict["gitignored"] = True
            out.append(file_dict)
    return out


def inventory_has_data() -> bool:
    """True iff the InventoryIndex has at least one entry for
    the served root. Used by the route layer to decide between
    inventory-backed and filesystem-walked tree responses."""

    # Deferred to break the tree → inventory → walker → tree cycle.
    from metabrowser.inventory import (
        get_instance as get_inventory,
    )

    return bool(get_inventory().entries(scope="all-known"))


def inventory_status() -> str:
    """Pass-through for the route layer's ``tally_cache_status``
    envelope field. Returns 'idle' / 'scanning' / 'done' /
    'truncated'."""

    # Deferred to break the tree → inventory → walker → tree cycle.
    from metabrowser.inventory import (
        get_instance as get_inventory,
    )

    return get_inventory().status()
