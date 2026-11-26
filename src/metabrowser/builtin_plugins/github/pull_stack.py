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

**Its size** is measured where the listing runs, once a comparison, and kept beside the
store (:func:`metabrowser.git.change_size.change_size`), so the first read after a member
moves waits on it with the listing, within ``MEASURE_TIMEOUT_S``, and every later read says
it with no Git (:func:`_size`). Its cost follows the objects packed more than the file
count, so the file cap bounds the usual stack and the deadline the rest. Only a comparison that is the plain diff of its two commits, every file of
which a layer changes, is measured, so the size and the file count describe one diff; one
restricted to its layers' files has no size, since no pair of commits pushes just those
files, and neither has one of more than :data:`MAX_SIZED_STACK_FILES` files.

The size is asked to an answer once a kept comparison, and the kept manifest is marked
when it has one (:func:`_settle_size`): a size, a reason Git has none, or that the
comparison is not one that is measured. A read that finds the manifest kept and marked,
in this process or a later one, as every ``metab --api`` read is, runs no Git for the
size. One found kept and not marked, as a build before the mark left it, is asked by the
read that loads it, which lists the plain diff once more, so that read waits as a moved
stack's first read does. A measurement that ran out of time is an answer, and is not run
again until a member moves; one Git failed, or whose read was cancelled, is asked again.

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
import logging
import os
import stat
import threading
from collections import Counter, OrderedDict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Final, Literal, TypedDict
from urllib.parse import urlencode
from weakref import WeakKeyDictionary

from metabrowser.builtin_plugins.diff.comparison_cache import ResolvedManifest
from metabrowser.builtin_plugins.diff.sidekick import comparison_cache_key, listed_totals
from metabrowser.builtin_plugins.github.pull_record import PullLabel, PullRecord
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
    from metabrowser.builtin_plugins.github.pull_list import ListedRepository, PullListRow
    from metabrowser.cache.acquire import PublishedSource
    from metabrowser.diff.format import ChangeSetManifest, FileChange, ResolvedComparison

log = logging.getLogger(__name__)

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
# The most files a stack's comparison is measured for (`combined`), so its first read waits
# at most about as long again as its listing. Measured 2026-11-25 on ranges of this
# repository's main branch (Git 2.43, load averages 54 to 96, each measured twice): 0.13 to
# 0.15 s for 43 files and 5 commits, 0.27 to 0.43 s for 63 files and 19, 0.78 to 1.16 s for
# 147 files and 52, 2.4 to 3.5 s for 326 files and 180, and 3.5 to 4.0 s for 477 files and
# 261. A larger comparison is not measured, and the stack's size line leaves its bytes out.
MAX_SIZED_STACK_FILES: Final = 150
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
    # menu's (docs/design-system.md, "Authors Follow Pull Requests"), by the rule the
    # stacks route's `authors` and `avatars` follow (`member_identity`): its record's, or
    # with none the repository's cached list row's, as its title is; None where neither
    # holds it.
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


class StackPersonWire(TypedDict):
    """An author or a merger, as a pull request's header names one: the login and the
    avatar, or None where the cache holds none."""

    login: str
    avatar: str | None


class StackLabelWire(TypedDict):
    """A label a member carries: its name, and the color and description its record gives it,
    or None from a cached list row, which names its labels alone."""

    name: str
    color: str | None
    description: str | None


class StackStatesWire(TypedDict):
    """How many members are in each state, every state named, 0 where none is."""

    open: int
    draft: int
    merged: int
    closed: int


class StackSizeWire(TypedDict):
    """The combined comparison's size: what the top head pushes over the bottom member's
    merge base, and its patch's size, as a pull request's size line says its own."""

    pushed_bytes: int
    diff_bytes: int


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
    # branch merged in counts as its one merge commit; 0 when the drawn top already held the
    # new head and not the earlier one, as it does for a record that lagged and caught up,
    # whether or not its earlier head is in the new one's history; None when that earlier
    # head is not (the branch was rewritten), or the store cannot say, so no count says what
    # is new.
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
    # What the page's header says of the stack where a pull request's says it of one pull
    # request (docs/design-system.md, "The Stack Page"), each from what the cache holds of
    # every member, its record's, or with none its cached list row's, as its title is:
    # - how many members are in each state, where a pull request's header has its state;
    states: StackStatesWire
    # - when a member was last opened and last updated, the latest of each, where a pull
    #   request's says when it was opened and updated;
    opened_at: str | None
    updated_at: str | None
    # - every member's author, top first, each once, and every merged member's merger, which
    #   the sentence names once every member is merged, as a pull request's names its merger;
    authors: list[StackPersonWire]
    mergers: list[StackPersonWire]
    # - the oldest of the members' records' fetches, so the stack is said to be no fresher
    #   than its stalest record; None with no record;
    fetched_at: str | None
    # - every label a member carries, top first, each once by its name, or None while a
    #   member has neither a record nor a cached row, whose labels are not known;
    labels: list[StackLabelWire] | None
    # - and the commits of the members the top contains, whose files the comparison holds,
    #   summed while every one's record counts them, and the size of the combined comparison
    #   while it is kept (``kept_change_size``: no Git runs for it), measured where the
    #   comparison was built and only where it is the plain diff of its two commits, so the
    #   size and the file count describe one diff (`_size`); on a current stack alone, and
    #   None otherwise.
    commits: int | None
    size: StackSizeWire | None
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
    details: _Details


