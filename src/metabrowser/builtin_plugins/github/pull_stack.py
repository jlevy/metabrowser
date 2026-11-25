"""A native stack's page: its members, its combined comparison, and which layers change a file.

A stack is one change delivered in layers, and its page shows the whole of it as one
comparison (docs/project/architecture/arch-github-pull-requests.md, "The Stack Page"):

- **Old side:** the bottom member's merge base, its record's ``comparison.base``.
- **New side:** the top member's head.
- **Files:** the entries of that diff a layer changes, those with a path, on either side of
  a rename, that an included member's own comparison names. The plain diff of the two
  commits is not the stack's change once a layer merged its base branch in or was
  retargeted: measured 2026-11-24 on a reader's cache of this repository, 91 of the 183
  files of one stack's plain diff, and 56 of 151 of another's, belonged to no layer.
- **Merged members stay in**, as the Pulls tab's change line counts them (the owner's
  decision of 2026-11-24): a merged pull request's pins never move.
- **A member the top lacks** is one whose head, or merge commit once merged, is not an
  ancestor of the top head. It contributes no files, and the answer names it in
  ``lacking`` for the page's line about it. Measured the same day, six members of one
  stack were such members, and 10 of the layers' files were missing from the plain diff.
- **Not linear:** a bottom merge base that is not an ancestor of the top head answers
  ``absent`` with ``not_linear``; it was an ancestor in all eight stacks measured.

Which layers change a file is itself an answer (a tenth to nearly half of the measured
stacks' files are changed by two or more): ``files`` names, for each file of the combined
comparison, each layer that changes it, by its number, its place from the bottom, and the
path that layer's own comparison gives it, which a chip on the page opens.

**Identity.** The comparison's key is the store, both commits, and a digest of every
member's number, merge base, and head, in stack order (:func:`stack_key`). A member that
moves, or a change to the member list, names another comparison, so nothing is invalidated
by hand and nothing stale is served. The digest is in the comparison route's address, its
key in memory (``scope`` of ``comparison_at``), its entity tag, and the kept manifest's
identity (``load_stack_manifest``), so the restricted manifest never shares an entry with
the unrestricted comparison of the same two commits.

**What a read runs.** No ``gh`` and no fetch, as every route of the plugin. The stack
snapshot, each member's record, and its catalog row are read through their parse caches;
the ancestry of each member's head is one ``git merge-base --is-ancestor``, kept for the
process (:data:`MAX_KEPT_ANCESTRIES`); each member's own changed paths come from its kept
manifest, which its fetch prepared (``prepare_pull_manifest``), so they usually run no Git;
and the combined listing runs once a comparison, kept in memory
(:data:`MAX_KEPT_STACK_COMPARISONS`) and beside the store. Measured 2026-11-24 on eight
stacks of this repository, the base-to-top listing took 0.3 to 2.1 s at load averages near
330 and 440, so a page's first read after a member moves waits that long, and no read after.

A member with no usable record (none cached, another account's, or one with no
comparison) leaves the stack ``pending``, with no comparison: the page asks ``pull-refresh``
for it. A member whose catalog row names a newer head than its record is named in
``pending`` while the stack stays ``current``, its record's comparison standing until a
refresh replaces it. Each pending member's ``fetching`` says whether its refresh was running
before its record was read, so the page asks again for one whose fetch ended without a
usable record, and never takes a fetch that ended during the read for one that failed.

**After a move.** A page keeps the comparison it drew, so each pair this route answers is
kept admitted (:mod:`.pull_stack_retained`), and ``stack-comparison``, ``pull-rendered-diff``
and ``pull-image`` keep answering it after the stack moves on.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import stat
import threading
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Final, Literal, TypedDict
from urllib.parse import urlencode
from weakref import WeakKeyDictionary

from metabrowser.builtin_plugins.diff.comparison_cache import ResolvedManifest
from metabrowser.builtin_plugins.diff.sidekick import comparison_cache_key, listed_totals
from metabrowser.builtin_plugins.github.pull_record import PullRecord
from metabrowser.builtin_plugins.github.pull_stacks import NativeStack, StackCache, read_stacks
from metabrowser.builtin_plugins.github.served_pull import ATTENDED_PROBE_S
from metabrowser.cache.locks import run_lock_section
from metabrowser.cache.paths import source_stacks
from metabrowser.diff.adapters.git import GitDiffSource
from metabrowser.git.process import (
    GitCommandError,
    GitLocation,
    RepositoryStoreTarget,
    run_git_at,
)
from metabrowser.http_caching import BUILD_TAG, build_scoped_etag, store_tag
from metabrowser.loading_cache import LoadingCache

if TYPE_CHECKING:
    from metabrowser.builtin_plugins.github.pull_list import ListedRepository
    from metabrowser.cache.acquire import PublishedSource
    from metabrowser.diff.format import ChangeSetManifest, FileChange, ResolvedComparison

STACK_ROUTE: Final = "/api/plugin/github/stack"
STACK_COMPARISON_ROUTE: Final = "/api/plugin/github/stack-comparison"

# The restriction rule's name, in the comparison's key: a change to which files a stack's
# comparison keeps moves every key, kept manifests beside the store included.
_RESTRICTION: Final = "stack-files-v1"

# Combined comparisons kept in memory, each a restricted manifest and its layers. A
# manifest weighs 3.1 to 4.1 KB a file (measured 2026-11-02 on real pull requests, beside
# MAX_CACHED_MANIFESTS in builtin_plugins/diff/comparison_cache.py), and the eight stacks
# measured on 2026-11-24 change 39 to 269 files, so eight kept stacks of that size hold at
# most about 9 MB; eight at the listing's own bound of 2,000 files, 66 MB. A page asks for
# its stack's comparison on every poll, so the open stacks of a session stay kept.
MAX_KEPT_STACK_COMPARISONS: Final = 8
# Ancestry answers kept for the process, least recently used out first: one per member a
# stack's top head is asked about, and they never change, since both ends are commit IDs.
# Measured 2026-11-24 with tracemalloc on Python 3.14.7 (Apple M1 Pro, macOS 26.5.2): 4,096
# entries keyed by two 40-character IDs and a 66-character store path held 1.30 MB sharing
# one path string, 1.74 MB with a copy each. The largest stack cached that day had 46
# members, which ask 47 (one a member and one for the base), so the bound holds about 87.
MAX_KEPT_ANCESTRIES: Final = 4096
# Counts of the commits a member's new head adds, kept for the process the same way: one per
# member whose head moved since the comparison a page drew, which every poll of that page
# asks again, and they never change, since all four ends are commit IDs. Measured
# 2026-11-25 with tracemalloc on Python 3.14.7 (arm64, macOS, load average 89): 4,096
# entries keyed by a 66-character store path and four 40-character IDs, each holding its
# count, held 2.16 MB sharing one path string, 2.43 MB with a copy each.
MAX_KEPT_COUNTS: Final = 4096
# Stack snapshots kept parsed, by file stamp: one per served repository, and a page's
# images and rendered documents each ask for admission, which reads it.
_MAX_KEPT_SNAPSHOTS: Final = 4

type StackAbsence = Literal[
    "not_github", "not_stacked", "no_store", "not_linear", "commits_unavailable"
]
type MemberState = Literal["open", "draft", "merged", "closed"]


class StackMemberWire(TypedDict):
    """One member as the page's header lists it, bottom first."""

    number: int
    # Its place from the bottom, 1 for the bottom; the page shows it as "2/4".
    place: int
    title: str | None
    state: MemberState | None
    # Its author and the author's avatar, which end its member row, as they end the stack
    # menu's (docs/design-system.md, "Authors Follow Pull Requests"): its record's, or with
    # none the repository's cached list row's, as its title is, and the stacks route's
    # `authors` and `avatars` are; None where neither holds it.
    author: str | None
    avatar: str | None
    # The record's comparison, or None with no usable record.
    base: str | None
    head: str | None
    # Whether the top head contains it; None with no record, True for the top itself.
    in_top: bool | None
    # Whether the page asks pull-refresh for it: no usable record, or a newer head known.
    pending: bool
    # Whether a refresh of this pending member was running when its record was about to be
    # read, so that the page tells a fetch under way from one that ended without a usable
    # record; false for any other.
    fetching: bool


