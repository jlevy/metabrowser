"""Opt-in live smoke test: open real public GitHub repositories over HTTPS.

Not part of ``make test`` or ``make verify``: it needs the network and an admitted Git.
Run it with::

    METABROWSER_LIVE_GITHUB=1 uv --config-file uv.toml run --frozen pytest -rs tests/test_github_live_smoke.py

Everything is read-only: anonymous clones of small public repositories, ``ls-remote``,
and, when ``gh`` is installed, the read-only ``repos/<o>/<r>`` size check. Nothing is
ever written to GitHub. Each command is a separate installed ``metab`` process with a
fresh application home, as a user would run it.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

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
