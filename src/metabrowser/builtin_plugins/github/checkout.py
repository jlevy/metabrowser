"""A checkout served as a folder: which GitHub repository its pull requests are of.

A folder server has no mirror session, so the pull routes ask this module instead. The
repository is the one :func:`~metabrowser.repository_context.discover_repository_context`
reads from the served root's checkout, a subdirectory's included: the ``origin`` remote,
read from files with no Git process. It is reduced through this plugin's URL grammar to
``https://github.com/<owner>/<repo>``, lowercased, so an HTTPS and an SSH remote of one
repository, and a mirror of it, share one identity and one set of records. A remote the
grammar refuses is not one the routes list: they answer ``not_github``. On a fork,
``origin`` is usually the fork, and the tab names the repository it lists.

Reading creates nothing. The routes read the records under the slug the source has, or
would have once published, and answer ``absent`` while there is no source directory. A
job's first write claims the slug and publishes the source with no store, the cache's
``unattached`` state (:func:`claim_source`). Opening Changes may attach a store that
borrows the checkout's objects; its lender path stays internal to the
cache. A healthy existing store is reused without acquisition. Only a reader's own
comparison request acquires one: the first acquisition fetches whatever the checkout
lacks from its origin, and every later refresh then fetches into the store. Once a store
is attached, a Conversation page can ask for one pull request's comparison as optional
work, which fetches only that pull request's head and base. It starts only while no other
pull job of the checkout runs, holds no network slot, records no outcome, and a reader's
own request promotes it or cancels it. Nothing is written to the
checkout, no Git runs in it, and the served folder stays the same.

What is resolved is remembered for the served root and the application home, so a route
answers from memory after its first request. Resolving reads the checkout's Git pointer
file, configuration, ``HEAD``, and the ref it names, each bounded: measured 2026-11-02 at
a load average near 28, 2.6 to 2.8 ms at the median and 14 ms at the worst of 30 on this
repository's own checkout, a linked worktree, and a subdirectory of it. It runs off the
event loop (:func:`resolve_served_checkout`), once per root.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal, overload

from metabrowser.builtin_plugins.github.gh_lists import PullDataError
from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from metabrowser.mirror_refresh import MAX_PULL_JOBS, PullJobStart, StoreTurn, mirror_session
from metabrowser.source import get_source_session

if TYPE_CHECKING:
    from metabrowser.builtin_plugins.github.pull_record import PullRecord, RecordAbsence
    from metabrowser.builtin_plugins.github.served_pull import ServedPull, ServedPulls
    from metabrowser.cache.acquire import PublishedSource
    from metabrowser.cache.urls import GitSource
    from metabrowser.mirror_refresh import RefreshCoordinator

# Roots a process resolves: one server serves one root, and tests serve several.
_MAX_RESOLVED: Final = 8
log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CheckoutRepository(ListedRepository):
    """A served checkout's repository: where its records are, and the source to claim.

    Before a store is attached, its page withholds any shared comparison.
    """

    git_source: GitSource
    checkout_root: Path
    cached: PublishedSource | None = field(default=None, compare=False, repr=False)


_RESOLVED: dict[tuple[str, str], CheckoutRepository | None] = {}


@dataclass(slots=True)
class _EagerComparison:
    """The checkout's one optional comparison job.

    *mode* is ``idle`` until a reader's own request for the same pull request promotes
    it; only that promotion changes it. *work* is the idle phase while it runs.
    """

    number: int
    revision: str
    mode: Literal["idle", "foreground"] = "idle"
    work: asyncio.Task[None] | None = None


@dataclass
class _CheckoutPulls:
    pulls: ServedPulls
    turn: StoreTurn = field(default_factory=StoreTurn)
    eager: _EagerComparison | None = None
    # The revision each pull request's idle comparison last failed for, so it is not
    # tried again; as many as the pull states a set holds.
    idle_failures: OrderedDict[int, str] = field(default_factory=OrderedDict[int, str])


_PULLS: dict[tuple[str, str, str], _CheckoutPulls] = {}
_LOCK: Final = threading.Lock()


def _served_key(app: Any) -> tuple[str, str] | None:
    """The served root and the application home, or ``None`` where no checkout is served."""

    if mirror_session(app) is not None:
        return None
    root = get_source_session().subject.filesystem_root
    if root is None:
        return None
    from metabrowser.home import StorageDirectoryError, application_cache

    try:
        home = application_cache()
    except StorageDirectoryError:
        return None
    return str(root), str(home)


def _resolve(root: Path, home: Path) -> CheckoutRepository | None:
    """The checkout's repository under the plugin's grammar, or ``None``. Blocking, bounded."""

    from metabrowser.builtin_plugins.github.urls import GithubUrlReducer, parse_repository_url
    from metabrowser.cache.acquire import source_slug
    from metabrowser.cache.urls import GitSource, classify_root_argument
    from metabrowser.repository_context import discover_repository_context, find_git_root

    context = discover_repository_context(root)
    if context is None:
        return None
    classified = classify_root_argument(
        f"https://github.com/{context['owner']}/{context['name']}", reducers=(GithubUrlReducer(),)
    )
    if not isinstance(classified, GitSource) or (
        classified.selection is not None and classified.selection.kind != "repository"
    ):
        return None
    parsed = parse_repository_url(classified.normalized)
    if parsed is None:
        return None
    owner, repo = parsed
    source = GitSource(classified.transport, classified.form, classified.normalized)
    checkout_root = find_git_root(root)
    if checkout_root is None:
        return None
    cached = _cached_store(source, home)
    slug = cached.slug if cached is not None else source_slug(source, home)
    return CheckoutRepository(home, slug, owner, repo, source, checkout_root, cached)


def resolve_served_checkout(app: Any) -> None:
    """Resolve the served checkout's repository, once per root. Blocking; run it off the loop."""

    key = _served_key(app)
    if key is None:
        return
    with _LOCK:
        if key in _RESOLVED:
            return
    resolved = _resolve(Path(key[0]), Path(key[1]))
    with _LOCK:
        if key not in _RESOLVED and len(_RESOLVED) >= _MAX_RESOLVED:
            _RESOLVED.pop(next(iter(_RESOLVED)))
        _RESOLVED.setdefault(key, resolved)


