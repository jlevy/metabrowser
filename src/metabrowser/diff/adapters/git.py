"""Git source: File Diff Format from revisions in a local repository.

Every subprocess goes through ``git/process.py``'s bounded runner. The
raw change list comes from ``git diff --raw --numstat -z`` — the same NUL
framing the history surface parses, with the same quirks — and per-file patches
come from a path-limited ``git diff`` fed through the *patch-file*
parser. Reusing that parser is the point of having one format: git's
own output must round-trip through the neutral model or the model is
wrong.

A comparison asked for by the diff plugin's route lists its files and prints its patch in
one run, the patch within :data:`MAX_LISTED_PATCH_BYTES`, and its revisions resolve in one
``rev-parse``, so a commit costs two Git processes where it cost four (H116). That run never
converts a file with a textconv driver; where the configuration names one, the page's files
are diffed in a run of their own, as before (``textconv.py``). Its answers are the separate
runs' with one exception, a better one, on every path to a page: a page whose files Git
paired otherwise when diffing them alone than when diffing the whole comparison left those
files out, and now shows them as the manifest lists them where the whole comparison's
patch is within :data:`MAX_LISTED_PATCH_BYTES` (:meth:`GitDiffSource.hydrate`).
``tests/test_diff_one_run.py`` holds the rest equal.

Merges are compared against their first parent
(``--diff-merges=first-parent``), matching the history surface.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from base64 import b64decode
from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from metabrowser.diff.adapters.base import DiffSourceError
from metabrowser.diff.adapters.patch_file import MAX_PATCH_BYTES, name_paths, parse_unified_patch
from metabrowser.diff.adapters.textconv import (
    kept_textconv_named,
    read_textconv_named,
    textconv_answer,
    textconv_named,
)
from metabrowser.diff.format import (
    Availability,
    BasePolicy,
    ChangeKind,
    ChangeSetDocument,
    ChangeSetManifest,
    ContentRef,
    ContentRefKind,
    DiffOptions,
    EntrySide,
    EntryType,
    FileChange,
    FileMode,
    FilePatch,
    Hunk,
    LineOp,
    LineRecord,
    ResolvedComparison,
    SnapshotKind,
    SnapshotRef,
    SourceInfo,
    Totals,
)
from metabrowser.git.process import (
    GitCommandError,
    GitError,
    GitLocation,
    GitOutputCutError,
    GitOutputTooLargeError,
    GitTimeoutError,
    RepositoryStoreTarget,
    as_location,
    failure_detail,
    read_chunk_bytes,
    run_git_at,
)
from metabrowser.git.shallow import PARENT_UNAVAILABLE, merge_base_answer, recorded_parents

_NO_MERGE_BASE = "these two commits share no history, so they have no merge base"

log = logging.getLogger(__name__)

MAX_MANIFEST_FILES = 2000
"""Manifest cap. A 2000-file change set is far past reviewable; beyond it
the manifest reports `truncated` with a cursor rather than growing without
bound, matching the patch-file parser's section cap."""

MAX_FILE_PATCH_BYTES = MAX_PATCH_BYTES
"""One file's patch, and what one run hydrates. A comparison is not a patch file a reader
chose: nobody picked its size, and a cut through the whole patch cost them files they never
asked about. So this bounds what the cost is, a file's parse and its rows. Measured
2026-11-02 at load 3: 8.26 MB of +442,000 lines parses in 3.4 s, and its 50 files decode to
13.5 MB. One file past this is `too_large`, and a file that would take a run past it is
`deferred`, and loads alone when the reader reaches it."""

MAX_PATHSPEC_BYTES = 128 * 1024
"""Past this much of paths the patch runs unrestricted. Git's argument list shares the
kernel's limit with the environment: `getconf ARG_MAX` is 1 MiB on macOS, measured
2026-11-02, and Linux's is usually 2 MiB. The comparison route asks for at most 50 paths or
one, and the CLI asks for every file, where a pathspec buys nothing anyway."""

MAX_LISTED_PATCH_BYTES = 256 * 1024
"""How much of its patch the run that lists a comparison may print after its listing before
it is stopped and the patch left to a run of its own (H116). The listing itself is bounded as
the listing run's always was. A Git process start cost about 17 ms on the machine the
hypothesis was measured on. Measured 2026-11-14 at load 12, untimed and as an order of
magnitude: the listing of a 1,635-file comparison took 0.79 s, the same run with its 40 MB
patch 1.11 s, so Git printed the patch at about 130 MB/s and a run stopped at this bound
spends about 2 ms past its listing; 329 of this repository's newest 400 commits list and
patch within it (median 41 KB, 90th percentile 817 KB). Whatever is printed of files a page
does not ask for is work thrown away, at most this much.

What it trades: a process start saved for every comparison within it, against what a run
past it prints and throws away, and the patch each request then holds, at most this much
(a page parses only its own sections' headers, :func:`_sections_by_position`). By the
figures above a stopped run wastes about 2 ms against the 17 ms it then fails to save, so
the break-even is near 2 MiB, and 1 MiB would take the 90th percentile. 256 KiB is a
conservative choice under those untimed figures, not a swept optimum: H116's timed round
sweeps 256 KiB, 1 MiB and 2 MiB and records the result here (bead ``mb-foi8``). The same
bound decides whether a page Git pairs otherwise alone is answered from the whole patch
(:meth:`GitDiffSource._whole_patch_within_bound`), so every path to a page answers alike."""

_NULL_OID = "0" * 40
_STATUS_KINDS = {
    "A": ChangeKind.added,
    "D": ChangeKind.deleted,
    "M": ChangeKind.modified,
    "T": ChangeKind.type_changed,
    "U": ChangeKind.unmerged,
}
_MODE_TYPES = {
    "120000": EntryType.symlink,
    "160000": EntryType.submodule,
}
# What `--diff-filter` keeps of a run limited to a pair's two paths: the pair, whichever
# letter the limited run gives it, and not its partner's own change. A copy whose source is
# deleted and copied elsewhere too is a rename in a run that sees only the two paths; the
# pair's paths and hunks are the same, which is what the manifest is matched on.
_PAIRED_KINDS = frozenset({ChangeKind.renamed, ChangeKind.copied})
_PAIR_FILTER = "RC"

