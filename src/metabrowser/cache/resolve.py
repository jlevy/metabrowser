"""Resolve what a reader selects -- a URL's ref-and-path, a ref, a commit ID -- in a mirror.

This is the one resolver: URL opening (:func:`resolve_selection`), the pin route
(:func:`resolve_pin`), and the refresh and status reads (:func:`ref_tip`) all look refs
up the same way.

A URL such as ``…/tree/release/v1/docs`` cannot be split by reading it: the ref may be
``release``, ``release/v1``, or ``release/v1/docs``. Only the mirror knows, so each
split is a candidate, up to :data:`MAX_REF_CANDIDATES`. Every candidate that passes
Git's ref-name rules is looked up in one ``for-each-ref``, which lists refs by the names
the store holds, and only an exact, case-sensitive match counts. The precedence is branch
(``refs/remotes/origin/<name>``), then tag (``refs/tags/<name>``), then a full or
abbreviated commit ID in the first segment; a first segment ``HEAD`` is the default
branch. A store cannot hold both ``a`` and ``a/b`` in one namespace, so at most one
candidate per namespace matches and the order of lengths does not matter.

User text never reaches ``rev-parse`` revision syntax, which would evaluate ``:/text``,
``@{…}``, or ``^{/…}``: a ref name is only ever a ``for-each-ref`` pattern after ``--``
that cannot hold a wildcard, and a commit ID is validated hexadecimal, expanded with
``rev-parse --disambiguate`` (a prefix listing, not revision syntax) and each full ID
typed with ``cat-file -t``.

An unresolved answer says whether one fetch could change it. Serving turns that into one
background refresh and a typed pending state; the one-shot CLI reads the mirror as it
is and reports it not found. The pin route's answers are
:class:`~metabrowser.mirror_refresh.SelectionError` subclasses.
"""

from __future__ import annotations

import bisect
import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Final, Literal

from metabrowser.cache.origin import BRANCH_MIRROR_PREFIX, TAG_PREFIX
from metabrowser.cache.repository_store import object_type
from metabrowser.cache.urls import RepositorySelection
from metabrowser.git.process import (
    STORE_READ_POLICY,
    GitCommandError,
    RepositoryStoreTarget,
    run_git,
)
from metabrowser.git.tree_source import display_segment
from metabrowser.git.wire import is_full_revision
from metabrowser.mirror_refresh import (
    AmbiguousSelectionError,
    InvalidSelectionError,
    SelectionNotFoundError,
)

# Candidates tried per URL, one per leading path segment, all in one ``for-each-ref``.
# The cap bounds the patterns and the refs they list, not spawns. Git bounds no ref
# depth, but a GitHub branch or tag name with more than eleven slashes is not one this
# needs to open.
MAX_REF_CANDIDATES: Final[int] = 12

# An abbreviated ID that names more objects than this is reported as ambiguous
# without checking each one's type, one ``cat-file -t`` spawn at a time.
MAX_DISAMBIGUATION_OBJECTS: Final[int] = 16
# Git's own bound on a ref name is the file system's; this is the record bound for one.
_REF_NAME_MAX_BYTES: Final = 1024

_REF_FORMAT: Final = "%(refname)%00%(objectname)%00%(objecttype)%00%(*objectname)%00%(*objecttype)"
# Seven hexadecimal digits is the shortest commit ID Git abbreviates to by default and
# the shortest a GitHub URL shows; anything shorter matches too much to mean one commit.
_COMMIT_ID = re.compile(r"^[0-9a-f]{7,64}$")
_REF_FORBIDDEN = frozenset(" ~^:?*[\\\x7f")

type ResolvedVia = Literal["default", "branch", "tag", "commit"]
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
    """Git's ``check-ref-format`` rules, for a short name or a full one under ``refs/``.

    No empty component, none that begins with ``.`` or ends with ``.lock``; no ``..``,
    ``@{``, control character, space, ``~ ^ : ? * [ \\``; not ``@`` alone; no ``.`` or
    ``/`` at the end; encodable as UTF-8 and at most 1024 bytes. Checked here rather
    than by running Git, so a name is refused before any process sees it.
    """

    try:
        encoded = name.encode("utf-8")
    except UnicodeEncodeError:
        return False
    if len(encoded) > _REF_NAME_MAX_BYTES:
        return False
    if not name or name == "@" or name.endswith((".", "/")) or name.startswith("/"):
        return False
    if ".." in name or "@{" in name:
        return False
    if any(ord(ch) < 0x20 or ch in _REF_FORBIDDEN for ch in name):
        return False
    return all(
        part and not part.startswith(".") and not part.endswith(".lock") for part in name.split("/")
    )


