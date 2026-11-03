"""What the list routes answer, built from the cache and memory alone.

``GET /api/plugin/github/pulls`` never runs gh or Git and never waits on the network, so a
list opens as fast offline as online. It answers one of:

- ``absent``: nothing to show, with a ``reason``: this server serves no GitHub repository
  (``not_github``), or no usable list is cached (``not_cached``, ``schema_mismatch``,
  ``unreadable``);
- ``pending``: no list yet, and a refresh is running;
- ``current``: a list fetched within the refresh coordinator's freshness window, by the
  account the last refresh ran as to its end;
- ``stale``: an older list, or one fetched by another account, still shown and labelled
  with its ``reader``.

The count is honest: ``fetched`` is how many rows are held, ``complete`` is false when
GitHub has more, and ``truncated`` is true when a bound cut a row's text or an item could
not be read. ``at_cap`` says the list holds as many pages as it may, so no more can be
asked for. Rows come as a window, by ``limit`` and ``after`` (a row's number), and
``next_after`` is where the next window of cached rows starts.

Which repository a server lists is :func:`listed_repository`'s to say, and nothing else
here knows whether it is a mirror.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import stat
import threading
from bisect import bisect_left, bisect_right
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from functools import partial
from pathlib import Path
from typing import Any, Final, Literal, TypedDict

from metabrowser.builtin_plugins.github import pull_list
from metabrowser.builtin_plugins.github.gh_lists import PullDataError, utc_stamp
from metabrowser.builtin_plugins.github.pull_list import (
    MAX_LIST_PAGES,
    MAX_LIST_ROWS,
    ListedRepository,
    PullList,
    PullListRow,
    can_extend,
    rate_limit_holds,
    read_list_refresh,
    read_pull_list,
    refresh_is_due,
    write_list_refresh,
)
from metabrowser.builtin_plugins.github.pull_record import PullRefreshStamp, RecordAbsence
from metabrowser.builtin_plugins.github.urls import parse_repository_url
from metabrowser.cache.paths import PULL_LIST_NAMES, PullListName, source_pull_list
from metabrowser.http_caching import build_scoped_etag
from metabrowser.mirror_refresh import (
    FRESHNESS_WINDOW_S,
    MirrorSession,
    RefreshCoordinator,
    mirror_session,
    refresh_coordinator,
)

PULLS_ROUTE: Final = "/api/plugin/github/pulls"
DEFAULT_LIST: Final[PullListName] = "all"
# One GitHub page of rows, the size the browser appends. ``limit=0`` asks for the envelope
# alone, which is what a refresh answers with.
DEFAULT_LIMIT: Final = 100
_NUMBER = re.compile(r"^[1-9][0-9]{0,9}$")
_LIMIT = re.compile(r"^(?:0|[1-9][0-9]{0,3})$")
_REFRESH_FIELDS: Final = frozenset({"state", "more", "retry"})
_JOB_STOPPED: Final = "the refresh stopped on an unexpected error, which the server log names"

type ListState = Literal["absent", "pending", "current", "stale"]
type ListAbsence = Literal["not_github"] | RecordAbsence
type ListRefreshStart = Literal["started", "joined", "not_due"]


class ListRequestError(Exception):
    """A request the list routes refuse. ``str()`` says why, and names only the request."""


class LastRefresh(TypedDict):
    """How the list's last refresh ended, in any process."""

    outcome: str
    message: str | None
    reset_at: str | None
    at: str


class PullListEnvelope(TypedDict):
    """What ``GET /api/plugin/github/pulls`` returns."""

    state: ListState
    reason: ListAbsence | None
    source: str | None
    list: PullListName
    fetched_at: str | None
    reader: str | None
    fresh_for_s: float
    refreshing: bool
    last_refresh: LastRefresh | None
    fetched: int
    complete: bool
    truncated: bool
    at_cap: bool
    limit: int
    next_after: int | None
    rows: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class ListWindow:
    """Which list a request asks for, and which of its cached rows."""

    name: PullListName
    limit: int = DEFAULT_LIMIT
    after: int | None = None


@dataclass(frozen=True, slots=True)
class RefreshRequest:
    """What a ``POST`` asks for. *more* and *retry* are a reader's own action."""

    name: PullListName
    more: bool
    retry: bool


def _list_name(value: object) -> PullListName:
    if value not in PULL_LIST_NAMES:
        raise ListRequestError('"state" is all, open, or closed')
    return value


