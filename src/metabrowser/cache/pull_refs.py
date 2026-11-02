"""Fetch a pull request's head into a published store and compute its comparison.

A pull request's commits, a fork's included, arrive through the origin's own
``refs/pull/<n>/head``, fetched into the same ref in the store: the one ref a store
holds beyond the origin's branches and tags. An open pull request's base branch is
fetched in the same command, into the ``refs/remotes/origin/<base>`` the mirror update
writes, so its merge base is computed against the base branch as it is now, as GitHub
computes Files changed. A closed or merged pull request's comparison starts from the
API's ``base.sha`` instead, fetched by ID when the mirror does not have it.

Every fetch is a network command on an acquisition-grade Git, all in
:func:`fetch_into_store`: :func:`~metabrowser.cache.origin.origin_git_args`, the
isolated acquisition policy, its own process group, and the Git floor, under the store's
fetch side lock with the leftovers of a killed fetch removed first, as the mirror update
does. Nothing here writes a record or takes a hierarchy lock.

A merge base on a store with a shallow boundary is believed only when it is certain
(:mod:`metabrowser.git.shallow`). :func:`comparison_endpoints` raises
:class:`BaseUncertainError` otherwise, and :func:`deepen_until_certain` is what the
pull request's refresh job does about it: it fetches more history from the origin into
the store's own objects, in rounds, until the answer can be believed or the bounds are
reached. The checkout an overlay borrows from is never written: the store takes over its
own boundary first (:func:`~metabrowser.cache.lender.own_boundary`).
"""

from __future__ import annotations

import asyncio
import functools
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal

from metabrowser.cache import acquire
from metabrowser.cache.atomic import RecordError
from metabrowser.cache.lender import (
    LenderGoneError,
    own_boundary,
    prepare_overlay_fetch,
    read_store_lender,
)
from metabrowser.cache.locks import (
    CacheLock,
    LockBusyError,
    LockOrder,
    lock_order,
    require_no_hierarchy_locks,
    run_lock_section,
    store_fetch_lock,
)
from metabrowser.cache.origin import (
    BRANCH_MIRROR_PREFIX,
    classify_remote_failure,
    fetched_refs,
    origin_git_args,
)
from metabrowser.cache.paths import MAX_PULL_REQUEST_NUMBER
from metabrowser.cache.resolve import (
    folded_refs,
    is_valid_ref_name,
    mirror_refs,
    store_ignores_case,
)
from metabrowser.cache.update import (
    finish_despite_cancel,
    remove_interrupted_fetch_leftovers,
    restore_mirror_refs,
)
from metabrowser.git.process import (
    ACQUISITION_POLICY,
    GIT_ACQUISITION_TIMEOUT_S,
    STORE_READ_POLICY,
    GitCommandError,
    GitError,
    GitTimeoutError,
    RepositoryStoreTarget,
    repository_store_target,
    run_git,
)
from metabrowser.git.shallow import merge_base_answer
from metabrowser.git.wire import is_full_revision
from metabrowser.home import PrivateStorageError

if TYPE_CHECKING:
    from metabrowser.cache.acquire import PublishedSource

log = logging.getLogger(__name__)

# How often a pull request's fetch tries the store's fetch lock again while another
# refresh holds it, and for how long. The mirror update that usually holds it moves
# nothing new in 135-170 ms over file:// and a few seconds over https (measured for
# step 4 of the thin-mirror plan); a minute covers a slow one, after which the pull
# request reports that the store is being refreshed elsewhere rather than wait on.
FETCH_LOCK_RETRY_S: Final = 0.25
FETCH_LOCK_WAIT_S: Final = 60.0

# How many more commits each round of deepening asks for, and so how many rounds there
# are. Measured 2026-11-02: a replica's depth-3 clone needed one round of two and its
# depth-1 clone two rounds, and fetching the 8.8 MB that ends the shallow history of a
# 1.2 GB repository took 7.5 s. A merge base further back than the first rounds reach is
# an old pull request on a depth-limited clone, the case this is for, so the rounds grow
# by a factor of eight and reach 9,362 commits. An answer still uncertain after them
# reads ``base_uncertain``, and the next refresh goes on from there.
DEEPEN_ROUNDS: Final[tuple[int, ...]] = (2, 16, 128, 1024, 8192)

