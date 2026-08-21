"""The nav filter, answered from the inventory instead of from the DOM.

The browser used to apply the filter as a decoration pass over rows it had
already mounted (``applyTreeFilters`` in ``static/app.js``). That layer cannot
answer either question a filter actually raises, because it does not hold the
data: whether a collapsed subtree contains a match, and what the matches in a
subtree add up to. ``/api/stream`` is scoped to ``root-depth-2``, so the
browser has no entries at depth 3 or deeper to reason from, and the aggregates
on a folder row are the unfiltered ones the walker computed.

The server does hold the whole index, so it answers both here. One pass over
the entries produces, per directory, the number of matching files below it,
their bytes, and their newest mtime. A directory then appears in the tree only
when that count is non-zero, and its row carries the filtered aggregates rather
than the directory's own.

The predicate mirrors ``static/filter_state.js`` exactly, because the browser
still judges rows that arrive live on ``/api/events`` and the two verdicts have
to agree. Where the two sides need a shared table they read the same one: the
recency windows come from :mod:`metabrowser.settings`, and the size floor
arrives as a byte count so there is no second catalog of bucket names.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock
from typing import TYPE_CHECKING

from metabrowser.file_type_filters import family_for_extension
from metabrowser.settings import RECENT_WINDOW_SECONDS

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from metabrowser.events import FsEntry


@dataclass(frozen=True, slots=True)
class TreeFilter:
    """One filter selection, in the vocabulary the nav filter bar uses.

    ``recency_seconds`` and ``min_size`` are zero when unbounded, ``types`` is
    empty when any type will do, so the default instance is "no filter" and
    :attr:`active` is the single test the route branches on.
    """

    recency_seconds: int = 0
    types: tuple[str, ...] = ()
    min_size: int = 0
    include_ignored: bool = True

    @property
    def active(self) -> bool:
        """Whether this selection removes anything at all."""

        return bool(self.recency_seconds or self.types or self.min_size or not self.include_ignored)

    @property
    def constrains_leaves(self) -> bool:
        """Whether a file-specific dimension is set.

        Symlinks are filesystem references rather than members of a type or
        size bucket, so they survive only while nothing file-specific is asked
        for. Recency counts as file-specific here for the same reason the
        browser treats it that way: a link's mtime is the link's, not its
        target's.
        """

        return bool(self.recency_seconds or self.types or self.min_size)


@dataclass(slots=True)
class DirMatches:
    """What a directory's subtree contributes under one filter.

    ``leaves`` counts every matching leaf, symlinks included, and is what
    decides whether the directory is listed at all. ``files`` and ``size``
    exclude symlinks, matching the aggregates the unfiltered tree already
    reports on a folder row, so the chip means the same thing in both modes.
    """

    leaves: int = 0
    files: int = 0
    size: int = 0
    newest_mtime_ns: int | None = None

    def absorb(self, other: DirMatches) -> None:
        self.leaves += other.leaves
        self.files += other.files
        self.size += other.size
        if other.newest_mtime_ns is not None and (
            self.newest_mtime_ns is None or other.newest_mtime_ns > self.newest_mtime_ns
        ):
            self.newest_mtime_ns = other.newest_mtime_ns


_EMPTY_MATCHES = DirMatches()


def parse_size_floor(raw: str) -> int:
    """Read the ``min_size`` query value as a byte count.

    The browser owns the bucket labels ("over 10M") and sends the floor it
    resolved them to, so there is no second table of bucket names here to drift
    from the one in ``static/filter_state.js``.
    """

    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 0
    return value if value > 0 else 0


def parse_recency(raw: str) -> int:
    """Read the ``recency`` query value as a bound in seconds.

    Unknown keys and the unbounded windows both mean "no bound", so a client
    from a different revision degrades to showing more rather than fewer.
    """

    seconds = RECENT_WINDOW_SECONDS.get(raw)
    return int(seconds) if seconds else 0


def parse_types(values: Sequence[str]) -> tuple[str, ...]:
    """Normalize repeated and comma-separated ``types`` values.

    A token is either an extension (leading dot, possibly a compound tail such
    as ``.min.js``) or a whole filename such as ``README``. That is the one
    convention ``static/filter_state.js`` uses, and it is what lets a preset
    name files that carry no extension at all.
    """

    tokens: list[str] = []
    seen: set[str] = set()
    for value in values:
        for part in value.split(","):
            token = part.strip().lower()
            if token and token != "." and token not in seen:
                seen.add(token)
                tokens.append(token)
    return tuple(tokens)


def type_matches(name: str, ext: str, types: tuple[str, ...]) -> bool:
    """Whether a file carries one of the selected types.

    ``ext`` is the index's bounded compound tail, which is the unit the filter
    menu counts, so a compound pick agrees with the tally that offered it. The
    ``endswith`` arm accepts a semantic suffix (``.md`` matching
    ``.runbook.md``) only when the registry declares the token as a family
    member, so an arbitrary tail match cannot sneak in.
    """

    if not types:
        return True
    lowered_ext = ext.lower()
    lowered_name = name.lower()
    for token in types:
        if token.startswith("."):
            if lowered_ext and (
                lowered_ext == token
                or (family_for_extension(token) is not None and lowered_ext.endswith(token))
            ):
                return True
        elif lowered_name == token:
            return True
    return False


def leaf_matches(entry: FsEntry, tree_filter: TreeFilter, now_sec: float) -> bool:
    """Whether one file or symlink survives *tree_filter*.

    Directories are not judged here: a folder's presence is decided by what its
    subtree contains, which is what :func:`filtered_rollups` computes.
    """

    if entry.type == "symlink":
        return not tree_filter.constrains_leaves
    if tree_filter.recency_seconds:
        mtime_sec = entry.mtime_ns / 1_000_000_000.0 if entry.mtime_ns else 0.0
        if mtime_sec > 0 and now_sec - mtime_sec > tree_filter.recency_seconds:
            return False
    if not type_matches(entry.name, entry.ext, tree_filter.types):
        return False
    return not (tree_filter.min_size and entry.size < tree_filter.min_size)


def parent_of(path: str) -> str:
    """The relative parent of *path*; ``""`` for a top-level entry."""

    cut = path.rfind("/")
    return path[:cut] if cut > 0 else ""


def _depth(path: str) -> int:
    return 0 if not path else path.count("/") + 1


def effective_gitignored(entries: Iterable[FsEntry]) -> dict[str, bool]:
    """Resolve "an ancestor was gitignored" into a per-directory flag.

    The walker stamps ``gitignored`` where the pathspec matched; the tree
    renderer propagates it down as it recurses. A rollup has no recursion to
    carry it, so the propagation is materialized once here, shallowest first.
    """

    dirs = sorted(
        (entry for entry in entries if entry.type == "dir" and entry.path),
        key=lambda entry: _depth(entry.path),
    )
    resolved: dict[str, bool] = {"": False}
    for entry in dirs:
        resolved[entry.path] = bool(entry.gitignored) or resolved.get(parent_of(entry.path), False)
    return resolved


def filtered_rollups(
    entries: Sequence[FsEntry],
    *,
    tree_filter: TreeFilter,
    now_sec: float,
) -> dict[str, DirMatches]:
    """Matching-leaf totals for every directory, rolled up from its subtree.

    Two passes and no recursion: matching leaves land on their own parent, then
    directories are folded into their parents deepest-first. That is O(index)
    for the whole tree rather than O(index) per directory, which matters
    because the caller needs presence for directories it will not even render —
    a folder at the depth cap is listed on the strength of matches far below
    it.
    """

    totals: dict[str, DirMatches] = {"": DirMatches()}
    ignored_dirs = effective_gitignored(entries)
    for entry in entries:
        if entry.type == "dir":
            totals.setdefault(entry.path, DirMatches())
            continue
        if entry.path == "":
            continue
        if not tree_filter.include_ignored and (
            entry.gitignored or ignored_dirs.get(entry.parent, False)
        ):
            continue
        if not leaf_matches(entry, tree_filter, now_sec):
            continue
        bucket = totals.setdefault(entry.parent, DirMatches())
        bucket.leaves += 1
        if entry.type == "file":
            bucket.files += 1
            bucket.size += entry.size
        if entry.mtime_ns and (
            bucket.newest_mtime_ns is None or entry.mtime_ns > bucket.newest_mtime_ns
        ):
            bucket.newest_mtime_ns = entry.mtime_ns
    for path in sorted(totals, key=_depth, reverse=True):
        if not path:
            continue
        totals.setdefault(parent_of(path), DirMatches()).absorb(totals[path])
    return totals


def matches_for(totals: Mapping[str, DirMatches], path: str) -> DirMatches:
    """Totals for *path*, or an all-zero record when nothing matched below it."""

    return totals.get(path, _EMPTY_MATCHES)


# One filter change fans out into many requests that all need the same
# rollup: the tree itself, plus a subtree fetch for every lazy stub the
# idle prefetch sweep warms. Measured with `filtered_rollups` over a
# synthetic index: 121 ms at 100k entries and 480 ms at 400k, which is
# nothing once and minutes across the sweep's 32 requests. The answer does
# not vary by subtree, so it is computed once per (index revision, filter).
#
# Small on purpose, and a settled-index optimization rather than a general
# one: the revision is part of the key, so during a crawl every write makes
# every entry unreachable. That is the same bargain `/api/rollup`'s body
# cache makes. The useful entries are the current filter and whatever the
# reader just came from.
_ROLLUP_CACHE_MAX = 4
# Keyed on the index revision, which `InventoryIndex` draws from a
# process-wide counter so a freshly built index can never reuse one. This
# cache depends on that: with a per-instance counter, two tests that each
# build an index and share a TreeFilter would collide on (1, filter) and one
# would be served the other's rollups. `reset_rollup_cache_for_tests` makes
# the dependency something a test can discharge rather than something that
# has to stay true by luck.
_ROLLUP_CACHE: OrderedDict[tuple[int, TreeFilter], dict[str, DirMatches]] = OrderedDict()
_ROLLUP_CACHE_LOCK = Lock()


def reset_rollup_cache_for_tests() -> None:
    """Drop memoized rollups so a fresh index cannot inherit them.

    Called from :func:`metabrowser.server.reset_response_caches_for_tests`, so
    a test resets every response-shaped cache through one door.
    """

    with _ROLLUP_CACHE_LOCK:
        _ROLLUP_CACHE.clear()


def cached_rollups(
    entries: Sequence[FsEntry],
    *,
    tree_filter: TreeFilter,
    now_sec: float,
    generation: int,
) -> dict[str, DirMatches]:
    """:func:`filtered_rollups`, memoized against the index generation.

    A recency filter is not cached: its verdicts move with the clock, so a
    reused answer would be a different question's. Every other dimension is a
    property of the entries alone, and the generation counter changes whenever
    those do.
    """

    if tree_filter.recency_seconds:
        return filtered_rollups(entries, tree_filter=tree_filter, now_sec=now_sec)
    key = (generation, tree_filter)
    with _ROLLUP_CACHE_LOCK:
        hit = _ROLLUP_CACHE.get(key)
    if hit is not None:
        return hit
    totals = filtered_rollups(entries, tree_filter=tree_filter, now_sec=now_sec)
    with _ROLLUP_CACHE_LOCK:
        _ROLLUP_CACHE[key] = totals
        while len(_ROLLUP_CACHE) > _ROLLUP_CACHE_MAX:
            _ROLLUP_CACHE.pop(next(iter(_ROLLUP_CACHE)))
    return totals
