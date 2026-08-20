"""``metab --diff``: File Diff Format from the command line.

The CLI is the standalone test surface for the diff data plane: the same
documents the browser renders, produced with no server running and
captured by the tryscript goldens. ``SPEC`` is ``BASE..TARGET``, a
single revision (compared against its first parent), or a path to a
``.patch``/``.diff`` file. ``--format json`` emits the hydrated
ChangeSetDocument; the text form is a fixed-width summary.
``--diff-check`` runs the apply oracle and reports the tree hashes it
compared.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import NoReturn

import typer

from metabrowser.diff.adapters.base import DiffSourceError
from metabrowser.diff.adapters.git import GitDiffSource
from metabrowser.diff.adapters.patch_file import MAX_PATCH_BYTES, parse_unified_patch
from metabrowser.diff.apply import TreeEntry, TreeSnapshot, apply_change_set
from metabrowser.diff.format import (
    Availability,
    ChangeKind,
    ChangeSetDocument,
    ContentRefKind,
    EntryType,
    FileChange,
    SnapshotKind,
    dump_document,
    validate_document,
)
from metabrowser.git.process import GitError, run_git

_KIND_LETTERS = {
    ChangeKind.added: "A",
    ChangeKind.deleted: "D",
    ChangeKind.modified: "M",
    ChangeKind.renamed: "R",
    ChangeKind.copied: "C",
    ChangeKind.type_changed: "T",
    ChangeKind.unmerged: "U",
}


def _fail(message: str) -> NoReturn:
    typer.echo(f"diff error: {message}", err=True)
    raise typer.Exit(code=2)


def _load_patch_document(root: Path, spec: str) -> ChangeSetDocument:
    candidate = (root / spec).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        _fail(f"patch path {spec!r} escapes the served root")
    data = candidate.read_bytes()[: MAX_PATCH_BYTES + 1]
    return parse_unified_patch(data)


async def _hydrate_git_document(root: Path, spec: str) -> ChangeSetDocument:
    source = GitDiffSource(root)
    if "..." in spec:
        # Git's three-dot idiom: compare right against the merge base —
        # the semantics a pull-request diff uses.
        left, _, right = spec.partition("...")
        intent: dict[str, str] = {"left": left, "right": right, "base_policy": "merge_base"}
    elif ".." in spec:
        left, _, right = spec.partition("..")
        intent = {"left": left, "right": right}
    else:
        intent = {"revision": spec}
    resolved = await source.resolve(intent)
    manifest = await source.manifest(resolved)
    ready_ids = [
        change.id for change in manifest.files if change.availability is Availability.ready
    ]
    # One diff run and one parse for every file (review R3); the CLI
    # hydrates the whole comparison, so the bulk path is the only sane one.
    patches = await source.file_patches(resolved, ready_ids) if ready_ids else {}
    document = ChangeSetDocument(
        schema="file-diff-v1",
        schema_version=1,
        resolved=resolved,
        manifest=manifest,
        patches=patches,
    )
    return validate_document(dump_document(document))


def _build_document(root: Path, spec: str) -> ChangeSetDocument:
    if spec.endswith((".patch", ".diff")) and (root / spec).is_file():
        return _load_patch_document(root, spec)
    try:
        return asyncio.run(_hydrate_git_document(root, spec))
    except (DiffSourceError, GitError) as exc:
        _fail(str(exc))


def _describe(change: FileChange) -> str:
    letter = _KIND_LETTERS[change.kind]
    if change.similarity is not None:
        letter = f"{letter}{change.similarity}"
    old, new = change.old, change.new
    if change.kind in (ChangeKind.renamed, ChangeKind.copied) and old and new:
        name = f"{old.path} -> {new.path}"
    else:
        side = new or old
        assert side is not None
        name = side.path
    notes: list[str] = []
    if old and new and old.mode is not new.mode:
        notes.append(f"{old.mode.value}->{new.mode.value}")
    if old and new and old.entry_type is not new.entry_type:
        notes.append(f"{old.entry_type.value}->{new.entry_type.value}")
    if change.availability is not Availability.ready:
        notes.append(change.availability.value)
    elif change.additions is not None and change.deletions is not None:
        notes.append(f"+{change.additions} -{change.deletions}")
    return f"{letter:<4} {name}" + (f"  [{', '.join(notes)}]" if notes else "")


def _print_text(document: ChangeSetDocument) -> None:
    resolved = document.resolved
    left = resolved.left.id or resolved.left.kind.value
    right = resolved.right.id or resolved.right.kind.value
    typer.echo(f"comparison {resolved.comparison_id} ({resolved.base_policy.value})")
    typer.echo(f"left  {left}")
    typer.echo(f"right {right}")
    totals = document.manifest.totals
    exactness = "exact" if totals.exact else "estimated"
    plus = "?" if totals.additions is None else str(totals.additions)
    minus = "?" if totals.deletions is None else str(totals.deletions)
    typer.echo(f"files {totals.files}  +{plus} -{minus}  ({exactness})")
    for change in document.manifest.files:
        typer.echo(_describe(change))
    if document.manifest.truncated:
        typer.echo(f"truncated: continue from cursor {document.manifest.cursor!r}")


def _print_patch(document: ChangeSetDocument, wanted_path: str) -> None:
    for change in document.manifest.files:
        side = change.new or change.old
        if side is None or side.path != wanted_path:
            continue
        patch = document.patches.get(change.id)
        if patch is None:
            _fail(f"{wanted_path!r} carries no textual patch ({change.availability.value})")
            return
        for hunk in patch.hunks:
            heading = f" {hunk.heading}" if hunk.heading else ""
            typer.echo(
                f"@@ -{hunk.old_start},{hunk.old_count} +{hunk.new_start},{hunk.new_count} @@"
                + heading
            )
            for line in hunk.lines:
                marker = {"context": " ", "add": "+", "del": "-"}[line.op.value]
                typer.echo(f"{marker}{line.text}")
                if line.no_newline:
                    typer.echo("\\ No newline at end of file")
        return
    _fail(f"no changed file named {wanted_path!r} in this comparison")


async def _materialize(root: Path, revision: str) -> TreeSnapshot:
    listing = await run_git(["ls-tree", "-r", "-z", "--full-tree", revision], cwd=root)
    entries: dict[str, TreeEntry] = {}
    for record in listing.split(b"\0"):
        if not record:
            continue
        meta, path_raw = record.split(b"\t", 1)
        mode_raw, obj_type, oid = meta.decode("ascii").split(" ")
        path = path_raw.decode("utf-8", "surrogateescape")
        if obj_type == "commit":
            entries[path] = TreeEntry(EntryType.submodule, mode_raw, oid.encode("ascii"))
            continue
        content = await run_git(["cat-file", "blob", oid], cwd=root)
        entry_type = EntryType.symlink if mode_raw == "120000" else EntryType.file
        entries[path] = TreeEntry(entry_type, mode_raw, content)
    return TreeSnapshot(entries=entries)


def _check_apply(root: Path, document: ChangeSetDocument) -> None:
    """The oracle, from the command line: rebuild the target tree and compare."""
    resolved = document.resolved
    if resolved.right.kind is not SnapshotKind.commit or resolved.right.id is None:
        _fail("--diff-check needs a revision comparison, not a patch file")
        return

    async def run_check() -> tuple[str, str]:
        base_tree = (
            await _materialize(root, str(resolved.left.id))
            if resolved.left.id is not None
            else TreeSnapshot()
        )
        target_tree = await _materialize(root, str(resolved.right.id))
        # apply's resolver is synchronous, so every referenced side is
        # prefetched here and served from memory.
        prefetched: dict[tuple[str, str], bytes] = {}
        for change in document.manifest.files:
            for side_name, entry in (("old", change.old), ("new", change.new)):
                if entry is not None and entry.content.kind is ContentRefKind.git_object:
                    prefetched[(change.id, side_name)] = await run_git(
                        ["cat-file", "blob", str(entry.content.oid)], cwd=root
                    )

        def resolve_content(change: FileChange, side: str) -> bytes:
            try:
                return prefetched[(change.id, side)]
            except KeyError as exc:
                raise DiffSourceError(f"no content for {change.id}/{side}") from exc

        produced = apply_change_set(document, base_tree, resolve_content)
        return produced.tree_hash(), target_tree.tree_hash()

    produced_hash, target_hash = asyncio.run(run_check())
    typer.echo(f"produced {produced_hash}")
    typer.echo(f"target   {target_hash}")
    if produced_hash != target_hash:
        typer.echo("apply: MISMATCH", err=True)
        raise typer.Exit(code=1)
    typer.echo("apply: clean")


def run_diff(
    root: Path,
    *,
    spec: str,
    fmt: str,
    patch_path: str | None,
    check: bool,
) -> None:
    if fmt == "yaml":
        # Silence would claim success while printing the wrong format.
        _fail("--format yaml is not supported in diff mode; use text or json")
    document = _build_document(root, spec)
    if check:
        _check_apply(root, document)
        return
    if patch_path is not None:
        _print_patch(document, patch_path)
        return
    if fmt == "json":
        json.dump(dump_document(document), sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return
    _print_text(document)
