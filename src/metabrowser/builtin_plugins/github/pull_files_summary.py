"""What each pull request's changed files sum to, for the brief change line its Pulls row shows.

``GET /api/plugin/github/pull-files-summary?numbers=<n>,<n>,...`` answers, for each pull
request it names, what its cached list of changed files sums to: how many files have each
status and the list's line totals, summed as a stack's members are (:mod:`.pull_change_sums`),
so a stack of one pull request says what its row says. It is the list the row's chevron
discloses (:mod:`.pull_files_route`), so the line under a row says what its tree holds. It is
read from the cache alone: it never runs gh or Git and never waits on the network, so a row's
line asks GitHub nothing the Pulls tab does not already ask, which is the changed-files lists
its prefetch names (:mod:`.pull_prefetch`) and a reader's own expansion.

Each pull request's answer is ``listed``, with the list's sums, or ``absent``, with a
``reason``: ``not_cached``, ``schema_mismatch``, or ``unreadable``, no usable list is cached;
``filling``, the list is still being read, or stopped part-way, so its sums would be short;
``too_large``, GitHub stopped at the most files it lists (``capped``) or an item could not be
read (``truncated``), so its sums are short too; ``deferred``, this request read as much as it
may, and the next asks for the rest. ``listing`` says a refresh of the list is running or the
prefetch lane holds one for it, so a list may arrive. A list's ``head`` is the commit it was
listed for, and its ``generation`` names the one refresh that wrote it; ``exact`` is false
when a file has no line counts, a binary one listed locally, which the totals count as none.

What a list sums to is kept by the list file's inode, modification time, and size, which an
atomic replacement changes, so a list read once is summed once. Measured 2026-11-16 on this
repository's own changed-files lists from GitHub, pull requests #440 to #488, 45 lists of 1 to
218 files, 20 at the median, and on the 3,000-row list ``tests/test_github_pull_files.py``
writes at the bound; the numbers are beside the constants.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import threading
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, Literal, TypedDict

from metabrowser.builtin_plugins.github.pull_change_sums import accumulate
from metabrowser.builtin_plugins.github.pull_files_route import list_file_stamp
from metabrowser.builtin_plugins.github.pull_list import (
    MAX_PULL_FILES_BYTES,
    PullFileList,
    read_pull_files,
)
from metabrowser.cache.paths import MAX_PULL_REQUEST_NUMBER
from metabrowser.git.wire import GitChangeSize
from metabrowser.http_caching import build_scoped_etag

if TYPE_CHECKING:
    from pathlib import Path

    from metabrowser.builtin_plugins.github.pull_list import ListedRepository

PULL_FILES_SUMMARY_ROUTE: Final = "/api/plugin/github/pull-files-summary"
# The pull requests one request may name: the rows a Pulls window mounts, those in view and
# PULL_ROWS_OVERSCAN (40) each way, 100 in a pane 1,200 px tall at 61 px a row; a taller
# pane's rest are named in the next request. Measured 2026-11-16 in-process at a load average
# of 45 to 58, 100 numbers took 0.7 to 1.0 ms once their lists were summed, a stat each, and
# as long when none was cached; an answer was 293 to 411 bytes a listed pull request, 330 at
# the median, and 202 for one with none. The whole list, which `GET pull-files` answers, was
# 150 bytes to 50 KB, 4.2 KB at the median, and 6.4 MB at the bound.
MAX_SUMMARY_NUMBERS: Final = 100
# The bytes of lists one request reads to sum, the bound of one list (``MAX_PULL_FILES_BYTES``):
# past them, the lists left are ``deferred``, and the next request reads them. The first list
# is read whatever its size, so every request makes progress. Measured 2026-11-16 at a load
# average of 45 to 58: reading and summing a list took 0.25 to 0.6 ms for this repository's,
# 462 bytes to 29 KB, and 18 to 26 ms for 3,000 files at the path bound, 6.4 MB; 100 numbers
# whose 45 lists were not yet summed took 17 ms.
MAX_SUMMARY_BYTES: Final = MAX_PULL_FILES_BYTES
# The sums kept, least recently used out first. Measured 2026-11-16 with tracemalloc, 1,024 of
# them, each with four statuses and its key, held 0.60 MB, 583 bytes each: ten windows of the
# Pulls tab's rows.
MAX_KEPT_SUMMARIES: Final = 1024

# Each number in the GitHub URL grammar's ``[1-9][0-9]{0,9}``, as ``parse_pull_number`` reads one.
_NUMBERS = re.compile(r"[1-9][0-9]{0,9}(?:,[1-9][0-9]{0,9})*")

type SummaryState = Literal["listed", "absent"]
type SummaryAbsence = Literal[
    "not_cached", "schema_mismatch", "unreadable", "filling", "too_large", "deferred"
]


class SummaryRequestError(Exception):
    """A request the summary route, or the statuses route, refuses. ``str()`` names only the
    request."""


class StatusCount(TypedDict):
    """How many of a list's files have one status, composed as a stack's are
    (:mod:`.pull_change_sums`): added, modified, removed, or renamed."""

    status: str
    count: int


class FilesSummaryWire(TypedDict):
    """One pull request's changed files, summed."""

    number: int
    state: SummaryState
    reason: SummaryAbsence | None
    listing: bool
    listed_from: str | None
    generation: str | None
    head: str | None
    # What the list was listed against: a local comparison's base commit, or the base branch
    # GitHub's list was read for. A pull request page draws a list's line only for the base
    # and head it shows (pull-summary-brief.js).
    base: str | None
    base_ref: str | None
    files: int | None
    additions: int | None
    deletions: int | None
    exact: bool
    statuses: list[StatusCount]
    # The size the list's comparison pushes, when it is kept: a list the store made, whose
    # size the refresh measured after listing it (:mod:`.pull_files_refresh`). Read from
    # what is kept alone, in memory or beside the store, so this route still runs no Git;
    # ``None`` until then, and for a list GitHub gave, which names no merge base.
    size: GitChangeSize | None


