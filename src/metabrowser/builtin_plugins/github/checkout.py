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
``unattached`` state (:func:`claim_source`). A reader's explicit comparison Fetch may
attach a store that borrows the checkout's objects; its lender path stays internal to the
cache. A healthy existing store is reused without acquisition. Nothing is written to the
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
from dataclasses import dataclass, field, replace
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from metabrowser.builtin_plugins.github.gh_lists import PullDataError
from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from metabrowser.mirror_refresh import MAX_PULL_JOBS, PullJobStart, StoreTurn, mirror_session
from metabrowser.source import get_source_session

if TYPE_CHECKING:
    from metabrowser.builtin_plugins.github.served_pull import ServedPulls
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


@dataclass
class _CheckoutPulls:
    pulls: ServedPulls
    turn: StoreTurn = field(default_factory=StoreTurn)


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
        # A record remains readable without a usable store. An explicit comparison
        # refresh reports the acquisition failure, and may repair a moved lender.
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


def checkout_job_key(repository: CheckoutRepository, number: int) -> str:
    """A stable internal job key while a checkout acquires its store."""

    identity = hashlib.sha256("\0".join(_checkout_key(repository)).encode()).hexdigest()
    return f"checkout:{identity}:pull/{number}"


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


def start_pull_refresh(
    coordinator: RefreshCoordinator,
    repository: CheckoutRepository,
    number: int,
    *,
    comparison: bool = False,
) -> PullJobStart:
    """Start or join a checkout's pull refresh; only *comparison* may acquire a store."""

    key = checkout_job_key(repository, number)
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


async def _pull_job(
    coordinator: RefreshCoordinator, repository: CheckoutRepository, number: int, key: str
) -> None:
    from metabrowser.builtin_plugins.github import pulls
    from metabrowser.builtin_plugins.github.gh_lists import utc_stamp
    from metabrowser.builtin_plugins.github.pull_record import PullRefreshStamp, write_pull_refresh
    from metabrowser.builtin_plugins.github.served_pull import PullRefreshOutcome
    from metabrowser.home import PrivateStorageError

    state = _checkout_state(repository)
    try:
        # Waiting at the store keeps no network slot, matching mirror refresh jobs.
        async with state.turn(lambda: True), coordinator.slot():
            companion = await state.pulls.companion(number)
            state.pulls.active = companion
            try:
                while True:
                    comparison = key in _COMPARISON_WANTED
                    _COMPARISON_WANTED.discard(key)
                    if comparison and state.pulls.git_dir is None:
                        try:
                            published = await _acquire_comparison(repository)
                        except PullDataError as exc:
                            at = utc_stamp(pulls.utc_now())
                            companion.last = PullRefreshOutcome(
                                outcome=exc.state, message=str(exc), reset_at=exc.reset_at, at=at
                            )
                            try:
                                claimed = await claim_source(repository)
                                await asyncio.to_thread(
                                    write_pull_refresh,
                                    claimed.home,
                                    claimed.slug,
                                    number,
                                    PullRefreshStamp(
                                        outcome=exc.state,
                                        message=str(exc),
                                        reset_at=exc.reset_at,
                                        at=at,
                                    ),
                                )
                            except (PullDataError, PrivateStorageError, OSError):
                                log.debug(
                                    "could not record checkout comparison failure", exc_info=True
                                )
                            return
                        state.pulls.bind(published)
                    await companion.refresh()
                    if key not in _COMPARISON_WANTED or state.pulls.git_dir is not None:
                        return
            finally:
                state.pulls.active = None
    finally:
        _COMPARISON_WANTED.discard(key)


__all__ = [
    "CheckoutRepository",
    "checkout_pulls",
    "checkout_job_key",
    "claim_source",
    "ensure_resolved",
    "resolve_served_checkout",
    "served_checkout",
    "start_pull_refresh",
]
