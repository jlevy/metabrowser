"""Opening a pinned revision: no ref, no lock, no write, and two readers of one store."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from metabrowser.cache.acquire import acquire_file_source
from metabrowser.cache.locks import held_locks
from metabrowser.cache.repository_store import open_revision
from metabrowser.git.process import GitUnavailableError
from metabrowser.git.tree_source import GitObjectUnavailableError, GitPath, GitPathError
from tests.test_cache_acquire import (
    _allow_installed_git,
    _file_source,
    _git,
    _git_env,
    _remove_owner_write,
    _restore_owner_write,
)

pytestmark = [
    pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required"),
    pytest.mark.skipif(os.name != "posix", reason="the cache is POSIX-only"),
]

CHILD_TIMEOUT = 30.0
_README = GitPath.from_segments(b"README")


def _git_out(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        env=_git_env(root),
    )
    return result.stdout.decode().strip()


def _two_commit_origin(tmp_path: Path) -> tuple[Path, str, str]:
    work = tmp_path / "work"
    origin = tmp_path / "origin.git"
    work.mkdir()
    _git(work, "init", "-q", "-b", "topic")
    (work / "README").write_text("first\n", encoding="utf-8")
    _git(work, "add", "README")
    _git(work, "commit", "-qm", "first")
    first = _git_out(work, "rev-parse", "HEAD")
    (work / "README").write_text("second\n", encoding="utf-8")
    _git(work, "add", "README")
    _git(work, "commit", "-qm", "second")
    second = _git_out(work, "rev-parse", "HEAD")
    _git(work, "clone", "--bare", "--template=", "--", str(work), str(origin))
    return origin, first, second


def _publish(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str, Path, str, str]:
    _allow_installed_git(monkeypatch)
    origin, first, second = _two_commit_origin(tmp_path)
    published = asyncio.run(acquire_file_source(_file_source(origin), home=tmp_path / "home"))
    assert published.default_revision == second
    return published.home, published.store_key, published.git_dir, first, second


def _snapshot(root: Path) -> dict[str, tuple[int, int]]:
    """Every file below *root* with its size and mtime: any write changes this."""

    return {
        str(path.relative_to(root)): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


async def _read_readme(home: Path, store_key: str, oid: str) -> bytes:
    subject = await open_revision(
        home=home, store_key=store_key, commit_oid=oid, store_identity=store_key
    )
    try:
        return await subject.tree_source.read_blob(_README)
    finally:
        await subject.aclose()


def test_opening_a_revision_writes_nothing_and_holds_no_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home, store_key, git_dir, first, second = _publish(tmp_path, monkeypatch)
    refs_before = _git_out(git_dir, "for-each-ref", "--format=%(refname)")
    before = _snapshot(home)

    async def run() -> tuple[bytes, bytes]:
        subject = await open_revision(
            home=home, store_key=store_key, commit_oid=second, store_identity=store_key
        )
        try:
            assert subject.commit_oid == second
            assert held_locks() == ()
            return await subject.tree_source.read_blob(_README), await _read_readme(
                home, store_key, first
            )
        finally:
            await subject.aclose()

    assert asyncio.run(run()) == (b"second\n", b"first\n")
    assert _git_out(git_dir, "for-each-ref", "--format=%(refname)") == refs_before
    assert "refs/metabrowser" not in refs_before
    assert _snapshot(home) == before
    assert not (git_dir / "index").exists()
    assert not (git_dir / "worktrees").exists()


def test_a_revision_opens_from_a_home_the_process_cannot_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if os.geteuid() == 0:
        pytest.skip("root is never denied by modes, so a denial cannot be staged")
    home, store_key, _git_dir, _first, second = _publish(tmp_path, monkeypatch)
    _remove_owner_write(home)
    try:
        assert asyncio.run(_read_readme(home, store_key, second)) == b"second\n"
    finally:
        _restore_owner_write(home)


def test_two_processes_read_two_oids_in_one_store_without_a_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home, store_key, git_dir, first, second = _publish(tmp_path, monkeypatch)
    script = textwrap.dedent(
        """
        import asyncio
        import sys
        from pathlib import Path
        from metabrowser.cache.repository_store import open_revision
        from metabrowser.git.tree_source import GitPath

        async def main() -> None:
            subject = await open_revision(
                home=Path(sys.argv[1]),
                store_key=sys.argv[2],
                commit_oid=sys.argv[3],
                store_identity=sys.argv[2],
            )
            try:
                print(await subject.tree_source.read_blob(GitPath.from_segments(b"README")))
                sys.stdout.flush()
                await asyncio.to_thread(sys.stdin.readline)
                print(await subject.tree_source.read_blob(GitPath.from_segments(b"README")))
            finally:
                await subject.aclose()

        asyncio.run(main())
        """
    )
    child = subprocess.Popen(
        [sys.executable, "-c", script, str(home), store_key, first],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout is not None
        assert child.stdout.readline().strip() == repr(b"first\n")
        # The child keeps its subject open while this process reads the other OID.
        assert asyncio.run(_read_readme(home, store_key, second)) == b"second\n"
        out, err = child.communicate("\n", timeout=CHILD_TIMEOUT)
        assert child.returncode == 0, err
        assert out.strip() == repr(b"first\n")
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate(timeout=CHILD_TIMEOUT)
    assert not (git_dir / "index").exists()


def test_open_refuses_abbreviated_missing_and_absent_stores(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home, store_key, git_dir, _first, second = _publish(tmp_path, monkeypatch)
    tree = _git_out(git_dir, "rev-parse", f"{second}^{{tree}}")

    def open_oid(key: str, oid: str) -> None:
        asyncio.run(open_revision(home=home, store_key=key, commit_oid=oid, store_identity=key))

    with pytest.raises(GitPathError):
        open_oid(store_key, second[:12])
    with pytest.raises(GitObjectUnavailableError):
        open_oid(store_key, "a" * 40)
    with pytest.raises(GitObjectUnavailableError):
        open_oid(store_key, tree)
    with pytest.raises(GitUnavailableError):
        open_oid("b" * 64, second)
    assert held_locks() == ()
