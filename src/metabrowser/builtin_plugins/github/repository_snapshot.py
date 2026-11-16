"""What the optional repository-wide snapshots share: the native stacks and the label set.

:mod:`.pull_stacks` and :mod:`.pull_labels` each keep one bounded snapshot of a paged REST
list of the repository beside its pull requests, read lock-free and published whole under
the source-alias lock by an optional background job of its own. Each keeps its models
and its page loop. This module holds what they do alike:

- the outcome a refused cache write still remembers in this process (:class:`Unwritten`);
- the age of a refresh (:func:`remaining_freshness`);
- GitHub's rate-limit hold, which the catalog's outcome imposes on them and they read but
  never write (:func:`rate_hold`, :func:`check_hold`);
- the publish step, which checks the source and refuses a superseded writer
  (:func:`publish_revision`);
- the outcome a failed refresh records, keeping the preceding snapshot
  (:func:`failure_stamp`, :func:`record_failure`).
"""

from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path
from typing import Final, Protocol

from metabrowser.builtin_plugins.github import pull_list
from metabrowser.builtin_plugins.github.gh import GhError
from metabrowser.builtin_plugins.github.gh_lists import (
    PullDataError,
    UnreadableItemError,
    cache_failure_reason,
    cache_unwritable,
    utc_stamp,
)
from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from metabrowser.builtin_plugins.github.pull_record import (
    MAX_REFRESH_MESSAGE_CHARS,
    PullRefreshStamp,
    ensure_pulls_directory,
)
from metabrowser.cache.atomic import RecordError, read_record
from metabrowser.cache.layout import FutureLayoutFormatError, LayoutError, read_layout
from metabrowser.cache.locks import run_lock_section, source_alias_lock
from metabrowser.cache.paths import source_record
from metabrowser.cache.records import REPOSITORY_SOURCE_CONTRACT_ID, RepositorySource
from metabrowser.home import PrivateStorageError, write_private_file_atomic

log = logging.getLogger(__name__)

# The cache's refusals, which a failed refresh records as ``cache_unwritable``.
_CACHE_ERRORS: Final = (
    RecordError,
    PrivateStorageError,
    OSError,
    LayoutError,
    FutureLayoutFormatError,
)
# Every failure a snapshot's refresh records as its outcome; anything else is a
# programming error, which the refresh coordinator logs.
FAILURES: Final = (
    GhError,
    PullDataError,
    *_CACHE_ERRORS,
    ValueError,
    KeyError,
    TypeError,
    UnreadableItemError,
)


class SnapshotCache(Protocol):
    """A snapshot's cache file as its module models it: one revision and its last outcome."""

    @property
    def revision(self) -> str: ...

    @property
    def last_refresh(self) -> PullRefreshStamp: ...

    def model_dump_json(self) -> str: ...


class Unwritten:
    """The outcome of a refresh whose cache write was refused, by home and source.

    A refused write must still back off in this process. Nothing else is kept: no path, no
    provider output, and only a bounded working set.
    """

    def __init__(self, limit: int = 64) -> None:
        self._held: OrderedDict[tuple[str, str], PullRefreshStamp] = OrderedDict()
        self._limit = limit

    def last_refresh(
        self, home: Path, source: str, durable: PullRefreshStamp | None
    ) -> PullRefreshStamp | None:
        """The later of *durable*, the cached outcome, and one this process could not write."""

        transient = self._held.get((str(home), source))
        if transient is not None and (durable is None or transient.at >= durable.at):
            return transient
        return durable

    def remember(self, repository: ListedRepository, stamp: PullRefreshStamp) -> None:
        """Keep *stamp*, unless a rate limit it would replace still holds."""

        key = (str(repository.home), repository.source)
        held = self._held.get(key)
        if held is None or not pull_list.rate_limit_holds(held, now=pull_list.utc_now()):
            self._held[key] = stamp
        self._held.move_to_end(key)
        while len(self._held) > self._limit:
            self._held.popitem(last=False)

    def written(self, repository: ListedRepository) -> None:
        """The cache now holds the outcome; forget the one this process kept."""

        self._held.pop((str(repository.home), repository.source), None)

    def clear(self) -> None:
        self._held.clear()


def remaining_freshness(stamp: PullRefreshStamp | None, freshness_s: float) -> float:
    """Seconds until a refresh that ended at *stamp* is *freshness_s* old; none, ``0``."""

    if stamp is None:
        return 0.0
    age = (pull_list.utc_now() - pull_list.parse_stamp(stamp.at)).total_seconds()
    return max(0.0, min(freshness_s, freshness_s - age))


