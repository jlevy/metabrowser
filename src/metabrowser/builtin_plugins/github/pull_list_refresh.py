"""Backfill lightweight PR metadata and refresh only rows changed since a checkpoint.

Every GitHub page is independently bounded and published before the next begins. The
server's catalog worker yields its network slot after each page, resumes durable cursors,
and never fetches a PullRecord, comparison, blob, comment, check or review.

Nothing caps how many rows the catalog holds. A reader's pages come first: the scan that
keeps the list current, and its filter's activity prefix as far as the reader has scrolled.
The backfill, from newest to oldest by creation, is background work,
which runs only while :mod:`.gh_budget` admits GraphQL work (:func:`backfill_admitted`).
Held, the job stops at a page boundary, and a later ask resumes it from the saved cursor.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial
from time import monotonic_ns
from typing import Any, Final, Literal

from metabrowser import event_log
from metabrowser.builtin_plugins.github import gh_budget, gh_lanes, pull_list
from metabrowser.builtin_plugins.github.avatars import avatar_of
from metabrowser.builtin_plugins.github.checkout import claim_source
from metabrowser.builtin_plugins.github.gh import GhCursorError, GhError, GhServerError, gh_graphql
from metabrowser.builtin_plugins.github.gh_lists import (
    READ_FAILURES,
    PullDataError,
    active_account,
    as_dict,
    cache_unwritable,
    login_of,
    newer_cache,
    readable_items,
    unknown_cache,
    utc_stamp,
)
from metabrowser.builtin_plugins.github.pull_catalog import (
    CATALOG_PROJECTION,
    PAGE_SIZE,
    CatalogRefreshTiming,
    CatalogState,
    CatalogUnusableError,
    NewerCatalogError,
    UnknownCatalogError,
    catalog_refusal,
    failure_line,
    publish_page,
    read_catalog,
    upgrade_catalog,
    write_catalog_refresh_timing,
)
from metabrowser.builtin_plugins.github.pull_list import (
    MAX_ROW_LABEL_BYTES,
    MAX_ROW_REF_BYTES,
    MAX_ROW_TITLE_BYTES,
    ListedRepository,
    PullListRow,
    rate_limit_holds,
    read_list_refresh,
    write_list_refresh,
)
from metabrowser.builtin_plugins.github.pull_record import MAX_LABELS, PullRefreshStamp, cut_escaped
from metabrowser.cache.locks import run_lock_section
from metabrowser.cache.paths import MAX_PULL_REQUEST_NUMBER, PULL_LIST_NAMES, PullListName
from metabrowser.home import PrivateStorageError
from metabrowser.mirror_refresh import FRESHNESS_WINDOW_S

log = logging.getLogger(__name__)
_MAX_RATE_HOLD_S = 15 * 60
_COMMIT_ID: Final = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")

# Two public repositories, two 100-row pages each (2026-11-03): 46–49 KB instead
# of REST's 1.9–2.2 MB, with every existing row field. GitHub reported cost=1/query.
# A page remains 100 rows and at most 100 bounded label names on each row.
# ``headRefOid`` lets a cached record or file list be checked against its row; on
# cli/cli's 100 newest rows it took a page from 58,811 to 64,410 bytes (9.5%), at the
# same cost of 1 (2026-11-11).
_QUERY = """query Catalog($owner:String!,$name:String!,$cursor:String) {
  viewer { login }
  rateLimit { cost }
  repository(owner:$owner,name:$name) {
    id
    all:pullRequests(first:1) { totalCount }
    open:pullRequests(first:1,states:OPEN) { totalCount }
    closed:pullRequests(first:1,states:[CLOSED,MERGED]) { totalCount }
    latest:pullRequests(first:1,orderBy:{field:UPDATED_AT,direction:DESC}) { nodes { updatedAt } }
    PREFIX_HEAD
    page:pullRequests(first:100,after:$cursor,orderBy:{field:ORDER,direction:DESC} FILTER) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number title state isDraft mergedAt createdAt updatedAt closedAt
        author { login avatar_url:avatarUrl(size:40) } baseRefName headRefName headRefOid headRepository { nameWithOwner }
        labels(first:100) { nodes { name } pageInfo { hasNextPage } }
      }
    }
  }
}"""
_FILTERS = {"all": "", "open": ",states:OPEN", "closed": ",states:[CLOSED,MERGED]"}
_PREFIX_HEAD = (
    "prefixHead:pullRequests(first:1,orderBy:{field:UPDATED_AT,direction:DESC} FILTER)"
    " { nodes { number updatedAt } }"
)


def _required_ref(value: object) -> tuple[str, bool]:
    if not isinstance(value, str):
        raise TypeError
    return cut_escaped(value, MAX_ROW_REF_BYTES)


def _row(value: object) -> tuple[PullListRow, bool]:
    """A row from one list item, and whether a bound cut anything in it."""

    item = as_dict(value)
    head = as_dict(item["head"])
    raw_title = item.get("title")
    title, title_cut = cut_escaped(
        raw_title if isinstance(raw_title, str) else "", MAX_ROW_TITLE_BYTES
    )
    base_ref, base_cut = _required_ref(as_dict(item["base"]).get("ref"))
    head_ref, head_cut = _required_ref(head.get("ref"))
    repository = head.get("repo")
    full_name = repository.get("full_name") if isinstance(repository, dict) else None  # pyright: ignore[reportUnknownMemberType]
    head_repository, repository_cut = (
        cut_escaped(full_name, MAX_ROW_REF_BYTES) if isinstance(full_name, str) else (None, False)
    )
    sha = head.get("sha")
    # A head GitHub did not name as a commit ID is unknown, not a reason to drop the row.
    head_oid = sha if isinstance(sha, str) and _COMMIT_ID.fullmatch(sha) else None
    labels = item.get("labels")
    listed: list[object] = labels if isinstance(labels, list) else []  # pyright: ignore[reportUnknownVariableType]
    names = [as_dict(label).get("name") for label in listed[:MAX_LABELS]]
    cut_names = [cut_escaped(name, MAX_ROW_LABEL_BYTES) for name in names if isinstance(name, str)]
    row = PullListRow(
        number=item["number"],
        title=title,
        state=item["state"],
        draft=item.get("draft") is True,
        merged_at=item.get("merged_at"),
        author=login_of(item.get("user")),
        author_avatar_url=avatar_of(item.get("user")),
        created_at=item["created_at"],
        updated_at=item["updated_at"],
        closed_at=item.get("closed_at"),
        base_ref=base_ref,
        head_ref=head_ref,
        head_repository=head_repository,
        labels=tuple(name for name, _cut in cut_names),
        head_oid=head_oid,
    )
    cut = (
        title_cut
        or base_cut
        or head_cut
        or repository_cut
        or len(listed) > MAX_LABELS
        or len(cut_names) < len(names)
        or any(name_cut for _name, name_cut in cut_names)
    )
    return row, cut


def _rows(values: Sequence[object]) -> tuple[tuple[PullListRow, ...], bool]:
    """The rows that could be read, and whether anything was cut or left out."""

    cut_any = False

    def build(value: object) -> PullListRow:
        nonlocal cut_any
        row, cut = _row(value)
        cut_any = cut_any or cut
        return row

    rows, dropped = readable_items(values, build)
    return rows, dropped or cut_any


@dataclass(frozen=True, slots=True)
class CatalogPage:
    repository_id: str
    rows: tuple[PullListRow, ...]
    totals: dict[str, int]
    cursor: str | None
    done: bool
    latest: str | None
    prefix_head: tuple[str, int] | None
    truncated: bool


def _graph_row(value: object) -> dict[str, Any]:
    raw = as_dict(value)
    state = raw["state"]
    if state not in {"OPEN", "CLOSED", "MERGED"}:
        raise ValueError("invalid pull-request state")
    head = raw.get("headRepository")
    return {
        "number": raw["number"],
        "title": raw["title"],
        "state": "open" if state == "OPEN" else "closed",
        "draft": raw["isDraft"],
        "merged_at": raw["mergedAt"],
        "created_at": raw["createdAt"],
        "updated_at": raw["updatedAt"],
        "closed_at": raw["closedAt"],
        "user": raw.get("author"),
        "base": {"ref": raw["baseRefName"]},
        "head": {
            "ref": raw["headRefName"],
            "sha": raw.get("headRefOid"),
            "repo": {"full_name": head.get("nameWithOwner")} if isinstance(head, dict) else None,
        },
        "labels": as_dict(raw["labels"])["nodes"],
    }


async def _read_page(
    repository: ListedRepository,
    name: PullListName,
    cursor: str | None,
    *,
    login: str,
    updated: bool = False,
    backfill: bool = False,
) -> CatalogPage:
    foreground = not updated and not backfill
    query = (
        _QUERY.replace("PREFIX_HEAD", _PREFIX_HEAD if foreground else "")
        .replace("ORDER", "CREATED_AT" if backfill else "UPDATED_AT")
        .replace("FILTER", _FILTERS[name])
    )
    if foreground:
        query = query.replace("query Catalog(", "query CatalogActivity(", 1)
    try:
        data = await gh_graphql(
            query,
            {
                "owner": repository.owner,
                "name": repository.repo,
                "cursor": cursor,
            },
            now=pull_list.utc_now(),
        )
    except GhCursorError:
        raise
    except GhError as exc:
        message = (
            "GitHub has no readable repository here"
            if exc.state == "not_found_or_private"
            else str(exc)
        )
        raise PullDataError(exc.state, message, reset_at=exc.reset_at) from exc
    try:
        if as_dict(data["viewer"])["login"] != login:
            raise PullDataError("account_changed", "the active gh account changed during the read")
        raw = data["repository"]
        if raw is None:
            raise PullDataError("not_found_or_private", "GitHub has no readable repository here")
        repo = as_dict(raw)
        repository_id = repo["id"]
        if not isinstance(repository_id, str) or not 1 <= len(repository_id) <= 256:
            raise ValueError("invalid repository identity")
        totals = {key: as_dict(repo[key])["totalCount"] for key in _FILTERS}
        if any(type(value) is not int or value < 0 for value in totals.values()):
            raise ValueError("invalid repository count")
        page = as_dict(repo["page"])
        values = page["nodes"]
        if not isinstance(values, list) or len(values) > PAGE_SIZE:
            raise ValueError("invalid metadata page")
        rows, truncated = _rows([_graph_row(value) for value in values])
        # A malformed page cannot advance its cursor past rows we could not keep.
        if len(rows) != len(values):
            raise ValueError("unreadable metadata row")
        info = as_dict(page["pageInfo"])
        more = info["hasNextPage"]
        following = info["endCursor"]
        if not isinstance(more, bool) or (
            following is not None
            and (not isinstance(following, str) or not 1 <= len(following) <= 1024)
        ):
            raise ValueError("invalid metadata cursor")
        if more and (not rows or following is None or following == cursor):
            raise ValueError("metadata cursor did not advance")
        latest_rows = as_dict(repo["latest"])["nodes"]
        latest = as_dict(latest_rows[0])["updatedAt"] if latest_rows else None
        if latest is not None:
            pull_list.parse_stamp(latest)
        prefix_head = None
        if foreground:
            prefix_rows = as_dict(repo["prefixHead"])["nodes"]
            if prefix_rows:
                head = as_dict(prefix_rows[0])
                number, stamp = head["number"], head["updatedAt"]
                if type(number) is not int or not 1 <= number <= MAX_PULL_REQUEST_NUMBER:
                    raise ValueError("invalid activity prefix head")
                pull_list.parse_stamp(stamp)
                prefix_head = (stamp, number)
        truncated = truncated or any(
            as_dict(as_dict(as_dict(value)["labels"])["pageInfo"])["hasNextPage"]
            for value in values
        )
        return CatalogPage(
            repository_id, rows, totals, following, not more, latest, prefix_head, truncated
        )
    except (*READ_FAILURES, ValueError, IndexError) as exc:
        raise PullDataError(
            "gh_failed", "GitHub answered with an unreadable metadata page"
        ) from exc


def prefix_wanted(state: CatalogState, name: PullListName, target: int) -> bool:
    """Whether *name*'s first *target* rows, which a reader asked for, are not all cached."""

    return (
        not state.done["all"]
        and not state.done[name]
        and min(state.covered[name], state.cached[name]) < min(target, state.totals[name])
    )


