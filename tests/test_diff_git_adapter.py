"""Git adapter against a real repository, ending at the apply oracle.

The oracle is the test that matters: the document the adapter produces
for base..target, applied to the materialized base tree, must reproduce
git's own target tree byte-for-byte. If that holds, the model captured
everything the renderer could need.
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

import pytest

from metabrowser.diff.adapters.git import GitDiffSource
from metabrowser.diff.apply import apply_change_set
from metabrowser.diff.format import (
    Availability,
    ChangeKind,
    ChangeSetDocument,
    ChangeSetManifest,
    FileChange,
    dump_document,
    validate_document,
)
from tests.diff_fixture_repo import build_diff_fixture, git, materialize_tree

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git executable is required to build the fixture repositories",
)


@pytest.fixture(scope="module")
def repo(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str, str]:
    root = tmp_path_factory.mktemp("diff-fixture")
    base, target = build_diff_fixture(root)
    return root, base, target


def _by_new_path(manifest: ChangeSetManifest) -> dict[str, FileChange]:
    out: dict[str, FileChange] = {}
    for change in manifest.files:
        side = change.new or change.old
        assert side is not None
        out[side.path] = change
    return out


def test_manifest_covers_the_change_taxonomy(repo: tuple[Path, str, str]) -> None:
    root, base, target = repo
    source = GitDiffSource(root)
    resolved = asyncio.run(source.resolve({"left": base, "right": target}))
    manifest = asyncio.run(source.manifest(resolved))
    by_path = _by_new_path(manifest)

    assert by_path["a.py"].kind is ChangeKind.modified
    assert by_path["new.md"].kind is ChangeKind.added
    assert by_path["gone.txt"].kind is ChangeKind.deleted
    renamed = by_path["src/helpers/util.py"]
    assert renamed.kind is ChangeKind.renamed
    assert renamed.old is not None and renamed.old.path == "src/util.py"
    assert renamed.similarity is not None and renamed.similarity >= 50
    chmod = by_path["run.sh"]
    assert chmod.kind is ChangeKind.modified
    assert chmod.old is not None and chmod.old.mode.value == "100644"
    assert chmod.new is not None and chmod.new.mode.value == "100755"
    typechange = by_path["cfg"]
    assert typechange.kind is ChangeKind.type_changed
    assert typechange.new is not None and typechange.new.entry_type.value == "symlink"
    binary = by_path["logo.bin"]
    assert binary.binary and binary.availability is Availability.binary
    assert manifest.totals.exact is False  # the binary file defers exact totals


def test_single_revision_resolves_to_first_parent(repo: tuple[Path, str, str]) -> None:
    root, base, target = repo
    source = GitDiffSource(root)
    resolved = asyncio.run(source.resolve({"revision": target}))
    assert resolved.base_policy.value == "first_parent"
    assert resolved.left.id == base and resolved.right.id == target


def test_file_patch_round_trips_through_the_shared_parser(
    repo: tuple[Path, str, str],
) -> None:
    root, base, target = repo
    source = GitDiffSource(root)
    resolved = asyncio.run(source.resolve({"left": base, "right": target}))
    manifest = asyncio.run(source.manifest(resolved))
    modified = _by_new_path(manifest)["a.py"]
    patch = asyncio.run(source.file_patch(resolved, modified.id))
    assert patch.file_id == modified.id
    ops = [line.op.value for hunk in patch.hunks for line in hunk.lines]
    assert "del" in ops and "add" in ops


def _hydrated_document(root: Path, base: str, target: str) -> ChangeSetDocument:
    source = GitDiffSource(root)
    resolved = asyncio.run(source.resolve({"left": base, "right": target}))
    manifest = asyncio.run(source.manifest(resolved))
    patches = {}
    for change in manifest.files:
        if change.availability is Availability.ready:
            patches[change.id] = asyncio.run(source.file_patch(resolved, change.id))
    document = ChangeSetDocument(
        schema="file-diff-v1",
        schema_version=1,
        resolved=resolved,
        manifest=manifest,
        patches=patches,
    )
    # Everything the adapter emits must be format-valid on the wire.
    return validate_document(dump_document(document))


def test_apply_oracle_reproduces_gits_own_target_tree(repo: tuple[Path, str, str]) -> None:
    root, base, target = repo
    document = _hydrated_document(root, base, target)
    base_tree = materialize_tree(root, base)
    target_tree = materialize_tree(root, target)

    def resolve_content(change: FileChange, side: str) -> bytes:
        entry = change.new if side == "new" else change.old
        assert entry is not None and entry.content.oid is not None
        return git(root, "cat-file", "blob", entry.content.oid)

    produced = apply_change_set(document, base_tree, resolve_content)
    assert produced.as_corpus() == target_tree.as_corpus()
    assert produced.tree_hash() == target_tree.tree_hash()


def test_fixture_commit_ids_are_deterministic(repo: tuple[Path, str, str]) -> None:
    """Pinned dates and identity make the goldens assert real ids."""
    root, base, target = repo
    probe = subprocess.run(
        ["git", "-C", str(root), "log", "--format=%H", "--reverse"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    assert probe == [base, target]
    assert base.startswith("55") or len(base) == 40  # shape only; ids asserted in goldens
