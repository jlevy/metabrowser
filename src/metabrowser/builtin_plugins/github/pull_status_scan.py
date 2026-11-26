"""Every open pull request's operational status, read for the Pulls tab a page at a time.

The pull request page reads its own status with the checks listed (:mod:`.pull_status_read`).
The Pulls tab needs the same verdict for every row it draws, so :func:`scan_statuses` reads
the repository's open pull requests, last updated first as the tab orders its rows,
with one GraphQL query a page,
``PullStatuses``: each one's head and base, ``mergeable``, ``mergeStateStatus``,
``reviewDecision``, auto-merge, the merge queue entry, and its head's ``statusCheckRollup``
with its counts by state and no check (``contexts(first: 0)``). It builds each status as the
page's read does (:func:`~.pull_status_read.operational_status`), ``observed_by`` ``scan``,
and writes each page's in one catalog transaction, under the lock and after the network
(:func:`~.pull_catalog.write_pull_statuses`). A scan lists no check, so its statuses carry no
``listed_at`` and no required counts, unless a read kept beside them listed the same checks
and none moved since (:func:`~.pull_status.kept_observation`).

**When it runs.** The Pulls tab's ask, ``POST pulls-refresh``, starts it when it is due
(:func:`ask_status_scan`), after the list's own refresh is started and answered for, and
never instead of it:

- when the list's probe found a change (``changed``);
- when a fetch moved a base branch the last walk's pull requests target: the mirror's tip
  of it is not the one that walk saw as it started (``base_moved``,
  :meth:`StatusScan.base_moved`);
- otherwise every ``FULL_REFRESH_S`` while the tab asks (``periodic``);
- and once, ``MERGEABLE_SETTLE_S`` after a scan that left answers ``unknown``, of only the
  pages that held them (``settle``): GitHub computes ``mergeable`` after the read that
  first asks, as :data:`SCAN_ROWS` records;
- a reader's own Refresh (``retry``), which only a rate hold stops: this process's, or the
  one the last scan's stamp records (``reset_at``), which outlives a restart.

The ask never waits on Git. A reader's Refresh, a settle re-read, a change, and the clock
are decided from the stamp alone; only when none is due and a moved base would be does
the ask look at the mirror, in a job of its own after its answer (:func:`ask_status_scan`),
which starts the scan once it finds a base moved. A mirror Git cannot read has moved
nothing, and says so in the server log once until it can be read again.

Until the catalog holds a page of rows nothing is scanned, so a first visit's list comes
first. The scan reads as the catalog's reader, the account that read the list, with no
account check of its own: every page's ``viewer`` must be that reader, so after an account
switch the scan fails ``account_changed`` until the list's next scan reads as the new one.

Each scan spaces the next by :data:`SCAN_POINT_GAP_S` for each page it read, so the scans
the clock, a change, or a moved base asks for spend at most :data:`SCANS_POINTS_PER_HOUR`
for any repository. A reader's own Refresh and the settle re-read do not wait for that
spacing, but add their pages to it, so the next scan waits the longer. The process keeps
the stamp its last scan left as well as the file (:attr:`StatusScan.last`) and decides
from the later of the two, so the spacing holds when the cache cannot keep the file.

It is reader work, held as the catalog's scan is (:mod:`.gh_budget`): a rate hold stops
every scan; the periodic one waits below ``BACKGROUND_FLOOR`` of GraphQL and slows past
the process's ceiling (``full_read_interval``); one a change or a moved base asks for, and
the settle re-read, go below the floor, as the scan a change starts does, and stop past
the ceiling.
Speculative work never starts one.

**Failing alone.** The scan is a coordinator job of its own, so it never holds or fails the
list's refresh. A failed scan keeps every status kept before it, and how it ended is kept
in ``pulls/statuses.scan.json`` (:class:`ScanStamp`), which ``GET pull-statuses`` answers
(:mod:`.pull_statuses_route`); the next scan then waits a freshness window, or until a rate
limit lifts. The stamp is also what the next scan needs: when the last whole walk started
and which pull requests it read, the spacing, the pages to read once more, and the
mirror's tip of each base branch the walk's pull requests target, as the walk started.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import sqlite3
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Final, Literal
from weakref import WeakKeyDictionary

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from metabrowser.builtin_plugins.github import gh_budget, pull_list
from metabrowser.builtin_plugins.github.gh_lists import (
    READ_FAILURES,
    PullDataError,
    UnreadableItemError,
    as_dict,
    cache_unwritable,
    newer_cache,
    unknown_cache,
    utc_stamp,
)
from metabrowser.builtin_plugins.github.pull_catalog import (
    CatalogUnusableError,
    NewerCatalogError,
    UnknownCatalogError,
    failure_line,
    write_pull_statuses,
)
from metabrowser.builtin_plugins.github.pull_record import (
    MAX_REFRESH_MESSAGE_CHARS,
    Reader,
    Sha,
    Short,
    Timestamp,
    ensure_pulls_directory,
)
from metabrowser.builtin_plugins.github.pull_status import ChecksSummary, PullStatus
from metabrowser.builtin_plugins.github.pull_status_read import (
    answered_repository,
    ask_github,
    head_of,
    known_repository_id,
    operational_status,
    rollup_summary,
    unreadable_status,
)
from metabrowser.builtin_plugins.github.served_pull import FULL_REFRESH_S, MERGEABLE_SETTLE_S
from metabrowser.cache.atomic import RecordError, read_bytes_bounded
from metabrowser.cache.locks import run_lock_section, source_alias_lock
from metabrowser.cache.paths import source_pull_status_scan
from metabrowser.home import PrivateStorageError, write_private_file_atomic
from metabrowser.mirror_refresh import FRESHNESS_WINDOW_S

if TYPE_CHECKING:
    from metabrowser.builtin_plugins.github.pull_list import ListedRepository
    from metabrowser.mirror_refresh import RefreshCoordinator

log = logging.getLogger(__name__)

# The open pull requests one page asks for. Measured 2026-11-26 from a cloud container with
# gh 2.97.0, this query at each size, newest first. A page of 100, the most a connection
# returns, failed on NixOS/nixpkgs (13,041 open) every time: twice HTTP 502 after 10.5 s,
# GitHub's own limit, and once RESOURCE_LIMITS_EXCEEDED on every row's rollup. A page of 50
# took 10.0 to 10.9 s there and failed once in three with a 502. A page of 25 never failed
# in 15 reads: 2.6 to 7.4 s on nixpkgs, 5.4 s at the median; 1.1 to 5.6 s on cli/cli (56
# open); 2.0 to 2.2 s for this repository's 20 open. Most of the time is
# ``mergeStateStatus``: without it 56 rows of cli/cli took 2.8 to 3.3 s, with it 5.8 to
# 10.1 s. Every page cost 1 point, at every size, and was about 1 KB a row.
SCAN_ROWS: Final = 25
# The pages one scan reads: the 100 open pull requests updated last, a Pulls tab's first
# five screens at 20 rows each in the tab's order, and the 100 rows the plan priced. The
# order costs nothing: measured 2026-11-26 on this repository, a page of 25 cost 1 point
# and the same 25.7 KB by ``UPDATED_AT`` as by ``CREATED_AT``, in 1.4 to 1.6 s against
# 1.7 to 2.0 s, three reads each. At most four points and, on
# nixpkgs, about 22 s of pages, each in its own network slot. Rows past them show no
# readiness until their own page is read: a status the scan kept of one that has fallen
# past them is ``not_scanned`` once a walk has started after it (:mod:`.pull_statuses_route`).
MAX_SCAN_PAGES: Final = 4
# The most statuses one scan reads, and so the most pull requests a walk's stamp names.
MAX_SCAN_STATUSES: Final = SCAN_ROWS * MAX_SCAN_PAGES
# The spacing a scan leaves for each page it read before the next may start, whatever asks:
# a point a minute, so the scans of one repository spend at most 60 points an hour, a fifth
# of ``AUTOMATIC_CORE_PER_HOUR``, beside the catalog's own 40 scans an hour. A repository of
# one page is scanned every ``FULL_REFRESH_S``, and within a minute of a change a probe
# finds; one of four pages every four minutes. The pull request page reads its own status on
# every change its probes find, whatever this spacing.
SCAN_POINT_GAP_S: Final = 60.0
SCANS_POINTS_PER_HOUR: Final = round(3600 / SCAN_POINT_GAP_S)
# The most bases one stamp keeps: one for each pull request a scan reads, so every base the
# scanned pull requests target fits, however many stacks they make.
MAX_SCAN_BASES: Final = MAX_SCAN_STATUSES
# The most a stamp may be, written or read: 100 bases of 1 KB names and SHA-256 commits,
# 100 seven-digit numbers, four cursors of 1,024 characters, and a whole message came to
# 115,755 bytes serialized (2026-11-26), every other field at its largest too.
MAX_SCAN_STAMP_BYTES: Final = 128 * 1024
_MAX_CURSOR_CHARS: Final = 1024

_QUERY: Final = f"""query PullStatuses($owner:String!,$name:String!,$cursor:String) {{
  viewer {{ login }}
  rateLimit {{ cost }}
  repository(owner:$owner,name:$name) {{
    id nameWithOwner
    pullRequests(first:{SCAN_ROWS},after:$cursor,states:OPEN,orderBy:{{field:UPDATED_AT,direction:DESC}}) {{
      pageInfo {{ hasNextPage endCursor }}
      nodes {{
        number headRefOid baseRefName baseRefOid mergeable mergeStateStatus
        reviewDecision isInMergeQueue
        mergeQueueEntry {{ state position enqueuedAt estimatedTimeToMerge mergeQueue {{ url }} }}
        autoMergeRequest {{ mergeMethod enabledAt enabledBy {{ login }} }}
        statusCheckRollup {{
          state
          contexts(first:0) {{
            checkRunCountsByState {{ state count }}
            statusContextCountsByState {{ state count }}
          }}
        }}
      }}
    }}
  }}
}}"""

type ScanTrigger = Literal["retry", "settle", "changed", "base_moved", "periodic"]
type ScanStart = Literal["started", "joined", "not_due"]
type Cursor = Annotated[str, StringConstraints(min_length=1, max_length=_MAX_CURSOR_CHARS)]


class ScanStamp(BaseModel):
    """How the last scan ended, and what the next needs of it.

    ``outcome`` is ``succeeded`` or the failure's state, with its ``message`` and the
    ``reset_at`` of a rate limit. ``started_at`` and ``at`` are when it started and ended,
    and ``trigger`` why it ran. ``pages``, ``rows``, ``cost``, and ``unknown`` are the pages
    it read, the statuses they held, the GraphQL points GitHub reported for them, and how
    many statuses GitHub had not finished computing (``mergeable`` or ``mergeStateStatus``
    unknown).

    ``walked_at`` is when the last whole walk from the first pull request started, which
    the periodic scan counts from, and ``walked_numbers`` the pull requests it read, which
    the route answers a status kept before it of any other by (``not_scanned``);
    ``next_at`` the earliest a scan the spacing holds may start (:data:`SCAN_POINT_GAP_S`);
    ``settle_at`` and ``settle_cursors`` when the pages that held unknown answers are read
    once more, by the cursors they were read with, ``None`` for the first. ``bases`` is the
    mirror's tip of each base branch that walk's pull requests target, as the walk started
    (one first seen in it, as it ended), which a fetch that moves one is compared with; a
    branch the mirror does not hold is left out.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: Annotated[str, StringConstraints(pattern=r"^[a-z_]{1,40}$")]
    message: Annotated[str, StringConstraints(max_length=MAX_REFRESH_MESSAGE_CHARS)] | None = None
    reset_at: Timestamp | None = None
    at: Timestamp
    started_at: Timestamp
    reader: Reader | None = None
    trigger: ScanTrigger
    pages: int = Field(ge=0, le=MAX_SCAN_PAGES)
    rows: int = Field(ge=0, le=MAX_SCAN_STATUSES)
    cost: int = Field(ge=0)
    unknown: int = Field(ge=0, le=MAX_SCAN_STATUSES)
    walked_at: Timestamp | None = None
    walked_numbers: tuple[Annotated[int, Field(ge=1)], ...] = Field(
        default=(), max_length=MAX_SCAN_STATUSES
    )
    next_at: Timestamp
    settle_at: Timestamp | None = None
    settle_cursors: tuple[Cursor | None, ...] = Field(default=(), max_length=MAX_SCAN_PAGES)
    bases: dict[Short, Sha] = Field(default_factory=dict[str, str], max_length=MAX_SCAN_BASES)

    @field_validator("reset_at", "at", "started_at", "walked_at", "next_at", "settle_at")
    @classmethod
    def _a_real_moment(cls, value: str | None) -> str | None:
        if value is not None:
            datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        return value


