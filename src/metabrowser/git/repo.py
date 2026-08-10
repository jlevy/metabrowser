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

The result is TTL-cached per served root. Identity is stable between
commits but must not survive a checkout, so the TTL is short — the same
shape as the gitignore checker cache in :mod:`metabrowser.tree`. An
unborn HEAD is the exception: it is rediscovered on every request so the
repository's first commit becomes visible immediately.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

from metabrowser.git.process import (
    GitCommandError,
    GitError,
    GitUnavailableError,
    git_executable,
    run_git,
)
from metabrowser.git.wire import GitHead, GitRepoInfo, is_full_revision
from metabrowser.paths_safe import register_root_callback
from metabrowser.settings import GIT_REPO_INFO_TTL_S

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RepoContext:
    """A resolved repository, and where the served root sits inside it.

    ``served_root`` is the directory git commands run in, which is always
    the served root rather than the repository root: running in the
    served root is what makes git's own pathspec and ownership checks
    apply to the directory the user actually asked to browse.
    """

    git_root: Path
    served_root: Path
    head: GitHead

    @property
    def served_root_inside_repo(self) -> bool:
        """True when the served root is the repo root or below it.

        False means the repository root is *above* the served root, which
        happens whenever a subdirectory of a checkout is served. History
        is still fully readable; it only changes which changed files are
        navigable. See :func:`metabrowser.git.detail.translate_repo_path`.
        """
        return self.served_root == self.git_root or self.git_root in self.served_root.parents


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


async def _resolve_head(served_root: Path) -> GitHead:
    """Read HEAD: the branch it is on, the commit it resolves to, or neither.

    Two commands rather than one because the three states are signalled
    by exit codes, not by output. ``symbolic-ref`` fails when HEAD is
    detached; ``rev-parse --verify`` fails when the branch is unborn (a
    fresh ``git init`` with no commit). Both failures are ordinary.
    """
    ref: str | None = None
    detached = False
    try:
        raw = await run_git(["symbolic-ref", "--quiet", "HEAD"], cwd=served_root)
        ref = raw.decode("utf-8", errors="replace").strip() or None
    except GitCommandError:
        detached = True

    revision: str | None = None
    unborn = False
    try:
        raw = await run_git(["rev-parse", "--verify", "--quiet", "HEAD"], cwd=served_root)
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


async def _discover(served_root: Path) -> tuple[RepoContext | None, GitRepoInfo]:
    """Run the discovery commands, uncached."""
    if git_executable() is None:
        return None, _negative("no_git")

    try:
        raw = await run_git(["rev-parse", "--show-toplevel"], cwd=served_root)
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
        log.warning("git repository discovery failed in %s: %s", served_root, exc)
        return None, _negative("git_failed")

    toplevel = raw.decode("utf-8", errors="replace").strip()
    if not toplevel:
        return None, _negative("not_a_repo")

    git_root = Path(toplevel)
    try:
        head = await _resolve_head(served_root)
    except GitError as exc:
        log.warning("git HEAD resolution failed in %s: %s", served_root, exc)
        return None, _negative("git_failed")

    context = RepoContext(git_root=git_root, served_root=served_root, head=head)
    return context, GitRepoInfo(
        is_repo=True,
        root=_repo_root_relative_to_served(git_root, served_root),
        head=head,
    )


def _repo_root_relative_to_served(git_root: Path, served_root: Path) -> str | None:
    """The repo root as a served-root-relative path, or ``None`` if above it.

    ``""`` means the served root *is* the repository root. ``None`` means
    a subdirectory of a checkout is being served, so the repository root
    has no representation inside the served tree — the browser uses this
    to explain why some changed files are not navigable.
    """
    if git_root == served_root:
        return ""
    try:
        return str(git_root.relative_to(served_root))
    except ValueError:
        return None


async def repo_info(served_root: Path) -> tuple[RepoContext | None, GitRepoInfo]:
    """Resolve the repository for *served_root*, TTL-cached.

    Returns ``(context, info)``. ``context`` is ``None`` exactly when
    ``info["is_repo"]`` is false; callers that need to run git branch on
    the context, and return ``info`` unchanged when it is absent.
    """
    key = str(served_root)
    now = time.monotonic()
    cached = _REPO_CACHE.get(key)
    if cached is not None and cached[0] > now:
        cached_context = cached[1]
        # The first commit is the one identity transition that can happen
        # without a checkout. Keeping an unborn entry until the TTL would
        # make both /repo and /log lie after that commit was created.
        if cached_context is None or not cached_context.head["unborn"]:
            return cached_context, cached[2]

    context, info = await _discover(served_root)
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
