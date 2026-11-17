"""A native stack's combined change, which its heading in the Pulls tab says in brief.

A stack is the accumulation of its pull requests, so its change is theirs accumulated: each
member's own changed files, the list its expanded row in the Pulls tab shows
(:mod:`.pull_files_route`), taken bottom first, every file once, with its line counts summed.
It is never a comparison against the stack's base branch, which would say nothing for a
stack whose pull requests have merged, and nothing for the history of one that has not
(the owner's decision on review A of #484, A1: "The stack historically is the set of PRs
it consists of").

**One file, once.** The lists are accumulated by :mod:`.pull_change_sums`: a file is
followed by its path and across a rename, its status is composed from what the members did
to it (``removed`` if the last one removed it, else ``added`` if the first one added it,
else ``renamed`` if one renamed it, else ``modified``), and its lines are each member's
summed, as each layer's own counts are what that layer wrote.

**What it reads.** The stack snapshot (:mod:`.pull_stacks`) for the members, and each
member's cached list of changed files, GitHub's or the one listed from the local
comparison, whichever its refresh last wrote, as the Pulls tab shows it, stale or current.
A read never asks GitHub, never fetches, and runs no Git. Measured 2026-11-16 on this
repository's cache: of the 173 pull requests its 19 stacks hold, 15 had a list of changed
files and 10 a record, so the lists are the change sets more often held, and reading one
runs no Git where a record's comparison is listed in the store first. What the lists
accumulate to is kept by each member's list file (its inode, modification time and size),
so asking again stats the lists and parses none. Measured the same day at a load average of
26 to 38: #446's 16 cached lists, 391 rows in 56 KB, were read and parsed in 6 to 16 ms and
accumulated in under 0.4 ms, and a repeat stats the 16 in 0.2 ms.

Measured 2026-11-16 on GitHub's own lists of each member: summed per pull request, as
GitHub counts each, #446's 28 layers say 754 files and #218's 46 say 1,925; accumulated, a
file several layers touch counted once and its lines summed, they are 263 and 672, of which
#218's 77 are files a later layer removed.

**Settled or not.** A member's list can be missing, still filling, or read for an older head
than the catalog's row or the record now names, as the files route's ``_head_moved`` asks;
a refresh, which the head's move starts, replaces it later. The answer names such members
in ``pending``, whatever its state, and the Pulls tab reads a stack that names any again,
so a list cached or refreshed after a read reaches its heading (review B of #484, B1); an
answer that names none holds until the stack's members or their heads change. Finding the
moved members reads a record and a catalog row a member, each through its own parse cache:
measured 2026-11-16 on #446's 28 members in this repository's cache at a load average of
19 to 27, 22 to 36 ms, 303 ms the first time.

The answer is ``current``, with the sums, or ``absent``, with a ``reason``: ``not_github``,
no GitHub repository; ``not_stacked``, no stack of that number in the snapshot;
``not_cached``, a member's list is not cached, or is still filling, until a refresh
publishes it whole, with those members in ``pending``; ``too_large``, a member's list is short, GitHub's most for a pull
request (``MAX_PULL_FILES``) or with a file left out, or the members' lists together pass
``MAX_STACK_LIST_BYTES``, so the sums would be short. Only an answer and ``too_large`` are
kept. An answer has no window of its own: the Pulls tab asks again when the catalog says a
member's head moved or the members changed (``stack-lines.js``). ``revision`` names the
answer's content, which the Pulls tab keeps it under. Its entity tag is the envelope's, as
every GitHub route's is, for a client that holds one, ``--api`` among them; the Pulls tab
sends none.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import stat
from collections.abc import Iterator
from dataclasses import dataclass
from threading import Lock
from typing import TYPE_CHECKING, Final, Literal, TypedDict
from weakref import WeakKeyDictionary

from metabrowser.builtin_plugins.github.pull_change_sums import ChangeSums, accumulate
from metabrowser.builtin_plugins.github.pull_stacks import read_stacks
from metabrowser.cache.paths import source_pull_files
from metabrowser.http_caching import BUILD_TAG, build_scoped_etag
from metabrowser.loading_cache import LoadingCache

if TYPE_CHECKING:
    from metabrowser.builtin_plugins.github.pull_list import ListedRepository, PullFileList

STACK_CHANGE_ROUTE: Final = "/api/plugin/github/stack-change"
# The accumulations kept, least recently used out first. Measured 2026-11-16 with
# tracemalloc, 256 sums, each with four statuses and its key, held 191 KB, 747 bytes each; a
# key now names each member's list, about 60 bytes a member more. This repository has 19
# stacks, and a member whose list is refreshed names a new key, so this keeps every stack's
# current sums and a few hundred older ones.
MAX_KEPT_STACK_CHANGES: Final = 256
# The members' lists read for one answer, together, in bytes as cached, checked on their
# stamps before any is read. Measured 2026-11-16 at a load average of 14 to 17: 36 lists of
# 3,000 rows, 13.9 MB, were read and folded in 284 to 321 ms, holding at most 12.3 MB by
# tracemalloc, one parsed list and the accumulation, where holding every list at once
# peaked at 123 MB (review B of #484, B5). #446's 16 cached lists are 56 KB. So this bounds
# an answer, off the event loop, at about 400 ms and some 12 MB, two of the largest lists a
# pull request can have (``MAX_PULL_FILES_BYTES``).
MAX_STACK_LIST_BYTES: Final = 16 * 1024 * 1024

type StackChangeAbsence = Literal["not_github", "not_stacked", "not_cached", "too_large"]
type _Stamp = tuple[int, int, int]


class StatusCount(TypedDict):
    """How many of the accumulated files have one status, in a pull request's words."""

    status: str
    count: int