type PullFetchFailure = Literal[
    "not_found_or_private",
    "network_error",
    "fetch_failed",
    "refreshing_elsewhere",
    "lender_missing",
]


class RefCaseCollisionError(Exception):
    """The fetch folded a branch into one whose name differs only in case.

    Every branch and tag was put back but ``unrestored``, which the next refresh restores.
    """

    def __init__(self, unrestored: tuple[str, ...] = ()) -> None:
        super().__init__("a fetch folded refs that differ only in letter case")
        self.unrestored = unrestored


class PullRefError(Exception):
    """Git could not fetch or read a pull request's commits; ``state`` says why.

    The message names no path and carries none of Git's own text.
    """

    def __init__(
        self, state: PullFetchFailure | Literal["no_merge_base", "base_uncertain"], message: str
    ) -> None:
        super().__init__(message)
        self.state = state


class BaseUncertainError(PullRefError):
    """The store's history is too shallow to know the merge base, and no guess is made.

    ``base_commit`` and ``base_from`` are what the comparison started from, which is what
    deepening asks the origin for.
    """

    def __init__(self, *, base_commit: str, base_from: Literal["base_branch", "base_sha"]) -> None:
        super().__init__(
            "base_uncertain",
            "the history here is too shallow to know what this pull request changed",
        )
        self.base_commit = base_commit
        self.base_from: Literal["base_branch", "base_sha"] = base_from


@dataclass(frozen=True, slots=True)
class PullEndpoints:
    """The merge base, the head, and the commit the merge base was computed from."""

    base: str
    head: str
    base_commit: str
    base_from: Literal["base_branch", "base_sha"]


def pull_head_ref(number: int) -> str:
    """``refs/pull/<n>/head`` for a validated pull-request number."""

    if isinstance(number, bool) or not 1 <= number <= MAX_PULL_REQUEST_NUMBER:
        raise ValueError("invalid pull-request number")
    return f"refs/pull/{number}/head"


def _target(published: PublishedSource) -> RepositoryStoreTarget:
    return repository_store_target(git_dir=published.git_dir)


async def _read(published: PublishedSource, args: list[str]) -> bytes:
    return await run_git(args, target=_target(published), policy=STORE_READ_POLICY)


def _claim_fetch_lock(published: PublishedSource, owner: LockOrder) -> CacheLock:
    return store_fetch_lock(published.home, published.store_key, order=owner)


def _release(lock: CacheLock) -> None:
    lock.release()


async def _take_fetch_lock(published: PublishedSource) -> CacheLock:
    """The store's fetch side lock, tried again while another refresh holds it.

    The lock is never waited on in a thread: each try is without blocking, and between
    tries this coroutine sleeps. Raises :class:`LockBusyError` after
    :data:`FETCH_LOCK_WAIT_S`.
    """

    waited = 0.0
    while True:
        try:
            return await run_lock_section(
                functools.partial(_claim_fetch_lock, published, lock_order()), release=_release
            )
        except LockBusyError:
            if waited >= FETCH_LOCK_WAIT_S:
                raise
        await asyncio.sleep(FETCH_LOCK_RETRY_S)
        waited += FETCH_LOCK_RETRY_S


