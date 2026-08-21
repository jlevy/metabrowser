"""Git source: File Diff Format from revisions in a local repository.

Every subprocess goes through ``git/process.py``'s bounded runner. The
raw change list comes from ``git diff --raw -z`` — the same NUL framing
the history surface parses, with the same quirks — and per-file patches
come from a path-limited ``git diff`` fed through the *patch-file*
parser. Reusing that parser is the point of having one format: git's
own output must round-trip through the neutral model or the model is
wrong.

Merges are compared against their first parent
(``--diff-merges=first-parent``), matching the history surface.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from hashlib import sha256
from pathlib import Path
from typing import Any

from metabrowser.diff.adapters.base import DiffSourceError
from metabrowser.diff.adapters.patch_file import parse_unified_patch
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
from metabrowser.git.process import GitError, run_git

MAX_MANIFEST_FILES = 2000
"""Manifest cap. A 2000-file change set is far past reviewable; beyond it
the manifest reports `truncated` with a cursor rather than growing without
bound, matching the patch-file parser's section cap."""

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


class GitDiffSource:
    """The worktree-tied source; ``repo_root`` must already be a repository."""

    name = "git"

    def __init__(self, repo_root: Path) -> None:
        self._root = repo_root
        self._empty_tree_oid: str | None = None

    async def _rev_parse(self, revision: str) -> str:
        try:
            out = await run_git(["rev-parse", "--verify", f"{revision}^{{commit}}"], cwd=self._root)
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
                left = ""  # root commit; git's empty-tree side
                await self._ensure_empty_tree_oid()
        else:
            left = await self._rev_parse(str(intent["left"]))
            right = await self._rev_parse(str(intent["right"]))
            if base_policy is BasePolicy.merge_base:
                out = await run_git(["merge-base", left, right], cwd=self._root)
                left = out.decode("ascii").strip()
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

    async def _ensure_empty_tree_oid(self) -> None:
        """Derive the repo's empty-tree oid once, honoring its object format.

        The SHA-1 constant is well known, but a repository initialized
        with ``objectFormat = sha256`` has a different one, and a wrong
        oid fails every root-commit comparison there.
        """
        if self._empty_tree_oid is None:
            out = await run_git(["hash-object", "-t", "tree", "/dev/null"], cwd=self._root)
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
        raw = await run_git(
            [
                "diff",
                "--raw",
                "-z",
                "--no-abbrev",
                "-M50",
                "-C",
                "--diff-merges=first-parent",
                *endpoints,
            ],
            cwd=self._root,
        )
        numstat = await run_git(
            ["diff", "--numstat", "-z", "-M50", "-C", "--diff-merges=first-parent", *endpoints],
            cwd=self._root,
        )
        counts = self._parse_numstat(numstat)
        files: list[FileChange] = []
        total_add = total_del = 0
        exact = True
        truncated = False
        for index, record in enumerate(self._parse_raw(raw), start=1):
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
        raw: bytes,
    ) -> list[tuple[str, str, str, str, str, int | None, bytes | None, bytes | None]]:
        """``--raw -z`` records: header NUL path [NUL path2] NUL ...

        The first record can arrive with a leading newline between the
        format section and the raw section — the quirk the history
        surface documents — so headers are lstripped.
        """
        records: list[tuple[str, str, str, str, str, int | None, bytes | None, bytes | None]] = []
        tokens = raw.split(b"\0")
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
        return records

    @staticmethod
    def _parse_numstat(raw: bytes) -> dict[bytes, tuple[int, int] | None]:
        """``--numstat -z``: additions TAB deletions TAB path (or NUL old NUL new).

        Binary files report ``-`` counts and map to None.
        """
        counts: dict[bytes, tuple[int, int] | None] = {}
        tokens = raw.split(b"\0")
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
        self, resolved: ResolvedComparison, file_ids: Sequence[str]
    ) -> dict[str, FilePatch]:
        """Hydrate any number of files from one diff run and one parse.

        The whole diff, unrestricted: limiting a rename to its own two
        paths makes git split it into a delete and an add, so section
        selection happens here rather than through a pathspec. Running
        it once per comparison — not once per file — is what keeps a
        50-file commit click at subprocess cost O(1); cross-request
        caching remains the future service's job. Bounded by run_git's
        output cap.
        """
        manifest = await self.manifest(resolved)
        by_id = {entry.id: entry for entry in manifest.files}
        missing = [file_id for file_id in file_ids if file_id not in by_id]
        if missing:
            raise DiffSourceError(f"no file {missing[0]!r} in this comparison")
        endpoints = self._endpoints(resolved)
        out = await run_git(
            ["diff", "-M50", "-C", "--diff-merges=first-parent", *endpoints],
            cwd=self._root,
        )
        document = parse_unified_patch(out)

        def side_key(side: EntrySide | None) -> tuple[str | None, str | None]:
            return (side.path if side else None, side.path_b64 if side else None)

        parsed_by_sides: dict[
            tuple[tuple[str | None, str | None], tuple[str | None, str | None]], FilePatch
        ] = {}
        for parsed_change in document.manifest.files:
            parsed = document.patches.get(parsed_change.id)
            if parsed is not None:
                key = (side_key(parsed_change.old), side_key(parsed_change.new))
                parsed_by_sides.setdefault(key, parsed)

        result: dict[str, FilePatch] = {}
        for file_id in file_ids:
            change = by_id[file_id]
            wanted = (side_key(change.old), side_key(change.new))
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
            raise DiffSourceError(f"file {file_id!r} not found in the produced diff")
        return result

    @staticmethod
    def _merge_type_change_sections(
        document: ChangeSetDocument,
        wanted: tuple[tuple[str | None, str | None], tuple[str | None, str | None]],
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

    async def content(
        self, resolved: ResolvedComparison, file_id: str, side: str
    ) -> AsyncIterator[bytes]:
        manifest = await self.manifest(resolved)
        change = next((entry for entry in manifest.files if entry.id == file_id), None)
        if change is None:
            raise DiffSourceError(f"no file {file_id!r} in this comparison")
        entry = change.old if side == "old" else change.new
        if entry is None or entry.content.kind is not ContentRefKind.git_object:
            raise DiffSourceError(f"file {file_id!r} has no {side} git content")
        blob = await run_git(["cat-file", "blob", str(entry.content.oid)], cwd=self._root)
        yield blob