def _folded(name: str) -> str:
    """How a case- and normalization-insensitive filesystem compares a name, as APFS does."""

    return unicodedata.normalize("NFD", unicodedata.normalize("NFD", name).casefold())


def case_colliding_refs(names: Iterable[str]) -> tuple[str, ...]:
    """Ref names a case-insensitive filesystem cannot hold apart, sorted.

    Two names collide when they fold to the same name, or when one folds to a directory
    of the other (``Release`` and ``release/v1``) while differing in case.
    """

    by_fold: dict[str, set[str]] = {}
    for name in names:
        by_fold.setdefault(_folded(name), set()).add(name)
    colliding: set[str] = set()
    for group in by_fold.values():
        if len(group) > 1:
            colliding |= group
    folds = sorted(by_fold)
    for fold in folds:
        start = bisect.bisect_left(folds, fold + "/")
        for below in folds[start:]:
            if not below.startswith(fold + "/"):
                break
            for upper in by_fold[fold]:
                for lower in by_fold[below]:
                    if not lower.startswith(upper + "/"):
                        colliding |= {upper, lower}
    return tuple(sorted(colliding))


def folded_refs(written: Mapping[str, str], held: Mapping[str, str]) -> tuple[str, ...]:
    """Refs a fetch wrote that the store does not hold as written, and refs it cannot hold apart.

    *written* is what ``fetch --porcelain`` reports it wrote, name to object; *held* is
    every ref the store lists by exact name afterwards. On a case-insensitive
    filesystem a loose ref is a file, so a fetch that writes ``SAME`` beside an
    unchanged ``same`` writes into ``same``'s file: Git reports ``SAME`` written, the
    store lists only ``same``, now naming ``SAME``'s commit, and nothing fails. A
    written ref the store does not list at that object is such a fold. A loose ref
    whose name folds onto a packed one shadows it on every read, so names in *held*
    that collide count too. Sorted; empty when the store holds exactly what was written.
    """

    folded = {name for name, oid in written.items() if held.get(name) != oid}
    return tuple(sorted(folded.union(case_colliding_refs(held))))


def describe_case_collision(colliding: tuple[str, ...]) -> str:
    """What a case collision is, naming a few of the refs, for a user message."""

    shown = ", ".join(
        display_segment(name.encode("utf-8", "surrogateescape")) for name in colliding[:4]
    )
    more = f" and {len(colliding) - 4} more" if len(colliding) > 4 else ""
    return (
        f"has branches or tags whose names differ only in letter case ({shown}{more}), "
        "which this filesystem cannot keep apart (ref_case_collision)"
    )


async def store_ignores_case(target: RepositoryStoreTarget) -> bool:
    """Whether Git found the store's filesystem case-insensitive when it created it."""

    try:
        value = await run_git(
            ["config", "--get", "--bool", "core.ignorecase"],
            target=target,
            policy=STORE_READ_POLICY,
        )
    except GitCommandError:
        return False
    return value.strip() == b"true"


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


@dataclass(frozen=True, slots=True)
class _RefObject:
    """What one ref names: its object, and the object an annotated tag points at."""

    oid: str
    kind: str
    peeled_oid: str | None
    peeled_kind: str | None


async def _exact_refs(target: RepositoryStoreTarget, refs: list[str]) -> dict[str, _RefObject]:
    """The refs among *refs* that the store holds under exactly that name.

    One ``for-each-ref`` for every candidate. It lists refs by the names the ref store
    holds, where ``show-ref --verify`` looks a loose ref up as a path: on a
    case-insensitive filesystem that finds ``refs/remotes/origin/topic`` for ``TOPIC``,
    and GitHub, whose refs are case-sensitive, has no branch ``TOPIC``. A pattern also
    lists refs below it, so only exact names are kept.
    """

    if not refs:
        return {}
    out = await _git(target, ["for-each-ref", f"--format={_REF_FORMAT}", "--", *refs])
    wanted = set(refs)
    found: dict[str, _RefObject] = {}
    for line in out.split(b"\n"):
        fields = line.decode("utf-8", "surrogateescape").split("\0")
        if len(fields) != 5 or fields[0] not in wanted or not is_full_revision(fields[1]):
            continue
        peeled = fields[3] if is_full_revision(fields[3]) else None
        found[fields[0]] = _RefObject(fields[1], fields[2], peeled, fields[4] or None)
    return found


