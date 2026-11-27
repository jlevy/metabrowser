"""Resolve what a reader selects -- a URL's ref-and-path, a ref, a commit ID -- in a mirror.

This is the one resolver: URL opening (:func:`resolve_selection`), the pin route
(:func:`resolve_pin`), the refresh and status reads (:func:`ref_tip`), and the branch
and tag listing (:func:`list_mirror_refs`) all look refs up the same way.

A served checkout's own refs go through the same pin resolver and listing, with
:data:`CHECKOUT_REFS` naming where a checkout keeps its branches where :data:`MIRROR_REFS`
names a mirror's (:class:`RefNamespaces`), so a folder's ref selector resolves a name by
the rules a mirror's does.

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

import asyncio
import bisect
import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal

from metabrowser.cache.origin import BRANCH_MIRROR_PREFIX, TAG_PREFIX
from metabrowser.cache.repository_store import object_type
from metabrowser.cache.urls import RepositorySelection
from metabrowser.git.log import TRUNK_BRANCH_NAMES
from metabrowser.git.process import (
    STORE_READ_POLICY,
    GitCommandError,
    RepositoryStoreTarget,
    run_git,
)
from metabrowser.git.ref_names import is_valid_ref_name
from metabrowser.git.wire import is_full_revision
from metabrowser.invisible_chars import display_segment
from metabrowser.mirror_refresh import (
    AmbiguousSelectionError,
    InvalidSelectionError,
    MirrorRef,
    RefKind,
    SelectionNotACommitError,
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

_REF_FORMAT: Final = "%(refname)%00%(objectname)%00%(objecttype)%00%(*objectname)%00%(*objecttype)"
# Seven hexadecimal digits is the shortest commit ID Git abbreviates to by default and
# the shortest a GitHub URL shows; anything shorter matches too much to mean one commit.
# Always ``fullmatch``: ``$`` also matches before a trailing newline.
_COMMIT_ID = re.compile(r"[0-9a-f]{7,64}")
# The one ref a mirror holds beyond its origin's branches and tags, fetched with a pull
# request, whose number follows the GitHub URL grammar.
_PULL_REFS: Final = "refs/pull/"
_PULL_HEAD = re.compile(r"refs/pull/([1-9][0-9]{0,9})/head")

type ResolvedVia = Literal["default", "branch", "tag", "commit", "pull_request"]


@dataclass(frozen=True, slots=True)
class RefNamespaces:
    """Where a repository keeps the refs a reader can select, and what it is called.

    A mirror holds its origin's branches under ``refs/remotes/origin/`` and no
    remote-tracking branches of its own, plus the pull-request heads fetched into it. A
    checkout holds its local branches under ``refs/heads/`` and every remote's under
    ``refs/remotes/``. Tags are ``refs/tags/`` in both. ``where`` is how a refusal names
    the repository, ``no_head`` what ``HEAD`` is told when it names no branch, and
    ``pinnable`` what a full ref outside these namespaces is told.
    """

    branch: str
    tag: str
    remote: str | None
    pull_heads: bool
    where: str
    no_head: str
    pinnable: str

    def prefix(self, kind: RefKind) -> str | None:
        """The namespace *kind* lists, or ``None`` when the repository has no such list."""

        if kind == "branch":
            return self.branch
        return self.tag if kind == "tag" else self.remote

    @property
    def prefixes(self) -> tuple[str, ...]:
        """Every namespace a short name is tried in, in precedence order."""

        return tuple(prefix for prefix in (self.branch, self.tag, self.remote) if prefix)


MIRROR_REFS: Final = RefNamespaces(
    branch=BRANCH_MIRROR_PREFIX,
    tag=TAG_PREFIX,
    remote=None,
    pull_heads=True,
    where="the mirror",
    no_head="the mirror has recorded no default branch",
    pinnable=(
        "only the origin's branches (refs/remotes/origin/…), tags (refs/tags/…), "
        "and pull-request heads (refs/pull/<n>/head) can be pinned"
    ),
)
_REMOTE_REF_PREFIX: Final = "refs/remotes/"

CHECKOUT_REFS: Final = RefNamespaces(
    branch="refs/heads/",
    tag=TAG_PREFIX,
    remote=_REMOTE_REF_PREFIX,
    pull_heads=False,
    where="the checkout",
    no_head="the checkout is on no branch",
    pinnable=(
        "only branches (refs/heads/…), tags (refs/tags/…), and remote-tracking "
        "branches (refs/remotes/…) can be pinned"
    ),
)
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


def is_pinnable_ref(ref: str, namespaces: RefNamespaces = MIRROR_REFS) -> bool:
    """Whether *ref* is a full name the repository holds and a pin may be served under.

    In a mirror, the origin's branches (``refs/remotes/origin/…``), its tags
    (``refs/tags/…``), and a pull request's head (``refs/pull/<n>/head``); in a
    checkout, its branches, tags, and remote-tracking branches. Each a valid ref name.
    """

    return (
        ref.startswith(namespaces.prefixes)
        or (namespaces.pull_heads and _PULL_HEAD.fullmatch(ref) is not None)
    ) and is_valid_ref_name(ref)


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


def _spelled(name: str) -> str:
    """A ref name as Git spells it whatever the filesystem's normalization: NFC, case kept."""

    return unicodedata.normalize("NFC", name)