class StackComparisonWire(TypedDict):
    """The combined comparison and the routes that answer it, for the diff view."""

    left: str
    right: str
    key: str
    route: str
    image_route: str
    rendered_route: str


class StackTotals(TypedDict):
    files: int
    additions: int | None
    deletions: int | None
    exact: bool


class LayerWire(TypedDict):
    """A layer that changes a file: its number, its place, and the file's path in it."""

    number: int
    place: int
    path: str


class FileLayersWire(TypedDict):
    path: str
    layers: list[LayerWire]


class StackProbeWire(TypedDict):
    """The automatic ask a visible stack page sends for its top member, as that member's own
    page would: its number, the record revision it holds, and how often."""

    number: int
    held: str | None
    every_s: float


class StackGuideWire(TypedDict):
    """The member whose description carries the stack's guide, and its record's revision,
    which the guide route answers as ``carrier`` and ``record_revision``."""

    number: int
    revision: str


class MemberMoveWire(TypedDict):
    """A member whose head moved since the comparison a page drew."""

    number: int
    # The commits the new head adds that the comparison drawn did not hold, in neither the
    # earlier head's history nor its top's, and that its merge base does not hold, so a base
    # branch merged in counts as its one merge commit, and commits the drawn comparison
    # showed while its record lagged count as none; None when the earlier head is not in the
    # new head's history (the branch was rewritten), or the store cannot say, so no count
    # says what is new.
    commits: int | None