def backfill_admitted() -> bool:
    """Whether GitHub's GraphQL budget admits the backfill past every reader's prefix.

    That backfill is background work, which :mod:`.gh_budget` admits only above its floor
    and outside a rate hold, and speculative work, which it admits only within its share of
    the process's ceiling. Unlike the cores walk, it reserves nothing of that share for the
    prefetch, and the walk waits for it (``pull_cores``): it reads one
    :data:`~.pull_catalog.PAGE_SIZE` of rows a point, once per catalog epoch, and Quick
    Search across every state and the ref chooser's pull requests by branch are complete
    only once it has, where reserving the prefetch's caps held a cold catalog of 800 rows
    to 8 points an hour with the walk (review D1 of #737). A reader's own pages, its
    filter's prefix and the scan that keeps the list current, are never asked.

    So a backfill of more pages than the share has left takes it first come until it is
    done, and the prefetch and the label set's first read get what it leaves: a record not
    read ahead is read by its page when opened, and a page's label chips wait. In review
    B2's model of #761, a model and not a measurement, that costs the prefetch little
    below about 12,000 rows, and from about 15,000 leaves it about two records in each
    whole hour the backfill runs after the first. Leaving the prefetch a scan's records
    here too kept it at its cap but left a backfill of 20,000 rows unfinished after six
    hours.
    """

    return gh_budget.admission(("graphql",), now=pull_list.utc_now(), speculative=True).admitted