def folded_refs(
    *,
    before: Mapping[str, str],
    written: Mapping[str, str],
    pruned: Iterable[str],
    held: Mapping[str, str],
) -> tuple[str, ...]:
    """What a fetch broke by writing two refs into one file, sorted; empty when nothing.

    *before* and *held* are the refs the store listed before and after the fetch;
    *written* and *pruned* are what ``fetch --porcelain`` reports. On a
    case-insensitive filesystem a loose ref is a file, so a fetch that writes ``SAME``
    beside an unchanged ``same`` writes into ``same``'s file and succeeds. Two things
    show that, and only that:

    - a ref the store held before, which the fetch neither wrote nor pruned, no longer
      names its old object (``same`` now names ``SAME``'s commit);
    - a ref the fetch wrote is not held, at the object written, under any name the
      filesystem folds its name to (two written refs shared one file).

    Names are compared as the filesystem does, not byte for byte: a ref written as
    ``Feature/x`` into an existing ``feature/`` directory lists as ``feature/x``, and
    Git lists a decomposed ``zürich`` precomposed. A loose ref whose name folds onto a
    packed one shadows it on every read, so names in *held* that collide count too.
    """

    touched = {_spelled(name) for name in written} | {_spelled(name) for name in pruned}
    broken = {
        name
        for name, oid in before.items()
        if _spelled(name) not in touched and held.get(name) != oid
    }
    held_by_fold: dict[str, set[str]] = {}
    for name, oid in held.items():
        held_by_fold.setdefault(_folded(name), set()).add(oid)
    broken |= {
        name for name, oid in written.items() if oid not in held_by_fold.get(_folded(name), set())
    }
    return tuple(sorted(broken.union(case_colliding_refs(held))))


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


# ``%(object)`` and ``%(type)`` are an annotated tag's own target, one level on every
# Git version; both are empty for a ref that names a commit.
# ``%(symref)`` is empty unless the ref is symbolic, as a checkout's ``origin/HEAD`` is.
# Then the commit's committer date, read from the ref's own object for a commit and from
# the tagged one, ``%(*…)``, for an annotated tag; a row shows it as the commit's age
# (static/source-ref-selector.js). For a tag whose own target is a commit, the only kind
# listed, the two spellings agree on every Git version. The date is free: Git has parsed
# the object for ``%(objecttype)``. A row shows its commit as every line names one, from
# the full ID (``shortCommit`` in static/formatters.js), so no abbreviation is asked of
# Git, which costs a lookup per ref (15 µs a ref over 528 branches, measured 2026-11-18 on
# macOS with Git 2.50.1).
_LIST_FORMAT: Final = (
    "%(refname)%00%(objectname)%00%(objecttype)%00%(object)%00%(type)%00%(symref)"
    "%00%(committerdate:unix)%00%(*committerdate:unix)"
)
_LIST_FIELDS: Final = 8


