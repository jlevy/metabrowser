"""Git runner policies, command targets, and the acquisition version floor."""

from __future__ import annotations

import asyncio
import os
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
from tests.required_tools import needs_git

pytestmark = needs_git


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
    """Isolation is an allowlist: a spawn gets exactly the variables its policy sets.

    An ambient ``GIT_ALLOW_PROTOCOL`` would otherwise replace every ``protocol.*``
    setting, on an acquisition and on a request-path read of a published store alike.
    Each policy's set is spelled out here rather than read back from the policy, so a
    policy that stopped forcing SSH batch mode would fail.
    """

    monkeypatch.setenv("GIT_ALLOW_PROTOCOL", "file:ext")
    monkeypatch.setenv("GIT_DEFAULT_REF_FORMAT", "reftable")
    monkeypatch.setenv("GIT_TRACE", "1")
    monkeypatch.setenv("GIT_SSH_COMMAND", "ssh -oProxyCommand=ambient")
    isolated = {
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_NO_LAZY_FETCH": "1",
    }
    ssh_batch = {"GIT_SSH_COMMAND": "ssh -oBatchMode=yes"}
    for policy, forced in (
        (ACQUISITION_POLICY, ssh_batch),
        (STORE_READ_POLICY, ssh_batch),
        (BATCH_OBJECT_POLICY, {}),
    ):
        env = git_environment(policy)
        assert {
            name: value for name, value in env.items() if name.startswith("GIT_")
        } == isolated | forced, policy.name
    ordinary = git_environment(READ_POLICY)
    assert ordinary["GIT_ALLOW_PROTOCOL"] == "file:ext"
    assert ordinary["GIT_TRACE"] == "1"
    # An ordinary read of the user's own worktree keeps the caller's environment:
    # nothing an isolated policy forces.
    assert ordinary["GIT_SSH_COMMAND"] == "ssh -oProxyCommand=ambient"
    assert "GIT_NO_LAZY_FETCH" not in ordinary
    assert "GIT_CONFIG_NOSYSTEM" not in ordinary


def test_no_git_can_ask_a_person_and_isolated_git_speaks_one_locale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """What the ``GIT_`` allowlist does not reach: the askpass, the manager, the locale.

    ``SSH_ASKPASS`` is cleared for every spawn, so a repository that needs a credential
    fails instead of waiting on a prompt nobody sees. An acquisition and a store read
    also tell the credential manager never to prompt, and run in the C locale, because
    Git's messages are matched as text (``cache/origin.py``, ``git/detail.py``).
    """

    monkeypatch.setenv("SSH_ASKPASS", "/usr/libexec/ambient-askpass")
    monkeypatch.setenv("GCM_INTERACTIVE", "always")
    monkeypatch.setenv("LC_ALL", "de_DE.UTF-8")
    for policy in (READ_POLICY, ACQUISITION_POLICY, STORE_READ_POLICY, BATCH_OBJECT_POLICY):
        assert git_environment(policy)["SSH_ASKPASS"] == "", policy.name
    for policy in (ACQUISITION_POLICY, STORE_READ_POLICY):
        env = git_environment(policy)
        assert (env["GCM_INTERACTIVE"], env["LC_ALL"]) == ("never", "C"), policy.name


# ``git hash-object --stdin`` of no input: the empty blob.
_EMPTY_BLOB = b"e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"


@pytest.mark.parametrize("policy", [ACQUISITION_POLICY, STORE_READ_POLICY], ids=lambda p: p.name)
def test_an_isolated_git_never_waits_on_the_callers_stdin(
    tmp_path: Path, policy: GitProcessPolicy
) -> None:
    """Its stdin is the null device, whatever this process's own stdin is.

    The process's stdin is replaced with a pipe nobody writes to or closes. A Git that
    inherited it would wait until the deadline; one reading the null device sees the
    end of input at once and names the empty blob.
    """

    read_end, write_end = os.pipe()
    saved = os.dup(0)
    os.dup2(read_end, 0)
    try:
        answered = asyncio.run(
            run_git(["hash-object", "--stdin"], cwd=tmp_path, policy=policy, timeout_s=15)
        )
    finally:
        os.dup2(saved, 0)
        for descriptor in (saved, read_end, write_end):
            os.close(descriptor)
    assert answered.strip() == _EMPTY_BLOB


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
