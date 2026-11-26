"""The repository's whole label set, cached once, so a label named alone has its color.

A pull request's record carries each label's color, but a record or a core cached before
label colors names its labels alone. Such a record is fetched again once, after its page
has painted it, and a core in that shape is drawn until its record arrives. This set
colors those chips by name from first paint (``mb-varu``): one bounded snapshot of
``repos/<owner>/<repo>/labels``, every page with its ETag, at
``sources/<slug>/pulls/labels.json``, published under the source-alias lock and read
lock-free with a size bound. It persists across restarts and is cleared with the rest of
the plugin's cache.

Reads never contact GitHub. The set is read on demand, by a job of its own under
:func:`labels_job_key`, which ``POST github/labels-refresh`` starts or joins. A pull
request's page sends it when it shows a label named alone that its envelope has no entry
for, and the job asks GitHub only when the set is absent, :data:`LABEL_FRESHNESS_S` old,
or a reader's own retry asks (:func:`refresh_wanted`). Nothing in the catalog's refresh
waits on it, and no failure of it reaches the catalog. GitHub's rate limit holds it as it
holds the catalog, and a failure keeps the preceding snapshot.

It shares its stamps, its hold, and its publish step with :mod:`.pull_stacks`, the other
optional repository-wide snapshot (:mod:`.repository_snapshot`).
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import stat
import threading
import uuid
from collections import OrderedDict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Annotated, Final, Literal, Self, TypedDict

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints, model_validator

from metabrowser.builtin_plugins.github import gh_budget, pull_list
from metabrowser.builtin_plugins.github.checkout import claim_source
from metabrowser.builtin_plugins.github.gh import GhResponse, gh_api
from metabrowser.builtin_plugins.github.gh_lists import PullDataError, as_dict, utc_stamp
from metabrowser.builtin_plugins.github.gh_lists import active_account as active_account
from metabrowser.builtin_plugins.github.pull_list import ETAG_PATTERN, ListedRepository
from metabrowser.builtin_plugins.github.pull_record import (
    LabelColor,
    PullRefreshStamp,
    Reader,
    Timestamp,
    cut_escaped,
    label_color,
    label_description,
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
from metabrowser.cache.atomic import RecordError, read_bytes_bounded
from metabrowser.cache.locks import run_lock_section
from metabrowser.cache.paths import source_labels
from metabrowser.home import PrivateStorageError

# A label set changes rarely, and only a page showing a label named alone asks for it, so
# a set is read again at most once in this age, as the native stack snapshot is
# (pull_stacks.STACK_FRESHNESS_S). Each page is asked for with its ETag, and an unchanged
# page answers 304, but a 304 costs a gh process and a round trip as a 200 does. Measured
# 2026-11-15 with real gh 2.98.0 against home-assistant/core (2,895 labels, 29 pages), one
# page after another as the job reads them, three runs at a load average of 11 to 12: a
# first read took 15.5 to 15.9 s, and a read again, all 29 pages answering 304, 14.0 to
# 15.8 s. So the job runs beside the catalog's, never inside it, and only on demand.
LABEL_FRESHNESS_S: Final = 300.0
LABEL_PAGE_SIZE: Final = 100
# Measured 2026-11-15 (``gh api repos/<r>/labels``): home-assistant/core has 2,894 labels,
# elastic/kibana 1,732, and rust-lang/rust 999, the most of eleven large repositories.
# Fifty pages hold 5,000.
MAX_LABEL_PAGES: Final = 50
# A GitHub label's name is at most 50 characters and its description 100, and each is cut
# at what that many characters of any script take escaped, 4 bytes each: a record names a
# label by its whole name, so a name cut shorter would never match it.
MAX_LABEL_NAME_BYTES: Final = 200
MAX_LABEL_DESCRIPTION_BYTES: Final = 400
# home-assistant/core's 2,894 labels are 208,661 bytes cached (29 pages, each with its
# ETag). A set of 5,000 labels at every bound, each name and description of 4-byte
# characters and each page's ETag of 256, is 3,246,738 bytes
# (tests/test_github_pull_labels.py); 4 MiB is the read bound and the write bound.
MAX_LABELS_BYTES: Final = 4 * 1024 * 1024
# Memory for a server's few repositories, and a test's many homes.
_MAX_INDEXES: Final = 16
# Room for the enclosing cache and its refresh outcome within the bound.
_ENVELOPE_BYTES: Final = 16 * 1024

Etag = Annotated[str, StringConstraints(pattern=ETAG_PATTERN)]
Revision = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$")]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RepositoryLabel(_Model):
    """One label of the repository: its name, GitHub's color, and its description."""

    name: Annotated[str, StringConstraints(max_length=MAX_LABEL_NAME_BYTES)]
    color: LabelColor | None
    description: Annotated[str, StringConstraints(max_length=MAX_LABEL_DESCRIPTION_BYTES)] | None