class StackMovedWire(TypedDict):
    """What moved since the comparison ``since`` names, which a page drew earlier: each
    member, in both, whose head moved, bottom first. Members added or gone, and members
    merged or closed, are the page's to see in the two answers' ``members``."""

    since: str
    members: list[MemberMoveWire]


class StackEnvelope(TypedDict):
    """What ``GET /api/plugin/github/stack`` answers."""

    state: Literal["absent", "pending", "current"]
    reason: StackAbsence | None
    number: int
    base_ref: str | None
    # The top member's head branch, which the page's header shows merging into
    # ``base_ref``; None until the top member's record is read.
    head_ref: str | None
    open: bool | None
    members: list[StackMemberWire]
    pending: list[int]
    lacking: list[int]
    comparison: StackComparisonWire | None
    totals: StackTotals | None
    truncated: bool
    files: list[FileLayersWire]
    # The member whose description carries the stack's guide, its `stack-review` block
    # (`stack_guide_carrier` in guided_review.py), or None: none does, or the stack is not
    # current, so a member not read yet may.
    guide: StackGuideWire | None
    # The top member's page on GitHub, which a guide's note is resolved against when its
    # step names no page. View on GitHub is the counterpart route's (counterpart.py).
    github_url: str | None
    # The top member's automatic ask, which keeps the repository's list probed while the
    # stack's page is all that is open, so the catalog reports every member's head.
    probe: StackProbeWire | None
    # Asked with ``since``, the digest of a comparison the route gave before: how each
    # member's head moved from it to this one, which the page's notice of a new comparison
    # says. None without ``since``, when it is this comparison, when the stack is not
    # current, or when the route no longer keeps that comparison.
    moved: StackMovedWire | None


@dataclass(frozen=True, slots=True)
class _Member:
    number: int
    record: PullRecord | None
    # The cached record's revision, which an ask names as the record the page holds.
    revision: str | None
    title: str | None
    state: MemberState | None
    author: str | None
    avatar: str | None
    moved: bool


@dataclass(frozen=True, slots=True)
class StackPair:
    """A stack's current comparison: its members' pairs, the two commits, and their digest."""

    number: int
    base: str
    head: str
    digest: str
    # (number, merge base, head), bottom first.
    members: tuple[tuple[int, str, str], ...]
    in_top: tuple[bool, ...]

    def place(self, number: int) -> int:
        return next(at for at, member in enumerate(self.members, 1) if member[0] == number)


@dataclass(frozen=True, slots=True)
class StackRead:
    """What a read of the stack found: the snapshot's stack, its members, and the pair, and
    the members whose refresh was running when their records were about to be read."""

    stack: NativeStack | None
    members: tuple[_Member, ...]
    pair: StackPair | None
    reason: StackAbsence | None
    fetching: frozenset[int] = frozenset()


_SNAPSHOTS: OrderedDict[tuple[str, str, tuple[int, int, int]], StackCache | None] = OrderedDict()
_SNAPSHOTS_LOCK: Final = threading.Lock()


