"""What the changed-files routes answer, built from the cache and memory alone.

``GET /api/plugin/github/pull-files?number=<n>&offset=&limit=`` never runs gh or Git and
never waits on the network. It answers one of:

- ``absent``: nothing to show, with a ``reason``: this server serves no GitHub repository
  (``not_github``), or no usable list is cached (``not_cached``, ``schema_mismatch``,
  ``unreadable``);
- ``pending``: no list yet, and a refresh is running;
- ``current``: a list of the pull request as it is now, by the freshness rule below;
- ``stale``: an older list, still shown.

**Freshness.** A local list belongs to both resolved comparison endpoints, ``base`` and
``head``, and is current only while the record names that exact comparison. An older local
list without a saved base, or a record with no comparison, is stale. GitHub-derived lists
do not depend on locally resolved endpoints: discovering a comparison later leaves their
freshness on the provider's head, ``updated_at``, and account rules. A GitHub list names
the head commit and base branch it was read for (``head``, ``base_ref``), and is current
while they are the pull request's as last known: the newer of the record and the cached
list row, by ``updated_at``. A comment, a review, or a label changes neither. When the list
or that newer source names no head, the list is current while the pull request's
``updated_at`` is no newer than the list's ``fetched_at``, because any push updates it, and
with neither known it ages by the refresh coordinator's window. A list another account
read, or one whose last refresh ended ``account_changed``, is stale, as a list of pull
requests is. ``fetched_at`` is this machine's clock and ``updated_at`` GitHub's, so under
that fallback a clock behind GitHub's can make a new list stale; the window holds such a
list to one attempt a window.

**The count is honest.** ``fetched`` is how many rows are held. While ``complete`` is false
the list is filling, or stopped part-way, and ``last_page`` is the page count GitHub's
``Link`` header gave, which counts pages, not files. ``capped`` says GitHub stopped at the
most it lists, 3,000, and ``truncated`` that an item could not be read and was left out.

Rows come as a window of the list's order, by ``offset`` and ``limit``: all of them by
default, none with ``limit=0``, and from ``offset`` on for a reader that already holds the
rows before it, as a tree filling page by page does. Every row carries its path as the
identity, and ``display``, the same path through the display rule a pinned tree's names use
(``display_segment``), for painting as text.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
import re
import stat
import threading
from collections.abc import AsyncGenerator, Callable, Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import timedelta
from functools import partial
from pathlib import Path
from typing import Any, Final, Literal, TypedDict

from metabrowser.builtin_plugins.github import pull_list
from metabrowser.builtin_plugins.github.gh_lists import PullDataError, utc_stamp
from metabrowser.builtin_plugins.github.pull_list import (
    MAX_PULL_FILES,
    FileListSource,
    KnownHead,
    ListedRepository,
    LocalComparison,
    PullFileList,
    rate_limit_holds,
    read_files_refresh,
    read_pull_files,
    refresh_is_due,
    write_files_refresh,
)
from metabrowser.builtin_plugins.github.pull_list_route import (
    LastRefresh,
    cached_list_row,
    served_repository,
)
from metabrowser.builtin_plugins.github.pull_record import (
    PullRecord,
    PullRefreshStamp,
    RecordAbsence,
)
from metabrowser.builtin_plugins.github.pull_route import cached_pull_record, pull_host
from metabrowser.cache.paths import MAX_PULL_REQUEST_NUMBER, source_pull_files
from metabrowser.http_caching import build_scoped_etag
from metabrowser.invisible_chars import display_segment
from metabrowser.mirror_refresh import (
    FRESHNESS_WINDOW_S,
    MAX_PULL_JOBS,
    RefreshCoordinator,
    refresh_coordinator,
)
from metabrowser.view_routes import parse_pull_number

PULL_FILES_ROUTE: Final = "/api/plugin/github/pull-files"
NUMBER_REQUIRED: Final = '"number" is a pull-request number'
_REFRESH_FIELDS: Final = frozenset({"number", "retry"})
_COUNT = re.compile(r"^(?:0|[1-9][0-9]{0,3})$")
_JOB_STOPPED: Final = "the refresh stopped on an unexpected error, which the server log names"

type FilesState = Literal["absent", "pending", "current", "stale"]
type FilesAbsence = Literal["not_github"] | RecordAbsence
type FilesRefreshStart = Literal["started", "joined", "not_due", "too_many"]
# A network slot a file list's job takes for each request, as ``pull_files_refresh`` names it.
type _Slot = Callable[[], AbstractAsyncContextManager[object]]


class FilesRequestError(Exception):
    """A request the file-list routes refuse. ``str()`` names only the request."""


class FileRowWire(TypedDict):
    """One row as the route answers it."""

    path: str
    previous_path: str | None
    status: str
    additions: int | None
    deletions: int | None
    display: str
    previous_display: str | None


class PullFilesEnvelope(TypedDict):
    """What ``GET /api/plugin/github/pull-files`` returns."""

    state: FilesState
    reason: FilesAbsence | None
    source: str | None
    number: int
    listed_from: FileListSource | None
    fetched_at: str | None
    generation: str | None
    reader: str | None
    head: str | None
    base: str | None
    base_ref: str | None
    fresh_for_s: float
    refreshing: bool
    last_refresh: LastRefresh | None
    fetched: int
    pages: int
    last_page: int | None
    complete: bool
    capped: bool
    truncated: bool
    offset: int
    limit: int
    rows: list[FileRowWire]


@dataclass(frozen=True, slots=True)
class FilesWindow:
    """Which pull request a ``GET`` asks for, and which of its cached rows."""

    number: int
    offset: int = 0
    limit: int = MAX_PULL_FILES


def _count(params: Mapping[str, str], name: str, default: int) -> int:
    value = params.get(name, str(default))
    if not _COUNT.match(value) or int(value) > MAX_PULL_FILES:
        raise FilesRequestError(f'"{name}" is a whole number from 0 to {MAX_PULL_FILES}')
    return int(value)


def files_window(params: Mapping[str, str]) -> FilesWindow:
    """The window a ``GET`` names, or :class:`FilesRequestError`. ``number`` is required."""

    number = parse_pull_number(params.get("number", ""))
    if number is None:
        raise FilesRequestError(NUMBER_REQUIRED)
    return FilesWindow(number, _count(params, "offset", 0), _count(params, "limit", MAX_PULL_FILES))


@dataclass(frozen=True, slots=True)
class FilesRefreshRequest:
    """What a ``POST`` asks for. *retry* is a reader's own **Retry**."""

    number: int
    retry: bool


