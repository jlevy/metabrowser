"""Open a pinned commit in a published worktree-free store, and resolve what to pin.

A store is a read-only mirror: acquisition fetches every object, nothing runs ``gc``,
``prune``, or ``repack`` on it, and Metabrowser writes no ref into it. A commit that is
in the store therefore stays readable, so opening one only proves it is there and
builds the :class:`~metabrowser.git.tree_source.GitRevisionSubject`. Nothing is written
and no lock is held, which is also why a cache hit opens from a home the process cannot
write. This module does not serve content or check out a worktree.

:func:`resolve_pin` turns a reader's selection -- a branch, a tag, or a commit ID --
into the commit to pin, reading the mirror alone. Selection text never reaches
``rev-parse`` revision syntax: a ref name is checked against Git's ref-name rules and
looked up with ``show-ref --verify`` on exact candidate refs, and a commit ID is
validated hexadecimal, which cannot spell ``:/text``, ``@{…}``, or ``^{/…}``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from metabrowser.cache.origin import BRANCH_MIRROR_PREFIX, TAG_PREFIX
from metabrowser.cache.paths import store_directory
from metabrowser.git.process import (
    GIT_DISABLE_MAILMAP_ARGS,
    STORE_READ_POLICY,
    GitCommandError,
    RepositoryStoreTarget,
    repository_store_target,
    run_git,
)
from metabrowser.git.tree_source import (
    GitObjectUnavailableError,
    GitRevisionSubject,
    git_revision_subject,
    require_full_oid,
)
from metabrowser.git.wire import is_full_revision
from metabrowser.mirror_refresh import (
    AmbiguousSelectionError,
    InvalidSelectionError,
    SelectionNotFoundError,
)

# Git's own bound on a ref name is the file system's; this is the record bound for one.
_REF_NAME_MAX_BYTES: Final = 1024
# Characters Git's ref-name rules forbid anywhere (git-check-ref-format(1), rules 4-5).
_REF_FORBIDDEN: Final = frozenset(" ~^:?*[\\")
# Seven hexadecimal digits is the shortest commit ID Git abbreviates to by default and
# the shortest a GitHub URL shows; anything shorter matches too much to mean one commit.
_COMMIT_ID_RE: Final = re.compile(r"[0-9a-f]{7,64}")
# An abbreviated ID that names more objects than this is reported as ambiguous without
# checking each one's type.
_MAX_ABBREVIATION_CANDIDATES: Final = 16


@dataclass(frozen=True, slots=True)
class ResolvedPin:
    """The commit a selection names, and the mirror ref it was found through, if any."""

    commit_oid: str
    ref: str | None


def _store_target(home: Path, store_key: str) -> RepositoryStoreTarget:
    return repository_store_target(git_dir=home / store_directory(store_key) / "repository.git")


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
    target = _store_target(home, store_key)
    if await _object_type(target, oid) != "commit":
        raise GitObjectUnavailableError(oid)
    return await git_revision_subject(
        target=target, commit_oid=oid, store_identity=store_identity, ref=ref
    )


def is_valid_ref_name(ref: str) -> bool:
    """Whether *ref* satisfies Git's ref-name rules for a full name under ``refs/``.

    The rules of git-check-ref-format(1), checked here rather than by running Git so a
    name is refused before any process sees it: no component starts with ``.`` or ends
    with ``.lock``; no ``..``, ``@{``, control character, space, or any of ``~^:?*[\\``;
    no leading, trailing, or doubled ``/``; no trailing ``.``; and not ``@``.
    """

    try:
        encoded = ref.encode("utf-8")
    except UnicodeEncodeError:
        return False
    if not ref.startswith("refs/") or len(encoded) > _REF_NAME_MAX_BYTES:
        return False
    if ref.endswith(("/", ".")) or "//" in ref or ".." in ref or "@{" in ref:
        return False
    if any(ord(char) < 0x20 or ord(char) == 0x7F or char in _REF_FORBIDDEN for char in ref):
        return False
    return all(
        component and not component.startswith(".") and not component.endswith(".lock")
        for component in ref.split("/")
    )


def mirror_ref_candidates(name: str) -> tuple[str, ...]:
    """The mirror refs a reader's ref name can mean, in precedence order.

    A short name is a branch of the origin first and a tag second. A full name must be
    in one of those two namespaces, because they are the only refs a mirror holds.
    Raises :class:`InvalidSelectionError` for a name Git would not accept.
    """

    if name.startswith("refs/"):
        if not name.startswith((BRANCH_MIRROR_PREFIX, TAG_PREFIX)):
            raise InvalidSelectionError(
                "only the origin's branches (refs/remotes/origin/…) and tags (refs/tags/…) "
                "can be pinned"
            )
        candidates: tuple[str, ...] = (name,)
    else:
        candidates = (BRANCH_MIRROR_PREFIX + name, TAG_PREFIX + name)
    if not all(is_valid_ref_name(candidate) for candidate in candidates):
        raise InvalidSelectionError("the ref is not a valid Git ref name")
    return candidates


async def _object_type(target: RepositoryStoreTarget, oid: str) -> str | None:
    """The type of the object *oid* names, or ``None`` when the store has none.

    *oid* is validated hexadecimal, so ``cat-file`` sees an object name, never syntax.
    """

    try:
        kind = await run_git(
            [*GIT_DISABLE_MAILMAP_ARGS, "cat-file", "-t", oid],
            target=target,
            policy=STORE_READ_POLICY,
        )
    except GitCommandError:
        return None
    return kind.decode("ascii", errors="replace").strip()


async def ref_tip(target: RepositoryStoreTarget, ref: str) -> str | None:
    """The commit *ref* names in the store, peeling an annotated tag.

    ``None`` when the ref does not exist -- never fetched, or pruned after the origin
    deleted it -- or names something other than a commit. *ref* is an exact full ref
    name; ``show-ref --verify`` never expands it.
    """

    if not is_valid_ref_name(ref):
        return None
    try:
        shown = await run_git(
            [*GIT_DISABLE_MAILMAP_ARGS, "show-ref", "--verify", "--dereference", "--", ref],
            target=target,
            policy=STORE_READ_POLICY,
        )
    except GitCommandError:
        return None
    direct: str | None = None
    peeled: str | None = None
    for line in shown.decode("utf-8", errors="replace").splitlines():
        value, _, name = line.partition(" ")
        if name == ref:
            direct = value
        elif name == ref + "^{}":
            peeled = value
    candidate = peeled if peeled is not None else direct
    if candidate is None or not is_full_revision(candidate):
        return None
    return candidate if await _object_type(target, candidate) == "commit" else None


async def _resolve_commit_id(target: RepositoryStoreTarget, text: str) -> str:
    value = text.lower()
    if _COMMIT_ID_RE.fullmatch(value) is None:
        raise InvalidSelectionError(
            "a commit ID is 7 to 64 hexadecimal digits; a ref name follows Git's ref-name rules"
        )
    if is_full_revision(value):
        if await _object_type(target, value) != "commit":
            raise SelectionNotFoundError("no commit with that ID is in the mirror")
        return value
    # An option value, not revision syntax: Git lists every object whose ID starts
    # with the prefix, and nothing in validated hexadecimal can be evaluated.
    listed = await run_git(
        [*GIT_DISABLE_MAILMAP_ARGS, "rev-parse", f"--disambiguate={value}"],
        target=target,
        policy=STORE_READ_POLICY,
    )
    names = [line for line in listed.decode("ascii", errors="replace").split() if line]
    if len(names) > _MAX_ABBREVIATION_CANDIDATES:
        raise AmbiguousSelectionError("that abbreviated commit ID matches several objects")
    commits = [
        name
        for name in names
        if is_full_revision(name) and await _object_type(target, name) == "commit"
    ]
    if not commits:
        raise SelectionNotFoundError("no commit with that ID is in the mirror")
    if len(commits) > 1:
        raise AmbiguousSelectionError("that abbreviated commit ID matches several commits")
    return commits[0]


async def resolve_pin(
    target: RepositoryStoreTarget, *, ref: str | None = None, oid: str | None = None
) -> ResolvedPin:
    """The commit a reader's selection names in the mirror, and the ref it came through.

    Exactly one of *ref* and *oid* is given. A ref name is tried as a branch, then as a
    tag, and then, when it is hexadecimal, as a commit ID; *oid* is only a commit ID,
    full or abbreviated to at least seven digits. A commit pinned by ID has no ref.
    Raises a :class:`~metabrowser.mirror_refresh.SelectionError`; Git failures other than "not there"
    propagate as :class:`~metabrowser.git.process.GitError`.
    """

    if (ref is None) == (oid is None):
        raise InvalidSelectionError('give exactly one of "ref" and "oid"')
    if ref is not None:
        if not ref:
            raise InvalidSelectionError("the ref is empty")
        try:
            candidates = mirror_ref_candidates(ref)
        except InvalidSelectionError:
            if _COMMIT_ID_RE.fullmatch(ref.lower()) is None:
                raise
            candidates = ()
        for candidate in candidates:
            tip = await ref_tip(target, candidate)
            if tip is not None:
                return ResolvedPin(commit_oid=tip, ref=candidate)
        if _COMMIT_ID_RE.fullmatch(ref.lower()) is None:
            raise SelectionNotFoundError("no branch or tag with that name is in the mirror")
        return ResolvedPin(commit_oid=await _resolve_commit_id(target, ref), ref=None)
    assert oid is not None
    return ResolvedPin(commit_oid=await _resolve_commit_id(target, oid), ref=None)


__all__ = [
    "ResolvedPin",
    "is_valid_ref_name",
    "mirror_ref_candidates",
    "open_revision",
    "ref_tip",
    "resolve_pin",
]