async def fetch_into_store(
    published: PublishedSource,
    specs: list[str],
    *,
    deepen: int | None = None,
    timeout_s: float | None = None,
) -> None:
    """``git fetch --atomic`` *specs* from the source's origin into its published store.

    Every fetch this module makes is this one command: the pull-request ref and the base
    branch with it, or one commit by ID. It holds the store's fetch side lock, as the
    mirror update does, and Git inherits the lock's descriptor so the lock stays held for
    as long as any Git it started runs. Under it, what a killed fetch left in the store
    is removed first. The origin is named by the URL its source was acquired from, with
    that URL's arguments: the protocol allowlist, the stall bound, and for github.com the
    ``gh`` credential helper. ``--atomic`` writes every ref or none, after the objects.

    Into an overlay store, the store's dangling refs are swept and the fetch negotiates
    from the checkout's remote-tracking tips (:func:`prepare_overlay_fetch`), so it brings
    only what the checkout lacks. *deepen* asks for that many more commits below the
    store's boundary, which the store first takes over as its own file, since Git would
    write it through a link into the checkout. *timeout_s* lowers the acquisition deadline.
    Raises :class:`~metabrowser.cache.lender.LenderGoneError` when the checkout has gone.
    """

    require_no_hierarchy_locks("a pull request's fetch")
    # Through the acquisition module, so the Git floor and the origin URL have one seam
    # each for every command that fetches into a store.
    await asyncio.to_thread(acquire.require_acquisition_git)
    remote_url = acquire.remote_url_for(published.source)
    lock = await _take_fetch_lock(published)
    try:
        # To the end even when cancelled: the lock is released on the way out.
        removed = await finish_despite_cancel(
            asyncio.to_thread(remove_interrupted_fetch_leftovers, published.git_dir)
        )
        if removed:
            log.debug("removed files an interrupted fetch left in a store: %s", removed)
        target = _target(published)
        negotiation = await _overlay_negotiation(published, target, lock)
        if deepen is not None:
            await finish_despite_cancel(asyncio.to_thread(own_boundary, published.git_dir))
        # On a case-insensitive filesystem the base branch can fold into a branch whose
        # name differs only in case; the mirror update's check and restore apply.
        before = await mirror_refs(target) if await store_ignores_case(target) else None
        written = await run_git(
            [
                *origin_git_args(remote_url),
                "fetch",
                "--atomic",
                "--porcelain",
                "--no-tags",
                "--no-write-fetch-head",
                *negotiation,
                *([f"--deepen={deepen}"] if deepen is not None else []),
                remote_url,
                *specs,
            ],
            target=target,
            policy=ACQUISITION_POLICY,
            pass_fds=(lock.descriptor,),
            timeout_s=timeout_s,
        )
        if before is not None:
            # Checked and undone to the end even when cancelled: the lock is released
            # on the way out, and a fold must not stay in the store.
            await finish_despite_cancel(_undo_a_fold(target, before, written, lock.descriptor))
    finally:
        lock.release()


async def _overlay_negotiation(
    published: PublishedSource, target: RepositoryStoreTarget, lock: CacheLock
) -> tuple[str, ...]:
    """An overlay's sweep and negotiation tips under the fetch lock; nothing for a full store.

    From the record, not *published*, so a lender repaired since this server started is
    the one used. The sweep runs to the end even when cancelled.
    """

    lender = await asyncio.to_thread(read_store_lender, published.home, published.store_key)
    if lender is None:
        return ()
    default = published.default_remote_ref.removeprefix(BRANCH_MIRROR_PREFIX)
    return await finish_despite_cancel(
        prepare_overlay_fetch(target, lender, lock.descriptor, preferred=default)
    )


async def _undo_a_fold(
    target: RepositoryStoreTarget, before: dict[str, str], written: bytes, lock_fd: int
) -> None:
    """Put every branch and tag back if the fetch folded a branch into another.

    Raises :class:`RefCaseCollisionError` naming any ref that could not be put back, and
    re-raises a failure to list the store after restoring, since unchecked refs could be
    folded ones.
    """

    branches = {
        name: oid
        for name, oid in fetched_refs(written).items()
        if name.startswith(BRANCH_MIRROR_PREFIX)
    }
    try:
        held = await mirror_refs(target)
    except GitError:
        await restore_mirror_refs(target, before, lock_fd)
        raise
    if folded_refs(before=before, written=branches, pruned=(), held=held):
        unrestored = await restore_mirror_refs(target, before, lock_fd)
        if unrestored:
            log.warning(
                "a pull request's fetch folded refs, and these could not be put back: %s",
                ", ".join(unrestored[:8]),
            )
        raise RefCaseCollisionError(unrestored)