def read_scan_stamp(home: Path, slug: str) -> ScanStamp | None:
    """How the last scan ended, or ``None``. Blocking and bounded; a file that cannot be read
    is none, and the next scan writes it again."""

    try:
        data = read_bytes_bounded(
            home, source_pull_status_scan(slug), max_bytes=MAX_SCAN_STAMP_BYTES
        )
        return ScanStamp.model_validate_json(data)
    except (FileNotFoundError, RecordError, PrivateStorageError, OSError, ValueError):
        return None


def write_scan_stamp(home: Path, slug: str, stamp: ScanStamp) -> None:
    """Keep *stamp* under the source's alias lock; call it through ``run_lock_section``."""

    data = stamp.model_dump_json().encode("utf-8")
    if len(data) > MAX_SCAN_STAMP_BYTES:
        raise ValueError("a scan's stamp is larger than its file may be")
    with source_alias_lock(home, slug):
        ensure_pulls_directory(home, slug)
        write_private_file_atomic(home, source_pull_status_scan(slug), data)


def _parse(stamp: str) -> datetime:
    return pull_list.parse_stamp(stamp)


# ── Reading ─────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ScanPage:
    """One page's statuses, the cursor after it when GitHub has more, and its cost."""

    statuses: tuple[PullStatus, ...]
    cursor: str | None
    cost: int


