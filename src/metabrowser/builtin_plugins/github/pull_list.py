"""A repository's lists of pull requests: one validated JSON file per list, and its bounds.

There are three lists, GitHub's three ``state`` values, each in its own file at
``sources/<slug>/pulls/list-<name>.json`` beside the records, written by the home's
private atomic file write and read with a size bound. Each file is a prefix of one GitHub
listing, so ``complete`` has one meaning: GitHub has nothing past the last page read.
Pydantic validates a list on write and parses it on read; one whose ``schema_version`` is
not :data:`PULL_LIST_SCHEMA` is refetched, never migrated.

A row keeps only what a list shows. The description, the repository objects GitHub embeds
in every item, and every URL are dropped, and a list's item has no ``merged`` flag, so
"merged" is read from ``merged_at``.

Listing needs the home, the slug, and the owner and repository, which is
:class:`ListedRepository`: never a store, so a list can be read and written where no
mirror exists, and no Git runs.

The bounds are measured below, with ``gh api`` on 2026-11-02, on the repositories of the
ten pull requests the record's bounds were measured on (``pull_record.py``): ten pages of
``state=all``, 70 pages and 7,000 rows, at a load average of 10 to 30.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Annotated, Final, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)

from metabrowser.builtin_plugins.github.pull_record import (
    API_PAGE_SIZE,
    MAX_LABELS,
    Login,
    PullRefreshStamp,
    Reader,
    RecordAbsence,
    RecordTooLargeError,
    Timestamp,
    Url,
    read_refresh_stamp,
    write_refresh_stamp,
)
from metabrowser.cache.atomic import RecordError, read_bytes_bounded
from metabrowser.cache.paths import (
    MAX_PULL_REQUEST_NUMBER,
    PullListName,
    source_pull_list,
    source_pull_list_refresh,
    source_pulls_directory,
)
from metabrowser.home import (
    PrivateStorageError,
    SharedEntryPolicy,
    ensure_private_directory,
    write_private_file_atomic,
)
from metabrowser.mirror_refresh import FRESHNESS_WINDOW_S

log = logging.getLogger(__name__)

PULL_LIST_SCHEMA: Final = 1

# One page, ``sort=created&direction=desc``, as gh prints it with headers:
#
# - per_page=100: 1.41 to 2.85 MB (kubernetes/kubernetes page 8 was 2,848,033 bytes), in
#   1.44 to 2.81 s; each item embeds both repositories and the description;
# - per_page=50: 0.75 to 1.20 MB, in 1.28 to 1.52 s;
# - per_page=25: 0.38 to 0.60 MB, in 0.96 to 1.29 s.
#
# So most of a request is the request: a hundred rows take about 1.5 times as long as
# twenty-five, and API_PAGE_SIZE stays the page size. No page of the 70 came within a
# factor of 2.9 of GH_API_MAX_BYTES, so the step down to smaller pages stays what it is
# for the record, the answer to a page of very long descriptions. A conditional request
# GitHub answers 304 took 1.18 to 1.37 s (cli/cli, four runs), so a refresh of a held
# list costs more than a second a page, one after another.
#
# Pull requests per repository, open and closed: Hello-World 1,358 and 693; cli/cli 55 and
# 4,695; kubernetes 1,324 and 91,429; rust 1,429 and 98,209; vscode 3,084 and 67,891;
# cpython 2,297 and 77,177; pytorch 3,719 and 136,385. No cap holds a closed list, so the
# cap is what a refresh can afford: ten pages is at least twelve seconds of gh every
# minute for a reader who asked for all of them. It reaches back nine months on cli/cli
# and ten days on vscode and pytorch, and past it the list says that GitHub has more.
MAX_LIST_PAGES: Final = 10
MAX_LIST_ROWS: Final = MAX_LIST_PAGES * API_PAGE_SIZE

# Text in a row, in bytes as written, since JSON escaping counts: a title of control
# characters costs six bytes a character. Measured: the longest title 162 bytes (GitHub
# refuses more than 256 characters), the longest label name 41 (it refuses more than 50),
# the longest head branch 100, and the most labels on a row 43 (kubernetes). A row with
# more labels than MAX_LABELS, GitHub's own limit, is not expected either.
MAX_ROW_TITLE_BYTES: Final = 1024
MAX_ROW_REF_BYTES: Final = 256
MAX_ROW_LABEL_BYTES: Final = 64

# The read bound. A real list at the cap was 318 to 546 KB of rows, and the largest row
# 1,152 bytes (kubernetes, 43 labels). The worst row these bounds allow is 8,406 bytes, and
# ``tests/test_github_pull_list.py`` writes a list of a thousand of them and reads it back:
# 8.42 MB. So every list written can be read, and only a hostile one comes near this. The
# route parses a list once per write, 16 ms at the cap and 88 ms for the worst list, and
# after that answers in 0.3 ms at the cap as at one page (a realistic list, measured
# in-process at a load average near 40).
MAX_PULL_LIST_BYTES: Final = 10 * 1024 * 1024

type PullNumber = Annotated[int, Field(ge=1, le=MAX_PULL_REQUEST_NUMBER)]
type _RowText = Annotated[str, StringConstraints(max_length=MAX_ROW_REF_BYTES)]
type _LabelName = Annotated[str, StringConstraints(max_length=MAX_ROW_LABEL_BYTES)]


_UNWRITTEN_STAMPS: dict[str, PullRefreshStamp] = {}


def utc_now() -> datetime:
    """The clock lists and their stamps are read and written by; a seam for transcripts."""

    return datetime.now(UTC)


def parse_stamp(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PullListRow(_Model):
    """One pull request as a list shows it.

    ``head_repository`` is ``owner/name``, or ``None`` when a fork was deleted.
    """

    number: PullNumber
    title: Annotated[str, StringConstraints(max_length=MAX_ROW_TITLE_BYTES)]
    state: Literal["open", "closed"]
    draft: bool
    merged_at: Timestamp | None
    author: Login | None
    created_at: Timestamp
    updated_at: Timestamp
    closed_at: Timestamp | None
    base_ref: _RowText
    head_ref: _RowText
    head_repository: _RowText | None
    labels: tuple[_LabelName, ...] = Field(max_length=MAX_LABELS)

    @property
    def merged(self) -> bool:
        return self.merged_at is not None


class ListPageMark(_Model):
    """What a refresh needs of one full-size page it holds.

    ``etag`` is ``None`` for a page read in smaller pieces, which is asked again in full.
    ``numbers`` says which rows a ``304`` for it reuses, and ``truncated`` whether a bound
    cut something on it, which a ``304`` also keeps.
    """

    etag: Annotated[str, StringConstraints(max_length=300)] | None
    numbers: tuple[PullNumber, ...] = Field(max_length=API_PAGE_SIZE)
    truncated: bool


class PullList(_Model):
    """A prefix of one GitHub listing, as the reader it names saw it.

    ``rows`` holds each pull request once, highest number first, which is GitHub's order
    for ``sort=created&direction=desc``. ``complete`` is false when the last page read had
    a next page, and ``truncated`` true when a bound cut a row's text or an item could not
    be read. ``etags`` has one mark per page held.
    """

    schema_version: int
    source: Url
    list: PullListName
    fetched_at: Timestamp
    reader: Reader
    pages: int = Field(ge=1, le=MAX_LIST_PAGES)
    complete: bool
    truncated: bool
    etags: tuple[ListPageMark, ...] = Field(max_length=MAX_LIST_PAGES)
    rows: tuple[PullListRow, ...] = Field(max_length=MAX_LIST_ROWS)

    @model_validator(mode="after")
    def _is_one_listing(self) -> Self:
        numbers = [row.number for row in self.rows]
        if any(newer <= older for newer, older in pairwise(numbers)):
            raise ValueError("a list's rows are unique and in descending number order")
        if len(self.etags) != self.pages:
            raise ValueError("a list has one mark per page it holds")
        if not {number for mark in self.etags for number in mark.numbers} <= set(numbers):
            raise ValueError("a page's mark names a row the list does not hold")
        return self


@dataclass(frozen=True, slots=True)
class ListedRepository:
    """The repository a list is of: where its files are, and what to ask GitHub for."""

    home: Path
    slug: str
    owner: str
    repo: str

    @property
    def source(self) -> str:
        return f"https://github.com/{self.owner}/{self.repo}"


def serialize_pull_list(listed: PullList) -> bytes:
    """Validate *listed* again and serialize it, refusing one past the read bound."""

    data = PullList.model_validate(listed.model_dump()).model_dump_json().encode("utf-8")
    if len(data) > MAX_PULL_LIST_BYTES:
        raise RecordTooLargeError(
            f"the list of pull requests would be {len(data):,} bytes, more than "
            f"{MAX_PULL_LIST_BYTES:,}"
        )
    return data


def write_pull_list(home: Path, slug: str, listed: PullList) -> None:
    """Publish *listed* atomically under its source. Blocking; run it off the event loop.

    Raises :class:`RecordTooLargeError`, or the home's ``PrivateStorageError`` or an
    ``OSError`` when the cache cannot take it.
    """

    data = serialize_pull_list(listed)
    ensure_private_directory(home, source_pulls_directory(slug))
    write_private_file_atomic(home, source_pull_list(slug, listed.list), data)


def read_pull_list(
    home: Path, slug: str, name: PullListName, *, shared: SharedEntryPolicy = "keep"
) -> PullList | RecordAbsence:
    """The cached list, or why there is none. Blocking and bounded; run it off the loop.

    A list another schema wrote is ``schema_mismatch``. One that is too large, malformed,
    outside the model, or not a private regular file is ``unreadable``; either way the
    next refresh replaces it.
    """

    try:
        data = read_bytes_bounded(
            home, source_pull_list(slug, name), max_bytes=MAX_PULL_LIST_BYTES, shared=shared
        )
    except FileNotFoundError:
        return "not_cached"
    except (RecordError, PrivateStorageError, OSError):
        return "unreadable"
    try:
        payload = json.loads(data)
    except ValueError:
        return "unreadable"
    if not isinstance(payload, dict) or payload.get("schema_version") != PULL_LIST_SCHEMA:
        return "schema_mismatch"
    try:
        listed = PullList.model_validate(payload)
    except ValidationError:
        return "unreadable"
    return listed if listed.list == name else "unreadable"


def write_list_refresh(home: Path, slug: str, name: PullListName, stamp: PullRefreshStamp) -> None:
    """Keep how the list's refresh ended beside it. Blocking; run it off the loop.

    A cache that will not take the stamp is the failure the stamp may be reporting, so
    this process remembers it instead: the route still says why, and the next automatic
    attempt still waits. One server lists one repository, so this holds at most its lists.
    """

    relative = source_pull_list_refresh(slug, name)
    try:
        write_refresh_stamp(home, slug, relative, stamp)
    except (PrivateStorageError, OSError) as exc:
        log.debug("could not keep how the list's refresh ended: %s", exc)
        _UNWRITTEN_STAMPS[str(home / relative)] = stamp
    else:
        _UNWRITTEN_STAMPS.pop(str(home / relative), None)


def read_list_refresh(home: Path, slug: str, name: PullListName) -> PullRefreshStamp | None:
    """How the list's last refresh ended, in any process, or ``None``. Blocking."""

    relative = source_pull_list_refresh(slug, name)
    return _UNWRITTEN_STAMPS.get(str(home / relative)) or read_refresh_stamp(home, relative)