class FilesSummaryEnvelope(TypedDict):
    """What ``GET /api/plugin/github/pull-files-summary`` answers."""

    source: str | None
    rows: list[FilesSummaryWire]


@dataclass(frozen=True, slots=True)
class _Sums:
    """What one list file sums to, or why it sums to nothing."""

    reason: SummaryAbsence | None
    listed_from: str | None = None
    generation: str | None = None
    head: str | None = None
    base: str | None = None
    base_ref: str | None = None
    files: int | None = None
    additions: int | None = None
    deletions: int | None = None
    exact: bool = False
    statuses: tuple[tuple[str, int], ...] = ()


type _Stamp = tuple[int, int, int]

# The sums kept, by home, slug, and number, each with the stamp it was read at.
_KEPT: OrderedDict[tuple[str, str, int], tuple[_Stamp, _Sums]] = OrderedDict()
_KEPT_LOCK: Final = threading.Lock()


def summary_numbers(params: Mapping[str, str]) -> tuple[int, ...]:
    """The pull requests a request names, in its order, or :class:`SummaryRequestError`."""

    return named_numbers(params, request="a summary", limit=MAX_SUMMARY_NUMBERS)


def named_numbers(params: Mapping[str, str], *, request: str, limit: int) -> tuple[int, ...]:
    """The pull requests *request*, a route's request, names by ``numbers`` alone, in its
    order: at most *limit*, each once. Anything else is :class:`SummaryRequestError`."""

    if set(params) != {"numbers"}:
        raise SummaryRequestError(f'{request} names its pull requests by "numbers" alone')
    text = params["numbers"]
    if not _NUMBERS.fullmatch(text):
        raise SummaryRequestError('"numbers" is pull request numbers separated by commas')
    numbers = tuple(int(part) for part in text.split(","))
    if (
        len(numbers) > limit
        or len(set(numbers)) != len(numbers)
        or any(number > MAX_PULL_REQUEST_NUMBER for number in numbers)
    ):
        raise SummaryRequestError(f'"numbers" names at most {limit} distinct pull request numbers')
    return numbers