def _cost(data: Mapping[str, Any]) -> int:
    limit = data.get("rateLimit")
    cost = limit.get("cost") if isinstance(limit, dict) else None  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return cost if type(cost) is int and cost >= 0 else 1


def _scanned(value: object, observed_at: str) -> PullStatus:
    """One open pull request of the page as a status; unreadable if GitHub sent it otherwise."""

    pull = as_dict(value)
    if type(pull.get("number")) is not int:
        raise UnreadableItemError
    state, counts = rollup_summary(pull["statusCheckRollup"])
    return operational_status(
        pull,
        head=head_of(pull),
        checks=ChecksSummary(state=state, counts=counts),
        observed_at=observed_at,
        observed_by="scan",
    )


def scan_page(
    data: Mapping[str, Any],
    cursor: str | None,
    *,
    reader: str,
    repository_id: str | None,
) -> ScanPage:
    """The statuses one answer of the scan holds, once its viewer and repository are checked.

    The repository is the one asked for by GitHub's id, *repository_id*, the catalog's,
    under whatever name GitHub has it now (:func:`~.pull_status_read.answered_repository`).
    A pull request GitHub sent in a shape it does not document is left out, and its kept
    status stays; a page that is not a page is unreadable.
    """

    found = answered_repository(data, reader, repository_id=repository_id)
    connection = as_dict(found["pullRequests"])
    nodes = connection["nodes"]
    if not isinstance(nodes, list) or len(nodes) > SCAN_ROWS:  # pyright: ignore[reportUnknownArgumentType]
        raise UnreadableItemError
    info = as_dict(connection["pageInfo"])
    following = info.get("endCursor")
    more = info.get("hasNextPage") is True
    if more and (
        not isinstance(following, str)
        or not 1 <= len(following) <= _MAX_CURSOR_CHARS
        or following == cursor
        or not nodes
    ):
        raise UnreadableItemError
    observed_at = utc_stamp(pull_list.utc_now())
    statuses: dict[int, PullStatus] = {}
    for node in nodes:  # pyright: ignore[reportUnknownVariableType]
        try:
            status = _scanned(node, observed_at)
        except (*READ_FAILURES, ValueError) as exc:
            log.debug("left out a pull request status GitHub sent that could not be read: %r", exc)
            continue
        statuses.setdefault(status.number, status)
    return ScanPage(
        tuple(statuses.values()),
        following if more else None,  # pyright: ignore[reportArgumentType]
        _cost(data),
    )


