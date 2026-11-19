"""A native stack's combined change through the CLI: cache-only, its members accumulated.

``GET /api/plugin/github/stack-change`` is the route the Pulls tab's stack heading reads its
brief change line from (mb-9ekj). This drives it the way a reader's server is driven, through
``metab --api``: before any snapshot, with a snapshot of two stacks, with one member's list
of changed files fetched, with both, and for a stack whose member's list is not. Stack #70
is the stand-in's pull requests 8, merged, which edited ``docs/guide.md``, and 10, a draft
that adds ``docs/draft.md``. A stack is the accumulation of its pull requests, merged or not
(the owner's decision on review A of #484, A1), so its change is 8's and 10's own, each file
once and their lines summed: one file added and one modified, +3 −0. Each list is the one
its expanded row in the Pulls tab shows, listed from its local comparison.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from metabrowser.builtin_plugins.github import pull_files_refresh, pull_list
from metabrowser.cache.urls import GitSource
from tests.github_pull_fixture import (
    CANONICAL,
    DEFAULT_BRANCH,
    FETCHED_AT,
    FIRST_CLONE_GH_CALLS,
    Origin,
    in_a_stable_order,
    install_fake_gh,
    logged_gh_calls,
    ok,
    scenario,
)
from tests.golden_harness import Labels, check_golden, isolate_cli, label_home, quoted, run_metab
from tests.required_tools import needs_git

pytestmark = [
    needs_git,
    pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only"),
]

ROUTE = "/api/plugin/github/stack-change"
STACKS = "repos/octo/demo/stacks?per_page=100&page=1"


def _stack(number: int, pulls: list[int]) -> dict[str, Any]:
    return {
        "number": number,
        "url": f"https://api.github.com/repos/octo/demo/stacks/{number}",
        "base": {"ref": DEFAULT_BRANCH},
        "open": True,
        "pull_requests": [{"number": n} for n in pulls],
    }


def test_golden_stack_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    home = isolate_cli(tmp_path, monkeypatch).home
    local = pull_origin.url

    def remote(source: GitSource) -> str:
        return local if source.normalized == CANONICAL else source.normalized

    monkeypatch.setattr("metabrowser.cache.acquire.remote_url_for", remote)
    monkeypatch.setattr(pull_list, "utc_now", lambda: FETCHED_AT)
    monkeypatch.setattr("metabrowser.builtin_plugins.github.pulls.utc_now", lambda: FETCHED_AT)
    # Each list's refresh names its generation from a counter, so the transcript is stable.
    generations = iter(range(1, 100))
    monkeypatch.setattr(pull_files_refresh, "uuid4", lambda: UUID(int=next(generations)))
    answers = scenario(pull_origin)
    answers["stack_version"] = "0.1.0"
    answers["api"][STACKS] = ok(STACKS, [_stack(70, [8, 10]), _stack(90, [9])])
    for key, value in install_fake_gh(tmp_path, answers).items():
        monkeypatch.setenv(key, value)
    blocks: list[str] = []

    def run(*args: str, gh_free: bool = True) -> Any:
        result = run_metab(args)
        shown = [arg.removeprefix(f"{tmp_path}/") for arg in args]
        calls = in_a_stable_order(logged_gh_calls(tmp_path))
        if gh_free:
            # A first command clones the mirror, which checks gh and asks GitHub the
            # repository's size.
            assert calls in ([], FIRST_CLONE_GH_CALLS), "a stack change asked GitHub"
        blocks.append(result.block(" ".join(quoted(arg) for arg in shown), gh=calls))
        return result

    def change(query: str) -> dict[str, Any]:
        result = run(CANONICAL, "--api", f"{ROUTE}?{query}")
        return result.payload()

    blocks.append("## No snapshot yet: no stack has a change, and nothing asks GitHub.\n")
    assert change("number=70")["reason"] == "not_stacked"
    blocks.append(
        "## With the snapshot, a stack whose members' lists are not fetched has no change.\n"
    )
    request = tmp_path / "request.json"
    request.write_text("{}\n")
    run(
        CANONICAL,
        "--api",
        "/api/plugin/github/stacks-refresh",
        "--data",
        str(request),
        gh_free=False,
    )
    assert change("number=70")["reason"] == "not_cached"
    lists = tmp_path / "lists"
    lists.mkdir()

    def listed(number: int) -> None:
        """Fetch pull request *number*'s record, then its list of changed files from it."""

        assert run(f"{CANONICAL}/pull/{number}", "--no-serve", gh_free=False).exit_code == 0
        body = lists / f"files-{number}.json"
        body.write_text(json.dumps({"number": number}) + "\n")
        refresh = run(
            CANONICAL,
            "--api",
            "/api/plugin/github/pull-files-refresh",
            "--data",
            str(body),
            gh_free=False,
        )
        assert refresh.exit_code == 0

    blocks.append("## One member's list fetched, the stack's change is still not had.\n")
    listed(8)
    assert change("number=70")["reason"] == "not_cached"
    blocks.append(
        "## Both members' lists fetched, the stack's change is theirs accumulated: each file"
        " once, the lines summed.\n"
    )
    listed(10)
    summed = change("number=70")
    assert summed["state"] == "current"
    assert summed["pulls"] == [8, 10]
    assert (summed["files"], summed["additions"], summed["deletions"]) == (2, 3, 0)
    assert summed["statuses"] == [
        {"status": "added", "count": 1},
        {"status": "modified", "count": 1},
    ]
    blocks.append("## A stack of one pull request whose list is not fetched has none.\n")
    assert change("number=90")["reason"] == "not_cached"
    blocks.append("## A request that names anything but the stack's number is refused.\n")
    refused = run(CANONICAL, "--api", f"{ROUTE}?number=70&left=main")
    assert "status: 400" in refused.stdout
    rendered = label_home(Labels().apply("".join(blocks)), home)
    assert str(tmp_path) not in rendered and "file://" not in rendered
    check_golden("cli-github-stack-change.txt", rendered)
    assert json.loads(json.dumps(summed)) == summed