def _snapshot(repository: ListedRepository) -> StackCache | None:
    """The stack snapshot, parsed once for each version of its file. Blocking and bounded."""

    try:
        status = os.lstat(repository.home / source_stacks(repository.slug))
    except OSError:
        return None
    if not stat.S_ISREG(status.st_mode):
        return None
    key = (
        str(repository.home),
        repository.slug,
        (status.st_ino, status.st_mtime_ns, status.st_size),
    )
    with _SNAPSHOTS_LOCK:
        if key in _SNAPSHOTS:
            _SNAPSHOTS.move_to_end(key)
            return _SNAPSHOTS[key]
    cache = read_stacks(repository)
    with _SNAPSHOTS_LOCK:
        _SNAPSHOTS[key] = cache
        while len(_SNAPSHOTS) > _MAX_KEPT_SNAPSHOTS:
            _SNAPSHOTS.popitem(last=False)
    return cache


def snapshot_stacks(repository: ListedRepository) -> tuple[NativeStack, ...]:
    """Every stack of the repository's snapshot, in its order, parsed once for each version
    of its file, or none without one. Blocking and bounded."""

    cache = _snapshot(repository)
    snapshot = cache.snapshot if cache is not None else None
    return () if snapshot is None else tuple(s for page in snapshot.pages for s in page.stacks)


def member_state(
    record: PullRecord | None, row_state: str | None, draft: bool, merged: bool
) -> MemberState | None:
    """A pull request's state as a stack's member shows it: from its record, else from its
    catalog row's *row_state*, *draft*, and *merged*, else ``None``."""

    if record is not None:
        pull = record.pull
        return (
            "merged"
            if pull.merged
            else "closed"
            if pull.state == "closed"
            else "draft"
            if pull.draft
            else "open"
        )
    if row_state is None:
        return None
    return (
        "merged" if merged else "closed" if row_state == "closed" else "draft" if draft else "open"
    )


def _snapshot_stack(repository: ListedRepository, number: int) -> NativeStack | None:
    """Stack *number* as the snapshot has it, or ``None``. Blocking and bounded."""

    cache = _snapshot(repository)
    snapshot = cache.snapshot if cache is not None else None
    if snapshot is None:
        return None
    return next(
        (found for page in snapshot.pages for found in page.stacks if found.number == number),
        None,
    )


def _read_members(
    repository: ListedRepository,
    published: PublishedSource,
    stack: NativeStack,
    reader: str | None,
) -> tuple[_Member, ...]:
    """*stack*'s members, bottom first. Blocking and bounded: a record and a catalog row a
    member, each through its parse cache."""

    from metabrowser.builtin_plugins.github.pull_files_route import known_head
    from metabrowser.builtin_plugins.github.pull_list_route import cached_list_row
    from metabrowser.builtin_plugins.github.pull_route import cached_pull_record

    members: list[_Member] = []
    for member in stack.pulls:
        found, _dumped, revision = cached_pull_record(published.home, published.slug, member)
        record = (
            found
            if isinstance(found, PullRecord)
            and found.source.casefold() == published.source.normalized.casefold()
            and (reader is None or found.reader == reader)
            and found.comparison is not None
            else None
        )
        row = cached_list_row(repository.home, repository.slug, member)
        head = known_head(repository.home, repository.slug, member)[0]
        moved = (
            record is not None
            and record.comparison is not None
            and head is not None
            and head != record.comparison.head
        )
        members.append(
            _Member(
                number=member,
                record=record,
                revision=revision if record is not None else None,
                title=record.pull.title if record is not None else row.title if row else None,
                author=record.pull.author if record is not None else row.author if row else None,
                avatar=record.pull.author_avatar_url
                if record is not None
                else row.author_avatar_url
                if row
                else None,
                state=member_state(
                    record,
                    row.state if row is not None else None,
                    row.draft if row is not None else False,
                    row.merged if row is not None else False,
                ),
                moved=moved,
            )
        )
    return tuple(members)


_ANCESTRIES: OrderedDict[tuple[str, str, str], bool] = OrderedDict()


async def _contains(target: RepositoryStoreTarget, ancestor: str, commit: str) -> bool | None:
    """Whether *commit*'s history holds *ancestor*, by ``git merge-base --is-ancestor``, the
    call a guide's pins are checked with; ``None`` when the store cannot say, as when it
    lacks either commit. A definite answer is kept: both ends are commit IDs."""

    if ancestor == commit:
        return True
    key = (str(target.git_dir), ancestor, commit)
    known = _ANCESTRIES.get(key)
    if known is not None:
        _ANCESTRIES.move_to_end(key)
        return known
    try:
        await run_git_at(
            ["merge-base", "--is-ancestor", ancestor, commit], GitLocation.revision(target, commit)
        )
        answer = True
    except GitCommandError as exc:
        if exc.returncode != 1:
            return None
        answer = False
    _ANCESTRIES[key] = answer
    while len(_ANCESTRIES) > MAX_KEPT_ANCESTRIES:
        _ANCESTRIES.popitem(last=False)
    return answer


