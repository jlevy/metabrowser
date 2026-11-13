"""Repository identity: root, HEAD, and whether git is usable at all.

Discovery asks git rather than looking for a ``.git`` marker. The marker
test in :func:`metabrowser.tree._find_git_root` is right for its purpose
— it only needs somewhere to anchor gitignore patterns — but it accepts
directories git itself would refuse: a linked worktree whose ``.git``
file points at a gitdir that no longer exists, a repository owned by
another user (``detected dubious ownership``), or a ``.git`` that is not
a repository at all. Asking ``git rev-parse`` collapses "is there a
repository" and "can we read it" into a single answer, which is exactly
the question the Git tab needs settled before it renders.

The served root must also be the repository's working-tree root. Git
history spans the whole working tree, so exposing it while Metabrowser
serves only a subdirectory would describe files outside the browser's
navigation boundary. Linked worktrees qualify because git reports each
worktree's own root from ``--show-toplevel``.

The result is TTL-cached per :class:`~metabrowser.git.process.GitLocation`
identity. A filesystem location keys on the resolved served root; a
revision location keys on the store plus the pinned object id. Identity
is stable between commits but must not survive a checkout, so the TTL is
short — the same shape as the gitignore checker cache in
:mod:`metabrowser.tree`. An unborn HEAD is the exception: it is
rediscovered on every request so the repository's first commit becomes
visible immediately.

Past the TTL a filesystem identity is checked rather than discovered again.
Discovery is three Git processes, and a request that came after the TTL paid them
inline: about 55 ms at the server on a commit's comparison and its detail together
(exp-081's server half and the contention sweep after it). Whichever request came
first after five quiet seconds paid it, so a page that asked the server less often,
as the kept comparisons and the route memo make it, moved that cost onto a hover or
a first commit instead of removing it. So each entry keeps the refs' state
(:func:`~metabrowser.git.ref_state.ref_state`) read just before its discovery. The
identity reads the served root's ``.git`` entry, ``HEAD``, the ref it names, and
``core.worktree`` from the configuration, all of which that state covers. Past the
TTL, an unchanged state keeps the entry for another TTL without running Git; a
changed one, or one that cannot be named, is rediscovered inline as before. What the
state does not cover, the reader's global Git configuration (``safe.directory``) and
Git going missing, is checked by rediscovering in the background once an entry is
:data:`~metabrowser.settings.GIT_REPO_INFO_MAX_AGE_S` old, off the request that
found it. A pinned revision, a negative answer, and a repository past the state's
entry bound keep the plain TTL.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from metabrowser.git.process import (
    GitCommandError,
    GitError,
    GitLocation,
    GitUnavailableError,
    as_location,
    failure_detail,
    git_executable,
    run_git_at,
)
from metabrowser.git.ref_state import ref_state
from metabrowser.git.wire import GitHead, GitRepoInfo, is_full_revision
from metabrowser.paths_safe import register_root_callback
from metabrowser.settings import GIT_REPO_INFO_MAX_AGE_S, GIT_REPO_INFO_TTL_S

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RepoContext:
    """A resolved repository for one :class:`GitLocation`.

    Filesystem discovery still guarantees ``git_root == served_root``.
    A revision subject has no working tree, so both paths are ``None``
    and :meth:`command_location` is the store pin. Keeping both path
    names preserves the defensive boundary in commit-detail parsing.
    """

    git_root: Path | None
    served_root: Path | None
    head: GitHead
    location: GitLocation | None = None

    def command_location(self) -> GitLocation:
        if self.location is not None:
            return self.location
        if self.served_root is None:
            raise TypeError("RepoContext needs a location or served_root")
        return GitLocation.filesystem(self.served_root)


@dataclass
class _Entry:
    """One location's identity and what decides whether it still holds.

    ``context`` is None exactly when ``info["is_repo"]`` is false, so a negative result
    is cached for the same TTL as a positive one — a non-repository root must not
    re-spawn git on every poll. ``state`` is the refs' state read just before the
    discovery, or None when the entry keeps the plain TTL.
    """

    expires_at: float
    context: RepoContext | None
    info: GitRepoInfo
    state: str | None
    discovered_at: float


_REPO_CACHE: dict[str, _Entry] = {}
# Background rediscoveries in flight, one per location, so a task is never collected
# while it runs and two never race for one entry.
_REFRESHING: dict[str, asyncio.Task[None]] = {}


def clear_repo_cache() -> None:
    """Drop every cached repository lookup.

    Registered as a served-root change callback so a root swap cannot
    serve another directory's repository identity.
    """
    _REPO_CACHE.clear()
    for task in _REFRESHING.values():
        task.cancel()
    _REFRESHING.clear()


def _negative(reason: str) -> GitRepoInfo:
    """The envelope every endpoint returns when there is no readable repo."""
    return GitRepoInfo(is_repo=False, root=None, head=None, reason=reason)


async def _resolve_head(location: GitLocation) -> GitHead:
    """Read HEAD: the branch it is on, the commit it resolves to, or neither.

    Two commands rather than one because the three states are signalled
    by exit codes, not by output. ``symbolic-ref`` fails when HEAD is
    detached; ``rev-parse --verify`` fails when the branch is unborn (a
    fresh ``git init`` with no commit). Both failures are ordinary.

    A pinned revision never asks the store's ambient HEAD: the subject
    is detached at that object id.
    """
    if location.pinned_revision is not None:
        return GitHead(
            ref=None,
            revision=location.pinned_revision,
            detached=True,
            unborn=False,
        )

    ref: str | None = None
    detached = False
    try:
        raw = await run_git_at(["symbolic-ref", "--quiet", "HEAD"], location)
        ref = raw.decode("utf-8", errors="replace").strip() or None
    except GitCommandError:
        detached = True

    revision: str | None = None
    unborn = False
    try:
        raw = await run_git_at(["rev-parse", "--verify", "--quiet", "HEAD"], location)
        candidate = raw.decode("utf-8", errors="replace").strip()
        revision = candidate if is_full_revision(candidate) else None
    except GitCommandError:
        unborn = True

    # An unborn HEAD is symbolic (it names the branch that will exist
    # after the first commit), so `detached` must not be inferred from a
    # missing revision. The two flags are independent.
    if revision is None:
        unborn = True

    return GitHead(ref=ref, revision=revision, detached=detached, unborn=unborn)


async def _discover_revision(location: GitLocation) -> tuple[RepoContext | None, GitRepoInfo]:
    """Prove a pinned commit without treating the store as a working tree."""
    pin = location.pinned_revision
    if pin is None:
        raise TypeError("revision discovery requires a pinned object id")
    if git_executable() is None:
        return None, _negative("no_git")

    try:
        raw = await run_git_at(
            ["rev-parse", "--verify", "--quiet", "--end-of-options", f"{pin}^{{commit}}"],
            location,
        )
    except GitUnavailableError:
        return None, _negative("no_git")
    except GitCommandError:
        return None, _negative("not_a_repo")
    except GitError as exc:
        log.warning(
            "git revision discovery failed for %s: %s",
            location.identity,
            failure_detail(exc),
        )
        return None, _negative("git_failed")

    candidate = raw.decode("utf-8", errors="replace").strip()
    if candidate != pin or not is_full_revision(candidate):
        return None, _negative("not_a_repo")

    try:
        head = await _resolve_head(location)
    except GitError as exc:
        log.warning(
            "git HEAD resolution failed for %s: %s",
            location.identity,
            failure_detail(exc),
        )
        return None, _negative("git_failed")

    context = RepoContext(git_root=None, served_root=None, head=head, location=location)
    return context, GitRepoInfo(is_repo=True, root="", head=head)


async def _discover_filesystem(location: GitLocation) -> tuple[RepoContext | None, GitRepoInfo]:
    """Run the working-tree discovery commands, uncached."""
    served_root = location.cwd
    if served_root is None:
        raise TypeError("filesystem discovery requires cwd")
    if git_executable() is None:
        return None, _negative("no_git")

    try:
        raw = await run_git_at(["rev-parse", "--show-toplevel"], location)
    except GitUnavailableError:
        return None, _negative("no_git")
    except GitCommandError:
        # The expected "not a git repository" path, and also the ownership
        # refusal. Both mean the same thing to the browser: no Git tab.
        return None, _negative("not_a_repo")
    except GitError as exc:
        # A timeout or an oversized response during discovery. Log it —
        # this one is genuinely unusual and worth seeing — but still
        # report the ordinary negative envelope rather than a 500: the
        # browser's only recourse either way is to hide the tab.
        log.warning("git repository discovery failed in %s: %s", served_root, failure_detail(exc))
        return None, _negative("git_failed")

    toplevel = raw.decode("utf-8", errors="replace").strip()
    if not toplevel:
        return None, _negative("not_a_repo")

    git_root = Path(toplevel).resolve()
    if git_root != served_root:
        # History is repository-wide. A subdirectory root would let the
        # Git view enumerate commits and files outside the tree the user
        # can browse, so it is deliberately not a Git-capable root.
        return None, _negative("not_repo_root")

    try:
        head = await _resolve_head(location)
    except GitError as exc:
        log.warning("git HEAD resolution failed in %s: %s", served_root, failure_detail(exc))
        return None, _negative("git_failed")

    context = RepoContext(
        git_root=git_root,
        served_root=served_root,
        head=head,
        location=location,
    )
    return context, GitRepoInfo(
        is_repo=True,
        root="",
        head=head,
    )


async def repo_info(root: Path | GitLocation) -> tuple[RepoContext | None, GitRepoInfo]:
    """Resolve the repository for *root*, TTL-cached and then checked against its refs.

    Returns ``(context, info)``. ``context`` is ``None`` exactly when
    ``info["is_repo"]`` is false; callers that need to run git branch on
    the context, and return ``info`` unchanged when it is absent. Past the TTL an
    entry whose refs' state is unchanged is kept without running Git (the module's
    docstring says what that state covers).
    """
    location = as_location(root)
    now = time.monotonic()
    entry = _REPO_CACHE.get(location.identity)
    # The first commit is the one identity transition that can happen
    # without a checkout. Keeping an unborn entry until the TTL would
    # make both /repo and /log lie after that commit was created.
    if entry is not None and (entry.context is None or not entry.context.head["unborn"]):
        if entry.expires_at > now:
            return entry.context, entry.info
        # Past the TTL: an unchanged refs' state keeps the identity without running Git.
        if entry.state is not None and await ref_state(location) == entry.state:
            entry.expires_at = now + GIT_REPO_INFO_TTL_S
            if now - entry.discovered_at >= GIT_REPO_INFO_MAX_AGE_S:
                _rediscover_in_background(location)
            return entry.context, entry.info
    return await _discover_and_keep(location, entry)


async def _discover_and_keep(
    location: GitLocation, previous: _Entry | None
) -> tuple[RepoContext | None, GitRepoInfo]:
    """Discover *location*'s identity and keep it with the refs' state it was read under.

    The state is read before the discovery, so a change made during it moves the state
    away from the one kept, and the next check discovers again. It is not read for a
    pinned revision, whose identity is its object id, or for a root the last discovery
    found was not a repository, which would spend a Git process on every poll.
    """
    started = time.monotonic()
    state: str | None = None
    if location.pinned_revision is None and (previous is None or previous.context is not None):
        state = await ref_state(location)
    if location.pinned_revision is not None:
        context, info = await _discover_revision(location)
    else:
        context, info = await _discover_filesystem(location)
    _REPO_CACHE[location.identity] = _Entry(
        expires_at=started + GIT_REPO_INFO_TTL_S,
        context=context,
        info=info,
        state=state if context is not None else None,
        discovered_at=started,
    )
    return context, info


def _rediscover_in_background(location: GitLocation) -> None:
    """Discover *location* again off the request path, once at a time."""

    key = location.identity
    if key in _REFRESHING:
        return
    entry = _REPO_CACHE.get(key)

    async def run() -> None:
        await _discover_and_keep(location, entry)

    task = asyncio.get_running_loop().create_task(run())
    _REFRESHING[key] = task

    def done(finished: asyncio.Task[None]) -> None:
        if _REFRESHING.get(key) is finished:
            del _REFRESHING[key]
        # Nothing awaits this task, so its failure is reported here; the entry it would
        # have replaced stays, and the next check past the TTL tries again.
        if not finished.cancelled() and (error := finished.exception()) is not None:
            log.warning("background git rediscovery failed for %s: %r", key, error)

    task.add_done_callback(done)


# Serving a different root must not keep answering with the previous
# root's repository identity, so the cache is dropped on every root swap
# — the same contract projections.py and activity.py use.
register_root_callback(clear_repo_cache)


__all__ = [
    "RepoContext",
    "clear_repo_cache",
    "repo_info",
]
