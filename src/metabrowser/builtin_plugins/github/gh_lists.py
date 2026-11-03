"""Read GitHub's lists through ``gh``: typed failures, the paging loop, and item helpers.

A pull request's record and a repository's list of pull requests are both one ``gh api``
request per page, so they share this: :func:`read_list` walks the pages and steps the page
size down when a page is larger than gh's output cap, and :class:`PullDataError` is the
one failure either raises. Nothing here reads or writes the cache, and nothing here needs
a store, so what is listed needs no Git.

The caller passes the clock, which :func:`gh_api` reads a ``Retry-After`` against, so each
caller's own clock seam reaches it.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, Literal

from pydantic import BaseModel, ValidationError

from metabrowser.builtin_plugins.github.gh import (
    GhError,
    GhOutputTooLargeError,
    GhResponse,
    gh_account,
    gh_api,
)
from metabrowser.builtin_plugins.github.pull_record import API_PAGE_SIZE

log = logging.getLogger(__name__)

# Page sizes a list steps down through when a page is larger than gh's output cap, each
# a divisor of the one before, so every page starts on a page boundary of its size.
_PAGE_SIZES: Final[tuple[int, ...]] = (API_PAGE_SIZE, 50, 25, 5, 1)
# Requests one list may make: the full pages its cap needs, plus ten asked again smaller
# after an oversized page. Past it the list is marked incomplete.
EXTRA_PAGE_REQUESTS: Final = 10
_LOGIN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\[\]-]{0,99}$")

type PullDataState = Literal[
    "gh_missing",
    "gh_too_old",
    "not_logged_in",
    "rate_limited",
    "not_found_or_private",
    "network_error",
    "gh_failed",
    "account_changed",
    "head_mismatch",
    "fetch_failed",
    "refreshing_elsewhere",
    "git_failed",
    "record_too_large",
    "cache_unwritable",
    "not_github",
]


class PullDataError(Exception):
    """Pull-request data could not be read or fetched; ``state`` says why.

    The message is for the user: it names what was asked for and never a local path, a
    token, or gh's or Git's own text.
    """

    def __init__(self, state: PullDataState, message: str, *, reset_at: str | None = None) -> None:
        super().__init__(message)
        self.state: PullDataState = state
        self.reset_at = reset_at


def utc_stamp(moment: datetime) -> str:
    """*moment* as every cached record and stamp spells a time."""

    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Reading one item ────────────────────────────────────────────


class UnreadableItemError(Exception):
    """A required field is missing or not what GitHub documents."""


READ_FAILURES: Final = (UnreadableItemError, KeyError, TypeError, ValidationError)


def as_dict(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise UnreadableItemError
    return value  # pyright: ignore[reportUnknownVariableType]


def login_of(user: object) -> str | None:
    login = user.get("login") if isinstance(user, dict) else None  # pyright: ignore[reportUnknownMemberType]
    return login if isinstance(login, str) and _LOGIN.match(login) else None


def readable_items[M: BaseModel](
    values: Sequence[object], build: Callable[[object], M]
) -> tuple[tuple[M, ...], bool]:
    """The items that could be read, and whether any was left out."""

    kept: list[M] = []
    for value in values:
        try:
            kept.append(build(value))
        except READ_FAILURES as exc:
            log.debug("left out an item GitHub sent that could not be read: %r", exc)
    return tuple(kept), len(kept) < len(values)


# ── Reading the API ─────────────────────────────────────────────


class PageTooLargeError(Exception):
    """One page was larger than gh's output cap."""


async def active_account() -> str:
    """The active github.com login, or the :class:`PullDataError` that says why not."""

    try:
        return await gh_account()
    except GhError as exc:
        raise PullDataError(exc.state, str(exc)) from exc


async def get_response(path: str, *, etag: str | None, now: datetime) -> GhResponse:
    try:
        return await gh_api(path, etag=etag, now=now)
    except GhOutputTooLargeError as exc:
        raise PageTooLargeError from exc
    except GhError as exc:
        raise PullDataError(exc.state, str(exc), reset_at=exc.reset_at) from exc