def files_refresh_request(body: Mapping[str, object]) -> FilesRefreshRequest:
    """What a ``POST`` body names, or :class:`FilesRequestError`."""

    if set(body) - _REFRESH_FIELDS:
        raise FilesRequestError('a refresh request names only "number" and "retry"')
    number = body.get("number")
    if (
        not isinstance(number, int)
        or isinstance(number, bool)
        or not 1 <= number <= MAX_PULL_REQUEST_NUMBER
    ):
        raise FilesRequestError(NUMBER_REQUIRED)
    retry = body.get("retry", False)
    if not isinstance(retry, bool):
        raise FilesRequestError('"retry" is true or false')
    return FilesRefreshRequest(number, retry)


@dataclass(frozen=True, slots=True)
class FilesView:
    """What the envelope needs from memory, read on the event loop that owns it.

    ``git_dir`` is the served mirror's store, where a local comparison is listed.
    """

    number: int
    repository: ListedRepository | None
    coordinator: RefreshCoordinator | None
    refreshing: bool
    git_dir: Path | None


def _job_key(repository: ListedRepository, number: int) -> str:
    """The single-flight key of one file list's refresh."""

    return f"{repository.slug}:pull/{number}/files"


def files_view(app: Any, number: int) -> FilesView:
    """The server's repository and whether the list of *number* is refreshing. Reads nothing."""

    repository = served_repository(app)
    coordinator = refresh_coordinator(app)
    host = pull_host(app)
    refreshing = (
        repository is not None
        and coordinator is not None
        and coordinator.running(_job_key(repository, number))
    )
    git_dir = host.pulls.git_dir if host is not None else None
    return FilesView(number, repository, coordinator, refreshing, git_dir)


def display_path(path: str) -> str:
    """*path* as a pinned tree displays a name: each segment through ``display_segment``.

    The rule replaces characters one for one and never a ``/``, so the display's segments
    are the path's.
    """

    return "/".join(
        display_segment(segment.encode("utf-8", "surrogatepass")) for segment in path.split("/")
    )


def _wire_rows(listed: PullFileList) -> list[FileRowWire]:
    return [
        FileRowWire(
            path=row.path,
            previous_path=row.previous_path,
            status=row.status,
            additions=row.additions,
            deletions=row.deletions,
            display=display_path(row.path),
            previous_display=(
                display_path(row.previous_path) if row.previous_path is not None else None
            ),
        )
        for row in listed.rows
    ]


@dataclass(frozen=True, slots=True)
class _Parsed:
    stamp: tuple[int, int, int]
    listed: PullFileList
    rows: list[FileRowWire]


