"""Refresh a published store from its origin with one plain fetch.

A store is a read-only mirror, so updating it is what ``git fetch`` already does:
observe which branch the origin's HEAD names, then fetch every branch and tag with
``--prune --atomic``. Every ref moves together or none does, a branch or tag deleted
upstream leaves the mirror, and no object is ever removed, so a commit a reader has
pinned stays readable after a force-push or a deleted branch.

Locks follow ``tests/fixtures/repository-cache/state-machines.json`` (``store_refresh``):

- the network work holds no hierarchy lock;
- the store's fetch side lock, ``cache/locks/stores/<store-key>.fetch.lock``, is tried
  without blocking and held across the fetch. Busy means another process is refreshing
  the store now, which is an outcome rather than a wait;
- under that side lock, lock files and temporary packs a killed Git left in the store
  are removed before fetching, because every writer of the store holds the side lock;
- only rewriting ``state.yml`` takes the store lock, briefly, in a worker thread.

Every failure is a typed :class:`RefreshOutcome`; nothing here raises into a caller for
something the origin or the network did. The origin is named by the URL its source was
acquired from, and :mod:`metabrowser.cache.origin` builds both commands for it: the
protocol allowlist, the stall bound, and the ``gh`` credential helper for github.com.
An https origin that does not answer ``ls-remote`` within the first-request deadline
times out, and a failure Git's text names is reported by that name.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from metabrowser.cache.atomic import RecordError, read_record, write_record_atomic
from metabrowser.cache.locks import (
    CacheLock,
    LockBusyError,
    LockOrder,
    LockWaitAbandonedError,
    lock_order,
    repository_store_lock,
    require_no_hierarchy_locks,
    run_lock_section,
    store_fetch_lock,
)
from metabrowser.cache.origin import (
    REMOTE_PROBE_TIMEOUT_S,
    OriginHeadError,
    classify_remote_failure,
    fetched_ref_names,
    ls_remote_head_args,
    mirror_fetch_args,
    parse_symref_head,
    remote_tracking_ref,
)
from metabrowser.cache.paths import store_directory, store_record
from metabrowser.cache.records import (
    REPOSITORY_STORE_STATE_CONTRACT_ID,
    RepositoryStoreState,
    StoreOperation,
    canonical_now,
)
from metabrowser.cache.resolve import case_colliding_refs, ref_tip, store_ignores_case
from metabrowser.git.process import (
    ACQUISITION_POLICY,
    GitCommandError,
    GitError,
    GitTimeoutError,
    GitUnavailableError,
    RepositoryStoreTarget,
    UnsupportedGitVersionError,
    failure_detail,
    repository_store_target,
    require_acquisition_git,
    run_git,
)
from metabrowser.home import PrivateStorageError

log = logging.getLogger(__name__)

# What a killed Git can leave in a store it was fetching into. Ref transactions lock
# with ``<ref>.lock`` beside each loose ref and ``packed-refs.lock``; ``index-pack``
# streams into ``objects/pack/tmp_pack_*`` and ``tmp_idx_*`` before it renames them.
# Neither kind of file is part of the repository: a lock file only blocks the next
# fetch, and a temporary pack holds no object Git can see.
_STALE_REF_LOCK_SUFFIX: Final = ".lock"
_TEMPORARY_PACK_PREFIXES: Final = ("tmp_pack_", "tmp_idx_", "tmp_rev_")


class RefreshOutcome(StrEnum):
    """How one refresh of a store ended."""

    succeeded = "succeeded"
    # Another holder has the store's fetch lock; it is refreshing the store now.
    refreshing_elsewhere = "refreshing_elsewhere"
    # ls-remote could not read the origin, for a reason Git's text does not name.
    origin_unavailable = "origin_unavailable"
    # The fetch itself failed, for a reason Git's text does not name. No ref moved.
    fetch_failed = "fetch_failed"
    # Named failures, as ``cache/origin.py`` classifies Git's text. No ref moved.
    not_found_or_private = "not_found_or_private"
    network_unreachable = "network_unreachable"
    connection_interrupted = "connection_interrupted"
    tls_failed = "tls_failed"
    timed_out = "timed_out"
    server_error = "server_error"
    rate_limited = "rate_limited"
    proxy_auth_required = "proxy_auth_required"
    # The origin has refs that differ only in letter case, which this store's
    # case-insensitive filesystem cannot hold apart. No ref moved.
    ref_case_collision = "ref_case_collision"
    # The origin's HEAD is not a branch, or its branch did not arrive as a commit.
    validation_failed = "validation_failed"
    # The installed Git is below the acquisition floor, so nothing was fetched.
    unsupported_git = "unsupported_git"
    # The store directory is missing or unreadable.
    store_unavailable = "store_unavailable"
    # The server stopped the refresh before it finished.
    cancelled = "cancelled"
    # Anything else, logged with its cause.
    failed = "failed"


# Outcomes a refresh records in ``state.yml``. The others describe why no fetch ran
# here, which is a fact about this process, not about the store.
_RECORDED_FAILURES: Final = frozenset(
    {
        RefreshOutcome.origin_unavailable,
        RefreshOutcome.fetch_failed,
        RefreshOutcome.validation_failed,
        RefreshOutcome.not_found_or_private,
        RefreshOutcome.network_unreachable,
        RefreshOutcome.connection_interrupted,
        RefreshOutcome.tls_failed,
        RefreshOutcome.timed_out,
        RefreshOutcome.server_error,
        RefreshOutcome.rate_limited,
        RefreshOutcome.proxy_auth_required,
        RefreshOutcome.ref_case_collision,
    }
)


@dataclass(frozen=True, slots=True)
class StoreUpdate:
    """One refresh's outcome, when it ended, and the default branch it observed.

    ``default_remote_ref`` and ``default_revision`` are set only when the refresh
    succeeded; ``at`` is also the new last-fetch time then.
    """

    outcome: RefreshOutcome
    at: str
    default_remote_ref: str | None = None
    default_revision: str | None = None


def remove_interrupted_fetch_leftovers(git_dir: Path) -> tuple[str, ...]:
    """Remove the lock files and temporary packs a killed fetch left in *git_dir*.

    Only safe while holding the store's fetch lock: every writer of a published store
    holds it, so no live Git owns any of these files. Returns the removed paths,
    relative to *git_dir*, for logs and tests. Blocking; callers use a worker thread.
    """

    removed: list[str] = []

    def remove(path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            return
        removed.append(path.relative_to(git_dir).as_posix())

    remove(git_dir / "packed-refs.lock")
    refs = git_dir / "refs"
    for directory, _subdirectories, files in os.walk(refs, followlinks=False):
        for name in files:
            if name.endswith(_STALE_REF_LOCK_SUFFIX):
                remove(Path(directory) / name)
    pack_directory = git_dir / "objects" / "pack"
    try:
        entries = list(os.scandir(pack_directory))
    except FileNotFoundError:
        entries = []
    for entry in entries:
        if entry.name.startswith(_TEMPORARY_PACK_PREFIXES) and entry.is_file(follow_symlinks=False):
            remove(Path(entry.path))
    return tuple(sorted(removed))


def _claim_fetch_lock(home: Path, store_key: str, owner: LockOrder) -> CacheLock:
    """Try the fetch lock in a worker thread, recording it for the awaiting thread."""

    return store_fetch_lock(home, store_key, order=owner)


def _release(lock: CacheLock) -> None:
    lock.release()


def _named(exc: GitError, remote_url: str, fallback: RefreshOutcome) -> RefreshOutcome:
    """The outcome Git's error text names for an https origin, else *fallback*.

    Only https: a ``file://`` failure's text names local paths, which could match.
    """

    if not remote_url.startswith("https://"):
        return fallback
    if isinstance(exc, GitTimeoutError):
        return RefreshOutcome.timed_out
    if isinstance(exc, GitCommandError):
        state = classify_remote_failure(exc.stderr_summary)
        if state is not None and state != "too_large":
            return RefreshOutcome(state)
    return fallback


async def _fetch(target: RepositoryStoreTarget, remote_url: str) -> StoreUpdate:
    """Observe the origin's HEAD, fetch, and read the default branch back from the mirror."""

    require_no_hierarchy_locks("a store refresh")
    probe_timeout_s = REMOTE_PROBE_TIMEOUT_S if remote_url.startswith("https://") else None
    try:
        observed = await run_git(
            ls_remote_head_args(remote_url),
            target=target,
            policy=ACQUISITION_POLICY,
            timeout_s=probe_timeout_s,
        )
        head_ref, _advertised = parse_symref_head(observed)
    except GitError as exc:
        log.info("refresh could not read the origin: %s", _detail(exc))
        outcome = _named(exc, remote_url, RefreshOutcome.origin_unavailable)
        return StoreUpdate(outcome, canonical_now())
    except OriginHeadError as exc:
        log.info("refresh could not read the origin: %s", _detail(exc))
        return StoreUpdate(RefreshOutcome.origin_unavailable, canonical_now())
    default_remote_ref = remote_tracking_ref(head_ref)
    if default_remote_ref is None:
        log.info("refresh refused an origin whose HEAD is not a branch")
        return StoreUpdate(RefreshOutcome.validation_failed, canonical_now())
    try:
        updated = await run_git(
            mirror_fetch_args(remote_url, prune=True), target=target, policy=ACQUISITION_POLICY
        )
    except GitError as exc:
        log.info("refresh fetch failed: %s", failure_detail(exc))
        # An atomic fetch of two refs a case-insensitive filesystem holds as one loose
        # file fails to lock the second; measured on macOS with Git 2.50.1.
        if (
            isinstance(exc, GitCommandError)
            and "cannot lock ref" in exc.stderr_summary
            and await store_ignores_case(target)
        ):
            return StoreUpdate(RefreshOutcome.ref_case_collision, canonical_now())
        return StoreUpdate(_named(exc, remote_url, RefreshOutcome.fetch_failed), canonical_now())
    if case_colliding_refs(fetched_ref_names(updated)) and await store_ignores_case(target):
        log.warning("refresh fetched refs that differ only in letter case")
        return StoreUpdate(RefreshOutcome.ref_case_collision, canonical_now())
    # The fetched ref, not the advertised object ID: the origin may have moved between
    # the two commands, and the mirror now holds whatever the fetch saw.
    revision = await ref_tip(target, default_remote_ref)
    if revision is None:
        log.info("refresh did not find the origin's default branch as a commit")
        return StoreUpdate(RefreshOutcome.validation_failed, canonical_now())
    return StoreUpdate(
        RefreshOutcome.succeeded,
        canonical_now(),
        default_remote_ref=default_remote_ref,
        default_revision=revision,
    )


