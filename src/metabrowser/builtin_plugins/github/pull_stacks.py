"""Optional repository-wide native stack metadata, separate from PR/catalog records.

One bounded snapshot is published after its pages and reader have been checked. GET
only reads this private disposable file; an optional background job owns every process
and provider call. Failure retains the preceding snapshot without touching core data.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from collections import OrderedDict
from functools import partial
from typing import Annotated, Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints, model_validator

from metabrowser.builtin_plugins.github import pull_list
from metabrowser.builtin_plugins.github.checkout import claim_source
from metabrowser.builtin_plugins.github.gh import GhError, GhResponse, gh_api, gh_stack_available
from metabrowser.builtin_plugins.github.gh_lists import (
    PullDataError,
    UnreadableItemError,
    as_dict,
    utc_stamp,
)
from metabrowser.builtin_plugins.github.gh_lists import active_account as active_account
from metabrowser.builtin_plugins.github.pull_list import ETAG_PATTERN, ListedRepository
from metabrowser.builtin_plugins.github.pull_record import (
    PullRefreshStamp,
    Reader,
    Timestamp,
    ensure_pulls_directory,
)
from metabrowser.cache.atomic import RecordError, read_bytes_bounded, read_record
from metabrowser.cache.layout import FutureLayoutFormatError, LayoutError, read_layout
from metabrowser.cache.locks import run_lock_section, source_alias_lock
from metabrowser.cache.paths import MAX_PULL_REQUEST_NUMBER, source_record, source_stacks
from metabrowser.cache.records import REPOSITORY_SOURCE_CONTRACT_ID, RepositorySource
from metabrowser.home import PrivateStorageError, write_private_file_atomic

log = logging.getLogger(__name__)

STACK_FRESHNESS_S: Final = 300.0
STACK_PAGE_SIZE: Final = 100
MAX_STACK_PAGES: Final = 10
MAX_STACK_MEMBERS: Final = 1000
MAX_SNAPSHOT_MEMBERS: Final = 10000
# Public API proof (2026-11-03): seven stacks/71 members took 13,622 response bytes.
# A 1,000-stack/10,000-member fixture normalized to 104,647 cache bytes.
# Member caps also bound the browser index: 1,000 per stack and 10,000 total, preserving whole ordered stacks.
# The optional snapshot stops at 1,000 stacks, 10,000 memberships or 8 MiB;
# it never treats missing membership beyond those bounds as proof of no stack.
MAX_STACK_BYTES: Final = 8 * 1024 * 1024
# Room for the enclosing snapshot, refresh outcome and page metadata within the read cap.
_ENVELOPE_BYTES: Final = 16 * 1024
_MAX_UNWRITTEN: Final = 64

Number = Annotated[int, Field(strict=True, ge=1, le=MAX_PULL_REQUEST_NUMBER)]
Etag = Annotated[str, StringConstraints(pattern=ETAG_PATTERN)]
Revision = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$")]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class NativeStack(_Model):
    """A native stack number and its members in GitHub's bottom-to-top order."""

    number: Number
    base_ref: Annotated[str, StringConstraints(max_length=1024)]
    open: StrictBool
    pulls: tuple[Number, ...] = Field(min_length=1, max_length=MAX_STACK_MEMBERS)
    titles: tuple[
        Annotated[str, StringConstraints(max_length=pull_list.MAX_ROW_TITLE_BYTES)] | None, ...
    ] = Field(max_length=MAX_STACK_MEMBERS)

    @model_validator(mode="after")
    def _distinct_members(self) -> Self:
        if not self.pulls or len(set(self.pulls)) != len(self.pulls):
            raise ValueError("stack members must be nonempty and distinct")
        if len(self.titles) != len(self.pulls):
            raise ValueError("stack titles must follow the member order")
        return self


class StackPage(_Model):
    """A conditional response retains its preceding continuation, even without Link."""

    etag: Etag | None
    has_next: StrictBool
    stacks: tuple[NativeStack, ...] = Field(max_length=STACK_PAGE_SIZE)


class StackSnapshot(_Model):
    source: str
    reader: Reader
    fetched_at: Timestamp
    complete: StrictBool
    pages: tuple[StackPage, ...] = Field(max_length=MAX_STACK_PAGES)

    @model_validator(mode="after")
    def _unique_membership(self) -> Self:
        numbers: set[int] = set()
        membership_count = 0
        for page in self.pages:
            for stack in page.stacks:
                if stack.number in numbers:
                    raise ValueError("ambiguous native stack membership")
                numbers.add(stack.number)
                membership_count += len(stack.pulls)
        if membership_count > MAX_SNAPSHOT_MEMBERS:
            raise ValueError("too many stack memberships")
        if self.complete and (not self.pages or self.pages[-1].has_next):
            raise ValueError("an unfinished page is not a complete snapshot")
        pull_list.parse_stamp(self.fetched_at)
        return self


