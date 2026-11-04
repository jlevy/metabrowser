"""List one pull request's changed files, and keep the list.

:func:`refresh_pull_files` is the whole job. It has two sources for one list:

- **The local comparison**, when the caller names one: the store holds both of the record's
  comparison commits, so the list is the comparison's manifest, ``git diff --raw`` and
  ``--numstat`` through :class:`GitDiffSource`, with no patch and no network. A manifest
  cut at ``MAX_MANIFEST_FILES``, or one Git cannot list, falls through to GitHub's.
- **GitHub's list**, which runs no Git: the active account, then one ``gh api
  repos/<owner>/<repo>/pulls/<n>/files`` request per hundred files, then the account again.
  Each request takes one of the coordinator's network slots for itself alone, through
  *slot*, so a long list never holds a slot between pages and a fetch the page of code waits
  on gets the next one.

GitHub's list is read progressively. After every page but the last, what has been read is
published as ``complete: false`` whenever it holds more rows than the file does, so a
reader of ``GET pull-files`` sees a first list arrive page by page, and a list the file
already holds, whole or stopped part-way, is not replaced by fewer rows while it is read
again, each page with its ``If-None-Match``; the whole list is published at the end. A page
that fails fails the job, and the file stays as last published.

The list is assembled over the job's duration. A push between two page reads can show a file
twice, which the path dedupes, or miss one until the next refresh. A list read while the
active account changed is reported ``account_changed``; the pages it published name the
account that read them, and the route then calls the list stale.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Final
from uuid import uuid4

from pydantic import ValidationError

from metabrowser.builtin_plugins.github import pull_list
from metabrowser.builtin_plugins.github.gh_lists import (
    PullDataError,
    UnreadableItemError,
    active_account,
    as_dict,
    read_list,
    readable_items,
    utc_stamp,
)
from metabrowser.builtin_plugins.github.pull_list import (
    MAX_FILE_PAGES,
    MAX_FILE_PATH_BYTES,
    MAX_PULL_FILES,
    PULL_FILES_SCHEMA,
    FilePageMark,
    FileStatus,
    ListedRepository,
    LocalComparison,
    PullFileList,
    PullFileRow,
    rate_limit_holds,
    read_files_refresh,
    read_pull_files,
    write_files_refresh,
    write_pull_files,
)
from metabrowser.builtin_plugins.github.pull_record import (
    API_PAGE_SIZE,
    PullRefreshStamp,
    RecordTooLargeError,
    escaped_size,
)
from metabrowser.home import PrivateStorageError

log = logging.getLogger(__name__)

_MESSAGE_CHARS: Final = 1000
_NO_PULL_REQUEST: Final = (
    "GitHub has no such pull request, or the repository is private and the gh account "
    "cannot read it"
)
_STATUSES: Final[frozenset[str]] = frozenset(
    {"added", "removed", "modified", "renamed", "copied", "changed", "unchanged"}
)
# The comparison's change kinds in GitHub's words. Git's ``unmerged`` cannot arise between two
# commits, and a type change is what GitHub calls ``changed``.
_KIND_STATUS: Final[dict[str, FileStatus]] = {
    "added": "added",
    "deleted": "removed",
    "modified": "modified",
    "renamed": "renamed",
    "copied": "copied",
    "type_changed": "changed",
    "unmerged": "changed",
}

type Slot = Callable[[], AbstractAsyncContextManager[object]]


def _path(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise UnreadableItemError
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise UnreadableItemError from exc
    if escaped_size(value) > MAX_FILE_PATH_BYTES:
        raise UnreadableItemError
    return value


def _count(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise UnreadableItemError
    return value


def _github_row(value: object) -> PullFileRow:
    """A row from one of GitHub's items. Everything else in it, the patch first, is dropped."""

    item = as_dict(value)
    status = item.get("status")
    if status not in _STATUSES:
        raise UnreadableItemError
    previous = item.get("previous_filename")
    return PullFileRow(
        path=_path(item.get("filename")),
        previous_path=_path(previous) if previous is not None else None,
        status=status,  # pyright: ignore[reportArgumentType]
        additions=_count(item.get("additions")),
        deletions=_count(item.get("deletions")),
    )


@dataclass(frozen=True, slots=True)
class _Page:
    mark: FilePageMark
    rows: tuple[PullFileRow, ...]
    has_next: bool


def _reused_page(previous: PullFileList, number: int) -> _Page:
    """Page *number* as *previous* holds it, after GitHub said it is unchanged."""

    # A 304 carries no Link, so this is what the file knew: :func:`_page_etag` asks whole a
    # last page that could have gained a next one with its body unchanged.
    has_next = number < previous.pages or not previous.complete
    return _Page(previous.marks[number - 1], previous.page_rows(number), has_next)


