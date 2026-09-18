"""file:// acquisition into staging: pack transport, no publication, no serving."""

from __future__ import annotations

import asyncio
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from metabrowser.cache import acquire as acquire_module
from metabrowser.cache.acquire import (
    AcquisitionError,
    RemoteUnavailableError,
    acquire_file_source,
    acquire_into_staging,
)
from metabrowser.cache.identity import source_identity
from metabrowser.cache.locks import LockKind, held_locks
from metabrowser.cache.reclaim import sweep_staging_and_trash
from metabrowser.cache.urls import GitSource, classify_root_argument
from metabrowser.git.process import (
    _REPO_PINNING_GIT_VARS,
    GitCommandError,
    GitProcessPolicy,
    UnsupportedGitVersionError,
    detect_git_version,
)

posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required")


def _git_env(root: Path) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key not in _REPO_PINNING_GIT_VARS}
    env.update(
        {
            "GIT_AUTHOR_NAME": "Fixture Author",
            "GIT_AUTHOR_EMAIL": "author@example.invalid",
            "GIT_COMMITTER_NAME": "Fixture Author",
            "GIT_COMMITTER_EMAIL": "author@example.invalid",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
        }
    )
    return env


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        env=_git_env(root),
    )


def _allow_installed_git(monkeypatch: pytest.MonkeyPatch) -> tuple[int, int, int]:
    """Exercise fetch on the runner's Git without admitting it for URL opening."""
    version, _raw = detect_git_version()
    if version is None:
        pytest.skip("git version is unparseable")
    monkeypatch.setattr("metabrowser.cache.acquire.require_acquisition_git", lambda: version)
    return version


def _file_source(path: Path) -> GitSource:
    classified = classify_root_argument(f"file://{path.resolve()}")
    assert isinstance(classified, GitSource)
    assert classified.transport == "file"
    return classified


def _origin(tmp_path: Path, *, allow_filter: bool) -> Path:
    work = tmp_path / "work"
    origin = tmp_path / "origin.git"
    work.mkdir()
    _git(work, "init", "-q", "-b", "topic")
    (work / "README").write_text("hello\n", encoding="utf-8")
    _git(work, "add", "README")
    _git(work, "commit", "-qm", "first")
    _git(work, "clone", "--bare", "--template=", "--", str(work), str(origin))
    if allow_filter:
        _git(origin, "config", "uploadpack.allowFilter", "true")
        _git(origin, "config", "uploadpack.allowAnySHA1InWant", "true")
    return origin


def _inodes(path: Path) -> set[int]:
    return {entry.stat().st_ino for entry in path.rglob("*") if entry.is_file()}


@posix_only
def test_file_origin_without_filter_support_fetches_a_complete_staging_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_installed_git(monkeypatch)
    origin = _origin(tmp_path, allow_filter=False)
    home = tmp_path / "home"
    staged = asyncio.run(acquire_into_staging(_file_source(origin), home=home))
    with staged:
        assert staged.strategy == "full"
        assert staged.object_format == "sha1"
        assert len(staged.default_revision) == 40
        assert staged.default_remote_ref == "refs/remotes/origin/topic"
        assert staged.git_dir.is_dir()
        assert (staged.git_dir / "config").is_file()
        assert staged.configuration_digest.startswith("sha256:")
        assert staged.source_id == source_identity("file", staged.source.normalized)
        assert any(
            lock.kind is LockKind.STAGING_ENTRY and lock.key == staged.entry
            for lock in held_locks()
        )
        assert list((home / "cache" / "sources").iterdir()) == []
        assert list((home / "cache" / "repository-stores").iterdir()) == []
        assert _inodes(staged.git_dir).isdisjoint(_inodes(origin))
        leaked = [
            path
            for path in [staged.git_dir, *staged.git_dir.rglob("*")]
            if path.exists() and path.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO)
        ]
        assert leaked == []


@posix_only
def test_file_origin_that_allows_filter_still_validates_the_observed_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_installed_git(monkeypatch)
    origin = _origin(tmp_path, allow_filter=True)
    home = tmp_path / "home"
    staged = asyncio.run(acquire_into_staging(_file_source(origin), home=home))
    with staged:
        assert staged.strategy in {"blobless", "full"}
        assert staged.default_revision
        assert staged.git_dir.is_dir()


@posix_only
def test_a_live_staging_entry_survives_the_startup_sweep_then_abandon_deletes_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_installed_git(monkeypatch)
    origin = _origin(tmp_path, allow_filter=False)
    home = tmp_path / "home"
    staged = asyncio.run(acquire_into_staging(_file_source(origin), home=home))
    entry = staged.entry
    with staged:
        report = sweep_staging_and_trash(home)
        assert f"cache/staging/{entry}" in report.live
        assert staged.git_dir.is_dir()
    staging = home / "cache" / "staging"
    assert list(staging.iterdir()) == []