def _sum(listed: PullFileList) -> _Sums:
    def absent(reason: SummaryAbsence) -> _Sums:
        # A list that sums to nothing still names its refresh, so a tree reading its pages
        # is known to read the list already answered.
        return _Sums(
            reason,
            listed_from=listed.listed_from,
            generation=listed.generation,
            head=listed.head,
            base=listed.base,
            base_ref=listed.base_ref,
        )

    if not listed.complete:
        return absent("filling")
    # The one sum a stack's heading says too, of this one pull request's list.
    sums = accumulate([listed])
    if sums.short:
        return absent("too_large")
    return _Sums(
        None,
        listed_from=listed.listed_from,
        generation=listed.generation,
        head=listed.head,
        base=listed.base,
        base_ref=listed.base_ref,
        files=sums.files,
        additions=sums.additions,
        deletions=sums.deletions,
        exact=sums.exact,
        statuses=sums.statuses,
    )


def _kept(key: tuple[str, str, int], stamp: _Stamp) -> _Sums | None:
    with _KEPT_LOCK:
        held = _KEPT.get(key)
        if held is None or held[0] != stamp:
            return None
        _KEPT.move_to_end(key)
        return held[1]


def _keep(key: tuple[str, str, int], stamp: _Stamp, sums: _Sums) -> None:
    with _KEPT_LOCK:
        _KEPT[key] = (stamp, sums)
        _KEPT.move_to_end(key)
        while len(_KEPT) > MAX_KEPT_SUMMARIES:
            _KEPT.popitem(last=False)


def _summed_lists(
    home: Path, slug: str, numbers: tuple[int, ...]
) -> dict[int, _Sums | SummaryAbsence]:
    """What each cached list sums to. Blocking, and bounded by :data:`MAX_SUMMARY_BYTES`.

    A list summed before and unchanged since is a stat; one not yet summed is read, within
    the list's own bound, while the request's bytes allow, and ``deferred`` after.
    """

    budget = MAX_SUMMARY_BYTES
    read_any = False
    out: dict[int, _Sums | SummaryAbsence] = {}
    for number in numbers:
        stamp = list_file_stamp(home, slug, number)
        if stamp is None:
            out[number] = "not_cached"
            continue
        key = (str(home), slug, number)
        held = _kept(key, stamp)
        if held is not None:
            out[number] = held
            continue
        if read_any and stamp[2] > budget:
            out[number] = "deferred"
            continue
        listed = read_pull_files(home, slug, number)
        read_any = True
        # The read is bounded by the list's own bound, so it is charged no more than that.
        budget -= min(stamp[2], MAX_PULL_FILES_BYTES)
        if isinstance(listed, PullFileList):
            sums = _sum(listed)
        elif listed == "not_cached":
            # Gone since its stat: nothing to keep.
            out[number] = listed
            continue
        else:
            # A list another schema wrote, or one that cannot be read, is kept by its stamp as
            # a sum is, so it is not read again on every request until a refresh replaces it.
            sums = _Sums(listed)
        # Kept by the stamp read before the list: a list replaced meanwhile is read again.
        _keep(key, stamp, sums)
        out[number] = sums
    return out


def _kept_size(store: Path | None, sums: _Sums) -> GitChangeSize | None:
    """The kept size of *sums*' comparison, for a list the store made. Blocking: it can read
    one bank file beside *store*."""

    if sums.listed_from != "comparison" or sums.base is None or sums.head is None:
        return None
    from metabrowser.git.change_size import KEPT_SIZES, kept_change_size
    from metabrowser.git.process import GitLocation, repository_store_target

    if store is None:
        return KEPT_SIZES.get(("range", sums.base, sums.head))
    try:
        location = GitLocation.revision(repository_store_target(git_dir=store), sums.head)
    except (OSError, ValueError):
        return None
    return kept_change_size(location, sums.base, sums.head)


def _sizes(
    store: Path | None, found: dict[int, _Sums | SummaryAbsence]
) -> dict[int, GitChangeSize | None]:
    return {
        number: _kept_size(store, sums) if isinstance(sums, _Sums) and sums.reason is None else None
        for number, sums in found.items()
    }