class StackCache(_Model):
    schema_version: Literal[2] = 2
    source: str
    revision: Revision = Field(default_factory=lambda: uuid.uuid4().hex)
    snapshot: StackSnapshot | None
    last_refresh: PullRefreshStamp

    @model_validator(mode="after")
    def _same_source(self) -> Self:
        if self.snapshot is not None and self.snapshot.source != self.source:
            raise ValueError("a stack snapshot belongs to another source")
        return self


# A refused cache write must still back off in this process. No paths or raw provider
# output are exposed, and only the coordinator's bounded working set is remembered.
_UNWRITTEN: OrderedDict[tuple[str, str], PullRefreshStamp] = OrderedDict()


def _key(repository: ListedRepository) -> tuple[str, str]:
    return str(repository.home), repository.source


def read_stacks(repository: ListedRepository) -> StackCache | None:
    """Read a source-matching snapshot without repairs, directory creation or processes."""
    try:
        data = read_bytes_bounded(
            repository.home,
            source_stacks(repository.slug),
            max_bytes=MAX_STACK_BYTES,
            shared="refuse",
        )
        cache = StackCache.model_validate_json(data)
    except (RecordError, PrivateStorageError, OSError, ValueError):
        return None
    return cache if cache.source == repository.source else None


def last_refresh(repository: ListedRepository, cache: StackCache | None) -> PullRefreshStamp | None:
    durable = cache.last_refresh if cache is not None else None
    transient = _UNWRITTEN.get(_key(repository))
    if transient is not None and (durable is None or transient.at >= durable.at):
        return transient
    return durable


def _remember(repository: ListedRepository, stamp: PullRefreshStamp) -> None:
    key = _key(repository)
    held = _UNWRITTEN.get(key)
    if held is None or not pull_list.rate_limit_holds(held, now=pull_list.utc_now()):
        _UNWRITTEN[key] = stamp
    _UNWRITTEN.move_to_end(key)
    while len(_UNWRITTEN) > _MAX_UNWRITTEN:
        _UNWRITTEN.popitem(last=False)


def remaining_freshness(stamp: PullRefreshStamp | None) -> float:
    if stamp is None:
        return 0.0
    age = (pull_list.utc_now() - pull_list.parse_stamp(stamp.at)).total_seconds()
    return max(0.0, min(STACK_FRESHNESS_S, STACK_FRESHNESS_S - age))


def _rate_hold(repository: ListedRepository) -> PullRefreshStamp | None:
    # The core catalog's provider refusal also applies to optional enrichment. Stack
    # work reads that hold but never writes or clears the catalog's outcome.
    candidates = (
        last_refresh(repository, read_stacks(repository)),
        pull_list.read_list_refresh(repository.home, repository.slug, "all"),
    )
    return next(
        (
            stamp
            for stamp in candidates
            if pull_list.rate_limit_holds(stamp, now=pull_list.utc_now())
        ),
        None,
    )


def refresh_wanted(repository: ListedRepository, *, retry: bool = False) -> bool:
    return _rate_hold(repository) is None and (
        retry or remaining_freshness(last_refresh(repository, read_stacks(repository))) == 0
    )


def _source_matches(repository: ListedRepository) -> None:
    layout = read_layout(repository.home, shared="refuse")
    if layout is None:
        raise ValueError("no cache layout")
    source = read_record(
        repository.home,
        source_record(repository.slug, "source.yml"),
        REPOSITORY_SOURCE_CONTRACT_ID,
        shared="refuse",
    )
    if not isinstance(source, RepositorySource) or source.clone_url != repository.source:
        raise ValueError("source identity changed")


def publish_stacks(
    repository: ListedRepository,
    previous: StackCache | None,
    snapshot: StackSnapshot | None,
    stamp: PullRefreshStamp,
) -> bool:
    """Publish one whole revision under the source lock; reject superseded writers.

    A failure supplies no snapshot and retains the preceding successful data. Async
    callers use run_lock_section so a cancelled lock waiter cannot write later.
    """
    _source_matches(repository)
    with source_alias_lock(repository.home, repository.slug):
        _source_matches(repository)
        current = read_stacks(repository)
        if (current.revision if current else None) != (previous.revision if previous else None):
            return False
        held = last_refresh(repository, current)
        if (
            pull_list.rate_limit_holds(held, now=pull_list.utc_now())
            and stamp.outcome != "rate_limited"
        ):
            return False
        result = StackCache(
            source=repository.source,
            snapshot=snapshot if snapshot is not None else current.snapshot if current else None,
            last_refresh=stamp,
        )
        data = result.model_dump_json().encode()
        if len(data) > MAX_STACK_BYTES:
            raise ValueError("stack snapshot exceeds its cache bound")
        ensure_pulls_directory(repository.home, repository.slug)
        write_private_file_atomic(repository.home, source_stacks(repository.slug), data)
        _UNWRITTEN.pop(_key(repository), None)
        return True


