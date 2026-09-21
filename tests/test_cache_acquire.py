"""file:// acquisition into staging: pack transport, no publication, no serving."""

from __future__ import annotations

import asyncio
import dataclasses
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
    ValidationFailedError,
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


@posix_only
def test_an_ordinary_non_bare_clone_acquires_through_its_own_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A clone also advertises ``refs/remotes/origin/HEAD``; only ``HEAD`` names the branch."""
    _allow_installed_git(monkeypatch)
    upstream = _origin(tmp_path, allow_filter=False)
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", "--template=", "--", str(upstream), str(clone))
    _git(clone, "checkout", "-q", "-b", "local-work")
    advertised = subprocess.run(
        ["git", "ls-remote", "--symref", "--", str(clone), "HEAD"],
        check=True,
        capture_output=True,
        env=_git_env(clone),
        text=True,
    ).stdout
    assert "ref: refs/remotes/origin/topic\trefs/remotes/origin/HEAD" in advertised
    published = asyncio.run(acquire_file_source(_file_source(clone), home=tmp_path / "home"))
    assert published.default_remote_ref == "refs/remotes/origin/local-work"
    _git(published.git_dir, "cat-file", "-e", published.default_revision)


def _rev_parse(root: Path, revision: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--verify", revision],
        check=True,
        capture_output=True,
        env=_git_env(root),
        text=True,
    ).stdout.strip()


@posix_only
def test_a_hostile_symref_named_head_does_not_choose_the_published_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_installed_git(monkeypatch)
    hostile = tmp_path / "hostile"
    hostile.mkdir()
    _git(hostile, "init", "-q", "-b", "trunk")
    (hostile / "README").write_text("trunk\n", encoding="utf-8")
    _git(hostile, "add", "README")
    _git(hostile, "commit", "-qm", "trunk commit")
    _git(hostile, "checkout", "-q", "-b", "decoy")
    (hostile / "other").write_text("decoy\n", encoding="utf-8")
    _git(hostile, "add", "other")
    _git(hostile, "commit", "-qm", "decoy commit")
    _git(hostile, "checkout", "-q", "trunk")
    _git(hostile, "symbolic-ref", "refs/heads/zz/HEAD", "refs/heads/decoy")
    published = asyncio.run(acquire_file_source(_file_source(hostile), home=tmp_path / "home"))
    assert published.default_remote_ref == "refs/remotes/origin/trunk"
    assert published.default_revision == _rev_parse(hostile, "refs/heads/trunk")
    assert _rev_parse(published.git_dir, published.default_remote_ref) == (
        published.default_revision
    )


@posix_only
def test_a_default_branch_that_does_not_resolve_to_the_observed_head_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The origin moves its branch after HEAD was observed and before the fetch."""
    _allow_installed_git(monkeypatch)
    origin = _origin(tmp_path, allow_filter=False)
    work = tmp_path / "work"
    home = tmp_path / "home"
    real_run = acquire_module._run

    async def move_branch_after_observation(
        args: list[str],
        *,
        cwd: Path | None = None,
        git_dir: Path | None = None,
        policy: GitProcessPolicy = acquire_module.ACQUISITION_POLICY,
        stdin: bytes | None = None,
    ) -> bytes:
        result = await real_run(args, cwd=cwd, git_dir=git_dir, policy=policy, stdin=stdin)
        if "ls-remote" in args:
            _git(work, "commit", "-q", "--allow-empty", "-m", "moved")
            _git(work, "push", "-q", str(origin), "topic")
        return result

    monkeypatch.setattr(acquire_module, "_run", move_branch_after_observation)
    with pytest.raises(ValidationFailedError, match="default branch"):
        asyncio.run(acquire_file_source(_file_source(origin), home=home))
    assert list((home / "cache" / "staging").iterdir()) == []
    assert list((home / "cache" / "sources").iterdir()) == []
    assert list((home / "cache" / "repository-stores").iterdir()) == []


@posix_only
def test_ambient_git_variables_do_not_steer_an_acquisition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An allowlist naming only https would refuse file://; reftable would change the store."""
    _allow_installed_git(monkeypatch)
    origin = _origin(tmp_path, allow_filter=False)
    monkeypatch.setenv("GIT_ALLOW_PROTOCOL", "https")
    monkeypatch.setenv("GIT_DEFAULT_REF_FORMAT", "reftable")
    published = asyncio.run(acquire_file_source(_file_source(origin), home=tmp_path / "home"))
    config = (published.git_dir / "config").read_text(encoding="utf-8").lower()
    assert "refstorage" not in config
    assert not (published.git_dir / "reftable").exists()