_COUNTS: OrderedDict[tuple[str, str, str, str, str], int] = OrderedDict()


async def _added(
    target: RepositoryStoreTarget, earlier: str, head: str, base: str, drawn: str
) -> int | None:
    """The commits *head* adds to *earlier* that neither *drawn*, the top of the comparison
    drawn, nor *base* holds, when *earlier* is in *head*'s history; ``None`` when it is not,
    or when the store cannot say. A count is kept: all four ends are commit IDs."""

    held = await _contains(target, earlier, head)
    if held is not True:
        return None
    key = (str(target.git_dir), earlier, head, base, drawn)
    known = _COUNTS.get(key)
    if known is not None:
        _COUNTS.move_to_end(key)
        return known
    try:
        raw = await run_git_at(
            ["rev-list", "--count", head, f"^{earlier}", f"^{drawn}", f"^{base}"],
            GitLocation.revision(target, head),
        )
        count = int(raw.strip())
    except (GitCommandError, ValueError):
        return None
    _COUNTS[key] = count
    while len(_COUNTS) > MAX_KEPT_COUNTS:
        _COUNTS.popitem(last=False)
    return count


async def stack_moves(
    target: RepositoryStoreTarget, since: StackPair, pair: StackPair
) -> list[MemberMoveWire]:
    """Each member of *pair* that *since* holds too whose head moved, bottom first, with the
    commits its new head adds that *since* did not show (:func:`_added`). Runs one ancestry
    check and one count a member that moved, each kept."""

    earlier = {number: head for number, _base, head in since.members}
    moves: list[MemberMoveWire] = []
    for number, base, head in pair.members:
        before = earlier.get(number)
        if before is None or before == head:
            continue
        moves.append(
            MemberMoveWire(
                number=number, commits=await _added(target, before, head, base, since.head)
            )
        )
    return moves


def stack_digest(members: tuple[tuple[int, str, str], ...]) -> str:
    """The digest of every member's number, merge base, and head, in stack order."""

    return hashlib.sha256(json.dumps([list(member) for member in members]).encode()).hexdigest()[
        :32
    ]


def _not_fetching(_number: int) -> bool:
    return False


async def read_stack(
    repository: ListedRepository | None,
    published: PublishedSource | None,
    number: int,
    reader: str | None,
    running: Callable[[int], bool] = _not_fetching,
) -> StackRead:
    """Stack *number* as this server has it now: its members and, when every member has a
    usable record, its current pair. Runs no ``gh``; its Git is ancestry checks alone.

    *running* says whether a member's refresh is running. It is asked on the loop, before the
    records are read in a thread, as ``PullView`` reads a job's state (``pull_route.py``): a
    refresh that ends during the read has written its record by then, so the answer never
    names a fetch as ended while still lacking the record it wrote."""

    if repository is None:
        return StackRead(None, (), None, "not_github")
    if published is None:
        found = await asyncio.to_thread(_snapshot, repository)
        snapshot = found.snapshot if found is not None else None
        known = snapshot is not None and any(
            stack.number == number for page in snapshot.pages for stack in page.stacks
        )
        return StackRead(None, (), None, "no_store" if known else "not_stacked")
    stack = await asyncio.to_thread(_snapshot_stack, repository, number)
    if stack is None:
        return StackRead(None, (), None, "not_stacked")
    fetching = frozenset(member for member in stack.pulls if running(member))
    members = await asyncio.to_thread(_read_members, repository, published, stack, reader)
    records = [member.record for member in members]
    if any(record is None for record in records):
        return StackRead(stack, members, None, None, fetching)
    pairs = tuple(
        (member.number, record.comparison.base, record.comparison.head)
        for member, record in zip(members, records, strict=True)
        if record is not None and record.comparison is not None
    )
    base, head = pairs[0][1], pairs[-1][2]
    target = RepositoryStoreTarget(published.git_dir, published.object_format)
    linear = await _contains(target, base, head)
    if linear is None:
        return StackRead(stack, members, None, "commits_unavailable", fetching)
    if not linear:
        return StackRead(stack, members, None, "not_linear", fetching)
    in_top: list[bool] = []
    for member, (_number, _base, member_head) in zip(members, pairs, strict=True):
        record = member.record
        assert record is not None
        held = await _contains(target, member_head, head)
        merge = record.pull.merge_commit_sha if record.pull.merged else None
        if not held and merge is not None:
            held = await _contains(target, merge, head)
        in_top.append(held is True)
    pair = StackPair(number, base, head, stack_digest(pairs), pairs, tuple(in_top))
    return StackRead(stack, members, pair, None, fetching)