def _page(repository: ListedRepository, response: GhResponse, old: StackPage | None) -> StackPage:
    if response.status == 304:
        if old is None or old.etag is None:
            raise ValueError("unconditional stack response was 304")
        return old.model_copy(update={"etag": response.etag or old.etag})
    payload = response.json()
    if not isinstance(payload, list) or len(payload) > STACK_PAGE_SIZE:
        raise ValueError("unreadable stack page")
    stacks: list[NativeStack] = []
    for raw in payload:
        item = as_dict(raw)
        number = item["number"]
        expected = (
            f"https://api.github.com/repos/{repository.owner}/{repository.repo}/stacks/{number}"
        )
        if not isinstance(item["url"], str) or item["url"].casefold() != expected.casefold():
            raise ValueError("a stack belongs to another repository")
        members = item["pull_requests"]
        if not isinstance(members, list):
            raise ValueError("unreadable stack members")
        stacks.append(
            NativeStack(
                number=number,
                base_ref=as_dict(item["base"])["ref"],
                open=item["open"],
                pulls=tuple(as_dict(member)["number"] for member in members),
                titles=tuple(as_dict(member).get("title") for member in members),
            )
        )
    return StackPage(etag=response.etag, has_next=response.has_next_page, stacks=tuple(stacks))


async def _check_hold(repository: ListedRepository) -> None:
    held = await asyncio.to_thread(_rate_hold, repository)
    if held is not None:
        raise GhError(
            "GitHub's API rate limit is exhausted", state="rate_limited", reset_at=held.reset_at
        )


async def refresh_stacks(
    repository: ListedRepository, *, slot: asyncio.Semaphore | None = None, retry: bool = False
) -> None:
    """Refresh independently, yielding the network slot after each bounded page."""
    if not await asyncio.to_thread(refresh_wanted, repository, retry=retry):
        return
    previous = await asyncio.to_thread(read_stacks, repository)
    reader: str | None = None
    try:
        if not await gh_stack_available():
            raise PullDataError("gh_stack_missing", "Optional GitHub stack tooling is unavailable")
        repository = await claim_source(repository)
        previous = await asyncio.to_thread(read_stacks, repository)
        async with slot if slot is not None else contextlib.nullcontext():
            await _check_hold(repository)
            reader = f"gh:{await active_account()}"
        old = previous.snapshot if previous is not None else None
        if old is not None and old.reader != reader:
            old = None
        pages: list[StackPage] = []
        used = _ENVELOPE_BYTES
        members_used = 0
        complete = False
        for index in range(MAX_STACK_PAGES):
            cached = old.pages[index] if old is not None and index < len(old.pages) else None
            path = f"repos/{repository.owner}/{repository.repo}/stacks?per_page={STACK_PAGE_SIZE}&page={index + 1}"
            async with slot if slot is not None else contextlib.nullcontext():
                await _check_hold(repository)
                response = await gh_api(path, etag=cached.etag if cached else None)
            page = _page(repository, response, cached)
            used += len(page.model_dump_json().encode())
            members_used += sum(len(stack.pulls) for stack in page.stacks)
            if used > MAX_STACK_BYTES or members_used > MAX_SNAPSHOT_MEMBERS:
                break
            pages.append(page)
            if not page.has_next:
                complete = True
                break
            await asyncio.sleep(0)
        async with slot if slot is not None else contextlib.nullcontext():
            await _check_hold(repository)
            if f"gh:{await active_account()}" != reader:
                raise PullDataError(
                    "account_changed", "GitHub account changed while reading stacks"
                )
        now = utc_stamp(pull_list.utc_now())
        snapshot = StackSnapshot(
            source=repository.source,
            reader=reader,
            fetched_at=now,
            complete=complete,
            pages=tuple(pages),
        )
        stamp = PullRefreshStamp(outcome="succeeded", at=now, reader=reader)
        await run_lock_section(partial(publish_stacks, repository, previous, snapshot, stamp))
        return
    except (GhError, PullDataError) as exc:
        stamp = PullRefreshStamp(
            outcome=exc.state,
            message=str(exc),
            reset_at=exc.reset_at,
            at=utc_stamp(pull_list.utc_now()),
            reader=reader,
        )
    except (RecordError, PrivateStorageError, OSError, LayoutError, FutureLayoutFormatError) as exc:
        log.debug("optional stack cache refused a write: %s", exc)
        stamp = PullRefreshStamp(
            outcome="cache_unwritable",
            message="Optional stack metadata could not be cached",
            at=utc_stamp(pull_list.utc_now()),
            reader=reader,
        )
    except (ValueError, KeyError, TypeError, UnreadableItemError) as exc:
        log.debug("optional stack metadata was unreadable: %s", exc)
        stamp = PullRefreshStamp(
            outcome="unreadable",
            message="Optional stack metadata is unavailable",
            at=utc_stamp(pull_list.utc_now()),
            reader=reader,
        )
    try:
        await run_lock_section(partial(publish_stacks, repository, previous, None, stamp))
    except (
        RecordError,
        PrivateStorageError,
        OSError,
        LayoutError,
        FutureLayoutFormatError,
        ValueError,
    ):
        _remember(repository, stamp)


__all__ = [
    "NativeStack",
    "StackPage",
    "StackSnapshot",
    "StackCache",
    "STACK_FRESHNESS_S",
    "read_stacks",
    "last_refresh",
    "remaining_freshness",
    "refresh_wanted",
    "refresh_stacks",
    "publish_stacks",
]