@posix_only
@pytest.mark.parametrize("nested", ["nested-home", "."])
def test_a_repository_enclosing_the_cache_home_does_not_rewrite_the_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, nested: str
) -> None:
    """A repository around the home, or the home itself, must not lend its config."""
    _allow_installed_git(monkeypatch)
    real = _origin(tmp_path, allow_filter=False)
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    _git(decoy, "init", "-q", "-b", "decoy-branch")
    _git(decoy, "commit", "-q", "--allow-empty", "-m", "decoy")
    outer = tmp_path / "outer"
    outer.mkdir(mode=0o700)
    _git(outer, "init", "-q", "-b", "main")
    source = _file_source(real)
    _git(outer, "config", f"url.file://{decoy.resolve()}.insteadOf", source.normalized)
    published = asyncio.run(acquire_file_source(source, home=outer / nested))
    assert published.default_remote_ref == "refs/remotes/origin/topic"
    assert published.default_revision == _rev_parse(real, "refs/heads/topic")


@posix_only
def test_a_detached_head_origin_is_refused_before_anything_is_fetched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_installed_git(monkeypatch)
    _origin(tmp_path, allow_filter=False)
    work = tmp_path / "work"
    _git(work, "checkout", "-q", "--detach")
    home = tmp_path / "home"
    commands: list[list[str]] = []
    real_run = acquire_module._run

    async def record(
        args: list[str],
        *,
        cwd: Path | None = None,
        git_dir: Path | None = None,
        policy: GitProcessPolicy = acquire_module.ACQUISITION_POLICY,
        stdin: bytes | None = None,
    ) -> bytes:
        commands.append(args)
        return await real_run(args, cwd=cwd, git_dir=git_dir, policy=policy, stdin=stdin)

    monkeypatch.setattr(acquire_module, "_run", record)
    with pytest.raises(ValidationFailedError, match="not a branch"):
        asyncio.run(acquire_file_source(_file_source(work), home=home))
    assert len(commands) == 1 and "ls-remote" in commands[0]
    assert list((home / "cache" / "staging").iterdir()) == []


def _has_object(git_dir: Path, oid: str) -> bool:
    probe = subprocess.run(
        ["git", "--git-dir", str(git_dir), "cat-file", "-e", oid],
        check=False,
        capture_output=True,
        env=_git_env(git_dir) | {"GIT_NO_LAZY_FETCH": "1"},
    )
    return probe.returncode == 0


@posix_only
@pytest.mark.parametrize("shape", ["unfiltered", "filtered", "filtered-with-tagged-tip"])
def test_the_filter_check_is_sound_and_does_not_buffer_the_origins_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shape: str
) -> None:
    """``old.txt`` lives only in history, so the tip prefetch never fetches it.

    A tag on the tip's blob makes the origin send it despite the filter, which leaves the
    tip complete while history is not.
    """
    _allow_installed_git(monkeypatch)
    origin = tmp_path / "long"
    origin.mkdir()
    _git(origin, "init", "-q", "-b", "topic")
    (origin / "README").write_text("hello\n", encoding="utf-8")
    (origin / "old.txt").write_text("only in history\n", encoding="utf-8")
    _git(origin, "add", ".")
    _git(origin, "commit", "-qm", "first")
    old_blob = _rev_parse(origin, "HEAD:old.txt")
    _git(origin, "rm", "-q", "old.txt")
    for index in range(40):
        _git(origin, "commit", "-q", "--allow-empty", "-m", f"commit {index}")
    if shape != "unfiltered":
        _git(origin, "config", "uploadpack.allowFilter", "true")
        _git(origin, "config", "uploadpack.allowAnySHA1InWant", "true")
    if shape == "filtered-with-tagged-tip":
        _git(origin, "tag", "tip-blob", _rev_parse(origin, "HEAD:README"))
    # Forty commit IDs alone are 1,640 bytes: a listing of every reachable object
    # overflows this cap, and a listing of the missing ones does not.
    capped = dataclasses.replace(acquire_module.ACQUISITION_POLICY, max_bytes=1024)
    real_run = acquire_module._run

    async def cap_rev_list(
        args: list[str],
        *,
        cwd: Path | None = None,
        git_dir: Path | None = None,
        policy: GitProcessPolicy = acquire_module.ACQUISITION_POLICY,
        stdin: bytes | None = None,
    ) -> bytes:
        if args[0] == "rev-list":
            policy = capped
        return await real_run(args, cwd=cwd, git_dir=git_dir, policy=policy, stdin=stdin)

    monkeypatch.setattr(acquire_module, "_run", cap_rev_list)
    with asyncio.run(acquire_into_staging(_file_source(origin), home=tmp_path / "home")) as staged:
        honored = not _has_object(staged.git_dir, old_blob)
        assert staged.strategy == ("blobless" if honored else "full")
        if shape == "unfiltered":
            assert not honored


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
