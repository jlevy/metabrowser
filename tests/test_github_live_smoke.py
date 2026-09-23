"""Opt-in live smoke test: open real public GitHub repositories over HTTPS.

Not part of ``make test`` or ``make verify``: it needs the network and an admitted Git.
Run it with::

    METABROWSER_LIVE_GITHUB=1 uv --config-file uv.toml run --frozen pytest -rs tests/test_github_live_smoke.py

Everything is read-only. One test serves a public repository in-process, asks
``POST /api/source/refresh``, and reads ``/api/source/status``. Clones are anonymous: each ``metab`` process has a fake ``gh``
first on ``PATH`` that answers nothing, so Git's credential helper never returns a real
credential. The real ``gh``, when it is installed and signed in, is used for one thing,
the provider's ``gh api --hostname github.com repos/<o>/<r>`` size check, a GET that
prints only a number. Nothing is ever written to GitHub. Each command is a separate
installed ``metab`` process with a fresh application home, as a user would run it.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import pytest

from metabrowser.builtin_plugins.github.gh import GhError, gh_executable, run_gh
from metabrowser.builtin_plugins.github.provider import GithubProvider
from metabrowser.cache.acquire import RepositoryTooLargeError
from metabrowser.cache.urls import GitSource
from metabrowser.git.process import _REPO_PINNING_GIT_VARS
from tests.admitted_git import require_admitted_git

LIVE_ENV = "METABROWSER_LIVE_GITHUB"

pytestmark = [
    pytest.mark.skipif(os.environ.get(LIVE_ENV) != "1", reason=f"set {LIVE_ENV}=1 to run"),
    pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only"),
    # Clones over a real network; the suite's 60 s default is for local work.
    pytest.mark.timeout(600),
]

HELLO = "https://github.com/octocat/Hello-World"
# A small public repository whose branches include names with a slash.
SLASHED = "https://github.com/github/gitignore"


@dataclass(frozen=True, slots=True)
class _Result:
    exit_code: int
    stdout: str
    stderr: str


def _metab() -> str:
    beside = Path(sys.executable).parent / "metab"
    found = str(beside) if beside.is_file() else shutil.which("metab")
    assert found, "the metab console script is not installed in this environment"
    return found


def _no_credentials_path(tmp_path: Path) -> str:
    """``PATH`` with a ``gh`` first that answers nothing, so every clone is anonymous."""

    directory = tmp_path / "no-credentials"
    directory.mkdir(exist_ok=True)
    gh = directory / "gh"
    gh.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    gh.chmod(gh.stat().st_mode | stat.S_IXUSR)
    return f"{directory}{os.pathsep}{os.environ.get('PATH', '')}"


def _run(home: Path, *args: str, path: str | None = None) -> _Result:
    env = {key: value for key, value in os.environ.items() if key not in _REPO_PINNING_GIT_VARS}
    env.update({"METABROWSER_HOME": str(home), "METABROWSER_LOG_LEVEL": "ERROR", "TERM": "dumb"})
    if path is not None:
        env["PATH"] = path
    completed = subprocess.run(
        [_metab(), *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        stdin=subprocess.DEVNULL,
        timeout=300,
    )
    return _Result(completed.returncode, completed.stdout, completed.stderr)


def _ok(home: Path, *args: str, path: str | None = None) -> _Result:
    result = _run(home, *args, path=path)
    assert result.exit_code == 0, (args, result.stdout, result.stderr)
    return result


def test_live_anonymous_open_of_a_public_repository(tmp_path: Path) -> None:
    require_admitted_git()
    home = tmp_path / "home"
    anonymous = _no_credentials_path(tmp_path)

    first = _ok(home, HELLO, "--no-serve", path=anonymous)
    assert "acquired: https://github.com/octocat/hello-world\n" in first.stdout
    revision = first.stdout.split("revision: ", 1)[1].split()[0]

    # A cache hit: the same identity, no clone.
    again = _ok(
        home, "https://www.github.com/OctoCat/Hello-World.git", "--no-serve", path=anonymous
    )
    assert again.stdout == first.stdout

    repo = _ok(home, HELLO, "--api", "/api/git/repo", path=anonymous)
    assert f'"revision": "{revision}"' in repo.stdout

    shown = _ok(home, f"{HELLO}/blob/master/README#L1", "--show", "README", path=anonymous)
    assert "kind: text" in shown.stdout
    assert "lines: L1" in shown.stderr and "(branch master)" in shown.stderr


def test_live_tree_url_with_a_slash_containing_ref(tmp_path: Path) -> None:
    require_admitted_git()
    listed = subprocess.run(
        ["git", "ls-remote", "--heads", "--", SLASHED],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    ).stdout
    slashed = [
        (line.split("\t")[0], line.split("\t")[1].removeprefix("refs/heads/"))
        for line in listed.splitlines()
        if "/" in line.split("\t")[1].removeprefix("refs/heads/")
    ]
    if not slashed:
        pytest.skip(f"{SLASHED} has no branch with a slash today")
    oid, branch = slashed[0]
    home = tmp_path / "home"
    anonymous = _no_credentials_path(tmp_path)
    opened = _ok(home, f"{SLASHED}/tree/{branch}", "--no-serve", path=anonymous)
    assert f"pin: {oid} (branch {branch})" in opened.stdout
    repo = _ok(home, f"{SLASHED}/tree/{branch}", "--api", "/api/git/repo", path=anonymous)
    assert f'"revision": "{oid}"' in repo.stdout


def test_live_missing_repository_is_a_typed_state(tmp_path: Path) -> None:
    require_admitted_git()
    result = _run(
        tmp_path / "home",
        "https://github.com/octocat/definitely-not-a-repository-9431",
        "--no-serve",
        path=_no_credentials_path(tmp_path),
    )
    assert result.exit_code == 1
    assert "(not_found_or_private)" in result.stderr
    assert "nothing was published" in result.stderr


def test_live_size_check_with_the_real_gh() -> None:
    """The provider's own read-only size query; no clone, and no credential command."""

    if gh_executable() is None:
        pytest.skip("gh is not installed")
    try:
        asyncio.run(
            run_gh(
                [
                    "api",
                    "--hostname",
                    "github.com",
                    "--method",
                    "GET",
                    "repos/octocat/Hello-World",
                    "--jq",
                    ".size",
                ]
            )
        )
    except GhError:
        pytest.skip("gh cannot read the GitHub API here (signed out or offline)")
    provider = GithubProvider()
    small = GitSource(
        transport="https", form="url", normalized="https://github.com/octocat/hello-world"
    )
    asyncio.run(provider.check_first_clone(small))
    large = GitSource(transport="https", form="url", normalized="https://github.com/torvalds/linux")
    with pytest.raises(RepositoryTooLargeError, match=r"\(too_large\)"):
        asyncio.run(provider.check_first_clone(large))


