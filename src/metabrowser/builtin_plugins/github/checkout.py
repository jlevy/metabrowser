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
``unattached`` state (:func:`claim_source`). Nothing about the checkout is recorded: no
path, no branch. Nothing is written to it, and no Git runs in it.

What is resolved is remembered for the served root and the application home, so a route
answers from memory after its first request. Resolving reads the checkout's Git pointer
file, configuration, ``HEAD``, and the ref it names, each bounded: measured 2026-11-02 at
a load average near 28, 2.6 to 2.8 ms at the median and 14 ms at the worst of 30 on this
repository's own checkout, a linked worktree, and a subdirectory of it. It runs off the
event loop (:func:`resolve_served_checkout`), once per root.
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from metabrowser.builtin_plugins.github.gh_lists import PullDataError
from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from metabrowser.mirror_refresh import MAX_PULL_JOBS, PullJobStart, mirror_session
from metabrowser.source import get_source_session

if TYPE_CHECKING:
    from metabrowser.builtin_plugins.github.served_pull import ServedPulls
    from metabrowser.cache.urls import GitSource
    from metabrowser.mirror_refresh import RefreshCoordinator

# Roots a process resolves: one server serves one root, and tests serve several.
_MAX_RESOLVED: Final = 8


@dataclass(frozen=True, slots=True)
class CheckoutRepository(ListedRepository):
    """A served checkout's repository: where its records are, and the source to claim.

    It has no store, so a pull request's record is written without a comparison.
    """

    git_source: GitSource


_RESOLVED: dict[tuple[str, str], CheckoutRepository | None] = {}
_PULLS: dict[tuple[str, str], ServedPulls] = {}
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
    from metabrowser.repository_context import discover_repository_context

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
    return CheckoutRepository(home, source_slug(source, home), owner, repo, source)


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


def checkout_pulls(repository: CheckoutRepository) -> ServedPulls:
    """The checkout's pull requests: one set per repository, kept as a mirror's is."""

    from metabrowser.builtin_plugins.github.served_pull import ServedPulls

    key = (str(repository.home), repository.slug)
    with _LOCK:
        held = _PULLS.get(key)
        if held is None:
            if len(_PULLS) >= _MAX_RESOLVED:
                _PULLS.pop(next(iter(_PULLS)))
            held = _PULLS[key] = ServedPulls(repository)
        return held


def claim_source(repository: ListedRepository) -> ListedRepository:
    """*repository*, its source published first when it is a checkout's. Blocking.

    A job calls it before its first write, so a read never creates a source and the first
    write claims one. A source published already, with a store or without, is left as it
    is. Raises :class:`PullDataError` ``cache_unwritable`` when the cache cannot take it.
    """

    if not isinstance(repository, CheckoutRepository):
        return repository
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
    claimed = replace(repository, home=home, slug=slug)
    with _LOCK:
        for key, held in _RESOLVED.items():
            if held == repository:
                _RESOLVED[key] = claimed
    return claimed


# The keys of a checkout's record jobs started, some of which may have ended. Read and
# written only on the event loop.
_PULL_JOBS: set[str] = set()


def start_pull_refresh(
    coordinator: RefreshCoordinator, pulls: ServedPulls, number: int
) -> PullJobStart:
    """Start or join pull request *number*'s refresh on a checkout. Runs on the event loop.

    As on a mirror, at most :data:`MAX_PULL_JOBS` may be queued or running, since the
    numbers are request text; past it a request is refused, ``too_many``. A checkout's job
    reads GitHub and no store, so it takes one of the coordinator's network slots and no
    turn at a store.
    """

    key = pulls.key(number)
    if coordinator.running(key):
        return "joined"
    _PULL_JOBS.intersection_update({job for job in _PULL_JOBS if coordinator.running(job)})
    if len(_PULL_JOBS) >= MAX_PULL_JOBS:
        return "too_many"
    _PULL_JOBS.add(key)
    return coordinator.start(key, partial(_pull_job, pulls, number))


async def _pull_job(pulls: ServedPulls, number: int) -> None:
    companion = await pulls.companion(number)
    await companion.refresh()


__all__ = [
    "CheckoutRepository",
    "checkout_pulls",
    "claim_source",
    "ensure_resolved",
    "resolve_served_checkout",
    "served_checkout",
    "start_pull_refresh",
]
