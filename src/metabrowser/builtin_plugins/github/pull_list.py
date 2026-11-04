"""A repository's lists of pull requests: one validated JSON file per list, and its bounds.

There are three lists, GitHub's three ``state`` values, each in its own file at
``sources/<slug>/pulls/list-<name>.json`` beside the records, written by the home's
private atomic file write and read with a size bound. Each file is a prefix of one GitHub
listing, so ``complete`` has one meaning: GitHub has nothing past the last page read.
Pydantic validates a list on write and parses it on read; one whose ``schema_version`` is
not :data:`PULL_LIST_SCHEMA` is refetched, never migrated.

A pull request's changed files are a list of their own, :class:`PullFileList`, at
``sources/<slug>/pulls/<n>.files.json``, written and bounded as a list of pull requests
is: see the section below.

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
    field_validator,
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
    Sha,
    Timestamp,
    Url,
    ensure_pulls_directory,
    read_refresh_stamp,
    write_refresh_stamp,
)
from metabrowser.cache.atomic import RecordError, read_bytes_bounded
from metabrowser.cache.paths import (
    MAX_PULL_REQUEST_NUMBER,
    PullListName,
    source_pull_files,
    source_pull_files_refresh,
    source_pull_list,
    source_pull_list_refresh,
)
from metabrowser.home import (
    PrivateStorageError,
    SharedEntryPolicy,
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

# What ``gh_api`` will send as ``If-None-Match``, the same as ``gh.py``'s, which this module
# does not load. It raises on anything else, which is no failure a job names, so a file
# holding anything else is refused where it is read.
ETAG_PATTERN: Final = r'^(?:W/)?"[\x21\x23-\x7e]{1,256}"$'

type PullNumber = Annotated[int, Field(ge=1, le=MAX_PULL_REQUEST_NUMBER)]
type _RowText = Annotated[str, StringConstraints(max_length=MAX_ROW_REF_BYTES)]
type _LabelName = Annotated[str, StringConstraints(max_length=MAX_ROW_LABEL_BYTES)]


_UNWRITTEN_STAMPS: dict[str, PullRefreshStamp] = {}
# Three lists and as many file lists as a server's job bound lets fail at once, with room.
_MAX_UNWRITTEN_STAMPS: Final = 64


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

    etag: Annotated[str, StringConstraints(pattern=ETAG_PATTERN)] | None
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

    @field_validator("fetched_at")
    @classmethod
    def _a_real_moment(cls, value: str) -> str:
        # The pattern admits a month 13 or a minute 61, and the route ages a list by this.
        parse_stamp(value)
        return value

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


@dataclass(frozen=True, slots=True)
class LocalComparison:
    """A store that holds both of a record's comparison commits, and those commits.

    ``base`` is the comparison's merge base, so the two name the page's Files changed.
    """

    git_dir: Path
    base: str
    head: str


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
    ensure_pulls_directory(home, slug)
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
        _remember_unwritten(str(home / relative), stamp)
    else:
        _UNWRITTEN_STAMPS.pop(str(home / relative), None)


def read_list_refresh(home: Path, slug: str, name: PullListName) -> PullRefreshStamp | None:
    """How the list's last refresh ended, in any process, or ``None``. Blocking."""

    relative = source_pull_list_refresh(slug, name)
    return _UNWRITTEN_STAMPS.get(str(home / relative)) or read_refresh_stamp(home, relative)


def rate_limit_holds(stamp: PullRefreshStamp | None, *, now: datetime) -> bool:
    """Whether GitHub's reset time still holds, even after a successful local refresh."""

    return stamp is not None and stamp.reset_at is not None and now < parse_stamp(stamp.reset_at)


def refresh_is_due(stamp: PullRefreshStamp | None, *, now: datetime) -> bool:
    """Whether an automatic refresh may start: not tried within the window, or before a limit lifts.

    A refresh that succeeded or failed within :data:`FRESHNESS_WINDOW_S` counts the same,
    so a failing ``gh`` is asked once a window rather than on every poll, and after
    ``rate_limited`` no attempt runs before ``reset_at``.
    """

    if stamp is None:
        return True
    if rate_limit_holds(stamp, now=now):
        return False
    return now - parse_stamp(stamp.at) > timedelta(seconds=FRESHNESS_WINDOW_S)