def test_live_serve_refresh_and_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve a public repository in-process, refresh it over HTTPS, and read status.

    Read-only, and anonymous: the fake ``gh`` is first on ``PATH`` for the process, so
    the credential helper and the size check both find nothing.
    """

    require_admitted_git()
    from starlette.testclient import TestClient
    from typer.testing import CliRunner

    from metabrowser import server
    from metabrowser.cli.main import _app
    from metabrowser.source import reset_source_session

    monkeypatch.setenv("METABROWSER_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("PATH", _no_credentials_path(tmp_path))
    monkeypatch.setattr("metabrowser.cli.git_pin_cli.stop_on_interrupt", lambda: None)
    with (
        patch("metabrowser.cli.serve._QuietForceExitServer"),
        patch("metabrowser.cli.serve.find_available_local_port", return_value=8411),
    ):
        result = CliRunner().invoke(_app, [f"{HELLO}/blob/master/README#L1", "--no-open"])
    assert result.exit_code == 0, result.output
    assert "Revision: " in result.stdout and "(master)" in result.stdout
    try:
        with TestClient(server.app) as client:
            status = client.get("/api/source/status").json()
            assert status["ref_name"] == "master" and status["refreshable"] is True
            pin = status["pin"]
            started = client.post(
                "/api/source/refresh", json={}, headers={"content-type": "application/json"}
            )
            assert started.status_code == 202
            deadline = time.monotonic() + 120
            while client.get("/api/source/status").json()["refreshing"]:
                assert time.monotonic() < deadline, "the refresh did not finish"
                time.sleep(0.2)
            after = client.get("/api/source/status").json()
            assert after["last_outcome"]["operation"] == "refresh"
            assert after["last_outcome"]["outcome"] == "succeeded", after
            assert after["pin"] == pin and after["latest"] is not None
            shell = client.get("/view/").text
            assert '"owner": "octocat"' in shell and '"name": "hello-world"' in shell
    finally:
        reset_source_session()
