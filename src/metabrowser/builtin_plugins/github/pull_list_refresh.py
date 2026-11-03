"""Read one list of a repository's pull requests with ``gh api``, and keep it.

:func:`refresh_pull_list` is the whole network job, and it runs no Git:

1. the active github.com account, from ``gh auth status``;
2. the pages, one ``gh api`` request each, ``sort=created&direction=desc``: every page the
   file holds, or the first page when the file is another reader's or there is none, or
   with ``more`` only the page after the ones it holds;
3. the account again: a list read while the active account changed is discarded;
4. the list, written atomically, and how the refresh ended, beside it.

Each full-size page goes out with its own ``If-None-Match`` when the same reader read it
last, and a ``304`` reuses that page's rows, which GitHub does not count against the
primary rate limit. The one exception is a complete list's last page when it may be full,
which is read whole: see :func:`_page_etag`. A page that fails fails the job, and the file
stays as it was.

The list is assembled over the job's duration and is not atomic. A pull request that opens
or closes between two page reads can appear twice, which the number dedupes, or be missed
until the next refresh; a page read later wins, being newer. ``more`` appends to what the
file holds, so the file keeps its ``fetched_at`` and a later refresh reads it all again.

Pages from two readers are never joined. A successful refresh by another account replaces
the whole file, so **Load more** under a new account starts again from the first page.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from pydantic import ValidationError

from metabrowser.builtin_plugins.github import pull_list
from metabrowser.builtin_plugins.github.checkout import claim_source
from metabrowser.builtin_plugins.github.gh_lists import (
    PullDataError,
    active_account,
    as_dict,
    login_of,
    read_list,
    readable_items,
    utc_stamp,
)
from metabrowser.builtin_plugins.github.pull_list import (
    MAX_ROW_LABEL_BYTES,
    MAX_ROW_REF_BYTES,
    MAX_ROW_TITLE_BYTES,
    PULL_LIST_SCHEMA,
    ListedRepository,
    ListPageMark,
    PullList,
    PullListRow,
    can_extend,
    read_pull_list,
    write_list_refresh,
    write_pull_list,
)
from metabrowser.builtin_plugins.github.pull_record import (
    API_PAGE_SIZE,
    MAX_LABELS,
    PullRefreshStamp,
    RecordTooLargeError,
    cut_escaped,
)
from metabrowser.cache.paths import PullListName
from metabrowser.home import PrivateStorageError

log = logging.getLogger(__name__)

_MESSAGE_CHARS: Final = 1000
# gh's wording for a refused path is a pull request's; a list asks about a repository.
_NO_REPOSITORY: Final = (
    "GitHub has no such repository, or it is private and the gh account cannot read it"
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
        created_at=item["created_at"],
        updated_at=item["updated_at"],
        closed_at=item.get("closed_at"),
        base_ref=base_ref,
        head_ref=head_ref,
        head_repository=head_repository,
        labels=tuple(name for name, _cut in cut_names),
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
class _Page:
    mark: ListPageMark
    rows: tuple[PullListRow, ...]
    has_next: bool


def _reused_page(previous: PullList, number: int) -> _Page:
    """Page *number* as *previous* holds it, after GitHub said it is unchanged."""

    mark = previous.etags[number - 1]
    held = {row.number: row for row in previous.rows}
    # A 304 carries no Link, so this is what the file knew: :func:`_page_etag` asks whole any
    # last page that could have gained a next one with its body unchanged.
    has_next = number < previous.pages or not previous.complete
    return _Page(mark, tuple(held[each] for each in mark.numbers), has_next)


def _page_etag(previous: PullList | None, number: int) -> str | None:
    """The ETag to ask page *number* with, or ``None`` to read it whole.

    A pull request that closes or reopens goes into ``closed`` or ``open`` at its created
    rank, which can be below every row a list holds. Below a page that is short, that
    changes the page's body. Below a page that is full, it starts a new page and leaves
    the body as it was, so GitHub answers ``304``, with no ``Link``, and the list would go
    on saying ``complete`` with no way for a reader to reach the rest. So a complete list's
    last page is read whole when it may be full, as a mark that lost an item may have been.
    That is one counted request a refresh, for a list whose rows are a multiple of a hundred.
    """

    if previous is None or number > previous.pages:
        return None
    mark = previous.etags[number - 1]
    may_be_full = len(mark.numbers) == API_PAGE_SIZE or mark.truncated
    return None if previous.complete and number == previous.pages and may_be_full else mark.etag


async def _read_page(
    repository: ListedRepository, name: PullListName, number: int, previous: PullList | None
) -> _Page:
    """Full-size page *number*. *previous*, by the same reader, may make it conditional."""

    try:
        read = await read_list(
            f"repos/{repository.owner}/{repository.repo}/pulls",
            key=None,
            cap=API_PAGE_SIZE,
            etag=_page_etag(previous, number),
            now=pull_list.utc_now,
            query=f"state={name}&sort=created&direction=desc",
            first_page=number,
        )
    except PullDataError as exc:
        if exc.state == "not_found_or_private":
            raise PullDataError(exc.state, _NO_REPOSITORY) from exc
        raise
    if read.items is None:
        # Only a conditional request, which needs a previous list, is answered 304.
        assert previous is not None
        return _reused_page(previous, number)
    rows, cut = _rows(read.items)
    return _Page(
        ListPageMark(
            etag=read.etag,
            numbers=tuple(row.number for row in rows),
            truncated=read.left_out or cut,
        ),
        rows,
        read.more,
    )


def _assembled(
    repository: ListedRepository,
    name: PullListName,
    reader: str,
    pages: Sequence[_Page],
    *,
    fetched_at: str,
) -> PullList:
    """Pages joined into one list: each pull request once, highest number first."""

    by_number = {row.number: row for page in pages for row in page.rows}
    try:
        return PullList(
            schema_version=PULL_LIST_SCHEMA,
            source=repository.source,
            list=name,
            fetched_at=fetched_at,
            reader=reader,
            pages=len(pages),
            complete=not pages[-1].has_next,
            truncated=any(page.mark.truncated for page in pages),
            etags=tuple(page.mark for page in pages),
            rows=tuple(by_number[number] for number in sorted(by_number, reverse=True)),
        )
    except ValidationError as exc:
        raise PullDataError(
            "gh_failed", "GitHub answered with a list Metabrowser cannot read"
        ) from exc


async def _read_held_pages(
    repository: ListedRepository, name: PullListName, reader: str, previous: PullList | None
) -> PullList:
    wanted = previous.pages if previous is not None else 1
    pages: list[_Page] = []
    for number in range(1, wanted + 1):
        page = await _read_page(repository, name, number, previous)
        pages.append(page)
        if not page.has_next:
            break
    fetched_at = utc_stamp(pull_list.utc_now())
    return _assembled(repository, name, reader, pages, fetched_at=fetched_at)


async def _read_one_more_page(
    repository: ListedRepository, name: PullListName, previous: PullList
) -> PullList:
    held = [_reused_page(previous, number) for number in range(1, previous.pages + 1)]
    page = await _read_page(repository, name, previous.pages + 1, None)
    return _assembled(
        repository, name, previous.reader, [*held, page], fetched_at=previous.fetched_at
    )


async def _write(repository: ListedRepository, listed: PullList) -> None:
    try:
        await asyncio.to_thread(write_pull_list, repository.home, repository.slug, listed)
    except (RecordTooLargeError, PrivateStorageError, OSError) as exc:
        log.debug("could not write the list of pull requests: %s", exc)
        raise PullDataError(
            "cache_unwritable", "the list of pull requests could not be written to the cache"
        ) from exc


async def _refresh(
    repository: ListedRepository, name: PullListName, login: str, *, more: bool
) -> PullList:
    reader = f"gh:{login}"
    cached = await asyncio.to_thread(read_pull_list, repository.home, repository.slug, name)
    previous = cached if isinstance(cached, PullList) and cached.reader == reader else None
    if more and previous is not None and can_extend(previous):
        listed = await _read_one_more_page(repository, name, previous)
    else:
        listed = await _read_held_pages(repository, name, reader, previous)
    if await active_account() != login:
        raise PullDataError(
            "account_changed",
            "the active gh account changed during the read, so what was read is discarded; "
            "open the list again",
        )
    await _write(repository, listed)
    return listed


async def refresh_pull_list(
    repository: ListedRepository, name: PullListName, *, more: bool = False
) -> PullList:
    """Read list *name* of *repository* from GitHub and cache it; see the module.

    *more* extends the list by one GitHub page. Raises only :class:`PullDataError`, and a
    failure leaves the file as it was. How it ended is kept beside the list either way.
    """

    reader: str | None = None
    try:
        # A checkout's source is published by its first write, which this is.
        repository = await claim_source(repository)
        login = await active_account()
        reader = f"gh:{login}"
        listed = await _refresh(repository, name, login, more=more)
    except PullDataError as exc:
        stamp = PullRefreshStamp(
            outcome=exc.state,
            message=str(exc)[:_MESSAGE_CHARS],
            reset_at=exc.reset_at,
            at=utc_stamp(pull_list.utc_now()),
            reader=reader,
        )
        await asyncio.to_thread(write_list_refresh, repository.home, repository.slug, name, stamp)
        raise
    # As of the moment the list is as of. ``more`` keeps ``fetched_at``, and the age the route
    # calls stale and the window an automatic refresh waits for are one clock.
    succeeded = PullRefreshStamp(outcome="succeeded", at=listed.fetched_at, reader=reader)
    await asyncio.to_thread(write_list_refresh, repository.home, repository.slug, name, succeeded)
    return listed


__all__ = ["refresh_pull_list"]