# File lists parsed for this route, by home, slug, and number, each with the inode,
# modification time, and size it was read at, as the list route keeps its lists. A list is
# replaced atomically, page by page while it fills, so each page is parsed once.
_PARSED: dict[tuple[str, str, int], _Parsed] = {}
_PARSED_LOCK: Final = threading.Lock()
_MAX_PARSED: Final = 16


def _file_stamp(home: Path, slug: str, number: int) -> tuple[int, int, int] | None:
    try:
        status = os.lstat(home / source_pull_files(slug, number))
    except OSError:
        return None
    if not stat.S_ISREG(status.st_mode):
        return None
    return status.st_ino, status.st_mtime_ns, status.st_size


def _cached_files(
    home: Path, slug: str, number: int
) -> tuple[PullFileList | RecordAbsence, list[FileRowWire]]:
    key = (str(home), slug, number)
    stamp = _file_stamp(home, slug, number)
    with _PARSED_LOCK:
        hit = _PARSED.get(key)
    if hit is not None and stamp is not None and hit.stamp == stamp:
        return hit.listed, hit.rows
    listed = read_pull_files(home, slug, number)
    if not isinstance(listed, PullFileList):
        return listed, []
    rows = _wire_rows(listed)
    if stamp is not None:
        with _PARSED_LOCK:
            if key not in _PARSED and len(_PARSED) >= _MAX_PARSED:
                _PARSED.pop(next(iter(_PARSED)))
            _PARSED[key] = _Parsed(stamp, listed, rows)
    return listed, rows


@dataclass(frozen=True, slots=True)
class _Facts:
    """The cached pull request, and the newest known provider update time and head.

    ``head`` and ``base_ref`` are the head commit and base branch name of the newer of the
    record and the catalog row, by ``updated_at``; ``None`` when that one does not say.
    """

    updated_at: str | None
    record: PullRecord | None
    head: str | None = None
    base_ref: str | None = None

    @property
    def known_head(self) -> KnownHead:
        return self.head, self.base_ref


def _facts(home: Path, slug: str, number: int) -> _Facts:
    record, _dumped, _revision = cached_pull_record(home, slug, number)
    held = record if isinstance(record, PullRecord) else None
    row = cached_list_row(home, slug, number)
    known: list[tuple[str, str | None, str | None]] = []
    if held is not None:
        known.append((held.pull.updated_at, held.pull.head.sha, held.pull.base.ref))
    if row is not None:
        known.append((row.updated_at, row.head_oid, row.base_ref))
    # On a tie the record, which always names its head, is the one taken, unless the row
    # names another: a push within the second the record was read leaves the times equal.
    newest = max(
        known,
        key=lambda fact: (fact[0], held is not None and fact[1] not in (None, held.pull.head.sha)),
        default=None,
    )
    if newest is None:
        return _Facts(updated_at=None, record=held)
    return _Facts(updated_at=newest[0], record=held, head=newest[1], base_ref=newest[2])


def known_head(home: Path, slug: str, number: int) -> KnownHead:
    """The head and base branch the pull request has as last known. Blocking and bounded."""

    return _facts(home, slug, number).known_head


def _read_by_another(listed: PullFileList, stamp: PullRefreshStamp | None) -> bool:
    """Whether a refresh since *listed* says the active account is not the one that read it."""

    if stamp is None or pull_list.parse_stamp(stamp.at) < pull_list.parse_stamp(listed.fetched_at):
        return False
    return stamp.outcome == "account_changed" or stamp.reader not in (None, listed.reader)


def _head_moved(listed: PullFileList, facts: _Facts) -> bool | None:
    """Whether GitHub's list was read for another head or base than the newest known one.

    ``None`` when the list or the newest source names no head, so it cannot say.
    """

    if listed.listed_from != "github" or listed.head is None or facts.head is None:
        return None
    bases = (listed.base_ref, facts.base_ref)
    return listed.head != facts.head or (None not in bases and bases[0] != bases[1])


def _state(listed: PullFileList, stamp: PullRefreshStamp | None, facts: _Facts) -> FilesState:
    if listed.listed_from == "comparison":
        comparison = facts.record.comparison if facts.record is not None else None
        current = (
            comparison is not None
            and listed.base is not None
            and (listed.base, listed.head) == (comparison.base, comparison.head)
        )
        return "current" if current else "stale"
    if _read_by_another(listed, stamp):
        return "stale"
    moved = _head_moved(listed, facts)
    if moved is not None:
        return "stale" if moved else "current"
    fetched = pull_list.parse_stamp(listed.fetched_at)
    if facts.updated_at is not None:
        fresh = pull_list.parse_stamp(facts.updated_at) <= fetched
    else:
        fresh = pull_list.utc_now() - fetched <= timedelta(seconds=FRESHNESS_WINDOW_S)
    return "current" if fresh else "stale"


