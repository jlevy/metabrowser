"""Git adapter against a real repository, ending at the apply oracle.

The oracle is the test that matters: the document the adapter produces
for base..target, applied to the materialized base tree, must reproduce
git's own target tree byte-for-byte. If that holds, the model captured
everything the renderer could need.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from base64 import b64decode
from pathlib import Path
from typing import Any

import pytest

from metabrowser.diff.adapters import git as adapter
from metabrowser.diff.adapters.base import DiffSourceError
from metabrowser.diff.adapters.git import GitDiffSource
from metabrowser.diff.adapters.patch_file import parse_unified_patch
from metabrowser.diff.apply import apply_change_set
from metabrowser.diff.format import (
    Availability,
    ChangeKind,
    ChangeSetDocument,
    ChangeSetManifest,
    FileChange,
    FilePatch,
    ResolvedComparison,
    dump_document,
    validate_document,
)
from metabrowser.git.process import GitLocation, GitOutputTooLargeError, repository_store_target
from tests.diff_fixture_repo import build_diff_fixture, git, materialize_tree
from tests.required_tools import needs_git

pytestmark = needs_git


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
    # Binary changes contribute no lines and leave line totals exact.
    assert manifest.totals.exact is True
    assert binary.additions is None and binary.deletions is None
    pure_rename = by_path["renamed-steady.txt"]
    assert pure_rename.kind is ChangeKind.renamed
    assert pure_rename.similarity == 100
    copied = by_path["lib_copy.py"]
    assert copied.kind is ChangeKind.copied
    assert copied.old is not None and copied.old.path == "lib.py"
    retarget = by_path["link"]
    assert retarget.kind is ChangeKind.modified
    assert retarget.old is not None and retarget.old.entry_type.value == "symlink"
    assert retarget.new is not None and retarget.new.entry_type.value == "symlink"


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
    # Through the scrubbing helper: inside a githook, git exports GIT_DIR
    # pointing at the real repository, and it beats -C.
    probe = git(root, "log", "--format=%H", "--reverse").decode().split()
    assert probe == [base, target]
    assert base.startswith("55") or len(base) == 40  # shape only; ids asserted in goldens


def test_store_location_honors_the_pin_not_store_head(
    repo: tuple[Path, str, str], tmp_path: Path
) -> None:
    """A bare store pin diffs that OID; HEAD is not the cloned default branch."""
    root, base, target = repo
    store = tmp_path / "store.git"
    git(root.parent, "clone", "--bare", "--template=", str(root), str(store))
    location = GitLocation.revision(repository_store_target(git_dir=store), base)
    source = GitDiffSource(location)
    head = asyncio.run(source.resolve({"revision": "HEAD"}))
    assert head.right.id == base
    assert head.right.id != target
    worktree = GitDiffSource(root)
    expected = asyncio.run(worktree.resolve({"left": base, "right": target}))
    actual = asyncio.run(source.resolve({"left": base, "right": target}))
    expected_manifest = asyncio.run(worktree.manifest(expected))
    actual_manifest = asyncio.run(source.manifest(actual))
    assert [change.kind for change in expected_manifest.files] == [
        change.kind for change in actual_manifest.files
    ]
    modified = _by_new_path(actual_manifest)["a.py"]
    patch = asyncio.run(source.file_patch(actual, modified.id))
    ops = [line.op.value for hunk in patch.hunks for line in hunk.lines]
    assert "del" in ops and "add" in ops
    document = dump_document(
        ChangeSetDocument(
            schema="file-diff-v1",
            schema_version=1,
            resolved=actual,
            manifest=actual_manifest,
            patches={modified.id: patch},
        )
    )
    assert str(store) not in json.dumps(document)


def test_store_location_content_reads_through_the_batch_pool(
    repo: tuple[Path, str, str], tmp_path: Path
) -> None:
    root, base, target = repo
    store = tmp_path / "store.git"
    git(root.parent, "clone", "--bare", "--template=", str(root), str(store))
    location = GitLocation.revision(repository_store_target(git_dir=store), target)
    source = GitDiffSource(location)
    worktree = GitDiffSource(root)

    async def _run() -> None:
        resolved = await source.resolve({"left": base, "right": target})
        manifest = await source.manifest(resolved)
        modified = _by_new_path(manifest)["a.py"]
        assert modified.new is not None and modified.new.content.oid is not None
        body = b"".join([chunk async for chunk in source.content(resolved, modified.id, "new")])
        expected = git(root, "cat-file", "blob", modified.new.content.oid)
        assert body == expected
        wt_resolved = await worktree.resolve({"left": base, "right": target})
        wt_manifest = await worktree.manifest(wt_resolved)
        wt_modified = _by_new_path(wt_manifest)["a.py"]
        wt_body = b"".join(
            [chunk async for chunk in worktree.content(wt_resolved, wt_modified.id, "new")]
        )
        assert wt_body == expected
        added = _by_new_path(manifest)["new.md"]
        with pytest.raises(DiffSourceError):
            async for _chunk in source.content(resolved, added.id, "old"):
                pass
        with pytest.raises(DiffSourceError, match="no file"):
            async for _chunk in source.content(resolved, "missing", "new"):
                pass
        assert str(store) not in body.decode("utf-8", "replace")

    asyncio.run(_run())


# ── The limited patch is the unrestricted patch ─────────────────────
#
# The route limits the diff to the files it serves. What it serves must be what the whole
# diff says about those files, byte for byte, renames and copies included.


def _patch_bytes(patches: dict[str, FilePatch]) -> dict[str, Any]:
    return {file_id: patch.model_dump(mode="json") for file_id, patch in patches.items()}


def _whole_run(source: GitDiffSource, resolved: ResolvedComparison) -> dict[str, Any]:
    """Every ready file, which asks for no pathspec: the unrestricted run."""
    manifest = asyncio.run(source.manifest(resolved))
    ready = [c.id for c in manifest.files if c.availability is Availability.ready]
    asked = [c.id for c in manifest.files]
    assert len(ready) < len(asked), "the fixture is meant to hold a binary file"
    document = parse_unified_patch(asyncio.run(source._patch(resolved, None)))
    found, left_out = source._patches_from(
        document, [c for c in manifest.files if c.availability is Availability.ready]
    )
    assert left_out == []
    return _patch_bytes(found)


def test_each_file_alone_is_what_the_whole_diff_says(repo: tuple[Path, str, str]) -> None:
    root, base, target = repo
    source = GitDiffSource(root)
    resolved = asyncio.run(source.resolve({"left": base, "right": target}))
    manifest = asyncio.run(source.manifest(resolved))
    whole = _whole_run(source, resolved)
    kinds = set()
    for change in manifest.files:
        if change.availability is not Availability.ready:
            continue
        kinds.add(change.kind)
        alone = asyncio.run(source.hydrate(resolved, [change.id], manifest=manifest))
        assert alone.left_out == ()
        assert _patch_bytes(alone.patches) == {change.id: whole[change.id]}
    assert {ChangeKind.renamed, ChangeKind.copied, ChangeKind.type_changed} <= kinds


def test_a_page_of_files_is_what_the_whole_diff_says(repo: tuple[Path, str, str]) -> None:
    root, base, target = repo
    source = GitDiffSource(root)
    resolved = asyncio.run(source.resolve({"left": base, "right": target}))
    manifest = asyncio.run(source.manifest(resolved))
    whole = _whole_run(source, resolved)
    ready = [c.id for c in manifest.files if c.availability is Availability.ready]
    for start in range(len(ready)):
        page = ready[start : start + 3]
        limited = asyncio.run(source.hydrate(resolved, page, manifest=manifest))
        assert _patch_bytes(limited.patches) == {file_id: whole[file_id] for file_id in page}


def test_the_manifest_is_the_two_listings_it_replaced(repo: tuple[Path, str, str]) -> None:
    """One run prints what the two runs printed, end to end, so it parses to the same files."""
    root, base, target = repo
    common = ["-M50", "-C", "--diff-merges=first-parent", base, target]
    raw = git(root, "diff", "--raw", "-z", "--no-abbrev", *common)
    numstat = git(root, "diff", "--numstat", "-z", *common)
    one = git(root, "diff", "--raw", "--numstat", "-z", "--no-abbrev", *common)
    assert one == raw + numstat
    records, rest = GitDiffSource._parse_raw(one.split(b"\0"))
    assert len(records) == raw.count(b":")
    assert GitDiffSource._parse_numstat(rest) == GitDiffSource._parse_numstat(numstat.split(b"\0"))


def _limit_fixture(tmp_path: Path) -> tuple[Path, str, str]:
    """Two renames with edits, in a repository whose rename limit stops the whole run."""
    root = tmp_path / "limit"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "diff.renameLimit", "1")
    body = "".join(f"line {number}\n" for number in range(40))
    (root / "one.txt").write_text(body)
    (root / "two.txt").write_text("other\n" + body)
    git(root, "add", "-A")
    git(root, "commit", "-qm", "base")
    base = git(root, "rev-parse", "HEAD").decode().strip()
    (root / "one.txt").rename(root / "one-moved.txt")
    (root / "two.txt").rename(root / "two-moved.txt")
    (root / "one-moved.txt").write_text(body + "more\n")
    (root / "two-moved.txt").write_text("another\n" + body)
    git(root, "add", "-A")
    git(root, "commit", "-qm", "target")
    return root, base, git(root, "rev-parse", "HEAD").decode().strip()


def test_past_the_rename_limit_asking_without_rename_detection_answers(tmp_path: Path) -> None:
    """The one way the runs differ. The whole run lists adds and deletes; a limited one of
    one add and one delete is under the limit and pairs them, which matches nothing."""
    root, base, target = _limit_fixture(tmp_path)
    source = GitDiffSource(root)
    resolved = asyncio.run(source.resolve({"left": base, "right": target}))
    manifest = asyncio.run(source.manifest(resolved))
    assert {c.kind for c in manifest.files} == {ChangeKind.added, ChangeKind.deleted}
    whole = _whole_run_of_all(source, resolved)
    paths = {(c.new or c.old).path: c.id for c in manifest.files}  # pyright: ignore[reportOptionalMemberAccess]
    pair = [paths["one.txt"], paths["one-moved.txt"]]
    limited = asyncio.run(source.hydrate(resolved, pair, manifest=manifest))
    assert limited.left_out == ()
    assert _patch_bytes(limited.patches) == {file_id: whole[file_id] for file_id in pair}


def _whole_run_of_all(source: GitDiffSource, resolved: ResolvedComparison) -> dict[str, Any]:
    manifest = asyncio.run(source.manifest(resolved))
    document = parse_unified_patch(asyncio.run(source._patch(resolved, None)))
    found, left_out = source._patches_from(document, list(manifest.files))
    assert left_out == []
    return _patch_bytes(found)


def test_a_name_that_is_not_utf8_reaches_git_as_its_bytes(tmp_path: Path) -> None:
    """Written with fast-import, because a filesystem such as APFS refuses such a name."""
    root = tmp_path / "names"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    name = b"calf\xe9 *.txt"

    def commit(mark: int, parent: bytes, keep: bytes, named: bytes) -> bytes:
        return b"".join(
            [
                b"commit refs/heads/main\n",
                b"mark :%d\n" % mark,
                b"committer T <t@example.com> 1700000000 +0000\n",
                b"data 1\nx\n",
                parent,
                b"M 100644 inline keep.txt\ndata %d\n%s\n" % (len(keep), keep),
                b'M 100644 inline "calf\\351 *.txt"\ndata %d\n%s\n' % (len(named), named),
            ]
        )

    stream = commit(1, b"", b"one\n", b"old\n") + commit(2, b"from :1\n", b"two\n", b"new\n")
    subprocess.run(["git", "-C", str(root), "fast-import", "--quiet"], input=stream, check=True)
    base = git(root, "rev-parse", "main~1").decode().strip()
    target = git(root, "rev-parse", "main").decode().strip()

    source = GitDiffSource(root)
    resolved = asyncio.run(source.resolve({"left": base, "right": target}))
    manifest = asyncio.run(source.manifest(resolved))
    named = next(c for c in manifest.files if c.new is not None and c.new.path_b64 is not None)
    assert named.new is not None and b64decode(str(named.new.path_b64)) == name
    hydrated = asyncio.run(source.hydrate(resolved, [named.id], manifest=manifest))
    assert hydrated.left_out == ()
    assert [line.text for line in hydrated.patches[named.id].hunks[0].lines] == ["old", "new"]


def test_past_the_argument_bound_the_diff_runs_unrestricted(
    repo: tuple[Path, str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, base, target = repo
    source = GitDiffSource(root)
    resolved = asyncio.run(source.resolve({"left": base, "right": target}))
    manifest = asyncio.run(source.manifest(resolved))
    change = next(c for c in manifest.files if c.availability is Availability.ready)
    monkeypatch.setattr(adapter, "MAX_PATHSPEC_BYTES", 1)
    assert adapter._pathspec([change]) is None
    hydrated = asyncio.run(source.hydrate(resolved, [change.id], manifest=manifest))
    assert hydrated.left_out == () and change.id in hydrated.patches


# ── The bound is per file ───────────────────────────────────────────


def _sized_fixture(tmp_path: Path) -> tuple[GitDiffSource, ResolvedComparison, ChangeSetManifest]:
    """Files of known sizes: `big` past a small bound, and `a`, `b`, `c` within it."""
    root = tmp_path / "sized"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    (root / "keep.txt").write_text("keep\n")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "base")
    base = git(root, "rev-parse", "HEAD").decode().strip()
    (root / "a.txt").write_text("a\n" * 30)
    (root / "b.txt").write_text("b\n" * 30)
    (root / "big.txt").write_text("big line\n" * 1000)
    (root / "c.txt").write_text("c\n" * 30)
    git(root, "add", "-A")
    git(root, "commit", "-qm", "target")
    target = git(root, "rev-parse", "HEAD").decode().strip()
    source = GitDiffSource(root)
    resolved = asyncio.run(source.resolve({"left": base, "right": target}))
    return source, resolved, asyncio.run(source.manifest(resolved))


def _ids(manifest: ChangeSetManifest) -> dict[str, str]:
    return {c.new.path: c.id for c in manifest.files if c.new is not None}


def test_a_file_past_the_bound_costs_only_itself(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, resolved, manifest = _sized_fixture(tmp_path)
    ids = _ids(manifest)
    monkeypatch.setattr(adapter, "MAX_FILE_PATCH_BYTES", 500)
    asked = [ids["a.txt"], ids["big.txt"]]
    hydrated = asyncio.run(source.hydrate(resolved, asked, manifest=manifest))
    assert set(hydrated.patches) == {ids["a.txt"]}
    assert hydrated.too_large == (ids["big.txt"],)
    assert hydrated.deferred == () and hydrated.left_out == ()


def test_a_file_past_what_one_run_hydrates_is_deferred_and_loads_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, resolved, manifest = _sized_fixture(tmp_path)
    ids = _ids(manifest)
    monkeypatch.setattr(adapter, "MAX_FILE_PATCH_BYTES", 400)
    asked = [ids["a.txt"], ids["b.txt"], ids["c.txt"]]
    hydrated = asyncio.run(source.hydrate(resolved, asked, manifest=manifest))
    assert set(hydrated.patches) == {ids["a.txt"]}, "each is within the bound; the run is not"
    assert set(hydrated.deferred) == {ids["b.txt"], ids["c.txt"]}
    alone = asyncio.run(source.hydrate(resolved, [ids["c.txt"]], manifest=manifest))
    assert set(alone.patches) == {ids["c.txt"]}


def test_what_is_kept_parses_to_what_the_whole_patch_says(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, resolved, manifest = _sized_fixture(tmp_path)
    ids = _ids(manifest)
    whole = _whole_run_of_all(source, resolved)
    monkeypatch.setattr(adapter, "MAX_FILE_PATCH_BYTES", 500)
    asked = [ids["a.txt"], ids["big.txt"], ids["c.txt"]]
    hydrated = asyncio.run(source.hydrate(resolved, asked, manifest=manifest))
    assert _patch_bytes(hydrated.patches) == {
        file_id: whole[file_id] for file_id in (ids["a.txt"], ids["c.txt"])
    }


def test_past_gits_output_cap_one_file_is_too_large_and_many_are_deferred(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, resolved, manifest = _sized_fixture(tmp_path)
    ids = _ids(manifest)

    async def overflows(*_args: Any, **_kwargs: Any) -> bytes:
        raise GitOutputTooLargeError("too much")

    monkeypatch.setattr(adapter, "run_git_at", overflows)
    one = asyncio.run(source.hydrate(resolved, [ids["big.txt"]], manifest=manifest))
    assert one.too_large == (ids["big.txt"],) and one.patches == {}
    many = asyncio.run(source.hydrate(resolved, [ids["a.txt"], ids["b.txt"]], manifest=manifest))
    assert many.deferred == (ids["a.txt"], ids["b.txt"]) and many.too_large == ()