def _next_scan(
    state: CatalogState | None, name: PullListName, target: int
) -> tuple[Literal["all", "open", "closed", "updated"] | None, bool]:
    """The next scan, and whether it is the background backfill past *target*."""

    if state is None:
        return name, False
    if state.delta_started or (
        pull_list.utc_now() - pull_list.parse_stamp(state.fetched_at)
        > timedelta(seconds=FRESHNESS_WINDOW_S)
    ):
        return "updated", False
    if prefix_wanted(state, name, target):
        return name, False
    return ("all", True) if not state.done["all"] else (None, False)


_LIST: Final = "the pull-request list"


async def _publish(
    repository: ListedRepository,
    previous: CatalogState | None,
    proposed: CatalogState,
    rows: tuple[PullListRow, ...],
) -> bool:
    return await _write_catalog(
        repository, partial(publish_page, repository, previous, proposed, rows)
    )


async def _write_catalog[T](repository: ListedRepository, write: Callable[[], T]) -> T:
    try:
        return await run_lock_section(write)
    except NewerCatalogError as exc:
        raise newer_cache(
            _LIST, str(exc), source=repository.source, checkout=repository.checkout
        ) from exc
    except UnknownCatalogError as exc:
        raise unknown_cache(
            _LIST, str(exc), source=repository.source, checkout=repository.checkout
        ) from exc
    except (PrivateStorageError, OSError, sqlite3.Error, CatalogUnusableError) as exc:
        # The job's own catch records only the message, so the cause is logged here.
        log.warning(
            "the pull-request catalog of %s could not be written: %s",
            repository.source,
            failure_line(exc),
        )
        raise cache_unwritable(
            _LIST, exc, source=repository.source, checkout=repository.checkout
        ) from exc


