"""The GitHub provider's first-clone size check, ``gh`` runner, hint, and context.

A fake ``gh`` on ``PATH`` answers ``gh api repos/<o>/<r> --jq .size`` from an
environment variable and records the environment and arguments it was given, so the
check runs with no network and no GitHub account.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import stat
from collections.abc import Sequence
from pathlib import Path

import pytest

from metabrowser.builtin_plugins.github import gh as gh_module
from metabrowser.builtin_plugins.github.gh import GhError, gh_executable, run_gh
from metabrowser.builtin_plugins.github.provider import (
    MAX_FIRST_CLONE_ENV,
    MAX_FIRST_CLONE_KB,
    GithubProvider,
)
from metabrowser.cache.acquire import RepositoryTooLargeError
from metabrowser.cache.origin import describe_remote_failure
from metabrowser.cache.providers import (
    installed_providers,
    provider_git_config,
    repository_context_for,
)
from metabrowser.cache.urls import GitSource
from metabrowser.git.process import GIT_ACQUISITION_TIMEOUT_S, terminate_git_process

pytestmark = pytest.mark.skipif(os.name != "posix", reason="the fake gh is a POSIX shell script")

_FAKE_GH = """#!/bin/sh
env > "$FAKE_GH_LOG.env"
printf '%s\\n' "$@" > "$FAKE_GH_LOG.args"
if [ -t 0 ]; then echo tty > "$FAKE_GH_LOG.stdin"; else cat > "$FAKE_GH_LOG.stdin"; fi
case "$FAKE_GH_MODE" in
  size) printf '%s\\n' "$FAKE_GH_SIZE" ;;
  fail) echo 'HTTP 404: Not Found' >&2; exit 1 ;;
  hang)
    sleep "${FAKE_GH_STARTUP_DELAY:-0}"
    sleep 30 & echo $! > "$FAKE_GH_LOG.child"
    echo $$ > "$FAKE_GH_LOG.parent"
    echo ready
    wait ;;
  flood) yes x | head -c 100000 ;;