def stack_key(published: PublishedSource, pair: StackPair) -> tuple[str, ...]:
    """The combined comparison's key: the store, both commits, and the members' digest."""

    location = GitLocation.revision(
        RepositoryStoreTarget(published.git_dir, published.object_format), pair.head
    )
    key = comparison_cache_key(location, _intent(pair), store_tag(published.git_dir))
    assert key is not None
    return (*key, *stack_scope(pair))


def stack_scope(pair: StackPair) -> tuple[str]:
    """What a stack's key adds to the two commits' own: the rule and the members' digest,
    as one item."""

    return (f"{_RESTRICTION}:{pair.digest}",)


def _intent(pair: StackPair) -> dict[str, str]:
    # Direct: the bottom's merge base is an ancestor of the top's head, which `read_stack`
    # checks, so it is the two commits' merge base too, and no second merge base is asked.
    return {"left": pair.base, "right": pair.head, "base_policy": "direct"}


@dataclass(frozen=True, slots=True)
class Combined:
    """The combined comparison restricted to the layers' files, and each file's layers."""

    manifest: ResolvedManifest
    files: tuple[FileLayersWire, ...]


def _display(change: FileChange) -> str:
    side = change.new if change.new is not None else change.old
    return side.path if side is not None else ""


def _sides(change: FileChange) -> set[str]:
    return {side.path for side in (change.old, change.new) if side is not None}


def _paths(manifest: ChangeSetManifest) -> dict[str, str]:
    """Every path a member's comparison names, on either side of a rename, mapped to the path
    its own changed file has there, the one its Changes opens."""

    named: dict[str, str] = {}
    for change in manifest.files:
        shown = _display(change)
        for path in _sides(change):
            named.setdefault(path, shown)
    return named


async def _member_paths(
    published: PublishedSource, pair: StackPair
) -> tuple[tuple[int, int, dict[str, str]], ...]:
    """Each member the top contains, with its place and its own changed paths, bottom first.

    From its kept manifest, which its fetch prepared, with no Git; else from its comparison
    listed now, which keeps it.
    """

    from metabrowser.builtin_plugins.github.pull_manifest import (
        kept_pull_manifest,
        shared_pull_manifest,
    )

    found: list[tuple[int, int, dict[str, str]]] = []
    for place, ((number, base, head), held) in enumerate(
        zip(pair.members, pair.in_top, strict=True), 1
    ):
        if not held:
            continue
        kept = await asyncio.to_thread(kept_pull_manifest, published, number, base, head)
        if kept is None:
            kept = await shared_pull_manifest(published, number, base, head, retain_memory=False)
        found.append((number, place, _paths(kept.manifest)))
    return tuple(found)


def _restricted(
    manifest: ChangeSetManifest, members: tuple[tuple[int, int, dict[str, str]], ...]
) -> ChangeSetManifest:
    named = set().union(*(paths for _number, _place, paths in members))
    kept = [change for change in manifest.files if _sides(change) & named]
    return manifest.model_copy(update={"files": tuple(kept), "totals": listed_totals(kept)})


def _layers(
    manifest: ChangeSetManifest, members: tuple[tuple[int, int, dict[str, str]], ...]
) -> tuple[FileLayersWire, ...]:
    files: list[FileLayersWire] = []
    for change in manifest.files:
        sides = _sides(change)
        layers: list[LayerWire] = []
        for number, place, paths in members:
            own = next((paths[path] for path in sorted(sides) if path in paths), None)
            if own is not None:
                layers.append(LayerWire(number=number, place=place, path=own))
        files.append(FileLayersWire(path=_display(change), layers=layers))
    return tuple(files)


_KEPT: WeakKeyDictionary[asyncio.AbstractEventLoop, LoadingCache[tuple[str, ...], Combined]] = (
    WeakKeyDictionary()
)
_KEPT_LOCK: Final = threading.Lock()


