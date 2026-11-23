"""The GitHub provider's first-clone size check, ``gh`` runner, hint, and context.

A fake ``gh`` on ``PATH`` answers ``gh api repos/<o>/<r> --jq .size`` from an
environment variable and records the environment and arguments it was given, so the
check runs with no network and no GitHub account.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import stat
from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

from metabrowser.builtin_plugins.github import gh as gh_module
from metabrowser.builtin_plugins.github import provider as provider_module
from metabrowser.builtin_plugins.github.gh import GhError, gh_executable, run_gh
from metabrowser.builtin_plugins.github.gh_lists import PullDataError
from metabrowser.builtin_plugins.github.gh_status import kept_github_status
from metabrowser.builtin_plugins.github.provider import (
    GithubProvider,
    GithubSignInRequiredError,
)
from metabrowser.cache.acquire import RepositoryTooLargeError
from metabrowser.cache.free_space import (
    FREE_SPACE_RESERVE_ENV,
    FREE_SPACE_RESERVE_MB,
    packed_bytes,
)
from metabrowser.cache.origin import describe_remote_failure
from metabrowser.cache.providers import (
    PullRequestUnavailableError,
    installed_providers,
    provider_git_config,
    repository_context_for,
)
from metabrowser.cache.urls import GitSource, RepositorySelection
from metabrowser.git.process import terminate_git_process

if TYPE_CHECKING:
    from metabrowser.cache.acquire import PublishedSource

pytestmark = pytest.mark.skipif(os.name != "posix", reason="the fake gh is a POSIX shell script")

# A volume with room for anything these tests clone, and a size that does not fit on it.
PLENTY_FREE: int = 100 * 10**9
TOO_LARGE_KB: int = 100_000_000
# The repository a fixed 1,350,000 KB limit refused (2026-11-23), at GitHub's reported size.
REPORTED_KB: int = 1_570_073
RESERVE: int = FREE_SPACE_RESERVE_MB * 1_000_000

_FAKE_GH = """#!/bin/sh
if [ "$1" = auth ]; then
  case "$FAKE_GH_AUTH" in
    too-old) echo 'unknown flag: --json' >&2; exit 1 ;;
    broken) exit 1 ;;
  esac
  printf '%s\\n' "$FAKE_GH_AUTH"; exit 0
fi
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
PULL = GitSource(
    transport="https",
    form="url",
    normalized="https://github.com/octo/demo",
    selection=RepositorySelection(kind="pull_request", pull_request=7),
)


def _signed_in(scopes: str = "gist, read:org, repo, workflow") -> str:
    """``gh auth status --json hosts`` for one active account, as gh 2.98.0 prints it."""

    host = {
        "state": "success",
        "active": True,
        "host": "github.com",
        "login": "octo-reader",
        "tokenSource": "keyring",
        "scopes": scopes,
        "gitProtocol": "https",
    }
    return json.dumps({"hosts": {"github.com": [host]}})