async def read_scan_page(
    repository: ListedRepository, cursor: str | None, *, reader: str, repository_id: str | None
) -> ScanPage:
    """One page of the scan, after *cursor*, read as *reader*. Raises only :class:`PullDataError`."""

    variables = {"owner": repository.owner, "name": repository.repo, "cursor": cursor}
    data = await ask_github(_QUERY, variables, now=pull_list.utc_now())
    try:
        return scan_page(data, cursor, reader=reader, repository_id=repository_id)
    except (*READ_FAILURES, ValueError) as exc:
        raise unreadable_status() from exc


# ── Scanning ────────────────────────────────────────────────────


def _unknown(status: PullStatus) -> bool:
    return status.conflicts == "unknown" or status.merge_state == "unknown"


@dataclass(slots=True)
class _Progress:
    """What a scan has read so far, for its stamp whichever way it ends."""

    pages: int = 0
    rows: int = 0
    cost: int = 0
    unknown: int = 0
    settle: list[str | None] = field(default_factory=list[str | None])
    base_refs: set[str] = field(default_factory=set[str])
    numbers: set[int] = field(default_factory=set[int])


_STATUSES: Final = "the statuses of the open pull requests"


async def _keep(repository: ListedRepository, statuses: Sequence[PullStatus]) -> None:
    try:
        await run_lock_section(partial(write_pull_statuses, repository, statuses))
    except NewerCatalogError as exc:
        raise newer_cache(
            _STATUSES, str(exc), source=repository.source, checkout=repository.checkout
        ) from exc
    except UnknownCatalogError as exc:
        raise unknown_cache(
            _STATUSES, str(exc), source=repository.source, checkout=repository.checkout
        ) from exc
    except (PrivateStorageError, OSError, sqlite3.Error, CatalogUnusableError) as exc:
        log.warning(
            "the statuses of the pull requests of %s could not be kept: %s",
            repository.source,
            failure_line(exc),
        )
        raise cache_unwritable(
            _STATUSES, exc, source=repository.source, checkout=repository.checkout
        ) from exc


async def scan_statuses(
    repository: ListedRepository,
    *,
    reader: str,
    cursors: Sequence[str | None] | None,
    slot: asyncio.Semaphore | None,
    progress: _Progress,
    repository_id: str | None = None,
) -> None:
    """Read and keep the open pull requests' statuses as *reader*, a page at a time.

    With *cursors* ``None`` the walk starts at the first and follows GitHub's cursor for
    at most :data:`MAX_SCAN_PAGES`; otherwise it reads exactly the page after each cursor,
    ``None`` for the first, once. Each page is read in *slot*, a network slot it yields
    after, and kept in one transaction before the next is asked. *progress* holds what was
    read, however it ends. Raises only :class:`PullDataError`.
    """

    walk = cursors is None
    pending: list[str | None] = [None] if walk else list(cursors[:MAX_SCAN_PAGES])
    while pending and progress.pages < MAX_SCAN_PAGES:
        cursor = pending.pop(0)
        async with slot if slot is not None else contextlib.nullcontext():
            page = await read_scan_page(
                repository, cursor, reader=reader, repository_id=repository_id
            )
        progress.pages += 1
        progress.cost += page.cost
        progress.rows += len(page.statuses)
        unknown = sum(_unknown(status) for status in page.statuses)
        progress.unknown += unknown
        if unknown:
            progress.settle.append(cursor)
        # At most MAX_SCAN_STATUSES of each: a page holds at most SCAN_ROWS statuses.
        progress.base_refs.update(status.base_ref for status in page.statuses)
        progress.numbers.update(status.number for status in page.statuses)
        await _keep(repository, page.statuses)
        if walk and page.cursor is not None:
            pending.append(page.cursor)
        await asyncio.sleep(0)


