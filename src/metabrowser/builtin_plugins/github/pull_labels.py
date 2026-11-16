"""The repository's whole label set, cached once, so every label chip has its color.

A pull request's record and the catalog's rows carry each label's color, but a record or
a core cached before label colors names its labels alone, and the catalog vouches for
such a record as current for as long as its pull request does not change, so it is never
read again. This set colors those chips by name (``mb-varu``): one bounded snapshot of
``repos/<owner>/<repo>/labels``, every page with its ETag, at
``sources/<slug>/pulls/labels.json``, published under the source-alias lock and read
lock-free with a size bound. It persists across restarts and is cleared with the rest of
the plugin's cache.

Reads never contact GitHub. The catalog's refresh job asks for the set once it has
published a page, when the set is absent or older than :data:`LABEL_FRESHNESS_S`, or
lacks a label a pull read showed without a color (:func:`note_unknown`) and was last
asked for at least :data:`UNKNOWN_LABEL_HOLD_S` ago; ``POST github/labels-refresh`` asks
for it too. Running inside the catalog's job keeps the two from asking GitHub at once. GitHub's
rate limit holds it as it holds the catalog. A failure keeps the preceding snapshot.

This module follows :mod:`.pull_stacks`, the other optional repository-wide snapshot.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
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

from metabrowser.builtin_plugins.github import pull_list
from metabrowser.builtin_plugins.github.checkout import claim_source
from metabrowser.builtin_plugins.github.gh import GhError, GhResponse, gh_api
from metabrowser.builtin_plugins.github.gh_lists import (
    PullDataError,
    UnreadableItemError,
    as_dict,
    cache_failure_reason,
    cache_unwritable,
    utc_stamp,
)
from metabrowser.builtin_plugins.github.gh_lists import active_account as active_account
from metabrowser.builtin_plugins.github.pull_list import (
    ETAG_PATTERN,
    MAX_ROW_LABEL_BYTES,
    ListedRepository,
)
from metabrowser.builtin_plugins.github.pull_record import (
    LabelColor,
    PullRefreshStamp,
    Reader,
    Timestamp,
    cut_escaped,
    ensure_pulls_directory,
    label_color,
    label_description,
)
from metabrowser.cache.atomic import RecordError, read_bytes_bounded
from metabrowser.cache.layout import FutureLayoutFormatError, LayoutError
from metabrowser.cache.locks import run_lock_section, source_alias_lock
from metabrowser.cache.paths import source_labels
from metabrowser.home import PrivateStorageError, write_private_file_atomic
from metabrowser.mirror_refresh import FRESHNESS_WINDOW_S

log = logging.getLogger(__name__)

# A label set changes rarely, so it is refreshed as the native stack snapshot is, the
# other repository-wide snapshot (pull_stacks.STACK_FRESHNESS_S). Each page is asked for
# with its ETag, and an unchanged page answers 304.
LABEL_FRESHNESS_S: Final = 300.0
# A record that names a label the set does not hold asks for the set again, once a
# freshness window: a label deleted on GitHub stays unknown, and must not be asked for on
# every read.
UNKNOWN_LABEL_HOLD_S: Final = FRESHNESS_WINDOW_S
LABEL_PAGE_SIZE: Final = 100
# Measured 2026-11-15 (``gh api repos/<r>/labels``): home-assistant/core has 2,894 labels,
# elastic/kibana 1,732, and rust-lang/rust 999, the most of eleven large repositories.
# Fifty pages hold 5,000. A label's name is at most 50 characters and its description 100,
# and they are cut as a row's name is and at 100 characters of any script.
MAX_LABEL_PAGES: Final = 50
MAX_LABEL_DESCRIPTION_BYTES: Final = 400
# home-assistant/core's 2,894 labels are 208,661 bytes cached (29 pages, each with its
# ETag). A set of 5,000 labels at every bound would be about 2.6 MB; 4 MiB is the read
# bound and the write bound.
MAX_LABELS_BYTES: Final = 4 * 1024 * 1024
# Memory for a server's few repositories, and a test's many homes.
_MAX_INDEXES: Final = 16
_MAX_UNWRITTEN: Final = 64
# Room for the enclosing cache and its refresh outcome within the bound.
_ENVELOPE_BYTES: Final = 16 * 1024

Etag = Annotated[str, StringConstraints(pattern=ETAG_PATTERN)]
Revision = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$")]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RepositoryLabel(_Model):
    """One label of the repository: its name, GitHub's color, and its description."""

    name: Annotated[str, StringConstraints(max_length=MAX_ROW_LABEL_BYTES)]
    color: LabelColor | None
    description: Annotated[str, StringConstraints(max_length=MAX_LABEL_DESCRIPTION_BYTES)] | None


