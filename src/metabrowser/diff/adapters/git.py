"""Git source: File Diff Format from revisions in a local repository.

Every subprocess goes through ``git/process.py``'s bounded runner. The
raw change list comes from ``git diff --raw --numstat -z`` — the same NUL
framing the history surface parses, with the same quirks — and per-file patches
come from a path-limited ``git diff`` fed through the *patch-file*
parser. Reusing that parser is the point of having one format: git's
own output must round-trip through the neutral model or the model is
wrong.

Merges are compared against their first parent
(``--diff-merges=first-parent``), matching the history surface.
"""

from __future__ import annotations

import asyncio
import logging
import os
from base64 import b64decode
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from metabrowser.diff.adapters.base import DiffSourceError
from metabrowser.diff.adapters.patch_file import MAX_PATCH_BYTES, name_paths, parse_unified_patch
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
    GitOutputTooLargeError,
    RepositoryStoreTarget,
    as_location,
    failure_detail,
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

type _SideKey = tuple[str | None, str | None]


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
    """

    name = "git"

    def __init__(self, repo: Path | GitLocation) -> None:
        self._location = as_location(repo)
        self._empty_tree_oid: str | None = None

    async def _rev_parse(self, revision: str) -> str:
        pin = self._location.pinned_revision
        if pin is not None and revision in {"HEAD", pin}:
            return pin
        try:
            out = await run_git_at(
                ["rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}"],
                self._location,
            )
        except GitError as exc:
            raise DiffSourceError(f"unknown revision {revision!r}") from exc
        return out.decode("ascii").strip()

    async def resolve(self, intent: dict[str, Any]) -> ResolvedComparison:
        base_policy = BasePolicy(intent.get("base_policy", "direct"))
        if "revision" in intent:
            # One revision: compare against its first parent (root commits
            # against the empty tree).
            right = await self._rev_parse(str(intent["revision"]))
            base_policy = BasePolicy.first_parent
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
            left = await self._rev_parse(str(intent["left"]))
            right = await self._rev_parse(str(intent["right"]))
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
        records, numstat = self._parse_raw(listed.split(b"\0"))
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
    def _parse_raw(
        tokens: list[bytes],
    ) -> tuple[
        list[tuple[str, str, str, str, str, int | None, bytes | None, bytes | None]], list[bytes]
    ]:
        """``--raw -z`` records: header NUL path [NUL path2] NUL ..., and the tokens after.

        The first record can arrive with a leading newline between the
        format section and the raw section — the quirk the history
        surface documents — so headers are lstripped. A record is read by its
        shape, so a path starting with ``:`` stays a path, and the first token
        that opens no record is where ``--numstat`` starts.
        """
        records: list[tuple[str, str, str, str, str, int | None, bytes | None, bytes | None]] = []
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
        """
        listed = manifest if manifest is not None else await self.manifest(resolved)
        by_id = {entry.id: entry for entry in listed.files}
        missing = [file_id for file_id in file_ids if file_id not in by_id]
        if missing:
            raise DiffSourceError(f"no file {missing[0]!r} in this comparison")
        changes = [by_id[file_id] for file_id in file_ids]
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
        return PatchHydration(
            patches=patches,
            left_out=tuple(change.id for change in left_out),
            too_large=budgeted.too_large,
            deferred=budgeted.deferred,
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
    ) -> bytes:
        return await run_git_at(
            [
                # Paths here are names, never patterns: `*` and `:(top)` mean themselves.
                "--literal-pathspecs",
                "diff",
                *(["-M50", "-C"] if renames else ["--no-renames"]),
                *([] if diff_filter is None else [f"--diff-filter={diff_filter}"]),
                # The shape the parser reads, whatever a folder's configuration says: Git's
                # own prefixes, which name a hunkless section, and no external driver.
                "--src-prefix=a/",
                "--dst-prefix=b/",
                "--no-ext-diff",
                "--diff-merges=first-parent",
                *self._endpoints(resolved),
                *([] if pathspec is None else ["--", *pathspec]),
            ],
            self._location,
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