def _spaced(previous: ScanStamp | None, started: datetime, pages: int) -> str:
    """When the next scan the spacing holds may start, after one of *pages* at *started*."""

    start = started
    if previous is not None:
        start = max(start, _parse(previous.next_at))
    return utc_stamp(start + timedelta(seconds=pages * SCAN_POINT_GAP_S))


def _stamp(
    previous: ScanStamp | None,
    trigger: ScanTrigger,
    started: datetime,
    progress: _Progress,
    *,
    reader: str | None,
    failure: PullDataError | None,
    bases: Mapping[str, str],
) -> ScanStamp:
    """The stamp a scan leaves, from what it read and how it ended.

    *bases* are the mirror's tips of the walk's base branches. Only a whole walk replaces
    what the last one kept, its clock, the pull requests it read, and those tips: a settle
    re-read or a failed walk read only some of the pull requests a moved base would ask for.
    """

    now = pull_list.utc_now()
    ended = utc_stamp(now)
    whole = trigger != "settle" and failure is None
    if whole:
        walked_at: str | None = utc_stamp(started)
        walked_numbers = tuple(sorted(progress.numbers))
        kept_bases = dict(bases)
    else:
        walked_at = None if previous is None else previous.walked_at
        walked_numbers = () if previous is None else previous.walked_numbers
        kept_bases = {} if previous is None else dict(previous.bases)
    settle = whole and bool(progress.settle)
    return ScanStamp(
        outcome="succeeded" if failure is None else failure.state,
        message=None if failure is None else str(failure)[:MAX_REFRESH_MESSAGE_CHARS],
        reset_at=None if failure is None else failure.reset_at,
        at=ended,
        started_at=utc_stamp(started),
        reader=reader,
        trigger=trigger,
        pages=progress.pages,
        rows=progress.rows,
        cost=progress.cost,
        unknown=progress.unknown,
        walked_at=walked_at,
        walked_numbers=walked_numbers,
        next_at=_spaced(previous, started, progress.pages),
        settle_at=utc_stamp(now + timedelta(seconds=MERGEABLE_SETTLE_S)) if settle else None,
        settle_cursors=tuple(progress.settle) if settle else (),
        bases=kept_bases,
    )


_JOB_STOPPED: Final = "the scan stopped on an unexpected error, which the server log names"

type MirrorTips = Callable[[Sequence[str]], Awaitable[dict[str, str] | None]]
"""The mirror's tip of each of some base branches it holds, by name, or ``None`` when Git
cannot read it (:meth:`StatusScan.mirror_tips`)."""


async def run_scan(
    repository: ListedRepository,
    trigger: ScanTrigger,
    *,
    reader: str,
    previous: ScanStamp | None,
    slot: asyncio.Semaphore | None = None,
    tips: MirrorTips | None = None,
    remember: Callable[[ScanStamp], None] | None = None,
) -> ScanStamp:
    """Scan as *trigger* asks, after *previous*, and keep how it ended; the stamp it kept.

    Every page's ``viewer`` must be *reader*, the catalog's, and its repository the
    catalog's by GitHub's id, whatever its name now. A walk asks *tips* for the mirror's
    tip of each base the last walk's pull requests target before its first page, and of
    any base first seen in it after its last; with no *tips* it keeps none. A failure
    keeps every status kept before it, and is the stamp's outcome; an unexpected
    error is kept as ``gh_failed`` and raised, for the coordinator to log. Every stamp it
    leaves is handed to *remember* before it is written, so a stamp the cache cannot keep
    still spaces the next scan in this process.
    """

    started = pull_list.utc_now()
    progress = _Progress()
    failure: PullDataError | None = None
    walk = trigger != "settle"
    cursors = previous.settle_cursors if not walk and previous is not None else None
    known = sorted(previous.bases) if walk and previous is not None else []
    at_start = (await tips(known) or {}) if tips is not None and known else {}
    try:
        identity = await asyncio.to_thread(known_repository_id, repository)
        await scan_statuses(
            repository,
            reader=reader,
            cursors=cursors,
            slot=slot,
            progress=progress,
            repository_id=identity,
        )
    except PullDataError as exc:
        log.debug("scanning the statuses of %s failed: %s", repository.source, exc)
        failure = exc
    except Exception:
        stopped = PullDataError("gh_failed", _JOB_STOPPED)
        await _leave(
            repository,
            _stamp(previous, trigger, started, progress, reader=reader, failure=stopped, bases={}),
            remember,
        )
        raise
    bases: dict[str, str] = {}
    if walk and failure is None:
        first_seen = sorted(progress.base_refs.difference(known))
        at_end = (await tips(first_seen) or {}) if tips is not None and first_seen else {}
        seen = at_start | at_end
        bases = {name: seen[name] for name in sorted(progress.base_refs) if name in seen}
    stamp = _stamp(
        previous, trigger, started, progress, reader=reader, failure=failure, bases=bases
    )
    await _leave(repository, stamp, remember)
    return stamp