def list_window(params: Mapping[str, str]) -> ListWindow:
    """The window a ``GET`` names, or :class:`ListRequestError`."""

    limit = params.get("limit", str(DEFAULT_LIMIT))
    if not _LIMIT.match(limit) or int(limit) > MAX_LIST_ROWS:
        raise ListRequestError(f'"limit" is a whole number from 0 to {MAX_LIST_ROWS}')
    after = params.get("after")
    if after is not None and not _NUMBER.match(after):
        raise ListRequestError('"after" is a pull-request number')
    return ListWindow(
        name=_list_name(params.get("state", DEFAULT_LIST)),
        limit=int(limit),
        after=int(after) if after is not None else None,
    )


def refresh_request(body: Mapping[str, object]) -> RefreshRequest:
    """What a ``POST`` body names, or :class:`ListRequestError`."""

    if set(body) - _REFRESH_FIELDS:
        raise ListRequestError('a refresh request names only "state", "more", and "retry"')
    more = body.get("more", False)
    retry = body.get("retry", False)
    if not isinstance(more, bool) or not isinstance(retry, bool):
        raise ListRequestError('"more" and "retry" are true or false')
    return RefreshRequest(_list_name(body.get("state", DEFAULT_LIST)), more, retry)


def listed_repository(mirror: MirrorSession | None) -> ListedRepository | None:
    """The GitHub repository this server lists, or ``None``: on a mirror, what it mirrors."""

    if mirror is None:
        return None
    # Here, not at the top: a server that serves a folder has no mirror to ask this of.
    from metabrowser.cache.served_mirror import StoreMirror

    served = mirror.mirror
    if not isinstance(served, StoreMirror):
        return None
    parsed = parse_repository_url(served.source.normalized)
    if parsed is None:
        return None
    owner, repo = parsed
    return ListedRepository(home=served.home, slug=served.slug, owner=owner, repo=repo)


def _job_key(repository: ListedRepository, name: PullListName) -> str:
    """The single-flight key of a list's refresh: one per source and list."""

    return f"{repository.slug}:pulls/{name}"


@dataclass(frozen=True, slots=True)
class ListView:
    """What the envelope needs from memory, read on the event loop that owns it."""

    repository: ListedRepository | None
    coordinator: RefreshCoordinator | None
    refreshing: bool


def list_view(app: Any, name: PullListName) -> ListView:
    """The server's repository and whether list *name* is refreshing, read on the loop."""

    repository = listed_repository(mirror_session(app))
    coordinator = refresh_coordinator(app)
    refreshing = (
        repository is not None
        and coordinator is not None
        and coordinator.running(_job_key(repository, name))
    )
    return ListView(repository, coordinator, refreshing)


@dataclass(frozen=True, slots=True)
class _Parsed:
    stamp: tuple[int, int, int]
    listed: PullList
    rows: list[dict[str, Any]]


# Lists parsed for this route, keyed by home, slug, and list, each kept with the inode,
# modification time, and size it was read at. A browser polls the route, and a list is
# rewritten only by atomic replacement, which changes the inode, so an unchanged file is
# answered without reading or parsing it again.
_PARSED: dict[tuple[str, str, str], _Parsed] = {}
_PARSED_LOCK: Final = threading.Lock()
_MAX_PARSED: Final = 16


def _file_stamp(home: Path, slug: str, name: PullListName) -> tuple[int, int, int] | None:
    try:
        status = os.lstat(home / source_pull_list(slug, name))
    except OSError:
        return None
    if not stat.S_ISREG(status.st_mode):
        return None
    return status.st_ino, status.st_mtime_ns, status.st_size


def _wire_rows(listed: PullList) -> list[dict[str, Any]]:
    """The rows as the route answers them: as the file has them, and ``merged``."""

    return [
        {**row.model_dump(mode="json"), "merged": row.merged}  # A list item has no such flag.
        for row in listed.rows
    ]


def _cached_list(
    home: Path, slug: str, name: PullListName
) -> tuple[PullList | RecordAbsence, list[dict[str, Any]]]:
    """The list and its rows' JSON form, parsed again only when its file changed."""

    key = (str(home), slug, name)
    stamp = _file_stamp(home, slug, name)
    with _PARSED_LOCK:
        hit = _PARSED.get(key)
    if hit is not None and stamp is not None and hit.stamp == stamp:
        return hit.listed, hit.rows
    listed = read_pull_list(home, slug, name)
    if not isinstance(listed, PullList):
        return listed, []
    rows = _wire_rows(listed)
    if stamp is not None:
        with _PARSED_LOCK:
            if key not in _PARSED and len(_PARSED) >= _MAX_PARSED:
                _PARSED.pop(next(iter(_PARSED)))
            _PARSED[key] = _Parsed(stamp, listed, rows)
    return listed, rows