def _last_refresh(stamp: PullRefreshStamp | None) -> LastRefresh | None:
    if stamp is None:
        return None
    return LastRefresh(
        outcome=stamp.outcome, message=stamp.message, reset_at=stamp.reset_at, at=stamp.at
    )


def pull_files_envelope(view: FilesView, window: FilesWindow) -> PullFilesEnvelope:
    """The envelope for one window of a pull request's files. Blocking and bounded."""

    empty = PullFilesEnvelope(
        state="absent",
        reason="not_github",
        source=None,
        number=view.number,
        listed_from=None,
        fetched_at=None,
        generation=None,
        reader=None,
        head=None,
        base=None,
        base_ref=None,
        fresh_for_s=FRESHNESS_WINDOW_S,
        refreshing=view.refreshing,
        last_refresh=None,
        fetched=0,
        pages=0,
        last_page=None,
        complete=False,
        capped=False,
        truncated=False,
        offset=window.offset,
        limit=window.limit,
        rows=[],
    )
    repository = view.repository
    if repository is None:
        return empty
    home, slug = repository.home, repository.slug
    stamp = read_files_refresh(home, slug, view.number)
    listed, rows = _cached_files(home, slug, view.number)
    last_refresh = _last_refresh(stamp)
    if not isinstance(listed, PullFileList):
        return {
            **empty,
            "state": "pending" if view.refreshing else "absent",
            "reason": None if view.refreshing else listed,
            "source": repository.source,
            "last_refresh": last_refresh,
        }
    return {
        **empty,
        "state": _state(listed, stamp, _facts(home, slug, view.number)),
        "reason": None,
        "source": listed.source,
        "listed_from": listed.listed_from,
        "fetched_at": listed.fetched_at,
        "generation": listed.generation,
        "reader": listed.reader,
        "head": listed.head,
        "base": listed.base,
        "base_ref": listed.base_ref,
        "last_refresh": last_refresh,
        "fetched": len(listed.rows),
        "pages": listed.pages,
        "last_page": listed.last_page,
        "complete": listed.complete,
        "capped": listed.capped,
        "truncated": listed.truncated,
        "rows": rows[window.offset : window.offset + window.limit],
    }


def files_file_stamp(view: FilesView) -> tuple[int, int, int] | None:
    """The list file's inode, modification time in nanoseconds, and size."""

    repository = view.repository
    if repository is None:
        return None
    return _file_stamp(repository.home, repository.slug, view.number)


def envelope_etag(envelope: PullFilesEnvelope, stamp: tuple[int, int, int] | None) -> str:
    """An entity tag for *envelope* that never serializes its rows; see the list route's."""

    fields: dict[str, Any] = {name: value for name, value in envelope.items() if name != "rows"}
    fields["files_stamp"] = list(stamp) if stamp is not None else None
    digest = hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()
    return build_scoped_etag(f"pull-files-{digest[:32]}")


def _local(view: FilesView, facts: _Facts) -> LocalComparison | None:
    """The record's comparison in the served store, when there is one to list locally."""

    record = facts.record
    if view.git_dir is None or record is None or record.comparison is None:
        return None
    return LocalComparison(view.git_dir, record.comparison.base, record.comparison.head)


def files_refresh_wanted(
    view: FilesView, ask: FilesRefreshRequest
) -> tuple[bool, LocalComparison | None]:
    """Whether *ask* may start a refresh, and the local comparison it would list. Blocking.

    A list the local comparison can give needs no GitHub, so GitHub's limit does not hold
    it. Otherwise, while that limit holds nothing may start, a reader's **Retry** included,
    as for the list of pull requests. A **Retry** may start one otherwise. Any other request,
    a row expanded, starts one for a list that is not cached, not complete, or stale, and
    not tried within the window. A successful stamp without readable rows allows repair
    immediately, as does a GitHub list read for a head or base that has since moved; failed
    attempts still wait for their window.
    """

    repository = view.repository
    assert repository is not None
    home, slug = repository.home, repository.slug
    facts = _facts(home, slug, view.number)
    local = _local(view, facts)
    now = pull_list.utc_now()
    stamp = read_files_refresh(home, slug, view.number)
    if local is None and rate_limit_holds(stamp, now=now):
        return False, local
    if ask.retry:
        return True, local
    listed, _rows = _cached_files(home, slug, view.number)
    if (
        isinstance(listed, PullFileList)
        and listed.complete
        and _state(listed, stamp, facts) == ("current")
    ):
        return False, local
    # A previous success cannot stand in for rows that were removed or became unreadable.
    # Repeated failure still backs off, and provider rate holds were checked above.
    if not isinstance(listed, PullFileList) and stamp is not None and stamp.outcome == "succeeded":
        return True, local
    # A head that moved since a successful read is read again at once: the next list names
    # the head known before it, so this cannot repeat for one push. A failure still waits.
    if (
        isinstance(listed, PullFileList)
        and _head_moved(listed, facts)
        and (stamp is None or stamp.outcome == "succeeded")
    ):
        return True, local
    if local is not None:
        due = stamp is None or now - pull_list.parse_stamp(stamp.at) > timedelta(
            seconds=FRESHNESS_WINDOW_S
        )
        return due, local
    return refresh_is_due(stamp, now=now), local