async def _leave(
    repository: ListedRepository,
    stamp: ScanStamp,
    remember: Callable[[ScanStamp], None] | None,
) -> None:
    if remember is not None:
        remember(stamp)
    try:
        await run_lock_section(partial(write_scan_stamp, repository.home, repository.slug, stamp))
    except (PrivateStorageError, OSError, ValueError) as exc:
        # Only the file is lost: the statuses the scan read are kept, and this process
        # spaces the next scan by the stamp it remembers.
        log.warning(
            "how the status scan of %s ended could not be kept: %s",
            repository.source,
            failure_line(exc),
        )


# ── When it runs ────────────────────────────────────────────────


def _admits_change(now: datetime) -> bool:
    """A scan a change asks for, or the settle re-read: below the floor too, not past the
    process's ceiling, and never during a rate hold."""

    return gh_budget.admission(("graphql",), now=now, floor=0.0).admitted


def _admits_periodic(now: datetime) -> bool:
    """The periodic scan: above the GraphQL floor, as background work is; the ceiling slows
    it instead (:func:`.gh_budget.full_read_interval`)."""

    return gh_budget.admission(("graphql",), now=now, ceiling=False).admitted


def scan_due(
    stamp: ScanStamp | None,
    *,
    now: datetime,
    retry: bool = False,
    changed: bool = False,
    base_moved: bool = False,
) -> ScanTrigger | None:
    """Why a scan is due at *now* after the one *stamp* records, or ``None``; see the module.

    *changed* says the list's probe found a change no walk has read since, and *base_moved*
    that a fetch moved a base branch the scanned pull requests target.
    """

    if gh_budget.held_until(now) is not None or gh_budget.speculating():
        return None
    # The last scan's rate limit holds a reader's Refresh too, as the list's own stamp holds
    # its refresh: this process's hold is gone after a restart, and the stamp's is not.
    if stamp is not None and stamp.reset_at is not None and now < _parse(stamp.reset_at):
        return None
    if retry:
        return "retry"
    if stamp is not None:
        if stamp.outcome != "succeeded" and now - _parse(stamp.at) <= timedelta(
            seconds=FRESHNESS_WINDOW_S
        ):
            return None
        if stamp.settle_at is not None and now >= _parse(stamp.settle_at) and _admits_change(now):
            return "settle"
        if now < _parse(stamp.next_at):
            return None
    if (changed or base_moved) and _admits_change(now):
        return "changed" if changed else "base_moved"
    walked = None if stamp is None else stamp.walked_at
    interval = timedelta(seconds=gh_budget.full_read_interval(FULL_REFRESH_S, now=now))
    if (walked is None or now - _parse(walked) > interval) and _admits_periodic(now):
        return "periodic"
    return None


type _RefStat = tuple[tuple[str, int, int, int] | None, ...]


def _refs_stat(git_dir: Path, refs: Sequence[str]) -> _RefStat:
    """What a fetch that moved one of *refs* would change on disk: each loose ref's file,
    and ``packed-refs``, by inode, size, and modification time. Git renames a lock over a
    ref it writes, so a moved ref has a new inode whatever its time."""

    stats: list[tuple[str, int, int, int] | None] = []
    for name in ("packed-refs", *refs):
        try:
            info = os.lstat(git_dir / name)
        except (OSError, ValueError):
            stats.append(None)
            continue
        stats.append((name, info.st_ino, info.st_size, info.st_mtime_ns))
    return tuple(stats)