def refresh_is_due(stamp: PullRefreshStamp | None, *, now: datetime) -> bool:
    """Whether an automatic refresh may start: not tried within the window, or before a limit lifts.

    A refresh that succeeded or failed within :data:`FRESHNESS_WINDOW_S` counts the same,
    so a failing ``gh`` is asked once a window rather than on every poll, and after
    ``rate_limited`` no attempt runs before ``reset_at``. A reader's own action, such as
    **Load more** or **Retry**, does not ask this.
    """

    if stamp is None:
        return True
    if stamp.outcome == "rate_limited" and stamp.reset_at and now < parse_stamp(stamp.reset_at):
        return False
    return now - parse_stamp(stamp.at) > timedelta(seconds=FRESHNESS_WINDOW_S)


def can_extend(listed: PullList) -> bool:
    """Whether GitHub has another page and the list may hold it."""

    return not listed.complete and listed.pages < MAX_LIST_PAGES


__all__ = [
    "MAX_LIST_PAGES",
    "MAX_LIST_ROWS",
    "MAX_PULL_LIST_BYTES",
    "MAX_ROW_LABEL_BYTES",
    "MAX_ROW_REF_BYTES",
    "MAX_ROW_TITLE_BYTES",
    "PULL_LIST_SCHEMA",
    "ListPageMark",
    "ListedRepository",
    "PullList",
    "PullListRow",
    "can_extend",
    "parse_stamp",
    "read_list_refresh",
    "read_pull_list",
    "refresh_is_due",
    "serialize_pull_list",
    "utc_now",
    "write_list_refresh",
    "write_pull_list",
]