def can_extend(listed: PullList) -> bool:
    """Whether GitHub has another page and the list may hold it."""

    return not listed.complete and listed.pages < MAX_LIST_PAGES


# ── A pull request's changed files ──────────────────────────────
#
# Two sources list the same comparison. When the store has both of the pull request's
# commits, the local comparison's manifest, which needs no network: ``listed_from`` is
# ``comparison`` and ``head`` the commit it belongs to. Otherwise GitHub's list, one ``gh
# api repos/<owner>/<repo>/pulls/<n>/files`` request per hundred files, read by the account
# ``reader`` names, with one mark per page held. A row keeps the path, the path before a
# rename or copy, the status, and the line counts; GitHub's embedded patch is dropped before
# anything is kept. The path is the row's identity, a rename's new path, since the diff view
# jumps to a file by its path. It is text a pull request's author wrote: it reaches no
# filesystem call and no markup.
#
# Measured 2026-11-03 with gh 2.98.0, at a load average of 4 to 7, first each page by ``gh
# api --include`` and then the whole job, ``refresh_pull_files``, on a source with no store:
#
# - nodejs/node#65161, which GitHub counts 8,161 files: 30 full pages, and page 30 names no
#   next page, so GitHub's limit is where the list ends. A page was 0.86 to 2.01 s and at most
#   985 KB with its patches, of which 15 KB is kept; the job took 27.0 s, each page 0.72 to 1.20
#   s and each account read about 0.5 s. django/django#15387, 2,003 files: 21 pages of at most
#   973 KB, 0.84 to 1.69 s each by hand, and 17.2 s for the job. pallets/click#2800, 4 files: one
#   page, and 1.3 s for the job. A 304 to a conditional page took 0.51 to 0.83 s. So a page is
#   about a second, a long list is published as each arrives, and no page came within a factor
#   of 8 of ``GH_API_MAX_BYTES``.
# - The local manifest of django/django#15387, ``GitDiffSource.manifest`` on a mirror (``git
#   diff --raw`` and ``--numstat``, copies detected, no patch), took 0.26 s, five runs. It is cut
#   at ``MAX_MANIFEST_FILES``, 2,000, and a cut one is not used, since GitHub's lists 3,000.
#
# GitHub lists at most 3,000 files of a pull request; the list holds them all.
MAX_PULL_FILES: Final = 3000
MAX_FILE_PAGES: Final = MAX_PULL_FILES // API_PAGE_SIZE
# A path, in bytes as written, since JSON escaping counts. The longest measured was 105 bytes
# (django/django#15387; 95 on nodejs/node#65161). A longer one is left out, never cut, since a
# cut path names another file, and the list then says it is incomplete.
MAX_FILE_PATH_BYTES: Final = 1024
# The read bound. nodejs/node#65161's 3,000 rows were written at 378 KB. The worst row these
# bounds allow is 2,124 bytes, and ``tests/test_github_pull_files.py`` writes 3,000 of them and
# reads them back: 6.38 MB. So every list written can be read.
MAX_PULL_FILES_BYTES: Final = 8 * 1024 * 1024
PULL_FILES_SCHEMA: Final = 2

type FileStatus = Literal[
    "added", "removed", "modified", "renamed", "copied", "changed", "unchanged"
]
type FileListSource = Literal["github", "comparison"]
type _FilePath = Annotated[str, StringConstraints(min_length=1, max_length=MAX_FILE_PATH_BYTES)]
type _LineCount = Annotated[int, Field(ge=0)]


class PullFileRow(_Model):
    """One changed file, in GitHub's words: ``status`` is one of GitHub's statuses.

    ``previous_path`` is the path before a rename or a copy. A count is ``None`` where the
    local comparison has none, for a binary file.
    """

    path: _FilePath
    previous_path: _FilePath | None
    status: FileStatus
    additions: _LineCount | None
    deletions: _LineCount | None


class FilePageMark(_Model):
    """What a refresh needs of one page of GitHub's list it holds.

    ``etag`` is ``None`` for a page read in smaller pieces, which is asked again in full;
    ``rows`` is how many of the list's rows came from it, in order, which a ``304`` reuses.
    ``places`` is how many items GitHub listed on it, read or not, so a full page is told
    from a short one, and ``truncated`` whether an item on it could not be read.
    """

    etag: Annotated[str, StringConstraints(pattern=ETAG_PATTERN)] | None
    rows: int = Field(ge=0, le=API_PAGE_SIZE)
    places: int = Field(ge=0, le=API_PAGE_SIZE)
    truncated: bool