@dataclass(eq=False)
class StatusScan:
    """One repository's scan in this process: what waits for its next walk, the last stamp
    it left, and its last look at the mirror.

    ``pending`` holds the triggers a walk has not yet answered, a change the list's probe
    found or a base a fetch moved, which the spacing may hold for a while. ``last`` is the
    stamp the last scan here left, whether or not its file took it, and the ask decides
    from the later of it and the file (:meth:`latest`). ``_looked`` is what the last look at
    the mirror's base branches found on disk, and the tips it compared them with, so a look
    asks Git only once one of them has changed (:meth:`base_moved`); ``_unreadable`` says
    the last read of the mirror failed, which is logged once until one succeeds.
    """

    source: str
    pending: set[Literal["changed", "base_moved"]] = field(
        default_factory=set[Literal["changed", "base_moved"]]
    )
    last: ScanStamp | None = None
    _looked: tuple[_RefStat, dict[str, str]] | None = field(default=None, repr=False)
    _unreadable: bool = field(default=False, repr=False)

    @property
    def key(self) -> str:
        """The scan's coordinator job key, which ``GET pull-statuses`` asks about."""

        return _scan_key(self.source)

    @property
    def look_key(self) -> str:
        """The job key of a look at the mirror's base branches (:func:`ask_status_scan`)."""

        return f"{self.source}:pull-statuses-bases"

    def remember(self, stamp: ScanStamp) -> None:
        """Keep *stamp*, the one a scan here just left, beside the file."""

        self.last = stamp

    def latest(self, kept: ScanStamp | None) -> ScanStamp | None:
        """The later of *kept*, the stamp on disk, and the one the last scan here left.

        The file is another process's when it is the later, and this process's own when it
        took it; when the cache could not keep the file, the one remembered is the later,
        so the spacing, the walk's clock, and the settle re-read hold all the same.
        """

        stamps = [stamp for stamp in (self.last, kept) if stamp is not None]
        return max(stamps, key=lambda stamp: (stamp.at, stamp.started_at), default=None)

    async def mirror_tips(self, git_dir: Path, names: Sequence[str]) -> dict[str, str] | None:
        """The mirror's tip of each base branch of *names* it holds, by name, in one
        ``for-each-ref``; ``None`` when Git cannot read the mirror."""

        from metabrowser.cache.origin import BRANCH_MIRROR_PREFIX
        from metabrowser.cache.resolve import ref_tips
        from metabrowser.git.process import GitError, repository_store_target

        refs = _mirror_refs(names)
        try:
            tips = await ref_tips(repository_store_target(git_dir=git_dir), sorted(refs))
        except (GitError, OSError) as exc:
            if not self._unreadable:
                log.warning(
                    "the status scan of %s could not read the mirror's base branches, so "
                    "no fetch moves one until it can: %s",
                    self.source,
                    failure_line(exc),
                )
            self._unreadable = True
            return None
        self._unreadable = False
        return {
            ref.removeprefix(BRANCH_MIRROR_PREFIX): tip for ref, tip in tips.items() if ref in refs
        }

    async def base_moved(self, stamp: ScanStamp | None, git_dir: Path | None) -> bool:
        """Whether a fetch moved a base the last walk's pull requests target since it started.

        That is a base whose tip in the mirror is not the one the walk saw
        (:attr:`ScanStamp.bases`), one the mirror no longer holds among them. Asks Git, one
        ``for-each-ref``, only when a ref's file or ``packed-refs`` changed on disk, or the
        stamp's tips did, since the last look; a mirror Git cannot read has moved nothing,
        and a server with no store has no mirror to look at.
        """

        if git_dir is None or stamp is None or not stamp.bases:
            return False
        refs = _mirror_refs(stamp.bases)
        seen = await asyncio.to_thread(_refs_stat, git_dir, sorted(refs))
        looked = (seen, dict(stamp.bases))
        if looked == self._looked:
            return False
        self._looked = looked
        tips = await self.mirror_tips(git_dir, sorted(stamp.bases))
        return tips is not None and any(
            tips.get(name) != tip for name, tip in stamp.bases.items() if _mirror_ref(name) in refs
        )


def _scan_key(source: str) -> str:
    return f"{source}:pull-statuses"


def _mirror_ref(name: str) -> str:
    from metabrowser.cache.origin import BRANCH_MIRROR_PREFIX

    return BRANCH_MIRROR_PREFIX + name


def _mirror_refs(names: Iterable[str]) -> set[str]:
    """The mirror refs of the base branches *names*, those that are valid ref names."""

    from metabrowser.git.ref_names import is_valid_ref_name

    return {ref for ref in map(_mirror_ref, names) if is_valid_ref_name(ref)}


_SCANS: WeakKeyDictionary[RefreshCoordinator, dict[str, StatusScan]] = WeakKeyDictionary()
# A server lists one repository, and a checkout whose origin changes another: bounded as
# the list's probes are, oldest dropped first.
_MAX_SCANNED_SOURCES: Final = 8


def status_scan(coordinator: RefreshCoordinator, source: str) -> StatusScan:
    """The scan of *source* under *coordinator*, made on first use. On the event loop."""

    scans = _SCANS.setdefault(coordinator, {})
    scan = scans.get(source)
    if scan is None:
        while len(scans) >= _MAX_SCANNED_SOURCES:
            del scans[next(iter(scans))]
        scan = scans[source] = StatusScan(source)
    return scan


def scanning(coordinator: RefreshCoordinator | None, source: str) -> bool:
    """Whether *source*'s scan runs now under *coordinator*. On the event loop."""

    if coordinator is None:
        return False
    return coordinator.running(_scan_key(source))


def _scan_inputs(repository: ListedRepository) -> ScanStamp | None:
    """The last scan's stamp. Blocking and bounded."""

    return read_scan_stamp(repository.home, repository.slug)