class LabelPage(_Model):
    """One page of the set, with the ETag that asks for it again conditionally."""

    etag: Etag | None
    has_next: StrictBool
    labels: tuple[RepositoryLabel, ...] = Field(max_length=LABEL_PAGE_SIZE)


class LabelSnapshot(_Model):
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


def labels_job_key(source: str) -> str:
    """The coordinator key of a repository's label job, by its normalized source."""

    return f"{source}:labels"


def labels_for(home: Path, slug: str, source: str, labels: Iterable[object]) -> list[LabelEntry]:
    """The set's entries for the *labels* a record or core names without a color.

    *labels* are a dumped record's or core's labels. One that has its own color needs
    nothing; one named alone, as a record cached before label colors names it, takes its
    color and description from the set, by name. Blocking and bounded: a stat, and a parse
    only when the set's file changed.
    """

    wanted: list[str] = []
    for label in labels:
        if isinstance(label, dict) and label.get("color") is None:  # pyright: ignore[reportUnknownMemberType]
            name = label.get("name")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            if isinstance(name, str) and name not in wanted:
                wanted.append(name)
    if not wanted:
        return []
    index = label_index(home, slug, source)
    if index is None:
        return []
    entries: list[LabelEntry] = []
    for name in wanted:
        found = index.get(name)
        if found is not None and found.color is not None:
            entries.append(LabelEntry(name=name, color=found.color, description=found.description))
    return entries


# A refused cache write must still back off in this process, as the stack job's does.
_UNWRITTEN: OrderedDict[tuple[str, str], PullRefreshStamp] = OrderedDict()
# The parsed set of each file, by its inode, modification time, and size: a pull read
# reads the set on every poll, and a replaced file has a new inode.
_INDEXES: OrderedDict[tuple[str, str], tuple[tuple[int, int, int], LabelIndex]] = OrderedDict()
_INDEX_LOCK = threading.Lock()


def _key(home: Path, source: str) -> tuple[str, str]:
    return str(home), source


# Labels a pull read showed without a color that the set did not hold, by source, which the
# catalog's next refresh asks for (:func:`take_unknown`). A read never asks GitHub, so it
# notes them here. Bounded: a few repositories, a page of names each.
_UNKNOWN: OrderedDict[str, list[str]] = OrderedDict()
_MAX_UNKNOWN_SOURCES: Final = 16
_MAX_UNKNOWN_NAMES: Final = 100
# The sets being read now, by home and source, so a pull read knows a color may be coming.
_FETCHING: set[tuple[str, str]] = set()


def note_unknown(source: str, names: Iterable[str], known: Iterable[LabelEntry]) -> None:
    """Note *names* a read showed uncolored that *known*, the set's entries, lacks."""

    held = {entry["name"] for entry in known}
    missing = [name for name in names if name not in held]
    if not missing:
        return
    noted = _UNKNOWN.setdefault(source, [])
    for name in missing:
        if name not in noted and len(noted) < _MAX_UNKNOWN_NAMES:
            noted.append(name)
    _UNKNOWN.move_to_end(source)
    while len(_UNKNOWN) > _MAX_UNKNOWN_SOURCES:
        _UNKNOWN.popitem(last=False)


def take_unknown(source: str) -> tuple[str, ...]:
    """The names :func:`note_unknown` noted for *source*, once."""

    return tuple(_UNKNOWN.pop(source, ()))


