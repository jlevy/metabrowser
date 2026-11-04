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
    pytest.mark.live_github,
    pytest.mark.skipif(os.environ.get(LIVE_ENV) != "1", reason=f"set {LIVE_ENV}=1 to run"),
    pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only"),
    # Clones and reads over a real network. Measured on 2026-09-30 from a home
    # connection, on a 10-core M1 Pro at load average 60-90: the seven live tests took
    # 151 s, the slowest 38 s. The network is not ours to bound, so this is generous;
    # it also has to exceed the 300 s bound on one ``metab`` call below.
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
    env.update(
        {"METABROWSER_CACHE_DIR": str(home), "METABROWSER_LOG_LEVEL": "ERROR", "TERM": "dumb"}
    )
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
        pytest.fail(f"{LIVE_ENV}=1 selected the live tier, which needs gh; it is not installed")
    status = subprocess.run(
        ["gh", "auth", "status", "--active", "--hostname", "github.com", "--json", "hosts"],
        check=False,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=60,
    )
    if '"login"' not in status.stdout:
        pytest.fail(f"{LIVE_ENV}=1 selected the live tier, but gh is not signed in to github.com")


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
        _run(home, f"{REPO_URL}/pull/{number}", "--api", f"/api/plugin/github/pull?number={number}")
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
            f"/api/plugin/github/pull?number={MERGED_FROM_FORK}",
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


def _github_pull_counts() -> dict[str, int]:
    """Exact provider totals without fetching full PR records or catalog rows."""

    owner, name = REPOSITORY.split("/", 1)
    query = """query($owner:String!,$name:String!) {
      repository(owner:$owner,name:$name) {
        all:pullRequests(first:1) { totalCount }
        open:pullRequests(first:1,states:OPEN) { totalCount }
        closed:pullRequests(first:1,states:[CLOSED,MERGED]) { totalCount }
      }
    }"""
    response = _gh_json(
        "graphql", "-f", f"query={query}", "-f", f"owner={owner}", "-f", f"name={name}"
    )
    assert not response.get("errors"), response
    repository = response["data"]["repository"]
    counts = {state: repository[state]["totalCount"] for state in ("all", "open", "closed")}
    assert all(type(count) is int and count >= 0 for count in counts.values()), counts
    return counts


def test_live_list_of_pull_requests(tmp_path: Path) -> None:
    """Bounded cache windows, exact totals, Open default, and offline catalog reads."""

    require_admitted_git()
    _require_signed_in_gh()
    home = tmp_path / "home"
    route = "/api/plugin/github/pulls"
    window_route = f"{route}?state=all&limit=100"
    # Resolve the explicit repository URL before observing HTTP-route behavior. Cold
    # acquisition performs its separate provider repository-size admission check.
    acquired = _run(home, REPO_URL, "--no-serve")
    assert acquired.returncode == 0, (acquired.stdout, acquired.stderr)
    offline = _no_gh_path(tmp_path)
    called = tmp_path / "no-gh" / "gh.called"
    # Observe calls as well as refusing them: silently falling back after consulting gh
    # must not make a cache-only read look correct.
    (tmp_path / "no-gh" / "gh").write_text(
        '#!/bin/sh\nprintf "called\\n" >> "$0.called"\nexit 1\n', encoding="utf-8"
    )
    absent = _envelope(_run(home, REPO_URL, "--api", route, path=offline))
    assert (absent["state"], absent["reason"], absent["list"]) == ("absent", "not_cached", "open")
    assert absent["rows"] == [] and absent["catalog_fetched"] == 0
    assert absent["total"] is None and absent["repository_total"] is None
    assert not called.exists(), "an uncached GET consulted gh"

    before = _github_pull_counts()
    body = tmp_path / "refresh.json"
    body.write_text('{"state": "all", "target": 500}\n', encoding="utf-8")
    refreshed = _run(home, REPO_URL, "--api", f"{route}-refresh", "--data", str(body))
    assert refreshed.returncode == 0, (refreshed.stdout, refreshed.stderr)

    listed = _envelope(_run(home, REPO_URL, "--api", window_route, path=offline))
    opened = _envelope(_run(home, REPO_URL, "--api", route, path=offline))
    # A closed window includes merged PRs. An explicit numeric cursor keeps this fork
    # fixture reachable even after it falls outside the newest100 metadata rows.
    closed_route = f"{route}?state=closed&after={MERGED_FROM_FORK + 1}&limit=1"
    closed = _envelope(_run(home, REPO_URL, "--api", closed_route, path=offline))
    after = _github_pull_counts()
    assert listed["state"] == "current" and listed["list"] == "all"
    assert listed["reader"].startswith("gh:")
    assert listed["complete"] is True and listed["refreshing"] is False
    assert listed["count_at"] and listed["generation"]
    assert listed["total"] == listed["repository_total"]
    assert listed["fetched"] == listed["catalog_fetched"]
    assert len(listed["rows"]) == min(100, listed["fetched"])
    assert listed["limit"] == 100
    assert opened["list"] == "open" and all(row["state"] == "open" for row in opened["rows"])
    assert closed["list"] == "closed"
    assert opened["repository_total"] == closed["repository_total"] == listed["repository_total"]
    assert opened["total"] + closed["total"] == listed["repository_total"]
    for state, envelope in (("all", listed), ("open", opened), ("closed", closed)):
        # Public PRs can open or close between commands. Bracket the independent exact
        # count instead of treating two different provider snapshots as one transaction.
        assert (
            min(before[state], after[state])
            <= envelope["total"]
            <= max(before[state], after[state])
        ), (state, before, envelope["total"], after)

    github = _gh_json(
        f"repos/{REPOSITORY}/pulls?state=all&sort=created&direction=desc&per_page=100"
    )
    actual = [row["number"] for row in listed["rows"]]
    expected = [item["number"] for item in github]
    assert actual == sorted(set(actual), reverse=True)
    lower, upper = max(min(actual), min(expected)), min(max(actual), max(expected))
    shared = [number for number in expected if lower <= number <= upper]
    assert len(shared) >= min(50, len(expected)), "the live windows moved too far apart to compare"
    assert [number for number in actual if lower <= number <= upper] == shared
    assert closed["rows"][0]["number"] == MERGED_FROM_FORK
    merged = closed["rows"][0]
    assert merged["merged"] is True and merged["state"] == "closed"
    assert merged["head_repository"] != REPOSITORY

    again = _envelope(_run(home, REPO_URL, "--api", window_route, path=offline))
    assert again["rows"] == listed["rows"] and again["generation"] == listed["generation"]
    assert again["catalog_fetched"] == listed["catalog_fetched"]
    assert not called.exists(), "a cached catalog GET consulted gh"