def _newest_first(entry: MirrorRef) -> tuple[bool, bool, float, str]:
    """Notable branches first, then newest first within each group, then by name.

    Every list, branches, tags, and remote-tracking branches alike, reads by the committer
    date of the commit each ref names, ``committed_at``, which is the date its row shows
    as an age (static/source-ref-selector.js), so the order and the ages agree. A tag is
    dated by its commit too, not by an annotated tag's tagger date: a lightweight tag has
    none, and a tag made later of an old commit would otherwise list above newer commits
    while its row showed the old commit's age. A release tag, made with its commit, lists
    where its tagger date would put it. A ref Git gave no date lists after every dated
    one. Equal dates read by name, in Git's byte order, which comparing the decoded names
    by code point keeps.
    """

    dated = entry.committed_at is not None
    return (not entry.notable, not dated, -(entry.committed_at or 0.0), entry.name)


def in_listing_order(entries: tuple[MirrorRef, ...]) -> tuple[MirrorRef, ...]:
    """*entries* in a listing's order (:func:`_newest_first`), for a list read from two places."""

    return tuple(sorted(entries, key=_newest_first))


async def list_mirror_refs(
    target: RepositoryStoreTarget,
    kind: RefKind,
    *,
    default_ref: str | None = None,
    namespaces: RefNamespaces = MIRROR_REFS,
    origin_default_ref: str | None = None,
) -> tuple[MirrorRef, ...]:
    """Every branch, or every tag, the store holds that names a commit, in one ``for-each-ref``.

    *namespaces* says where the repository keeps each kind; a kind it has no list of, as a
    mirror has no remote-tracking branches, lists nothing. A remote-tracking ref that is
    symbolic, ``origin/HEAD``, is left out: it names another row of the same list.

    Notable branches list first, then each group reads newest first by the date each row
    shows, then by name. Main, master, and any known remote default are notable. A
    mirror's *default_ref* marks its default and a checkout's marks its checked-out branch.
    *origin_default_ref* is the checkout's origin default as recorded in its mirror,
    when available. Git sorts nothing; ordering 10,001 refs here took a median 1.8 ms of nine
    runs (measured 2026-11-19 on an M1 Pro at a load average of 18). A ref is listed when
    it names a commit, or names an annotated tag whose own target is a commit. A tag of
    a tree, a blob, or another tag is left out rather than peeled one process at a
    time; the pin route still takes it by name. The target is read from the tag
    object's own ``%(object)`` and ``%(type)``, which name exactly one level on every
    Git version, where ``%(*objecttype)`` peels one level on older Git and the whole
    chain on newer. A name that is not valid UTF-8 or not a valid ref name is left out
    too: it could not be shown, or sent back to the pin route, as JSON text. The
    listing is bounded by the store-read policy's output cap and deadline, and Git's
    output is read and ordered off the event loop, since that work grows with every ref.
    """

    prefix = namespaces.prefix(kind)
    if prefix is None:
        return ()
    checkout_branches = kind == "branch" and namespaces == CHECKOUT_REFS
    patterns = [prefix]
    if checkout_branches:
        patterns.append(f"{_REMOTE_REF_PREFIX}**/HEAD")
    out = await _git(target, ["for-each-ref", f"--format={_LIST_FORMAT}", "--", *patterns])
    return await asyncio.to_thread(
        _listed_refs,
        out,
        kind=kind,
        prefix=prefix,
        default_ref=default_ref,
        checkout_branches=checkout_branches,
        origin_default_ref=origin_default_ref,
    )


