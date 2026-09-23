"""Live revision leases over a published worktree-free store.

A leased subject holds the store's shared maintenance lock so reclamation and
``gc`` wait, and a durable private ref so the pinned commit stays reachable
after the process exits. ``maintain_store`` runs ``gc`` and ``repack`` under
the exclusive maintenance lock, never under the store lock. This module does
not serve content, migrate remaining routes, or check out a worktree.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Self

from metabrowser.cache.locks import (
    CacheLock,
    acquire_store_lease,
    repository_store_lock,
    require_no_hierarchy_locks,
    store_maintenance_lock,
)
from metabrowser.cache.paths import store_directory
from metabrowser.git.process import (
    ACQUISITION_POLICY,
    STORE_READ_POLICY,
    GitCommandError,
    GitUnavailableError,
    RepositoryStoreTarget,
    repository_store_target,
    run_git,
    run_git_blocking,
)
from metabrowser.git.tree_source import GitObjectUnavailableError, require_full_oid

_MAILMAP_ARGS: Final[tuple[str, ...]] = ("-c", "mailmap.blob=", "-c", "mailmap.file=")
SUBJECT_REF_PREFIX: Final = "refs/metabrowser/subjects/"


def subject_revision_ref(commit_oid: str) -> str:
    """Private reachability ref for one pinned full commit OID."""

    return f"{SUBJECT_REF_PREFIX}{require_full_oid(commit_oid)}"


@dataclass(frozen=True, slots=True)
class RevisionLease:
    """Shared store lease plus the durable ref that names the pinned commit."""

    home: Path
    store_key: str
    commit_oid: str
    target: RepositoryStoreTarget
    ref_name: str
    _lock: CacheLock

    def release(self) -> None:
        self._lock.release()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> None:
        self.release()


async def _require_commit(target: RepositoryStoreTarget, oid: str) -> None:
    try:
        kind = (
            await run_git(
                [*_MAILMAP_ARGS, "cat-file", "-t", oid],
                target=target,
                policy=STORE_READ_POLICY,
            )
        ).strip()
    except GitCommandError as exc:
        raise GitObjectUnavailableError(oid) from exc
    if kind != b"commit":
        raise GitObjectUnavailableError(oid)


def _write_subject_ref(
    home: Path, store_key: str, target: RepositoryStoreTarget, ref: str, oid: str
) -> None:
    """Write the durable subject ref under the store lock, in one thread.

    The frozen ``revision_subject_lease`` machine writes this ref holding the store
    lock and the lease. That lock belongs to the thread that took it: its ``flock``
    blocks the thread, and the order check reads the thread's held locks. Spanning an
    ``await`` would put two logical holders on one thread, so a second concurrent
    ``lease_revision`` looked like the first re-entering the rank out of order, and the
    blocking ``flock`` stalled the loop for as long as another process held it.
    """

    with repository_store_lock(home, store_key):
        run_git_blocking(
            [*_MAILMAP_ARGS, "update-ref", "--no-deref", ref, oid],
            target=target,
            policy=ACQUISITION_POLICY,
        )


async def _publish_subject_ref(
    home: Path, store_key: str, target: RepositoryStoreTarget, oid: str
) -> str:
    ref = subject_revision_ref(oid)
    await asyncio.to_thread(_write_subject_ref, home, store_key, target, ref, oid)
    return ref


async def lease_revision(*, home: Path, store_key: str, commit_oid: str) -> RevisionLease:
    """Hold the store lease and pin *commit_oid* with a durable private ref.

    The flock is released on :meth:`RevisionLease.release`. The ref remains so
    Git can still reach the commit when no process is running.

    The lease belongs to the calling thread, which for a coroutine is the event-loop
    thread that keeps and releases it; see :func:`acquire_store_lease`. Only its wait
    leaves the loop, so a maintenance holder in another process running ``gc`` or
    ``repack`` delays this coroutine without stalling the others on the loop.
    """

    oid = require_full_oid(commit_oid)
    git_dir = home / store_directory(store_key) / "repository.git"
    if not git_dir.is_dir():
        raise GitUnavailableError(f"repository store is not a directory: {git_dir}")
    lock = await acquire_store_lease(home, store_key)
    try:
        if not git_dir.is_dir():
            raise GitUnavailableError(f"repository store is not a directory: {git_dir}")
        target = repository_store_target(git_dir=git_dir)
        await _require_commit(target, oid)
        ref = await _publish_subject_ref(home, store_key, target, oid)
        lease = RevisionLease(
            home=home,
            store_key=store_key,
            commit_oid=oid,
            target=target,
            ref_name=ref,
            _lock=lock,
        )
        lock = None
        return lease
    finally:
        if lock is not None and lock.held:
            lock.release()


async def maintain_store(*, home: Path, store_key: str) -> None:
    """Run ``gc`` and ``repack`` under the exclusive maintenance lock.

    The exclusive form never blocks. A live shared lease makes this busy
    (or a same-thread ``LockOrderError``). Hierarchy locks, including the
    store lock, are refused first. Durable subject refs stay; this does
    not delete them or create a checkout.
    """

    require_no_hierarchy_locks("gc")
    git_dir = home / store_directory(store_key) / "repository.git"
    if not git_dir.is_dir():
        raise GitUnavailableError(f"repository store is not a directory: {git_dir}")
    maintenance = store_maintenance_lock(home, store_key)
    try:
        if not git_dir.is_dir():
            raise GitUnavailableError(f"repository store is not a directory: {git_dir}")
        target = repository_store_target(git_dir=git_dir)
        await run_git(
            [*_MAILMAP_ARGS, "gc", "--prune=now"],
            target=target,
            policy=ACQUISITION_POLICY,
        )
        await run_git(
            [*_MAILMAP_ARGS, "repack", "-a", "-d"],
            target=target,
            policy=ACQUISITION_POLICY,
        )
    finally:
        if maintenance.held:
            maintenance.release()


__all__ = [
    "SUBJECT_REF_PREFIX",
    "RevisionLease",
    "lease_revision",
    "maintain_store",
    "subject_revision_ref",
]