def _kept() -> LoadingCache[tuple[str, ...], Combined]:
    loop = asyncio.get_running_loop()
    with _KEPT_LOCK:
        kept = _KEPT.get(loop)
        if kept is None:
            kept = _KEPT[loop] = LoadingCache(max_values=MAX_KEPT_STACK_COMPARISONS)
        return kept


async def combined(published: PublishedSource, pair: StackPair) -> Combined:
    """The stack's combined comparison, restricted and attributed, computed once a key.

    Raises ``DiffSourceError`` or ``GitError`` when the store cannot list it now.
    """

    from metabrowser.builtin_plugins.github.pull_manifest import load_stack_manifest

    key = stack_key(published, pair)

    async def load() -> Combined:
        members = await _member_paths(published, pair)
        location = GitLocation.revision(
            RepositoryStoreTarget(published.git_dir, published.object_format), pair.head
        )
        source = GitDiffSource(location)

        async def compute(resolved: ResolvedComparison) -> ChangeSetManifest:
            return _restricted(await source.manifest(resolved), members)

        manifest = await load_stack_manifest(
            published, pair.number, source, _intent(pair), key, compute
        )
        return Combined(manifest, _layers(manifest.manifest, members))

    return await _kept().get(key, load)


def forget(published: PublishedSource, pair: StackPair) -> None:
    """Drop a combined comparison found corrupt, so the next read lists it again."""

    loop = asyncio.get_running_loop()
    with _KEPT_LOCK:
        kept = _KEPT.get(loop)
    if kept is not None:
        kept.discard(stack_key(published, pair))


def _query(pair: StackPair, store: str) -> dict[str, str | int]:
    return {"stack": pair.number, "left": pair.base, "right": pair.head, "store": store}


def comparison_wire(published: PublishedSource, pair: StackPair) -> StackComparisonWire:
    """The combined comparison's routes. The comparison's address names everything its
    answer depends on, so the browser keeps it; the image and rendered routes take
    ``stack=`` in place of ``number`` and admit the stack's current pair, and an earlier
    one while it is kept (:mod:`.pull_stack_retained`)."""

    from metabrowser.builtin_plugins.github.pull_route import IMAGE_ROUTE, RENDERED_ROUTE

    store = store_tag(published.git_dir)
    comparison = urlencode(
        {
            "number": pair.number,
            "left": pair.base,
            "right": pair.head,
            "base_policy": "direct",
            "key": pair.digest,
            "build": BUILD_TAG,
            "store": store,
        }
    )
    return StackComparisonWire(
        left=pair.base,
        right=pair.head,
        key=pair.digest,
        route=f"{STACK_COMPARISON_ROUTE}?{comparison}",
        image_route=f"{IMAGE_ROUTE}?{urlencode(_query(pair, store))}",
        rendered_route=f"{RENDERED_ROUTE}?{urlencode(_query(pair, store))}",
    )


def absent(number: int, reason: StackAbsence, read: StackRead | None = None) -> StackEnvelope:
    envelope = _envelope(number, read, "absent")
    envelope["reason"] = reason
    return envelope


def _envelope(
    number: int,
    read: StackRead | None,
    state: Literal["absent", "pending", "current"],
) -> StackEnvelope:
    stack = read.stack if read is not None else None
    members = read.members if read is not None else ()
    pair = read.pair if read is not None else None
    fetching = read.fetching if read is not None else frozenset[int]()
    top = members[-1].record if members else None
    wires: list[StackMemberWire] = []
    for place, member in enumerate(members, 1):
        pending = member.record is None or member.moved
        wires.append(
            StackMemberWire(
                number=member.number,
                place=place,
                title=member.title,
                state=member.state,
                author=member.author,
                avatar=member.avatar,
                base=member.record.comparison.base
                if member.record is not None and member.record.comparison is not None
                else None,
                head=member.record.comparison.head
                if member.record is not None and member.record.comparison is not None
                else None,
                in_top=pair.in_top[place - 1] if pair is not None else None,
                pending=pending,
                fetching=pending and member.number in fetching,
            )
        )
    return StackEnvelope(
        state=state,
        reason=None,
        number=number,
        base_ref=stack.base_ref if stack is not None else None,
        head_ref=top.pull.head.ref if top is not None else None,
        open=stack.open if stack is not None else None,
        members=wires,
        pending=[wire["number"] for wire in wires if wire["pending"]],
        lacking=[wire["number"] for wire in wires if wire["in_top"] is False],
        comparison=None,
        totals=None,
        truncated=False,
        files=[],
        guide=None,
        github_url=None,
        probe=None,
        moved=None,
    )