esac
"""

SOURCE = GitSource(transport="https", form="url", normalized="https://github.com/octo/demo")


@pytest.fixture
def fake_gh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "bin"
    directory.mkdir()
    gh = directory / "gh"
    gh.write_text(_FAKE_GH, encoding="utf-8")
    gh.chmod(gh.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_GH_LOG", str(tmp_path / "gh-log"))
    monkeypatch.setenv("GH_DEBUG", "api")
    monkeypatch.setenv("GH_HOST", "enterprise.example.com")
    monkeypatch.setenv("GH_REPO", "other/repo")
    monkeypatch.setenv("CLICOLOR_FORCE", "1")
    monkeypatch.setenv("GH_FORCE_TTY", "1")
    return tmp_path / "gh-log"


def test_a_repository_over_the_limit_is_refused_before_cloning(
    fake_gh: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_GH_MODE", "size")
    monkeypatch.setenv("FAKE_GH_SIZE", str(MAX_FIRST_CLONE_KB + 1))
    with pytest.raises(RepositoryTooLargeError) as refused:
        asyncio.run(GithubProvider().check_first_clone(SOURCE))
    assert refused.value.state == "too_large"
    message = str(refused.value)
    assert message.startswith("https://github.com/octo/demo is over the size limit")
    assert f"{MAX_FIRST_CLONE_KB + 1:,} KB" in message and "(too_large)" in message
    # Says what to do next, in words that stay true of a limit that can be moved: it claims
    # neither that this repository cannot be cloned in time nor that the limit is fixed.
    assert f"{MAX_FIRST_CLONE_ENV}={MAX_FIRST_CLONE_KB + 1} to try it" in message
    assert "still stops at 900 s" in message
    assert "within the acquisition deadline" not in message
    # Pinned to github.com: a user signed in only to an Enterprise host must not send
    # this repository name, or that host's token, anywhere but github.com.
    assert (fake_gh.parent / "gh-log.args").read_text().split() == [
        "api",
        "--hostname",
        "github.com",
        "--method",
        "GET",
        "repos/octo/demo",
        "--jq",
        ".size",
    ]


def test_the_limit_admits_what_was_measured_and_holds_at_the_slowest_rate(
    fake_gh: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The repository the limit was raised for: 185 s on 2026-11-02, reported at this size.
    monkeypatch.setenv("FAKE_GH_MODE", "size")
    monkeypatch.setenv("FAKE_GH_SIZE", "1222854")
    asyncio.run(GithubProvider().check_first_clone(SOURCE))
    # The comment beside the constant derives it: 1,820 KB/s of pack at 1.1 times the
    # reported size, inside the deadline.
    assert MAX_FIRST_CLONE_KB * 1.1 / 1820 < GIT_ACQUISITION_TIMEOUT_S


@pytest.mark.parametrize("override", ["5000000", " 5000000 "])
def test_the_environment_raises_the_limit(
    override: str, fake_gh: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_GH_MODE", "size")
    monkeypatch.setenv("FAKE_GH_SIZE", "5000000")
    monkeypatch.setenv(MAX_FIRST_CLONE_ENV, override)
    asyncio.run(GithubProvider().check_first_clone(SOURCE))


def test_the_environment_can_lower_the_limit_and_the_refusal_names_it(
    fake_gh: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_GH_MODE", "size")
    monkeypatch.setenv("FAKE_GH_SIZE", "2000")
    monkeypatch.setenv(MAX_FIRST_CLONE_ENV, "1000")
    with pytest.raises(RepositoryTooLargeError, match=r"limited to 1,000 KB"):
        asyncio.run(GithubProvider().check_first_clone(SOURCE))


@pytest.mark.parametrize("override", ["lots", "-5", "0", "1.5", "9" * 5000])
def test_a_limit_that_is_not_a_size_is_ignored_with_a_warning(
    override: str, fake_gh: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("FAKE_GH_MODE", "size")
    monkeypatch.setenv("FAKE_GH_SIZE", str(MAX_FIRST_CLONE_KB + 1))
    monkeypatch.setenv(MAX_FIRST_CLONE_ENV, override)
    with pytest.raises(RepositoryTooLargeError, match=f"limited to {MAX_FIRST_CLONE_KB:,} KB"):
        asyncio.run(GithubProvider().check_first_clone(SOURCE))
    assert f"ignored {MAX_FIRST_CLONE_ENV}" in caplog.text


def test_gh_runs_isolated_with_no_stdin(fake_gh: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_GH_MODE", "size")
    monkeypatch.setenv("FAKE_GH_SIZE", "12")
    asyncio.run(GithubProvider().check_first_clone(SOURCE))
    env = dict(
        line.split("=", 1)
        for line in (fake_gh.parent / "gh-log.env").read_text().splitlines()
        if "=" in line
    )
    assert env["GH_PROMPT_DISABLED"] == "1"
    assert env["GH_NO_UPDATE_NOTIFIER"] == "1"
    assert env["NO_COLOR"] == "1"
    assert "GH_DEBUG" not in env and "GH_HOST" not in env and "GH_REPO" not in env
    assert "CLICOLOR_FORCE" not in env and "GH_FORCE_TTY" not in env
    assert (fake_gh.parent / "gh-log.stdin").read_text() == ""


@pytest.mark.parametrize(("mode", "size"), [("size", "12"), ("fail", ""), ("size", "not-a-number")])
def test_a_small_repository_or_an_unanswered_check_does_not_refuse(
    fake_gh: Path, monkeypatch: pytest.MonkeyPatch, mode: str, size: str
) -> None:
    monkeypatch.setenv("FAKE_GH_MODE", mode)
    monkeypatch.setenv("FAKE_GH_SIZE", size)
    asyncio.run(GithubProvider().check_first_clone(SOURCE))


def test_no_gh_and_other_hosts_skip_the_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    assert gh_executable() is None
    asyncio.run(GithubProvider().check_first_clone(SOURCE))
    other = GitSource(transport="https", form="url", normalized="https://example.com/o/r.git")
    asyncio.run(GithubProvider().check_first_clone(other))


@pytest.mark.parametrize("startup_delay", ["0", "1.25"])
def test_a_hung_gh_is_killed_with_its_children(
    fake_gh: Path, monkeypatch: pytest.MonkeyPatch, startup_delay: str
) -> None:
    monkeypatch.setenv("FAKE_GH_MODE", "hang")
    monkeypatch.setenv("FAKE_GH_STARTUP_DELAY", startup_delay)
    finish = gh_module._finish
    process: asyncio.subprocess.Process | None = None
    pids: set[int] = set()

    async def after_ready(
        proc: asyncio.subprocess.Process,
        args: Sequence[str],
        *,
        timeout_s: float,
        max_bytes: int,
    ) -> gh_module._Completed:
        nonlocal process
        process = proc
        # The fixture must have a child before testing child cleanup. Its startup can
        # exceed the real one-second deadline on a loaded filesystem; do not lengthen
        # that deadline or accept a child which never existed.
        assert proc.stdout is not None
        async with asyncio.timeout(10):
            assert await proc.stdout.readline() == b"ready\n"
        assert int(fake_gh.with_suffix(".parent").read_text()) == proc.pid
        pids.update((proc.pid, int(fake_gh.with_suffix(".child").read_text())))
        assert len(pids) == 2
        for pid in pids:
            os.kill(pid, 0)
        return await finish(proc, args, timeout_s=timeout_s, max_bytes=max_bytes)

    monkeypatch.setattr(gh_module, "_finish", after_ready)

    async def check() -> None:
        try:
            with pytest.raises(GhError, match="did not answer within 1 s") as failed:
                await run_gh(["api", "x"], timeout_s=1)
            assert failed.value.state == "network_error"
            assert process is not None and process.returncode is not None
            async with asyncio.timeout(5):
                while pids:
                    for pid in tuple(pids):
                        try:
                            os.kill(pid, 0)
                        except ProcessLookupError:
                            pids.remove(pid)
                    if pids:
                        await asyncio.sleep(0.02)
        finally:
            # Cleanup follows the assertions, including readiness/cleanup failures.
            if process is not None:
                await terminate_git_process(process)
            for pid in pids:
                with contextlib.suppress(ProcessLookupError):
                    os.kill(pid, 9)

    asyncio.run(check())


def test_gh_output_is_capped(fake_gh: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_GH_MODE", "flood")
    with pytest.raises(GhError, match="more than 64 bytes"):
        asyncio.run(run_gh(["api", "x"], max_bytes=64))


def test_the_credential_hint_names_gh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    provider = GithubProvider()
    assert provider.credential_hint("https://example.com/o/r.git") is None
    monkeypatch.setenv("PATH", str(tmp_path))
    assert "install GitHub CLI (gh)" in (provider.credential_hint(SOURCE.normalized) or "")
    message = describe_remote_failure("not_found_or_private", SOURCE.normalized)
    assert message == (
        "https://github.com/octo/demo was not found, or it is private and could not be read "
        "(not_found_or_private); if it is private, install GitHub CLI (gh) and sign in with "
        "gh auth login; nothing was published"
    )


def test_a_not_found_message_does_not_say_git_has_no_credentials(fake_gh: Path) -> None:
    """With ``gh`` installed, Git asks it for credentials, and an account that cannot
    see the repository gets the same answer as no account. The message says the
    repository was not found or could not be read, not that Git had no credentials."""

    assert provider_git_config(SOURCE.normalized), "gh is Git's credential helper here"
    message = describe_remote_failure("not_found_or_private", SOURCE.normalized)
    assert message == (
        "https://github.com/octo/demo was not found, or it is private and could not be read "
        "(not_found_or_private); if it is private, sign in with gh auth login to an account "
        "that can read it; nothing was published"
    )


def test_repository_context_for_a_github_mirror() -> None:
    revision = "a" * 40
    assert repository_context_for(SOURCE.normalized, revision=revision, branch="topic") == {
        "branch": "topic",
        "host": "github.com",
        "name": "demo",
        "owner": "octo",
        "revision": revision,
        "served_prefix": "",
    }
    assert repository_context_for("file:///srv/demo.git", revision=revision, branch=None) is None
    assert repository_context_for(SOURCE.normalized, revision="b" * 64, branch=None) is None


def test_github_is_the_one_built_in_provider() -> None:
    assert [type(provider).__name__ for provider in installed_providers()] == ["GithubProvider"]
