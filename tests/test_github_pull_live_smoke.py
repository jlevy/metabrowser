"""Opt-in live smoke test: read real public pull requests with gh and Git.

Not part of ``make test`` or ``make verify``: it needs the network, an admitted Git, and
a ``gh`` signed in to github.com. Run it with::

    METABROWSER_LIVE_GITHUB=1 uv --config-file uv.toml run --frozen pytest -rs tests/test_github_pull_live_smoke.py

Everything is read-only: ``gh api`` reads of public pull requests, an anonymous clone of
a small public repository, and ``refs/pull/<n>/head`` fetches. Nothing is written to
GitHub. Each command is a separate installed ``metab`` process with a fresh application
home, as a user would run it. Files changed is checked against GitHub's own list, for a
merged pull request from a fork and for an open one.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from metabrowser.git.process import _REPO_PINNING_GIT_VARS  # pyright: ignore[reportPrivateUsage]
from tests.admitted_git import require_admitted_git

LIVE_ENV = "METABROWSER_LIVE_GITHUB"

pytestmark = [
    pytest.mark.skipif(os.environ.get(LIVE_ENV) != "1", reason=f"set {LIVE_ENV}=1 to run"),
    pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only"),
    pytest.mark.timeout(600),
]

REPOSITORY = "pallets/markupsafe"
REPO_URL = f"https://github.com/{REPOSITORY}"
# Merged, from the crusaderky/markupsafe fork, three commits and five files.
MERGED_FROM_FORK = 507


def _metab() -> str:
    beside = Path(sys.executable).parent / "metab"
    found = str(beside) if beside.is_file() else shutil.which("metab")
    assert found, "the metab console script is not installed in this environment"
    return found


def _env(home: Path, path: str | None = None) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key not in _REPO_PINNING_GIT_VARS}
    env.update({"METABROWSER_HOME": str(home), "METABROWSER_LOG_LEVEL": "ERROR", "TERM": "dumb"})
    if path is not None:
        env["PATH"] = path
    return env


def _run(home: Path, *args: str, path: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [_metab(), *args],
        check=False,
        capture_output=True,
        text=True,
        env=_env(home, path),
        stdin=subprocess.DEVNULL,
        timeout=300,
    )


def _envelope(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    assert result.returncode == 0, (result.stdout, result.stderr)
    return json.loads(result.stdout[result.stdout.index("{") :])


def _gh_json(*args: str) -> Any:
    return json.loads(
        subprocess.run(
            ["gh", "api", "--hostname", "github.com", *args],
            check=True,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=60,
        ).stdout
    )


def _require_signed_in_gh() -> None:
    if shutil.which("gh") is None:
        pytest.skip("gh is not installed")
    status = subprocess.run(
        ["gh", "auth", "status", "--active", "--hostname", "github.com", "--json", "hosts"],
        check=False,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=60,
    )
    if '"login"' not in status.stdout:
        pytest.skip("gh is not signed in to github.com")


def _changed_paths(document: dict[str, Any]) -> set[str]:
    return {
        (change.get("new") or change.get("old"))["path"] for change in document["manifest"]["files"]
    }


def _github_files(number: int) -> set[str]:
    return {
        entry["filename"]
        for entry in _gh_json(f"repos/{REPOSITORY}/pulls/{number}/files?per_page=100")
    }


def _no_gh_path(tmp_path: Path) -> str:
    """``PATH`` with a ``gh`` first that fails, so a cached read that asked it would fail."""

    directory = tmp_path / "no-gh"
    directory.mkdir(exist_ok=True)
    gh = directory / "gh"
    gh.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    gh.chmod(gh.stat().st_mode | stat.S_IXUSR)
    return f"{directory}{os.pathsep}{os.environ.get('PATH', '')}"


def _check_files_changed(home: Path, number: int, *, merged: bool) -> dict[str, Any]:
    envelope = _envelope(
        _run(home, f"{REPO_URL}/pull/{number}", "--api", "/api/plugin/github/pull")
    )
    record = envelope["record"]
    pull = record["pull"]
    assert envelope["state"] == "current"
    assert envelope["pin"] == pull["head"]["sha"]
    assert record["reader"].startswith("gh:")
    assert pull["merged"] is merged
    comparison = record["comparison"]
    assert comparison["head"] == pull["head"]["sha"]
    assert comparison["base_from"] == ("base_sha" if merged else "base_branch")
    document = _envelope(
        _run(home, f"{REPO_URL}/pull/{number}", "--api", envelope["comparison_route"])
    )
    assert document["resolved"]["base_policy"] == "merge_base"
    assert document["resolved"]["left"]["id"] == comparison["base"]
    assert _changed_paths(document) == _github_files(number)
    return envelope


def test_live_merged_pull_request_from_a_fork(tmp_path: Path) -> None:
    require_admitted_git()
    _require_signed_in_gh()
    home = tmp_path / "home"
    first = _check_files_changed(home, MERGED_FROM_FORK, merged=True)
    assert first["record"]["pull"]["head"]["repository"] != REPOSITORY

    # Offline from gh's point of view: the cached record answers, and gh is not asked.
    again = _envelope(
        _run(
            home,
            f"{REPO_URL}/pull/{MERGED_FROM_FORK}",
            "--api",
            "/api/plugin/github/pull",
            path=_no_gh_path(tmp_path),
        )
    )
    assert again["record"] == first["record"]


def test_live_open_pull_request(tmp_path: Path) -> None:
    require_admitted_git()
    _require_signed_in_gh()
    listed = _gh_json(f"repos/{REPOSITORY}/pulls?state=open&per_page=1")
    if not listed:
        pytest.skip(f"{REPOSITORY} has no open pull request today")
    _check_files_changed(tmp_path / "home", listed[0]["number"], merged=False)
