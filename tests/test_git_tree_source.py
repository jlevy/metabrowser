"""GitPath codec, revision subject, and worktree-free tree/blob reads."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from contextlib import suppress
from dataclasses import replace
from pathlib import Path

import pytest

from metabrowser.git import tree_source as tree_module
from metabrowser.git.process import (
    GitTimeoutError,
    GitUnavailableError,
    repository_store_target,
)
from metabrowser.git.tree_source import (
    GIT_REVISION_CAPABILITIES,
    GitBatchProtocolError,
    GitBlobIndex,
    GitBlobTooLargeError,
    GitObjectUnavailableError,
    GitPath,
    GitPathError,
    GitRevisionSubject,
    GitTreeTally,
    git_revision_subject,
    read_store_blob,
    store_batch_reader_count,
)
from metabrowser.plugin_api import (
    UnsupportedSourceCapabilityError,
    require_source_capability,
    resolve_path,
    served_root,
)
from metabrowser.source import (
    attach_subject,
    get_source_session,
    reset_source_session,
)

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git executable is required",
)

_ZERO_OID = "0" * 40
_LFS_POINTER = (
    b"version https://git-lfs.github.com/spec/v1\n"
    b"oid sha256:4d7a214614ab2935c943f9e0ff69d22eadbb8f32b1258daaa5e2ca24d17e2393\n"
    b"size 12345\n"
)


def _git_env(root: Path) -> dict[str, str]:
    env = dict(os.environ)
    for name in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_COMMON_DIR",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    ):
        env.pop(name, None)
    env.update(
        {
            "GIT_AUTHOR_NAME": "Tree Source",
            "GIT_AUTHOR_EMAIL": "tree@example.invalid",
            "GIT_COMMITTER_NAME": "Tree Source",
            "GIT_COMMITTER_EMAIL": "tree@example.invalid",
            "GIT_AUTHOR_DATE": "2026-01-01T00:00:00 +0000",
            "GIT_COMMITTER_DATE": "2026-01-01T00:00:00 +0000",
            "GIT_CONFIG_GLOBAL": str(root / ".gitconfig-absent"),
            "GIT_CONFIG_SYSTEM": str(root / ".gitconfig-absent"),
        }
    )
    return env


def _git(cwd: Path, *args: str, env_root: Path | None = None) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        env=_git_env(env_root or cwd),
    )
    return result.stdout


def _hash_blob(work: Path, data: bytes) -> str:
    result = subprocess.run(
        ["git", "-C", str(work), "hash-object", "-w", "--stdin"],
        check=True,
        capture_output=True,
        input=data,
        env=_git_env(work),
    )
    return result.stdout.decode().strip()


def _index_info(work: Path, records: bytes) -> None:
    subprocess.run(
        ["git", "-C", str(work), "update-index", "-z", "--index-info"],
        check=True,
        capture_output=True,
        input=records,
        env=_git_env(work),
    )


def _build_store(tmp_path: Path) -> tuple[Path, str]:
    work = tmp_path / "work"
    store = tmp_path / "store.git"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    (work / "README.md").write_text("hello\n", encoding="utf-8")
    (work / "docs").mkdir()
    (work / "docs" / "note.txt").write_text("nested\n", encoding="utf-8")
    (work / "100%.html").write_text("<p>ok</p>\n", encoding="utf-8")
    (work / "link").symlink_to("README.md")
    (work / "big.bin").write_bytes(b"x" * 64)
    _git(work, "add", "-A")
    utf8_oid = _hash_blob(work, b"bytes\n")
    newline_oid = _hash_blob(work, b"newline-name\n")
    _index_info(
        work,
        b"100644 blob " + utf8_oid.encode() + b"\tx\xff.txt\x00"
        b"100644 blob " + newline_oid.encode() + b"\tnew\nline.txt\x00",
    )
    _git(work, "commit", "-qm", "one")
    first = _git(work, "rev-parse", "HEAD").decode().strip()
    _index_info(work, f"160000 commit {first}\tvendor/dep\x00".encode())
    _git(work, "commit", "-qm", "gitlink")
    commit = _git(work, "rev-parse", "HEAD").decode().strip()
    _git(tmp_path, "clone", "--bare", "--template=", str(work), str(store), env_root=tmp_path)
    return store, commit


def _delete_store_blob(store: Path, oid: str) -> None:
    """Remove one object so cat-file reports a miss, not a present blob."""

    loose = store / "objects" / oid[:2] / oid[2:]
    if not loose.is_file():
        pack_dir = store / "objects" / "pack"
        for pack in pack_dir.glob("*.pack"):
            subprocess.run(
                ["git", "-C", str(store), "unpack-objects", "-q"],
                check=True,
                capture_output=True,
                input=pack.read_bytes(),
                env=_git_env(store),
            )
            pack.unlink()
            pack.with_suffix(".idx").unlink(missing_ok=True)
    if not loose.is_file():
        raise AssertionError(f"store blob {oid} was not a loose object")
    loose.unlink()


def test_git_path_round_trips_invalid_utf8_and_newlines() -> None:
    path = GitPath.from_segments(b"docs", b"x\xff.txt", b"new\nline.txt", b"100%.html")
    wire = path.to_wire()
    assert GitPath.from_wire(wire) == path
    assert path.display().startswith("docs/")
    assert "\ufffd" in path.display()
    assert "\n" not in path.display()
    assert GitPath.from_segments(b"new\nline.txt").display() == "new\ufffdline.txt"
    assert GitPath.from_segments(b"x\xff.txt").display() == "x\ufffd.txt"
    assert path.parent().segments == (b"docs", b"x\xff.txt", b"new\nline.txt")
    assert GitPath.root().to_wire() == ""
    assert GitPath.from_wire("") == GitPath.root()
    ordered = sorted(
        [
            GitPath.from_segments(b"b"),
            GitPath.from_segments(b"a"),
            GitPath.from_segments(b"a", b"z"),
        ]
    )
    assert ordered[0].segments == (b"a",)


def test_git_path_refuses_nul_padding_and_noncanonical_atoms() -> None:
    with pytest.raises(GitPathError):
        GitPath.from_segments(b"a\x00b")
    with pytest.raises(GitPathError):
        GitPath.from_segments(b"a/b")
    with pytest.raises(GitPathError):
        GitPath.from_segments(b"")
    with pytest.raises(GitPathError):
        GitPath.from_wire("docs/note.txt")
    padded = GitPath.from_segments(b"docs").to_wire() + "="
    with pytest.raises(GitPathError):
        GitPath.from_wire(padded)
    with pytest.raises(GitPathError):
        GitPath.from_wire("g1-@@@@")


def test_git_path_from_display_accepts_names_and_wires() -> None:
    nested = GitPath.from_display("docs/note.txt")
    assert nested.segments == (b"docs", b"note.txt")
    assert GitPath.from_display(nested.to_wire()) == nested
    assert GitPath.from_display("") == GitPath.root()
    assert GitPath.from_display(".") == GitPath.root()
    with pytest.raises(GitPathError):
        GitPath.from_display("docs/../secret")
    with pytest.raises(GitPathError):
        GitPath.from_display("docs//note.txt")


def test_git_revision_subject_reads_trees_and_blobs_without_a_checkout(tmp_path: Path) -> None:
    async def _run() -> None:
        store, commit = _build_store(tmp_path)
        target = repository_store_target(git_dir=store)
        subject = await git_revision_subject(
            target=target, commit_oid=commit, store_identity="fixture"
        )
        source = subject.tree_source
        try:
            assert subject.kind == "git_revision"
            assert subject.filesystem_root is None
            assert subject.capabilities == GIT_REVISION_CAPABILITIES
            assert subject.identity == f"fixture:{commit}"
            assert (store / "index").exists() is False
            assert (store / "HEAD").is_file()

            children = await source.list_tree()
            names = {entry.path.segments[-1] for entry in children}
            assert b"README.md" in names
            assert b"docs" in names
            assert b"100%.html" in names
            assert b"link" in names
            assert b"x\xff.txt" in names
            assert b"new\nline.txt" in names
            assert b"vendor" in names

            readme = next(entry for entry in children if entry.path.segments[-1] == b"README.md")
            assert readme.size == 6
            assert await source.read_blob(readme.path) == b"hello\n"
            handle = source.resolve(readme.path.to_wire())
            assert handle is not None
            assert handle.is_file

            docs = next(entry for entry in children if entry.path.segments[-1] == b"docs")
            assert docs.size is None
            nested = await source.list_tree(docs.path)
            note = next(entry for entry in nested if entry.path.segments[-1] == b"note.txt")
            assert await source.read_blob(note.path) == b"nested\n"

            percent = next(entry for entry in children if entry.path.segments[-1] == b"100%.html")
            assert await source.read_blob(percent.path) == b"<p>ok</p>\n"

            link = next(entry for entry in children if entry.path.segments[-1] == b"link")
            assert link.is_symlink
            assert link.size == 9
            assert await source.read_blob(link.path) == b"README.md"

            odd = next(entry for entry in children if entry.path.segments[-1] == b"x\xff.txt")
            assert await source.read_blob(odd.path) == b"bytes\n"
            newline = next(
                entry for entry in children if entry.path.segments[-1] == b"new\nline.txt"
            )
            assert await source.read_blob(newline.path) == b"newline-name\n"

            vendor = next(entry for entry in children if entry.path.segments[-1] == b"vendor")
            vendor_kids = await source.list_tree(vendor.path)
            gitlink = next(entry for entry in vendor_kids if entry.path.segments[-1] == b"dep")
            assert gitlink.is_gitlink
            assert gitlink.size is None
            assert gitlink.oid == _git(tmp_path / "work", "rev-parse", "HEAD~1").decode().strip()
            handle = source.resolve(gitlink.path.to_wire())
            assert handle is not None
            assert handle.exists
            assert not handle.is_dir
            assert not handle.is_file
            try:
                await source.read_blob(gitlink.path)
                raise AssertionError("gitlink must not be read as a blob")
            except GitObjectUnavailableError:
                pass

            root_tally = await source.tree_tally()
            assert root_tally is not None
            assert root_tally.total_files == 7
            docs_tally = await source.tree_tally(docs.path)
            assert docs_tally == GitTreeTally(total_files=1, total_size=7)
            vendor_tally = await source.tree_tally(vendor.path)
            assert vendor_tally == GitTreeTally(total_files=0, total_size=0)
            listed_size = (readme.size or 0) + 7 + (percent.size or 0) + (link.size or 0)
            big = next(entry for entry in children if entry.path.segments[-1] == b"big.bin")
            listed_size += big.size or 0
            listed_size += odd.size or 0
            listed_size += newline.size or 0
            assert root_tally.total_size == listed_size

            missing = GitPath.from_segments(b"nope.txt")
            assert await source.resolve_path(missing) is None
            try:
                await source.read_blob_oid(_ZERO_OID)
                raise AssertionError("missing oid must fail closed")
            except GitObjectUnavailableError as exc:
                assert exc.code == "object_unavailable"
                assert exc.oid == _ZERO_OID
        finally:
            await subject.aclose()

    asyncio.run(_run())


def test_oversized_blob_is_refused_before_contents(tmp_path: Path) -> None:
    async def _run() -> None:
        store, commit = _build_store(tmp_path)
        subject = await git_revision_subject(
            target=repository_store_target(git_dir=store),
            commit_oid=commit,
            store_identity="fixture",
            max_blob_bytes=16,
        )
        source = subject.tree_source
        try:
            big = next(
                entry for entry in await source.list_tree() if entry.path.segments[-1] == b"big.bin"
            )
            try:
                await source.read_blob(big.path)
                raise AssertionError("oversized blob must be refused")
            except GitBlobTooLargeError as exc:
                assert exc.size == 64
                assert exc.max_bytes == 16
            small = next(
                entry
                for entry in await source.list_tree()
                if entry.path.segments[-1] == b"README.md"
            )
            assert await source.read_blob(small.path) == b"hello\n"
        finally:
            await subject.aclose()

    asyncio.run(_run())


def test_cancelled_blob_read_restarts_the_batch_reader(tmp_path: Path) -> None:
    async def _run() -> None:
        work = tmp_path / "work"
        store = tmp_path / "store.git"
        work.mkdir()
        _git(work, "init", "-q", "-b", "main")
        (work / "small.txt").write_text("ok\n", encoding="utf-8")
        (work / "huge.bin").write_bytes(os.urandom(2 * 1024 * 1024))
        _git(work, "add", "-A")
        _git(work, "commit", "-qm", "big")
        commit = _git(work, "rev-parse", "HEAD").decode().strip()
        _git(tmp_path, "clone", "--bare", "--template=", str(work), str(store), env_root=tmp_path)
        subject = await git_revision_subject(
            target=repository_store_target(git_dir=store),
            commit_oid=commit,
            store_identity="fixture",
        )
        source = subject.tree_source
        try:
            huge = next(
                entry
                for entry in await source.list_tree()
                if entry.path.segments[-1] == b"huge.bin"
            )
            task = asyncio.create_task(source.read_blob(huge.path))
            await asyncio.sleep(0)
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            small = next(
                entry
                for entry in await source.list_tree()
                if entry.path.segments[-1] == b"small.txt"
            )
            assert await source.read_blob(small.path) == b"ok\n"
        finally:
            await subject.aclose()

    asyncio.run(_run())


def test_git_revision_subject_gates_filesystem_hooks(tmp_path: Path) -> None:
    async def _run() -> None:
        store, commit = _build_store(tmp_path)
        subject = await git_revision_subject(
            target=repository_store_target(git_dir=store),
            commit_oid=commit,
            store_identity="fixture",
        )
        try:
            session = attach_subject(subject)
            assert get_source_session() is session
            assert isinstance(session.subject, GitRevisionSubject)
            try:
                resolve_path("README.md")
                raise AssertionError("resolve_path must refuse a git revision")
            except UnsupportedSourceCapabilityError as exc:
                assert exc.capability == "filesystem"
            try:
                served_root()
                raise AssertionError("served_root must refuse a git revision")
            except UnsupportedSourceCapabilityError as exc:
                assert exc.capability == "filesystem"
            for name in ("recency", "ignore", "watcher", "activity", "mutation"):
                try:
                    require_source_capability(name)
                    raise AssertionError(f"{name} must be unsupported")
                except UnsupportedSourceCapabilityError as exc:
                    assert exc.capability == name
            require_source_capability("navigation")
            require_source_capability("index")
        finally:
            await subject.aclose()
            reset_source_session()

    asyncio.run(_run())


def test_git_revision_subject_refuses_a_worktree_target(tmp_path: Path) -> None:
    async def _run() -> None:
        work = tmp_path / "work"
        work.mkdir()
        _git(work, "init", "-q", "-b", "main")
        (work / "f.txt").write_text("x\n", encoding="utf-8")
        _git(work, "add", "f.txt")
        _git(work, "commit", "-qm", "one")
        commit = _git(work, "rev-parse", "HEAD").decode().strip()
        from metabrowser.git.process import attached_worktree_target

        target = attached_worktree_target(worktree=work, git_dir=work / ".git")
        try:
            await git_revision_subject(target=target, commit_oid=commit, store_identity="fixture")
            raise AssertionError("worktree targets must be refused")
        except GitPathError:
            pass

    asyncio.run(_run())


def test_abbreviated_oid_never_enters_the_batch_protocol(tmp_path: Path) -> None:
    async def _run() -> None:
        store, commit = _build_store(tmp_path)
        subject = await git_revision_subject(
            target=repository_store_target(git_dir=store),
            commit_oid=commit,
            store_identity="fixture",
        )
        try:
            try:
                await subject.tree_source.read_blob_oid(commit[:12])
                raise AssertionError("abbreviations must not reach cat-file")
            except GitPathError:
                pass
        finally:
            await subject.aclose()

    asyncio.run(_run())


def test_repository_store_target_rejects_a_missing_dir(tmp_path: Path) -> None:
    with pytest.raises(GitUnavailableError):
        repository_store_target(git_dir=tmp_path / "missing.git")


def test_blob_index_tally_uses_sorted_prefix_spans() -> None:
    sizes = {f"{index:040x}": 1 for index in range(5)}
    oids = list(sizes)
    index = GitBlobIndex(
        blobs=(
            (b"documentation/x.txt", oids[0]),
            (b"docs!", oids[1]),
            (b"other.txt", oids[2]),
            (b"docs/nested/a.txt", oids[3]),
            (b"docs/note.txt", oids[4]),
        ),
        sizes=sizes,
    )
    assert [name for name, _oid in index.blobs] == [
        b"docs!",
        b"docs/nested/a.txt",
        b"docs/note.txt",
        b"documentation/x.txt",
        b"other.txt",
    ]
    assert index.tally(b"docs") == GitTreeTally(2, 2)
    assert index.tally(b"docs/nested") == GitTreeTally(1, 1)
    assert index.tally(b"documentation") == GitTreeTally(1, 1)
    assert index.tally(b"docs!") == GitTreeTally(1, 1)
    assert index.tally() == GitTreeTally(5, 5)
    assert [name for name, _oid in index.iter_blobs(b"docs")] == [
        b"docs/nested/a.txt",
        b"docs/note.txt",
    ]


def test_identical_subtrees_resolve_under_each_parent(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    for name in ("one", "two"):
        (work / name).mkdir()
        (work / name / "file.txt").write_bytes(b"same content\n")
    _git(work, "add", ".")
    _git(work, "commit", "-qm", "identical trees")
    commit = _git(work, "rev-parse", "HEAD").decode().strip()
    store = tmp_path / "store.git"
    _git(tmp_path, "clone", "--bare", "--template=", str(work), str(store))

    async def run() -> None:
        subject = await git_revision_subject(
            target=repository_store_target(git_dir=store),
            commit_oid=commit,
            store_identity="fixture",
        )
        try:
            roots = await subject.tree_source.list_tree()
            assert roots[0].oid == roots[1].oid
            for name in (b"one", b"two", b"one"):
                path = GitPath.from_segments(name, b"file.txt")
                assert await subject.tree_source.read_blob(path) == b"same content\n"
                entries = await subject.tree_source.list_tree(path.parent())
                assert [entry.path for entry in entries] == [path]
                resolved = subject.tree_source.resolve(path.to_wire())
                assert resolved is not None and resolved.is_file
        finally:
            await subject.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("many", [False, True])
def test_batch_timeout_discards_actor_and_next_read_recovers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, many: bool
) -> None:
    store, commit = _build_store(tmp_path)

    async def run() -> None:
        actor = tree_module._BatchObjectReader(repository_store_target(git_dir=store))
        await actor.info(commit)
        original_process = actor._proc

        async def stalled_header(_reader: asyncio.StreamReader) -> bytes:
            return await asyncio.Future[bytes]()

        try:
            with monkeypatch.context() as scoped:
                scoped.setattr(tree_module, "_read_header", stalled_header)
                scoped.setattr(
                    tree_module,
                    "BATCH_OBJECT_POLICY",
                    replace(tree_module.BATCH_OBJECT_POLICY, timeout_s=0.01),
                )
                with pytest.raises(GitTimeoutError):
                    # The outer deadline makes the regression fail rather than hang.
                    async with asyncio.timeout(2):
                        if many:
                            await actor.info_many((commit,))
                        else:
                            await actor.info(commit)
            assert original_process is not None and original_process.returncode is not None
            assert actor._proc is None
            assert (await actor.info(commit)).kind == "commit"
        finally:
            await actor.aclose()

    asyncio.run(run())


def test_two_tree_sources_share_one_store_reader_pool(tmp_path: Path) -> None:
    async def _run() -> None:
        store, commit = _build_store(tmp_path)
        target = repository_store_target(git_dir=store)
        first = await git_revision_subject(
            target=target, commit_oid=commit, store_identity="fixture"
        )
        second = await git_revision_subject(
            target=target, commit_oid=commit, store_identity="fixture"
        )
        try:
            assert store_batch_reader_count(target) == 1
            path = GitPath.from_segments(b"README.md")
            assert await first.tree_source.read_blob(path) == b"hello\n"
            assert store_batch_reader_count(target) == 1
            assert await second.tree_source.read_blob(path) == b"hello\n"
            assert store_batch_reader_count(target) == 1
        finally:
            await first.aclose()
        assert await second.tree_source.read_blob(GitPath.from_segments(b"README.md")) == b"hello\n"
        assert store_batch_reader_count(target) == 1
        await second.aclose()
        assert store_batch_reader_count(target) == 0
        assert (store / "index").exists() is False

    asyncio.run(_run())


def test_read_store_blob_gates_size_without_a_live_subject(tmp_path: Path) -> None:
    async def _run() -> None:
        store, commit = _build_store(tmp_path)
        target = repository_store_target(git_dir=store)
        subject = await git_revision_subject(
            target=target, commit_oid=commit, store_identity="fixture"
        )
        source = subject.tree_source
        try:
            readme = next(
                entry
                for entry in await source.list_tree()
                if entry.path.segments[-1] == b"README.md"
            )
            big = next(
                entry for entry in await source.list_tree() if entry.path.segments[-1] == b"big.bin"
            )
            readme_oid, big_oid = readme.oid, big.oid
        finally:
            await subject.aclose()
        assert store_batch_reader_count(target) == 0
        assert await read_store_blob(target, readme_oid) == b"hello\n"
        try:
            await read_store_blob(target, big_oid, max_blob_bytes=16)
            raise AssertionError("oversized blob must be refused")
        except GitBlobTooLargeError as exc:
            assert exc.size == 64
            assert exc.max_bytes == 16
        assert store_batch_reader_count(target) == 0

    asyncio.run(_run())


def test_lfs_pointer_blob_is_stored_bytes_without_smudge(tmp_path: Path) -> None:
    work = tmp_path / "work"
    store = tmp_path / "store.git"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    (work / ".gitattributes").write_text(
        "*.bin filter=lfs diff=lfs merge=lfs -text\n", encoding="utf-8"
    )
    (work / "media.bin").write_bytes(_LFS_POINTER)
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "lfs pointer")
    commit = _git(work, "rev-parse", "HEAD").decode().strip()
    _git(tmp_path, "clone", "--bare", "--template=", str(work), str(store), env_root=tmp_path)
    marker = tmp_path / "smudge-ran"
    smudge = tmp_path / "smudge.sh"
    smudge.write_text(
        f"#!/bin/sh\necho SMUDGED > '{marker}'\necho SMUDGED\n",
        encoding="utf-8",
    )
    smudge.chmod(0o755)
    _git(store, "config", "filter.lfs.smudge", str(smudge))
    _git(store, "config", "filter.lfs.required", "true")

    async def _run() -> None:
        subject = await git_revision_subject(
            target=repository_store_target(git_dir=store),
            commit_oid=commit,
            store_identity="fixture",
        )
        source = subject.tree_source
        try:
            path = GitPath.from_segments(b"media.bin")
            assert await source.read_blob(path) == _LFS_POINTER
        finally:
            await subject.aclose()

    asyncio.run(_run())
    assert marker.exists() is False


def test_a_blob_missing_from_the_store_is_object_unavailable(tmp_path: Path) -> None:
    work = tmp_path / "work"
    store = tmp_path / "store.git"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    (work / "README.md").write_text("hello\n", encoding="utf-8")
    (work / "keep.txt").write_text("kept\n", encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "two blobs")
    commit = _git(work, "rev-parse", "HEAD").decode().strip()
    missing_oid = _git(work, "rev-parse", "HEAD:README.md").decode().strip()
    _git(tmp_path, "clone", "--bare", "--template=", str(work), str(store), env_root=tmp_path)
    _delete_store_blob(store, missing_oid)

    async def _run() -> None:
        subject = await git_revision_subject(
            target=repository_store_target(git_dir=store),
            commit_oid=commit,
            store_identity="fixture",
        )
        source = subject.tree_source
        try:
            children = await source.list_tree()
            names = {entry.path.segments[-1] for entry in children}
            assert names == {b"README.md", b"keep.txt"}
            readme = next(entry for entry in children if entry.path.segments[-1] == b"README.md")
            assert readme.oid == missing_oid
            assert readme.size is None
            miss_tally = await source.tree_tally()
            assert miss_tally is not None
            assert miss_tally.total_files == 2
            assert miss_tally.total_size is None
            with pytest.raises(GitObjectUnavailableError) as caught:
                await source.read_blob(readme.path)
            assert caught.value.code == "object_unavailable"
            assert caught.value.oid == missing_oid
            assert await source.read_blob(GitPath.from_segments(b"keep.txt")) == b"kept\n"
        finally:
            await subject.aclose()

    asyncio.run(_run())


def test_revision_subject_identity_requires_the_real_store_id(tmp_path: Path) -> None:
    store, commit = _build_store(tmp_path)
    target = repository_store_target(git_dir=store)

    async def _run() -> None:
        with pytest.raises(TypeError):
            # No default: two stores pinning one commit must not share an identity.
            await git_revision_subject(  # pyright: ignore[reportCallIssue]
                target=target, commit_oid=commit
            )
        first = await git_revision_subject(
            target=target, commit_oid=commit, store_identity="store-a"
        )
        second = await git_revision_subject(
            target=target, commit_oid=commit, store_identity="store-b"
        )
        try:
            assert first.identity == f"store-a:{commit}"
            assert first.identity != second.identity
        finally:
            await first.aclose()
            await second.aclose()

    asyncio.run(_run())


def test_a_closed_reader_pool_never_respawns_an_actor(tmp_path: Path) -> None:
    """The pool closes between ``read_blob``'s info and contents transactions.

    The checked-out actor was terminated by the close. Its next transaction
    must not spawn a fresh ``cat-file`` process that nothing owns.
    """

    store, commit = _build_store(tmp_path)
    target = repository_store_target(git_dir=store)

    async def _run() -> None:
        subject = await git_revision_subject(
            target=target, commit_oid=commit, store_identity="fixture"
        )
        source = subject.tree_source
        captured: list[tree_module._BatchObjectReader] = []
        original_info = tree_module._BatchObjectReader.info

        async def info_then_close(
            self: tree_module._BatchObjectReader, oid: str
        ) -> tree_module._ObjectInfo:
            result = await original_info(self, oid)
            captured.append(self)
            await subject.aclose()
            return result

        readme = await source.resolve_path(GitPath.from_segments(b"README.md"))
        assert readme is not None
        tree_module._BatchObjectReader.info = info_then_close  # type: ignore[method-assign]
        try:
            with pytest.raises(GitBatchProtocolError):
                await source.read_blob_oid(readme.oid)
        finally:
            tree_module._BatchObjectReader.info = original_info  # type: ignore[method-assign]
        assert store_batch_reader_count(target) == 0
        assert captured and all(reader._proc is None for reader in captured)
        with pytest.raises(GitBatchProtocolError):
            await captured[0].info(commit)
        assert captured[0]._proc is None

    asyncio.run(_run())
