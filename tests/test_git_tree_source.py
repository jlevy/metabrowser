"""GitPath codec, revision subject, and worktree-free tree/blob reads."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from contextlib import suppress
from pathlib import Path

import pytest

from metabrowser.git.process import (
    GitUnavailableError,
    repository_store_target,
)
from metabrowser.git.tree_source import (
    GIT_REVISION_CAPABILITIES,
    GitBlobTooLargeError,
    GitObjectUnavailableError,
    GitPath,
    GitPathError,
    GitRevisionSubject,
    git_revision_subject,
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


def test_git_path_round_trips_invalid_utf8_and_newlines() -> None:
    path = GitPath.from_segments(b"docs", b"x\xff.txt", b"new\nline.txt", b"100%.html")
    wire = path.to_wire()
    assert GitPath.from_wire(wire) == path
    assert path.display().startswith("docs/")
    assert "\ufffd" in path.display()
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
            assert await source.read_blob(readme.path) == b"hello\n"
            handle = source.resolve(readme.path.to_wire())
            assert handle is not None
            assert handle.is_file

            docs = next(entry for entry in children if entry.path.segments[-1] == b"docs")
            nested = await source.list_tree(docs.path)
            note = next(entry for entry in nested if entry.path.segments[-1] == b"note.txt")
            assert await source.read_blob(note.path) == b"nested\n"

            percent = next(entry for entry in children if entry.path.segments[-1] == b"100%.html")
            assert await source.read_blob(percent.path) == b"<p>ok</p>\n"

            link = next(entry for entry in children if entry.path.segments[-1] == b"link")
            assert link.is_symlink
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
            await git_revision_subject(target=target, commit_oid=commit)
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


def test_two_tree_sources_share_one_store_reader_pool(tmp_path: Path) -> None:
    async def _run() -> None:
        store, commit = _build_store(tmp_path)
        target = repository_store_target(git_dir=store)
        first = await git_revision_subject(target=target, commit_oid=commit)
        second = await git_revision_subject(target=target, commit_oid=commit)
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
