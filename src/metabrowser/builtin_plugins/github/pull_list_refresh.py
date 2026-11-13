"""Backfill lightweight PR metadata and refresh only rows changed since a checkpoint.

Every GitHub page is independently bounded and published before the next begins. The
server's catalog worker yields its network slot after each page, resumes durable cursors,
and never fetches a PullRecord, comparison, blob, comment, check or review.
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
from typing import Any, Final, Literal

from metabrowser.builtin_plugins.github import pull_list
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
    CatalogState,
    CatalogUnusableError,
    NewerCatalogError,
    UnknownCatalogError,
    catalog_refusal,
    failure_line,
    publish_page,
    read_catalog,
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
from metabrowser.cache.paths import PullListName
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
  repository(owner:$owner,name:$name) {
    id
    all:pullRequests(first:1) { totalCount }
    open:pullRequests(first:1,states:OPEN) { totalCount }
    closed:pullRequests(first:1,states:[CLOSED,MERGED]) { totalCount }
    latest:pullRequests(first:1,orderBy:{field:UPDATED_AT,direction:DESC}) { nodes { updatedAt } }
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
) -> CatalogPage:
    query = _QUERY.replace("ORDER", "UPDATED_AT" if updated else "CREATED_AT").replace(
        "FILTER", "" if updated else _FILTERS[name]
    )
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
        truncated = truncated or any(
            as_dict(as_dict(as_dict(value)["labels"])["pageInfo"])["hasNextPage"]
            for value in values
        )
        return CatalogPage(repository_id, rows, totals, following, not more, latest, truncated)
    except (*READ_FAILURES, ValueError, IndexError) as exc:
        raise PullDataError(
            "gh_failed", "GitHub answered with an unreadable metadata page"
        ) from exc


def _next_scan(
    state: CatalogState | None, name: PullListName, target: int
) -> Literal["all", "open", "closed", "updated"] | None:
    if state is None:
        return name
    if state.delta_started or (
        pull_list.utc_now() - pull_list.parse_stamp(state.fetched_at)
        > timedelta(seconds=FRESHNESS_WINDOW_S)
    ):
        return "updated"
    if (
        not state.done["all"]
        and not state.done[name]
        and min(state.covered[name], state.cached[name]) < min(target, state.totals[name])
    ):
        return name
    return "all" if not state.done["all"] else None


_LIST: Final = "the pull-request list"


async def _publish(
    repository: ListedRepository,
    previous: CatalogState | None,
    proposed: CatalogState,
    rows: tuple[PullListRow, ...],
) -> bool:
    try:
        return await run_lock_section(partial(publish_page, repository, previous, proposed, rows))
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
    """Warm a requested prefix, then resume all metadata; each page yields its slot."""
    reader: str | None = None
    last_refresh: PullRefreshStamp | None = None
    source_claimed = False
    try:
        repository = await claim_source(repository)
        source_claimed = True
        await _stop_at_kept_catalog(repository)
        login = await active_account()
        reader = f"gh:{login}"
        restarted: set[str] = set()
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
                # Only ALL restarts: filtered progress and the mutable-data watermark
                # remain useful. A losing writer rereads the accepted checkpoint.
                upgraded = state.model_copy(
                    update={
                        "projection_version": CATALOG_PROJECTION,
                        "cursors": {**state.cursors, "all": None},
                        "covered": {**state.covered, "all": 0},
                        "done": {**state.done, "all": False},
                    }
                )
                await _publish(repository, previous, upgraded, ())
                continue
            selected, wanted = demand() if demand else (name, target)
            force = take_retry() if take_retry else False
            scan = (
                "updated"
                if (retry or force) and state is not None
                else _next_scan(state, selected, wanted)
            )
            retry = False
            if scan is None:
                assert state is not None
                return state
            updated = scan == "updated"
            cursor = (
                state.delta_cursor if state and updated else state.cursors[scan] if state else None
            )
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
                    # A delta scan vouches for what GitHub had when it asked for its first page.
                    asked_at = utc_stamp(pull_list.utc_now())
                    page = await _read_page(
                        repository, "all" if updated else scan, cursor, login=login, updated=updated
                    )
                    # The query's viewer identifies the reader of these rows. A settings
                    # switch after that response cannot relabel it; the next page must
                    # still match this job's reader before it can advance the checkpoint.
            except GhCursorError as exc:
                if state is None or cursor is None or scan in restarted:
                    raise PullDataError("gh_failed", str(exc)) from exc
                restarted.add(scan)
                cursors, covered = dict(state.cursors), dict(state.covered)
                if updated:
                    retry_state = state.model_copy(
                        update={
                            "delta_cursor": None,
                            "delta_started": False,
                            "delta_started_at": None,
                        }
                    )
                    retry = True
                else:
                    cursors[scan], covered[scan] = None, 0
                    retry_state = state.model_copy(update={"cursors": cursors, "covered": covered})
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
            else:
                cursors, covered, done = dict(state.cursors), dict(state.covered), dict(state.done)
                cursors[scan], covered[scan], done[scan] = (
                    page.cursor,
                    covered[scan] + len(page.rows),
                    page.done,
                )
                changes.update(cursors=cursors, covered=covered, done=done)
            proposed = state.model_copy(update=changes)
            accepted = await _publish(repository, previous, proposed, page.rows)
            if accepted:
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


__all__ = ["refresh_pull_list"]
