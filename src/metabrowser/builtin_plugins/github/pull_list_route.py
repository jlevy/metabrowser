"""Cache-only PR catalog windows and one resumable background metadata job.

Provider totals are distinct from locally cached rows. Window pagination reads only
SQLite indexes; the display budget does not cap the background catalog. A generation
changes when existing filter content changes, not when older pages are appended.

An automatic ask that finds nothing else due probes the list (:mod:`.pull_list_probe`):
one conditional request, which starts the catalog's delta scan at once when GitHub has a
pull request the catalog lacks. While probes vouch for the catalog its scan is due once
every ``FULL_REFRESH_S``, for what a probe cannot see; otherwise once a freshness window,
as before probes (:func:`refresh_wanted`).
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path
from time import monotonic
from typing import Any, Final, Literal, NotRequired, TypedDict
from weakref import WeakKeyDictionary

from metabrowser.builtin_plugins.github import gh_budget, gh_lanes, pull_list
from metabrowser.builtin_plugins.github.checkout import served_checkout
from metabrowser.builtin_plugins.github.gh_lists import PullDataError, utc_stamp
from metabrowser.builtin_plugins.github.pull_catalog import (
    MAX_WINDOW,
    CatalogRefreshTiming,
    CatalogState,
    catalog_position,
    catalog_row,
    catalog_window,
    read_catalog,
    read_catalog_refresh_timing,
    upgrade_catalog,
)
from metabrowser.builtin_plugins.github.pull_list import (
    ListedRepository,
    PullListRow,
    rate_limit_holds,
    read_list_refresh,
    refresh_is_due,
    write_list_refresh,
)
from metabrowser.builtin_plugins.github.pull_list_probe import LIST_PROBE_S, ListProbe, list_probe
from metabrowser.builtin_plugins.github.pull_record import PullRefreshStamp, RecordAbsence
from metabrowser.builtin_plugins.github.refresh_metrics import RefreshTiming
from metabrowser.builtin_plugins.github.served_pull import FULL_REFRESH_S
from metabrowser.builtin_plugins.github.urls import parse_repository_url
from metabrowser.cache.locks import run_lock_section
from metabrowser.cache.paths import MAX_PULL_REQUEST_NUMBER, PULL_LIST_NAMES, PullListName
from metabrowser.home import PrivateStorageError
from metabrowser.http_caching import build_scoped_etag
from metabrowser.mirror_refresh import (
    FRESHNESS_WINDOW_S,
    MirrorSession,
    RefreshCoordinator,
    mirror_session,
    refresh_coordinator,
)

log = logging.getLogger(__name__)

PULLS_ROUTE: Final = "/api/plugin/github/pulls"
DEFAULT_LIST: Final[PullListName] = "open"
DEFAULT_LIMIT: Final = 100
DEFAULT_TARGET: Final = 500
MAX_SEARCH_QUERY_CHARS: Final = 256
_MAX_TARGET: Final = MAX_PULL_REQUEST_NUMBER
_JOB_STOPPED: Final = "the refresh stopped on an unexpected error, which the server log names"

type ListState = Literal["absent", "pending", "current", "stale"]
type ListAbsence = Literal["not_github"] | RecordAbsence
type ListRefreshStart = Literal["started", "joined", "not_due"]
# ``probe``: nothing is due but a list probe, which the route runs and which then makes
# the ask ``changed`` (a delta scan is due at once) or ``False``. ``scan``: the delta scan
# is due by age; ``backfill``: only the backfill past every reader's prefix is due. Either
# starts the catalog's job in the background lane (:mod:`.gh_lanes`), and ``True`` in the
# asker's.
type ListRefreshWanted = bool | Literal["reconnect", "probe", "changed", "scan", "backfill"]


class ListRequestError(Exception):
    """An invalid list request; its message contains no local data."""


class LastRefresh(TypedDict):
    outcome: str
    message: str | None
    reset_at: str | None
    at: str


class PullListEnvelope(TypedDict):
    state: ListState
    reason: ListAbsence | None
    source: str | None
    list: PullListName
    fetched_at: str | None
    # When a list probe last found the catalog unchanged, if after ``fetched_at``: the
    # list is ``current`` for a window from the newer of the two. Not in the entity tag,
    # so a poll of an unchanged list stays a ``304`` while probes move it.
    checked_at: str | None
    reader: str | None
    fresh_for_s: float
    # How often a visible page asks while it shows a list: the server then probes it or
    # scans it when that is due, and answers ``not_due`` otherwise. ``None`` with no
    # catalog to probe.
    probe_every_s: float | None
    refreshing: bool
    last_refresh: LastRefresh | None
    refresh_timing: NotRequired[RefreshTiming]
    total: int | None
    repository_total: int | None
    filter_totals: dict[str, int] | None
    count_at: str | None
    catalog_fetched: int
    generation: str | None
    fetched: int
    complete: bool
    truncated: bool
    limit: int
    next_after: int | None
    rows: list[dict[str, Any]]
    position: NotRequired[int | None]


@dataclass(frozen=True, slots=True)
class ListWindow:
    name: PullListName
    limit: int = DEFAULT_LIMIT
    after: int | None = None
    at: int | None = None


# The lanes a list's ask may name (:mod:`.gh_lanes`): the Pulls tab's, for the list it
# shows, and a pull request page's, for the list behind it that vouches for its record.
ASK_LANES: Final[tuple[gh_lanes.Lane, ...]] = ("visible", "attended")


@dataclass(frozen=True, slots=True)
class RefreshRequest:
    name: PullListName
    target: int = DEFAULT_TARGET
    retry: bool = False
    background: bool = False
    reconnect: bool = False
    lane: gh_lanes.Lane = "visible"


def _list_name(value: object) -> PullListName:
    if value not in PULL_LIST_NAMES:
        raise ListRequestError('"state" is all, open, or closed')
    return value


def _number(value: str, maximum: int, label: str, *, zero: bool = False) -> int:
    if not value.isascii() or not value.isdecimal() or len(value) > 10:
        raise ListRequestError(f'"{label}" is a whole number')
    number = int(value)
    if str(number) != value or not (0 if zero else 1) <= number <= maximum:
        raise ListRequestError(f'"{label}" is outside its allowed range')
    return number


def list_window(params: Mapping[str, str]) -> ListWindow:
    after = params.get("after")
    at = params.get("at")
    name = _list_name(params.get("state", DEFAULT_LIST))
    if at is not None and (after is not None or name != "all"):
        raise ListRequestError('"at" requires state=all and no "after"')
    return ListWindow(
        name,
        _number(params.get("limit", str(DEFAULT_LIMIT)), MAX_WINDOW, "limit", zero=True),
        _number(after, MAX_PULL_REQUEST_NUMBER, "after") if after is not None else None,
        _number(at, MAX_PULL_REQUEST_NUMBER, "at") if at is not None else None,
    )


def search_query(value: str) -> str:
    query = value.strip()
    if len(value) > MAX_SEARCH_QUERY_CHARS or not query:
        raise ListRequestError(f'"q" must contain 1 to {MAX_SEARCH_QUERY_CHARS} characters')
    return query


def refresh_request(body: Mapping[str, object]) -> RefreshRequest:
    if set(body) - {"state", "target", "retry", "background", "reconnect", "lane"}:
        raise ListRequestError(
            'a catalog request names only "state", "target", "retry", "background", '
            '"reconnect", and "lane"'
        )
    retry = body.get("retry", False)
    background, reconnect = body.get("background", False), body.get("reconnect", False)
    target = body.get("target", DEFAULT_TARGET)
    named = body.get("lane", "visible")
    lane: gh_lanes.Lane | None = None
    for each in ASK_LANES:
        if named == each:
            lane = each
    if not isinstance(background, bool):
        raise ListRequestError('"background" is boolean')
    if not isinstance(retry, bool) or type(target) is not int or not 1 <= target <= _MAX_TARGET:
        raise ListRequestError('"retry" is boolean and "target" is a positive PR count')
    if not isinstance(reconnect, bool) or (retry and reconnect):
        raise ListRequestError('"reconnect" is boolean and cannot be combined with "retry"')
    if lane is None:
        raise ListRequestError('"lane" is "visible" or "attended"')
    return RefreshRequest(
        _list_name(body.get("state", DEFAULT_LIST)), target, retry, background, reconnect, lane
    )


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


def served_repository(app: Any) -> ListedRepository | None:
    """The GitHub repository this server lists, or ``None``.

    On a mirror, what it mirrors; on a folder, what a served checkout's ``origin`` names
    (:mod:`.checkout`), read from memory once the route has resolved it.
    """

    mirror = mirror_session(app)
    if mirror is not None:
        return listed_repository(mirror)
    return served_checkout(app)


def catalog_job_key(source: str) -> str:
    """The coordinator key of a repository's catalog job, by its normalized source."""

    # Publication can disambiguate a slug; normalized source identity stays stable.
    return f"{source}:pull-catalog"