def cached_list_row(home: Path, slug: str, number: int) -> PullListRow | None:
    """Pull request *number*'s row in the newest cached list that holds it, or ``None``.

    Blocking and bounded, and each list is parsed once per write, as the route does.
    """

    found: PullListRow | None = None
    for name in PULL_LIST_NAMES:
        listed, _rows = _cached_list(home, slug, name)
        if not isinstance(listed, PullList):
            continue
        # Rows are in descending number order, so negated numbers ascend.
        at = bisect_left(listed.rows, -number, key=lambda row: -row.number)
        if at < len(listed.rows) and listed.rows[at].number == number:
            row = listed.rows[at]
            if found is None or row.updated_at > found.updated_at:
                found = row
    return found


def _window(
    rows: list[dict[str, Any]], window: ListWindow
) -> tuple[list[dict[str, Any]], int | None]:
    """The rows *window* names, and the number the next window starts after, if any."""

    start = 0
    if window.after is not None:
        # Rows are in descending number order, so negated numbers ascend.
        start = bisect_right(rows, -window.after, key=lambda row: -row["number"])
    shown = rows[start : start + window.limit]
    more = start + window.limit < len(rows)
    return shown, shown[-1]["number"] if more and shown else None


def _another_reader(listed: PullList, stamp: PullRefreshStamp | None) -> bool:
    """Whether the last refresh shows the active account is not the one that fetched *listed*.

    A stamp names the account its job started as, so one that ended ``account_changed``
    says this whichever it names. A stamp older than the list was written before it and
    says nothing of it: a process that stops between the two writes leaves one.
    """

    if stamp is None or pull_list.parse_stamp(stamp.at) < pull_list.parse_stamp(listed.fetched_at):
        return False
    return stamp.outcome == "account_changed" or stamp.reader not in (None, listed.reader)


def _state(listed: PullList, stamp: PullRefreshStamp | None) -> ListState:
    age = pull_list.utc_now() - pull_list.parse_stamp(listed.fetched_at)
    fresh = age <= timedelta(seconds=FRESHNESS_WINDOW_S)
    return "current" if fresh and not _another_reader(listed, stamp) else "stale"


def _last_refresh(stamp: PullRefreshStamp | None) -> LastRefresh | None:
    if stamp is None:
        return None
    return LastRefresh(
        outcome=stamp.outcome, message=stamp.message, reset_at=stamp.reset_at, at=stamp.at
    )


def pull_list_envelope(view: ListView, window: ListWindow) -> PullListEnvelope:
    """The envelope for one window. Blocking and bounded; run it off the loop."""

    empty = PullListEnvelope(
        state="absent",
        reason="not_github",
        source=None,
        list=window.name,
        fetched_at=None,
        reader=None,
        fresh_for_s=FRESHNESS_WINDOW_S,
        refreshing=view.refreshing,
        last_refresh=None,
        fetched=0,
        complete=False,
        truncated=False,
        at_cap=False,
        limit=window.limit,
        next_after=None,
        rows=[],
    )
    repository = view.repository
    if repository is None:
        return empty
    home, slug = repository.home, repository.slug
    stamp = read_list_refresh(home, slug, window.name)
    listed, rows = _cached_list(home, slug, window.name)
    last_refresh = _last_refresh(stamp)
    if not isinstance(listed, PullList):
        state: ListState = "pending" if view.refreshing else "absent"
        return {
            **empty,
            "state": state,
            "reason": None if view.refreshing else listed,
            "source": repository.source,
            "last_refresh": last_refresh,
        }
    shown, next_after = _window(rows, window)
    return {
        **empty,
        "state": _state(listed, stamp),
        "reason": None,
        "source": listed.source,
        "fetched_at": listed.fetched_at,
        "reader": listed.reader,
        "last_refresh": last_refresh,
        "fetched": len(listed.rows),
        "complete": listed.complete,
        "truncated": listed.truncated,
        "at_cap": not listed.complete and listed.pages >= MAX_LIST_PAGES,
        "next_after": next_after,
        "rows": shown,
    }


def list_file_stamp(view: ListView, name: PullListName) -> tuple[int, int, int] | None:
    """The list file's inode, modification time in nanoseconds, and size."""

    repository = view.repository
    return None if repository is None else _file_stamp(repository.home, repository.slug, name)


