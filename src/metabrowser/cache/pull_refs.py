"""Fetch a pull request's head into a published store and compute its comparison.

A pull request's commits, a fork's included, arrive through the origin's own
``refs/pull/<n>/head``, fetched into the same ref in the store: the one ref a store
holds beyond the origin's branches and tags. An open pull request's base branch is
fetched in the same command, into the ``refs/remotes/origin/<base>`` the mirror update
writes, so its merge base is computed against the base branch as it is now, as GitHub
computes Files changed. A closed or merged pull request's comparison starts from the
API's ``base.sha`` instead, fetched by ID when the mirror does not have it.

Every fetch is a network command on an acquisition-grade Git: :func:`remote_git_args`,
the isolated acquisition policy, its own process group, and the Git floor. Nothing here
writes a record or takes a cache lock.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from metabrowser.cache import acquire
from metabrowser.cache.paths import MAX_PULL_REQUEST_NUMBER
from metabrowser.cache.remote import classify_remote_failure, remote_git_args
from metabrowser.cache.resolve import BRANCH_REF_PREFIX, is_valid_ref_name
from metabrowser.git.process import (
    ACQUISITION_POLICY,
    STORE_READ_POLICY,
    GitCommandError,
    GitTimeoutError,
    RepositoryStoreTarget,
    repository_store_target,
    run_git,
)
from metabrowser.git.wire import is_full_revision

if TYPE_CHECKING:
    from metabrowser.cache.acquire import PublishedSource

type PullFetchFailure = Literal["not_found_or_private", "network_error", "fetch_failed"]


class PullRefError(Exception):
    """Git could not fetch or read a pull request's commits; ``state`` says why.

    The message names no path and carries none of Git's own text.
    """

    def __init__(self, state: PullFetchFailure | Literal["no_merge_base"], message: str) -> None:
        super().__init__(message)
        self.state = state


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


async def _fetch(published: PublishedSource, specs: list[str]) -> None:
    """``git fetch`` *specs* from the source's origin into its store."""

    # Through the acquisition module, so the Git floor and the origin URL have one seam
    # each for every command that fetches into a store.
    await asyncio.to_thread(acquire.require_acquisition_git)
    remote_url = acquire.remote_url_for(published.source)
    try:
        await run_git(
            [
                *remote_git_args(remote_url),
                "fetch",
                "--no-tags",
                "--no-write-fetch-head",
                "origin",
                *specs,
            ],
            target=_target(published),
            policy=ACQUISITION_POLICY,
        )
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
                "the origin has no such pull request, or Git has no credentials for it",
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


async def fetch_pull_head(
    published: PublishedSource, number: int, *, base_branch: str | None = None
) -> str | None:
    """Fetch ``refs/pull/<n>/head`` (and *base_branch*, if valid) and return the head.

    ``None`` means the fetch succeeded but the ref is not in the store.
    """

    ref = pull_head_ref(number)
    specs = [f"+{ref}:{ref}"]
    if base_branch is not None and is_valid_ref_name(base_branch):
        specs.append(f"+refs/heads/{base_branch}:{BRANCH_REF_PREFIX}{base_branch}")
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
    if open_pull and base_branch is not None and is_valid_ref_name(base_branch):
        base_commit = await ref_commit(published, BRANCH_REF_PREFIX + base_branch)
        if base_commit is not None:
            base_from = "base_branch"
    if base_commit is None:
        if not await has_commit(published, base_sha):
            await fetch_commit(published, base_sha)
        base_commit = base_sha
    try:
        out = await _read(published, ["merge-base", base_commit, head])
    except GitCommandError as exc:
        raise PullRefError("no_merge_base", "the base and head share no history") from exc
    merge_base = out.decode("ascii", errors="replace").strip()
    if not is_full_revision(merge_base):
        raise PullRefError("no_merge_base", "the base and head share no history")
    return PullEndpoints(base=merge_base, head=head, base_commit=base_commit, base_from=base_from)


__all__ = [
    "PullEndpoints",
    "PullFetchFailure",
    "PullRefError",
    "comparison_endpoints",
    "fetch_commit",
    "fetch_pull_head",
    "has_commit",
    "pull_head_ref",
    "ref_commit",
]
