"""Git runner policies, command targets, and the acquisition version floor."""

from __future__ import annotations

import asyncio
import os
import shutil
import stat
from pathlib import Path

import pytest

from metabrowser.git.process import (
    ACQUISITION_POLICY,
    BATCH_OBJECT_POLICY,
    READ_POLICY,
    STORE_READ_POLICY,
    GitCommandError,
    GitLocation,
    GitProcessPolicy,
    UnsupportedGitVersionError,
    acquisition_allowed,
    as_location,
    attached_worktree_target,
    detect_git_version,
    git_environment,
    parse_git_version,
    repository_store_target,
    require_acquisition_git,
    run_git,
    run_git_at,
)

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git executable is required",
)


def test_acquisition_policy_isolates_config_and_disables_lazy_fetch() -> None:
    env = git_environment(ACQUISITION_POLICY)
    assert env["GIT_CONFIG_NOSYSTEM"] == "1"
    assert env["GIT_CONFIG_GLOBAL"] == os.devnull
    assert env["GIT_NO_LAZY_FETCH"] == "1"
    assert env["GIT_SSH_COMMAND"] == "ssh -oBatchMode=yes"
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    read_env = git_environment(READ_POLICY)
    assert "GIT_NO_LAZY_FETCH" not in read_env
    assert "GIT_CONFIG_NOSYSTEM" not in read_env
    assert "GIT_SSH_COMMAND" not in read_env
    batch_env = git_environment(BATCH_OBJECT_POLICY)
    assert BATCH_OBJECT_POLICY.no_lazy_fetch is True
    assert batch_env["GIT_NO_LAZY_FETCH"] == "1"


def test_run_git_rejects_cwd_and_target_together(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    asyncio.run(run_git(["init", "-q", "-b", "main"], cwd=repo))
    target = attached_worktree_target(worktree=repo, git_dir=repo / ".git")
    with pytest.raises(TypeError, match="target or cwd"):
        asyncio.run(run_git(["rev-parse", "HEAD"], cwd=repo, target=target))


@pytest.mark.parametrize("injection", ["count", "parameters", "file"])
def test_isolated_policies_ignore_environment_injected_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, injection: str
) -> None:
    if injection == "count":
        monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
        monkeypatch.setenv("GIT_CONFIG_KEY_0", "review.injected")
        monkeypatch.setenv("GIT_CONFIG_VALUE_0", "ambient")
    elif injection == "parameters":
        monkeypatch.setenv("GIT_CONFIG_PARAMETERS", "'review.injected=ambient'")
    else:
        config = tmp_path / "injected.config"
        config.write_text("[review]\n  injected = ambient\n")
        monkeypatch.setenv("GIT_CONFIG", str(config))
    for policy in (ACQUISITION_POLICY, STORE_READ_POLICY, BATCH_OBJECT_POLICY):
        result = asyncio.run(run_git(["config", "--list"], cwd=tmp_path, policy=policy))
        assert b"review.injected=ambient" not in result
    ordinary = asyncio.run(run_git(["config", "--list"], cwd=tmp_path, policy=READ_POLICY))
    assert b"review.injected=ambient" in ordinary


@pytest.mark.parametrize("policy", [ACQUISITION_POLICY, STORE_READ_POLICY, BATCH_OBJECT_POLICY])
def test_isolated_policies_ignore_an_ambient_protocol_allowlist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, policy: GitProcessPolicy
) -> None:
    """``GIT_ALLOW_PROTOCOL`` replaces every ``protocol.*`` setting when Git sees it."""
    origin = tmp_path / "origin"
    origin.mkdir()
    asyncio.run(run_git(["init", "-q", "-b", "main"], cwd=origin))
    monkeypatch.setenv("GIT_ALLOW_PROTOCOL", "file")
    args = ["-c", "protocol.allow=never", "ls-remote", "--", f"file://{origin}", "HEAD"]
    with pytest.raises(GitCommandError):
        asyncio.run(run_git(args, cwd=tmp_path, policy=policy))
    assert asyncio.run(run_git(args, cwd=tmp_path, policy=READ_POLICY)) == b""


def test_isolated_policies_drop_every_ambient_git_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GIT_ALLOW_PROTOCOL", "file:ext")
    monkeypatch.setenv("GIT_DEFAULT_REF_FORMAT", "reftable")
    monkeypatch.setenv("GIT_TRACE", "1")
    monkeypatch.setenv("GIT_SSH_COMMAND", "ssh -oProxyCommand=ambient")
    for policy in (ACQUISITION_POLICY, STORE_READ_POLICY, BATCH_OBJECT_POLICY):
        env = git_environment(policy)
        wanted = {
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_NO_LAZY_FETCH": "1",
        }
        if policy.ssh_batch:
            wanted["GIT_SSH_COMMAND"] = "ssh -oBatchMode=yes"
        assert {name: value for name, value in env.items() if name.startswith("GIT_")} == wanted
    ordinary = git_environment(READ_POLICY)
    assert ordinary["GIT_ALLOW_PROTOCOL"] == "file:ext"
    assert ordinary["GIT_TRACE"] == "1"