def _wire(
    number: int, found: _Sums | SummaryAbsence, listing: bool, size: GitChangeSize | None
) -> FilesSummaryWire:
    reason = found if isinstance(found, str) else found.reason
    if isinstance(found, str) or reason is not None:
        held = None if isinstance(found, str) else found
        return FilesSummaryWire(
            number=number,
            state="absent",
            reason=reason,
            listing=listing,
            listed_from=None if held is None else held.listed_from,
            generation=None if held is None else held.generation,
            head=None if held is None else held.head,
            base=None if held is None else held.base,
            base_ref=None if held is None else held.base_ref,
            files=None,
            additions=None,
            deletions=None,
            exact=False,
            statuses=[],
            size=None,
        )
    return FilesSummaryWire(
        number=number,
        state="listed",
        reason=None,
        listing=listing,
        listed_from=found.listed_from,
        generation=found.generation,
        head=found.head,
        base=found.base,
        base_ref=found.base_ref,
        files=found.files,
        additions=found.additions,
        deletions=found.deletions,
        exact=found.exact,
        statuses=[StatusCount(status=status, count=count) for status, count in found.statuses],
        size=size,
    )


async def files_summary(
    repository: ListedRepository | None,
    listing: frozenset[int],
    numbers: tuple[int, ...],
    store: Path | None = None,
) -> FilesSummaryEnvelope:
    """Each of *numbers*' lists summed, in their order. *listing* is read on the loop.

    *store* is the Git directory of the repository store the lists were made in, where
    their sizes are kept, or ``None`` before one is attached.
    """

    if repository is None:
        return FilesSummaryEnvelope(source=None, rows=[])

    def read() -> tuple[dict[int, _Sums | SummaryAbsence], dict[int, GitChangeSize | None]]:
        found = _summed_lists(repository.home, repository.slug, numbers)
        return found, _sizes(store, found)

    found, sizes = await asyncio.to_thread(read)
    return FilesSummaryEnvelope(
        source=repository.source,
        rows=[_wire(number, found[number], number in listing, sizes[number]) for number in numbers],
    )


def listing_numbers(app: Any, numbers: tuple[int, ...]) -> frozenset[int]:
    """Which of *numbers* have a list refresh running or held in the prefetch lane. Memory
    alone, on the event loop that changes both."""

    from metabrowser.builtin_plugins.github.pull_files_route import files_job_key
    from metabrowser.builtin_plugins.github.pull_list_route import served_repository
    from metabrowser.builtin_plugins.github.pull_prefetch import lane_of
    from metabrowser.builtin_plugins.github.pull_route import pull_host
    from metabrowser.mirror_refresh import refresh_coordinator

    repository = served_repository(app)
    host = pull_host(app)
    coordinator = refresh_coordinator(app)
    if repository is None:
        return frozenset()
    held: set[int] = set()
    if host is not None:
        lane = lane_of(host.pulls)
        items = [*lane.queue, *([] if lane.running is None else [lane.running])]
        held = {item.number for item in items if item.kind == "files"}
    return frozenset(
        number
        for number in numbers
        if number in held
        or (coordinator is not None and coordinator.running(files_job_key(repository, number)))
    )


def envelope_etag(envelope: FilesSummaryEnvelope) -> str:
    digest = hashlib.sha256(json.dumps(envelope, sort_keys=True).encode()).hexdigest()
    return build_scoped_etag(f"pull-files-summary-{digest[:32]}")


def clear_kept_summaries() -> None:
    """Forget every sum kept, for a test that rewrites lists in place."""

    with _KEPT_LOCK:
        _KEPT.clear()


__all__ = [
    "MAX_KEPT_SUMMARIES",
    "MAX_SUMMARY_BYTES",
    "MAX_SUMMARY_NUMBERS",
    "PULL_FILES_SUMMARY_ROUTE",
    "FilesSummaryEnvelope",
    "FilesSummaryWire",
    "SummaryRequestError",
    "clear_kept_summaries",
    "envelope_etag",
    "files_summary",
    "listing_numbers",
    "named_numbers",
    "summary_numbers",
]