async def _fetch(
    published: PublishedSource,
    specs: list[str],
    *,
    deepen: int | None = None,
    timeout_s: float | None = None,
) -> None:
    """:func:`fetch_into_store`, with Git's failure as a typed :class:`PullRefError`."""

    try:
        await fetch_into_store(published, specs, deepen=deepen, timeout_s=timeout_s)
    except LenderGoneError as exc:
        raise PullRefError(
            "lender_missing", "the checkout this mirror borrows objects from is gone"
        ) from exc
    except RecordError as exc:
        raise PullRefError("fetch_failed", "the store's record could not be read") from exc
    except LockBusyError as exc:
        raise PullRefError(
            "refreshing_elsewhere", "another refresh of the mirror kept its fetch lock"
        ) from exc
    except RefCaseCollisionError as exc:
        raise PullRefError(
            "fetch_failed",
            "the base branch differs only in letter case from another branch, which this "
            "filesystem cannot hold apart",
        ) from exc
    except (PrivateStorageError, OSError) as exc:
        # The lock file could not be opened: the cache is not the owner-only directory
        # it must be, or the disk refused. The mirror update reports the same.
        raise PullRefError("fetch_failed", "the store's fetch lock could not be taken") from exc
    except GitTimeoutError as exc:
        raise PullRefError("network_error", "Git did not finish the fetch in time") from exc
    except GitCommandError as exc:
        # Only https: a file:// failure's text names local paths, which could match.
        state = None
        if published.source.transport == "https":
            state = classify_remote_failure(exc.stderr_summary)
        if state == "not_found_or_private":
            raise PullRefError(
                "not_found_or_private",
                "the origin has no such pull request, or the repository is private and "
                "could not be read",
            ) from exc
        if state is not None:
            raise PullRefError("network_error", "Git could not reach the origin") from exc
        raise PullRefError("fetch_failed", "Git could not fetch the pull request") from exc


async def ref_commit(published: PublishedSource, ref: str) -> str | None:
    """The commit an exact ref names in the store, or ``None``."""

    try:
        out = await _read(published, ["show-ref", "--verify", "--", ref])
    except GitCommandError:
        return None
    oid = out.split(b" ", 1)[0].decode("ascii", errors="replace")
    return oid if is_full_revision(oid) else None


async def has_commit(published: PublishedSource, oid: str) -> bool:
    """Whether the store has the full commit ID *oid*."""

    if not is_full_revision(oid):
        return False
    try:
        kind = await _read(published, ["cat-file", "-t", oid])
    except GitCommandError:
        return False
    return kind.strip() == b"commit"


async def base_branch_usable(published: PublishedSource, base_branch: str) -> bool:
    """Whether the base branch may be fetched into, and compared from, the mirror's ref.

    On a case-insensitive filesystem only when the store lists it under exactly that
    name. One it lists under another spelling (``Feature/x`` kept as ``feature/x``
    beside ``feature/y``) shares that ref's file, so writing it would pass for a fold;
    the comparison then starts from the API's ``base.sha`` instead.
    """

    if not is_valid_ref_name(base_branch):
        return False
    target = _target(published)
    if not await store_ignores_case(target):
        return True
    return BRANCH_MIRROR_PREFIX + base_branch in await mirror_refs(target)


async def fetch_pull_head(
    published: PublishedSource, number: int, *, base_branch: str | None = None
) -> str | None:
    """Fetch ``refs/pull/<n>/head`` (and *base_branch*, if valid) and return the head.

    ``None`` means the fetch succeeded but the ref is not in the store.
    """

    ref = pull_head_ref(number)
    specs = [f"+{ref}:{ref}"]
    if base_branch is not None and await base_branch_usable(published, base_branch):
        specs.append(f"+refs/heads/{base_branch}:{BRANCH_MIRROR_PREFIX}{base_branch}")
    await _fetch(published, specs)
    return await ref_commit(published, ref)