class PullFileList(_Model):
    """The changed files of one pull request, from one of two sources.

    ``generation`` identifies one refresh, shared by all its progressive publications.
    It is persisted, never inferred from timestamps or minted on read.
    ``complete`` is false while GitHub has pages not yet read, which is the state a list is
    published in while it fills. ``last_page`` is the page count the first page's ``Link``
    header gave, which counts pages and not files. ``capped`` says GitHub stopped at the
    most files it lists, :data:`MAX_PULL_FILES`, so the pull request may have more.
    ``truncated`` says an item could not be read or had a path past
    :data:`MAX_FILE_PATH_BYTES`, and was left out.
    """

    schema_version: int
    source: Url
    number: PullNumber
    listed_from: FileListSource
    generation: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$", max_length=32)]
    fetched_at: Timestamp
    reader: Reader | None
    head: Sha | None
    # A comparison without a base cannot prove freshness; the route calls it stale.
    base: Sha | None = None
    pages: int = Field(ge=0, le=MAX_FILE_PAGES)
    last_page: Annotated[int, Field(ge=1)] | None
    complete: bool
    capped: bool
    truncated: bool
    marks: tuple[FilePageMark, ...] = Field(max_length=MAX_FILE_PAGES)
    rows: tuple[PullFileRow, ...] = Field(max_length=MAX_PULL_FILES)

    @field_validator("fetched_at")
    @classmethod
    def _a_real_moment(cls, value: str) -> str:
        parse_stamp(value)
        return value

    @model_validator(mode="after")
    def _is_one_list(self) -> Self:
        if len({row.path for row in self.rows}) != len(self.rows):
            raise ValueError("a file list names each path once")
        if self.listed_from == "comparison":
            if self.reader is not None or self.head is None or self.marks or self.pages:
                raise ValueError("a comparison's list names its head, and no reader or pages")
            if not self.complete or self.capped:
                raise ValueError("a comparison's list is whole")
            return self
        if self.reader is None or self.head is not None or self.base is not None or self.pages < 1:
            raise ValueError("GitHub's list names its reader and pages, not local endpoints")
        if len(self.marks) != self.pages:
            raise ValueError("GitHub's list has one mark per page it holds")
        if sum(mark.rows for mark in self.marks) != len(self.rows):
            raise ValueError("GitHub's list holds exactly the rows its marks count")
        return self

    def page_rows(self, number: int) -> tuple[PullFileRow, ...]:
        """The rows page *number* of GitHub's list gave, in order."""

        start = sum(mark.rows for mark in self.marks[: number - 1])
        return self.rows[start : start + self.marks[number - 1].rows]


def serialize_pull_files(listed: PullFileList) -> bytes:
    """Validate *listed* again and serialize it, refusing one past the read bound."""

    data = PullFileList.model_validate(listed.model_dump()).model_dump_json().encode("utf-8")
    if len(data) > MAX_PULL_FILES_BYTES:
        raise RecordTooLargeError(
            f"the list of changed files would be {len(data):,} bytes, more than "
            f"{MAX_PULL_FILES_BYTES:,}"
        )
    return data


def write_pull_files(home: Path, slug: str, listed: PullFileList) -> None:
    """Publish *listed* atomically under its source. Blocking; run it off the event loop.

    Raises :class:`RecordTooLargeError`, or the home's ``PrivateStorageError`` or an
    ``OSError`` when the cache cannot take it.
    """

    data = serialize_pull_files(listed)
    ensure_pulls_directory(home, slug)
    write_private_file_atomic(home, source_pull_files(slug, listed.number), data)


