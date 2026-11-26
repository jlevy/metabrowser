"""Which GitHub repository a served checkout's pull requests are of.

A checkout's server has no mirror session, so the pull routes ask this module. The
repository is the one :func:`~metabrowser.repository_context.discover_repository_context`
reads for the working tree, a subdirectory, or a revision the checkout serves.
The reader gets the ``origin`` remote directly from the checkout's files. The plugin's URL
grammar reduces it to
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
import contextlib
import hashlib
import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Final, Literal, overload

from metabrowser import event_log
from metabrowser.builtin_plugins.github.gh_lists import PullDataError, PullDataState
from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from metabrowser.mirror_refresh import MAX_PULL_JOBS, PullJobStart, StoreTurn, mirror_session
from metabrowser.source import get_source_session

if TYPE_CHECKING:
    from collections.abc import Callable

    from metabrowser.builtin_plugins.github.pull_record import PullRecord, RecordAbsence
    from metabrowser.builtin_plugins.github.served_pull import ServedPull, ServedPulls
    from metabrowser.cache.acquire import PublishedSource
    from metabrowser.cache.urls import GitSource
    from metabrowser.mirror_refresh import RefreshAsk, RefreshCoordinator

# Roots a process resolves: one server serves one root, and tests serve several.
_MAX_RESOLVED: Final = 8
log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CheckoutRepository(ListedRepository):
    """A served checkout's repository: where its records are, and the source to claim.

    Before a store is attached, its page withholds any shared comparison.
    """

    checkout: ClassVar[bool] = True
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
    work: asyncio.Task[_IdleFailure | None] | None = None


@dataclass
class _CheckoutPulls:
    pulls: ServedPulls
    # The store's one turn in this server, which core keeps: the folder's own fetch of the
    # store takes it too (``metabrowser/checkout_store.py``).
    turn: StoreTurn
    eager: _EagerComparison | None = None
    # The revision each pull request's idle comparison last failed for, so it is not
    # tried again; as many as the pull states a set holds.
    idle_failures: OrderedDict[int, str] = field(default_factory=OrderedDict[int, str])
    # The keys of background pull jobs not yet promoted; each removes its own.
    background: set[str] = field(default_factory=set[str])


_PULLS: dict[tuple[str, str, str], _CheckoutPulls] = {}
_LOCK: Final = threading.Lock()


def _served_key(app: Any) -> tuple[str, str] | None:
    """The served root and the application home, or ``None`` where no checkout is served."""

    if mirror_session(app) is not None:
        return None
    subject = get_source_session().subject
    root = subject.filesystem_root
    if root is None:
        from metabrowser.checkout_revisions import checkout_revisions

        checkout = checkout_revisions()
        if checkout is None or not checkout.serves(subject):
            return None
        root = checkout.root
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
    """The served checkout's repository, or ``None`` when the subject has no checkout.

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
    from metabrowser.cache.identity import SlugCollisionError, StoreKeyCollisionError
    from metabrowser.cache.layout import FutureLayoutFormatError, LayoutError
    from metabrowser.home import PrivateStorageError, StorageDirectoryError

    try:
        return cached_source(source, home)
    except (
        AcquisitionError,
        RecordError,
        SlugCollisionError,
        StoreKeyCollisionError,
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
    from metabrowser.checkout_store import store_turn

    key = _checkout_key(repository)
    with _LOCK:
        held = _PULLS.get(key)
        if held is None:
            if len(_PULLS) >= _MAX_RESOLVED:
                _PULLS.pop(next(iter(_PULLS)))
            held = _PULLS[key] = _CheckoutPulls(
                ServedPulls(repository.cached or repository),
                store_turn(repository.home, repository.git_source),
            )
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
    from metabrowser.cache.identity import SlugCollisionError, StoreKeyCollisionError
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
        StoreKeyCollisionError,
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
    """Whether a reader's pull job of this checkout is queued or running.

    A background job is not one: it gives way at the checkout's turn, and the optional
    comparison waiting there as a reader's work preempts it (:class:`StoreTurn`).
    """
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


def prefetch_waits_for_acquisition(repository: CheckoutRepository, number: int) -> bool:
    """Whether this background pull job waits for the checkout's first store."""
    state = _checkout_state(repository)
    return state.turn.acquiring and checkout_job_key(repository, number) in state.background


@overload
def start_pull_refresh(
    coordinator: RefreshCoordinator,
    repository: CheckoutRepository,
    number: int,
    ask: RefreshAsk,
    *,
    comparison: bool = False,
    eager_revision: None = None,
    background: Literal[False] = False,
) -> PullJobStart: ...


@overload
def start_pull_refresh(
    coordinator: RefreshCoordinator,
    repository: CheckoutRepository,
    number: int,
    ask: RefreshAsk,
    *,
    comparison: Literal[False] = False,
    eager_revision: None = None,
    background: Literal[True],
) -> PullJobStart | Literal["not_due"]: ...


@overload
def start_pull_refresh(
    coordinator: RefreshCoordinator,
    repository: CheckoutRepository,
    number: int,
    ask: RefreshAsk,
    *,
    comparison: Literal[True],
    eager_revision: str,
    background: Literal[False] = False,
) -> PullJobStart | Literal["not_due"]: ...


def start_pull_refresh(
    coordinator: RefreshCoordinator,
    repository: CheckoutRepository,
    number: int,
    ask: RefreshAsk,
    *,
    comparison: bool = False,
    eager_revision: str | None = None,
    background: bool = False,
) -> PullJobStart | Literal["not_due"]:
    """Start or join a checkout's pull refresh for *ask*; only *comparison* may acquire a store.

    *ask* is why (:data:`~metabrowser.mirror_refresh.RefreshAsk`), which the job is told
    whoever started it (:meth:`~metabrowser.mirror_refresh.RefreshCoordinator.asked`). An
    answer that starts and joins nothing notes none, even while another job of the number
    runs.

    With *eager_revision* the start is optional: the comparison of that cached record
    revision, prepared in a store already attached, and only while no reader's pull job of
    the checkout is queued or running. Anything else is ``not_due``. A background job of
    another pull request does not stop it, and gives way to it at the store; one of the
    same pull request, which fetches and compares, is promoted and joined instead. Every
    other start is a reader's, and ends the optional job: one for the same pull request
    promotes it, and cancels its idle phase when it asks for metadata; one for another
    cancels it while it is still optional, and otherwise leaves the promoted job to run
    on as the reader's it now is.

    A *background* start, a prefetch's, is a metadata refresh that counts toward no bound,
    takes no network slot, and gives way at the checkout's turn (:class:`StoreTurn`); it
    is ``not_due`` while the optional comparison job runs and is still optional, and starts
    beside one a reader's start has promoted, as beside any reader's job. A reader's start
    that joins it promotes it to the reader's, and from then on it counts, and a background
    job holding the turn it waits for is stopped, as on a mirror.

    A reader's start that joins a job already told to stop, a prefetch's that gave way at
    the turn or the optional job another reader's start ended, has the reader's job
    started once that one has unwound (:func:`_start_again_when_stopped`), so ``joined``
    is never an answer for work that is then dropped.
    """

    answer = _start_pull_refresh(
        coordinator,
        repository,
        number,
        ask,
        comparison=comparison,
        eager_revision=eager_revision,
        background=background,
    )
    if answer in ("started", "joined"):
        coordinator.asked(checkout_job_key(repository, number), ask)
    return answer


def _start_pull_refresh(
    coordinator: RefreshCoordinator,
    repository: CheckoutRepository,
    number: int,
    ask: RefreshAsk,
    *,
    comparison: bool,
    eager_revision: str | None,
    background: bool,
) -> PullJobStart | Literal["not_due"]:
    key = checkout_job_key(repository, number)
    state = _checkout_state(repository)
    eager = _live_eager(coordinator, repository, state)
    if eager_revision is not None:
        _PULL_JOBS.intersection_update({job for job in _PULL_JOBS if coordinator.running(job)})
        if key in state.background and coordinator.running(key):
            # The open pull request's own prefetch. With a store its read fetches and
            # compares, so it is promoted to the reader's, which nothing preempts, and
            # which stops a background job holding the turn it waits for.
            state.background.discard(key)
            state.turn.promoted()
            _PULL_JOBS.add(key)
            _start_again_when_stopped(coordinator, repository, number, key, ask)
            return "joined"
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
    if background:
        if coordinator.running(key):
            return "joined"
        if eager is not None and eager.mode == "idle":
            return "not_due"
        state.background.add(key)
        return coordinator.start(
            key, partial(_pull_job, coordinator, repository, number, key), network=False
        )
    return _readers_start(coordinator, repository, number, ask, comparison=comparison, bounded=True)


def _live_eager(
    coordinator: RefreshCoordinator, repository: CheckoutRepository, state: _CheckoutPulls
) -> _EagerComparison | None:
    """The checkout's optional comparison job, forgotten once it has ended."""
    eager = state.eager
    if eager is not None and not coordinator.running(checkout_job_key(repository, eager.number)):
        state.eager = eager = None
    return eager


def _readers_start(
    coordinator: RefreshCoordinator,
    repository: CheckoutRepository,
    number: int,
    ask: RefreshAsk,
    *,
    comparison: bool,
    bounded: bool,
) -> PullJobStart:
    """A reader's start of pull request *number*'s job, or their join of the one running.

    A job joined counts among the reader's jobs from then on, in the place it takes now.
    Only *bounded* starts count against :data:`MAX_PULL_JOBS`: a restart of a job the
    reader joined took its place when they joined it.
    """
    key = checkout_job_key(repository, number)
    state = _checkout_state(repository)
    eager = _live_eager(coordinator, repository, state)
    if eager is not None:
        if eager.number == number:
            eager.mode = "foreground"
            if not comparison and eager.work is not None:
                # A metadata read with a store also fetches and compares, so the idle
                # phase would only delay it.
                eager.work.cancel()
        else:
            # Ended only while it is still optional: once a reader's start promoted it, it
            # is that reader's job, which was answered ``joined``, and it runs on as any
            # reader's does. Either way it is no longer the checkout's optional job.
            if eager.mode == "idle":
                coordinator.cancel(checkout_job_key(repository, eager.number))
            state.eager = None
    if coordinator.running(key):
        # A prefetch's job counts from here, and stops a background job holding the turn
        # it waits for (:meth:`StoreTurn.promoted`). The optional one, the other a reader
        # can find stopping, has counted since it started.
        if key in state.background:
            state.background.discard(key)
            companion = state.pulls.held(number)
            if (
                state.turn.acquiring
                and not comparison
                and companion is not None
                and companion.unattached_selection() is not None
            ):
                # The acquisition holds the turn, so this prefetch has not started its
                # read. Restart it through the reader's path instead of waiting at Git.
                coordinator.cancel(key)
            else:
                state.turn.promoted()
            _PULL_JOBS.add(key)
        if comparison:
            _COMPARISON_WANTED.add(key)
        _start_again_when_stopped(coordinator, repository, number, key, ask)
        return "joined"
    if bounded:
        _PULL_JOBS.intersection_update({job for job in _PULL_JOBS if coordinator.running(job)})
        if len(_PULL_JOBS) >= MAX_PULL_JOBS:
            return "too_many"
    _PULL_JOBS.add(key)
    if comparison:
        _COMPARISON_WANTED.add(key)
    return coordinator.start(
        key, partial(_pull_job, coordinator, repository, number, key), network=False
    )


def _start_again_when_stopped(
    coordinator: RefreshCoordinator,
    repository: CheckoutRepository,
    number: int,
    key: str,
    ask: RefreshAsk,
) -> None:
    """Start the reader's job for *number* once its job, if it was told to stop, has unwound.

    Cancellation is delivered a loop step after it is asked for, so a job a reader joins
    can already be stopping (:meth:`RefreshCoordinator.start_again_when_stopped`). The
    reader's job then starts as their own start would have, in the place it took when
    they joined. A comparison any start that joined asked for is kept for it in
    ``_COMPARISON_WANTED``, which the stopped job leaves as it ends (:func:`_pull_job`).
    """

    def restart() -> None:
        _readers_start(coordinator, repository, number, ask, comparison=False, bounded=False)

    coordinator.start_again_when_stopped(key, restart)


async def _wait_for_cold_open(repository: CheckoutRepository) -> None:
    """Wait out another process's cold open of the checkout's source, holding nothing."""
    from metabrowser.cache.acquire import AcquiringElsewhereError, wait_for_source_reservation
    from metabrowser.cache.locks import LockBusyError
    from metabrowser.home import PrivateStorageError, StorageDirectoryError

    try:
        await wait_for_source_reservation(repository.git_source, home=repository.home)
    except AcquiringElsewhereError as exc:
        raise PullDataError("refreshing_elsewhere", str(exc)) from exc
    except (LockBusyError, PrivateStorageError, StorageDirectoryError, OSError):
        # The acquisition that follows meets the same condition and reports it.
        log.debug("could not wait for another cold open", exc_info=True)


# What a reader's comparison is told for each way core's acquisition of the store fails
# (``metabrowser/checkout_store.py``). ``refreshing_elsewhere`` keeps core's own words,
# which can name the reservation's lock file for a reader to find the holder.
_ACQUISITION_FAILURE: Final[dict[str, str]] = {
    "lender_missing": "the checkout cannot supply this comparison",
    "not_found_or_private": "the repository could not be read from its origin",
    "network_error": "the repository could not be read from its origin",
    "git_failed": "Git could not prepare this comparison",
    "fetch_failed": "the comparison store could not be prepared",
}


async def _acquire_comparison(repository: CheckoutRepository) -> PublishedSource:
    """The checkout's store, acquired by core, which owns it and its turn.

    The store is the one a folder's server lists its origin's branches from, so core
    makes it (:func:`~metabrowser.checkout_store.acquire_checkout_store`) and this only
    words its failures for a comparison. The caller holds the store's turn.
    """
    from metabrowser.checkout_store import CheckoutStoreError, acquire_checkout_store

    try:
        return await acquire_checkout_store(
            repository.git_source, home=repository.home, checkout=repository.checkout_root
        )
    except CheckoutStoreError as exc:
        # A comparison has no state of its own for an acquisition that ran out its
        # deadline, which core tells apart for its timer: it is the Git failure it was.
        state: PullDataState = "git_failed" if exc.code == "timed_out" else exc.code
        raise PullDataError(state, _ACQUISITION_FAILURE.get(state, str(exc))) from exc


async def _keep_comparison_failure(
    companion: ServedPull,
    repository: CheckoutRepository,
    error: PullDataError,
    *,
    expected: PullRecord | RecordAbsence,
) -> None:
    """Keep why a reader's comparison request failed, in memory and beside the record.

    The page holds its automatic request on it. Only a reader's request records anything:
    a success writes no stamp, which still says how the last metadata read ended, and
    idle work records nothing. This server reports the failure whether or not the stamp
    is kept; the stamp is refused when another observation replaced *expected*.
    """
    from metabrowser.builtin_plugins.github import pulls
    from metabrowser.builtin_plugins.github.gh_lists import utc_stamp
    from metabrowser.builtin_plugins.github.pull_record import PullRefreshStamp, write_pull_refresh
    from metabrowser.builtin_plugins.github.served_pull import PullRefreshOutcome
    from metabrowser.cache.locks import run_lock_section
    from metabrowser.home import PrivateStorageError

    at = utc_stamp(pulls.utc_now())
    message = str(error)[:1000]
    companion.outcome_on_disk = False
    companion.last = PullRefreshOutcome(
        outcome=error.state, message=message, reset_at=error.reset_at, at=at
    )
    try:
        claimed = await claim_source(repository)
        await run_lock_section(
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


@dataclass(frozen=True, slots=True)
class _IdleFailure:
    """Why an idle phase prepared nothing, for a reader who promoted it meanwhile.

    *error* is ``None`` when only a reader's request could go on: an uncertain merge base,
    which optional work does not deepen.
    """

    record: PullRecord
    error: PullDataError | None


async def _prepare_idle(
    state: _CheckoutPulls, companion: ServedPull, eager: _EagerComparison
) -> _IdleFailure | None:
    """Prepare the named revision's comparison in the attached store, or do nothing.

    It fetches only what that comparison needs, the pull request's head and observed base
    when the store lacks them, and publishes nothing but a computed comparison: no
    failure, no pending uncertain base, no stamp. A failure is kept in memory only, so
    the same revision is not tried again, and is returned for a reader who promoted the
    job while it ran.
    """
    from metabrowser.builtin_plugins.github import pulls
    from metabrowser.builtin_plugins.github.served_pull import (
        cached_comparison_record,
        written_without_store,
    )

    published = state.pulls.published
    reader = state.pulls.observed_reader
    if isinstance(published, ListedRepository):
        return None
    record = await asyncio.to_thread(
        cached_comparison_record, published, reader, companion.number, eager.revision
    )
    if (
        record is None
        or not written_without_store(record)
        or state.pulls.published is not published
        or state.pulls.observed_reader != reader
    ):
        return None
    try:
        prepared = await pulls.prepare_pull_comparison(published, record, optional=True)
    except pulls.PullObservationSuperseded as exc:
        _adopt(companion, exc.current)
    except pulls.NeedsDeepening:
        _remember_idle_failure(state, companion.number, eager.revision)
        return _IdleFailure(record, None)
    except PullDataError as exc:
        log.debug("idle comparison of pull request %s failed", companion.number, exc_info=True)
        _remember_idle_failure(state, companion.number, eager.revision)
        return _IdleFailure(record, exc)
    else:
        if prepared is not None:
            _adopt(companion, prepared)
    return None


async def _idle_phase(
    state: _CheckoutPulls, companion: ServedPull, eager: _EagerComparison
) -> _IdleFailure | None:
    """Run :func:`_prepare_idle` as a task a reader's metadata request can cancel."""
    work = asyncio.get_running_loop().create_task(
        event_log.job(
            _prepare_idle(state, companion, eager),
            "checkout.prepare_idle",
            attrs={"pull": companion.number},
        )
    )
    eager.work = work
    try:
        await asyncio.wait((work,))
    except asyncio.CancelledError:
        work.cancel()
        await asyncio.wait((work,))
        raise
    finally:
        eager.work = None
    return None if work.cancelled() else work.result()


type _Prepared = Literal["done", "refresh_metadata"]


async def _attach_store(
    coordinator: RefreshCoordinator,
    state: _CheckoutPulls,
    repository: CheckoutRepository,
    companion: ServedPull,
) -> bool:
    """Attach a store for a reader's comparison; ``False`` when that failed, and why is kept.

    Another process's cold open of the same source is waited out first, holding no network
    slot; the acquisition itself holds one.
    """
    from metabrowser.builtin_plugins.github.pull_record import read_pull_record

    try:
        await _wait_for_cold_open(repository)
        async with coordinator.slot():
            state.pulls.bind(await _acquire_comparison(repository))
    except PullDataError as exc:
        # Read after the failure, which may have waited long: the stamp describes the
        # record on disk now.
        current = await asyncio.to_thread(
            read_pull_record, state.pulls.home, state.pulls.slug, companion.number
        )
        await _keep_comparison_failure(companion, repository, exc, expected=current)
        return False
    return True


def checkout_store_turn(
    repository: CheckoutRepository, preempt: Callable[[], object]
) -> contextlib.AbstractAsyncContextManager[None]:
    """The checkout's store turn for background work outside a pull request's job, the
    prefetch's: it goes when no other job waits, and *preempt* is called when one starts
    waiting (:class:`StoreTurn`)."""

    return _checkout_state(repository).turn(lambda: False, background=lambda: True, preempt=preempt)


# How long the prefetch waits for another process's cold open of the checkout's source
# before it leaves the lists to GitHub: a reader's comparison waits the acquisition's own
# bound, but the lane must not stall behind it.
ATTACH_WAIT_S: Final = 30.0


async def attach_store_for_lists(repository: CheckoutRepository) -> PublishedSource | None:
    """The checkout's store, attached now if it has none, for the prefetch to list changed
    files from (:mod:`.pull_prefetch`); ``None`` when it could not be attached, or when no
    store of the checkout's origin is to be kept
    (:func:`~metabrowser.checkout_store.origin_store_wanted`).

    The caller holds the checkout's store turn (:func:`checkout_store_turn`), as a reader's
    comparison does when it attaches the same store (:func:`_attach_store`), so the two
    never bind at once. This one is background work: it holds no network slot, gives up
    after :data:`ATTACH_WAIT_S`, and a failure is only logged, since each list then goes to
    GitHub as it would have, and a reader's comparison reports its own.
    """
    from metabrowser.checkout_store import origin_store_wanted

    if not origin_store_wanted():
        # Nothing a reader asked for: the prefetch neither makes the store nor fetches the
        # pull requests' heads into one a reader's comparison made, and each list goes to
        # GitHub. The reader's comparison is the one thing that still makes the store.
        return None
    state = _checkout_state(repository)
    if state.pulls.git_dir is None:
        try:
            async with asyncio.timeout(ATTACH_WAIT_S):
                await _wait_for_cold_open(repository)
                acquired = await _acquire_comparison(repository)
        except (PullDataError, TimeoutError) as exc:
            log.debug("the prefetch could not attach the checkout's store: %r", exc)
            return None
        # Another attach may have bound one meanwhile; a second bind would drop the
        # previews it kept.
        if state.pulls.git_dir is None:
            state.pulls.bind(acquired)
    published = state.pulls.published
    return None if isinstance(published, ListedRepository) else published


async def _prepare_foreground(
    coordinator: RefreshCoordinator,
    state: _CheckoutPulls,
    repository: CheckoutRepository,
    companion: ServedPull,
) -> _Prepared:
    """Attach a store if there is none, then prepare the comparison from the cached record.

    The cached record serves only while
    :func:`~metabrowser.builtin_plugins.github.served_pull.cached_comparison_record` admits
    it. A stale record, another reader's, or one with a failed refresh since is read from
    GitHub again, as every comparison request was before this layer. A record whose head
    has moved is too.
    """
    from metabrowser.builtin_plugins.github import pulls
    from metabrowser.builtin_plugins.github.served_pull import (
        cached_comparison_record,
        written_without_store,
    )

    if state.pulls.git_dir is None and not await _attach_store(
        coordinator, state, repository, companion
    ):
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
        async with coordinator.slot():
            prepared = await pulls.prepare_pull_comparison(published, record)
    except pulls.PullObservationSuperseded as exc:
        _adopt(companion, exc.current)
        return "done" if exc.current.comparison is not None else "refresh_metadata"
    except PullDataError as exc:
        # A pending uncertain base this request wrote before it failed is the same
        # observation with its comparison changed, which the stamp still describes.
        await _keep_comparison_failure(companion, repository, exc, expected=record)
        return "done"
    if prepared is None:
        return "refresh_metadata"
    _adopt(companion, prepared)
    return "refresh_metadata" if written_without_store(prepared) else "done"


async def _run_foreground(
    coordinator: RefreshCoordinator,
    state: _CheckoutPulls,
    repository: CheckoutRepository,
    companion: ServedPull,
    key: str,
    idle: _IdleFailure | None,
) -> None:
    """A reader's own work: the comparison when one was asked for, then any metadata read.

    Each step takes a network slot only for its own network work. *idle* is how an idle
    phase this reader promoted failed: a failure the reader's comparison would only repeat
    becomes the reader's, and an uncertain base goes on to be deepened.
    """
    while True:
        prepared: _Prepared = "refresh_metadata"
        if key in _COMPARISON_WANTED:
            _COMPARISON_WANTED.discard(key)
            if idle is not None and idle.error is not None:
                await _keep_comparison_failure(
                    companion, repository, idle.error, expected=idle.record
                )
                prepared = "done"
            else:
                prepared = await _prepare_foreground(coordinator, state, repository, companion)
            idle = None
        if prepared == "done" and not companion.recovery_pending:
            return
        # A background refresh takes no network slot; a promoted one is a reader's.
        slot = contextlib.nullcontext() if key in state.background else coordinator.slot()
        async with slot:
            await companion.refresh(coordinator.asks(key))
        if key not in _COMPARISON_WANTED or state.pulls.git_dir is not None:
            return


async def _read_selection_during_acquisition(
    coordinator: RefreshCoordinator, state: _CheckoutPulls, number: int, key: str
) -> bool:
    """Prioritize one provider slot for selected metadata that needs no Git store."""

    if not state.turn.acquiring or key in _COMPARISON_WANTED:
        return False
    companion = state.pulls.held(number)
    if companion is None or companion.unattached_selection() is None:
        return False
    async with coordinator.selected_slot():
        # A companion can be evicted while a job waits for this slot.
        companion = state.pulls.held(number)
        if companion is None:
            return False
        publication = companion.unattached_selection()
        if publication is None or key in _COMPARISON_WANTED:
            return False
        with state.turn.read_during_acquisition() as admitted:
            if not admitted:
                return False
            await companion.refresh(coordinator.asks(key), unattached=publication)
    return key not in _COMPARISON_WANTED and not companion.recovery_pending


async def _pull_job(
    coordinator: RefreshCoordinator, repository: CheckoutRepository, number: int, key: str
) -> None:
    state = _checkout_state(repository)
    eager = state.eager if state.eager is not None and state.eager.number == number else None
    try:
        if (
            eager is None
            and key not in state.background
            and await _read_selection_during_acquisition(coordinator, state, number, key)
        ):
            return
        # An idle job starts only when no reader's job runs, so it has the turn at once or
        # once a background holder unwinds, and it holds no network slot. Waiting at the
        # store keeps none either. Promotion moves an idle job's place in the store queue
        # without starting another producer. A background job gives way to any other,
        # an idle one included, and is cancelled when one waits.
        async with state.turn(
            lambda: eager is None or eager.mode == "foreground",
            background=lambda: key in state.background,
            preempt=partial(coordinator.cancel, key),
        ):
            companion = await state.pulls.companion(number)
            state.pulls.active = companion
            try:
                idle = None
                if eager is not None and eager.mode == "idle":
                    idle = await _idle_phase(state, companion, eager)
                    if eager.mode == "idle":
                        return
                await _run_foreground(coordinator, state, repository, companion, key, idle)
            finally:
                state.pulls.active = None
    finally:
        # A comparison a reader asked for after the job was told to stop is the restart's.
        if not coordinator.restarting(key):
            _COMPARISON_WANTED.discard(key)
        state.background.discard(key)
        if eager is not None and state.eager is eager:
            state.eager = None


__all__ = [
    "CheckoutRepository",
    "attach_store_for_lists",
    "checkout_store_turn",
    "checkout_pulls",
    "checkout_job_key",
    "claim_source",
    "comparison_preparing",
    "prefetch_waits_for_acquisition",
    "ensure_resolved",
    "resolve_served_checkout",
    "served_checkout",
    "start_pull_refresh",
]
