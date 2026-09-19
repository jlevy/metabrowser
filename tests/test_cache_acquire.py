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
from metabrowser.cache.atomic import read_record
from metabrowser.cache.identity import source_identity
from metabrowser.cache.layout import FutureLayoutFormatError
from metabrowser.cache.locks import LockBusyError, LockKind, held_locks
from metabrowser.cache.paths import source_record
from metabrowser.cache.reclaim import sweep_staging_and_trash
from metabrowser.cache.records import REPOSITORY_SOURCE_STATE_CONTRACT_ID, RepositorySourceState
from metabrowser.cache.urls import GitSource, classify_root_argument
from metabrowser.git.process import (
    _REPO_PINNING_GIT_VARS,
    GitCommandError,
    GitProcessPolicy,
    UnsupportedGitVersionError,
    detect_git_version,
)
from metabrowser.home import PrivateStorageError


def _last_opened_at(home: Path, slug: str) -> str | None:
    try:
        record = read_record(
            home,
            source_record(slug, "state.yml"),
            REPOSITORY_SOURCE_STATE_CONTRACT_ID,
            shared="keep",
        )
    except FileNotFoundError:
        return None
    assert isinstance(record, RepositorySourceState)
    return record.last_opened_at


posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")
skip_as_root = pytest.mark.skipif(
    os.geteuid() == 0, reason="root is never denied by modes, so a denial cannot be staged"
)

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


def _remove_owner_write(path: Path) -> None:
    for root, _directories, _files in os.walk(path, topdown=False):
        os.chmod(root, 0o500)
    os.chmod(path, 0o500)


def _restore_owner_write(path: Path) -> None:
    for root, _directories, _files in os.walk(path, topdown=True):
        os.chmod(root, 0o700)
    os.chmod(path, 0o700)


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


