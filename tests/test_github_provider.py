"""The GitHub provider's first-clone size check, ``gh`` runner, hint, and context.

A fake ``gh`` on ``PATH`` answers ``gh api repos/<o>/<r> --jq .size`` from an
environment variable and records the environment and arguments it was given, so the
check runs with no network and no GitHub account.
"""

from __future__ import annotations

import asyncio
import os
import stat
import time
from pathlib import Path

import pytest

from metabrowser.builtin_plugins.github.gh import GhError, gh_executable, run_gh
from metabrowser.builtin_plugins.github.provider import MAX_FIRST_CLONE_KB, GithubProvider
from metabrowser.cache.acquire import RepositoryTooLargeError
from metabrowser.cache.providers import installed_providers, repository_context_for
from metabrowser.cache.remote import describe_remote_failure
from metabrowser.cache.urls import GitSource

pytestmark = pytest.mark.skipif(os.name != "posix", reason="the fake gh is a POSIX shell script")

_FAKE_GH = """#!/bin/sh
env > "$FAKE_GH_LOG.env"
printf '%s\\n' "$@" > "$FAKE_GH_LOG.args"
if [ -t 0 ]; then echo tty > "$FAKE_GH_LOG.stdin"; else cat > "$FAKE_GH_LOG.stdin"; fi
case "$FAKE_GH_MODE" in
  size) printf '%s\\n' "$FAKE_GH_SIZE" ;;
  fail) echo 'HTTP 404: Not Found' >&2; exit 1 ;;
  hang) sleep 30 & echo $! > "$FAKE_GH_LOG.child"; wait ;;
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
    assert message.startswith("https://github.com/octo/demo is too large to clone")
    assert f"{MAX_FIRST_CLONE_KB + 1:,} KB" in message and "(too_large)" in message
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


def test_a_hung_gh_is_killed_with_its_children(
    fake_gh: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_GH_MODE", "hang")
    with pytest.raises(GhError, match="did not answer"):
        asyncio.run(run_gh(["api", "x"], timeout_s=1))
    child = int((fake_gh.parent / "gh-log.child").read_text())
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.kill(child, 0)
        except ProcessLookupError:
            return
        time.sleep(0.02)
    os.kill(child, 9)
    pytest.fail("the hung gh's child outlived the timeout")


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
    assert message.startswith("https://github.com/octo/demo was not found, or it is private")
    assert "(not_found_or_private)" in message and "gh auth login" in message
    assert message.endswith("nothing was published")


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