def test_an_ambient_ref_format_does_not_reach_an_acquired_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Git 2.45 and newer honor ``GIT_DEFAULT_REF_FORMAT``; older admitted Gits read files."""
    monkeypatch.setenv("GIT_DEFAULT_REF_FORMAT", "reftable")
    store = tmp_path / "store.git"
    asyncio.run(
        run_git(
            ["init", "--bare", "--template=", "-q", str(store)],
            cwd=tmp_path,
            policy=ACQUISITION_POLICY,
        )
    )
    assert "refstorage" not in (store / "config").read_text(encoding="utf-8").lower()
    assert not (store / "reftable").exists()


@pytest.mark.parametrize("policy", [ACQUISITION_POLICY, STORE_READ_POLICY, BATCH_OBJECT_POLICY])
def test_isolated_policies_do_not_discover_an_enclosing_repository(
    tmp_path: Path, policy: GitProcessPolicy
) -> None:
    outer = tmp_path / "outer"
    nested = outer / "nested" / "home"
    nested.mkdir(parents=True)
    asyncio.run(run_git(["init", "-q", "-b", "main"], cwd=outer))
    asyncio.run(run_git(["config", "review.marker", "enclosing"], cwd=outer))
    isolated = asyncio.run(run_git(["config", "--list"], cwd=nested, policy=policy))
    assert b"review.marker" not in isolated
    ordinary = asyncio.run(run_git(["config", "--list"], cwd=nested, policy=READ_POLICY))
    assert b"review.marker=enclosing" in ordinary


def test_attached_worktree_target_does_not_follow_a_poisoned_git_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    decoy = tmp_path / "decoy"
    repo.mkdir()
    decoy.mkdir()
    asyncio.run(run_git(["init", "-q", "-b", "main"], cwd=repo))
    asyncio.run(run_git(["init", "-q", "-b", "main"], cwd=decoy))
    (repo / "file.txt").write_text("repo\n", encoding="utf-8")
    asyncio.run(run_git(["add", "file.txt"], cwd=repo))
    asyncio.run(
        run_git(
            ["-c", "user.name=T", "-c", "user.email=t@example.invalid", "commit", "-qm", "one"],
            cwd=repo,
        )
    )
    target = attached_worktree_target(worktree=repo, git_dir=repo / ".git")
    monkeypatch.setenv("GIT_DIR", str(decoy / ".git"))
    top = asyncio.run(run_git(["rev-parse", "--show-toplevel"], target=target))
    assert Path(top.decode().strip()).resolve() == repo.resolve()


def test_repository_store_target_names_the_bare_git_dir(tmp_path: Path) -> None:
    store = tmp_path / "store.git"
    asyncio.run(
        run_git(["init", "--bare", "-q", str(store)], cwd=tmp_path, policy=ACQUISITION_POLICY)
    )
    target = repository_store_target(git_dir=store)
    git_dir = asyncio.run(run_git(["rev-parse", "--absolute-git-dir"], target=target))
    assert Path(git_dir.decode().strip()).resolve() == store.resolve()


def test_acquisition_policy_creates_owner_only_store_entries(tmp_path: Path) -> None:
    store = tmp_path / "store.git"
    asyncio.run(
        run_git(
            ["init", "--bare", "--template=", str(store)], cwd=tmp_path, policy=ACQUISITION_POLICY
        )
    )
    leaked = [
        path
        for path in [store, *store.rglob("*")]
        if path.exists() and path.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO)
    ]
    assert leaked == []


def test_require_acquisition_git_matches_the_installed_binary() -> None:
    version, raw = detect_git_version()
    if acquisition_allowed(version):
        assert require_acquisition_git() == version
        return
    with pytest.raises(UnsupportedGitVersionError, match="unsupported Git version"):
        require_acquisition_git()
    assert parse_git_version(raw) == version


def test_git_location_requires_cwd_xor_target(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="cwd XOR target"):
        GitLocation(cwd=None, target=None, identity="x", pinned_revision=None)
    repo = tmp_path / "repo"
    repo.mkdir()
    asyncio.run(run_git(["init", "-q", "-b", "main"], cwd=repo))
    target = repository_store_target(git_dir=repo / ".git")
    with pytest.raises(TypeError, match="pinned revision"):
        GitLocation(cwd=None, target=target, identity="x", pinned_revision=None)
    with pytest.raises(TypeError, match="cwd XOR target"):
        GitLocation(cwd=repo, target=target, identity="x", pinned_revision="a" * 40)
    with pytest.raises(TypeError, match="cannot pin"):
        GitLocation(cwd=repo, target=None, identity="x", pinned_revision="a" * 40)
    located = GitLocation.filesystem(repo)
    assert as_location(repo).identity == located.identity
    assert located.pinned_revision is None
    assert located.cwd == repo.resolve()


def test_run_git_at_reads_a_filesystem_location(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    asyncio.run(run_git(["init", "-q", "-b", "main"], cwd=repo))
    (repo / "file.txt").write_text("ok\n", encoding="utf-8")
    asyncio.run(run_git(["add", "file.txt"], cwd=repo))
    asyncio.run(
        run_git(
            ["-c", "user.name=T", "-c", "user.email=t@example.invalid", "commit", "-qm", "one"],
            cwd=repo,
        )
    )
    oid = asyncio.run(run_git_at(["rev-parse", "HEAD"], GitLocation.filesystem(repo)))
    assert len(oid.strip()) == 40
