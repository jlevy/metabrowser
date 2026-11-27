"""Optional repository-wide native stack metadata, separate from PR/catalog records.

One bounded snapshot is published after its pages and reader have been checked. GET
only reads this private disposable file; an optional background job owns every process
and provider call. Failure retains the preceding snapshot without touching core data.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from functools import partial
from typing import Annotated, Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints, model_validator

from metabrowser.builtin_plugins.github import gh_budget, pull_list
from metabrowser.builtin_plugins.github.checkout import claim_source
from metabrowser.builtin_plugins.github.gh import GhResponse, gh_api, gh_stack_available
from metabrowser.builtin_plugins.github.gh_lists import (
    PullDataError,
    as_dict,
    utc_stamp,
)
from metabrowser.builtin_plugins.github.gh_lists import active_account as active_account
from metabrowser.builtin_plugins.github.pull_list import ETAG_PATTERN, ListedRepository
from metabrowser.builtin_plugins.github.pull_record import (
    PullRefreshStamp,
    Reader,
    Timestamp,
)
from metabrowser.builtin_plugins.github.repository_snapshot import (
    FAILURES,
    Unwritten,
    check_hold,
    failure_stamp,
    publish_revision,
    rate_hold,
    record_failure,
)
from metabrowser.builtin_plugins.github.repository_snapshot import (
    remaining_freshness as snapshot_freshness,
)
from metabrowser.builtin_plugins.github.served_pull import FULL_REFRESH_S
from metabrowser.cache.atomic import RecordError, read_bytes_bounded
from metabrowser.cache.locks import run_lock_section
from metabrowser.cache.paths import MAX_PULL_REQUEST_NUMBER, source_stacks
from metabrowser.home import PrivateStorageError

# How long a failed attempt holds off the next automatic refresh; an explicit retry still
# waits for a known rate-limit reset. A snapshot that was read holds it off for
# ``FULL_REFRESH_S`` (:func:`remaining_freshness`): nothing reports a stack's change, so
# while a view shows stacks they are read in full that often. An unchanged read is one
# conditional page, answered ``304`` in 0.88 to 1.02 s for jlevy/metabrowser (50 KB of
# stacks) and cli/cli with gh 2.98.0 (six reads, 2026-11-22, load average near 200), and
# its two account checks.
STACK_FRESHNESS_S: Final = 300.0
# Stacks per REST page, and pages per refresh: at most 1,000 stacks.
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

    @model_validator(mode="after")
    def _distinct_members(self) -> Self:
        if not self.pulls or len(set(self.pulls)) != len(self.pulls):
            raise ValueError("stack members must be nonempty and distinct")
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
    schema_version: Literal[1] = 1
    source: str
    revision: Revision = Field(default_factory=lambda: uuid.uuid4().hex)
    snapshot: StackSnapshot | None
    last_refresh: PullRefreshStamp

    @model_validator(mode="after")
    def _same_source(self) -> Self:
        if self.snapshot is not None and self.snapshot.source != self.source:
            raise ValueError("a stack snapshot belongs to another source")
        return self


# A refused cache write must still back off in this process (:class:`.Unwritten`).
_UNWRITTEN: Final = Unwritten()


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
    return _UNWRITTEN.last_refresh(repository.home, repository.source, durable)


def remaining_freshness(stamp: PullRefreshStamp | None) -> float:
    """How long the last refresh still holds off the next automatic one, in seconds."""

    read = stamp is not None and stamp.outcome == "succeeded"
    # Over the process's own ceiling a full read waits five minutes, as a failure does.
    usual = gh_budget.full_read_interval(FULL_REFRESH_S, now=pull_list.utc_now())
    return snapshot_freshness(stamp, usual if read else STACK_FRESHNESS_S)


def _rate_hold(repository: ListedRepository) -> PullRefreshStamp | None:
    return rate_hold(repository, last_refresh(repository, read_stacks(repository)))


def refresh_wanted(repository: ListedRepository, *, retry: bool = False) -> bool:
    """Whether an ask reads the stacks now. Blocking and bounded; never contacts GitHub.

    A reader's *retry* does unless GitHub's limit holds. An automatic ask does once the
    last refresh has aged out (:func:`remaining_freshness`), and only while the budget
    admits it (:func:`.gh_budget.admission`), as other automatic work is admitted; the
    process's own ceiling slows it rather than stopping it.
    """

    if _rate_hold(repository) is not None:
        return False
    if retry:
        return True
    return (
        remaining_freshness(last_refresh(repository, read_stacks(repository))) == 0
        and gh_budget.admission(("core",), now=pull_list.utc_now(), ceiling=False).admitted
    )


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

    def compose(current: StackCache | None) -> StackCache:
        kept = snapshot if snapshot is not None else current.snapshot if current else None
        return StackCache(source=repository.source, snapshot=kept, last_refresh=stamp)

    return publish_revision(
        repository,
        previous,
        stamp,
        read=partial(read_stacks, repository),
        compose=compose,
        relative=source_stacks(repository.slug),
        max_bytes=MAX_STACK_BYTES,
        unwritten=_UNWRITTEN,
        too_large="stack snapshot exceeds its cache bound",
    )


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
            )
        )
    return StackPage(etag=response.etag, has_next=response.has_next_page, stacks=tuple(stacks))


async def _check_hold(repository: ListedRepository) -> None:
    await check_hold(partial(_rate_hold, repository))


async def refresh_stacks(
    repository: ListedRepository,
    *,
    slot: contextlib.AbstractAsyncContextManager[None] | None = None,
    retry: bool = False,
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
    except FAILURES as exc:
        stamp = failure_stamp(
            exc,
            repository,
            reader=reader,
            subject="optional stack metadata",
            unavailable="Optional stack metadata is unavailable",
        )
    await record_failure(
        partial(publish_stacks, repository, previous, None, stamp), repository, stamp, _UNWRITTEN
    )


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