def _page_etag(previous: PullFileList | None, number: int) -> str | None:
    """The ETag to ask page *number* with, or ``None`` to read it whole.

    A push that adds files past a full last page starts a new page and leaves that page's
    body as it was, so GitHub answers ``304``, with no ``Link``, and the list would go on
    saying ``complete``. So a complete list's last page is read whole when it is full, as
    the list of pull requests does: one counted request a refresh, for a list whose files
    are a multiple of a hundred, and at GitHub's limit.
    """

    if previous is None or number > previous.pages:
        return None
    mark = previous.marks[number - 1]
    full = mark.places == API_PAGE_SIZE or mark.truncated
    return None if previous.complete and number == previous.pages and full else mark.etag


async def _read_page(
    repository: ListedRepository, number: int, page: int, previous: PullFileList | None
) -> tuple[_Page, int | None]:
    """Full-size page *page* of the list, and the page count its ``Link`` gave, if any."""

    try:
        read = await read_list(
            f"repos/{repository.owner}/{repository.repo}/pulls/{number}/files",
            key=None,
            cap=API_PAGE_SIZE,
            etag=_page_etag(previous, page),
            now=pull_list.utc_now,
            first_page=page,
        )
    except PullDataError as exc:
        if exc.state == "not_found_or_private":
            raise PullDataError(exc.state, _NO_PULL_REQUEST) from exc
        raise
    if read.items is None:
        # Only a conditional request, which needs a previous list, is answered 304.
        assert previous is not None
        return _reused_page(previous, page), previous.last_page if page == 1 else None
    rows, dropped = readable_items(read.items, _github_row)
    mark = FilePageMark(
        etag=read.etag,
        rows=len(rows),
        places=min(len(read.items) + (1 if read.left_out else 0), API_PAGE_SIZE),
        truncated=read.left_out or dropped,
    )
    return _Page(mark, rows, read.more), read.last_page


def _assembled(
    repository: ListedRepository,
    number: int,
    reader: str,
    pages: Sequence[_Page],
    *,
    last_page: int | None,
    fetched_at: str,
    generation: str,
    final: bool,
) -> PullFileList:
    """Pages joined into one list: each path once, where it first appeared."""

    seen: set[str] = set()
    marks: list[FilePageMark] = []
    rows: list[PullFileRow] = []
    for page in pages:
        kept = [row for row in page.rows if row.path not in seen]
        seen.update(row.path for row in kept)
        rows.extend(kept)
        marks.append(page.mark.model_copy(update={"rows": len(kept)}))
    has_next = pages[-1].has_next
    full_at_limit = len(pages) == MAX_FILE_PAGES and pages[-1].mark.places == API_PAGE_SIZE
    try:
        return PullFileList(
            schema_version=PULL_FILES_SCHEMA,
            generation=generation,
            source=repository.source,
            number=number,
            listed_from="github",
            fetched_at=fetched_at,
            reader=reader,
            head=None,
            pages=len(pages),
            last_page=last_page,
            complete=final and not has_next,
            capped=final and full_at_limit,
            truncated=any(page.mark.truncated for page in pages),
            marks=tuple(marks),
            rows=tuple(rows),
        )
    except ValidationError as exc:
        raise PullDataError(
            "gh_failed", "GitHub answered with a list of files Metabrowser cannot read"
        ) from exc


async def _write(repository: ListedRepository, listed: PullFileList) -> None:
    try:
        await asyncio.to_thread(write_pull_files, repository.home, repository.slug, listed)
    except (RecordTooLargeError, PrivateStorageError, OSError) as exc:
        log.debug("could not write the list of changed files: %s", exc)
        raise PullDataError(
            "cache_unwritable", "the list of changed files could not be written to the cache"
        ) from exc


async def _from_github(
    repository: ListedRepository, number: int, login: str, slot: Slot, generation: str
) -> PullFileList:
    reader = f"gh:{login}"
    cached = await asyncio.to_thread(read_pull_files, repository.home, repository.slug, number)
    previous = (
        cached
        if isinstance(cached, PullFileList)
        and cached.listed_from == "github"
        and cached.reader == reader
        else None
    )
    held = len(cached.rows) if isinstance(cached, PullFileList) else 0
    fetched_at = utc_stamp(pull_list.utc_now())
    pages: list[_Page] = []
    last_page: int | None = None
    for page_number in range(1, MAX_FILE_PAGES + 1):
        async with slot():
            page, named_last = await _read_page(repository, number, page_number, previous)
        if page_number == 1:
            last_page = named_last
        pages.append(page)
        if not page.has_next:
            break
        partial = _assembled(
            repository,
            number,
            reader,
            pages,
            last_page=last_page,
            fetched_at=fetched_at,
            generation=generation,
            final=False,
        )
        # Never fewer rows than the file holds, so a reread does not shrink what a reader has.
        if len(partial.rows) > held:
            await _write(repository, partial)
    listed = _assembled(
        repository,
        number,
        reader,
        pages,
        last_page=last_page,
        fetched_at=fetched_at,
        generation=generation,
        final=True,
    )
    async with slot():
        if await active_account() != login:
            raise PullDataError(
                "account_changed",
                "the active gh account changed during the read, so it is not taken as "
                "complete; open the files again",
            )
    await _write(repository, listed)
    return listed


