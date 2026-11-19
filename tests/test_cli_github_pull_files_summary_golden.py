"""What each pull request's cached changed-files list sums to, through the CLI (mb-d0a3).

``GET /api/plugin/github/pull-files-summary`` is the route the brief change line under a Pulls
row reads. This drives it the way a reader's server is driven, through ``metab --api``, with
the substitutions of ``tests/test_cli_github_pull_files_golden.py``: the stand-in origin for
``https://github.com/octo/demo``, a fake ``gh`` that replays full-size pages of changed files
built on a scrubbed real item and logs every call, listed after each command, and a fixed
clock. Before any list is cached, every pull request named has none. After
``POST pull-files-refresh`` reads 106's from GitHub's three pages, the summary sums it by
GitHub's status words and in lines; after 7's record is fetched, its list is the local
comparison's, which names its head. The summary itself asks GitHub nothing at each step.
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from itertools import count
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from metabrowser.builtin_plugins.github import pull_files_refresh, pull_list, pulls
from metabrowser.cache.urls import GitSource
from tests.github_pull_fixture import (
    CANONICAL,
    FETCHED_AT,
    FIRST_CLONE_GH_CALLS,
    TREE_PULL,
    Origin,
    files_scenario,
    in_a_stable_order,
    install_fake_gh,
    logged_gh_calls,
)
from tests.golden_harness import (
    Invocation,
    Labels,
    check_golden,
    isolate_cli,
    label_home,
    quoted,
    run_metab,
)
from tests.required_tools import needs_git

pytestmark = [
    needs_git,
    pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only"),
]

ROUTE = "/api/plugin/github/pull-files-summary"
REFRESH = "/api/plugin/github/pull-files-refresh"


def _rows(result: Invocation) -> list[tuple[int, str, str | None, str | None]]:
    return [
        (row["number"], row["state"], row["reason"], row["listed_from"])
        for row in result.payload()["rows"]
    ]


def test_golden_pull_files_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    home = isolate_cli(tmp_path, monkeypatch).home
    local = pull_origin.url

    def remote(source: GitSource) -> str:
        return local if source.normalized == CANONICAL else source.normalized

    monkeypatch.setattr("metabrowser.cache.acquire.remote_url_for", remote)
    monkeypatch.setattr(pull_list, "utc_now", lambda: FETCHED_AT)
    monkeypatch.setattr(pulls, "utc_now", lambda: FETCHED_AT)
    generations = count(1)
    monkeypatch.setattr(pull_files_refresh, "uuid4", lambda: UUID(int=next(generations)))
    for key, value in install_fake_gh(tmp_path, files_scenario(pull_origin)).items():
        monkeypatch.setenv(key, value)
    blocks: list[str] = []

    def run(*args: str, gh_free: bool = True, **sections: Sequence[str]) -> Invocation:
        result = run_metab(args)
        shown = [arg.removeprefix(f"{tmp_path}/") for arg in args]
        calls = in_a_stable_order(logged_gh_calls(tmp_path))
        if gh_free:
            # A first command clones the mirror, which checks gh and asks GitHub the
            # repository's size.
            assert calls in ([], FIRST_CLONE_GH_CALLS), "a summary asked GitHub"
        blocks.append(result.block(" ".join(quoted(arg) for arg in shown), **sections, gh=calls))
        return result

    def summary(query: str) -> Invocation:
        return run(CANONICAL, "--api", f"{ROUTE}?{query}")

    def refresh(number: int) -> Invocation:
        request = tmp_path / "request.json"
        text = json.dumps({"number": number})
        request.write_text(text + "\n", encoding="utf-8")
        result = run(
            CANONICAL, "--api", REFRESH, "--data", str(request), gh_free=False, body=[text]
        )
        assert result.exit_code == 0, result.stdout + result.stderr
        return result

    blocks.append("## Nothing is cached: no pull request named has a list, and none asks GitHub.\n")
    assert _rows(summary(f"numbers={TREE_PULL},7")) == [
        (TREE_PULL, "absent", "not_cached", None),
        (7, "absent", "not_cached", None),
    ]
    blocks.append(f"## {TREE_PULL}'s list read from GitHub's pages, the one step here that asks.\n")
    refresh(TREE_PULL)
    blocks.append(
        f"## Summed from the cache: {TREE_PULL}'s files by GitHub's status words, and its lines;"
        " 7 has no list yet.\n"
    )
    summed = summary(f"numbers={TREE_PULL},7").payload()["rows"]
    assert [(row["number"], row["state"]) for row in summed] == [
        (TREE_PULL, "listed"),
        (7, "absent"),
    ]
    assert (summed[0]["files"], summed[0]["additions"], summed[0]["deletions"]) == (249, 1093, 493)
    assert summed[0]["generation"] == UUID(int=1).hex
    blocks.append(
        "## 7's record fetched, its list is the local comparison's, which names its head.\n"
    )
    assert run(f"{CANONICAL}/pull/7", "--no-serve", gh_free=False).exit_code == 0
    refresh(7)
    both = summary(f"numbers=7,{TREE_PULL}")
    assert _rows(both) == [
        (7, "listed", None, "comparison"),
        (TREE_PULL, "listed", None, "github"),
    ]
    local_row: dict[str, Any] = both.payload()["rows"][0]
    assert local_row["head"] == pull_origin["fork_head"]
    assert local_row["statuses"] == [
        {"status": "added", "count": 1},
        {"status": "modified", "count": 1},
    ]
    blocks.append("## A request that names anything but the pull requests' numbers is refused.\n")
    refused = summary(f"numbers={TREE_PULL}&extra=1")
    assert refused.exit_code != 0 and "status: 400" in refused.stdout
    rendered = label_home(Labels().apply("".join(blocks)), home)
    assert str(tmp_path) not in rendered and "file://" not in rendered
    check_golden("cli-github-pull-files-summary.txt", rendered)
