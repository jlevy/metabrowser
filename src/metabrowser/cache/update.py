"""Refresh a published store from its origin with one plain fetch.

A store is a read-only mirror, so updating it is what ``git fetch`` already does:
observe which branch the origin's HEAD names, then fetch every branch and tag with
``--prune --atomic``. Every ref moves together or none does, a branch or tag deleted
upstream leaves the mirror, and no object is ever removed, so a commit a reader has
pinned stays readable after a force-push or a deleted branch. One atomic transaction
cannot delete ``side`` and create ``side/x``, or on a case-insensitive file system
rename ``Topic`` to ``topic``. Git words that refusal differently for loose refs,
packed refs, and reftable, and a long fetch can push it past the bounded stderr, so
any failure of the atomic fetch is followed by pruning the stale refs on their own and
one more try; a failure that was not a clash costs one more round trip. On a
case-insensitive file system Git can also succeed wrongly, writing ``SAME`` into the
loose file of an unchanged ``same``; there the refs are listed before the fetch and
checked after it, and a fold, or a clash the retry still meets, puts every ref back
and is reported as ``ref_case_collision``.

Locks follow ``tests/fixtures/repository-cache/state-machines.json`` (``store_refresh``):

- the network work holds no hierarchy lock;
- the store's fetch side lock, ``cache/locks/stores/<store-key>.fetch.lock``, is tried
  without blocking and held across the fetch. The Git processes that write the store
  inherit its descriptor, so the lock stays held for as long as any of them runs, even
  if this process dies first. Busy therefore means a live refresh, here or elsewhere,
  which is an outcome rather than a wait;
- under that side lock, lock files and temporary objects a killed Git left in the store
  are removed before fetching, because no live writer can own them;
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
import contextlib
import functools
import logging
import os
import re
from collections.abc import Awaitable
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
    fetched_refs,
    ls_remote_head_args,
    mirror_fetch_args,
    mirror_prune_args,
    parse_symref_head,
    pruned_ref_names,
    remote_tracking_ref,
)
from metabrowser.cache.paths import store_directory, store_record
from metabrowser.cache.records import (
    REPOSITORY_STORE_STATE_CONTRACT_ID,
    RecordedOutcome,
    RepositoryStoreState,
    StoreOperation,
    canonical_now,
)
from metabrowser.cache.resolve import folded_refs, mirror_refs, ref_tip, store_ignores_case
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
# ``unpack-objects`` writes a small fetch as loose ``objects/??/tmp_obj_*`` files first.
# None of these files is part of the repository: a lock file only blocks the next
# fetch, and a temporary object or pack holds nothing Git can see.
_STALE_REF_LOCK_SUFFIX: Final = ".lock"
_TEMPORARY_PACK_PREFIXES: Final = ("tmp_pack_", "tmp_idx_", "tmp_rev_")
_TEMPORARY_OBJECT_PREFIX: Final = "tmp_obj_"
_LOOSE_OBJECT_DIRECTORY: Final = re.compile(r"[0-9a-f]{2}")
# How Git refuses a ref transaction whose lock it cannot take, in the loose-ref files
# backend under LC_ALL=C. Only used to tell a case collision from other failures on a
# case-insensitive store, whose refs are loose files; any failure is retried after a prune.
_REF_LOCK_CONFLICT: Final = re.compile(r"cannot lock ref")


class RefreshOutcome(StrEnum):
    """How one refresh of a store ended."""

    succeeded = "succeeded"
    # The fetch succeeded, but the origin's HEAD names no branch, so the default
    # branch recorded before is kept.
    default_branch_unknown = "default_branch_unknown"
    # Another holder has the store's fetch lock; it is refreshing the store now.
    refreshing_elsewhere = "refreshing_elsewhere"
    # ls-remote could not read the origin, for a reason Git's text does not name.
    origin_unavailable = "origin_unavailable"
    # The fetch itself failed, for a reason Git's text does not name. No ref moved except
    # stale refs pruned before a second try, and then the record keeps a default branch
    # the mirror still has.
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
    # case-insensitive filesystem cannot hold apart, even after pruning. No ref moved.
    ref_case_collision = "ref_case_collision"
    # The origin's default branch did not arrive as a commit.
    validation_failed = "validation_failed"
    # The installed Git is below the acquisition floor, so nothing was fetched.
    unsupported_git = "unsupported_git"
    # The store directory is missing or unreadable.
    store_unavailable = "store_unavailable"
    # The server stopped the refresh before it finished.
    cancelled = "cancelled"
    # Anything else, logged with its cause.
    failed = "failed"


# Outcomes a refresh records in ``state.yml``, by name, so a later start reports the
# same outcome. The others describe why no fetch ran here, which is a fact about this
# process, not about the store.
_FETCHED: Final = frozenset({RefreshOutcome.succeeded, RefreshOutcome.default_branch_unknown})
_RECORDED: Final[dict[RefreshOutcome, RecordedOutcome]] = {
    RefreshOutcome.succeeded: "succeeded",
    RefreshOutcome.default_branch_unknown: "default_branch_unknown",
    RefreshOutcome.origin_unavailable: "origin_unavailable",
    RefreshOutcome.fetch_failed: "fetch_failed",
    RefreshOutcome.validation_failed: "validation_failed",
    RefreshOutcome.not_found_or_private: "not_found_or_private",
    RefreshOutcome.network_unreachable: "network_unreachable",
    RefreshOutcome.connection_interrupted: "connection_interrupted",
    RefreshOutcome.tls_failed: "tls_failed",
    RefreshOutcome.timed_out: "timed_out",
    RefreshOutcome.server_error: "server_error",
    RefreshOutcome.rate_limited: "rate_limited",
    RefreshOutcome.proxy_auth_required: "proxy_auth_required",
    RefreshOutcome.ref_case_collision: "ref_case_collision",
}


@dataclass(frozen=True, slots=True)
class StoreUpdate:
    """One refresh's outcome, when it ended, and the default branch it observed.

    ``default_remote_ref`` and ``default_revision`` are set when the refresh fetched,
    and ``at`` is also the new last-fetch time then. They are also set by a failed
    fetch after a prune deleted refs, because the record must then name what is left.
    ``unrestored`` names refs a case fold moved that could not be put back; the outcome
    is then ``ref_case_collision`` and the recorded tip does not move.
    """

    outcome: RefreshOutcome
    at: str
    default_remote_ref: str | None = None
    default_revision: str | None = None
    unrestored: tuple[str, ...] = ()


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
    for entry in _entries(git_dir / "objects" / "pack"):
        if entry.name.startswith(_TEMPORARY_PACK_PREFIXES) and entry.is_file(follow_symlinks=False):
            remove(Path(entry.path))
    for directory in _entries(git_dir / "objects"):
        if not _LOOSE_OBJECT_DIRECTORY.fullmatch(directory.name):
            continue
        for entry in _entries(Path(directory.path)):
            if entry.name.startswith(_TEMPORARY_OBJECT_PREFIX) and entry.is_file(
                follow_symlinks=False
            ):
                remove(Path(entry.path))
    return tuple(sorted(removed))


def _entries(directory: Path) -> list[os.DirEntry[str]]:
    try:
        return list(os.scandir(directory))
    except (FileNotFoundError, NotADirectoryError):
        return []


def _claim_fetch_lock(home: Path, store_key: str, owner: LockOrder) -> CacheLock:
    """Try the fetch lock in a worker thread, recording it for the awaiting thread."""

    return store_fetch_lock(home, store_key, order=owner)


def _release(lock: CacheLock) -> None:
    lock.release()


class _FetchFailedError(Exception):
    """The atomic fetch failed; ``pruned`` says whether a prune ran, even in part, first."""

    def __init__(self, cause: GitError, *, pruned: bool) -> None:
        super().__init__(str(cause))
        self.cause = cause
        self.pruned = pruned


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


@dataclass(frozen=True, slots=True)
class _Fetched:
    """The ``--porcelain`` output of the fetch that landed, and the refs before it ran.

    ``baseline`` is *before* as given, or the store's refs after a prune when the
    first fetch failed and the prune ran; ``None`` when no listing was asked for.
    """

    porcelain: bytes
    baseline: dict[str, str] | None


async def _fetch_atomically(
    target: RepositoryStoreTarget,
    remote_url: str,
    lock_fd: int,
    before: dict[str, str] | None,
) -> _Fetched:
    """Fetch every branch and tag in one transaction, pruning separately and retrying once.

    Raises :class:`_FetchFailedError` when the fetch fails after the one retry, or when
    the prune itself fails. With *before*, the refs listed before the fetch, the result
    says what the store held just before the fetch that landed.
    """

    fetch = mirror_fetch_args(remote_url, prune=True)
    try:
        porcelain = await run_git(
            fetch, target=target, policy=ACQUISITION_POLICY, pass_fds=(lock_fd,)
        )
        return _Fetched(porcelain, before)
    except GitCommandError as exc:
        log.debug("the atomic fetch failed; pruning stale refs, then once more: %s", _detail(exc))
    except GitError as exc:
        raise _FetchFailedError(exc, pruned=False) from exc
    try:
        # Deletions only, so nothing in it can clash; then the transaction runs again.
        await run_git(
            mirror_prune_args(remote_url),
            target=target,
            policy=ACQUISITION_POLICY,
            pass_fds=(lock_fd,),
        )
    except GitError as exc:
        # A prune deletes one ref at a time, so a failed one may have deleted some.
        raise _FetchFailedError(exc, pruned=True) from exc
    try:
        # The prune deleted refs the retry's porcelain does not list.
        baseline = await mirror_refs(target) if before is not None else None
        porcelain = await run_git(
            fetch, target=target, policy=ACQUISITION_POLICY, pass_fds=(lock_fd,)
        )
    except GitError as exc:
        raise _FetchFailedError(exc, pruned=True) from exc
    return _Fetched(porcelain, baseline)


async def _apply_ref_batch(target: RepositoryStoreTarget, batch: list[str], lock_fd: int) -> None:
    """Apply ``update-ref --stdin`` lines in one transaction, or one at a time if it fails.

    Two names that fold onto one lock file cannot be in one transaction, so a refused
    batch is retried line by line; a line that still fails is logged and left for the
    caller's listing to report.
    """

    def run(lines: list[str]) -> Awaitable[bytes]:
        return run_git(
            ["update-ref", "--no-deref", "--stdin"],
            target=target,
            policy=ACQUISITION_POLICY,
            pass_fds=(lock_fd,),
            stdin_bytes="".join(lines).encode("utf-8", "surrogateescape"),
        )

    if not batch:
        return
    try:
        await run(batch)
        return
    except GitCommandError as exc:
        log.debug("a ref transaction was refused; applying it a ref at a time: %s", _detail(exc))
    for line in batch:
        try:
            await run([line])
        except GitCommandError as exc:
            log.warning("could not put one ref back: %s", _detail(exc))


async def _finish_despite_cancel[T](work: Awaitable[T]) -> T:
    """Run *work* to the end even if the caller is cancelled meanwhile, then re-raise.

    For work that must not stop half done under the fetch lock: removing what a killed
    fetch left, and checking and undoing a case fold.
    """

    task = asyncio.ensure_future(work)
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        while not task.done():
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.shield(task)
        raise


async def _restore_refs(
    target: RepositoryStoreTarget, before: dict[str, str], lock_fd: int
) -> tuple[str, ...]:
    """Put every branch and tag back as *before* lists them; the refs still moved after.

    Two ``update-ref --stdin`` transactions: names the store lists now and did not before
    are deleted first, because on a case-insensitive filesystem one of them may be the
    file a name in *before* was folded into; then each name in *before* is set to its old
    object, which the store still has because nothing removes objects. Under the fetch
    lock no other writer holds, so each update checks nothing it did not just read.
    Returns the refs that still differ from *before* -- all of them when the store
    cannot be listed -- so a caller can say which stayed moved; the next refresh
    restores again.
    """

    try:
        held = await mirror_refs(target)
        deletions = [f"delete {name} {held[name]}\n" for name in sorted(set(held) - set(before))]
        updates = [
            f"update {name} {oid}\n"
            for name, oid in sorted(before.items())
            if held.get(name) != oid
        ]
        for batch in (deletions, updates):
            await _apply_ref_batch(target, batch, lock_fd)
        held = await mirror_refs(target)
    except GitError as exc:
        log.warning("could not put the store's refs back after a case fold: %s", _detail(exc))
        return tuple(sorted(before))
    moved = tuple(
        sorted(
            {name for name, oid in before.items() if held.get(name) != oid}
            | (set(held) - set(before))
        )
    )
    if moved:
        log.warning("after a case fold these refs are still moved: %s", ", ".join(moved[:8]))
    return moved


def _collision(unrestored: tuple[str, ...]) -> StoreUpdate:
    """``ref_case_collision``, naming any ref a fold moved that could not be put back."""

    if unrestored:
        log.error(
            "refs a case fold moved could not be put back and may name a twin's commit: %s",
            ", ".join(unrestored[:8]),
        )
    return StoreUpdate(RefreshOutcome.ref_case_collision, canonical_now(), unrestored=unrestored)


async def _check_for_folds(
    target: RepositoryStoreTarget, before: dict[str, str], fetched: _Fetched, lock_fd: int
) -> StoreUpdate | None:
    """``None`` when the fetch folded nothing; otherwise the refs go back first."""

    assert fetched.baseline is not None
    try:
        folded = folded_refs(
            before=fetched.baseline,
            written=fetched_refs(fetched.porcelain),
            pruned=pruned_ref_names(fetched.porcelain),
            held=await mirror_refs(target),
        )
    except GitError as exc:
        # Unchecked refs could be folded ones; nothing that cannot be checked stays.
        log.warning("could not check the refs a refresh wrote: %s", _detail(exc))
        unrestored = await _restore_refs(target, before, lock_fd)
        if unrestored:
            return _collision(unrestored)
        return StoreUpdate(RefreshOutcome.failed, canonical_now())
    if not folded:
        return None
    log.warning(
        "refresh fetched refs that differ only in letter case; putting every ref back: %s",
        ", ".join(folded[:4]),
    )
    return _collision(await _restore_refs(target, before, lock_fd))


async def _fetch(
    target: RepositoryStoreTarget, remote_url: str, *, lock_fd: int, previous_ref: str | None
) -> StoreUpdate:
    """Observe the origin's HEAD, fetch, and read the default branch back from the mirror.

    Git's own messages can carry the origin's local path and span several lines, so
    they are logged at debug only; an https failure is reported by the state its text
    names.
    """

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
        log.debug("refresh could not read the origin: %s", _detail(exc))
        outcome = _named(exc, remote_url, RefreshOutcome.origin_unavailable)
        return StoreUpdate(outcome, canonical_now())
    except OriginHeadError as exc:
        log.debug("refresh could not read the origin: %s", _detail(exc))
        return StoreUpdate(RefreshOutcome.origin_unavailable, canonical_now())
    # On a case-insensitive filesystem, what the store held before is kept, so a fetch
    # that folded two refs into one file can be undone; see ``folded_refs``.
    before = await mirror_refs(target) if await store_ignores_case(target) else None
    try:
        fetched = await _fetch_atomically(target, remote_url, lock_fd, before)
    except asyncio.CancelledError:
        # Stopped as the fetch ended: it may have landed and folded. Nothing a cancelled
        # refresh did stays, so the refs go back as they were before it began.
        if before is not None:
            await _finish_despite_cancel(_restore_refs(target, before, lock_fd))
        raise
    except _FetchFailedError as exc:
        cause = exc.cause
        log.debug("refresh fetch failed: %s", _detail(cause))
        # Still a ref-lock clash after pruning, on a case-insensitive filesystem: the
        # origin has two refs that differ only in case, which one loose file cannot hold.
        # The prune before the retry is undone too, so no ref moved.
        if (
            before is not None
            and isinstance(cause, GitCommandError)
            and _REF_LOCK_CONFLICT.search(cause.stderr_summary) is not None
        ):
            unrestored = await _finish_despite_cancel(_restore_refs(target, before, lock_fd))
            return _collision(unrestored)
        outcome = _named(cause, remote_url, RefreshOutcome.fetch_failed)
        if not exc.pruned:
            return StoreUpdate(outcome, canonical_now())
        # A prune ran, at least in part, before the fetch failed: record the first of
        # the origin's default branch and the one recorded before that is still there.
        for ref in (remote_tracking_ref(head_ref), previous_ref):
            tip = await ref_tip(target, ref) if ref is not None else None
            if tip is not None:
                return StoreUpdate(
                    outcome, canonical_now(), default_remote_ref=ref, default_revision=tip
                )
        return StoreUpdate(outcome, canonical_now())
    if before is not None and fetched.baseline is not None:
        # Checked and, when folded, undone to the end, whatever cancels the refresh.
        verdict = await _finish_despite_cancel(_check_for_folds(target, before, fetched, lock_fd))
        if verdict is not None:
            return verdict
    default_remote_ref = remote_tracking_ref(head_ref)
    outcome = RefreshOutcome.succeeded
    if default_remote_ref is None:
        # A detached HEAD names no branch. Everything was fetched; the default branch
        # stays the one recorded before, at the commit that branch names now.
        outcome = RefreshOutcome.default_branch_unknown
        default_remote_ref = previous_ref
        if default_remote_ref is None:
            return StoreUpdate(outcome, canonical_now())
    # The fetched ref, not the advertised object ID: the origin may have moved between
    # the two commands, and the mirror now holds whatever the fetch saw.
    revision = await ref_tip(target, default_remote_ref)
    if revision is None:
        if outcome is RefreshOutcome.default_branch_unknown:
            return StoreUpdate(outcome, canonical_now())
        log.debug("refresh did not find the origin's default branch as a commit")
        return StoreUpdate(RefreshOutcome.validation_failed, canonical_now())
    return StoreUpdate(
        outcome,
        canonical_now(),
        default_remote_ref=default_remote_ref,
        default_revision=revision,
    )


def _detail(exc: Exception) -> str:
    return failure_detail(exc) if isinstance(exc, GitError) else str(exc)


def _record(home: Path, store_key: str, update: StoreUpdate) -> None:
    """Rewrite ``state.yml`` under the store lock; synchronous and blocking.

    A fetch records the fetch time. Any refresh that observed the default branch and
    its commit records them -- a fetch, or a failed retry after a prune moved refs --
    and otherwise keeps the ones recorded before. Either way the outcome is recorded by
    name, so a later start reports it as this one did.
    """

    relative = store_record(store_key, "state.yml")
    with repository_store_lock(home, store_key):
        previous = read_record(home, relative, REPOSITORY_STORE_STATE_CONTRACT_ID)
        if not isinstance(previous, RepositoryStoreState):
            raise RecordError("state.yml did not validate", home / relative)
        fetched = update.outcome in _FETCHED
        observed = update.default_remote_ref is not None
        state = RepositoryStoreState(
            default_remote_ref=(
                update.default_remote_ref if observed else previous.default_remote_ref
            ),
            default_revision=update.default_revision if observed else previous.default_revision,
            last_fetch_at=update.at if fetched else previous.last_fetch_at,
            last_operation=StoreOperation(
                kind="refresh", outcome=_RECORDED[update.outcome], at=update.at
            ),
        )
        write_record_atomic(home, relative, state, REPOSITORY_STORE_STATE_CONTRACT_ID)


def _previous_default_ref(home: Path, store_key: str) -> str | None:
    """The default branch the store recorded before this refresh, if it can be read."""

    try:
        state = read_record(
            home, store_record(store_key, "state.yml"), REPOSITORY_STORE_STATE_CONTRACT_ID
        )
    except (FileNotFoundError, PrivateStorageError, RecordError, OSError):
        return None
    return state.default_remote_ref if isinstance(state, RepositoryStoreState) else None


async def update_store(home: Path, store_key: str, *, remote_url: str) -> StoreUpdate:
    """Refresh the published store *store_key* under *home* from *remote_url*.

    *remote_url* is where the store's source is fetched from: its normalized URL, as
    :func:`~metabrowser.cache.acquire.remote_url_for` says, which also decides the
    credential helper.

    Returns a :class:`StoreUpdate` for every outcome the origin, the network, the
    installed Git, or another process can cause. The fetch lock is tried before the
    Git floor is checked, so a refresh another process is running is reported as such
    whatever Git this process has. Cancellation propagates after Git's process group
    is killed and the fetch lock is released; the atomic fetch leaves every ref as it
    was or wholly updated, and ``state.yml`` untouched.
    """

    try:
        target = repository_store_target(
            git_dir=home / store_directory(store_key) / "repository.git"
        )
    except GitUnavailableError as exc:
        log.debug("refresh skipped: %s", exc)
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
        try:
            require_acquisition_git()
        except UnsupportedGitVersionError as exc:
            log.info("refresh skipped: %s", exc)
            return StoreUpdate(RefreshOutcome.unsupported_git, canonical_now())
        # The lock is released on the way out, so the removal must finish first,
        # however many times the refresh is cancelled while it runs.
        removed = await _finish_despite_cancel(
            asyncio.to_thread(remove_interrupted_fetch_leftovers, target.git_dir)
        )
        if removed:
            log.debug("removed files an interrupted fetch left in a store: %s", removed)
        previous_ref = await asyncio.to_thread(_previous_default_ref, home, store_key)
        try:
            update = await _fetch(
                target, remote_url, lock_fd=fetch_lock.descriptor, previous_ref=previous_ref
            )
        except GitError as exc:
            # A local read of the store failed around the fetch: listing its refs, its
            # case setting, or a tip. Reported, never raised into the caller.
            log.warning("refresh could not read the store: %s", _detail(exc))
            update = StoreUpdate(RefreshOutcome.failed, canonical_now())
        if update.outcome in _RECORDED:
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


# The same restore and cancellation shield, for a pull request's fetch into the store.
restore_mirror_refs = _restore_refs
finish_despite_cancel = _finish_despite_cancel

__all__ = [
    "RefreshOutcome",
    "StoreUpdate",
    "finish_despite_cancel",
    "remove_interrupted_fetch_leftovers",
    "restore_mirror_refs",
    "update_store",
]
