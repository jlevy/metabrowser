"""A native stack's combined change through the CLI: cache-only, then summed in the store.

``GET /api/plugin/github/stack-change`` is the route the Pulls tab's stack heading reads its
brief change line from (mb-9ekj). This drives it the way a reader's server is driven, through
``metab --api``: before any snapshot, with a snapshot of two stacks, after one stack's top's
record is fetched, and for a stack whose top's record is not. Stack #70 is the stand-in's
pull requests 8, merged, and 10, a draft on the base branch after 8 was merged into it. Its
change runs from where 10's head meets the base branch the store mirrors, ``topic``, to that
head, which is what ``git diff topic...10-head`` lists in the stand-in: 10's own
``docs/draft.md``, one line. Neither ``README.md``, which the base branch changed after 8's
base, nor 8's merged ``docs/guide.md`` is the stack's to change (review of #484, A1); 8's
record is not needed, and is never fetched.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from metabrowser.builtin_plugins.github import pull_list
from metabrowser.cache.urls import GitSource
from tests.github_pull_fixture import (
    CANONICAL,
    DEFAULT_BRANCH,
    FETCHED_AT,
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
            assert [call for call in calls if "--jq .size" not in call] == [], (
                "a stack change asked GitHub"
            )
        blocks.append(result.block(" ".join(quoted(arg) for arg in shown), gh=calls))
        return result

    def change(query: str) -> dict[str, Any]:
        result = run(CANONICAL, "--api", f"{ROUTE}?{query}")
        return result.payload()

    blocks.append("## No snapshot yet: no stack has a change, and nothing asks GitHub.\n")
    assert change("number=70")["reason"] == "not_stacked"
    blocks.append("## With the snapshot, a stack whose ends are not fetched has no change.\n")
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
    blocks.append(
        "## Its top's record fetched, the stack's change is summed in the store: the top's head"
        " against the base branch, from where they meet.\n"
    )
    assert run(f"{CANONICAL}/pull/10", "--no-serve", gh_free=False).exit_code == 0
    summed = change("number=70")
    assert summed["state"] == "current"
    assert (summed["bottom"], summed["top"]) == (8, 10)
    assert summed["head"] == pull_origin["draft_head"]
    # Where 10's head meets the base branch: the base branch's own tip, 8's merge.
    assert summed["base"] == pull_origin["topic"]
    assert (summed["files"], summed["additions"], summed["deletions"]) == (1, 1, 0)
    assert summed["statuses"] == [{"status": "added", "count": 1}]
    blocks.append("## A stack of one pull request whose top's record is not fetched has none.\n")
    assert change("number=90")["reason"] == "not_cached"
    blocks.append("## A request that names anything but the stack's number is refused.\n")
    refused = run(CANONICAL, "--api", f"{ROUTE}?number=70&left=main")
    assert "status: 400" in refused.stdout
    rendered = label_home(Labels().apply("".join(blocks)), home)
    assert str(tmp_path) not in rendered and "file://" not in rendered
    check_golden("cli-github-stack-change.txt", rendered)
    assert json.loads(json.dumps(summed)) == summed