def _job_key(repository: ListedRepository) -> str:
    return catalog_job_key(repository.source)


@dataclass(frozen=True, slots=True)
class ListView:
    """What an envelope needs from memory, read on the event loop that owns it.

    ``checked_at`` is the list probe's, copied here so a thread reads one moment of it.
    """

    repository: ListedRepository | None
    coordinator: RefreshCoordinator | None
    refreshing: bool
    probe: ListProbe | None = None
    checked_at: str | None = None


def list_view(app: Any, name: PullListName) -> ListView:
    repository, coordinator = served_repository(app), refresh_coordinator(app)
    probe = (
        list_probe(coordinator, repository.source)
        if repository is not None and coordinator is not None
        else None
    )
    return ListView(
        repository,
        coordinator,
        bool(
            repository is not None
            and coordinator is not None
            and coordinator.running(_job_key(repository))
        ),
        probe,
        probe.checked_at if probe is not None else None,
    )


def cached_list_row(home: Path, slug: str, number: int) -> PullListRow | None:
    return catalog_row(home, slug, number)


def _checked_at(listed: CatalogState, view: ListView) -> str | None:
    """When a probe found *listed* unchanged after its scan, or ``None``."""

    checked = view.checked_at
    return checked if checked is not None and checked > listed.fetched_at else None


