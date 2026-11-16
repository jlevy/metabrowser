"""A native stack's combined change, which its heading in the Pulls tab says in brief.

A stack's change is what the whole stack changes: its top pull request's head compared with
the stack's base branch, from their merge base, which is the Changes one pull request from
the top into the stack's base would have. Summing each pull request's counts would count
twice a file two layers change, and every line one layer writes and the next rewrites. The
left end is the base branch as the repository store mirrors it
(``refs/remotes/origin/<base_ref>``), not any layer's record, so the change leaves out what
the base branch itself changed since a layer's record was fetched, a bottom that merged
among it (review of #484, A1). The right end is the top's cached record's comparison
``head``, the commit the top's page shows; membership, bottom first, and the base branch's
name are the stack snapshot's (:mod:`.pull_stacks`).

A read never asks GitHub and never fetches. It reads the snapshot and the top's record,
then finds in the store the base branch's commit and its merge base with the top's head.
The first time a merge base and a head are asked for together, it lists their comparison,
a manifest with no patch (``git diff --raw`` and ``--numstat``, copies found, as a pull
request's own). What that comparison sums to, how many files have each status and its line
totals, is kept by the merge base, the head, the store and the build, so a base branch that
moves on and leaves the merge base where it was lists nothing again. A comparison the
comparison route keeps, a stack of one open pull request's, is summed from what that route
keeps; a stack's own manifest is not kept, so it takes no place from the comparisons a page
opens.

Measured 2026-11-16 with ``comparison_sums`` on this repository's own 19 stacks, of 2 to 46
pull requests, in a full clone at a load average of 11 to 16, twice each: a first listing
ran 3 Git processes, 4 for one whose renames were looked for again, and took 52 to 298 ms;
a repeat ran none and took under 1 ms; an answer was 318 to 430 bytes of JSON. Summed per
pull request, as GitHub counts each, #446's 28 layers would have said 754 files where the
stack changes 263, and #218's 46 said 1,925 where it changes 596. Finding the left end
(``stack_ends``) runs Git on every answer, first or repeat: measured 2026-11-16 on the same
19 tops in a full clone at a load average of 30 to 35, on a case-insensitive filesystem,
where ``base_branch_usable`` lists the mirrored refs, it ran 4 Git processes, 5 where the
merge base is neither end, and took 60 to 232 ms.

The answer is ``current``, with the sums, or ``absent``, with a ``reason``: ``not_github``,
no GitHub repository; ``no_store``, no repository store to compare in; ``not_stacked``, no
stack of that number in the snapshot; ``not_cached``, the top's record is not cached;
``no_comparison``, the top's record names no comparison, since its commits are not in the
store; ``no_base_branch``, the store mirrors no branch of the stack's base name, or none it
can compare from (``base_branch_usable``); ``too_large``, the comparison lists more files
than a manifest holds (``MAX_MANIFEST_FILES``) or more than Git's read cap, so its sums
would be short; ``unavailable``, the store could not compare the two, as for a missing
object or a shallow history that cannot say where they meet. Only an answer and
``too_large`` are kept: a refusal is asked again, since a fetch can answer it.

An answer has no window of its own. It changes when the stack's members, the top's record,
or the merge base do, and the Pulls tab asks again when the catalog says a member or the
top's head changed (``stack-lines.js``). Its entity tag is the envelope's, as every GitHub
route's is, for a client that holds one, ``--api`` among them; the Pulls tab sends none.
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

from metabrowser.builtin_plugins.github.pull_stacks import read_stacks
from metabrowser.http_caching import BUILD_TAG, build_scoped_etag, store_tag
from metabrowser.loading_cache import LoadingCache

if TYPE_CHECKING:
    from pathlib import Path

    from metabrowser.builtin_plugins.github.pull_list import ListedRepository
    from metabrowser.builtin_plugins.github.pull_route import PullHost
    from metabrowser.builtin_plugins.github.pull_stacks import NativeStack
    from metabrowser.builtin_plugins.github.served_pull import ServedPulls
    from metabrowser.cache.acquire import PublishedSource
    from metabrowser.git.process import GitLocation

STACK_CHANGE_ROUTE: Final = "/api/plugin/github/stack-change"
# The sums kept, least recently used out first. Measured 2026-11-16 with tracemalloc, 256
# of them, each with four statuses and its key, held 191 KB, 747 bytes each. This repository
# has 19 stacks, and a stack whose top moves names a new head, so this keeps every stack's
# current sums and a few hundred older ones.
MAX_KEPT_STACK_CHANGES: Final = 256

type StackChangeAbsence = Literal[
    "not_github",
    "no_store",
    "not_stacked",
    "not_cached",
    "no_comparison",
    "no_base_branch",
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
    files: int | None
    additions: int | None
    deletions: int | None
    exact: bool
    statuses: list[StatusCount]


@dataclass(frozen=True, slots=True)
class StackEnds:
    """A stack's bottom and top pull requests, and the commits its change runs between:
    the merge base of its base branch and its top's head, and that head."""

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