def _detail(exc: Exception) -> str:
    return failure_detail(exc) if isinstance(exc, GitError) else str(exc)


def _record(home: Path, store_key: str, update: StoreUpdate) -> None:
    """Rewrite ``state.yml`` under the store lock; synchronous and blocking.

    A success records the default branch, its commit, and the fetch time. A recorded
    failure keeps all three and replaces only the last operation.
    """

    relative = store_record(store_key, "state.yml")
    with repository_store_lock(home, store_key):
        previous = read_record(home, relative, REPOSITORY_STORE_STATE_CONTRACT_ID)
        if not isinstance(previous, RepositoryStoreState):
            raise RecordError("state.yml did not validate", home / relative)
        succeeded = update.outcome is RefreshOutcome.succeeded
        operation = StoreOperation(
            kind="refresh", outcome="succeeded" if succeeded else "failed", at=update.at
        )
        state = RepositoryStoreState(
            default_remote_ref=(
                update.default_remote_ref if succeeded else previous.default_remote_ref
            ),
            default_revision=update.default_revision if succeeded else previous.default_revision,
            last_fetch_at=update.at if succeeded else previous.last_fetch_at,
            last_operation=operation,
        )
        write_record_atomic(home, relative, state, REPOSITORY_STORE_STATE_CONTRACT_ID)