async def ask_status_scan(
    repository: ListedRepository | None,
    coordinator: RefreshCoordinator | None,
    *,
    reader: str | None,
    git_dir: Path | None,
    retry: bool = False,
    changed: bool = False,
) -> ScanStart:
    """Start the scan when it is due (:func:`scan_due`), or join the one running.

    The list's ask, after its own refresh has started: *reader* is the catalog's, as the
    ask read it before that start, ``None`` with no catalog of this repository's rows yet;
    *changed* says its probe found a change, and *retry* is a reader's own Refresh. It
    decides from the later of the stamp on disk and the one this process remembers
    (:meth:`StatusScan.latest`), and never waits on Git: when nothing else is due and a
    moved base would be, it starts a look at the mirror in *git_dir* as a job of its own
    and answers ``not_due``, and the look starts the scan once it finds a base moved.
    Never raises: whatever goes wrong here is logged and answered ``not_due``, so the
    list's answer stands.
    """

    if repository is None or coordinator is None or coordinator.closed or reader is None:
        return "not_due"
    scan = status_scan(coordinator, repository.source)
    if changed:
        scan.pending.add("changed")
    try:
        if coordinator.running(scan.key):
            return "joined"
        stamp = scan.latest(await asyncio.to_thread(_scan_inputs, repository))
        if coordinator.running(scan.key):
            return "joined"
        started = _start_due(
            repository, coordinator, scan, stamp, reader=reader, git_dir=git_dir, retry=retry
        )
        if started is not None:
            return started
        if _look_due(scan, stamp, git_dir):
            look = partial(_look_job, repository, coordinator, scan, reader, git_dir)
            coordinator.start(scan.look_key, look, network=False)
        return "not_due"
    except Exception:
        log.exception("starting the status scan of %s failed", repository.source)
        return "not_due"


def _start_due(
    repository: ListedRepository,
    coordinator: RefreshCoordinator,
    scan: StatusScan,
    stamp: ScanStamp | None,
    *,
    reader: str,
    git_dir: Path | None,
    retry: bool,
) -> ScanStart | None:
    """Start the scan when it is due after *stamp*; ``None`` when it is not. On the loop."""

    trigger = scan_due(
        stamp,
        now=pull_list.utc_now(),
        retry=retry,
        changed="changed" in scan.pending,
        base_moved="base_moved" in scan.pending,
    )
    if trigger is None:
        return None
    if trigger != "settle":
        scan.pending.clear()
    work = partial(_scan_job, repository, coordinator, scan, trigger, reader, stamp, git_dir)
    with gh_budget.readers_own() if retry else contextlib.nullcontext():
        return coordinator.start(scan.key, work, network=False)


def _look_due(scan: StatusScan, stamp: ScanStamp | None, git_dir: Path | None) -> bool:
    """Whether only a moved base could start a scan now, so the mirror is worth a look."""

    if git_dir is None or stamp is None or not stamp.bases or "base_moved" in scan.pending:
        return False
    return scan_due(stamp, now=pull_list.utc_now(), base_moved=True) == "base_moved"


async def _look_job(
    repository: ListedRepository,
    coordinator: RefreshCoordinator,
    scan: StatusScan,
    reader: str,
    git_dir: Path | None,
) -> None:
    """Look at the mirror's base branches, and start the scan if a fetch moved one."""

    stamp = scan.latest(await asyncio.to_thread(_scan_inputs, repository))
    if not await scan.base_moved(stamp, git_dir):
        return
    scan.pending.add("base_moved")
    if coordinator.closed or coordinator.running(scan.key):
        return
    _start_due(repository, coordinator, scan, stamp, reader=reader, git_dir=git_dir, retry=False)


async def _scan_job(
    repository: ListedRepository,
    coordinator: RefreshCoordinator,
    scan: StatusScan,
    trigger: ScanTrigger,
    reader: str,
    previous: ScanStamp | None,
    git_dir: Path | None,
) -> None:
    tips = None if git_dir is None else partial(scan.mirror_tips, git_dir)
    await run_scan(
        repository,
        trigger,
        reader=reader,
        previous=previous,
        slot=coordinator.slot(),
        tips=tips,
        remember=scan.remember,
    )


__all__ = [
    "MAX_SCAN_BASES",
    "MAX_SCAN_PAGES",
    "MAX_SCAN_STAMP_BYTES",
    "MAX_SCAN_STATUSES",
    "SCANS_POINTS_PER_HOUR",
    "SCAN_POINT_GAP_S",
    "SCAN_ROWS",
    "MirrorTips",
    "ScanPage",
    "ScanStamp",
    "ScanStart",
    "ScanTrigger",
    "StatusScan",
    "ask_status_scan",
    "read_scan_page",
    "read_scan_stamp",
    "run_scan",
    "scan_due",
    "scan_page",
    "scan_statuses",
    "scanning",
    "status_scan",
    "write_scan_stamp",
]