@posix_only
def test_a_missing_file_origin_abandons_without_leaving_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_installed_git(monkeypatch)
    missing = tmp_path / "missing.git"
    home = tmp_path / "home"
    with pytest.raises(RemoteUnavailableError):
        asyncio.run(acquire_into_staging(_file_source(missing), home=home))
    staging = home / "cache" / "staging"
    if staging.is_dir():
        assert list(staging.iterdir()) == []


@posix_only
def test_a_crashed_staging_holder_is_swept(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_installed_git(monkeypatch)
    origin = _origin(tmp_path, allow_filter=False)
    home = tmp_path / "home"
    staged = asyncio.run(acquire_into_staging(_file_source(origin), home=home))
    lock = staged._lock
    assert lock is not None
    lock.release()
    staged._lock = None
    report = sweep_staging_and_trash(home)
    assert f"cache/staging/{staged.entry}" in report.removed
    assert not staged.git_dir.exists()


@posix_only
def test_prefetch_failure_still_leaves_a_validated_staging_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_installed_git(monkeypatch)
    origin = _origin(tmp_path, allow_filter=True)
    home = tmp_path / "home"
    real_run = acquire_module._run

    async def fail_object_fetch(
        args: list[str],
        *,
        cwd: Path | None = None,
        git_dir: Path | None = None,
        policy: GitProcessPolicy = acquire_module.ACQUISITION_POLICY,
        stdin: bytes | None = None,
    ) -> bytes:
        if "--stdin" in args:
            raise GitCommandError(args, 1, "prefetch failed")
        return await real_run(args, cwd=cwd, git_dir=git_dir, policy=policy, stdin=stdin)

    monkeypatch.setattr(acquire_module, "_run", fail_object_fetch)
    staged = asyncio.run(acquire_into_staging(_file_source(origin), home=home))
    with staged:
        assert staged.git_dir.is_dir()
        assert staged.default_revision


@posix_only
def test_blobless_prefetch_makes_head_tree_blobs_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_installed_git(monkeypatch)
    origin = _origin(tmp_path, allow_filter=True)
    home = tmp_path / "home"
    staged = asyncio.run(acquire_into_staging(_file_source(origin), home=home))
    with staged:
        if staged.strategy != "blobless":
            pytest.skip("this Git ignored blob:none over file://")
        oids = asyncio.run(acquire_module._tree_blob_oids(staged.git_dir, staged.default_revision))
        assert oids
        kind = asyncio.run(acquire_module._run(["cat-file", "-t", oids[0]], git_dir=staged.git_dir))
        assert kind.strip() == b"blob"


def test_https_sources_are_out_of_scope_for_staging_fetch() -> None:
    source = classify_root_argument("https://example.com/owner/repo.git")
    assert isinstance(source, GitSource)
    with pytest.raises(AcquisitionError, match="not acquired yet"):
        asyncio.run(acquire_into_staging(source, home=Path("/tmp/unused")))


def test_git_below_the_acquisition_floor_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin = _origin(tmp_path, allow_filter=False)
    home = tmp_path / "home"

    def refuse() -> tuple[int, int, int]:
        raise UnsupportedGitVersionError("git version 2.39.5", "2.43.7")

    monkeypatch.setattr("metabrowser.cache.acquire.require_acquisition_git", refuse)
    with pytest.raises(UnsupportedGitVersionError):
        asyncio.run(acquire_into_staging(_file_source(origin), home=home))
    assert (
        not (home / "cache" / "staging").exists()
        or list((home / "cache" / "staging").iterdir()) == []
    )


@posix_only
def test_acquire_file_source_refuses_below_floor_git_before_creating_the_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin = _origin(tmp_path, allow_filter=False)
    home = tmp_path / "home"

    def refuse() -> tuple[int, int, int]:
        raise UnsupportedGitVersionError("git version 2.39.5", "2.43.7")

    monkeypatch.setattr("metabrowser.cache.acquire.require_acquisition_git", refuse)
    with pytest.raises(UnsupportedGitVersionError):
        asyncio.run(acquire_file_source(_file_source(origin), home=home))
    assert not home.exists()


@posix_only
def test_a_cache_hit_does_not_require_the_acquisition_floor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_installed_git(monkeypatch)
    origin = _origin(tmp_path, allow_filter=False)
    home = tmp_path / "home"
    source = _file_source(origin)
    first = asyncio.run(acquire_file_source(source, home=home))

    def refuse() -> tuple[int, int, int]:
        raise UnsupportedGitVersionError("git version 2.39.5", "2.43.7")

    monkeypatch.setattr("metabrowser.cache.acquire.require_acquisition_git", refuse)
    second = asyncio.run(acquire_file_source(source, home=home))
    assert second.store_id == first.store_id
    assert second.slug == first.slug