async def _stop_at_kept_catalog(repository: ListedRepository) -> None:
    """Stop before GitHub is asked for a page no publication could keep.

    That is a catalog a newer release wrote, or one whose versions cannot be read, which
    a writer leaves as it is.
    """

    refusal = await asyncio.to_thread(catalog_refusal, repository.home, repository.slug)
    if refusal is None:
        return
    kind, why = refusal
    refuse = newer_cache if kind == "newer" else unknown_cache
    raise refuse(_LIST, why, source=repository.source, checkout=repository.checkout)


def _rate_limit_retry_at(now: datetime, previous: PullRefreshStamp | None) -> str:
    """Hold for at least a minute and back off if a refusal follows the last reset."""

    delay = FRESHNESS_WINDOW_S
    if previous is not None and previous.outcome == "rate_limited" and previous.reset_at:
        reset = pull_list.parse_stamp(previous.reset_at)
        if 0 <= (now - reset).total_seconds() <= FRESHNESS_WINDOW_S:
            previous_delay = (reset - pull_list.parse_stamp(previous.at)).total_seconds()
            delay = min(_MAX_RATE_HOLD_S, max(delay, 2 * previous_delay))
    deadline = now + timedelta(seconds=delay)
    if deadline.microsecond:
        deadline += timedelta(seconds=1)
    return utc_stamp(deadline)