def read_pull_files(
    home: Path, slug: str, number: int, *, shared: SharedEntryPolicy = "keep"
) -> PullFileList | RecordAbsence:
    """The cached list of changed files, or why there is none. Blocking and bounded.

    The absences are a list of pull requests': ``schema_mismatch`` for another schema's, and
    ``unreadable`` for one too large, malformed, outside the model, or another pull
    request's; the next refresh replaces it either way.
    """

    try:
        data = read_bytes_bounded(
            home, source_pull_files(slug, number), max_bytes=MAX_PULL_FILES_BYTES, shared=shared
        )
    except FileNotFoundError:
        return "not_cached"
    except (RecordError, PrivateStorageError, OSError):
        return "unreadable"
    try:
        payload = json.loads(data)
    except ValueError:
        return "unreadable"
    if not isinstance(payload, dict) or payload.get("schema_version") != PULL_FILES_SCHEMA:
        return "schema_mismatch"
    try:
        listed = PullFileList.model_validate(payload)
    except ValidationError:
        return "unreadable"
    return listed if listed.number == number else "unreadable"


def write_files_refresh(
    home: Path, slug: str, number: int, stamp: PullRefreshStamp, *, persist: bool = True
) -> None:
    """Keep the outcome beside the file list, or only in memory before cache admission.

    ``persist=False`` attempts no lock, directory creation, or file write. The bounded
    fallback still reports the refusal and holds automatic retries; it cannot shorten
    an existing network rate-limit deadline.
    """

    relative = source_pull_files_refresh(slug, number)
    if not persist:
        held = read_files_refresh(home, slug, number)
        if held is not None and rate_limit_holds(held, now=utc_now()):
            stamp = stamp.model_copy(
                update={"reset_at": max(held.reset_at or "", stamp.reset_at or "")}
            )
        _remember_unwritten(str(home / relative), stamp)
        return
    try:
        write_refresh_stamp(home, slug, relative, stamp)
    except (PrivateStorageError, OSError) as exc:
        log.debug("could not keep how the file list's refresh ended: %s", exc)
        _remember_unwritten(str(home / relative), stamp)
    else:
        _UNWRITTEN_STAMPS.pop(str(home / relative), None)


def read_files_refresh(home: Path, slug: str, number: int) -> PullRefreshStamp | None:
    """How the file list's last refresh ended, in any process, or ``None``. Blocking."""

    relative = source_pull_files_refresh(slug, number)
    candidates = [
        stamp
        for stamp in (
            _UNWRITTEN_STAMPS.get(str(home / relative)),
            read_refresh_stamp(home, relative),
        )
        if stamp is not None
    ]
    holds = [stamp for stamp in candidates if rate_limit_holds(stamp, now=utc_now())]
    return (
        max(holds, key=lambda stamp: (stamp.reset_at or "", stamp.at))
        if holds
        else max(candidates, key=lambda stamp: stamp.at, default=None)
    )


def _remember_unwritten(key: str, stamp: PullRefreshStamp) -> None:
    # File lists are per pull request, and numbers are request text, so this is bounded:
    # the oldest is forgotten first, and its list's next automatic attempt is not held.
    if key not in _UNWRITTEN_STAMPS and len(_UNWRITTEN_STAMPS) >= _MAX_UNWRITTEN_STAMPS:
        _UNWRITTEN_STAMPS.pop(next(iter(_UNWRITTEN_STAMPS)))
    _UNWRITTEN_STAMPS[key] = stamp


__all__ = [
    "ETAG_PATTERN",
    "MAX_FILE_PAGES",
    "MAX_FILE_PATH_BYTES",
    "MAX_LIST_PAGES",
    "MAX_LIST_ROWS",
    "MAX_PULL_FILES",
    "MAX_PULL_FILES_BYTES",
    "MAX_PULL_LIST_BYTES",
    "MAX_ROW_LABEL_BYTES",
    "MAX_ROW_REF_BYTES",
    "MAX_ROW_TITLE_BYTES",
    "PULL_FILES_SCHEMA",
    "PULL_LIST_SCHEMA",
    "FilePageMark",
    "FileListSource",
    "FileStatus",
    "ListPageMark",
    "ListedRepository",
    "LocalComparison",
    "PullFileList",
    "PullFileRow",
    "PullList",
    "PullListRow",
    "can_extend",
    "parse_stamp",
    "rate_limit_holds",
    "read_files_refresh",
    "read_list_refresh",
    "read_pull_files",
    "read_pull_list",
    "refresh_is_due",
    "serialize_pull_files",
    "serialize_pull_list",
    "utc_now",
    "write_files_refresh",
    "write_list_refresh",
    "write_pull_files",
    "write_pull_list",
]