async def update_store(home: Path, store_key: str, *, remote_url: str) -> StoreUpdate:
    """Refresh the published store *store_key* under *home* from *remote_url*.

    *remote_url* is where the store's source is fetched from: its normalized URL, as
    :func:`~metabrowser.cache.acquire.remote_url_for` says, which also decides the
    credential helper.

    Returns a :class:`StoreUpdate` for every outcome the origin, the network, the
    installed Git, or another process can cause. Cancellation propagates after Git's
    process group is killed and the fetch lock is released; the atomic fetch leaves
    every ref as it was or wholly updated, and ``state.yml`` untouched.
    """

    try:
        require_acquisition_git()
    except UnsupportedGitVersionError as exc:
        log.info("refresh skipped: %s", exc)
        return StoreUpdate(RefreshOutcome.unsupported_git, canonical_now())
    try:
        target = repository_store_target(
            git_dir=home / store_directory(store_key) / "repository.git"
        )
    except GitUnavailableError as exc:
        log.info("refresh skipped: %s", exc)
        return StoreUpdate(RefreshOutcome.store_unavailable, canonical_now())
    try:
        fetch_lock = await run_lock_section(
            functools.partial(_claim_fetch_lock, home, store_key, lock_order()),
            release=_release,
        )
    except LockBusyError:
        return StoreUpdate(RefreshOutcome.refreshing_elsewhere, canonical_now())
    except (PrivateStorageError, OSError) as exc:
        log.warning("refresh could not take the store's fetch lock: %s", exc)
        return StoreUpdate(RefreshOutcome.store_unavailable, canonical_now())
    try:
        removed = await asyncio.to_thread(remove_interrupted_fetch_leftovers, target.git_dir)
        if removed:
            log.info("removed files an interrupted fetch left in a store: %s", ", ".join(removed))
        update = await _fetch(target, remote_url)
        if update.outcome is RefreshOutcome.succeeded or update.outcome in _RECORDED_FAILURES:
            try:
                await run_lock_section(functools.partial(_record, home, store_key, update))
            except (PrivateStorageError, RecordError, OSError, LockWaitAbandonedError) as exc:
                # The refs already moved, or nothing did; the record only trails them,
                # and the next refresh rewrites it.
                log.warning("refresh could not record its outcome in state.yml: %s", exc)
        return update
    finally:
        # Closing the descriptor is the release; it does not wait on anything.
        fetch_lock.release()


__all__ = [
    "RefreshOutcome",
    "StoreUpdate",
    "remove_interrupted_fetch_leftovers",
    "update_store",
]