class LabelPage(_Model):
    """One page of the set, with the ETag that asks for it again conditionally."""

    etag: Etag | None
    has_next: StrictBool
    labels: tuple[RepositoryLabel, ...] = Field(max_length=LABEL_PAGE_SIZE)


class LabelSnapshot(_Model):
    """The pages one reader read, in GitHub's order; ``complete`` when the last named no next."""

    source: str
    reader: Reader
    fetched_at: Timestamp
    complete: StrictBool
    pages: tuple[LabelPage, ...] = Field(max_length=MAX_LABEL_PAGES)

    @model_validator(mode="after")
    def _complete_ends_its_pages(self) -> Self:
        if self.complete and (not self.pages or self.pages[-1].has_next):
            raise ValueError("an unfinished page is not a complete label set")
        pull_list.parse_stamp(self.fetched_at)
        return self

    def labels(self) -> Iterable[RepositoryLabel]:
        return (label for page in self.pages for label in page.labels)


class LabelCache(_Model):
    schema_version: Literal[1] = 1
    source: str
    revision: Revision = Field(default_factory=lambda: uuid.uuid4().hex)
    snapshot: LabelSnapshot | None
    last_refresh: PullRefreshStamp

    @model_validator(mode="after")
    def _same_source(self) -> Self:
        if self.snapshot is not None and self.snapshot.source != self.source:
            raise ValueError("a label set belongs to another source")
        return self


@dataclass(frozen=True, slots=True)
class LabelIndex:
    """A cached set, by exact name and, for a name another case wrote, by its casefold."""

    cache: LabelCache
    exact: Mapping[str, RepositoryLabel]
    folded: Mapping[str, RepositoryLabel]

    def get(self, name: str) -> RepositoryLabel | None:
        return self.exact.get(name) or self.folded.get(name.casefold())


class LabelEntry(TypedDict):
    name: str
    color: str | None
    description: str | None


@dataclass(frozen=True, slots=True)
class LabelLookup:
    """The set's entries for the labels named alone, and the names the set does not hold.

    A name the set holds without a color is in neither: no read of the set can color it.
    """

    entries: list[LabelEntry]
    missing: tuple[str, ...]


def labels_job_key(source: str) -> str:
    """The coordinator key of a repository's label job, by its normalized source."""

    return f"{source}:labels"


def labels_for(home: Path, slug: str, source: str, labels: Iterable[object]) -> LabelLookup:
    """The set's entries for the *labels* a record or core names without a color.

    *labels* are a dumped record's or core's labels. One that has its own color needs
    nothing; one named alone, as a record cached before label colors names it, takes its
    color and description from the set, by name. Each distinct name counts once. Blocking
    and bounded: a stat, and a parse only when the set's file changed.
    """

    wanted: list[str] = []
    for label in labels:
        if isinstance(label, dict) and label.get("color") is None:  # pyright: ignore[reportUnknownMemberType]
            name = label.get("name")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            if isinstance(name, str) and name not in wanted:
                wanted.append(name)
    if not wanted:
        return LabelLookup([], ())
    index = label_index(home, slug, source)
    if index is None:
        return LabelLookup([], tuple(wanted))
    entries: list[LabelEntry] = []
    missing: list[str] = []
    for name in wanted:
        found = index.get(name)
        if found is None:
            missing.append(name)
        elif found.color is not None:
            entries.append(LabelEntry(name=name, color=found.color, description=found.description))
    return LabelLookup(entries, tuple(missing))


# A refused cache write must still back off in this process (:class:`.Unwritten`).
_UNWRITTEN: Final = Unwritten()
# The parsed set of each file, by home and source, with the file's inode, modification
# time, and size: a pull read reads the set on every poll, and a replaced file has a new
# inode.
_INDEXES: OrderedDict[tuple[str, str], tuple[tuple[int, int, int], LabelIndex]] = OrderedDict()
_INDEX_LOCK = threading.Lock()


def forget() -> None:
    """Forget every set this process parsed and every outcome it could not write.

    A new process starts with neither; the suite starts each test this way.
    """

    _UNWRITTEN.clear()
    with _INDEX_LOCK:
        _INDEXES.clear()


def _file_stamp(home: Path, slug: str) -> tuple[int, int, int] | None:
    try:
        found = os.lstat(home / source_labels(slug))
    except OSError:
        return None
    if not stat.S_ISREG(found.st_mode):
        return None
    return found.st_ino, found.st_mtime_ns, found.st_size