# A commit ID in full, SHA-1 or SHA-256, as rev-parse prints one a line.
_COMMIT_ID = re.compile(rb"[0-9a-f]{40}(?:[0-9a-f]{24})?")
# What makes rev-parse read a name in a list otherwise than alone: a range (`..`), a
# negation (`^` first), the parent shorthands (`^@`, `^!`, `^-`), an option (`-` first),
# and a colon, which names a path, an index entry, or a message search that a suffix
# appended to the name would become part of. And a reflog selector, `@{`: where the peeled
# name's parent does not resolve, as a root's does not, Git reads the whole argument as
# that selector, the suffixes as part of a date it then guesses, so `HEAD@{1}^{commit}^`
# named some other entry of the reflog rather than failing. Whitespace can be part of one
# revision, `HEAD^{/fix the}`, and each argument is one name either way.
_NOT_LISTED = re.compile(r"\.\.|\^[@!-]|:|@\{|^[-^]|^$")

type _SideKey = tuple[str | None, str | None]
type _RawRecord = tuple[str, str, str, str, str, int | None, bytes | None, bytes | None]


class _PatchBound:
    """Says when a listing run has printed more than *bound* bytes of patch.

    The patch begins after the first two NULs in a row, which end the listing, whose fields
    are never empty but for a name with no byte; such a name ends the count early, and its
    listing is then refused whole (:func:`_listing_and_patch`). Each read is searched as it
    is, and the two NULs are found across two reads by the last byte of the first.
    """

    __slots__ = ("_bound", "_ended_in_nul", "_patch")

    def __init__(self, bound: int) -> None:
        self._bound = bound
        self._patch: int | None = None
        self._ended_in_nul = False

    def __call__(self, chunk: bytes) -> bool:
        if self._patch is not None:
            self._patch += len(chunk)
        elif self._ended_in_nul and chunk[:1] == b"\0":
            self._patch = len(chunk) - 1
        else:
            end = chunk.find(b"\0\0")
            if end < 0:
                self._ended_in_nul = chunk[-1:] == b"\0"
                return False
            self._patch = len(chunk) - (end + 2)
        return self._patch > self._bound


class _ByteBound:
    """Says when a run has printed more than *bound* bytes."""

    __slots__ = ("_bound", "_seen")

    def __init__(self, bound: int) -> None:
        self._bound = bound
        self._seen = 0

    def __call__(self, chunk: bytes) -> bool:
        self._seen += len(chunk)
        return self._seen > self._bound


@dataclass(frozen=True, slots=True)
class _Split:
    """One ``diff --raw --numstat -p -z`` run's output, parsed once: the raw records and the
    numstat tokens the manifest is built from, how many bytes of the output are the listing,
    and the patch after it."""

    records: list[_RawRecord]
    numstat: list[bytes]
    listing_bytes: int
    patch: bytes


@dataclass(frozen=True, slots=True)
class _Listed:
    """The patch the run that listed a comparison printed, with the manifest it listed."""

    comparison_id: str
    manifest: ChangeSetManifest
    patch: bytes


@dataclass(frozen=True, slots=True)
class PatchHydration:
    """The patches one diff run produced, and what became of the files it did not.

    *too_large* is a file past the bound of one patch. *deferred* is a file past what one
    run hydrates, which can be asked for alone. *left_out* is one the diff did not produce.
    """

    patches: dict[str, FilePatch]
    left_out: tuple[str, ...] = ()
    too_large: tuple[str, ...] = ()
    deferred: tuple[str, ...] = ()


def _is_gitlink(change: FileChange) -> bool:
    """Whether either side is a submodule, whose section no run pairs otherwise."""
    return any(
        side is not None and side.entry_type is EntryType.submodule
        for side in (change.old, change.new)
    )


def display_path(change: FileChange) -> str:
    """The path a reader knows a change by: its new side, else its old."""
    side = change.new if change.new is not None else change.old
    return side.path if side is not None else ""


def mark_past_the_bounds(files: list[FileChange], hydration: PatchHydration) -> list[FileChange]:
    """Say what became of the files one run could not hydrate, in each file's availability."""
    if not hydration.too_large and not hydration.deferred:
        return files
    states = {
        **dict.fromkeys(hydration.too_large, Availability.too_large),
        **dict.fromkeys(hydration.deferred, Availability.deferred),
    }
    return [
        change.model_copy(update={"availability": states[change.id]})
        if change.id in states
        else change
        for change in files
    ]


def say_left_out(
    files: list[FileChange], resolved: ResolvedComparison, left_out: tuple[str, ...]
) -> tuple[list[FileChange], ResolvedComparison]:
    """Mark the files the diff did not produce, and name them, keeping every other file."""
    gone = set(left_out)
    marked = [
        change.model_copy(update={"availability": Availability.failed})
        if change.id in gone
        else change
        for change in files
    ]
    named = [display_path(change) for change in files if change.id in gone]
    warning = f"{len(named)} file(s) could not be read from the produced diff: {name_paths(named)}"
    return marked, resolved.model_copy(update={"warnings": (*resolved.warnings, warning)})


def _display(raw: bytes) -> tuple[str, str | None]:
    try:
        return raw.decode("utf-8"), None
    except UnicodeDecodeError:
        from base64 import b64encode

        return raw.decode("utf-8", "replace"), b64encode(raw).decode("ascii")


def _mode(text: str) -> FileMode:
    try:
        return FileMode(text)
    except ValueError:
        return FileMode.regular


def _entry_type(mode: FileMode) -> EntryType:
    return _MODE_TYPES.get(mode.value, EntryType.file)


def _side(path_raw: bytes, mode_text: str, oid: str) -> EntrySide:
    path, path_b64 = _display(path_raw)
    mode = _mode(mode_text)
    content = (
        ContentRef(kind=ContentRefKind.git_object, oid=oid)
        if oid != _NULL_OID
        else ContentRef(kind=ContentRefKind.empty)
    )
    return EntrySide(
        path=path, path_b64=path_b64, entry_type=_entry_type(mode), mode=mode, content=content
    )


def _git_sections(out: bytes) -> list[bytes]:
    """The sections of Git's patch, which add up to it byte for byte.

    A hunk's every line has a marker, so only a section can open with this. With
    ``diff.suppressBlankEmpty`` a blank context line has none, which is why a section keeps
    exactly the newline the split took and nothing is stripped.
    """
    parts = out.split(b"\ndiff --git ")
    last = len(parts) - 1
    return [
        (b"diff --git " if index else b"") + part + (b"\n" if index < last else b"")
        for index, part in enumerate(parts)
    ]


def _section_header(section: bytes) -> bytes:
    """A section without its hunks, which the parser reads as what changed."""
    end = section.find(b"\n@@ ")
    return (section if end < 0 else section[:end]).rstrip(b"\n") + b"\n"


def _side_key(side: EntrySide | None) -> _SideKey:
    return (side.path if side else None, side.path_b64 if side else None)