def response_json(response: GhResponse) -> object:
    try:
        return response.json()
    except GhError as exc:
        raise PullDataError("gh_failed", str(exc)) from exc


def _page_items(response: GhResponse, key: str | None) -> list[object]:
    payload = response_json(response)
    if key is not None:
        payload = payload.get(key) if isinstance(payload, dict) else None  # pyright: ignore[reportUnknownMemberType]
    if not isinstance(payload, list):
        raise PullDataError("gh_failed", "GitHub answered with a list Metabrowser cannot read")
    return payload  # pyright: ignore[reportUnknownVariableType]


def unconditional_304() -> PullDataError:
    return PullDataError("gh_failed", "GitHub answered 304 to a request that was not conditional")


@dataclass(frozen=True, slots=True)
class ListRead:
    """A list read from the API: new items, or ``None`` when the previous one stands.

    ``left_out`` says an item too large to read, or the request cap, cost it items.
    ``more`` says GitHub has more past what was read; it says nothing about a ``304``,
    whose caller knows from the read that ETag came from. ``last_page`` is the full-size
    page the first page's ``Link`` named last, when it was read whole and was not the last.
    """

    items: list[object] | None
    left_out: bool
    more: bool
    etag: str | None
    last_page: int | None = None

    @property
    def incomplete(self) -> bool:
        return self.left_out or self.more


async def read_list(
    path: str,
    *,
    key: str | None,
    cap: int,
    etag: str | None,
    now: Callable[[], datetime],
    query: str = "",
    first_page: int = 1,
) -> ListRead:
    """The items of *path* from full-size page *first_page*, up to *cap* places in the list.

    *query* is what the path's own query says, ahead of the page size and number. *etag*
    makes the first page conditional, and the answer's ``etag`` is that page's, when it
    was read whole.

    A page larger than gh's output cap is asked for again in smaller pages, down to one
    item; an item that alone is too large is left out and ``left_out`` set. *cap* counts
    places and not items kept, an item left out among them, so reading one page never runs
    into the next.
    """

    prefix = f"{path}?{query}&" if query else f"{path}?"
    items: list[object] = []
    first_etag: str | None = None
    last_page: int | None = None
    left_out = False
    start = (first_page - 1) * API_PAGE_SIZE
    end = start + cap
    offset = start
    size = API_PAGE_SIZE
    for _request in range(cap // API_PAGE_SIZE + EXTRA_PAGE_REQUESTS):
        whole_first_page = offset == start and size == API_PAGE_SIZE
        conditional = etag if whole_first_page else None
        try:
            response = await get_response(
                f"{prefix}per_page={size}&page={offset // size + 1}",
                etag=conditional,
                now=now(),
            )
        except PageTooLargeError:
            if size > 1:
                size = next(smaller for smaller in _PAGE_SIZES if smaller < size)
            else:
                log.debug("left out item %s of %s: larger than one page may be", offset, path)
                offset += 1
                left_out = True
                if offset >= end:
                    # No answer said whether anything follows, so it may.
                    return ListRead(items[:cap], True, True, first_etag, last_page)
            continue
        if response.status == 304:
            if conditional is not None:
                return ListRead(None, False, False, etag)
            raise unconditional_304()
        if whole_first_page:
            first_etag = response.etag
            last_page = response.last_page
        batch = _page_items(response, key)
        items.extend(batch)
        offset += len(batch)
        if not batch or not response.has_next_page:
            return ListRead(items[:cap], left_out, len(items) > cap, first_etag, last_page)
        if offset >= end:
            return ListRead(items[:cap], left_out, True, first_etag, last_page)
        size = max(candidate for candidate in _PAGE_SIZES if offset % candidate == 0)
    return ListRead(items[:cap], True, True, first_etag, last_page)


__all__ = [
    "EXTRA_PAGE_REQUESTS",
    "READ_FAILURES",
    "ListRead",
    "PageTooLargeError",
    "PullDataError",
    "PullDataState",
    "UnreadableItemError",
    "active_account",
    "as_dict",
    "get_response",
    "login_of",
    "read_list",
    "readable_items",
    "response_json",
    "unconditional_304",
    "utc_stamp",
]