async def ensure_resolved(app: Any) -> None:
    """Resolve the served checkout off the event loop, unless it is remembered."""

    key = _served_key(app)
    if key is not None and key not in _RESOLVED:
        await asyncio.to_thread(resolve_served_checkout, app)


def served_checkout(app: Any) -> CheckoutRepository | None:
    """The served checkout's repository, or ``None``: a mirror, a pin, or a plain folder.

    From memory once :func:`ensure_resolved` has run, which every route does first.
    """

    key = _served_key(app)
    if key is None:
        return None
    if key not in _RESOLVED:
        resolve_served_checkout(app)
    return _RESOLVED.get(key)


def _cached_store(source: GitSource, home: Path) -> PublishedSource | None:
    from metabrowser.cache.acquire import AcquisitionError, cached_source
    from metabrowser.cache.atomic import RecordError
    from metabrowser.cache.identity import SlugCollisionError
    from metabrowser.cache.layout import FutureLayoutFormatError, LayoutError
    from metabrowser.home import PrivateStorageError, StorageDirectoryError

    try:
        return cached_source(source, home)
    except (
        AcquisitionError,
        RecordError,
        SlugCollisionError,
        LayoutError,
        FutureLayoutFormatError,
        PrivateStorageError,
        StorageDirectoryError,
        OSError,
    ):
        # A record remains readable without a usable store. A comparison refresh
        # reports the acquisition failure, and may repair a moved lender.
        return None


def _checkout_key(repository: CheckoutRepository) -> tuple[str, str, str]:
    return str(repository.home), repository.source, str(repository.checkout_root)


def _checkout_state(repository: CheckoutRepository) -> _CheckoutPulls:
    from metabrowser.builtin_plugins.github.served_pull import ServedPulls

    key = _checkout_key(repository)
    with _LOCK:
        held = _PULLS.get(key)
        if held is None:
            if len(_PULLS) >= _MAX_RESOLVED:
                _PULLS.pop(next(iter(_PULLS)))
            held = _PULLS[key] = _CheckoutPulls(ServedPulls(repository.cached or repository))
        return held