def _state(
    listed: CatalogState, stamp: PullRefreshStamp | None, checked_at: str | None
) -> ListState:
    fresh = pull_list.utc_now() - pull_list.parse_stamp(
        checked_at or listed.fetched_at
    ) <= timedelta(seconds=FRESHNESS_WINDOW_S)
    other = (
        stamp is not None
        and stamp.at >= listed.fetched_at
        and (stamp.outcome == "account_changed" or stamp.reader not in (None, listed.reader))
    )
    return "current" if fresh and not other else "stale"


@dataclass(frozen=True, slots=True)
class ListFound:
    """What one envelope is built from, as :func:`read_catalog_window` read it from the cache."""

    stamp: PullRefreshStamp | None
    listed: CatalogState | None
    rows: list[dict[str, Any]]
    following: int | None
    position: int | None = None
    refresh_timing: CatalogRefreshTiming | None = None


def read_catalog_window(view: ListView, window: ListWindow) -> ListFound | None:
    """What *view*'s envelope for *window* is built from, or ``None`` with no repository.

    Blocking: the stamp and one indexed window, preparing a legacy index on first use.
    """

    repository = view.repository
    if repository is None:
        return None
    stamp = read_list_refresh(repository.home, repository.slug, "all")
    if window.at is not None:
        read = partial(
            catalog_position, repository.home, repository.slug, window.at, limit=window.limit
        )
    else:
        read = partial(
            catalog_window,
            repository.home,
            repository.slug,
            window.name,
            limit=window.limit,
            after=window.after,
        )
    listed, rows, marker = read()
    if listed is None:
        # Local preparation of an existing legacy cache is independent of refresh admission.
        with contextlib.suppress(PrivateStorageError, OSError, sqlite3.Error, ValueError):
            if upgrade_catalog(repository):
                listed, rows, marker = read()
    if listed is None or listed.source != repository.source:
        return ListFound(stamp, None, [], None)
    timing = read_catalog_refresh_timing(repository.home, repository.slug)
    if timing is not None and timing.epoch != listed.epoch:
        timing = None
    if window.at is not None:
        return ListFound(stamp, listed, rows, None, position=marker, refresh_timing=timing)
    return ListFound(stamp, listed, rows, marker, refresh_timing=timing)