def labels_fetching(home: Path, source: str) -> bool:
    """Whether *source*'s set is being read from GitHub now. Memory only."""

    return _key(home, source) in _FETCHING


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

    A pull read calls this on every poll. Parsing and indexing home-assistant/core's 2,894
    labels took a median 3.5 ms, at most 5.7, in 30 runs at a load average of 18
    (2026-11-15); a file that has not changed since costs a stat.
    """

    stamp = _file_stamp(home, slug)
    if stamp is None:
        return None
    key = _key(home, source)
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


def last_refresh(home: Path, source: str, cache: LabelCache | None) -> PullRefreshStamp | None:
    durable = cache.last_refresh if cache is not None else None
    transient = _UNWRITTEN.get(_key(home, source))
    if transient is not None and (durable is None or transient.at >= durable.at):
        return transient
    return durable


def _remember(repository: ListedRepository, stamp: PullRefreshStamp) -> None:
    key = _key(repository.home, repository.source)
    held = _UNWRITTEN.get(key)
    if held is None or not pull_list.rate_limit_holds(held, now=pull_list.utc_now()):
        _UNWRITTEN[key] = stamp
    _UNWRITTEN.move_to_end(key)
    while len(_UNWRITTEN) > _MAX_UNWRITTEN:
        _UNWRITTEN.popitem(last=False)


def _age(stamp: PullRefreshStamp | None) -> float:
    if stamp is None:
        return float("inf")
    return (pull_list.utc_now() - pull_list.parse_stamp(stamp.at)).total_seconds()


def remaining_freshness(stamp: PullRefreshStamp | None) -> float:
    return max(0.0, min(LABEL_FRESHNESS_S, LABEL_FRESHNESS_S - _age(stamp)))


def _rate_hold(repository: ListedRepository, cache: LabelCache | None) -> PullRefreshStamp | None:
    # The catalog's provider refusal holds this optional set too; the set never writes
    # or clears the catalog's outcome.
    candidates = (
        last_refresh(repository.home, repository.source, cache),
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


def refresh_wanted(
    repository: ListedRepository, *, retry: bool = False, names: Iterable[str] = ()
) -> bool:
    """Whether to ask GitHub for the set now. Blocking and bounded; never contacts GitHub.

    Wanted when nothing is cached, the set is older than :data:`LABEL_FRESHNESS_S`, or a
    reader's own *retry* asks; or when it does not hold one of *names* and was last asked
    for at least :data:`UNKNOWN_LABEL_HOLD_S` ago. Never while GitHub's limit holds.
    """

    names = tuple(names)
    index = label_index(repository.home, repository.slug, repository.source)
    cache = index.cache if index is not None else None
    if _rate_hold(repository, cache) is not None:
        return False
    stamp = last_refresh(repository.home, repository.source, cache)
    if retry or remaining_freshness(stamp) == 0:
        return True
    unknown = bool(names) and (index is None or any(index.get(name) is None for name in names))
    return unknown and _age(stamp) >= UNKNOWN_LABEL_HOLD_S


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

    with source_alias_lock(repository.home, repository.slug):
        current = read_labels(repository.home, repository.slug, repository.source)
        if (current.revision if current else None) != (previous.revision if previous else None):
            return False
        held = last_refresh(repository.home, repository.source, current)
        if (
            pull_list.rate_limit_holds(held, now=pull_list.utc_now())
            and stamp.outcome != "rate_limited"
        ):
            return False
        result = LabelCache(
            source=repository.source,
            snapshot=snapshot if snapshot is not None else current.snapshot if current else None,
            last_refresh=stamp,
        )
        data = result.model_dump_json().encode()
        if len(data) > MAX_LABELS_BYTES:
            raise ValueError("the label set exceeds its cache bound")
        ensure_pulls_directory(repository.home, repository.slug)
        write_private_file_atomic(repository.home, source_labels(repository.slug), data)
        _UNWRITTEN.pop(_key(repository.home, repository.source), None)
        return True


def _label(value: object) -> RepositoryLabel | None:
    item = as_dict(value)
    name = item.get("name")
    if not isinstance(name, str):
        return None
    description = label_description(item.get("description"))
    return RepositoryLabel(
        name=cut_escaped(name, MAX_ROW_LABEL_BYTES)[0],
        color=label_color(item.get("color")),
        description=None
        if description is None
        else cut_escaped(description, MAX_LABEL_DESCRIPTION_BYTES)[0],
    )


def _page(response: GhResponse, old: LabelPage | None) -> LabelPage:
    if response.status == 304:
        if old is None or old.etag is None:
            raise ValueError("an unconditional label page answered 304")
        return old.model_copy(update={"etag": response.etag or old.etag})
    payload = response.json()
    if not isinstance(payload, list) or len(payload) > LABEL_PAGE_SIZE:  # pyright: ignore[reportUnknownArgumentType]
        raise ValueError("unreadable label page")
    items: list[object] = payload  # pyright: ignore[reportUnknownVariableType]
    labels = tuple(label for label in map(_label, items) if label is not None)
    return LabelPage(etag=response.etag, has_next=response.has_next_page, labels=labels)


async def _check_hold(repository: ListedRepository) -> None:
    def held() -> PullRefreshStamp | None:
        return _rate_hold(
            repository, read_labels(repository.home, repository.slug, repository.source)
        )

    stamp = await asyncio.to_thread(held)
    if stamp is not None:
        raise GhError(
            "GitHub's API rate limit is exhausted", state="rate_limited", reset_at=stamp.reset_at
        )


async def refresh_labels(
    repository: ListedRepository,
    *,
    slot: asyncio.Semaphore | None = None,
    retry: bool = False,
    names: tuple[str, ...] = (),
    reader: str | None = None,
) -> None:
    """Ask GitHub for the set, yielding the network slot after each bounded page.

    *reader* is the account a caller already reads as, the catalog's job, which checks it
    on every page of its own; without one, the job asks gh before and after its pages.
    """

    if not await asyncio.to_thread(refresh_wanted, repository, retry=retry, names=names):
        return
    fetching = _key(repository.home, repository.source)
    _FETCHING.add(fetching)
    try:
        await _refresh(repository, slot=slot, known_reader=reader)
    finally:
        _FETCHING.discard(fetching)


async def _refresh(
    repository: ListedRepository, *, slot: asyncio.Semaphore | None, known_reader: str | None
) -> None:
    previous = await asyncio.to_thread(
        read_labels, repository.home, repository.slug, repository.source
    )
    reader: str | None = None
    try:
        repository = await claim_source(repository)
        previous = await asyncio.to_thread(
            read_labels, repository.home, repository.slug, repository.source
        )
        async with slot if slot is not None else contextlib.nullcontext():
            await _check_hold(repository)
            reader = known_reader or f"gh:{await active_account()}"
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
            if known_reader is None and f"gh:{await active_account()}" != reader:
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
    except (GhError, PullDataError) as exc:
        stamp = PullRefreshStamp(
            outcome=exc.state,
            message=str(exc)[:1000],
            reset_at=exc.reset_at,
            at=utc_stamp(pull_list.utc_now()),
            reader=reader,
        )
    except (RecordError, PrivateStorageError, OSError, LayoutError, FutureLayoutFormatError) as exc:
        log.debug("the label set's cache refused a write: %s", exc)
        message = (
            str(
                cache_unwritable(
                    "the repository's labels",
                    exc,
                    source=repository.source,
                    checkout=repository.checkout,
                )
            )
            if isinstance(exc, (PrivateStorageError, OSError))
            else f"the repository's labels could not be cached: {cache_failure_reason(exc)}"
        )
        stamp = PullRefreshStamp(
            outcome="cache_unwritable",
            message=message[:1000],
            at=utc_stamp(pull_list.utc_now()),
            reader=reader,
        )
    except (ValueError, KeyError, TypeError, UnreadableItemError) as exc:
        log.debug("the repository's labels were unreadable: %s", exc)
        stamp = PullRefreshStamp(
            outcome="unreadable",
            message="The repository's labels are unavailable",
            at=utc_stamp(pull_list.utc_now()),
            reader=reader,
        )
    try:
        await run_lock_section(partial(publish_labels, repository, previous, None, stamp))
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
    "LABEL_FRESHNESS_S",
    "LabelCache",
    "LabelEntry",
    "LabelIndex",
    "LabelPage",
    "LabelSnapshot",
    "MAX_LABELS_BYTES",
    "MAX_LABEL_PAGES",
    "RepositoryLabel",
    "UNKNOWN_LABEL_HOLD_S",
    "label_index",
    "labels_fetching",
    "labels_for",
    "labels_job_key",
    "last_refresh",
    "note_unknown",
    "publish_labels",
    "read_labels",
    "refresh_labels",
    "refresh_wanted",
    "remaining_freshness",
    "take_unknown",
]