def _listed_refs(
    out: bytes,
    *,
    kind: RefKind,
    prefix: str,
    default_ref: str | None,
    checkout_branches: bool,
    origin_default_ref: str | None,
) -> tuple[MirrorRef, ...]:
    """The rows of :func:`list_mirror_refs`'s ``for-each-ref`` output, in their order."""

    notable_refs = {prefix + name for name in TRUNK_BRANCH_NAMES} if kind == "branch" else set()
    origin_default_name = None
    if origin_default_ref is not None and origin_default_ref.startswith(BRANCH_MIRROR_PREFIX):
        origin_default_name = origin_default_ref.removeprefix(BRANCH_MIRROR_PREFIX)
    if checkout_branches and origin_default_name is not None:
        notable_refs.add(prefix + origin_default_name)
    elif kind == "branch" and not checkout_branches and default_ref is not None:
        notable_refs.add(default_ref)
    listed: list[tuple[str, str, float | None]] = []
    for line in out.split(b"\n"):
        try:
            fields = line.decode("utf-8").split("\0")
        except UnicodeDecodeError:
            continue
        if len(fields) != _LIST_FIELDS:
            continue
        ref, oid, object_kind, target_oid, target_kind, symbolic = fields[:6]
        own_date, tagged_date = fields[6:]
        if (checkout_branches or kind == "remote") and ref.startswith(_REMOTE_REF_PREFIX):
            if symbolic:
                if ref.endswith("/HEAD"):
                    remote_prefix = ref.removesuffix("HEAD")
                    default = symbolic.removeprefix(remote_prefix)
                    if default != symbolic and default:
                        if kind == "remote":
                            notable_refs.add(symbolic)
                            notable_refs.update(remote_prefix + name for name in TRUNK_BRANCH_NAMES)
                        elif remote_prefix != BRANCH_MIRROR_PREFIX or origin_default_name is None:
                            notable_refs.add(prefix + default)
                continue
            name = ref.removeprefix(_REMOTE_REF_PREFIX)
            if kind == "remote" and name.partition("/")[2] in TRUNK_BRANCH_NAMES:
                notable_refs.add(ref)
        if not ref.startswith(prefix):
            continue
        if object_kind == "commit":
            commit, date = oid, own_date
        elif object_kind == "tag" and target_kind == "commit":
            commit, date = target_oid, tagged_date
        else:
            continue
        if not is_full_revision(commit) or not is_valid_ref_name(ref):
            continue
        listed.append((ref, commit, float(date) if date.isdigit() else None))
    return in_listing_order(
        tuple(
            MirrorRef(
                name=ref.removeprefix(prefix),
                ref=ref,
                commit=commit,
                default=ref == default_ref,
                committed_at=date,
                notable=ref in notable_refs,
            )
            for ref, commit, date in listed
        )
    )


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
    if not _COMMIT_ID.fullmatch(text):
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


async def ref_tips(target: RepositoryStoreTarget, refs: Sequence[str]) -> dict[str, str]:
    """The commit each of the full refs *refs* names, for those that name one, in one read.

    :func:`ref_tip` for several refs with one ``for-each-ref``: a ref that does not exist
    under exactly that name, or names no commit, is left out. Only a tag of a tag costs
    a further process, to peel it.
    """

    wanted = [ref for ref in refs if ref.startswith("refs/") and is_valid_ref_name(ref)]
    tips: dict[str, str] = {}
    for ref, found in (await _exact_refs(target, wanted)).items():
        commit = await _peeled_commit(target, found)
        if commit is not None:
            tips[ref] = commit
    return tips


@dataclass(frozen=True, slots=True)
class ResolvedPin:
    """The commit a pin request names, and the mirror ref it was found through, if any."""

    commit_oid: str
    ref: str | None


