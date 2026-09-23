"""Open a pinned commit in a published worktree-free store.

A store is a read-only mirror: acquisition fetches every object, nothing runs ``gc``,
``prune``, or ``repack`` on it, and Metabrowser writes no ref into it. A commit that is
in the store therefore stays readable, so opening one only proves it is there and
builds the :class:`~metabrowser.git.tree_source.GitRevisionSubject`. Nothing is written
and no lock is held, which is also why a cache hit opens from a home the process cannot
write. This module does not serve content or check out a worktree.
"""

from __future__ import annotations

from pathlib import Path

from metabrowser.cache.paths import store_directory
from metabrowser.git.process import (
    GIT_DISABLE_MAILMAP_ARGS,
    STORE_READ_POLICY,
    GitCommandError,
    repository_store_target,
    run_git,
)
from metabrowser.git.tree_source import (
    GitObjectUnavailableError,
    GitRevisionSubject,
    git_revision_subject,
    require_full_oid,
)


async def open_revision(
    *,
    home: Path,
    store_key: str,
    commit_oid: str,
    store_identity: str,
    ref: str | None = None,
) -> GitRevisionSubject:
    """Pin *commit_oid* in the published store *store_key* under *home*.

    *ref* is the store ref the commit was resolved from, recorded on the subject as
    its label; the pin itself is the commit.

    Raises :class:`~metabrowser.git.tree_source.GitPathError` for an abbreviated
    object ID, :class:`~metabrowser.git.process.GitUnavailableError` when the store
    directory is absent, and :class:`GitObjectUnavailableError` when the store has no
    such commit.
    """

    oid = require_full_oid(commit_oid)
    target = repository_store_target(git_dir=home / store_directory(store_key) / "repository.git")
    try:
        kind = await run_git(
            [*GIT_DISABLE_MAILMAP_ARGS, "cat-file", "-t", oid],
            target=target,
            policy=STORE_READ_POLICY,
        )
    except GitCommandError as exc:
        raise GitObjectUnavailableError(oid) from exc
    if kind.strip() != b"commit":
        raise GitObjectUnavailableError(oid)
    return await git_revision_subject(
        target=target, commit_oid=oid, store_identity=store_identity, ref=ref
    )


__all__ = ["open_revision"]