def checkout_pulls(repository: CheckoutRepository) -> ServedPulls:
    """The checkout's pull records, with a cached store if one is already usable."""

    return _checkout_state(repository).pulls


def _job_prefix(repository: CheckoutRepository) -> str:
    identity = hashlib.sha256("\0".join(_checkout_key(repository)).encode()).hexdigest()
    return f"checkout:{identity}:pull/"


def checkout_job_key(repository: CheckoutRepository, number: int) -> str:
    """A stable internal job key while a checkout acquires its store."""

    return f"{_job_prefix(repository)}{number}"


async def claim_source(repository: ListedRepository) -> ListedRepository:
    """Publish before a job writes, then rebind checkout state on the event loop.

    The filesystem operation runs in a worker. A disambiguated slug is adopted by every
    checkout of this source without replacing held records or an active acquisition.
    A read never calls this operation. Cache refusals become safe ``cache_unwritable``.
    """
    if not isinstance(repository, CheckoutRepository):
        return repository
    claimed = await asyncio.to_thread(_claim_source, repository)
    if claimed == repository:
        return repository
    with _LOCK:
        for key, held in _RESOLVED.items():
            if (
                held is not None
                and held.home == repository.home
                and held.source == repository.source
            ):
                _RESOLVED[key] = replace(held, home=claimed.home, slug=claimed.slug)
        for state in _PULLS.values():
            published = state.pulls.published
            if (
                isinstance(published, ListedRepository)
                and published.home == repository.home
                and published.source == repository.source
            ):
                state.pulls.bind(replace(published, home=claimed.home, slug=claimed.slug))
    return claimed


def _claim_source(repository: CheckoutRepository) -> CheckoutRepository:
    """Blocking publication only; held pull state belongs to the caller's event loop."""
    from metabrowser.cache.acquire import AcquisitionError, publish_unattached_source
    from metabrowser.cache.atomic import RecordError
    from metabrowser.cache.identity import SlugCollisionError
    from metabrowser.cache.layout import FutureLayoutFormatError, LayoutError
    from metabrowser.cache.locks import LockBusyError
    from metabrowser.home import PrivateStorageError, StorageDirectoryError

    try:
        home, slug = publish_unattached_source(repository.git_source, repository.home)
    except (
        OSError,
        PrivateStorageError,
        StorageDirectoryError,
        LayoutError,
        FutureLayoutFormatError,
        RecordError,
        LockBusyError,
        SlugCollisionError,
        AcquisitionError,
    ) as exc:
        # Each is the cache refusing the write, which is all a job can say of it.
        raise PullDataError(
            "cache_unwritable", "the repository could not be recorded in the cache"
        ) from exc
    if (home, slug) == (repository.home, repository.slug):
        return repository
    return replace(repository, home=home, slug=slug)


# Active jobs are bounded independently of the set of remembered records. An explicit
# comparison request can upgrade an already-running metadata job without losing the ask.
_PULL_JOBS: set[str] = set()
_COMPARISON_WANTED: set[str] = set()


def _checkout_busy(coordinator: RefreshCoordinator, repository: CheckoutRepository) -> bool:
    """Whether any pull job of this checkout is queued or running."""
    prefix = _job_prefix(repository)
    return any(job.startswith(prefix) and coordinator.running(job) for job in _PULL_JOBS)


def comparison_preparing(
    coordinator: RefreshCoordinator, repository: CheckoutRepository, number: int
) -> bool:
    """An optional comparison job, still unclaimed by a foreground reader."""
    eager = _checkout_state(repository).eager
    return (
        eager is not None
        and eager.number == number
        and eager.mode == "idle"
        and coordinator.running(checkout_job_key(repository, number))
    )


@overload
def start_pull_refresh(
    coordinator: RefreshCoordinator,
    repository: CheckoutRepository,
    number: int,
    *,
    comparison: bool = False,
    eager_revision: None = None,
) -> PullJobStart: ...