def rate_hold(
    repository: ListedRepository, own: PullRefreshStamp | None
) -> PullRefreshStamp | None:
    """The stamp whose GitHub rate limit still holds: the snapshot's *own*, or the catalog's.

    The core catalog's provider refusal also holds optional enrichment. A snapshot reads
    that hold but never writes or clears the catalog's outcome. Blocking and bounded.
    """

    now = pull_list.utc_now()
    candidates = (own, pull_list.read_list_refresh(repository.home, repository.slug, "all"))
    return next((stamp for stamp in candidates if pull_list.rate_limit_holds(stamp, now=now)), None)


async def check_hold(held: Callable[[], PullRefreshStamp | None]) -> None:
    """Raise GitHub's rate limit when *held*, run off the event loop, names a hold."""

    stamp = await asyncio.to_thread(held)
    if stamp is not None:
        raise GhError(
            "GitHub's API rate limit is exhausted", state="rate_limited", reset_at=stamp.reset_at
        )


def source_matches(repository: ListedRepository) -> None:
    """Refuse, with ``ValueError``, a cache whose source record names another repository."""

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


def publish_revision[Cache: SnapshotCache](
    repository: ListedRepository,
    previous: Cache | None,
    stamp: PullRefreshStamp,
    *,
    read: Callable[[], Cache | None],
    compose: Callable[[Cache | None], Cache],
    relative: str,
    max_bytes: int,
    unwritten: Unwritten,
    too_large: str,
) -> bool:
    """Publish one whole revision under the source lock; reject a superseded writer.

    The source must be *repository*'s, before the lock and under it. *read* is the cached
    revision now; one other than *previous* means another writer published since this one
    read, and this one is refused. A success never replaces a rate limit that still holds.
    *compose* builds the new revision from the current one, which keeps its snapshot when
    a failure supplies none. Async callers use run_lock_section, so a cancelled lock waiter
    cannot write later.
    """

    source_matches(repository)
    with source_alias_lock(repository.home, repository.slug):
        source_matches(repository)
        current = read()
        if (current.revision if current else None) != (previous.revision if previous else None):
            return False
        held = unwritten.last_refresh(
            repository.home, repository.source, current.last_refresh if current else None
        )
        if (
            pull_list.rate_limit_holds(held, now=pull_list.utc_now())
            and stamp.outcome != "rate_limited"
        ):
            return False
        data = compose(current).model_dump_json().encode()
        if len(data) > max_bytes:
            raise ValueError(too_large)
        ensure_pulls_directory(repository.home, repository.slug)
        write_private_file_atomic(repository.home, relative, data)
        unwritten.written(repository)
        return True


def failure_stamp(
    exc: BaseException,
    repository: ListedRepository,
    *,
    reader: str | None,
    subject: str,
    unavailable: str,
) -> PullRefreshStamp:
    """The outcome a refresh records for *exc*, one of :data:`FAILURES`.

    *subject* names the snapshot in a cache refusal, and *unavailable* is what an
    unreadable answer says; neither names a path or repeats GitHub's output.
    """

    at = utc_stamp(pull_list.utc_now())
    if isinstance(exc, (GhError, PullDataError)):
        return PullRefreshStamp(
            outcome=exc.state,
            message=str(exc)[:MAX_REFRESH_MESSAGE_CHARS],
            reset_at=exc.reset_at,
            at=at,
            reader=reader,
        )
    if isinstance(exc, _CACHE_ERRORS):
        log.debug("%s: the cache refused a write: %s", subject, exc)
        # Clearing the plugin's cache mends what it holds, not the home's layout or records.
        message = (
            str(
                cache_unwritable(
                    subject, exc, source=repository.source, checkout=repository.checkout
                )
            )
            if isinstance(exc, (PrivateStorageError, OSError))
            else f"{subject} could not be cached: {cache_failure_reason(exc)}"
        )
        return PullRefreshStamp(
            outcome="cache_unwritable",
            message=message[:MAX_REFRESH_MESSAGE_CHARS],
            at=at,
            reader=reader,
        )
    log.debug("%s was unreadable: %s", subject, exc)
    return PullRefreshStamp(outcome="unreadable", message=unavailable, at=at, reader=reader)


async def record_failure(
    write: Callable[[], bool],
    repository: ListedRepository,
    stamp: PullRefreshStamp,
    unwritten: Unwritten,
) -> None:
    """Publish a failure's *stamp* with *write*, keeping the snapshot; refused, remember it."""

    try:
        await run_lock_section(write)
    except (*_CACHE_ERRORS, ValueError):
        unwritten.remember(repository, stamp)


__all__ = [
    "FAILURES",
    "SnapshotCache",
    "Unwritten",
    "check_hold",
    "failure_stamp",
    "publish_revision",
    "rate_hold",
    "record_failure",
    "remaining_freshness",
    "source_matches",
]