async def _pin_commit_id(
    target: RepositoryStoreTarget, text: str, *, where: str = "the mirror"
) -> str:
    resolved = await resolve_commit_id(target, text)
    if isinstance(resolved, ResolvedSelection):
        return resolved.commit
    if resolved.reason == "invalid_ref":
        raise InvalidSelectionError(
            "a commit ID is 7 to 64 hexadecimal digits; a ref name follows Git's ref-name rules"
        )
    if resolved.reason == "commit_ambiguous":
        raise AmbiguousSelectionError("that abbreviated commit ID matches several commits")
    if resolved.reason == "not_a_commit":
        raise SelectionNotACommitError(f"that ID names an object in {where} that is not a commit")
    raise SelectionNotFoundError(f"no commit with that ID is in {where}")


async def _ref_at(target: RepositoryStoreTarget, commit: str, refs: tuple[str, ...]) -> str | None:
    """The first of *refs* whose tip in the mirror is *commit*, or ``None``."""

    for ref in refs:
        if await ref_tip(target, ref) == commit:
            return ref
    return None


async def _pull_head_at(target: RepositoryStoreTarget, commit: str) -> str | None:
    """The head ref of a pull request whose tip in the mirror is *commit*, or ``None``.

    The newest such pull request, when a commit heads several, as a stacked or reopened
    one does. One ``for-each-ref --points-at`` over every fetched head, which stays small
    against the switch it belongs to. Measured 2026-11-02 with Git 2.50.1 at a load average
    of 15, on a mirror of pallets/click: 20 to 30 ms with eight heads; 140 to 190 ms with
    all 1,934 of its pull requests fetched one by one, as loose refs; 30 ms with those packed.
    """

    out = await _git(
        target, ["for-each-ref", "--format=%(refname)", f"--points-at={commit}", "--", _PULL_REFS]
    )
    heads = [_PULL_HEAD.fullmatch(line.decode("ascii", "replace")) for line in out.split(b"\n")]
    numbered = [int(head.group(1)) for head in heads if head is not None]
    return f"{_PULL_REFS}{max(numbered)}/head" if numbered else None