def _section_owners(sections: Sequence[bytes], changes: Sequence[FileChange]) -> list[str | None]:
    """Which of *changes* each section is, or None for a section nobody asked for.

    A limited run holds sections of files that were not asked for: a copy's pathspec names
    its source, whose own modification comes too, and a run past ``diff.renameLimit`` pairs
    what the manifest listed apart. A type change is two sections, delete and add, of one
    change. Each header is parsed alone, so the answer is aligned with the sections however
    many there are.
    """
    exact: dict[tuple[_SideKey, _SideKey], str] = {}
    type_old: dict[_SideKey, str] = {}
    type_new: dict[_SideKey, str] = {}
    for change in changes:
        exact.setdefault((_side_key(change.old), _side_key(change.new)), change.id)
        if change.kind is ChangeKind.type_changed:
            type_old.setdefault(_side_key(change.old), change.id)
            type_new.setdefault(_side_key(change.new), change.id)
    nothing: _SideKey = (None, None)
    owners: list[str | None] = []
    for section in sections:
        parsed = parse_unified_patch(_section_header(section)).manifest.files
        if len(parsed) != 1:
            owners.append(None)
            continue
        old, new = _side_key(parsed[0].old), _side_key(parsed[0].new)
        owner = exact.get((old, new))
        if owner is None and new == nothing:
            owner = type_old.get(old)
        if owner is None and old == nothing:
            owner = type_new.get(new)
        owners.append(owner)
    return owners


@dataclass(frozen=True, slots=True)
class _Budgeted:
    """One run's output for the files asked, within the bounds: the patch to parse, the
    files whose own sections are past the bound of one patch, and the files past what the
    run has room for."""

    kept: bytes
    too_large: tuple[str, ...] = ()
    deferred: tuple[str, ...] = ()


def _within_file_bounds(out: bytes, changes: Sequence[FileChange]) -> _Budgeted:
    """What of *out* is parsed for *changes*, and what became of the rest.

    Only the sections of the files asked for spend the bound, in the order they come, each
    file's sections together: a section nobody asked for is left out whole, so a file asked
    for alone is kept or is too large, and is never deferred by a partner's own change.
    """
    if len(out) <= MAX_FILE_PATCH_BYTES:
        return _Budgeted(out)
    sections = _git_sections(out)
    owners = _section_owners(sections, changes)
    sizes: dict[str, int] = {}
    for section, owner in zip(sections, owners, strict=True):
        if owner is not None:
            sizes[owner] = sizes.get(owner, 0) + len(section)
    kept_ids: set[str] = set()
    too_large: list[str] = []
    deferred: list[str] = []
    total = 0
    for owner, size in sizes.items():
        if size > MAX_FILE_PATCH_BYTES:
            too_large.append(owner)
        elif total + size > MAX_FILE_PATCH_BYTES:
            deferred.append(owner)
        else:
            kept_ids.add(owner)
            total += size
    kept = b"".join(
        section for section, owner in zip(sections, owners, strict=True) if owner in kept_ids
    )
    return _Budgeted(kept, tuple(too_large), tuple(deferred))


def _asked_sections(out: bytes, changes: Sequence[FileChange]) -> bytes:
    """The sections of *out* that are *changes*, in their order, and no other section."""
    sections = _git_sections(out)
    owners = _section_owners(sections, changes)
    return b"".join(
        section for section, owner in zip(sections, owners, strict=True) if owner is not None
    )


def _sections_by_position(
    patch: bytes, listed: ChangeSetManifest, changes: Sequence[FileChange]
) -> bytes | None:
    """The sections of *changes* in the whole comparison's *patch*, found by position and
    confirmed by their own headers; None when any is not where its position says.

    The unrestricted run prints a section for each record of its listing, in the listing's
    order, and two for a type change, delete and add; *listed* is that listing. Where that
    holds, a page's sections are cut out without parsing any other header, so the cost of a
    page follows the page and not the comparison. It does not always hold:
    ``diff.submodule=log`` prints a changed submodule as a ``Submodule`` line under the
    section before it, and ``diff`` as the sections of the submodule's own files. So each
    asked section's header is parsed and must name its positional owner, and the sections
    must add up to the records when the listing is whole; on any mismatch the caller parses
    every header (:func:`_asked_sections`).
    """
    sections = _git_sections(patch)
    starts: dict[str, int] = {}
    count = 0
    for change in listed.files:
        starts[change.id] = count
        count += 2 if change.kind is ChangeKind.type_changed else 1
    if len(sections) < count or (len(sections) != count and not listed.truncated):
        return None
    asked = sorted({change.id: change for change in changes}.values(), key=lambda c: starts[c.id])
    picked: list[bytes] = []
    expected: list[str | None] = []
    for change in asked:
        width = 2 if change.kind is ChangeKind.type_changed else 1
        picked.extend(sections[starts[change.id] : starts[change.id] + width])
        expected.extend([change.id] * width)
    if _section_owners(picked, asked) != expected:
        return None
    return b"".join(picked)


def _commit_ids(out: bytes, count: int) -> list[str] | None:
    """*count* commit IDs, one a line and of one length, or None for any other answer."""
    lines = out.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    if len(lines) != count or not all(_COMMIT_ID.fullmatch(line) for line in lines):
        return None
    if len({len(line) for line in lines}) != 1:
        return None
    return [line.decode("ascii") for line in lines]


def _listing_and_patch(out: bytes, *, cut: bool) -> _Split | None:
    """The listing and the patch one ``diff --raw --numstat -p -z`` run prints, or None.

    Git prints the two listings the manifest reads, then one NUL, then the patch. A listing
    holds no empty field while every name in it has a byte, so the first two NULs in a row
    end it, as :class:`_PatchBound` finds them, and only the listing is split and parsed; a
    name with none, which a source that runs no fsck can hold, ends it early, and is found in
    the parse, which leaves the listing to its own run. A *cut* run's patch is cut too, and
    only its listing is any use: None unless the patch has begun after it.
    """
    if not out:
        return None if cut else _Split([], [], 0, b"")
    end = out.find(b"\0\0")
    if end < 0:
        return None
    records, numstat = GitDiffSource._parse_raw(out[: end + 1].split(b"\0"))
    if not records or any(
        path == b"" for record in records for path in record[6:] if path is not None
    ):
        return None
    patch = out[end + 2 :]
    if not patch.startswith(b"diff --git "):
        return None
    return _Split(records, numstat, end + 1, patch)


def _pathspec(changes: Sequence[FileChange]) -> list[str] | None:
    """Every path of *changes*, or None when it is too long to be an argument list."""
    paths: dict[str, None] = {}
    for change in changes:
        for side in (change.old, change.new):
            if side is not None:
                # A name that is not UTF-8 reaches Git as its own bytes.
                exact = os.fsdecode(b64decode(side.path_b64)) if side.path_b64 else side.path
                paths[exact] = None
    if sum(len(os.fsencode(path)) + 1 for path in paths) > MAX_PATHSPEC_BYTES:
        return None
    return list(paths)