def pull_list_envelope(view: ListView, window: ListWindow) -> PullListEnvelope:
    """The envelope for one indexed window of the local catalog."""

    return list_envelope(view, read_catalog_window(view, window), window)


def list_envelope(view: ListView, found: ListFound | None, window: ListWindow) -> PullListEnvelope:
    """The envelope for *window* of what *found* holds, as *view* is. Reads no file.

    ``refreshing`` is *view*'s, which may be newer than *found*: the refresh route reads
    what a job finds before it starts the job.
    """

    empty = PullListEnvelope(
        state="absent",
        reason="not_github",
        source=None,
        list=window.name,
        fetched_at=None,
        checked_at=None,
        reader=None,
        fresh_for_s=FRESHNESS_WINDOW_S,
        probe_every_s=None,
        refreshing=view.refreshing,
        last_refresh=None,
        total=None,
        repository_total=None,
        filter_totals=None,
        count_at=None,
        catalog_fetched=0,
        generation=None,
        fetched=0,
        complete=False,
        truncated=False,
        limit=window.limit,
        next_after=None,
        rows=[],
    )
    if window.at is not None:
        empty["position"] = found.position if found is not None else None
    repository = view.repository
    if repository is None or found is None:
        return empty
    stamp, listed = found.stamp, found.listed
    empty.update(
        source=repository.source,
        last_refresh=LastRefresh(
            outcome=stamp.outcome, message=stamp.message, reset_at=stamp.reset_at, at=stamp.at
        )
        if stamp
        else None,
    )
    if listed is None:
        empty.update(
            state="pending" if view.refreshing else "absent",
            reason=None if view.refreshing else "not_cached",
        )
        return empty
    if found.refresh_timing is not None:
        empty["refresh_timing"] = found.refresh_timing.wire()
    checked_at = _checked_at(listed, view)
    return {
        **empty,
        "state": _state(listed, stamp, checked_at),
        "reason": None,
        "fetched_at": listed.fetched_at,
        "checked_at": checked_at,
        "reader": listed.reader,
        "probe_every_s": LIST_PROBE_S if view.probe is not None else None,
        "total": listed.totals[window.name],
        "repository_total": listed.totals["all"],
        "filter_totals": listed.totals,
        "count_at": listed.count_at,
        "catalog_fetched": listed.cached["all"],
        "generation": listed.generation(window.name),
        "fetched": listed.cached[window.name],
        "complete": listed.done["all"],
        "truncated": listed.truncated,
        "next_after": found.following,
        "rows": found.rows,
    }


def envelope_etag(envelope: PullListEnvelope, window: ListWindow) -> str:
    # Without ``checked_at``, which every unchanged probe moves and no reader of a ``304``
    # needs: ``state`` says what it decides.
    digest = hashlib.sha256(
        json.dumps({**envelope, "checked_at": None, "after": window.after}, sort_keys=True).encode()
    ).hexdigest()
    return build_scoped_etag(f"pulls-{digest[:32]}")


@dataclass(slots=True)
class _Demand:
    name: PullListName
    target: int
    retry: bool

    def take_retry(self) -> bool:
        requested, self.retry = self.retry, False
        return requested


# One demand per coordinator's live job, removed on completion or cancellation.
_DEMANDS: dict[tuple[int, str], _Demand] = {}
# A browser going online can retry an interrupted connection once per freshness
# window. Claim it on the coordinator loop so simultaneous tabs share the budget.
_RECONNECTS: WeakKeyDictionary[RefreshCoordinator, dict[str, float]] = WeakKeyDictionary()


def _demand_key(repository: ListedRepository, coordinator: RefreshCoordinator) -> tuple[int, str]:
    return id(coordinator), repository.source


async def _run_refresh(repository: ListedRepository, coordinator: RefreshCoordinator) -> None:
    from metabrowser.builtin_plugins.github.pull_list_refresh import refresh_pull_list

    key = _demand_key(repository, coordinator)
    try:
        demand = _DEMANDS[key]
        await refresh_pull_list(
            repository,
            demand.name,
            target=demand.target,
            take_retry=demand.take_retry,
            slot=coordinator.slot(),
            demand=lambda: (demand.name, demand.target),
        )
    except PullDataError:
        return
    except Exception:
        await run_lock_section(
            partial(
                write_list_refresh,
                repository.home,
                repository.slug,
                "all",
                PullRefreshStamp(
                    outcome="gh_failed",
                    message=_JOB_STOPPED,
                    at=utc_stamp(pull_list.utc_now()),
                ),
            )
        )
        raise
    finally:
        _DEMANDS.pop(key, None)