class StackChangeEnvelope(TypedDict):
    """What ``GET /api/plugin/github/stack-change`` answers."""

    state: Literal["absent", "current"]
    reason: StackChangeAbsence | None
    number: int
    # The members accumulated, bottom first, for an answer with sums.
    pulls: list[int]
    # The members not settled: with no whole list, or with a list read for another head
    # than the newest one known. A stack that names any is asked for again.
    pending: list[int]
    revision: str | None
    files: int | None
    additions: int | None
    deletions: int | None
    exact: bool
    statuses: list[StatusCount]


_KEPT: WeakKeyDictionary[
    asyncio.AbstractEventLoop, LoadingCache[tuple[object, ...], _Accumulated]
] = WeakKeyDictionary()
_KEPT_LOCK: Final = Lock()


def _kept() -> LoadingCache[tuple[object, ...], _Accumulated]:
    loop = asyncio.get_running_loop()
    with _KEPT_LOCK:
        kept = _KEPT.get(loop)
        if kept is None:
            kept = _KEPT[loop] = LoadingCache(max_values=MAX_KEPT_STACK_CHANGES)
        return kept


def absent(
    number: int, reason: StackChangeAbsence, *, pending: list[int] | None = None
) -> StackChangeEnvelope:
    return StackChangeEnvelope(
        state="absent",
        reason=reason,
        number=number,
        pulls=[],
        pending=[] if pending is None else pending,
        revision=None,
        files=None,
        additions=None,
        deletions=None,
        exact=False,
        statuses=[],
    )


def _list_stamp(repository: ListedRepository, number: int) -> _Stamp | None:
    try:
        status = os.lstat(repository.home / source_pull_files(repository.slug, number))
    except OSError:
        return None
    if not stat.S_ISREG(status.st_mode):
        return None
    return status.st_ino, status.st_mtime_ns, status.st_size


def stack_lists(
    repository: ListedRepository, number: int
) -> tuple[tuple[int, ...], tuple[_Stamp | None, ...]] | StackChangeAbsence:
    """Stack *number*'s members, bottom first, and the stamp of each one's cached list, or
    ``None`` for a member with none. Blocking; one bounded snapshot read and a stat a member."""

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
    stamps = tuple(_list_stamp(repository, member) for member in stack.pulls)
    if sum(stamp[2] for stamp in stamps if stamp is not None) > MAX_STACK_LIST_BYTES:
        return "too_large"
    return stack.pulls, stamps


@dataclass(frozen=True, slots=True)
class _Accumulated:
    """What the members' lists accumulate to, and the head each list was read for."""

    sums: ChangeSums
    heads: tuple[str | None, ...]