@overload
def start_pull_refresh(
    coordinator: RefreshCoordinator,
    repository: CheckoutRepository,
    number: int,
    *,
    comparison: Literal[True],
    eager_revision: str,
) -> PullJobStart | Literal["not_due"]: ...


def start_pull_refresh(
    coordinator: RefreshCoordinator,
    repository: CheckoutRepository,
    number: int,
    *,
    comparison: bool = False,
    eager_revision: str | None = None,
) -> PullJobStart | Literal["not_due"]:
    """Start or join a checkout's pull refresh; only *comparison* may acquire a store.

    With *eager_revision* the start is optional: the comparison of that cached record
    revision, prepared in a store already attached, and only while no other pull job of
    the checkout is queued or running. Anything else is ``not_due``. Every other start is
    a reader's, and ends the optional job: one for the same pull request promotes it, and
    cancels its idle phase when it asks for metadata; one for another cancels it.
    """

    key = checkout_job_key(repository, number)
    state = _checkout_state(repository)
    eager = state.eager
    if eager is not None and not coordinator.running(checkout_job_key(repository, eager.number)):
        state.eager = eager = None
    if eager_revision is not None:
        _PULL_JOBS.intersection_update({job for job in _PULL_JOBS if coordinator.running(job)})
        if (
            eager is not None
            or state.pulls.git_dir is None
            or _checkout_busy(coordinator, repository)
            or state.idle_failures.get(number) == eager_revision
            or len(_PULL_JOBS) >= MAX_PULL_JOBS
        ):
            return "not_due"
        _PULL_JOBS.add(key)
        state.eager = _EagerComparison(number, eager_revision)
        return coordinator.start(
            key, partial(_pull_job, coordinator, repository, number, key), network=False
        )
    if eager is not None:
        if eager.number == number:
            eager.mode = "foreground"
            if not comparison and eager.work is not None:
                # A metadata read with a store also fetches and compares, so the idle
                # phase would only delay it.
                eager.work.cancel()
        else:
            coordinator.cancel(checkout_job_key(repository, eager.number))
            state.eager = None
    if coordinator.running(key):
        if comparison:
            _COMPARISON_WANTED.add(key)
        return "joined"
    _PULL_JOBS.intersection_update({job for job in _PULL_JOBS if coordinator.running(job)})
    if len(_PULL_JOBS) >= MAX_PULL_JOBS:
        return "too_many"
    _PULL_JOBS.add(key)
    if comparison:
        _COMPARISON_WANTED.add(key)
    return coordinator.start(
        key, partial(_pull_job, coordinator, repository, number, key), network=False
    )


async def _acquire_comparison(repository: CheckoutRepository) -> PublishedSource:
    from metabrowser.cache.acquire import (
        AcquisitionError,
        LenderMissingError,
        RemoteAccessError,
        acquire_source,
    )
    from metabrowser.cache.atomic import RecordError
    from metabrowser.cache.identity import SlugCollisionError
    from metabrowser.cache.layout import FutureLayoutFormatError, LayoutError
    from metabrowser.cache.lender import CheckoutRefusedError
    from metabrowser.cache.locks import LockBusyError
    from metabrowser.git.process import GitError
    from metabrowser.home import PrivateStorageError, StorageDirectoryError

    try:
        return await acquire_source(
            repository.git_source,
            home=repository.home,
            checkout=repository.checkout_root,
            allow_clone_fallback=False,
        )
    except (LenderMissingError, CheckoutRefusedError) as exc:
        raise PullDataError("lender_missing", "the checkout cannot supply this comparison") from exc
    except RemoteAccessError as exc:
        state = "not_found_or_private" if exc.state == "not_found_or_private" else "network_error"
        raise PullDataError(state, "the repository could not be read from its origin") from exc
    except GitError as exc:
        raise PullDataError("git_failed", "Git could not prepare this comparison") from exc
    except LockBusyError as exc:
        raise PullDataError(
            "refreshing_elsewhere", "another refresh is preparing the store"
        ) from exc
    except (
        AcquisitionError,
        RecordError,
        SlugCollisionError,
        LayoutError,
        FutureLayoutFormatError,
        PrivateStorageError,
        StorageDirectoryError,
        OSError,
    ) as exc:
        raise PullDataError("fetch_failed", "the comparison store could not be prepared") from exc