def scan_is_due(stamp: PullRefreshStamp | None, probe: ListProbe | None, *, now: datetime) -> bool:
    """Whether the catalog's periodic delta scan is due, after a scan that succeeded.

    Once every ``FULL_REFRESH_S`` while a list probe vouches for the catalog, for what the
    probe cannot see, a pull request whose ``updated_at`` did not move; once a freshness
    window otherwise, as before probes.
    """

    if stamp is None:
        return True
    window = FULL_REFRESH_S if probe is not None and probe.vouches(now) else FRESHNESS_WINDOW_S
    # Over the process's own ceiling a full read waits five minutes.
    window = gh_budget.full_read_interval(window, now=now)
    return not rate_limit_holds(stamp, now=now) and now - pull_list.parse_stamp(
        stamp.at
    ) > timedelta(seconds=window)


def refresh_wanted(view: ListView, ask: RefreshRequest) -> ListRefreshWanted:
    """What *ask* is due to start. Blocking and bounded; never contacts GitHub.

    ``True`` for the catalog job, ``changed`` for the job with its delta scan first, since
    a probe found GitHub ahead of the catalog, ``scan`` for the job when only its delta scan
    is due by age, ``backfill`` when only the backfill past every reader's prefix is, ``probe``
    when only a list probe is due, which the route then runs, and ``False`` for nothing.
    """

    repository = view.repository
    if repository is None:
        return True
    now = pull_list.utc_now()
    stamp = read_list_refresh(repository.home, repository.slug, "all")
    if rate_limit_holds(stamp, now=now) or (
        stamp is not None
        and stamp.outcome == "rate_limited"
        and stamp.reset_at is None
        and not refresh_is_due(stamp, now=now)
    ):
        return False
    if ask.retry:
        return True
    if stamp is not None and stamp.outcome != "succeeded":
        if refresh_is_due(stamp, now=now):
            return True
        return "reconnect" if ask.reconnect and stamp.outcome == "network_error" else False
    listed = read_catalog(repository.home, repository.slug)
    probe = view.probe
    if listed is None:
        return True
    if probe is not None and probe.saw is not None:
        # A probe that outlasted its request's wait found a change: its scan is due now,
        # below the floor too. Asked before the periodic scan, which would otherwise start
        # the job without telling the probe, and the row would then be scanned for twice.
        return "changed"
    # The periodic scan is automatic work, admitted as background work is; below the floor
    # it stops.
    admitted = gh_budget.admission(("graphql", "core"), now=now, ceiling=False).admitted
    scan_due = admitted and scan_is_due(stamp, probe, now=now)
    if not listed.done["all"]:
        from metabrowser.builtin_plugins.github.pull_list_refresh import (
            backfill_admitted,
            prefix_wanted,
        )

        # The asked prefix is the asker's to wait for, whatever else is due. Past it the
        # backfill is background work, which the budget may pause.
        if prefix_wanted(listed, ask.name, ask.target):
            return True
        if not scan_due and backfill_admitted():
            return "backfill"
    if scan_due:
        return "scan"
    due = probe is not None and listed.source == repository.source and probe.due(now)
    return "probe" if due else False


async def probe_list(view: ListView) -> ListRefreshWanted:
    """Run the list probe an ask found due, and say what the ask is due to start then.

    ``changed`` when the probe found a pull request the catalog lacks, and ``False`` when
    it found none, failed, or outlasted the wait, which leaves it to end on its own.
    """

    repository, probe = view.repository, view.probe
    assert repository is not None and probe is not None
    now = pull_list.utc_now()
    if not probe.due(now):
        # The ask found it due in a worker thread, and another ask's probe started, or
        # ended, before this one reached the loop again: two tabs, or a tab and a page
        # (review A2 of #737). That probe's own ask starts the scan for what it finds, and
        # one that outlasted its wait leaves ``saw`` for the next ask's
        # :func:`refresh_wanted`, so this ask starts nothing: answering ``changed`` too
        # could start a second delta scan for the same row.
        return False
    if not probe.may_start(now):
        # The server's cap on probes in flight is full; the next ask probes.
        return False
    try:
        await probe.run(repository, coordinator=view.coordinator)
    except TimeoutError:
        return False
    return "changed" if probe.saw is not None else False