async def mirror_refs(target: RepositoryStoreTarget) -> dict[str, str]:
    """Every branch and tag the store holds, by the exact name it lists, with its object."""

    out = await _git(
        target,
        [
            "for-each-ref",
            "--format=%(refname)%00%(objectname)",
            "--",
            BRANCH_MIRROR_PREFIX,
            TAG_PREFIX,
        ],
    )
    held: dict[str, str] = {}
    for line in out.split(b"\n"):
        fields = line.decode("utf-8", "surrogateescape").split("\0")
        if len(fields) == 2 and is_full_revision(fields[1]):
            held[fields[0]] = fields[1]
    return held


async def _peeled_commit(target: RepositoryStoreTarget, ref: _RefObject) -> str | None:
    """The commit a ref names, through any chain of annotated tags, or ``None``."""

    if ref.kind == "commit":
        return ref.oid
    if ref.kind != "tag" or ref.peeled_oid is None:
        return None
    if ref.peeled_kind == "commit":
        return ref.peeled_oid
    if ref.peeled_kind != "tag":
        return None
    # A tag of a tag: peel the rest of the chain. The argument is a full object ID
    # Git printed, never text from the URL.
    try:
        out = await _git(
            target,
            ["rev-parse", "--verify", "--quiet", "--end-of-options", f"{ref.peeled_oid}^{{}}"],
        )
    except GitCommandError:
        return None
    oid = out.decode("ascii", "replace").strip()
    return oid if is_full_revision(oid) and await object_type(target, oid) == "commit" else None


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
    commits = [oid for oid in oids if await object_type(target, oid) == "commit"]
    if len(commits) > 1:
        return UnresolvedSelection("commit_ambiguous")
    if not commits:
        return UnresolvedSelection("not_a_commit" if oids else "commit_not_found")
    return ResolvedSelection(via="commit", name=None, ref=None, commit=commits[0])


async def ref_tip(target: RepositoryStoreTarget, ref: str) -> str | None:
    """The commit the full ref *ref* names, peeling annotated tags; ``None`` otherwise.

    ``None`` when the ref does not exist under exactly that name -- never fetched, or
    pruned after the origin deleted it -- or names something other than a commit.
    """

    if not ref.startswith("refs/") or not is_valid_ref_name(ref):
        return None
    found = (await _exact_refs(target, [ref])).get(ref)
    return None if found is None else await _peeled_commit(target, found)


@dataclass(frozen=True, slots=True)
class ResolvedPin:
    """The commit a pin request names, and the mirror ref it was found through, if any."""

    commit_oid: str
    ref: str | None


async def _pin_commit_id(target: RepositoryStoreTarget, text: str) -> str:
    resolved = await resolve_commit_id(target, text)
    if isinstance(resolved, ResolvedSelection):
        return resolved.commit
    if resolved.reason == "invalid_ref":
        raise InvalidSelectionError(
            "a commit ID is 7 to 64 hexadecimal digits; a ref name follows Git's ref-name rules"
        )
    if resolved.reason == "commit_ambiguous":
        raise AmbiguousSelectionError("that abbreviated commit ID matches several commits")
    raise SelectionNotFoundError("no commit with that ID is in the mirror")


