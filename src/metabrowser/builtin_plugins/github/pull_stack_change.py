"""A native stack's combined change, which its heading in the Pulls tab says in brief.

A stack's change is what the whole stack changes: its bottom pull request's base compared
with its top pull request's head, from their merge base, as one pull request's Changes
compares its own two ends. Summing each pull request's counts would count twice a file two
layers change, and every line one layer writes and the next rewrites. The two ends are the
cached records' comparisons, the bottom's ``base`` and the top's ``head``, so the stack's
change starts and ends at the commits those two pages show; membership, bottom first, is
the stack snapshot's (:mod:`.pull_stacks`).

A read never asks GitHub and never fetches. It reads the snapshot and the two records, and
the first time a pair of ends is asked for it lists their comparison in the repository
store, a manifest with no patch (``git diff --raw`` and ``--numstat``, copies found, as a
pull request's own). What that comparison sums to, how many files have each status and its
line totals, is kept by the two commit IDs, the store and the build, so asking again runs
no Git. A comparison the comparison route keeps, a stack of one pull request's, is summed
from what that route keeps; a stack's own manifest is not kept, so it takes no place from
the comparisons a page opens.

Measured 2026-11-16 with ``comparison_sums`` on this repository's own 19 stacks, of 2 to 46
pull requests, in a full clone at a load average of 11 to 16, twice each: a first answer ran
3 Git processes, 4 for one whose renames were looked for again, and took 52 to 298 ms; a
repeat ran none and took under 1 ms; an answer was 318 to 430 bytes of JSON. Summed per pull
request, as GitHub counts each, #446's 28 layers would have said 754 files where the stack
changes 263, and #218's 46 said 1,925 where it changes 596.

The answer is ``current``, with the sums, or ``absent``, with a ``reason``: ``not_github``,
no GitHub repository; ``no_store``, no repository store to compare in; ``not_stacked``, no
stack of that number in the snapshot; ``not_cached``, the bottom's or the top's record is
not cached; ``no_comparison``, a record names no comparison, since its commits are not in
the store; ``too_large``, the comparison lists more files than a manifest holds
(``MAX_MANIFEST_FILES``), so its sums would be short; ``unavailable``, the store could not
compare the two, as for a missing object. Only an answer and ``too_large`` are kept: a
refusal is asked again, since a fetch can answer it.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from threading import Lock
from typing import TYPE_CHECKING, Any, Final, Literal, TypedDict
from weakref import WeakKeyDictionary

from metabrowser.builtin_plugins.github.pull_stacks import STACK_FRESHNESS_S, read_stacks
from metabrowser.http_caching import BUILD_TAG, build_scoped_etag, store_tag
from metabrowser.loading_cache import LoadingCache

if TYPE_CHECKING:
    from pathlib import Path

    from metabrowser.builtin_plugins.github.pull_list import ListedRepository
    from metabrowser.builtin_plugins.github.pull_route import PullHost
    from metabrowser.builtin_plugins.github.served_pull import ServedPulls
    from metabrowser.git.process import GitLocation

STACK_CHANGE_ROUTE: Final = "/api/plugin/github/stack-change"
# The sums kept, least recently used out first. Measured 2026-11-16 with tracemalloc, 256
# of them, each with four statuses and its key, held 191 KB, 747 bytes each. This repository
# has 19 stacks, and a stack whose members change names new ends, so this keeps every
# stack's current sums and a few hundred older ones.
MAX_KEPT_STACK_CHANGES: Final = 256

type StackChangeAbsence = Literal[
    "not_github",
    "no_store",
    "not_stacked",
    "not_cached",
    "no_comparison",
    "too_large",
    "unavailable",
]


class StatusCount(TypedDict):
    """How many of the comparison's files have one status, in a pull request's words."""

    status: str
    count: int


class StackChangeEnvelope(TypedDict):
    """What ``GET /api/plugin/github/stack-change`` answers."""

    state: Literal["absent", "current"]
    reason: StackChangeAbsence | None
    number: int
    bottom: int | None
    top: int | None
    base: str | None
    head: str | None
    # How long the answer holds: the stack snapshot's own window, past which its members,
    # and so its ends, may have moved.
    fresh_for_s: float
    files: int | None
    additions: int | None
    deletions: int | None
    exact: bool
    statuses: list[StatusCount]


@dataclass(frozen=True, slots=True)
class StackEnds:
    """A stack's bottom and top pull requests, and the commits its change runs between."""

    bottom: int
    top: int
    base: str
    head: str


@dataclass(frozen=True, slots=True)
class ComparisonSums:
    """What one comparison sums to: its files by status and its line totals.

    ``truncated`` says the listing stopped at its bound, so the rest are not known.
    """

    files: int
    additions: int | None
    deletions: int | None
    exact: bool
    statuses: tuple[tuple[str, int], ...]
    truncated: bool


_KEPT: WeakKeyDictionary[
    asyncio.AbstractEventLoop, LoadingCache[tuple[str, ...], ComparisonSums]
] = WeakKeyDictionary()
_KEPT_LOCK: Final = Lock()


def _kept() -> LoadingCache[tuple[str, ...], ComparisonSums]:
    loop = asyncio.get_running_loop()
    with _KEPT_LOCK:
        kept = _KEPT.get(loop)
        if kept is None:
            kept = _KEPT[loop] = LoadingCache(max_values=MAX_KEPT_STACK_CHANGES)
        return kept


