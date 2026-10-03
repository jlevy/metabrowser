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
"""

from __future__ import annotations

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
from metabrowser.git.wire import GitHead, GitRepoInfo, is_full_revision
from metabrowser.paths_safe import register_root_callback
from metabrowser.settings import GIT_REPO_INFO_TTL_S

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


# Cache entries are (expires_at, context_or_none, info). ``context`` is
# None exactly when ``info["is_repo"]`` is false, so a negative result is
# cached for the same TTL as a positive one — a non-repository root must
# not re-spawn git on every poll.
_REPO_CACHE: dict[str, tuple[float, RepoContext | None, GitRepoInfo]] = {}


def clear_repo_cache() -> None:
    """Drop every cached repository lookup.

    Registered as a served-root change callback so a root swap cannot
    serve another directory's repository identity.
    """
    _REPO_CACHE.clear()


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
    """Resolve the repository for *root*, TTL-cached.

    Returns ``(context, info)``. ``context`` is ``None`` exactly when
    ``info["is_repo"]`` is false; callers that need to run git branch on
    the context, and return ``info`` unchanged when it is absent.
    """
    location = as_location(root)
    key = location.identity
    now = time.monotonic()
    cached = _REPO_CACHE.get(key)
    if cached is not None and cached[0] > now:
        cached_context = cached[1]
        # The first commit is the one identity transition that can happen
        # without a checkout. Keeping an unborn entry until the TTL would
        # make both /repo and /log lie after that commit was created.
        if cached_context is None or not cached_context.head["unborn"]:
            return cached_context, cached[2]

    if location.pinned_revision is not None:
        context, info = await _discover_revision(location)
    else:
        context, info = await _discover_filesystem(location)
    _REPO_CACHE[key] = (now + GIT_REPO_INFO_TTL_S, context, info)
    return context, info


# Serving a different root must not keep answering with the previous
# root's repository identity, so the cache is dropped on every root swap
# — the same contract projections.py and activity.py use.
register_root_callback(clear_repo_cache)


__all__ = [
    "RepoContext",
    "clear_repo_cache",
    "repo_info",
]
