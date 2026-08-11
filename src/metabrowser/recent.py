"""Recent-files surface — server-side filter + gitignore resolver.

Exposes the helpers behind ``GET /api/recent``. The endpoint
itself lives in :mod:`metabrowser.proc_browser`; this module
owns the pure transformation: an ``InventoryIndex`` snapshot →
a flat newest-first leaf list plus the set of gitignored
ancestor directories.

Layering
========

* **Filtering, gitignore, file metadata — backend.**
  Everything that has to be cached, kept current, and stay
  consistent across SSE/HTTP consumers lives on the server.
  The server is the single source of truth for which paths
  exist, what their mtimes are, and which paths gitignore
  matches; the browser never tries to recompute any of that.

* **Clustering — rendering layer.** Single-dir compaction and
  the ``RECENT_CLUSTER_PCT`` cluster-collapse rule are presentation
  concerns: they decide how a flat leaf list paints. The
  authoritative implementation lives in ``clusterRecentTreeJs``
  in ``static/app.js``; the client re-runs it on every
  ``fs.change`` burst, so a Python copy would be both unused
  past first paint and a source of drift. Don't reintroduce
  one — extend the JS function and pin the rule with a
  client-side test instead.

The wire shape this module produces (``RecentResult``) is
therefore *unclustered*: ``entries_flat`` plus
``gitignored_dirs``. The renderer composes them.

This module owns the Recent view's query and projection contract.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from metabrowser.events import FsEntry
from metabrowser.inventory import get_instance as get_inventory
from metabrowser.settings import (
    RECENT_DEFAULT_LIMIT,
    RECENT_MAX_LIMIT,
    RECENT_WINDOW_SECONDS,
)

# Re-exports kept so existing tests / external callers that
# import the module-level constants directly stay working.
# Authoritative defaults live in :mod:`metabrowser.settings`.
WindowKey = Literal["live", "1h", "24h", "7d", "30d", "all"]
DEFAULT_LIMIT = RECENT_DEFAULT_LIMIT
MAX_LIMIT = RECENT_MAX_LIMIT


# ── Recent-set helper ──────────────────────────────────────────


@dataclass(slots=True, frozen=True)
class RecentResult:
    """Filtered recent set + the gitignore decisions it depends on.

    ``entries_flat`` is the newest-first file list the SPA renders.
    ``gitignored_dirs`` is every ancestor directory of those leaves
    whose own path matches gitignore — the client uses it to mark
    dirs gray after running ``clusterRecentTreeJs`` (which can't
    run pathspec). ``total_matching`` is the count BEFORE the
    limit cap so the UI can say "showing 200 of 415".
    """

    entries_flat: list[dict[str, Any]]
    gitignored_dirs: list[str]
    total_matching: int
    truncated: bool
    window: WindowKey
    limit: int


def collect_recent_entries(
    *,
    root: Path,
    window: WindowKey = "24h",
    limit: int = DEFAULT_LIMIT,
    ext_filter: tuple[str, ...] = (),
    prefix_filter: str = "",
    include_ignored: bool = True,
) -> RecentResult:
    """Read trackable file entries from the inventory, filter
    by mtime window + ext + prefix, sort by mtime desc, cap at
    *limit*, and resolve gitignore status for every leaf and its
    ancestor directories.

    *root* is the served root. Gitignore status is read directly
    from each ``FsEntry.gitignored`` field, which the walker
    populates once at index-write time using the same checker as
    the Files tab. Response construction does not repeat that work
    per leaf or ancestor.

    *ext_filter* is matched against the entry's compound-tail
    extension (``.runbook.md`` for ``foo.runbook.md``); empty
    tuple disables the filter.

    *prefix_filter* is a path prefix (e.g. ``"runs/2026-05-05"``);
    empty string disables.

    *include_ignored* keeps gitignored files in the result. Pass False
    when the caller is going to hide them anyway, so the cap is not
    spent on rows nobody will see.

    Truncation drops gitignored files before tracked ones. A dependency
    install touches thousands of files at once, and a straight
    newest-first cap let that bulk fill the whole response — a day
    window on a repository with ``node_modules`` returned 2 000
    gitignored entries and not one of the user's own files. Tracked
    files therefore claim the cap first and ignored files fill whatever
    is left, with the selection re-sorted by mtime so the result still
    reads newest-first.
    """

    if window not in RECENT_WINDOW_SECONDS:
        raise ValueError(f"unknown window: {window!r}")
    cap = max(1, min(limit, MAX_LIMIT))

    seconds = RECENT_WINDOW_SECONDS[window]
    min_mtime_s = (time.time() - seconds) if seconds is not None else 0.0
    min_mtime_ns = int(min_mtime_s * 1_000_000_000)

    inv = get_inventory()
    matching: list[FsEntry] = []
    for entry in inv.entries(scope="all-known"):
        if entry.type != "file":
            continue
        if entry.mtime_ns < min_mtime_ns:
            continue
        if ext_filter and entry.ext not in ext_filter:
            continue
        if prefix_filter and not entry.path.startswith(prefix_filter):
            continue
        if not include_ignored and entry.gitignored:
            continue
        matching.append(entry)

    matching.sort(key=lambda e: e.mtime_ns, reverse=True)
    total_matching = len(matching)
    if total_matching > cap:
        # Tracked files claim the cap first; ignored ones fill the rest.
        capped = [e for e in matching if not e.gitignored][:cap]
        if len(capped) < cap:
            capped += [e for e in matching if e.gitignored][: cap - len(capped)]
        capped.sort(key=lambda e: e.mtime_ns, reverse=True)
    else:
        capped = matching

    file_dicts = [_file_entry_to_recent_dict(e) for e in capped]
    gitignored_dirs = _gitignored_ancestor_dirs(capped)
    return RecentResult(
        entries_flat=file_dicts,
        gitignored_dirs=gitignored_dirs,
        total_matching=total_matching,
        truncated=total_matching > cap,
        window=window,
        limit=cap,
    )


def _file_entry_to_recent_dict(entry: FsEntry) -> dict[str, Any]:
    """Convert an FsEntry into the recent-flat shape the SPA reads.

    ``mtime`` is exposed in seconds (matching what ``formatAge`` wants
    on the client); the gitignore flag is set only when the leaf's
    own path matches the spec, never inherited. Reads
    ``entry.gitignored`` straight off the inventory; the walker is
    the producer.
    """

    out: dict[str, Any] = {
        "name": entry.name,
        "path": entry.path,
        "type": "file",
        "size": entry.size,
        "mtime": entry.mtime_ns / 1_000_000_000.0 if entry.mtime_ns else 0.0,
        # The compound-tail extension (".min.js", ".runbook.md"), which
        # is the unit the nav's type filter and its tally both use. The
        # tree payload carries it too; without it here, rows from this
        # source could not be matched against a compound extension.
        "ext": entry.ext,
    }
    if entry.gitignored:
        out["gitignored"] = True
    return out


def _gitignored_ancestor_dirs(leaves: list[FsEntry]) -> list[str]:
    """Return every distinct ancestor directory of *leaves* whose
    inventory entry has ``gitignored=True``.

    The client clusters these leaves into a directory tree and
    needs to know which of the resulting dir nodes should paint
    gray. It can't run pathspec, so the server pre-computes the
    answer over the leaves' parent chains. Result is sorted for
    a stable wire representation.

    Reads from the inventory; ancestors that aren't in the index
    (e.g. dirs that were rolled out of the truncation cap) are
    treated as not-gitignored.
    """

    inv = get_inventory()
    seen: set[str] = set()
    ignored: list[str] = []
    for leaf in leaves:
        parts = leaf.path.split("/")
        for i in range(1, len(parts)):
            ancestor = "/".join(parts[:i])
            if ancestor in seen:
                continue
            seen.add(ancestor)
            entry = inv.get(ancestor)
            if entry is not None and entry.gitignored:
                ignored.append(ancestor)
    ignored.sort()
    return ignored