async def stack_envelope(
    repository: ListedRepository | None,
    published: PublishedSource | None,
    number: int,
    reader: str | None,
    running: Callable[[int], bool] = _not_fetching,
    since: str | None = None,
) -> StackEnvelope:
    """Stack *number*'s page answer, or why there is none. Runs no ``gh`` and no fetch.

    *running* says whether a member's refresh is running; :func:`read_stack` asks it before it
    reads the records, and each pending member's ``fetching`` reports it. A current pair is
    kept admitted for later (:func:`.pull_stack_retained.retain_stack_pair`), so the page can
    keep drawing it after the stack moves. *since*, the digest of a pair answered before and
    still kept, the one the asking page draws, is kept with it, and asks how each member's
    head moved from it (``moved``).
    """

    from metabrowser.builtin_plugins.github.pull_stack_retained import (
        retain_stack_pair,
        retained_stack_digest,
    )
    from metabrowser.diff.adapters.base import DiffSourceError
    from metabrowser.git.process import GitError

    read = await read_stack(repository, published, number, reader, running)
    if read.reason is not None:
        return absent(number, read.reason, read)
    if read.pair is None or published is None:
        envelope = _envelope(number, read, "pending")
    else:
        try:
            found = await combined(published, read.pair)
        except (DiffSourceError, GitError):
            return absent(number, "commits_unavailable", read)
        top_record = read.members[-1].record
        moved: StackMovedWire | None = None
        if top_record is not None:
            await run_lock_section(
                partial(retain_stack_pair, published, read.pair, top_record.reader, since)
            )
            if since is not None and since != read.pair.digest:
                kept = await asyncio.to_thread(
                    retained_stack_digest, published, number, top_record.reader, since
                )
                if isinstance(kept, StackPair):
                    target = RepositoryStoreTarget(published.git_dir, published.object_format)
                    moves = await stack_moves(target, kept, read.pair)
                    moved = StackMovedWire(since=since, members=moves)
        envelope = _envelope(number, read, "current")
        envelope["moved"] = moved
        manifest = found.manifest.manifest
        totals = manifest.totals
        envelope["comparison"] = comparison_wire(published, read.pair)
        envelope["totals"] = StackTotals(
            files=totals.files,
            additions=totals.additions,
            deletions=totals.deletions,
            exact=totals.exact,
        )
        envelope["truncated"] = manifest.truncated
        envelope["files"] = list(found.files)
        envelope["guide"] = await _guide(published, read)
    if repository is not None and read.stack is not None:
        envelope["github_url"] = f"{repository.source}/pull/{read.stack.pulls[-1]}"
    top = read.members[-1] if read.members else None
    if top is not None and top.record is not None:
        envelope["probe"] = StackProbeWire(
            number=top.number, held=top.revision, every_s=ATTENDED_PROBE_S
        )
    return envelope


async def _guide(published: PublishedSource, read: StackRead) -> StackGuideWire | None:
    """The member that carries the stack's guide, read from the records the stack's read
    holds: a description is parsed only when it names the block, and the parse is kept."""

    from metabrowser.builtin_plugins.github.guided_review import stack_guide_carrier

    members = [(member.number, member.record, member.revision) for member in read.members]
    found = await asyncio.to_thread(stack_guide_carrier, published.home, published.slug, members)
    return None if found is None else StackGuideWire(number=found[0], revision=found[1])


def envelope_etag(envelope: StackEnvelope) -> str:
    digest = hashlib.sha256(json.dumps(envelope, sort_keys=True).encode()).hexdigest()
    return build_scoped_etag(f"stack-{digest[:32]}")


__all__ = [
    "MAX_KEPT_ANCESTRIES",
    "MAX_KEPT_COUNTS",
    "MAX_KEPT_STACK_COMPARISONS",
    "STACK_COMPARISON_ROUTE",
    "STACK_ROUTE",
    "Combined",
    "MemberMoveWire",
    "StackEnvelope",
    "StackGuideWire",
    "StackMovedWire",
    "StackPair",
    "StackRead",
    "combined",
    "comparison_wire",
    "envelope_etag",
    "forget",
    "member_state",
    "read_stack",
    "snapshot_stacks",
    "stack_digest",
    "stack_envelope",
    "stack_key",
    "stack_moves",
    "stack_scope",
]
