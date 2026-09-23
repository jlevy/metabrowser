"""Split a web URL's ref-and-path against a mirror and resolve it to one commit.

A URL such as ``…/tree/release/v1/docs`` cannot be split by reading it: the ref may be
``release``, ``release/v1``, or ``release/v1/docs``. Only the mirror knows, so each
split is a candidate, up to :data:`MAX_REF_CANDIDATES`, and each candidate that passes
Git's ref-name rules is checked with ``show-ref --verify`` against the exact ref it would
be. The precedence is branch (``refs/remotes/origin/<name>``), then tag
(``refs/tags/<name>``), then a full or abbreviated commit ID in the first segment. A
store cannot hold both ``a`` and ``a/b`` in one namespace, so at most one candidate per
namespace matches and the order of lengths does not matter.

User text never reaches ``rev-parse`` revision syntax, which would evaluate ``:/text``,
``@{…}``, or ``^{/…}``: a ref name is only ever an exact ``show-ref --verify`` argument
after ``--``, and a commit ID is validated hexadecimal, expanded with
``rev-parse --disambiguate`` (a prefix listing, not revision syntax) and each full ID
typed with ``cat-file -t``.

An unresolved answer says whether one fetch could change it. Serving turns that into one
background refresh and a typed pending state; the one-shot CLI reads the mirror as it
is and reports it not found.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal

from metabrowser.cache.urls import RepositorySelection
from metabrowser.git.process import (
    STORE_READ_POLICY,
    GitCommandError,
    RepositoryStoreTarget,
    run_git,
)
from metabrowser.git.wire import is_full_revision

# Candidates tried per URL, one per leading path segment. A miss costs one
# ``show-ref --verify`` spawn per candidate per namespace, so a URL that matches nothing
# costs twice the cap; a match stops at the first candidate that exists, which for a
# typical ``blob/<branch>/…`` URL is the first. Measured 2026-09-23 on macOS against a
# store with 2,000 packed refs, under load average 36: 22 to 24 ms per spawn, found or
# not (``git --version`` alone took 30 ms under the same load). Twelve candidates bound
# a miss at 24 spawns, about 0.6 s under that load. Git bounds no ref depth, but a
# GitHub branch or tag name with more than eleven slashes is not one this needs to open.
MAX_REF_CANDIDATES: Final[int] = 12

# An abbreviated ID that matches more objects than this is reported ambiguous rather
# than typed one ``cat-file -t`` spawn at a time. Four hexadecimal digits match about
# 150 objects in a ten-million-object repository; the seven GitHub shows match one.
MAX_DISAMBIGUATION_OBJECTS: Final[int] = 8

BRANCH_REF_PREFIX: Final = "refs/remotes/origin/"
TAG_REF_PREFIX: Final = "refs/tags/"
_COMMIT_ID = re.compile(r"^[0-9a-f]{4,64}$")
_REF_FORBIDDEN = frozenset(" ~^:?*[\\\x7f")

type ResolvedVia = Literal["default", "branch", "tag", "commit", "pull_request"]
type UnresolvedReason = Literal[
    "ref_not_found", "commit_not_found", "commit_ambiguous", "not_a_commit", "invalid_ref"
]


@dataclass(frozen=True, slots=True)
class RefCandidate:
    """One split of a ref-and-path: a short ref name and the path after it."""

    name: str
    path: tuple[bytes, ...]


@dataclass(frozen=True, slots=True)
class ResolvedSelection:
    """The commit a selection pins, how it was found, and the path within it."""

    via: ResolvedVia
    name: str | None
    ref: str | None
    commit: str
    path: tuple[bytes, ...] = ()


@dataclass(frozen=True, slots=True)
class UnresolvedSelection:
    """No commit in the mirror answers the selection."""

    reason: UnresolvedReason

    @property
    def needs_fetch(self) -> bool:
        """Whether one fetch could change the answer: the ref or commit may be newer."""

        return self.reason in {"ref_not_found", "commit_not_found"}


type SelectionResolution = ResolvedSelection | UnresolvedSelection


def is_valid_ref_name(name: str) -> bool:
    """Git's ``check-ref-format`` rules for a short branch or tag name.

    No empty component, none that begins with ``.`` or ends with ``.lock``; no ``..``,
    ``@{``, control character, space, ``~ ^ : ? * [ \\``; not ``@`` alone; and no ``.``
    or ``/`` at the end.
    """

    if not name or name == "@" or name.endswith((".", "/")) or name.startswith("/"):
        return False
    if ".." in name or "@{" in name:
        return False
    if any(ord(ch) < 0x20 or ch in _REF_FORBIDDEN for ch in name):
        return False
    return all(
        part and not part.startswith(".") and not part.endswith(".lock") for part in name.split("/")
    )


def ref_candidates(
    segments: tuple[bytes, ...], *, cap: int = MAX_REF_CANDIDATES
) -> tuple[RefCandidate, ...]:
    """One candidate per leading segment count, up to *cap*, that is a valid ref name."""

    found: list[RefCandidate] = []
    for length in range(1, min(len(segments), cap) + 1):
        try:
            name = b"/".join(segments[:length]).decode("utf-8")
        except UnicodeDecodeError:
            # Every longer candidate contains the same undecodable segment.
            break
        if is_valid_ref_name(name):
            found.append(RefCandidate(name, segments[length:]))
    return tuple(found)


async def _git(target: RepositoryStoreTarget, args: list[str]) -> bytes:
    return await run_git(args, target=target, policy=STORE_READ_POLICY)


async def _verified_oid(target: RepositoryStoreTarget, ref: str) -> str | None:
    """The object a ref names, peeled through annotated tags, or ``None``."""

    try:
        out = await _git(target, ["show-ref", "--verify", "--dereference", "--", ref])
    except GitCommandError:
        return None
    oid: str | None = None
    for line in out.decode("ascii", errors="replace").splitlines():
        value, _, name = line.partition(" ")
        if name in {ref, f"{ref}^{{}}"} and is_full_revision(value):
            oid = value
    return oid


async def _object_type(target: RepositoryStoreTarget, oid: str) -> str | None:
    """The type of a full object ID the store has, or ``None``."""

    try:
        return (await _git(target, ["cat-file", "-t", oid])).decode("ascii", "replace").strip()
    except GitCommandError:
        return None


async def _commit_at(target: RepositoryStoreTarget, ref: str) -> str | UnresolvedSelection | None:
    oid = await _verified_oid(target, ref)
    if oid is None:
        return None
    if await _object_type(target, oid) != "commit":
        return UnresolvedSelection("not_a_commit")
    return oid


async def resolve_commit_id(
    target: RepositoryStoreTarget, commit_id: str
) -> ResolvedSelection | UnresolvedSelection:
    """Expand a full or abbreviated hexadecimal commit ID that the store has."""

    text = commit_id.lower()
    if not _COMMIT_ID.match(text):
        return UnresolvedSelection("invalid_ref")
    try:
        listed = await _git(target, ["rev-parse", f"--disambiguate={text}"])
    except GitCommandError:
        return UnresolvedSelection("commit_not_found")
    oids = tuple(
        line for line in listed.decode("ascii", errors="replace").split() if is_full_revision(line)
    )
    if len(oids) > MAX_DISAMBIGUATION_OBJECTS:
        return UnresolvedSelection("commit_ambiguous")
    commits = [oid for oid in oids if await _object_type(target, oid) == "commit"]
    if len(commits) > 1:
        return UnresolvedSelection("commit_ambiguous")
    if not commits:
        return UnresolvedSelection("not_a_commit" if oids else "commit_not_found")
    return ResolvedSelection(via="commit", name=None, ref=None, commit=commits[0])


async def resolve_ref_and_path(
    target: RepositoryStoreTarget, segments: tuple[bytes, ...]
) -> ResolvedSelection | UnresolvedSelection:
    """Split *segments* into a ref and a path by what the mirror has.

    A leading ``refs/heads/`` or ``refs/tags/`` limits the search to that namespace,
    as GitHub's own URLs do.
    """

    namespaces: tuple[tuple[ResolvedVia, str], ...] = (
        ("branch", BRANCH_REF_PREFIX),
        ("tag", TAG_REF_PREFIX),
    )
    rest = segments
    explicit = segments[:2]
    if explicit == (b"refs", b"heads"):
        namespaces, rest = namespaces[:1], segments[2:]
    elif explicit == (b"refs", b"tags"):
        namespaces, rest = namespaces[1:], segments[2:]
    candidates = ref_candidates(rest)
    for via, prefix in namespaces:
        for candidate in candidates:
            found = await _commit_at(target, prefix + candidate.name)
            if isinstance(found, UnresolvedSelection):
                return found
            if found is not None:
                return ResolvedSelection(
                    via=via,
                    name=candidate.name,
                    ref=prefix + candidate.name,
                    commit=found,
                    path=candidate.path,
                )
    if len(namespaces) == 2 and rest:
        try:
            first = rest[0].decode("ascii")
        except UnicodeDecodeError:
            first = ""
        if _COMMIT_ID.match(first.lower()):
            resolved = await resolve_commit_id(target, first)
            if isinstance(resolved, ResolvedSelection):
                return ResolvedSelection(
                    via="commit", name=None, ref=None, commit=resolved.commit, path=rest[1:]
                )
            if resolved.reason != "commit_not_found":
                return resolved
    return UnresolvedSelection("ref_not_found")


async def resolve_selection(
    target: RepositoryStoreTarget,
    selection: RepositorySelection,
    *,
    default_ref: str,
    default_revision: str,
) -> ResolvedSelection | UnresolvedSelection:
    """The commit and path a URL selection pins in the store at *target*.

    A repository URL pins the default branch. A pull-request URL pins its head, which
    only its record names, so callers open the pull request through its provider first
    (``cli/selection.py``); asked here, it answers the default branch. Reading only,
    from the mirror as it is: the integration point for serving is to start one
    background refresh when the answer ``needs_fetch`` and resolve again once it
    finishes.
    """

    if selection.kind in {"tree", "blob"}:
        return await resolve_ref_and_path(target, selection.ref_and_path)
    if selection.kind == "commit" and selection.commit is not None:
        return await resolve_commit_id(target, selection.commit)
    name = default_ref.removeprefix(BRANCH_REF_PREFIX)
    return ResolvedSelection(via="default", name=name, ref=default_ref, commit=default_revision)


__all__ = [
    "BRANCH_REF_PREFIX",
    "MAX_DISAMBIGUATION_OBJECTS",
    "MAX_REF_CANDIDATES",
    "TAG_REF_PREFIX",
    "RefCandidate",
    "ResolvedSelection",
    "SelectionResolution",
    "UnresolvedSelection",
    "is_valid_ref_name",
    "ref_candidates",
    "resolve_commit_id",
    "resolve_ref_and_path",
    "resolve_selection",
]