async def _keep_comparison_failure(
    companion: ServedPull,
    repository: CheckoutRepository,
    error: PullDataError,
    *,
    expected: PullRecord | RecordAbsence,
) -> None:
    """Keep why a reader's comparison request failed beside the record.

    The page holds its automatic request on it. Only a reader's request records anything:
    a success writes no stamp, which still says how the last metadata read ended, and
    idle work records nothing.
    """
    from metabrowser.builtin_plugins.github import pulls
    from metabrowser.builtin_plugins.github.gh_lists import utc_stamp
    from metabrowser.builtin_plugins.github.pull_record import PullRefreshStamp, write_pull_refresh
    from metabrowser.builtin_plugins.github.served_pull import PullRefreshOutcome
    from metabrowser.cache.locks import run_lock_section
    from metabrowser.home import PrivateStorageError

    at = utc_stamp(pulls.utc_now())
    message = str(error)[:1000]
    try:
        claimed = await claim_source(repository)
        kept = await run_lock_section(
            partial(
                write_pull_refresh,
                claimed.home,
                claimed.slug,
                companion.number,
                PullRefreshStamp(
                    outcome=error.state, message=message, reset_at=error.reset_at, at=at
                ),
                expected=expected,
            )
        )
    except (PullDataError, PrivateStorageError, OSError):
        log.debug("could not record checkout comparison failure", exc_info=True)
    else:
        if not kept:
            return
    companion.outcome_on_disk = False
    companion.last = PullRefreshOutcome(
        outcome=error.state, message=message, reset_at=error.reset_at, at=at
    )


def _adopt(companion: ServedPull, record: PullRecord) -> None:
    from metabrowser.builtin_plugins.github.served_pull import written_without_store

    companion.fetched_at = record.fetched_at
    companion.without_store = written_without_store(record)
    if record.comparison is not None:
        companion.note_comparison((record.comparison.base, record.comparison.head))


def _remember_idle_failure(state: _CheckoutPulls, number: int, revision: str) -> None:
    from metabrowser.builtin_plugins.github.served_pull import MAX_KEPT_PULLS

    state.idle_failures.pop(number, None)
    state.idle_failures[number] = revision
    while len(state.idle_failures) > MAX_KEPT_PULLS:
        state.idle_failures.popitem(last=False)


async def _prepare_idle(
    state: _CheckoutPulls, companion: ServedPull, eager: _EagerComparison
) -> None:
    """Prepare the named revision's comparison in the attached store, or do nothing.

    It fetches only what that comparison needs, the pull request's head and observed base
    when the store lacks them, and records nothing about how it ended. A failure is kept
    in memory only so the same revision is not tried again, and stays quiet until the
    reader's own Changes request.
    """
    from metabrowser.builtin_plugins.github import pulls
    from metabrowser.builtin_plugins.github.served_pull import (
        cached_comparison_record,
        written_without_store,
    )

    published = state.pulls.published
    reader = state.pulls.observed_reader
    if isinstance(published, ListedRepository):
        return
    record = await asyncio.to_thread(
        cached_comparison_record, published, reader, companion.number, eager.revision
    )
    if (
        record is None
        or not written_without_store(record)
        or state.pulls.published is not published
        or state.pulls.observed_reader != reader
    ):
        return
    try:
        prepared = await pulls.prepare_pull_comparison(published, record)
    except pulls.PullObservationSuperseded as exc:
        _adopt(companion, exc.current)
    except PullDataError:
        log.debug("idle comparison of pull request %s failed", companion.number, exc_info=True)
        _remember_idle_failure(state, companion.number, eager.revision)
    else:
        if prepared is not None:
            _adopt(companion, prepared)


async def _idle_phase(
    state: _CheckoutPulls, companion: ServedPull, eager: _EagerComparison
) -> None:
    """Run :func:`_prepare_idle` as a task a reader's metadata request can cancel."""
    work = asyncio.get_running_loop().create_task(_prepare_idle(state, companion, eager))
    eager.work = work
    try:
        await asyncio.wait((work,))
    except asyncio.CancelledError:
        work.cancel()
        await asyncio.wait((work,))
        raise
    finally:
        eager.work = None
    if not work.cancelled():
        work.result()