def read_labels(home: Path, slug: str, source: str) -> LabelCache | None:
    """The cached set of *source*, or ``None``. Blocking and bounded; never repairs."""

    try:
        data = read_bytes_bounded(
            home, source_labels(slug), max_bytes=MAX_LABELS_BYTES, shared="refuse"
        )
        cache = LabelCache.model_validate_json(data)
    except (RecordError, PrivateStorageError, OSError, ValueError):
        return None
    return cache if cache.source == source else None


def label_index(home: Path, slug: str, source: str) -> LabelIndex | None:
    """The cached set as an index, parsed once a file. Blocking and bounded.

    A pull read calls this on every poll, and a refresh for each of its rate-limit checks.
    Parsing and indexing home-assistant/core's 2,894 labels took a median 3.5 ms, at most
    5.7, in 30 runs at a load average of 18 (2026-11-15); a file that has not changed
    since costs a stat.
    """

    stamp = _file_stamp(home, slug)
    if stamp is None:
        return None
    key = (str(home), source)
    with _INDEX_LOCK:
        held = _INDEXES.get(key)
        if held is not None and held[0] == stamp:
            _INDEXES.move_to_end(key)
            return held[1]
    cache = read_labels(home, slug, source)
    if cache is None:
        return None
    exact: dict[str, RepositoryLabel] = {}
    folded: dict[str, RepositoryLabel] = {}
    for label in cache.snapshot.labels() if cache.snapshot is not None else ():
        exact.setdefault(label.name, label)
        folded.setdefault(label.name.casefold(), label)
    index = LabelIndex(cache, exact, folded)
    with _INDEX_LOCK:
        _INDEXES[key] = (stamp, index)
        _INDEXES.move_to_end(key)
        while len(_INDEXES) > _MAX_INDEXES:
            _INDEXES.popitem(last=False)
    return index


def _cached(repository: ListedRepository) -> LabelCache | None:
    index = label_index(repository.home, repository.slug, repository.source)
    return index.cache if index is not None else None


def last_refresh(home: Path, source: str, cache: LabelCache | None) -> PullRefreshStamp | None:
    durable = cache.last_refresh if cache is not None else None
    return _UNWRITTEN.last_refresh(home, source, durable)


def remaining_freshness(stamp: PullRefreshStamp | None) -> float:
    return snapshot_freshness(stamp, LABEL_FRESHNESS_S)


def _rate_hold(repository: ListedRepository) -> PullRefreshStamp | None:
    # The set's own stamp comes from its stat-gated index, so a check during a refresh,
    # which holds the network slot, costs a stat and the catalog's small stamp file.
    return rate_hold(
        repository, last_refresh(repository.home, repository.source, _cached(repository))
    )


def refresh_wanted(repository: ListedRepository, *, retry: bool = False) -> bool:
    """Whether an ask reads the set from GitHub now. Blocking and bounded; never contacts GitHub.

    Wanted when nothing is cached, once the set's last refresh is :data:`LABEL_FRESHNESS_S`
    old and the budget admits automatic work (:func:`.gh_budget.admission`), or when a
    reader's own *retry* asks; never while GitHub's limit holds. Only
    ``POST github/labels-refresh`` asks, which a page sends for a label named alone that
    its envelope has no entry for, so the set is read again at most once in that age, and
    only while something asks. A failure backs off for that age too.
    """

    if _rate_hold(repository) is not None:
        return False
    if retry:
        return True
    stamp = last_refresh(repository.home, repository.source, _cached(repository))
    # A page's own ask is automatic work, which the budget may hold: only chip colors wait.
    return (
        remaining_freshness(stamp) == 0
        and gh_budget.admission(("core",), now=pull_list.utc_now(), speculative=True).admitted
    )


def publish_labels(
    repository: ListedRepository,
    previous: LabelCache | None,
    snapshot: LabelSnapshot | None,
    stamp: PullRefreshStamp,
) -> bool:
    """Publish one whole revision under the source lock; reject a superseded writer.

    A failure supplies no snapshot and keeps the preceding one. Async callers use
    run_lock_section, so a cancelled lock waiter cannot write later.
    """

    def compose(current: LabelCache | None) -> LabelCache:
        kept = snapshot if snapshot is not None else current.snapshot if current else None
        return LabelCache(source=repository.source, snapshot=kept, last_refresh=stamp)

    return publish_revision(
        repository,
        previous,
        stamp,
        read=partial(read_labels, repository.home, repository.slug, repository.source),
        compose=compose,
        relative=source_labels(repository.slug),
        max_bytes=MAX_LABELS_BYTES,
        unwritten=_UNWRITTEN,
        too_large="the label set exceeds its cache bound",
    )