# The keys of the file-list jobs started, some of which may have ended. Read and written only
# on the event loop.
_FILE_JOBS: set[str] = set()


def start_files_refresh(
    view: FilesView,
    ask: FilesRefreshRequest,
    *,
    wanted: bool,
    local: LocalComparison | None,
    background: bool = False,
) -> FilesRefreshStart:
    """Start the refresh *ask* names, join the one running, or say why it starts none.

    Runs on the event loop. A file-list job needs the network and not the store, so it takes
    no turn at the store: it is started outside the coordinator's network slots and holds one
    for each ``gh`` request alone, which keeps a long list from holding a slot between pages.
    Like the pull-request jobs, at most :data:`MAX_PULL_JOBS` may be queued or running,
    since the numbers are request text; past it a request is refused, ``too_many``, and
    starts nothing. A *background* job, a prefetch's, counts toward no bound and holds no
    network slot for its requests; a reader's request that joins it makes it count.
    """

    repository, coordinator = view.repository, view.coordinator
    assert repository is not None and coordinator is not None
    key = _job_key(repository, ask.number)
    if coordinator.running(key):
        if not background:
            _FILE_JOBS.add(key)
        return "joined"
    if not wanted:
        return "not_due"
    if not background:
        _FILE_JOBS.intersection_update({job for job in _FILE_JOBS if coordinator.running(job)})
        if len(_FILE_JOBS) >= MAX_PULL_JOBS:
            return "too_many"
        _FILE_JOBS.add(key)
    slot: _Slot = _no_slot if background else coordinator.slot
    work = partial(_run_files_refresh, repository, ask.number, local, slot)
    return coordinator.start(key, work, network=False)


@contextlib.asynccontextmanager
async def _no_slot() -> AsyncGenerator[None]:
    yield


def files_job_key(repository: ListedRepository, number: int) -> str:
    """The coordinator key of one file list's refresh, for a caller that waits for it."""

    return _job_key(repository, number)


async def _run_files_refresh(
    repository: ListedRepository,
    number: int,
    local: LocalComparison | None,
    slot: _Slot,
) -> None:
    # Here, not at the top: answering from the cache starts no gh, and loads none of it.
    from metabrowser.builtin_plugins.github.pull_files_refresh import refresh_pull_files

    try:
        await refresh_pull_files(
            repository,
            number,
            local=local,
            slot=slot,
            known_head=partial(known_head, repository.home, repository.slug, number),
        )
    except PullDataError:
        # Its stamp says how it ended, and the route reports that.
        return
    except Exception:
        # A bug, which no stamp names; keep one, as the list's job does.
        stopped = PullRefreshStamp(
            outcome="gh_failed", message=_JOB_STOPPED, at=utc_stamp(pull_list.utc_now())
        )
        await asyncio.to_thread(
            write_files_refresh, repository.home, repository.slug, number, stopped
        )
        raise


def status_route(number: int) -> str:
    """Where a one-shot ``--api`` reads how a refresh ended."""

    return f"{PULL_FILES_ROUTE}?number={number}&limit=0"


__all__ = [
    "NUMBER_REQUIRED",
    "PULL_FILES_ROUTE",
    "FileRowWire",
    "FilesRefreshRequest",
    "FilesRefreshStart",
    "FilesRequestError",
    "FilesState",
    "FilesView",
    "FilesWindow",
    "PullFilesEnvelope",
    "display_path",
    "envelope_etag",
    "files_file_stamp",
    "files_job_key",
    "files_refresh_request",
    "files_refresh_wanted",
    "files_view",
    "files_window",
    "pull_files_envelope",
    "start_files_refresh",
    "status_route",
]
