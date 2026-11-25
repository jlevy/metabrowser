"""A native stack's page: its members, its combined comparison, and which layers change a file.

A stack is one change delivered in layers, and its page shows the whole of it as one
comparison (docs/project/specs/active/plan-2026-11-24-stack-review.md, "Phase 1"):

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
refresh replaces it.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import stat
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal, TypedDict
from urllib.parse import urlencode
from weakref import WeakKeyDictionary

from metabrowser.builtin_plugins.diff.comparison_cache import ResolvedManifest
from metabrowser.builtin_plugins.diff.sidekick import comparison_cache_key, listed_totals
from metabrowser.builtin_plugins.github.pull_record import PullRecord
from metabrowser.builtin_plugins.github.pull_stacks import NativeStack, StackCache, read_stacks
from metabrowser.builtin_plugins.github.served_pull import ATTENDED_PROBE_S
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
    # The record's comparison, or None with no usable record.
    base: str | None
    head: str | None
    # Whether the top head contains it; None with no record, True for the top itself.
    in_top: bool | None
    # Whether the page asks pull-refresh for it: no usable record, or a newer head known.
    pending: bool


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


class StackEnvelope(TypedDict):
    """What ``GET /api/plugin/github/stack`` answers."""

    state: Literal["absent", "pending", "current"]
    reason: StackAbsence | None
    number: int
    base_ref: str | None
    open: bool | None
    members: list[StackMemberWire]
    pending: list[int]
    lacking: list[int]
    comparison: StackComparisonWire | None
    totals: StackTotals | None
    truncated: bool
    files: list[FileLayersWire]
    # The member whose description carries the stack's guide; phase 3 reads it.
    guide: int | None
    # What View on GitHub opens: the top member's page, which GitHub draws with its stack.
    github_url: str | None
    # The top member's automatic ask, which keeps the repository's list probed while the
    # stack's page is all that is open, so the catalog reports every member's head.
    probe: StackProbeWire | None


@dataclass(frozen=True, slots=True)
class _Member:
    number: int
    record: PullRecord | None
    # The cached record's revision, which an ask names as the record the page holds.
    revision: str | None
    title: str | None
    state: MemberState | None
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
    """What a read of the stack found: the snapshot's stack, its members, and the pair."""

    stack: NativeStack | None
    members: tuple[_Member, ...]
    pair: StackPair | None
    reason: StackAbsence | None


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


def _state(
    record: PullRecord | None, row_state: str | None, draft: bool, merged: bool
) -> MemberState | None:
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


def _read_members(
    repository: ListedRepository,
    published: PublishedSource,
    number: int,
    reader: str | None,
) -> tuple[NativeStack, tuple[_Member, ...]] | None:
    """Stack *number* and its members, bottom first, or ``None`` when the snapshot has no such
    stack. Blocking and bounded: the snapshot, and a record and a catalog row a member, each
    through its parse cache."""

    from metabrowser.builtin_plugins.github.pull_files_route import known_head
    from metabrowser.builtin_plugins.github.pull_list_route import cached_list_row
    from metabrowser.builtin_plugins.github.pull_route import cached_pull_record

    cache = _snapshot(repository)
    snapshot = cache.snapshot if cache is not None else None
    stack = (
        None
        if snapshot is None
        else next(
            (found for page in snapshot.pages for found in page.stacks if found.number == number),
            None,
        )
    )
    if stack is None:
        return None
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
                state=_state(
                    record,
                    row.state if row is not None else None,
                    row.draft if row is not None else False,
                    row.merged if row is not None else False,
                ),
                moved=moved,
            )
        )
    return stack, tuple(members)


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


def stack_digest(members: tuple[tuple[int, str, str], ...]) -> str:
    """The digest of every member's number, merge base, and head, in stack order."""

    return hashlib.sha256(json.dumps([list(member) for member in members]).encode()).hexdigest()[
        :32
    ]