def _label(value: object) -> RepositoryLabel | None:
    item = as_dict(value)
    name = item.get("name")
    if not isinstance(name, str):
        return None
    description = label_description(item.get("description"))
    return RepositoryLabel(
        name=cut_escaped(name, MAX_LABEL_NAME_BYTES)[0],
        color=label_color(item.get("color")),
        description=None
        if description is None
        else cut_escaped(description, MAX_LABEL_DESCRIPTION_BYTES)[0],
    )


def _page(response: GhResponse, old: LabelPage | None) -> LabelPage:
    if response.status == 304:
        if old is None or old.etag is None:
            raise ValueError("an unconditional label page answered 304")
        # GitHub's ETag covers a page's body, not its Link header, and a 304 carries the
        # Link: a full last page answers 304 after a label is added past it, naming the
        # next page. Only a 304 that names no Link keeps the page's cached continuation.
        has_next = response.has_next_page if "link" in response.headers else old.has_next
        return old.model_copy(update={"etag": response.etag or old.etag, "has_next": has_next})
    payload = response.json()
    if not isinstance(payload, list) or len(payload) > LABEL_PAGE_SIZE:  # pyright: ignore[reportUnknownArgumentType]
        raise ValueError("unreadable label page")
    items: list[object] = payload  # pyright: ignore[reportUnknownVariableType]
    labels = tuple(label for label in map(_label, items) if label is not None)
    return LabelPage(etag=response.etag, has_next=response.has_next_page, labels=labels)


async def _check_hold(repository: ListedRepository) -> None:
    await check_hold(partial(_rate_hold, repository))


async def refresh_labels(
    repository: ListedRepository,
    *,
    slot: contextlib.AbstractAsyncContextManager[None] | None = None,
    retry: bool = False,
) -> None:
    """Read the set when it is wanted, yielding the network slot after each bounded page.

    The job under :func:`labels_job_key` runs this. It asks gh for the account before its
    pages and after them, so a snapshot's reader read every page of it.
    """

    if not await asyncio.to_thread(refresh_wanted, repository, retry=retry):
        return
    previous = await asyncio.to_thread(_cached, repository)
    reader: str | None = None
    try:
        repository = await claim_source(repository)
        previous = await asyncio.to_thread(_cached, repository)
        async with slot if slot is not None else contextlib.nullcontext():
            await _check_hold(repository)
            reader = f"gh:{await active_account()}"
        old = previous.snapshot if previous is not None else None
        if old is not None and old.reader != reader:
            old = None
        pages: list[LabelPage] = []
        used = 0
        complete = False
        for index in range(MAX_LABEL_PAGES):
            cached = old.pages[index] if old is not None and index < len(old.pages) else None
            path = (
                f"repos/{repository.owner}/{repository.repo}/labels"
                f"?per_page={LABEL_PAGE_SIZE}&page={index + 1}"
            )
            async with slot if slot is not None else contextlib.nullcontext():
                await _check_hold(repository)
                response = await gh_api(path, etag=cached.etag if cached else None)
            page = _page(response, cached)
            used += len(page.model_dump_json().encode())
            if used > MAX_LABELS_BYTES - _ENVELOPE_BYTES:
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
                    "account_changed", "GitHub account changed while reading labels"
                )
        now = utc_stamp(pull_list.utc_now())
        snapshot = LabelSnapshot(
            source=repository.source,
            reader=reader,
            fetched_at=now,
            complete=complete,
            pages=tuple(pages),
        )
        stamp = PullRefreshStamp(outcome="succeeded", at=now, reader=reader)
        await run_lock_section(partial(publish_labels, repository, previous, snapshot, stamp))
        return
    except FAILURES as exc:
        stamp = failure_stamp(
            exc,
            repository,
            reader=reader,
            subject="the repository's labels",
            unavailable="The repository's labels are unavailable",
        )
    await record_failure(
        partial(publish_labels, repository, previous, None, stamp), repository, stamp, _UNWRITTEN
    )


__all__ = [
    "LABEL_FRESHNESS_S",
    "LABEL_PAGE_SIZE",
    "LabelCache",
    "LabelEntry",
    "LabelIndex",
    "LabelLookup",
    "LabelPage",
    "LabelSnapshot",
    "MAX_LABELS_BYTES",
    "MAX_LABEL_NAME_BYTES",
    "MAX_LABEL_PAGES",
    "RepositoryLabel",
    "forget",
    "label_index",
    "labels_for",
    "labels_job_key",
    "last_refresh",
    "publish_labels",
    "read_labels",
    "refresh_labels",
    "refresh_wanted",
    "remaining_freshness",
]