async def resolve_pin(
    target: RepositoryStoreTarget, *, ref: str | None = None, oid: str | None = None
) -> ResolvedPin:
    """The commit a pin request names in the mirror, and the ref it came through.

    Exactly one of *ref* and *oid* is given. A short ref name is tried as a branch,
    then as a tag, and then, when it is hexadecimal, as a commit ID; a full name must
    be under ``refs/remotes/origin/`` or ``refs/tags/``, the only refs a mirror holds.
    *oid* is only a commit ID, full or abbreviated to at least seven digits. A commit
    pinned by ID has no ref. Raises a
    :class:`~metabrowser.mirror_refresh.SelectionError`; Git failures other than "not
    there" propagate as :class:`~metabrowser.git.process.GitError`.
    """

    if (ref is None) == (oid is None):
        raise InvalidSelectionError('give exactly one of "ref" and "oid"')
    if oid is not None:
        return ResolvedPin(commit_oid=await _pin_commit_id(target, oid), ref=None)
    assert ref is not None
    if not ref:
        raise InvalidSelectionError("the ref is empty")
    if ref.startswith("refs/"):
        if not ref.startswith((BRANCH_MIRROR_PREFIX, TAG_PREFIX)):
            raise InvalidSelectionError(
                "only the origin's branches (refs/remotes/origin/…) and tags (refs/tags/…) "
                "can be pinned"
            )
        candidates: tuple[str, ...] = (ref,)
    else:
        candidates = (BRANCH_MIRROR_PREFIX + ref, TAG_PREFIX + ref)
    is_hex = _COMMIT_ID.match(ref.lower()) is not None
    if all(is_valid_ref_name(candidate) for candidate in candidates):
        exact = await _exact_refs(target, list(candidates))
        for candidate in candidates:
            found = exact.get(candidate)
            commit = None if found is None else await _peeled_commit(target, found)
            if commit is not None:
                return ResolvedPin(commit_oid=commit, ref=candidate)
    elif not is_hex:
        raise InvalidSelectionError("the ref is not a valid Git ref name")
    if is_hex:
        return ResolvedPin(commit_oid=await _pin_commit_id(target, ref), ref=None)
    raise SelectionNotFoundError("no branch or tag with that name is in the mirror")


async def resolve_ref_and_path(
    target: RepositoryStoreTarget, segments: tuple[bytes, ...]
) -> ResolvedSelection | UnresolvedSelection:
    """Split *segments* into a ref and a path by what the mirror has.

    A leading ``refs/heads/`` or ``refs/tags/`` limits the search to that namespace,
    as GitHub's own URLs do.
    """

    namespaces: tuple[tuple[ResolvedVia, str], ...] = (
        ("branch", BRANCH_MIRROR_PREFIX),
        ("tag", TAG_PREFIX),
    )
    rest = segments
    explicit = segments[:2]
    if explicit == (b"refs", b"heads"):
        namespaces, rest = namespaces[:1], segments[2:]
    elif explicit == (b"refs", b"tags"):
        namespaces, rest = namespaces[1:], segments[2:]
    candidates = ref_candidates(rest)
    exact = await _exact_refs(
        target, [prefix + candidate.name for _via, prefix in namespaces for candidate in candidates]
    )
    for via, prefix in namespaces:
        for candidate in candidates:
            ref = exact.get(prefix + candidate.name)
            if ref is None:
                continue
            commit = await _peeled_commit(target, ref)
            if commit is None:
                return UnresolvedSelection("not_a_commit")
            return ResolvedSelection(
                via=via,
                name=candidate.name,
                ref=prefix + candidate.name,
                commit=commit,
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

    A repository or pull-request URL pins the default branch, and so does a tree or blob
    URL whose ref is ``HEAD``, as on GitHub. Reading only, from the mirror as it is: the
    integration point for serving is to start one background refresh when the answer
    ``needs_fetch`` and resolve again once it finishes.
    """

    name = default_ref.removeprefix(BRANCH_MIRROR_PREFIX)
    if selection.kind in {"tree", "blob"}:
        if selection.ref_and_path[:1] == (b"HEAD",):
            return ResolvedSelection(
                via="default",
                name=name,
                ref=default_ref,
                commit=default_revision,
                path=selection.ref_and_path[1:],
            )
        return await resolve_ref_and_path(target, selection.ref_and_path)
    if selection.kind == "commit" and selection.commit is not None:
        return await resolve_commit_id(target, selection.commit)
    return ResolvedSelection(via="default", name=name, ref=default_ref, commit=default_revision)


__all__ = [
    "MAX_DISAMBIGUATION_OBJECTS",
    "MAX_REF_CANDIDATES",
    "RefCandidate",
    "ResolvedPin",
    "ResolvedSelection",
    "SelectionResolution",
    "UnresolvedSelection",
    "case_colliding_refs",
    "describe_case_collision",
    "folded_refs",
    "is_valid_ref_name",
    "mirror_refs",
    "ref_candidates",
    "ref_tip",
    "resolve_commit_id",
    "resolve_pin",
    "resolve_ref_and_path",
    "resolve_selection",
    "store_ignores_case",
]