async def resolve_pin(
    target: RepositoryStoreTarget,
    *,
    ref: str | None = None,
    oid: str | None = None,
    default_ref: str | None = None,
    keep_refs: tuple[str, ...] = (),
    namespaces: RefNamespaces = MIRROR_REFS,
) -> ResolvedPin:
    """The commit a pin request names in the mirror, and the ref it came through.

    Exactly one of *ref* and *oid* is given. A short ref name is tried as a branch,
    then as a tag, and then, when it is hexadecimal, as a commit ID; a full name must
    be under ``refs/remotes/origin/`` or ``refs/tags/``, or be a pull request's
    ``refs/pull/<n>/head``: the only refs a mirror holds. In a checkout
    (:data:`CHECKOUT_REFS`) a short name is a branch, then a tag, then a remote-tracking
    branch such as ``origin/topic``, and a full name is under one of those three; it holds
    no pull-request heads, and its ``HEAD`` is the checked-out branch.
    *oid* is only a commit ID, full or abbreviated to at least seven digits. A commit
    pinned by ID has no ref, unless it is the tip of one of *keep_refs* in the mirror
    now: the refs a server was serving, which a reader who went to another commit and
    came back by ID is still on. The first such ref is kept, so the selector names it
    and freshness says when it moves on; the commit itself stays put
    (``MirrorSession._by_id``). A request names its own first such ref, as View on
    branch names the pull request's head. Otherwise it is served under a pull request's
    head when it is the tip of one the mirror holds. ``HEAD`` is the default branch,
    *default_ref*, as in a URL.
    A name the mirror holds that is not a commit, such as a tag of a tree, is refused
    at once, as URL opening refuses it. Raises a
    :class:`~metabrowser.mirror_refresh.SelectionError`; Git failures other than "not
    there" propagate as :class:`~metabrowser.git.process.GitError`.
    """

    if (ref is None) == (oid is None):
        raise InvalidSelectionError('give exactly one of "ref" and "oid"')
    if oid is not None:
        commit = await _pin_commit_id(target, oid, where=namespaces.where)
        kept = await _ref_at(target, commit, keep_refs)
        if kept is None and namespaces.pull_heads:
            kept = await _pull_head_at(target, commit)
        return ResolvedPin(commit_oid=commit, ref=kept)
    assert ref is not None
    if not ref:
        raise InvalidSelectionError("the ref is empty")
    if ref == "HEAD":
        if default_ref is None:
            raise SelectionNotFoundError(namespaces.no_head)
        candidates: tuple[str, ...] = (default_ref,)
    elif ref.startswith("refs/"):
        if not ref.startswith(namespaces.prefixes) and not (
            namespaces.pull_heads and _PULL_HEAD.fullmatch(ref)
        ):
            raise InvalidSelectionError(namespaces.pinnable)
        candidates = (ref,)
    else:
        candidates = tuple(prefix + ref for prefix in namespaces.prefixes)
    is_hex = _COMMIT_ID.fullmatch(ref.lower()) is not None
    # A name that is not a commit, such as a tag of a tree, is decided only after every
    # other reading -- a tag of the same name, a commit ID -- had its turn.
    not_a_commit = SelectionNotACommitError(
        f"that name is in {namespaces.where} but does not name a commit"
    )
    names_a_non_commit = False
    if all(is_valid_ref_name(candidate) for candidate in candidates):
        exact = await _exact_refs(target, list(candidates))
        for candidate in candidates:
            found = exact.get(candidate)
            if found is None:
                continue
            commit = await _peeled_commit(target, found)
            if commit is not None:
                return ResolvedPin(commit_oid=commit, ref=candidate)
            names_a_non_commit = True
    elif not is_hex:
        raise InvalidSelectionError("the ref is not a valid Git ref name")
    if is_hex:
        try:
            return ResolvedPin(
                commit_oid=await _pin_commit_id(target, ref, where=namespaces.where), ref=None
            )
        except SelectionNotFoundError:
            if names_a_non_commit:
                raise not_a_commit from None
            raise
    if names_a_non_commit:
        raise not_a_commit
    raise SelectionNotFoundError(f"no branch or tag with that name is in {namespaces.where}")


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
    # A name that is not a commit is decided only after every other reading had its turn.
    names_a_non_commit = False
    for via, prefix in namespaces:
        for candidate in candidates:
            ref = exact.get(prefix + candidate.name)
            if ref is None:
                continue
            commit = await _peeled_commit(target, ref)
            if commit is None:
                names_a_non_commit = True
                continue
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
        if _COMMIT_ID.fullmatch(first.lower()):
            resolved = await resolve_commit_id(target, first)
            if isinstance(resolved, ResolvedSelection):
                return ResolvedSelection(
                    via="commit", name=None, ref=None, commit=resolved.commit, path=rest[1:]
                )
            if resolved.reason != "commit_not_found":
                return resolved
    return UnresolvedSelection("not_a_commit" if names_a_non_commit else "ref_not_found")


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
    "CHECKOUT_REFS",
    "MAX_DISAMBIGUATION_OBJECTS",
    "MAX_REF_CANDIDATES",
    "MIRROR_REFS",
    "in_listing_order",
    "RefCandidate",
    "RefNamespaces",
    "ResolvedPin",
    "ResolvedSelection",
    "SelectionResolution",
    "UnresolvedSelection",
    "case_colliding_refs",
    "describe_case_collision",
    "folded_refs",
    "is_pinnable_ref",
    "is_valid_ref_name",
    "list_mirror_refs",
    "mirror_refs",
    "ref_candidates",
    "ref_tip",
    "ref_tips",
    "resolve_commit_id",
    "resolve_pin",
    "resolve_ref_and_path",
    "resolve_selection",
    "store_ignores_case",
]