async def fetch_commit(published: PublishedSource, oid: str) -> None:
    """Fetch one commit by ID, which the origin may still serve without any ref naming it."""

    if not is_full_revision(oid):
        raise ValueError("not a full commit ID")
    await _fetch(published, [oid])


async def comparison_endpoints(
    published: PublishedSource,
    *,
    head: str,
    base_sha: str,
    base_branch: str | None,
    open_pull: bool,
) -> PullEndpoints:
    """Files changed as GitHub shows it: ``merge-base(base, head)..head``.

    An open pull request starts from the mirror's base branch when it has one; a closed
    or merged one, or an open one whose base branch is not mirrored, from ``base.sha``,
    fetched first if the store lacks it.
    """

    base_commit: str | None = None
    base_from: Literal["base_branch", "base_sha"] = "base_sha"
    if open_pull and base_branch is not None and await base_branch_usable(published, base_branch):
        base_commit = await ref_commit(published, BRANCH_MIRROR_PREFIX + base_branch)
        if base_commit is not None:
            base_from = "base_branch"
    if base_commit is None:
        if not await has_commit(published, base_sha):
            await fetch_commit(published, base_sha)
        base_commit = base_sha
    return await _endpoints_from(published, head, base_commit, base_from)


async def _endpoints_from(
    published: PublishedSource,
    head: str,
    base_commit: str,
    base_from: Literal["base_branch", "base_sha"],
) -> PullEndpoints:
    """The merge base of *base_commit* and *head*, when it can be believed."""

    try:
        answer = await merge_base_answer(_target(published), base_commit, head)
    except GitCommandError as exc:
        raise PullRefError("no_merge_base", "the base and head share no history") from exc
    if not answer.certain:
        raise BaseUncertainError(base_commit=base_commit, base_from=base_from)
    if answer.merge_base is None:
        raise PullRefError("no_merge_base", "the base and head share no history")
    return PullEndpoints(
        base=answer.merge_base, head=head, base_commit=base_commit, base_from=base_from
    )


async def deepen_until_certain(
    published: PublishedSource,
    number: int,
    *,
    head: str,
    base_branch: str | None,
    uncertain: BaseUncertainError,
) -> PullEndpoints:
    """Fetch more history into the store until the merge base can be believed.

    The base and the head are fetched with ``--deepen``, a round at a time
    (:data:`DEEPEN_ROUNDS`), all of it within the acquisition deadline. The base is the
    branch when that is what the comparison started from and otherwise the commit by ID.
    Raises *uncertain* when the rounds run out, and the fetch's own typed
    :class:`PullRefError` when the origin cannot be reached, as when offline. The objects
    go into the store's own directory, and the checkout is not touched.
    """

    ref = pull_head_ref(number)
    base_spec = (
        f"+refs/heads/{base_branch}:{BRANCH_MIRROR_PREFIX}{base_branch}"
        if uncertain.base_from == "base_branch" and base_branch is not None
        else uncertain.base_commit
    )
    deadline = time.monotonic() + GIT_ACQUISITION_TIMEOUT_S
    for depth in DEEPEN_ROUNDS:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        await _fetch(published, [f"+{ref}:{ref}", base_spec], deepen=depth, timeout_s=remaining)
        try:
            return await _endpoints_from(
                published, head, uncertain.base_commit, uncertain.base_from
            )
        except BaseUncertainError:
            log.debug(
                "the merge base of pull request %s is uncertain after --deepen=%s", number, depth
            )
    raise uncertain


__all__ = [
    "DEEPEN_ROUNDS",
    "BaseUncertainError",
    "PullEndpoints",
    "PullFetchFailure",
    "PullRefError",
    "RefCaseCollisionError",
    "base_branch_usable",
    "comparison_endpoints",
    "deepen_until_certain",
    "fetch_commit",
    "fetch_into_store",
    "fetch_pull_head",
    "has_commit",
    "pull_head_ref",
    "ref_commit",
]