async def read_stack(
    repository: ListedRepository | None,
    published: PublishedSource | None,
    number: int,
    reader: str | None,
) -> StackRead:
    """Stack *number* as this server has it now: its members and, when every member has a
    usable record, its current pair. Runs no ``gh``; its Git is ancestry checks alone."""

    if repository is None:
        return StackRead(None, (), None, "not_github")
    if published is None:
        found = await asyncio.to_thread(_snapshot, repository)
        snapshot = found.snapshot if found is not None else None
        known = snapshot is not None and any(
            stack.number == number for page in snapshot.pages for stack in page.stacks
        )
        return StackRead(None, (), None, "no_store" if known else "not_stacked")
    read = await asyncio.to_thread(_read_members, repository, published, number, reader)
    if read is None:
        return StackRead(None, (), None, "not_stacked")
    stack, members = read
    records = [member.record for member in members]
    if any(record is None for record in records):
        return StackRead(stack, members, None, None)
    pairs = tuple(
        (member.number, record.comparison.base, record.comparison.head)
        for member, record in zip(members, records, strict=True)
        if record is not None and record.comparison is not None
    )
    base, head = pairs[0][1], pairs[-1][2]
    target = RepositoryStoreTarget(published.git_dir, published.object_format)
    linear = await _contains(target, base, head)
    if linear is None:
        return StackRead(stack, members, None, "commits_unavailable")
    if not linear:
        return StackRead(stack, members, None, "not_linear")
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
    return StackRead(stack, members, pair, None)


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
    ``stack=`` in place of ``number`` and admit the stack's current pair alone."""

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
    number: int, read: StackRead | None, state: Literal["absent", "pending", "current"]
) -> StackEnvelope:
    stack = read.stack if read is not None else None
    members = read.members if read is not None else ()
    pair = read.pair if read is not None else None
    wires = [
        StackMemberWire(
            number=member.number,
            place=place,
            title=member.title,
            state=member.state,
            base=member.record.comparison.base
            if member.record is not None and member.record.comparison is not None
            else None,
            head=member.record.comparison.head
            if member.record is not None and member.record.comparison is not None
            else None,
            in_top=pair.in_top[place - 1] if pair is not None else None,
            pending=member.record is None or member.moved,
        )
        for place, member in enumerate(members, 1)
    ]
    return StackEnvelope(
        state=state,
        reason=None,
        number=number,
        base_ref=stack.base_ref if stack is not None else None,
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
    )


async def stack_envelope(
    repository: ListedRepository | None,
    published: PublishedSource | None,
    number: int,
    reader: str | None,
) -> StackEnvelope:
    """Stack *number*'s page answer, or why there is none. Runs no ``gh`` and no fetch."""

    from metabrowser.diff.adapters.base import DiffSourceError
    from metabrowser.git.process import GitError

    read = await read_stack(repository, published, number, reader)
    if read.reason is not None:
        return absent(number, read.reason, read)
    if read.pair is None or published is None:
        envelope = _envelope(number, read, "pending")
    else:
        try:
            found = await combined(published, read.pair)
        except (DiffSourceError, GitError):
            return absent(number, "commits_unavailable", read)
        envelope = _envelope(number, read, "current")
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
    if repository is not None and read.stack is not None:
        envelope["github_url"] = f"{repository.source}/pull/{read.stack.pulls[-1]}"
    top = read.members[-1] if read.members else None
    if top is not None and top.record is not None:
        envelope["probe"] = StackProbeWire(
            number=top.number, held=top.revision, every_s=ATTENDED_PROBE_S
        )
    return envelope


def envelope_etag(envelope: StackEnvelope) -> str:
    digest = hashlib.sha256(json.dumps(envelope, sort_keys=True).encode()).hexdigest()
    return build_scoped_etag(f"stack-{digest[:32]}")


__all__ = [
    "MAX_KEPT_ANCESTRIES",
    "MAX_KEPT_STACK_COMPARISONS",
    "STACK_COMPARISON_ROUTE",
    "STACK_ROUTE",
    "Combined",
    "StackEnvelope",
    "StackPair",
    "StackRead",
    "combined",
    "comparison_wire",
    "envelope_etag",
    "forget",
    "read_stack",
    "stack_digest",
    "stack_envelope",
    "stack_key",
    "stack_scope",
]