def envelope_etag(
    envelope: PullListEnvelope, stamp: tuple[int, int, int] | None, window: ListWindow
) -> str:
    """An entity tag for *envelope* that never serializes its rows.

    Every field but the rows is in it, with the window that chose them and *stamp*, the
    list file's :func:`list_file_stamp`: a list is replaced atomically, which changes its
    inode, so two lists written within the same second still differ. Read the stamp before
    the envelope; a list replaced in between then gets a tag the next request no longer
    matches, and is sent again rather than taken as unchanged.
    """

    fields: dict[str, Any] = {name: value for name, value in envelope.items() if name != "rows"}
    fields["after"] = window.after
    fields["list_stamp"] = list(stamp) if stamp is not None else None
    digest = hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()
    return build_scoped_etag(f"pulls-{digest[:32]}")


# The jobs a reader asked for more of while they ran, by job key, each dropped when the next
# job for its key starts. Read and written only on the event loop, so a job that finds its
# key absent ends before another request can add it.
_MORE_ASKED: set[str] = set()


async def _run_refresh(repository: ListedRepository, name: PullListName, *, more: bool) -> None:
    # Here, not at the top: answering from the cache starts no gh, and loads none of it.
    from metabrowser.builtin_plugins.github.pull_list_refresh import refresh_pull_list

    try:
        listed = await refresh_pull_list(repository, name, more=more)
        # A job that read the next page has answered the reader's second click too.
        if not more and _job_key(repository, name) in _MORE_ASKED and can_extend(listed):
            await refresh_pull_list(repository, name, more=True)
    except PullDataError:
        # Its stamp says how it ended, and the route reports that.
        return
    except Exception:
        # A bug, which no stamp names. Keep one, so the route says the job stopped and the
        # next automatic attempt waits a window instead of running this again on every poll.
        # The coordinator logs the exception; its text may name a path, so no stamp has it.
        stopped = PullRefreshStamp(
            outcome="gh_failed", message=_JOB_STOPPED, at=utc_stamp(pull_list.utc_now())
        )
        await asyncio.to_thread(write_list_refresh, repository.home, repository.slug, name, stopped)
        raise


def refresh_wanted(view: ListView, ask: RefreshRequest) -> bool:
    """Whether *ask* may start a refresh. Blocking and bounded; run it off the loop.

    While GitHub's limit holds nothing may, a reader's own action included: it would be a
    request GitHub asked not to get, and each refusal moves the time on. The route cannot
    ask ``gh`` who is active, so an account that was not limited waits too.

    Otherwise a reader's **Retry** may, and a **Load more** that has a page to read. A
    **Load more** that does not, on a complete list or one at its cap, could only reread
    every page held, so it waits for the list's stamp to say one is due, as an automatic
    request does.
    """

    repository = view.repository
    if repository is None:
        return True
    now = pull_list.utc_now()
    stamp = read_list_refresh(repository.home, repository.slug, ask.name)
    if rate_limit_holds(stamp, now=now):
        return False
    if ask.retry:
        return True
    if ask.more:
        listed, _rows = _cached_list(repository.home, repository.slug, ask.name)
        if not isinstance(listed, PullList) or can_extend(listed):
            return True
    return refresh_is_due(stamp, now=now)


def start_refresh(view: ListView, ask: RefreshRequest, *, wanted: bool) -> ListRefreshStart:
    """Start the refresh *ask* names, or join the one running. Runs on the event loop.

    A ``more`` that joins a job is kept, and that job reads the next page after its refresh,
    so ``joined`` means the same to a reader whatever was running: the list will have it
    when ``refreshing`` is false, unless ``last_refresh`` says why not. A request
    :func:`refresh_wanted` turned down starts nothing and answers ``not_due``.
    """

    repository, coordinator = view.repository, view.coordinator
    assert repository is not None and coordinator is not None
    key = _job_key(repository, ask.name)
    if coordinator.running(key):
        if ask.more and wanted:
            _MORE_ASKED.add(key)
        return "joined"
    _MORE_ASKED.discard(key)
    if not wanted:
        return "not_due"
    return coordinator.start(key, partial(_run_refresh, repository, ask.name, more=ask.more))


def status_route(name: PullListName) -> str:
    """Where a one-shot ``--api`` reads how a refresh ended: the envelope, without rows."""

    return f"{PULLS_ROUTE}?state={name}&limit=0"


__all__ = [
    "DEFAULT_LIMIT",
    "DEFAULT_LIST",
    "PULLS_ROUTE",
    "LastRefresh",
    "ListAbsence",
    "ListRefreshStart",
    "ListRequestError",
    "ListState",
    "ListView",
    "ListWindow",
    "PullListEnvelope",
    "RefreshRequest",
    "cached_list_row",
    "envelope_etag",
    "list_file_stamp",
    "list_view",
    "list_window",
    "listed_repository",
    "pull_list_envelope",
    "refresh_request",
    "refresh_wanted",
    "start_refresh",
    "status_route",
]