async def refresh_pull_list(
    repository: ListedRepository,
    name: PullListName,
    *,
    target: int = 500,
    slot: asyncio.Semaphore | None = None,
    demand: Callable[[], tuple[PullListName, int]] | None = None,
    retry: bool = False,
    take_retry: Callable[[], bool] | None = None,
) -> CatalogState:
    """Warm a requested prefix, then resume all metadata; each page yields its slot.

    The backfill past the prefix stops, returning the checkpoint, while the GraphQL budget
    holds background work.
    """
    started_ns = monotonic_ns()
    published_epoch: str | None = None
    published_pages = 0
    reader: str | None = None
    last_refresh: PullRefreshStamp | None = None
    source_claimed = False
    try:
        repository = await claim_source(repository)
        source_claimed = True
        await _stop_at_kept_catalog(repository)
        await _write_catalog(repository, partial(upgrade_catalog, repository))
        login = await active_account()
        reader = f"gh:{login}"
        restarted: set[tuple[str, bool]] = set()
        activity_restarted: set[PullListName] = set()
        activity_deferred: set[PullListName] = set()
        # The lane the job was started in: a reader's pages serve it, and the rest serve
        # the background (:mod:`.gh_lanes`). A delta scan serves the reader when a change
        # or a Refresh asked for it, through all its pages, and otherwise it is due by age.
        asked_lane = gh_lanes.current_lane()
        delta_asked = False
        while True:
            previous = await asyncio.to_thread(read_catalog, repository.home, repository.slug)
            state = (
                previous
                if previous is not None
                and previous.reader == reader
                and previous.source == repository.source
                else None
            )
            if state is not None and state.projection_version < CATALOG_PROJECTION:
                # Enrich already cached rows once without discarding their offline view.
                # Only the full backfill restarts. Filtered activity progress and the
                # mutable-data watermark remain useful. A losing writer rereads.
                upgraded = state.model_copy(
                    update={
                        "projection_version": CATALOG_PROJECTION,
                        "backfill_cursor": None,
                        "done": {**state.done, "all": False},
                    }
                )
                await _publish(repository, previous, upgraded, ())
                continue
            selected, wanted = demand() if demand else (name, target)
            force = take_retry() if take_retry else False
            asked = (retry or force) and state is not None
            scan, backfill = ("updated", False) if asked else _next_scan(state, selected, wanted)
            retry = False
            if scan is None:
                break
            updated = scan == "updated"
            if updated:
                # A delta scan already under way keeps the lane its first page served.
                delta_asked = asked or (delta_asked and state is not None and state.delta_started)
            lane: gh_lanes.Lane = (
                "background" if backfill or (updated and not delta_asked) else asked_lane
            )
            cursor = None
            if state is not None:
                if backfill:
                    cursor = state.backfill_cursor
                elif scan == "updated":
                    cursor = state.delta_cursor
                elif scan in activity_deferred:
                    return state
                else:
                    cursor = state.cursors[scan]
            try:
                async with slot if slot is not None else contextlib.nullcontext():
                    last_refresh = await asyncio.to_thread(
                        read_list_refresh, repository.home, repository.slug, "all"
                    )
                    if rate_limit_holds(last_refresh, now=pull_list.utc_now()):
                        assert last_refresh is not None
                        raise PullDataError(
                            "rate_limited",
                            "GitHub's API rate limit is exhausted",
                            reset_at=last_refresh.reset_at,
                        )
                    if backfill and not backfill_admitted():
                        # Paused, not failed: the next ask resumes from the saved cursor.
                        break
                    # A delta scan vouches for what GitHub had when it asked for its first page.
                    asked_at = utc_stamp(pull_list.utc_now())
                    # A backfill page is one no reader asked for: speculative work, counted
                    # toward its share (:mod:`.gh_budget`).
                    with (
                        gh_budget.speculative() if backfill else contextlib.nullcontext(),
                        gh_lanes.serving(lane),
                    ):
                        page = await _read_page(
                            repository,
                            "all" if updated else scan,
                            cursor,
                            login=login,
                            updated=updated,
                            backfill=backfill,
                        )
                    # The query's viewer identifies the reader of these rows. A settings
                    # switch after that response cannot relabel it; the next page must
                    # still match this job's reader before it can advance the checkpoint.
            except GhCursorError as exc:
                key = (scan, backfill)
                if state is None or cursor is None or key in restarted:
                    raise PullDataError("gh_failed", str(exc)) from exc
                restarted.add(key)
                if updated:
                    retry_state = state.model_copy(
                        update={
                            "delta_cursor": None,
                            "delta_started": False,
                            "delta_started_at": None,
                        }
                    )
                    retry = True
                elif backfill:
                    retry_state = state.model_copy(update={"backfill_cursor": None})
                else:
                    retry_state = state.model_copy(
                        update={
                            "cursors": {**state.cursors, scan: None},
                            "covered": {**state.covered, scan: 0},
                        }
                    )
                await _publish(repository, previous, retry_state, ())
                continue
            now = utc_stamp(pull_list.utc_now())
            if state is None or state.repository_id != page.repository_id:
                state = CatalogState(
                    projection_version=CATALOG_PROJECTION,
                    source=repository.source,
                    repository_id=page.repository_id,
                    reader=reader,
                    fetched_at=now,
                    count_at=now,
                    watermark=page.latest,
                    totals=page.totals,
                )
                if cursor is not None:
                    # A transferred/replaced repository cannot inherit a resume cursor.
                    await _publish(repository, previous, state, ())
                    continue
            changes: dict[str, Any] = {
                "totals": page.totals,
                "count_at": now,
                "truncated": state.truncated or page.truncated,
            }
            if updated:
                watermark = state.delta_watermark if state.delta_started else page.latest
                started_at = (
                    state.delta_started_at
                    if state.delta_started and state.delta_started_at is not None
                    else asked_at
                )
                reached = page.done or any(
                    state.watermark is not None and row.updated_at < state.watermark
                    for row in page.rows
                )
                changes.update(
                    delta_started=not reached,
                    delta_cursor=None if reached else page.cursor,
                    delta_watermark=None if reached else watermark,
                    delta_started_at=None if reached else started_at,
                )
                if reached:
                    changes.update(fetched_at=started_at, watermark=watermark or state.watermark)
            elif backfill:
                changes.update(
                    backfill_cursor=None if page.done else page.cursor,
                    done=dict.fromkeys(PULL_LIST_NAMES, True) if page.done else state.done,
                )
            elif cursor is not None and state.prefix_heads[scan] != page.prefix_head:
                # The provider's activity window moved while the cursor was open.
                # Keep its rows and restart coverage from the new head.
                changes.update(
                    cursors={**state.cursors, scan: None},
                    covered={**state.covered, scan: 0},
                )
                if scan in activity_restarted:
                    activity_deferred.add(scan)
                activity_restarted.add(scan)
            else:
                cursors, covered, done = dict(state.cursors), dict(state.covered), dict(state.done)
                cursors[scan], covered[scan], done[scan] = (
                    page.cursor,
                    covered[scan] + len(page.rows),
                    page.done,
                )
                changes.update(
                    cursors=cursors,
                    covered=covered,
                    done=done,
                    prefix_heads={**state.prefix_heads, scan: page.prefix_head},
                )
            proposed = state.model_copy(update=changes)
            accepted = await _publish(repository, previous, proposed, page.rows)
            if accepted:
                published_epoch = proposed.epoch
                published_pages += 1
                await run_lock_section(
                    partial(
                        write_list_refresh,
                        repository.home,
                        repository.slug,
                        "all",
                        PullRefreshStamp(
                            outcome="succeeded",
                            at=proposed.fetched_at,
                            reader=reader,
                        ),
                    )
                )
            await asyncio.sleep(0)
    except PullDataError as exc:
        now = pull_list.utc_now()
        outcome = "github_unavailable" if isinstance(exc.__cause__, GhServerError) else exc.state
        message, reset_at = str(exc), exc.reset_at
        if exc.state == "rate_limited" and reset_at is None:
            message = "GitHub reached its API rate limit without reporting a reset time"
            reset_at = _rate_limit_retry_at(now, last_refresh)
        await run_lock_section(
            partial(
                write_list_refresh,
                repository.home,
                repository.slug,
                "all",
                PullRefreshStamp(
                    outcome=outcome,
                    message=message[:1000],
                    reset_at=reset_at,
                    at=utc_stamp(now),
                    reader=reader,
                ),
                persist=source_claimed,
            )
        )
        if outcome != exc.state:
            raise PullDataError(outcome, message) from exc
        raise
    finally:
        finished_at = pull_list.utc_now()
        duration_ms = round((monotonic_ns() - started_ns) / 1_000_000)
        event_log.current().set(
            refresh_finished_at=finished_at.isoformat().replace("+00:00", "Z"),
            refresh_duration_ms=duration_ms,
            refresh_pages=published_pages,
        )

    assert state is not None
    if state.epoch == published_epoch:
        timing = CatalogRefreshTiming(
            epoch=state.epoch, finished_at=finished_at, duration_ms=duration_ms
        )
        await run_lock_section(partial(write_catalog_refresh_timing, repository, timing))
    return state


__all__ = ["backfill_admitted", "prefix_wanted", "refresh_pull_list"]