def _attended_wanted(view: ListView, ask: RefreshRequest) -> ListRefreshWanted:
    repository = view.repository
    assert repository is not None
    # A page shows one pull request, not the list: it keeps a catalog current, and never
    # starts the first read of one nobody opened.
    if read_catalog(repository.home, repository.slug) is None:
        return False
    return refresh_wanted(view, ask)


async def _attend(view: ListView) -> None:
    ask = RefreshRequest(DEFAULT_LIST, background=True, lane="attended")
    try:
        wanted = await asyncio.to_thread(_attended_wanted, view, ask)
        # The list is read for the page's record, not shown: the probe's job and the
        # catalog's copy this lane (:mod:`.gh_lanes`).
        with gh_lanes.serving(ask.lane):
            if wanted == "probe":
                wanted = await probe_list(view)
            if wanted:
                start_refresh(view, ask, wanted=wanted)
    except Exception:
        # Nothing waits on this but the catalog's freshness, and the page's own ask must
        # still be answered.
        log.exception("keeping the pull-request list current for a visible page failed")


def attend_list(view: ListView) -> asyncio.Future[None] | None:
    """Keep the repository's catalog current for a visible pull request page. On the loop.

    The page's automatic ask for its own record, sent every ``ATTENDED_PROBE_S`` while it
    is visible, stands for the ask a visible Pulls tab sends for the list: the list is
    probed, and scanned when that is due, so the catalog keeps vouching for the page's
    record, its stack, and the list behind it while the page is all that is open. Asked no
    more than once every ``LIST_PROBE_FLOOR_S`` however many pages ask. The result ends
    within ``PROBE_WAIT_S`` and a thread's read, never raises, and is ``None`` when
    nothing was asked.
    """

    probe = view.probe
    if view.repository is None or view.coordinator is None or probe is None:
        return None
    if not probe.attend(monotonic()):
        return None
    return asyncio.ensure_future(_attend(view))


def start_refresh(
    view: ListView, ask: RefreshRequest, *, wanted: ListRefreshWanted
) -> ListRefreshStart:
    repository, coordinator = view.repository, view.coordinator
    assert repository is not None and coordinator is not None and wanted != "probe"
    key = _job_key(repository)
    # A change a probe found, or a reader's Refresh, reads the delta scan first.
    changed = wanted == "changed"
    if (changed or ask.retry) and view.probe is not None:
        view.probe.scan_started()
    if coordinator.running(key):
        if wanted and not (ask.background or ask.reconnect):
            demand = _DEMANDS[_demand_key(repository, coordinator)]
            demand.name, demand.target = ask.name, ask.target
            demand.retry = demand.retry or ask.retry
        if changed:
            # The running job's next page is then the delta scan, whoever asked.
            _DEMANDS[_demand_key(repository, coordinator)].retry = True
        return "joined"
    if not wanted:
        return "not_due"
    reconnect = wanted == "reconnect"
    if reconnect:
        starts = _RECONNECTS.setdefault(coordinator, {})
        now = monotonic()
        previous = starts.get(repository.source)
        if previous is not None and now - previous < FRESHNESS_WINDOW_S:
            return "not_due"
        starts[repository.source] = now
    _DEMANDS[_demand_key(repository, coordinator)] = _Demand(
        ask.name, ask.target, ask.retry or reconnect or changed
    )
    # A job started for the clock's scan or the backfill alone reads nothing a reader
    # waits for; any other reads its asker's pages first (:mod:`.gh_lanes`). A job keeps
    # the lane it was started in, as it keeps its budget, whoever joins it.
    lane = "background" if wanted in ("scan", "backfill") else ask.lane
    with gh_lanes.serving(lane):
        return coordinator.start(key, partial(_run_refresh, repository, coordinator), network=False)


def status_route(name: PullListName) -> str:
    return f"{PULLS_ROUTE}?state={name}&limit=0"