@posix_only
def test_sha256_source_acquires_and_reopens_without_changing_object_format(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_installed_git(monkeypatch)
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-q", "-b", "topic", "--object-format=sha256")
    (work / "README").write_text("SHA-256 source\n")
    _git(work, "add", ".")
    _git(work, "commit", "-qm", "first")
    source = _file_source(work)
    home = tmp_path / "home"
    published = asyncio.run(acquire_file_source(source, home=home))
    assert published.object_format == "sha256"
    assert len(published.default_revision) == 64
    _git(published.git_dir, "cat-file", "-e", published.default_revision)
    assert asyncio.run(acquire_file_source(source, home=home)) == published


@posix_only
def test_racing_acquisitions_return_the_selected_stores_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_installed_git(monkeypatch)
    origin = _origin(tmp_path, allow_filter=False)
    source = _file_source(origin)
    home = tmp_path / "home"
    with asyncio.run(acquire_into_staging(source, home=home)) as first:
        work = tmp_path / "work"
        (work / "second").write_text("second revision\n")
        _git(work, "add", ".")
        _git(work, "commit", "-qm", "second")
        _git(work, "push", str(origin), "topic")
        with asyncio.run(acquire_into_staging(source, home=home)) as second:
            assert second.default_revision != first.default_revision
            winner = acquire_module.publish_from_staging(first)
            reused = acquire_module.publish_from_staging(second)
    assert reused == winner
    _git(reused.git_dir, "cat-file", "-e", reused.default_revision)
    assert asyncio.run(acquire_file_source(source, home=home)) == winner


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
def test_acquire_file_source_refuses_below_floor_git_without_writing_an_empty_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin = _origin(tmp_path, allow_filter=False)
    home = tmp_path / "home"
    home.mkdir()

    def refuse() -> tuple[int, int, int]:
        raise UnsupportedGitVersionError("git version 2.39.5", "2.43.7")

    monkeypatch.setattr("metabrowser.cache.acquire.require_acquisition_git", refuse)
    with pytest.raises(UnsupportedGitVersionError):
        asyncio.run(acquire_file_source(_file_source(origin), home=home))
    assert list(home.iterdir()) == []


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


@posix_only
def test_a_cache_hit_does_not_open_the_home_for_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_installed_git(monkeypatch)
    origin = _origin(tmp_path, allow_filter=False)
    home = tmp_path / "home"
    source = _file_source(origin)
    first = asyncio.run(acquire_file_source(source, home=home))

    def refuse_write(home_path: Path | None = None, *, version: str | None = None) -> object:
        raise AssertionError("a cache hit must not open the home for write")

    monkeypatch.setattr(acquire_module, "open_cache", refuse_write)
    second = asyncio.run(acquire_file_source(source, home=home))
    assert second.store_id == first.store_id
    assert second.slug == first.slug
    assert second.git_dir == first.git_dir


@posix_only
@skip_as_root
def test_a_cache_hit_against_a_home_without_owner_write_reuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_installed_git(monkeypatch)
    origin = _origin(tmp_path, allow_filter=False)
    home = tmp_path / "home"
    source = _file_source(origin)
    first = asyncio.run(acquire_file_source(source, home=home))
    _remove_owner_write(home)
    try:
        second = asyncio.run(acquire_file_source(source, home=home))
        assert second.store_id == first.store_id
        assert second.slug == first.slug
        assert list((home / "cache" / "staging").iterdir()) == []
    finally:
        _restore_owner_write(home)


@posix_only
@skip_as_root
def test_a_cache_miss_against_a_home_without_owner_write_does_not_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_installed_git(monkeypatch)
    origin = _origin(tmp_path, allow_filter=False)
    home = tmp_path / "home"
    asyncio.run(acquire_file_source(_file_source(origin), home=home))
    other = tmp_path / "other"
    other.mkdir()
    other_source = _file_source(_origin(other, allow_filter=False))
    _remove_owner_write(home)
    try:
        with pytest.raises(PrivateStorageError):
            asyncio.run(acquire_file_source(other_source, home=home))
        assert list((home / "cache" / "staging").iterdir()) == []
    finally:
        _restore_owner_write(home)


@posix_only
def test_a_future_home_is_refused_before_opening_the_cache_for_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_installed_git(monkeypatch)
    origin = _origin(tmp_path, allow_filter=False)
    home = tmp_path / "home"
    source = _file_source(origin)
    asyncio.run(acquire_file_source(source, home=home))
    layout = home / "cache" / "layout.yml"
    layout.write_text(layout.read_text(encoding="utf-8").replace("format: f01", "format: f02", 1))

    def refuse_write(home_path: Path | None = None, *, version: str | None = None) -> object:
        raise AssertionError("a future layout must not open the home for write")

    monkeypatch.setattr(acquire_module, "open_cache", refuse_write)
    with pytest.raises(FutureLayoutFormatError, match="Upgrade Metabrowser"):
        asyncio.run(acquire_file_source(source, home=home))


@posix_only
def test_a_writable_cache_hit_records_last_opened_at(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_installed_git(monkeypatch)
    origin = _origin(tmp_path, allow_filter=False)
    home = tmp_path / "home"
    source = _file_source(origin)
    first = asyncio.run(acquire_file_source(source, home=home))
    opened = _last_opened_at(home, first.slug)
    assert opened is not None
    second = asyncio.run(acquire_file_source(source, home=home))
    later = _last_opened_at(home, second.slug)
    assert later is not None
    assert later >= opened


@posix_only
@skip_as_root
def test_a_read_only_hit_keeps_the_published_last_opened_at(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_installed_git(monkeypatch)
    origin = _origin(tmp_path, allow_filter=False)
    home = tmp_path / "home"
    source = _file_source(origin)
    first = asyncio.run(acquire_file_source(source, home=home))
    opened = _last_opened_at(home, first.slug)
    _remove_owner_write(home)
    try:
        second = asyncio.run(acquire_file_source(source, home=home))
        assert second.store_id == first.store_id
        assert _last_opened_at(home, second.slug) == opened
    finally:
        _restore_owner_write(home)


@posix_only
def test_a_dropped_last_opened_at_write_does_not_fail_the_hit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_installed_git(monkeypatch)
    origin = _origin(tmp_path, allow_filter=False)
    home = tmp_path / "home"
    source = _file_source(origin)
    first = asyncio.run(acquire_file_source(source, home=home))

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(acquire_module, "write_record_atomic", refuse)

    def refuse_write(home_path: Path | None = None, *, version: str | None = None) -> object:
        raise AssertionError("a cache hit must not open the home for write")

    monkeypatch.setattr(acquire_module, "open_cache", refuse_write)
    second = asyncio.run(acquire_file_source(source, home=home))
    assert second.store_id == first.store_id
    assert second.slug == first.slug


@posix_only
def test_a_contended_alias_lock_does_not_fail_the_hit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_installed_git(monkeypatch)
    origin = _origin(tmp_path, allow_filter=False)
    home = tmp_path / "home"
    source = _file_source(origin)
    first = asyncio.run(acquire_file_source(source, home=home))

    def busy(*_args: object, **_kwargs: object) -> object:
        raise LockBusyError(LockKind.SOURCE_ALIAS, first.slug)

    monkeypatch.setattr(acquire_module, "source_alias_lock", busy)
    second = asyncio.run(acquire_file_source(source, home=home))
    assert second.store_id == first.store_id