class GitDiffSource:
    """File Diff Format from two revisions at a :class:`GitLocation`.

    A filesystem location is a working-tree repository. A revision
    location is a worktree-free store pin. ``HEAD`` on a pin is that
    object id, not the store's ambient HEAD. Neither form checks out.
    Store ``content`` reads go through the shared cat-file pool.

    With *patch_with_listing*, :meth:`manifest` lists a comparison in a run that prints its
    patch too, within :data:`MAX_LISTED_PATCH_BYTES`, and :meth:`hydrate` answers from that
    patch when it is given that manifest. One instance holds one such patch, so a source made
    with it serves one comparison, as a route's request does.
    """

    name = "git"

    def __init__(self, repo: Path | GitLocation, *, patch_with_listing: bool = False) -> None:
        self._location = as_location(repo)
        self._empty_tree_oid: str | None = None
        self._patch_with_listing = patch_with_listing
        self._listed: _Listed | None = None

    def _pinned(self, revision: str) -> str | None:
        pin = self._location.pinned_revision
        return pin if pin is not None and revision in {"HEAD", pin} else None

    async def _rev_parse(self, revision: str) -> str:
        pinned = self._pinned(revision)
        if pinned is not None:
            return pinned
        try:
            out = await run_git_at(
                ["rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}"],
                self._location,
            )
        except GitError as exc:
            raise DiffSourceError(f"unknown revision {revision!r}") from exc
        return out.decode("ascii").strip()

    def _listable(self, revision: str) -> bool:
        return self._pinned(revision) is None and _NOT_LISTED.search(revision) is None

    async def _rev_parse_together(self, revisions: Sequence[str]) -> list[str] | None:
        """Each of *revisions* as a commit ID from one ``rev-parse``, or None.

        ``--verify`` takes one name; without it ``rev-parse`` takes several and prints an ID
        a line, reading each name as ``--verify`` does unless the name has what
        ``_NOT_LISTED`` names, which no name reaching here has. A name that does not resolve
        ends the run, and so does any answer that is not one ID a name: None leaves every
        name to :meth:`_rev_parse`, whose refusal names the revision that failed. A run that
        times out is refused as one at a time refuses it, by the first name, without
        waiting out a second deadline.
        """
        try:
            out = await run_git_at(
                ["rev-parse", *(f"{revision}^{{commit}}" for revision in revisions)],
                self._location,
            )
        except GitTimeoutError as exc:
            # One name at a time would wait as long again, and refuse the first name so.
            raise DiffSourceError(f"unknown revision {revisions[0]!r}") from exc
        except GitError as exc:
            log.debug("rev-parse of %d names failed: %s", len(revisions), failure_detail(exc))
            return None
        return _commit_ids(out, len(revisions))

    async def resolve(self, intent: dict[str, Any]) -> ResolvedComparison:
        base_policy = BasePolicy(intent.get("base_policy", "direct"))
        if "revision" in intent:
            # One revision: compare against its first parent (root commits
            # against the empty tree).
            revision = str(intent["revision"])
            base_policy = BasePolicy.first_parent
            # `<rev>^{commit}^`, peeled, is the first parent of what `<rev>^{commit}` names,
            # as `<that ID>^` is: Git resolves the suffix on the name it ends.
            together = (
                await self._rev_parse_together([revision, f"{revision}^{{commit}}^"])
                if self._listable(revision)
                else None
            )
            if together is not None:
                right, left = together
            else:
                right = await self._rev_parse(revision)
                try:
                    left = await self._rev_parse(f"{right}^")
                except DiffSourceError:
                    # No parent resolves: a root commit, or a commit at a shallow boundary,
                    # whose parent Git grafts away. The object tells them apart. A boundary
                    # commit's diff against the empty tree would show the whole tree as
                    # added, a wrong answer with no warning, on a store and a served
                    # shallow checkout alike.
                    if await recorded_parents(self._location, right):
                        raise DiffSourceError(PARENT_UNAVAILABLE) from None
                    left = ""  # root commit; git's empty-tree side
                    await self._ensure_empty_tree_oid()
        else:
            names = [str(intent["left"]), str(intent["right"])]
            together = (
                await self._rev_parse_together(names)
                if all(self._listable(name) for name in names)
                else None
            )
            if together is None:
                together = [await self._rev_parse(name) for name in names]
            left, right = together
            if base_policy is BasePolicy.merge_base:
                left = await self._merge_base(left, right)
        comparison_id = "git:" + sha256(f"{left}..{right}".encode()).hexdigest()[:16]
        return ResolvedComparison(
            comparison_id=comparison_id,
            source=SourceInfo(name=self.name),
            kind="content",
            base_policy=base_policy,
            left=SnapshotRef(
                kind=SnapshotKind.commit if left else SnapshotKind.empty,
                id=left or None,
                symbolic=str(intent.get("left") or intent.get("revision") or "") or None,
            ),
            right=SnapshotRef(
                kind=SnapshotKind.commit, id=right, symbolic=str(intent.get("right") or "") or None
            ),
            options=DiffOptions(context=3, rename_detection=True, rename_similarity=50),
        )

    async def _merge_base(self, left: str, right: str) -> str:
        """The merge base of two commits, which on a shallow store must be certain."""

        target = self._location.target
        if isinstance(target, RepositoryStoreTarget):
            answer = await merge_base_answer(target, left, right)
            if not answer.certain:
                raise DiffSourceError(
                    "this store's history is too shallow to know what these two commits share "
                    "(base_uncertain)"
                )
            if answer.merge_base is None:
                raise DiffSourceError(_NO_MERGE_BASE)
            return answer.merge_base
        try:
            out = await run_git_at(["merge-base", left, right], self._location)
        except GitCommandError as exc:
            # Exit status 1 is Git's answer for histories with no common commit.
            if exc.returncode != 1:
                raise
            raise DiffSourceError(_NO_MERGE_BASE) from exc
        return out.decode("ascii").strip()

    async def _ensure_empty_tree_oid(self) -> None:
        """Derive the repo's empty-tree oid once, honoring its object format.

        The SHA-1 constant is well known, but a repository initialized
        with ``objectFormat = sha256`` has a different one, and a wrong
        oid fails every root-commit comparison there.
        """
        if self._empty_tree_oid is None:
            out = await run_git_at(["hash-object", "-t", "tree", "/dev/null"], self._location)
            self._empty_tree_oid = out.decode("ascii").strip()

    def _endpoints(self, resolved: ResolvedComparison) -> list[str]:
        right = resolved.right.id
        assert right is not None
        if resolved.left.kind is SnapshotKind.empty:
            # Root commit: diff the empty tree against it, using the oid
            # derived for this repo's object format (SHA-1 or SHA-256).
            empty = self._empty_tree_oid or "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
            return [empty, right]
        left = resolved.left.id
        assert left is not None
        return [left, right]

    async def manifest(self, resolved: ResolvedComparison) -> ChangeSetManifest:
        if self._patch_with_listing:
            with_patch = await self._list_with_patch(resolved)
            if with_patch is not None:
                return with_patch
        endpoints = self._endpoints(resolved)
        # One run for both listings, so renames and copies are detected once. Its output is
        # the two listings' bytes end to end. Measured 2026-11-02 on a comparison of 1,183
        # files at load average 15: 1,293 ms as two runs, 705 ms as one; 57 and 28 ms on 42.
        listed = await run_git_at(
            [
                "diff",
                "--raw",
                "--numstat",
                "-z",
                "--no-abbrev",
                "-M50",
                "-C",
                "--diff-merges=first-parent",
                *endpoints,
            ],
            self._location,
        )
        # Bounded by the read cap, not the manifest's: every record is parsed, off the loop.
        return await asyncio.to_thread(self._manifest_from, listed)

    async def _list_with_patch(self, resolved: ResolvedComparison) -> ChangeSetManifest | None:
        """The manifest from one run that prints the patch after the listings, kept for
        :meth:`hydrate`; or None, which leaves the listing to the run above.

        That run's options are the listing's and the patch's together, ``--no-textconv``
        added, and its output is the listing run's bytes, one NUL, then the unrestricted
        patch run's bytes with no driver run (``test_one_run_prints_what_the_two_runs_print``).
        Its patch is kept for :meth:`hydrate` only when the configuration names no textconv
        driver, which ``textconv.py`` keeps an answer to. One known to be named is the
        listing run alone, and the page's run of its own with its drivers, so the run is
        not started only to be thrown away. Otherwise the run starts at once, since
        ``--numstat`` runs no driver and its listing is the manifest whatever the answer,
        and the answer is checked, or asked, beside it. A run that fails is None, so the
        runs that answer are the ones that always did, in their own words. That includes a
        run that takes more than half the read deadline: it does both runs' work, the
        patch's pass over each pair after the listing's, and Git prints its listing only
        at the end, so a listing that would finish in time alone is listed again, and one
        that cannot is refused after a deadline and a half. A listing past the read cap is
        refused as the listing run would refuse it, after this one run: its cap is raised
        by the patch's bound and one read, so it overflows only where the listing alone
        would. A run past :data:`MAX_LISTED_PATCH_BYTES` of patch is stopped there: its
        listing is the manifest, and the patch is left to :meth:`hydrate`'s run. The output
        is split and parsed once, off the event loop.
        """
        if kept_textconv_named(self._location) is True:
            if await textconv_named(self._location):
                return None
            answer = read_textconv_named(self._location)
        else:
            answer = textconv_answer(self._location)
        try:
            out, named = await asyncio.gather(self._patch(resolved, None, listing=True), answer)
        except GitOutputCutError as exc:
            cut = await asyncio.to_thread(self._listed_from, exc.prefix, cut=True)
            return None if cut is None else cut[0]
        except GitOutputTooLargeError:
            raise
        except GitError as exc:
            log.info("the listing with its patch failed, listing alone: %s", failure_detail(exc))
            return None
        listed = await asyncio.to_thread(self._listed_from, out, cut=False)
        if listed is None:
            return None
        manifest, patch = listed
        if named is False:
            self._listed = _Listed(resolved.comparison_id, manifest, patch)
        return manifest

    def _listed_from(self, out: bytes, *, cut: bool) -> tuple[ChangeSetManifest, bytes] | None:
        """The manifest and the patch of one listing run's output, or None
        (:func:`_listing_and_patch`). A listing past the read cap is refused as the listing
        run refuses it."""
        split = _listing_and_patch(out, cut=cut)
        if split is None:
            return None
        cap = self._location.read_policy.max_bytes
        if split.listing_bytes > cap:
            raise GitOutputTooLargeError(f"git diff listed more than {cap} bytes on stdout")
        return self._manifest_of(split.records, split.numstat), split.patch

    def _manifest_from(self, listed: bytes) -> ChangeSetManifest:
        """The manifest of the listing run's output."""
        return self._manifest_of(*self._parse_raw(listed.split(b"\0")))

    def _manifest_of(self, records: list[_RawRecord], numstat: list[bytes]) -> ChangeSetManifest:
        """The manifest of a listing's raw records and numstat tokens."""
        counts = self._parse_numstat(numstat)
        files: list[FileChange] = []
        total_add = total_del = 0
        exact = True
        truncated = False
        for index, record in enumerate(records, start=1):
            if index > MAX_MANIFEST_FILES:
                truncated = True
                break
            old_mode, new_mode, old_oid, new_oid, status, similarity, old_path, new_path = record
            file_id = f"f{index}"
            kind = _STATUS_KINDS.get(status[:1])
            if status[:1] == "R":
                kind = ChangeKind.renamed
            elif status[:1] == "C":
                kind = ChangeKind.copied
            if kind is None:
                kind = ChangeKind.modified
            key = new_path if new_path is not None else old_path
            assert key is not None  # --raw always names at least one path
            add_del = counts.get(key)
            binary = add_del is None
            additions, deletions = add_del if add_del else (None, None)
            if kind is ChangeKind.unmerged:
                availability = Availability.unsupported
                additions = deletions = None
                exact = False
            elif binary:
                # Binary changes contribute no lines; totals stay exact
                # (git's shortstat semantics). Per-file counts are null.
                availability = Availability.binary
            else:
                availability = Availability.ready
                total_add += additions or 0
                total_del += deletions or 0
            old_side = (
                _side(old_path, old_mode, old_oid)
                if kind not in (ChangeKind.added,) and old_path is not None
                else None
            )
            new_side = None
            if kind is not ChangeKind.deleted:
                new_raw = new_path if new_path is not None else old_path
                assert new_raw is not None  # only deleted lacks a new path
                new_side = _side(new_raw, new_mode, new_oid)
            files.append(
                FileChange(
                    id=file_id,
                    kind=kind,
                    old=old_side,
                    new=new_side,
                    similarity=similarity,
                    binary=binary and kind is not ChangeKind.unmerged,
                    availability=availability,
                    additions=additions,
                    deletions=deletions,
                )
            )
        return ChangeSetManifest(
            files=tuple(files),
            totals=Totals(
                files=len(files),
                additions=total_add if exact else None,
                deletions=total_del if exact else None,
                exact=exact,
            ),
            truncated=truncated,
            cursor="manifest-cap" if truncated else None,
        )

    @staticmethod
    def _parse_raw(tokens: list[bytes]) -> tuple[list[_RawRecord], list[bytes]]:
        """``--raw -z`` records: header NUL path [NUL path2] NUL ..., and the tokens after.

        The first record can arrive with a leading newline between the
        format section and the raw section — the quirk the history
        surface documents — so headers are lstripped. A record is read by its
        shape, so a path starting with ``:`` stays a path, and the first token
        that opens no record is where ``--numstat`` starts.
        """
        records: list[_RawRecord] = []
        cursor = 0
        while cursor < len(tokens):
            header = tokens[cursor].lstrip(b"\n")
            if not header.startswith(b":"):
                break
            fields = header[1:].decode("ascii", "replace").split(" ")
            if len(fields) != 5:
                break
            old_mode, new_mode, old_oid, new_oid, status = fields
            similarity = None
            if len(status) > 1 and status[1:].isdigit():
                similarity = int(status[1:])
            two_paths = status[:1] in ("R", "C")
            path_one = tokens[cursor + 1] if cursor + 1 < len(tokens) else b""
            if two_paths:
                path_two = tokens[cursor + 2] if cursor + 2 < len(tokens) else b""
                records.append(
                    (
                        old_mode,
                        new_mode,
                        old_oid.rstrip("."),
                        new_oid.rstrip("."),
                        status,
                        similarity,
                        path_one,
                        path_two,
                    )
                )
                cursor += 3
            else:
                status_letter = status[:1]
                old_path = path_one if status_letter != "A" else None
                new_path = path_one if status_letter != "D" else None
                records.append(
                    (
                        old_mode,
                        new_mode,
                        old_oid.rstrip("."),
                        new_oid.rstrip("."),
                        status,
                        similarity,
                        old_path,
                        new_path,
                    )
                )
                cursor += 2
        return records, tokens[cursor:]

    @staticmethod
    def _parse_numstat(tokens: list[bytes]) -> dict[bytes, tuple[int, int] | None]:
        """``--numstat -z``: additions TAB deletions TAB path (or NUL old NUL new).

        Binary files report ``-`` counts and map to None.
        """
        counts: dict[bytes, tuple[int, int] | None] = {}
        cursor = 0
        while cursor < len(tokens):
            head = tokens[cursor].lstrip(b"\n")
            if not head:
                cursor += 1
                continue
            parts = head.split(b"\t")
            if len(parts) < 3:
                cursor += 1
                continue
            add_raw, del_raw, path = parts[0], parts[1], b"\t".join(parts[2:])
            if path == b"":
                # Rename form: counts TAB TAB NUL old NUL new
                old = tokens[cursor + 1] if cursor + 1 < len(tokens) else b""
                new = tokens[cursor + 2] if cursor + 2 < len(tokens) else b""
                path = new or old
                cursor += 3
            else:
                cursor += 1
            if add_raw == b"-" or del_raw == b"-":
                counts[path] = None
            else:
                counts[path] = (int(add_raw), int(del_raw))
        return counts

    async def file_patch(self, resolved: ResolvedComparison, file_id: str) -> FilePatch:
        patches = await self.file_patches(resolved, (file_id,))
        return patches[file_id]

    async def file_patches(
        self,
        resolved: ResolvedComparison,
        file_ids: Sequence[str],
        *,
        manifest: ChangeSetManifest | None = None,
    ) -> dict[str, FilePatch]:
        """The patches of *file_ids*, all of them or an error."""
        hydration = await self.hydrate(resolved, file_ids, manifest=manifest)
        missing = (*hydration.left_out, *hydration.too_large, *hydration.deferred)
        if missing:
            raise DiffSourceError(f"file {missing[0]!r} not found in the produced diff")
        return hydration.patches

    async def hydrate(
        self,
        resolved: ResolvedComparison,
        file_ids: Sequence[str],
        *,
        manifest: ChangeSetManifest | None = None,
    ) -> PatchHydration:
        """Hydrate any number of files from one diff run and one parse.

        A file the diff did not produce is left out and named, so one section the parser
        cannot read does not cost the reader every other file of the comparison. Pass the
        *manifest* a caller already holds; it is a whole comparison's work to compute.

        The diff is limited to the files' own paths, both sides of a rename or a copy, so
        Git still pairs them: its candidates are a subset of the whole run's, each file's
        true partner among them, and ``-C`` turns off the basename heuristic that made an
        answer depend on what else was changed. A pair's hunks follow from its two blobs.
        The one way the runs can differ is that the whole comparison was past
        ``diff.renameLimit`` and listed an add and a delete that the limited run, with few
        candidates, pairs. Those sections do not match the manifest, so they cannot be taken
        for the wrong file, and asking for them with rename detection off answers for them.

        A rename or a copy asked for alone is selected as a pair, so its partner's own
        change, which the pathspec had to name for the pairing, is not in the output at
        all: the pairing is decided before the filter and the section's bytes are the
        same. A name Git refuses as a pathspec, ``..`` from a source that runs no fsck,
        fails the limited run, and the unrestricted run answers for every file instead.

        Git pairs a page's files otherwise alone when a file's best partner in the whole
        comparison went to another file the page does not hold, and the retry without
        rename detection cannot find a rename. Such a page is answered from the whole
        comparison's patch within :data:`MAX_LISTED_PATCH_BYTES`, one run more, as the
        route answers from the patch its listing run printed; past that bound both leave
        the file out (:meth:`_whole_patch_within_bound`). A gitlink left out is one
        ``diff.submodule`` printed with no section of its own, which no run pairs otherwise.
        """
        listed = manifest if manifest is not None else await self.manifest(resolved)
        by_id = {entry.id: entry for entry in listed.files}
        missing = [file_id for file_id in file_ids if file_id not in by_id]
        if missing:
            raise DiffSourceError(f"no file {missing[0]!r} in this comparison")
        changes = [by_id[file_id] for file_id in file_ids]
        target = self._location.target
        if (
            isinstance(target, RepositoryStoreTarget)
            and (target.git_dir / "objects/info/alternates").exists()
        ):
            from metabrowser.git.tree_source import verify_store_blobs

            oids = tuple(
                dict.fromkeys(
                    str(side.content.oid)
                    for change in changes
                    for side in (change.old, change.new)
                    if side is not None
                    and side.entry_type is not EntryType.submodule
                    and side.content.kind is ContentRefKind.git_object
                )
            )
            await verify_store_blobs(target, oids, max_bytes=MAX_FILE_PATCH_BYTES)
        kept = self._listed
        whole_patch_tried = (
            kept is not None
            and kept.manifest is listed
            and kept.comparison_id == resolved.comparison_id
        )
        if kept is not None and whole_patch_tried:
            answered = await self._hydrate_from(
                kept.patch, changes, listed, whole=len(file_ids) == len(listed.files)
            )
            if answered is not None:
                return answered
        pathspec = None if len(file_ids) == len(listed.files) else _pathspec(changes)
        diff_filter = (
            _PAIR_FILTER
            if pathspec is not None and len(changes) == 1 and changes[0].kind in _PAIRED_KINDS
            else None
        )
        try:
            try:
                out = await self._patch(resolved, pathspec, diff_filter=diff_filter)
            except GitCommandError as exc:
                if pathspec is None:
                    raise
                log.info("path-limited diff failed, running unrestricted: %s", failure_detail(exc))
                pathspec = None
                out = await self._patch(resolved, None)
        except GitOutputTooLargeError:
            # Past Git's output cap: one file is too large, and several can each be asked for.
            asked = tuple(file_ids)
            if len(asked) == 1:
                return PatchHydration(patches={}, too_large=asked)
            return PatchHydration(patches={}, deferred=asked)
        budgeted = await asyncio.to_thread(_within_file_bounds, out, changes)
        document = await asyncio.to_thread(parse_unified_patch, budgeted.kept)
        patches, left_out = self._patches_from(document, changes)
        # A file past the bounds is what it is; the rest of what has no section was not produced.
        over = {*budgeted.too_large, *budgeted.deferred}
        left_out = [change for change in left_out if change.id not in over]
        if left_out and pathspec is not None:
            pairless = [
                change
                for change in left_out
                if change.kind not in (ChangeKind.renamed, ChangeKind.copied)
            ]
            limited = _pathspec(pairless)
            if pairless and limited is not None:
                try:
                    out = await self._patch(resolved, limited, renames=False)
                except GitCommandError as exc:
                    log.info("the retry without renames failed: %s", failure_detail(exc))
                else:
                    document = await asyncio.to_thread(parse_unified_patch, out)
                    found, still_out = self._patches_from(document, pairless)
                    patches.update(found)
                    left_out = [
                        *[change for change in left_out if change not in pairless],
                        *still_out,
                    ]
        if (
            pathspec is not None
            and not whole_patch_tried
            and any(not _is_gitlink(change) for change in left_out)
        ):
            # Paired otherwise alone: answer as the whole comparison's patch does.
            whole_patch = await self._whole_patch_within_bound(resolved)
            if whole_patch is not None:
                answered = await self._hydrate_from(whole_patch, changes, listed, whole=False)
                if answered is not None:
                    return answered
        return PatchHydration(
            patches=patches,
            left_out=tuple(change.id for change in left_out),
            too_large=budgeted.too_large,
            deferred=budgeted.deferred,
        )

    async def _whole_patch_within_bound(self, resolved: ResolvedComparison) -> bytes | None:
        """The comparison's whole patch, or None past :data:`MAX_LISTED_PATCH_BYTES`.

        A page whose files Git pairs otherwise in a run limited to their paths is answered
        from it, as the route answers from the patch its listing run printed: the one bound
        decides on both paths, so a comparison answers alike however its manifest was had,
        from a kept manifest, from a listing another request computed, from a caller's own
        loader, or past a configuration's textconv driver, which this run honors as the
        page's own does. Any failure leaves the page as the limited run answered it.
        """
        try:
            return await self._patch(resolved, None, bound=MAX_LISTED_PATCH_BYTES)
        except GitOutputCutError:
            return None
        except GitError as exc:
            log.info("the whole patch for a page paired otherwise failed: %s", failure_detail(exc))
            return None

    async def _hydrate_from(
        self,
        patch: bytes,
        changes: Sequence[FileChange],
        listed: ChangeSetManifest,
        *,
        whole: bool,
    ) -> PatchHydration | None:
        """What :meth:`hydrate` answers for *changes*, from the listing run's whole *patch*.

        Asked for every file, the run below is unrestricted and prints *patch* itself, but
        for the textconv drivers this one never runs, which is why it is used only where the
        configuration names none. Asked for some, the run below is limited to their paths,
        and where Git pairs renames and copies there as it did in the whole comparison, its
        sections for them are the unrestricted run's byte for byte
        (``test_each_file_alone_is_what_the_whole_diff_says``): those sections are taken from
        *patch* and spend the same bound in the same order. The limited run's sections of
        files not asked for, a copy's source among them, never spend it. Where it pairs a
        file otherwise, the limited run's section matched nothing the manifest lists, and the
        file was left out unless the retry without rename detection found it; *patch* pairs
        it as the manifest does, and it is answered (``test_a_page_paired_otherwise_alone``).
        The sections of some are found by position, and every header is parsed only where a
        position proves wrong (:func:`_sections_by_position`). None when a file has no
        section of its own, which the runs below answer for.
        """

        def bounded() -> _Budgeted:
            if whole:
                return _within_file_bounds(patch, changes)
            asked = _sections_by_position(patch, listed, changes)
            if asked is None:
                asked = _asked_sections(patch, changes)
            return _within_file_bounds(asked, changes)

        budgeted = await asyncio.to_thread(bounded)
        document = await asyncio.to_thread(parse_unified_patch, budgeted.kept)
        patches, left_out = self._patches_from(document, changes)
        over = {*budgeted.too_large, *budgeted.deferred}
        if any(change.id not in over for change in left_out):
            return None
        return PatchHydration(
            patches=patches, too_large=budgeted.too_large, deferred=budgeted.deferred
        )

    async def hydrate_each(
        self,
        resolved: ResolvedComparison,
        file_ids: Sequence[str],
        *,
        manifest: ChangeSetManifest | None = None,
    ) -> PatchHydration:
        """Every file of *file_ids*, each one past what one run hydrates asked for alone.

        What the page shows once a reader has reached every file, for the command line,
        which has no reader to wait for (review of #284, Qodo): one run for the files
        within the bound, then one run a file for the rest, so the whole comparison costs
        one run more per file past the bound and never fails for being large. A file too
        large alone is said to be, as the page says it; nothing comes back deferred.
        """
        listed = manifest if manifest is not None else await self.manifest(resolved)
        first = await self.hydrate(resolved, file_ids, manifest=listed)
        patches = dict(first.patches)
        too_large = list(first.too_large)
        left_out = list(first.left_out)
        for file_id in first.deferred:
            alone = await self.hydrate(resolved, [file_id], manifest=listed)
            if alone.deferred:
                # A single ask is kept or too large; this is a bug in the bounds.
                raise DiffSourceError(f"file {file_id!r} could not be hydrated alone")
            patches.update(alone.patches)
            too_large.extend(alone.too_large)
            left_out.extend(alone.left_out)
        return PatchHydration(patches=patches, left_out=tuple(left_out), too_large=tuple(too_large))

    async def _patch(
        self,
        resolved: ResolvedComparison,
        pathspec: list[str] | None,
        *,
        renames: bool = True,
        diff_filter: str | None = None,
        listing: bool = False,
        bound: int | None = None,
    ) -> bytes:
        """The patch; with *listing*, the manifest's listings before it and no textconv
        driver run, stopped past :data:`MAX_LISTED_PATCH_BYTES` (:meth:`_list_with_patch`);
        with *bound*, stopped past that many bytes."""
        stop_when: Callable[[bytes], bool] | None = None
        if listing:
            stop_when = _PatchBound(MAX_LISTED_PATCH_BYTES)
        elif bound is not None:
            stop_when = _ByteBound(bound)
        return await run_git_at(
            [
                # Paths here are names, never patterns: `*` and `:(top)` mean themselves.
                "--literal-pathspecs",
                "diff",
                # The listing run's own options, and `-p` so the patch follows them.
                *(
                    ["--raw", "--numstat", "-p", "-z", "--no-abbrev", "--no-textconv"]
                    if listing
                    else []
                ),
                *(["-M50", "-C"] if renames else ["--no-renames"]),
                *([] if diff_filter is None else [f"--diff-filter={diff_filter}"]),
                # The shape the parser reads, whatever a folder's configuration says: Git's
                # own prefixes, which name a hunkless section, no external driver, and no
                # color, which `color.diff=always` would write around every line.
                "--src-prefix=a/",
                "--dst-prefix=b/",
                "--no-ext-diff",
                "--no-color",
                "--diff-merges=first-parent",
                *self._endpoints(resolved),
                *([] if pathspec is None else ["--", *pathspec]),
            ],
            self._location,
            # The listing as the listing run bounded it, the patch after it as above, and the
            # read that passes the bound, so the run overflows only past the listing's cap.
            max_bytes=(
                self._location.read_policy.max_bytes
                + MAX_LISTED_PATCH_BYTES
                + read_chunk_bytes()
                + 1
                if listing
                else None
            ),
            # Both runs' work under one run's deadline: half of it (_list_with_patch).
            timeout_s=self._location.read_policy.timeout_s / 2 if listing else None,
            stop_when=stop_when,
        )

    def _patches_from(
        self, document: ChangeSetDocument, changes: Sequence[FileChange]
    ) -> tuple[dict[str, FilePatch], list[FileChange]]:
        """The sections of *document* that are these changes, and the changes with none."""
        parsed_by_sides: dict[tuple[_SideKey, _SideKey], FilePatch] = {}
        for parsed_change in document.manifest.files:
            parsed = document.patches.get(parsed_change.id)
            if parsed is not None:
                key = (_side_key(parsed_change.old), _side_key(parsed_change.new))
                parsed_by_sides.setdefault(key, parsed)

        result: dict[str, FilePatch] = {}
        left_out: list[FileChange] = []
        for change in changes:
            file_id = change.id
            wanted = (_side_key(change.old), _side_key(change.new))
            parsed = parsed_by_sides.get(wanted)
            if parsed is not None:
                result[file_id] = FilePatch(
                    file_id=file_id, hunks=parsed.hunks, truncated=parsed.truncated
                )
                continue
            if change.kind is ChangeKind.type_changed:
                merged = self._merge_type_change_sections(document, wanted)
                if merged is not None:
                    result[file_id] = FilePatch(file_id=file_id, hunks=merged, truncated=False)
                    continue
            left_out.append(change)
        return result, left_out

    @staticmethod
    def _merge_type_change_sections(
        document: ChangeSetDocument,
        wanted: tuple[_SideKey, _SideKey],
    ) -> tuple[Hunk, ...] | None:
        """A type change arrives as delete + add sections; the manifest has one T.

        Replaying old content out and new content in is one hunk, which is
        exactly what the two full-file sections contain between them.
        """
        (want_old, want_new) = wanted
        del_lines: tuple[LineRecord, ...] | None = None
        add_lines: tuple[LineRecord, ...] | None = None
        for parsed_change in document.manifest.files:
            old_key = (
                parsed_change.old.path if parsed_change.old else None,
                parsed_change.old.path_b64 if parsed_change.old else None,
            )
            new_key = (
                parsed_change.new.path if parsed_change.new else None,
                parsed_change.new.path_b64 if parsed_change.new else None,
            )
            patch = document.patches.get(parsed_change.id)
            if patch is None or len(patch.hunks) > 1:
                continue
            lines = patch.hunks[0].lines if patch.hunks else ()
            if old_key == want_old and new_key == (None, None):
                del_lines = lines
            elif old_key == (None, None) and new_key == want_new:
                add_lines = lines
        if del_lines is None or add_lines is None:
            return None
        combined = tuple(del_lines) + tuple(add_lines)
        old_count = sum(1 for line in combined if line.op is not LineOp.add)
        new_count = sum(1 for line in combined if line.op is not LineOp.delete)
        return (
            Hunk(
                old_start=1 if old_count else 0,
                old_count=old_count,
                new_start=1 if new_count else 0,
                new_count=new_count,
                lines=combined,
            ),
        )

    async def _read_blob(self, oid: str) -> bytes:
        target = self._location.target
        if isinstance(target, RepositoryStoreTarget):
            from metabrowser.git.tree_source import read_store_blob

            return await read_store_blob(target, oid)
        return await run_git_at(["cat-file", "blob", oid], self._location)

    async def content(
        self, resolved: ResolvedComparison, file_id: str, side: str
    ) -> AsyncIterator[bytes]:
        # Imported when a blob is read rather than with this module: the diff plugin's
        # sidekick loads this adapter in every server, and the revision tree source
        # behind these names is work a server that never reads a blob has no use for.
        from metabrowser.git.tree_source import (
            GitBlobTooLargeError,
            GitObjectUnavailableError,
            GitPathError,
        )

        manifest = await self.manifest(resolved)
        change = next((entry for entry in manifest.files if entry.id == file_id), None)
        if change is None:
            raise DiffSourceError(f"no file {file_id!r} in this comparison")
        entry = change.old if side == "old" else change.new
        if entry is None or entry.content.kind is not ContentRefKind.git_object:
            raise DiffSourceError(f"file {file_id!r} has no {side} git content")
        try:
            blob = await self._read_blob(str(entry.content.oid))
        except GitBlobTooLargeError as exc:
            raise DiffSourceError(str(exc)) from exc
        except (GitObjectUnavailableError, GitPathError, GitError) as exc:
            raise DiffSourceError(f"file {file_id!r} has no {side} git content") from exc
        yield blob