# A listing past Git's read cap: more files than any manifest holds, so its sums are short.
_TOO_LARGE: Final = ComparisonSums(
    files=0, additions=None, deletions=None, exact=False, statuses=(), truncated=True
)

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
        files=None,
        additions=None,
        deletions=None,
        exact=False,
        statuses=[],
    )


def stack_top(
    repository: ListedRepository, served: ServedPulls, number: int
) -> tuple[NativeStack, str] | StackChangeAbsence:
    """Stack *number* and its top's head, from the snapshot and the top's cached record.
    Blocking and bounded.

    The snapshot is read within its own bound (``MAX_STACK_BYTES``) and the record within
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
    record, _dumped, _revision = cached_pull_record(served.home, served.slug, stack.pulls[-1])
    if not isinstance(record, PullRecord):
        return "not_cached"
    if record.comparison is None:
        return "no_comparison"
    return stack, record.comparison.head


async def stack_ends(
    published: PublishedSource, stack: NativeStack, head: str
) -> StackEnds | StackChangeAbsence:
    """Where *stack*'s change runs: from the merge base of its base branch, as the store
    mirrors it, and its top's *head*, to that head.

    The base branch is read as an open pull request's comparison reads it
    (``comparison_endpoints``), without the fetch that falls back to: a branch the store
    does not mirror, or one it lists under another spelling, is ``no_base_branch``. Runs Git
    in the store, under its read policy, and never fetches.
    """

    from metabrowser.cache.origin import BRANCH_MIRROR_PREFIX
    from metabrowser.cache.pull_refs import base_branch_usable, ref_commit
    from metabrowser.git.process import GitError, repository_store_target
    from metabrowser.git.shallow import merge_base_answer

    try:
        if not await base_branch_usable(published, stack.base_ref):
            return "no_base_branch"
        base_commit = await ref_commit(published, BRANCH_MIRROR_PREFIX + stack.base_ref)
        if base_commit is None:
            return "no_base_branch"
        answer = await merge_base_answer(
            repository_store_target(git_dir=published.git_dir), base_commit, head
        )
    except GitError:
        return "unavailable"
    if answer.merge_base is None or not answer.certain:
        return "unavailable"
    return StackEnds(stack.pulls[0], stack.pulls[-1], answer.merge_base, head)


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
    from metabrowser.git.process import GitOutputTooLargeError

    kept = kept_comparison_manifest(key)
    if kept is not None:
        manifest = kept.manifest
    else:
        source = GitDiffSource(location)
        try:
            manifest = await source.manifest(await source.resolve(intent))
        except GitOutputTooLargeError:
            # Answered and kept as a listing past ``MAX_MANIFEST_FILES`` is, so it is not
            # listed again (review of #484, A8).
            return _TOO_LARGE
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

    from metabrowser.cache.acquire import PublishedSource
    from metabrowser.diff.adapters.base import DiffSourceError
    from metabrowser.git.process import GitError

    if host is None or repository is None:
        return absent(number, "not_github")
    served = host.pulls
    published = served.published
    if not isinstance(published, PublishedSource):
        return absent(number, "no_store")
    found = await asyncio.to_thread(stack_top, repository, served, number)
    if isinstance(found, str):
        return absent(number, found)
    stack, head = found
    ends = await stack_ends(published, stack, head)
    if isinstance(ends, str):
        return absent(number, ends)
    try:
        sums = await comparison_sums(published.git_dir, ends.base, ends.head)
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
    "stack_top",
]