def absent(
    number: int, reason: StackChangeAbsence, ends: StackEnds | None = None
) -> StackChangeEnvelope:
    return StackChangeEnvelope(
        state="absent",
        reason=reason,
        number=number,
        bottom=None if ends is None else ends.bottom,
        top=None if ends is None else ends.top,
        base=None if ends is None else ends.base,
        head=None if ends is None else ends.head,
        fresh_for_s=STACK_FRESHNESS_S,
        files=None,
        additions=None,
        deletions=None,
        exact=False,
        statuses=[],
    )


def stack_ends(
    repository: ListedRepository, served: ServedPulls, number: int
) -> StackEnds | StackChangeAbsence:
    """Stack *number*'s ends from the snapshot and two cached records. Blocking and bounded.

    The snapshot is read within its own bound (``MAX_STACK_BYTES``) and each record within
    the record's, through the pull route's parse cache.
    """

    from metabrowser.builtin_plugins.github.pull_record import PullRecord
    from metabrowser.builtin_plugins.github.pull_route import cached_pull_record

    cache = read_stacks(repository)
    snapshot = cache.snapshot if cache is not None else None
    stack = (
        None
        if snapshot is None
        else next(
            (found for page in snapshot.pages for found in page.stacks if found.number == number),
            None,
        )
    )
    if stack is None:
        return "not_stacked"
    bottom, top = stack.pulls[0], stack.pulls[-1]
    ends: list[str] = []
    for member, end in ((bottom, "base"), (top, "head")):
        record, _dumped, _revision = cached_pull_record(served.home, served.slug, member)
        if not isinstance(record, PullRecord):
            return "not_cached"
        if record.comparison is None:
            return "no_comparison"
        ends.append(record.comparison.base if end == "base" else record.comparison.head)
    return StackEnds(bottom, top, ends[0], ends[1])


async def comparison_sums(git_dir: Path, base: str, head: str) -> ComparisonSums:
    """What the merge-base comparison of *base* and *head* in the store sums to.

    Kept by the comparison's own key and the build, and computed once however many ask
    together. Raises the adapter's ``DiffSourceError`` or ``GitError`` for a refusal.
    """

    from metabrowser.builtin_plugins.diff.sidekick import comparison_cache_key
    from metabrowser.git.process import GitLocation, repository_store_target

    location = GitLocation.revision(repository_store_target(git_dir=git_dir), head)
    intent = {"left": base, "right": head, "base_policy": "merge_base"}
    key = comparison_cache_key(location, intent, store_tag(git_dir))
    if key is None:
        raise ValueError("a stack's ends are two full commit IDs in a store")
    return await _kept().get((BUILD_TAG, *key), lambda: _sum(location, intent, key))


async def _sum(
    location: GitLocation, intent: dict[str, Any], key: tuple[str, ...]
) -> ComparisonSums:
    from metabrowser.builtin_plugins.diff.sidekick import kept_comparison_manifest
    from metabrowser.builtin_plugins.github.pull_files_refresh import KIND_STATUS
    from metabrowser.diff.adapters.git import GitDiffSource

    kept = kept_comparison_manifest(key)
    if kept is not None:
        manifest = kept.manifest
    else:
        source = GitDiffSource(location)
        manifest = await source.manifest(await source.resolve(intent))
    # Each file's status in a pull request's words, as its list of changed files says it.
    counts = Counter(KIND_STATUS[change.kind.value] for change in manifest.files)
    totals = manifest.totals
    return ComparisonSums(
        files=totals.files,
        additions=totals.additions,
        deletions=totals.deletions,
        exact=totals.exact,
        statuses=tuple(sorted(counts.items())),
        truncated=manifest.truncated,
    )


async def stack_change(
    host: PullHost | None, repository: ListedRepository | None, number: int
) -> StackChangeEnvelope:
    """Stack *number*'s change, or why there is none. Runs no GitHub call."""

    from metabrowser.diff.adapters.base import DiffSourceError
    from metabrowser.git.process import GitError

    if host is None or repository is None:
        return absent(number, "not_github")
    served = host.pulls
    git_dir = served.git_dir
    if git_dir is None:
        return absent(number, "no_store")
    ends = await asyncio.to_thread(stack_ends, repository, served, number)
    if isinstance(ends, str):
        return absent(number, ends)
    try:
        sums = await comparison_sums(git_dir, ends.base, ends.head)
    except (DiffSourceError, GitError):
        return absent(number, "unavailable", ends)
    if sums.truncated:
        return absent(number, "too_large", ends)
    return StackChangeEnvelope(
        state="current",
        reason=None,
        number=number,
        bottom=ends.bottom,
        top=ends.top,
        base=ends.base,
        head=ends.head,
        fresh_for_s=STACK_FRESHNESS_S,
        files=sums.files,
        additions=sums.additions,
        deletions=sums.deletions,
        exact=sums.exact,
        statuses=[StatusCount(status=status, count=count) for status, count in sums.statuses],
    )


def envelope_etag(envelope: StackChangeEnvelope) -> str:
    digest = hashlib.sha256(json.dumps(envelope, sort_keys=True).encode()).hexdigest()
    return build_scoped_etag(f"stack-change-{digest[:32]}")


__all__ = [
    "MAX_KEPT_STACK_CHANGES",
    "STACK_CHANGE_ROUTE",
    "ComparisonSums",
    "StackChangeEnvelope",
    "StackEnds",
    "comparison_sums",
    "envelope_etag",
    "stack_change",
    "stack_ends",
]