async def _from_comparison(
    repository: ListedRepository, number: int, local: LocalComparison, generation: str
) -> PullFileList | None:
    """The local comparison's list, or ``None`` when GitHub's is to be read instead."""

    # Here, not at the top: GitHub's list needs none of Git.
    from metabrowser.diff.adapters.base import DiffSourceError
    from metabrowser.diff.adapters.git import GitDiffSource
    from metabrowser.git.process import GitError, GitLocation, repository_store_target

    try:
        location = GitLocation.revision(repository_store_target(git_dir=local.git_dir), local.head)
        source = GitDiffSource(location)
        # The base is already the merge base, so a direct comparison is the page's own.
        resolved = await source.resolve(
            {"left": local.base, "right": local.head, "base_policy": "direct"}
        )
        manifest = await source.manifest(resolved)
    except (DiffSourceError, GitError) as exc:
        log.debug("pull request %s's comparison could not be listed: %s", number, exc)
        return None
    if manifest.truncated:
        return None
    rows: list[PullFileRow] = []
    left_out = False
    for change in manifest.files:
        side = change.new if change.new is not None else change.old
        moved = change.kind.value in {"renamed", "copied"} and change.old is not None
        try:
            if side is None:
                raise UnreadableItemError
            rows.append(
                PullFileRow(
                    path=_path(side.path),
                    previous_path=_path(change.old.path) if moved and change.old else None,
                    status=_KIND_STATUS[change.kind.value],
                    additions=change.additions,
                    deletions=change.deletions,
                )
            )
        except (UnreadableItemError, ValidationError):
            left_out = True
    unique = {row.path: row for row in reversed(rows)}
    kept = [row for row in rows if unique.get(row.path) is row]
    try:
        return PullFileList(
            schema_version=PULL_FILES_SCHEMA,
            generation=generation,
            source=repository.source,
            number=number,
            listed_from="comparison",
            fetched_at=utc_stamp(pull_list.utc_now()),
            reader=None,
            head=local.head,
            base=local.base,
            pages=0,
            last_page=None,
            complete=True,
            capped=False,
            truncated=left_out or len(kept) < len(rows) or len(kept) > MAX_PULL_FILES,
            marks=(),
            rows=tuple(kept[:MAX_PULL_FILES]),
        )
    except ValidationError:
        return None


async def refresh_pull_files(
    repository: ListedRepository, number: int, *, local: LocalComparison | None, slot: Slot
) -> PullFileList:
    """List pull request *number*'s changed files and cache them; see the module.

    *local* names the store and commits of the record's comparison, when the store holds
    both. *slot* is one of the coordinator's network slots, held for one ``gh`` request at a
    time. Raises only :class:`PullDataError`; how it ended is kept beside the list either way.
    """

    # One identity for the whole refresh, including every progressive page or fallback.
    generation = uuid4().hex
    listed = await _from_comparison(repository, number, local, generation) if local else None
    stamp = await asyncio.to_thread(read_files_refresh, repository.home, repository.slug, number)
    held = stamp if rate_limit_holds(stamp, now=pull_list.utc_now()) else None
    # A named comparison can still fail or be truncated. Check at the network
    # boundary, after trying it, and retain the original hold unchanged.
    if listed is None and held is not None:
        raise PullDataError(
            "rate_limited",
            held.message or "GitHub's rate limit holds; retry after the reset time",
            reset_at=held.reset_at,
        )
    reader: str | None = None
    try:
        if listed is not None:
            await _write(repository, listed)
        else:
            async with slot():
                login = await active_account()
            reader = f"gh:{login}"
            listed = await _from_github(repository, number, login, slot, generation)
    except PullDataError as exc:
        stamp = PullRefreshStamp(
            outcome=exc.state,
            message=str(exc)[:_MESSAGE_CHARS],
            reset_at=exc.reset_at or (held.reset_at if held is not None else None),
            at=utc_stamp(pull_list.utc_now()),
            reader=reader,
        )
        await asyncio.to_thread(
            write_files_refresh, repository.home, repository.slug, number, stamp
        )
        raise
    # Local success changes the latest outcome, but says nothing about when GitHub
    # will answer a later fallback. Keep that independent network deadline.
    succeeded = PullRefreshStamp(
        outcome="succeeded",
        at=listed.fetched_at,
        reader=listed.reader,
        reset_at=held.reset_at if held is not None else None,
    )
    await asyncio.to_thread(
        write_files_refresh, repository.home, repository.slug, number, succeeded
    )
    return listed


__all__ = ["Slot", "refresh_pull_files"]