def _read_and_accumulate(
    repository: ListedRepository, members: tuple[int, ...]
) -> _Accumulated | tuple[int, ...]:
    """Read each member's list and fold it into the accumulation, or name the members with
    no whole list. Blocking; run it off the event loop.

    Each list is read within its own bound (``MAX_PULL_FILES_BYTES``), all of them within
    ``MAX_STACK_LIST_BYTES``, which :func:`stack_lists` checked on their stamps, and one at
    a time: a list is folded in as it is read and let go, so a read holds one parsed list
    and the accumulation, not every list at once (review B of #484, B5).
    """

    from metabrowser.builtin_plugins.github.pull_list import read_pull_files

    lacking: list[int] = []
    heads: list[str | None] = []

    def lists() -> Iterator[PullFileList]:
        for member in members:
            listed = read_pull_files(repository.home, repository.slug, member)
            if isinstance(listed, str) or not listed.complete:
                lacking.append(member)
                continue
            heads.append(listed.head)
            yield listed

    sums = accumulate(lists())
    if lacking:
        return tuple(lacking)
    return _Accumulated(sums, tuple(heads))


def _moved(
    repository: ListedRepository, members: tuple[int, ...], heads: tuple[str | None, ...]
) -> list[int]:
    """The members whose list was read for another head than the newest one known, from
    the catalog's row or the record, as the files route's ``_head_moved`` asks. Blocking
    and bounded: a record and a catalog row a member, each through its own parse cache."""

    from metabrowser.builtin_plugins.github.pull_files_route import known_head

    moved: list[int] = []
    for member, head in zip(members, heads, strict=True):
        newest, _base = known_head(repository.home, repository.slug, member)
        if head is not None and newest is not None and newest != head:
            moved.append(member)
    return moved


class _NotWhole(Exception):
    """Members whose lists are not whole, which is not kept."""

    def __init__(self, lacking: tuple[int, ...]) -> None:
        super().__init__(lacking)
        self.lacking = lacking


async def stack_change(repository: ListedRepository | None, number: int) -> StackChangeEnvelope:
    """Stack *number*'s change, or why there is none. Runs no GitHub call and no Git."""

    if repository is None:
        return absent(number, "not_github")
    found = await asyncio.to_thread(stack_lists, repository, number)
    if isinstance(found, str):
        return absent(number, found)
    members, stamps = found
    missing = [member for member, stamp in zip(members, stamps, strict=True) if stamp is None]
    if missing:
        return absent(number, "not_cached", pending=missing)
    key = (BUILD_TAG, str(repository.home), repository.slug, members, stamps)

    async def load() -> _Accumulated:
        summed = await asyncio.to_thread(_read_and_accumulate, repository, members)
        if isinstance(summed, tuple):
            raise _NotWhole(summed)
        return summed

    try:
        accumulated = await _kept().get(key, load)
    except _NotWhole as exc:
        return absent(number, "not_cached", pending=list(exc.lacking))
    sums = accumulated.sums
    if sums.short:
        return absent(number, "too_large")
    pending = await asyncio.to_thread(_moved, repository, members, accumulated.heads)
    statuses = [StatusCount(status=status, count=count) for status, count in sums.statuses]
    content = [members, sums.files, sums.additions, sums.deletions, sums.exact, sums.statuses]
    revision = hashlib.sha256(json.dumps(content).encode()).hexdigest()[:32]
    return StackChangeEnvelope(
        state="current",
        reason=None,
        number=number,
        pulls=list(members),
        pending=pending,
        revision=revision,
        files=sums.files,
        additions=sums.additions,
        deletions=sums.deletions,
        exact=sums.exact,
        statuses=statuses,
    )


def envelope_etag(envelope: StackChangeEnvelope) -> str:
    digest = hashlib.sha256(json.dumps(envelope, sort_keys=True).encode()).hexdigest()
    return build_scoped_etag(f"stack-change-{digest[:32]}")


__all__ = [
    "MAX_KEPT_STACK_CHANGES",
    "MAX_STACK_LIST_BYTES",
    "STACK_CHANGE_ROUTE",
    "StackChangeEnvelope",
    "envelope_etag",
    "stack_change",
    "stack_lists",
]