@pytest.fixture
def fake_gh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "bin"
    directory.mkdir()
    gh = directory / "gh"
    gh.write_text(_FAKE_GH, encoding="utf-8")
    gh.chmod(gh.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_GH_LOG", str(tmp_path / "gh-log"))
    monkeypatch.setenv("FAKE_GH_AUTH", _signed_in())
    monkeypatch.setenv("GH_DEBUG", "api")
    monkeypatch.setenv("GH_HOST", "enterprise.example.com")
    monkeypatch.setenv("GH_REPO", "other/repo")
    monkeypatch.setenv("CLICOLOR_FORCE", "1")
    monkeypatch.setenv("GH_FORCE_TTY", "1")
    return tmp_path / "gh-log"


def test_a_repository_that_does_not_fit_is_refused_before_cloning(
    fake_gh: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_GH_MODE", "size")
    monkeypatch.setenv("FAKE_GH_SIZE", str(REPORTED_KB))
    free = 2 * 10**9
    with pytest.raises(RepositoryTooLargeError) as refused:
        asyncio.run(GithubProvider().check_first_clone(SOURCE, free_bytes=free))
    assert refused.value.state == "too_large"
    assert str(refused.value) == (
        "https://github.com/octo/demo does not fit on the cache's volume for a first clone "
        "(too_large); GitHub reports 1,570,073 KB, which can take 1.8 GB, and the cache's "
        "volume has 2.0 GB free, of which metab leaves 1.0 GB; free space on the volume, "
        f"set METABROWSER_CACHE_DIR to one with more, or lower {FREE_SPACE_RESERVE_ENV}; "
        "nothing was published"
    )
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


def test_a_repository_that_fits_with_the_reserve_left_is_cloned_whatever_its_size(
    fake_gh: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No size is refused for itself: what fits, with the reserve left free, clones."""

    monkeypatch.setenv("FAKE_GH_MODE", "size")
    monkeypatch.setenv("FAKE_GH_SIZE", str(REPORTED_KB))
    fits = packed_bytes(REPORTED_KB) + RESERVE
    asyncio.run(GithubProvider().check_first_clone(SOURCE, free_bytes=fits))
    with pytest.raises(RepositoryTooLargeError):
        asyncio.run(GithubProvider().check_first_clone(SOURCE, free_bytes=fits - 1))
    monkeypatch.setenv("FAKE_GH_SIZE", str(TOO_LARGE_KB // 10))
    asyncio.run(GithubProvider().check_first_clone(SOURCE, free_bytes=PLENTY_FREE))


@pytest.mark.parametrize("override", ["0", " 0 "])
def test_the_environment_sets_the_reserve(
    override: str, fake_gh: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_GH_MODE", "size")
    monkeypatch.setenv("FAKE_GH_SIZE", str(REPORTED_KB))
    monkeypatch.setenv(FREE_SPACE_RESERVE_ENV, override)
    asyncio.run(GithubProvider().check_first_clone(SOURCE, free_bytes=packed_bytes(REPORTED_KB)))
    monkeypatch.setenv(FREE_SPACE_RESERVE_ENV, "5000")
    with pytest.raises(RepositoryTooLargeError, match=r"of which metab leaves 5\.0 GB"):
        asyncio.run(GithubProvider().check_first_clone(SOURCE, free_bytes=6 * 10**9))


@pytest.mark.parametrize("override", ["lots", "-5", "1.5", "9" * 5000])
def test_a_reserve_that_is_not_a_size_is_ignored_with_a_warning(
    override: str, fake_gh: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("FAKE_GH_MODE", "size")
    monkeypatch.setenv("FAKE_GH_SIZE", str(REPORTED_KB))
    monkeypatch.setenv(FREE_SPACE_RESERVE_ENV, override)
    fits = packed_bytes(REPORTED_KB) + RESERVE
    asyncio.run(GithubProvider().check_first_clone(SOURCE, free_bytes=fits))
    with pytest.raises(RepositoryTooLargeError, match=r"of which metab leaves 1\.0 GB"):
        asyncio.run(GithubProvider().check_first_clone(SOURCE, free_bytes=fits - 1))
    assert f"ignored {FREE_SPACE_RESERVE_ENV}" in caplog.text


def test_a_volume_whose_free_space_is_unknown_skips_the_size_read(
    fake_gh: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_GH_MODE", "size")
    monkeypatch.setenv("FAKE_GH_SIZE", str(TOO_LARGE_KB))
    asyncio.run(GithubProvider().check_first_clone(SOURCE, free_bytes=None))
    assert not (fake_gh.parent / "gh-log.args").exists()


def test_gh_runs_isolated_with_no_stdin(fake_gh: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_GH_MODE", "size")
    monkeypatch.setenv("FAKE_GH_SIZE", "12")
    asyncio.run(GithubProvider().check_first_clone(SOURCE, free_bytes=PLENTY_FREE))
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
    asyncio.run(GithubProvider().check_first_clone(SOURCE, free_bytes=PLENTY_FREE))


@pytest.mark.parametrize(("auth", "state"), [("too-old", "gh_too_old"), ("broken", "gh_failed")])
def test_a_gh_the_status_check_cannot_type_still_reads_the_size(
    fake_gh: Path, monkeypatch: pytest.MonkeyPatch, auth: str, state: str
) -> None:
    """A gh too old for `auth status --json`, or one whose answer the check cannot type,
    may still read the API, so the size guard still runs; only no gh, no account, or no
    network skips it."""

    monkeypatch.setenv("FAKE_GH_AUTH", auth)
    monkeypatch.setenv("FAKE_GH_MODE", "size")
    monkeypatch.setenv("FAKE_GH_SIZE", str(TOO_LARGE_KB))
    with pytest.raises(RepositoryTooLargeError):
        asyncio.run(GithubProvider().check_first_clone(SOURCE, free_bytes=PLENTY_FREE))
    kept = kept_github_status()
    assert kept is not None and kept.state == state


def test_no_gh_and_other_hosts_skip_the_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    assert gh_executable() is None
    asyncio.run(GithubProvider().check_first_clone(SOURCE, free_bytes=PLENTY_FREE))
    other = GitSource(transport="https", form="url", normalized="https://example.com/o/r.git")
    asyncio.run(GithubProvider().check_first_clone(other, free_bytes=PLENTY_FREE))


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


def test_a_pull_request_gh_cannot_read_stops_before_its_first_clone(
    fake_gh: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Signed out, a pull-request URL stops before anything is cloned, with the command
    that fixes it; a repository URL goes on, since a public one clones without gh."""

    monkeypatch.setenv("FAKE_GH_AUTH", '{"hosts":{}}')
    monkeypatch.setenv("FAKE_GH_MODE", "size")
    monkeypatch.setenv("FAKE_GH_SIZE", str(TOO_LARGE_KB))
    with pytest.raises(GithubSignInRequiredError) as refused:
        asyncio.run(GithubProvider().check_first_clone(PULL, free_bytes=PLENTY_FREE))
    assert refused.value.state == "not_logged_in"
    assert str(refused.value) == (
        "pull request 7 of https://github.com/octo/demo cannot be read: GitHub CLI is not "
        "signed in to github.com. Run gh auth login --hostname github.com, then retry. "
        "(not_logged_in); nothing was cloned"
    )
    # Signed out, the size read would fail as well, so it is not asked.
    asyncio.run(GithubProvider().check_first_clone(SOURCE, free_bytes=PLENTY_FREE))
    assert not (fake_gh.parent / "gh-log.args").exists()


def test_a_pull_request_with_no_gh_stops_before_its_first_clone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(
        GithubSignInRequiredError, match=r"Install it from https://cli\.github\.com/"
    ):
        asyncio.run(GithubProvider().check_first_clone(PULL, free_bytes=PLENTY_FREE))


def test_a_token_without_the_repo_scope_is_named_when_a_repository_is_not_found(
    fake_gh: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A public repository still clones, so the check stops nothing, and the size is
    still read; the not-found message a failed clone then prints names the scope."""

    monkeypatch.setenv("FAKE_GH_AUTH", _signed_in("gist, read:org"))
    monkeypatch.setenv("FAKE_GH_MODE", "size")
    monkeypatch.setenv("FAKE_GH_SIZE", "12")
    asyncio.run(GithubProvider().check_first_clone(PULL, free_bytes=PLENTY_FREE))
    assert (fake_gh.parent / "gh-log.args").read_text().split()[-1] == ".size"
    message = describe_remote_failure("not_found_or_private", SOURCE.normalized)
    assert message == (
        "https://github.com/octo/demo was not found, or it is private and could not be read "
        "(not_found_or_private); if it is private, gh's token for octo-reader lacks the repo "
        "scope: gh auth refresh --hostname github.com --scopes repo; nothing was published"
    )


def test_a_pull_request_on_a_cached_mirror_names_a_missing_scope(
    fake_gh: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cached mirror skips the first-clone check, so no recent answer is kept; a pull
    request GitHub does not show still names the scope, whatever ran before."""

    async def not_shown(*_args: object, **_kwargs: object) -> None:
        raise PullDataError("not_found_or_private", "pull request 9 was not found")

    monkeypatch.setattr(provider_module, "open_pull_request", not_shown)
    monkeypatch.setenv("FAKE_GH_AUTH", _signed_in("gist, read:org"))
    assert kept_github_status() is None
    published = cast("PublishedSource", SimpleNamespace(source=SOURCE))
    with pytest.raises(PullRequestUnavailableError) as unavailable:
        asyncio.run(GithubProvider().pull_request(published, 9, fetch="if_missing"))
    assert not unavailable.value.blocking
    assert str(unavailable.value) == (
        "pull request 9 of https://github.com/octo/demo: pull request 9 was not found "
        "(not_found_or_private); if it is private, gh's token for octo-reader lacks the "
        "repo scope: gh auth refresh --hostname github.com --scopes repo"
    )


def test_repository_context_for_a_github_mirror() -> None:
    revision = "a" * 40
    assert repository_context_for(SOURCE.normalized, revision=revision, branch="topic") == {
        "branch": "topic",
        "branch_on_origin": True,
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