@dataclass(frozen=True, slots=True)
class _Details:
    """What the header sums or gathers of a member (``StackEnvelope``): its record's, or with
    none its catalog row's, whose labels are names alone; the commits and the merger are the
    record's alone, which a row lacks. *known* is whether it has either, so its labels are
    known, even as none."""

    known: bool = False
    created_at: str | None = None
    updated_at: str | None = None
    labels: tuple[StackLabelWire, ...] = ()
    commits: int | None = None
    merger: StackPersonWire | None = None


def _record_labels(
    labels: Sequence[PullLabel], row: PullListRow | None
) -> tuple[StackLabelWire, ...]:
    """The member's labels by `member_identity`'s rule, the list row's names wherever there is
    a row, each with the record's colour and description where the record knows that name."""

    known = {label.name: label for label in labels}
    names = row.labels if row is not None else tuple(known)
    return tuple(
        StackLabelWire(
            name=name,
            color=known[name].color if name in known else None,
            description=known[name].description if name in known else None,
        )
        for name in names
    )


def _details(record: PullRecord | None, row: PullListRow | None) -> _Details:
    if record is not None:
        pull = record.pull
        return _Details(
            known=True,
            created_at=pull.created_at,
            updated_at=pull.updated_at,
            labels=_record_labels(pull.labels, row),
            commits=pull.commits,
            merger=StackPersonWire(login=pull.merged_by, avatar=pull.merged_by_avatar_url)
            if pull.merged and pull.merged_by
            else None,
        )
    if row is not None:
        return _Details(
            known=True,
            created_at=row.created_at,
            updated_at=row.updated_at,
            labels=tuple(
                StackLabelWire(name=name, color=None, description=None) for name in row.labels
            ),
        )
    return _Details()


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
    from metabrowser.builtin_plugins.github.pull_stacks_route import member_identity

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
        named = member_identity(record, row)
        members.append(
            _Member(
                number=member,
                record=record,
                revision=revision if record is not None else None,
                title=named.title,
                author=named.author,
                avatar=named.avatar,
                state=member_state(
                    record,
                    row.state if row is not None else None,
                    row.draft if row is not None else False,
                    row.merged if row is not None else False,
                ),
                moved=moved,
                details=_details(record, row),
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
    drawn, nor *base* holds: 0 when *drawn* holds *head* and not *earlier*, a record that
    caught up to what the comparison drawn shows, as each member's does after its branch is
    rebased under a top read first; otherwise a count when *earlier* is in *head*'s
    history; ``None`` when it is not, a branch rewritten, or when the store cannot say. A
    count is kept: all four ends are commit IDs."""

    if (
        await _contains(target, head, drawn) is True
        and await _contains(target, earlier, drawn) is False
    ):
        return 0
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
    commits its new head adds that *since* did not show (:func:`_added`). Runs at most three
    ancestry checks and one count a member that moved, each kept."""

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


def _sized(plain: ChangeSetManifest, restricted: ChangeSetManifest) -> bool:
    """Whether the stack's comparison is measured (:func:`combined`): it is the whole of the
    plain diff of its two commits, which the measurement measures, so the size and the file
    count describe one diff, and it is at most :data:`MAX_SIZED_STACK_FILES` files."""

    return (
        not plain.truncated
        and len(restricted.files) == len(plain.files)
        and len(plain.files) <= MAX_SIZED_STACK_FILES
    )


async def _measure(location: GitLocation, pair: StackPair) -> bool:
    """Measure and keep the size of *pair*'s two commits, and say whether Git answered: a
    size, or a reason it has none, which leaves the stack without one, as a pull request's
    row is left (``_measure_size`` in :mod:`.pull_files_refresh`). False where Git failed,
    which a later read may ask again."""

    from metabrowser.git.change_size import change_size
    from metabrowser.git.process import GitError

    try:
        await change_size(location, pair.base, pair.head)
    except GitError as exc:
        log.debug("a stack's size could not be measured: %r", exc)
        return False
    return True


async def _settle_size(
    published: PublishedSource,
    source: GitDiffSource,
    location: GitLocation,
    pair: StackPair,
    key: tuple[str, ...],
    kept: ResolvedManifest,
    plain: ChangeSetManifest | None,
) -> None:
    """Ask the comparison's size to an answer, once a kept manifest, and mark the manifest
    so that no later read or process asks again (``size_settled``).

    An answer is a size, a reason Git has none (``too_costly`` among them), or that the
    comparison is not one that is measured (:func:`_sized`). The mark is kept beside the
    store with the manifest, so a process that finds the manifest kept and marked runs no
    Git here: a ``metab --api`` read is a process of its own, and an answer held in memory
    alone would be asked again by every one.

    *plain* is the plain listing where this read built the comparison. A manifest found
    kept and not marked, as one a build before the mark kept, or one whose read ended
    before its answer, has none, so the plain diff is listed again, within the listing's
    own bounds (``MAX_MANIFEST_FILES`` and Git's timeout) and only for a comparison small
    enough to be measured. Nothing cheaper says whether a restricted comparison is its
    plain diff whole, and with the mark it runs once a comparison, not once a process.

    Not marked, and so asked again by the next load: a listing or a measurement that Git
    failed, and a read cancelled before its answer.
    """

    from metabrowser.builtin_plugins.github.pull_manifest import (
        settle_stack_size,
        stack_size_settled,
    )
    from metabrowser.diff.adapters.base import DiffSourceError
    from metabrowser.git.change_size import kept_change_size
    from metabrowser.git.process import GitError

    if await asyncio.to_thread(stack_size_settled, published, pair.number, key):
        return
    restricted = kept.manifest
    measurable = not restricted.truncated and len(restricted.files) <= MAX_SIZED_STACK_FILES
    if (
        measurable
        and await asyncio.to_thread(kept_change_size, location, pair.base, pair.head) is None
    ):
        if plain is None:
            try:
                plain = await source.manifest(kept.resolved)
            except (DiffSourceError, GitError) as exc:
                log.debug("a kept stack comparison could not be listed for its size: %r", exc)
                return
        if _sized(plain, restricted) and not await _measure(location, pair):
            return
    await asyncio.to_thread(settle_stack_size, published, pair.number, key)


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
        plain: ChangeSetManifest | None = None

        async def compute(resolved: ResolvedComparison) -> ChangeSetManifest:
            nonlocal plain
            plain = await source.manifest(resolved)
            return _restricted(plain, members)

        manifest = await load_stack_manifest(
            published, pair.number, source, _intent(pair), key, compute
        )
        await _settle_size(published, source, location, pair, key, manifest, plain)
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


def _states(members: tuple[_Member, ...]) -> StackStatesWire:
    """How many of *members* are in each state; a member in none known is in no count."""

    counted = Counter(member.state for member in members)
    return StackStatesWire(
        open=counted["open"],
        draft=counted["draft"],
        merged=counted["merged"],
        closed=counted["closed"],
    )


def _people(found: Iterable[StackPersonWire | None]) -> list[StackPersonWire]:
    """Each person *found* names, once, in the order found, with the first avatar given."""

    people: dict[str, StackPersonWire] = {}
    for person in found:
        if person is not None and person["login"] not in people:
            people[person["login"]] = person
    return list(people.values())


def _labels(members: tuple[_Member, ...]) -> list[StackLabelWire] | None:
    """Every label of *members*, top first, each once by its name: the first member that
    names it, top first, gives its color and description, or a later one where it gives
    none. None while any member's labels are not known, as a pull request's page holds its
    labels row until its record says them."""

    if not all(member.details.known for member in members):
        return None
    labels: dict[str, StackLabelWire] = {}
    for member in reversed(members):
        for label in member.details.labels:
            held = labels.get(label["name"])
            if held is None or (held["color"] is None and label["color"] is not None):
                labels[label["name"]] = label
    return list(labels.values())


def _commits(members: tuple[_Member, ...], pair: StackPair | None) -> int | None:
    """The commits of the members the top contains, every member while that is not known,
    summed, or None where any of them has no count."""

    counted = [
        member.details.commits
        for at, member in enumerate(members)
        if pair is None or pair.in_top[at]
    ]
    if not counted or any(count is None for count in counted):
        return None
    return sum(count for count in counted if count is not None)


async def _size(published: PublishedSource, pair: StackPair) -> StackSizeWire | None:
    """The combined comparison's size, kept where it was built (:func:`combined`) and read
    with ``kept_change_size``, which runs no Git; None where none is kept, as for a
    comparison restricted to its layers' files or too large to measure, or where it is
    unknown."""

    from metabrowser.git.change_size import kept_change_size

    location = GitLocation.revision(
        RepositoryStoreTarget(published.git_dir, published.object_format), pair.head
    )
    size = await asyncio.to_thread(kept_change_size, location, pair.base, pair.head)
    if size is None or size["pushed_bytes"] is None or size["diff_bytes"] is None:
        return None
    return StackSizeWire(pushed_bytes=size["pushed_bytes"], diff_bytes=size["diff_bytes"])


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
        states=_states(members),
        opened_at=max(
            (m.details.created_at for m in members if m.details.created_at), default=None
        ),
        updated_at=max(
            (m.details.updated_at for m in members if m.details.updated_at), default=None
        ),
        authors=_people(
            StackPersonWire(login=member.author, avatar=member.avatar) if member.author else None
            for member in reversed(members)
        ),
        mergers=_people(member.details.merger for member in reversed(members)),
        fetched_at=min(
            (member.record.fetched_at for member in members if member.record is not None),
            default=None,
        ),
        labels=_labels(members),
        commits=_commits(members, pair),
        size=None,
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
        envelope["size"] = await _size(published, read.pair)
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
