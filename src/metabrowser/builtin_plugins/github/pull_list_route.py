"""Cache-only PR catalog windows and one resumable background metadata job.

Provider totals are distinct from locally cached rows. Window pagination reads only
SQLite indexes; the display budget does not cap the background catalog. A generation
changes when existing filter content changes, not when older pages are appended.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from functools import partial
from pathlib import Path
from time import monotonic
from typing import Any, Final, Literal, TypedDict
from weakref import WeakKeyDictionary

from metabrowser.builtin_plugins.github import pull_list
from metabrowser.builtin_plugins.github.checkout import served_checkout
from metabrowser.builtin_plugins.github.gh_lists import PullDataError, utc_stamp
from metabrowser.builtin_plugins.github.pull_catalog import (
    MAX_WINDOW,
    CatalogState,
    catalog_row,
    catalog_window,
    read_catalog,
)
from metabrowser.builtin_plugins.github.pull_list import (
    ListedRepository,
    PullListRow,
    rate_limit_holds,
    read_list_refresh,
    refresh_is_due,
    write_list_refresh,
)
from metabrowser.builtin_plugins.github.pull_record import PullRefreshStamp, RecordAbsence
from metabrowser.builtin_plugins.github.urls import parse_repository_url
from metabrowser.cache.locks import run_lock_section
from metabrowser.cache.paths import MAX_PULL_REQUEST_NUMBER, PULL_LIST_NAMES, PullListName
from metabrowser.http_caching import build_scoped_etag
from metabrowser.mirror_refresh import (
    FRESHNESS_WINDOW_S,
    MirrorSession,
    RefreshCoordinator,
    mirror_session,
    refresh_coordinator,
)

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
type ListRefreshWanted = bool | Literal["reconnect"]


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
    reader: str | None
    fresh_for_s: float
    refreshing: bool
    last_refresh: LastRefresh | None
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


@dataclass(frozen=True, slots=True)
class ListWindow:
    name: PullListName
    limit: int = DEFAULT_LIMIT
    after: int | None = None


@dataclass(frozen=True, slots=True)
class RefreshRequest:
    name: PullListName
    target: int = DEFAULT_TARGET
    retry: bool = False
    background: bool = False
    reconnect: bool = False


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
    return ListWindow(
        _list_name(params.get("state", DEFAULT_LIST)),
        _number(params.get("limit", str(DEFAULT_LIMIT)), MAX_WINDOW, "limit", zero=True),
        _number(after, MAX_PULL_REQUEST_NUMBER, "after") if after is not None else None,
    )


def search_query(value: str) -> str:
    query = value.strip()
    if len(value) > MAX_SEARCH_QUERY_CHARS or not query:
        raise ListRequestError(f'"q" must contain 1 to {MAX_SEARCH_QUERY_CHARS} characters')
    return query


def refresh_request(body: Mapping[str, object]) -> RefreshRequest:
    if set(body) - {"state", "target", "retry", "background", "reconnect"}:
        raise ListRequestError(
            'a catalog request names only "state", "target", "retry", "background", and "reconnect"'
        )
    retry = body.get("retry", False)
    background, reconnect = body.get("background", False), body.get("reconnect", False)
    target = body.get("target", DEFAULT_TARGET)
    if not isinstance(background, bool):
        raise ListRequestError('"background" is boolean')
    if not isinstance(retry, bool) or type(target) is not int or not 1 <= target <= _MAX_TARGET:
        raise ListRequestError('"retry" is boolean and "target" is a positive PR count')
    if not isinstance(reconnect, bool) or (retry and reconnect):
        raise ListRequestError('"reconnect" is boolean and cannot be combined with "retry"')
    return RefreshRequest(
        _list_name(body.get("state", DEFAULT_LIST)), target, retry, background, reconnect
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
    repository: ListedRepository | None
    coordinator: RefreshCoordinator | None
    refreshing: bool


def list_view(app: Any, name: PullListName) -> ListView:
    repository, coordinator = served_repository(app), refresh_coordinator(app)
    return ListView(
        repository,
        coordinator,
        bool(
            repository is not None
            and coordinator is not None
            and coordinator.running(_job_key(repository))
        ),
    )


def cached_list_row(home: Path, slug: str, number: int) -> PullListRow | None:
    return catalog_row(home, slug, number)


def _state(listed: CatalogState, stamp: PullRefreshStamp | None) -> ListState:
    fresh = pull_list.utc_now() - pull_list.parse_stamp(listed.fetched_at) <= timedelta(
        seconds=FRESHNESS_WINDOW_S
    )
    other = (
        stamp is not None
        and stamp.at >= listed.fetched_at
        and (stamp.outcome == "account_changed" or stamp.reader not in (None, listed.reader))
    )
    return "current" if fresh and not other else "stale"


def pull_list_envelope(view: ListView, window: ListWindow) -> PullListEnvelope:
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
    repository = view.repository
    if repository is None:
        return empty
    stamp = read_list_refresh(repository.home, repository.slug, "all")
    listed, rows, following = catalog_window(
        repository.home, repository.slug, window.name, limit=window.limit, after=window.after
    )
    if listed is not None and listed.source != repository.source:
        listed, rows, following = None, [], None
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
    return {
        **empty,
        "state": _state(listed, stamp),
        "reason": None,
        "fetched_at": listed.fetched_at,
        "reader": listed.reader,
        "total": listed.totals[window.name],
        "repository_total": listed.totals["all"],
        "filter_totals": listed.totals,
        "count_at": listed.count_at,
        "catalog_fetched": listed.cached["all"],
        "generation": listed.generation(window.name),
        "fetched": listed.cached[window.name],
        "complete": listed.done["all"],
        "truncated": listed.truncated,
        "next_after": following,
        "rows": rows,
    }


def envelope_etag(envelope: PullListEnvelope, window: ListWindow) -> str:
    digest = hashlib.sha256(
        json.dumps({**envelope, "after": window.after}, sort_keys=True).encode()
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


def refresh_wanted(view: ListView, ask: RefreshRequest) -> ListRefreshWanted:
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
    return listed is None or not listed.done["all"] or refresh_is_due(stamp, now=now)


def start_refresh(
    view: ListView, ask: RefreshRequest, *, wanted: ListRefreshWanted
) -> ListRefreshStart:
    repository, coordinator = view.repository, view.coordinator
    assert repository is not None and coordinator is not None
    key = _job_key(repository)
    if coordinator.running(key):
        if wanted and not (ask.background or ask.reconnect):
            demand = _DEMANDS[_demand_key(repository, coordinator)]
            demand.name, demand.target = ask.name, ask.target
            demand.retry = demand.retry or ask.retry
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
        ask.name, ask.target, ask.retry or reconnect
    )
    return coordinator.start(key, partial(_run_refresh, repository, coordinator), network=False)


def status_route(name: PullListName) -> str:
    return f"{PULLS_ROUTE}?state={name}&limit=0"