type _Prepared = Literal["done", "refresh_metadata"]


async def _prepare_foreground(
    state: _CheckoutPulls, repository: CheckoutRepository, companion: ServedPull
) -> _Prepared:
    """Attach a store if there is none, then prepare the comparison from the cached record.

    The cached record serves only while
    :func:`~metabrowser.builtin_plugins.github.served_pull.cached_comparison_record` admits
    it. A stale record, another reader's, or one with a failed refresh since is read from
    GitHub again, as every comparison request was before this layer. A record whose head
    has moved is too.
    """
    from metabrowser.builtin_plugins.github import pulls
    from metabrowser.builtin_plugins.github.pull_record import read_pull_record
    from metabrowser.builtin_plugins.github.served_pull import (
        cached_comparison_record,
        written_without_store,
    )

    if state.pulls.git_dir is None:
        before = await asyncio.to_thread(
            read_pull_record, state.pulls.home, state.pulls.slug, companion.number
        )
        try:
            state.pulls.bind(await _acquire_comparison(repository))
        except PullDataError as exc:
            await _keep_comparison_failure(companion, repository, exc, expected=before)
            return "done"
    published = state.pulls.published
    if isinstance(published, ListedRepository):
        return "refresh_metadata"
    reader = state.pulls.observed_reader
    record = await asyncio.to_thread(cached_comparison_record, published, reader, companion.number)
    if (
        record is None
        or state.pulls.published is not published
        or state.pulls.observed_reader != reader
    ):
        return "refresh_metadata"
    if record.comparison is not None:
        # The request raced an idle job's publication, or another server's.
        return "done"
    try:
        prepared = await pulls.prepare_pull_comparison(published, record)
    except pulls.PullObservationSuperseded as exc:
        _adopt(companion, exc.current)
        return "done" if exc.current.comparison is not None else "refresh_metadata"
    except PullDataError as exc:
        await _keep_comparison_failure(companion, repository, exc, expected=record)
        return "done"
    if prepared is None:
        return "refresh_metadata"
    _adopt(companion, prepared)
    return "refresh_metadata" if written_without_store(prepared) else "done"


async def _run_foreground(
    state: _CheckoutPulls, repository: CheckoutRepository, companion: ServedPull, key: str
) -> None:
    """A reader's own work: the comparison when one was asked for, then any metadata read."""
    while True:
        prepared: _Prepared = "refresh_metadata"
        if key in _COMPARISON_WANTED:
            _COMPARISON_WANTED.discard(key)
            prepared = await _prepare_foreground(state, repository, companion)
        if prepared == "done" and not companion.recovery_pending:
            return
        await companion.refresh()
        if key not in _COMPARISON_WANTED or state.pulls.git_dir is not None:
            return


async def _pull_job(
    coordinator: RefreshCoordinator, repository: CheckoutRepository, number: int, key: str
) -> None:
    state = _checkout_state(repository)
    eager = state.eager if state.eager is not None and state.eager.number == number else None
    try:
        # An idle job starts only on a quiet checkout, so it has the turn at once, and it
        # holds no network slot. Waiting at the store keeps none either. Promotion moves
        # an idle job's place in the store queue without starting another producer.
        async with state.turn(lambda: eager is None or eager.mode == "foreground"):
            companion = await state.pulls.companion(number)
            state.pulls.active = companion
            try:
                if eager is not None and eager.mode == "idle":
                    await _idle_phase(state, companion, eager)
                    if eager.mode == "idle":
                        return
                async with coordinator.slot():
                    await _run_foreground(state, repository, companion, key)
            finally:
                state.pulls.active = None
    finally:
        _COMPARISON_WANTED.discard(key)
        if eager is not None and state.eager is eager:
            state.eager = None


__all__ = [
    "CheckoutRepository",
    "checkout_pulls",
    "checkout_job_key",
    "claim_source",
    "comparison_preparing",
    "ensure_resolved",
    "resolve_served_checkout",
    "served_checkout",
    "start_pull_refresh",
]
