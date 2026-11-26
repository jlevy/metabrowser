"""Every open pull request's status and verdict, through the CLI (mb-0vb0).

``GET /api/plugin/github/pull-statuses`` is the route the Pulls tab's readiness column reads,
and ``POST pulls-refresh`` the ask that starts the scan it answers from
(:mod:`metabrowser.builtin_plugins.github.pull_status_scan`). This drives both the way a
reader's server is driven, through ``metab --api``, with the substitutions of
``tests/test_cli_github_pulls_golden.py``: the stand-in origin for
``https://github.com/octo/demo``, a fake ``gh`` that replays the catalog's pages and the
scan's and logs every call, listed after each command, and a clock that moves only where a
block says.

The fixture's open pull requests are one for each verdict the derivation gives
(:func:`~metabrowser.builtin_plugins.github.pull_readiness.readiness`), each kept by the
scan's own writer from GitHub's answer, and one whose head the catalog has not seen. The
first scan finds GitHub still computing one answer; the ask after ``MERGEABLE_SETTLE_S``
reads that page once more. A scan GitHub refuses keeps every status, and says so, and a pull
request GitHub no longer lists among the open ones has no verdict from an older scan once
a walk has not read it.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from metabrowser.builtin_plugins.github import gh_budget, pull_list, pulls
from metabrowser.builtin_plugins.github.pull_status_scan import SCAN_POINT_GAP_S
from metabrowser.builtin_plugins.github.served_pull import MERGEABLE_SETTLE_S
from metabrowser.cache.urls import GitSource
from metabrowser.mirror_refresh import FRESHNESS_WINDOW_S
from tests.github_pull_fixture import (
    CANONICAL,
    FETCHED_AT,
    FIRST_CLONE_GH_CALLS,
    Origin,
    account,
    catalog_entries,
    generated_item,
    in_a_stable_order,
    install_fake_gh,
    logged_gh_calls,
    ok,
    scan_node,
    statuses_entries,
)
from tests.golden_harness import (
    Invocation,
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

ROUTE = "/api/plugin/github/pull-statuses"
REFRESH = "/api/plugin/github/pulls-refresh"
_PASSING = {"state": "SUCCESS", "count": 2}


def _rollup(state: str, *runs: dict[str, Any]) -> dict[str, Any]:
    return {
        "state": state,
        "contexts": {"checkRunCountsByState": list(runs), "statusContextCountsByState": []},
    }


_QUEUE = {"position": 1, "enqueuedAt": "2026-09-17T11:50:00Z", "estimatedTimeToMerge": 600}
# One open pull request for each verdict, by what GitHub answers for it; 112 is still being
# computed when first asked.
VERDICTS: dict[int, tuple[str, dict[str, Any], dict[str, Any] | None]] = {
    101: ("ready", {}, _rollup("SUCCESS", _PASSING)),
    102: ("ready_for_review", {}, _rollup("SUCCESS", _PASSING)),
    103: (
        "conflicts",
        {"mergeable": "CONFLICTING", "mergeStateStatus": "DIRTY"},
        _rollup("SUCCESS", _PASSING),
    ),
    104: (
        "checks_failing",
        {"mergeStateStatus": "UNSTABLE"},
        _rollup("FAILURE", _PASSING, {"state": "FAILURE", "count": 1}),
    ),
    105: (
        "changes_requested",
        {"mergeStateStatus": "BLOCKED", "reviewDecision": "CHANGES_REQUESTED"},
        _rollup("SUCCESS", _PASSING),
    ),
    106: ("blocked", {"mergeStateStatus": "BLOCKED"}, _rollup("SUCCESS", _PASSING)),
    107: (
        "queue_failing",
        {"isInMergeQueue": True, "mergeQueueEntry": {**_QUEUE, "state": "UNMERGEABLE"}},
        _rollup("SUCCESS", _PASSING),
    ),
    108: (
        "queued",
        {"isInMergeQueue": True, "mergeQueueEntry": {**_QUEUE, "state": "QUEUED"}},
        _rollup("SUCCESS", _PASSING),
    ),
    109: (
        "checks_pending",
        {"mergeStateStatus": "UNSTABLE"},
        _rollup("PENDING", _PASSING, {"state": "IN_PROGRESS", "count": 1}),
    ),
    110: (
        "review_required",
        {"mergeStateStatus": "BLOCKED", "reviewDecision": "REVIEW_REQUIRED"},
        None,
    ),
    111: ("behind", {"mergeStateStatus": "BEHIND"}, _rollup("SUCCESS", _PASSING)),
    112: (
        "checking",
        {"mergeable": "UNKNOWN", "mergeStateStatus": "UNKNOWN"},
        _rollup("SUCCESS", _PASSING),
    ),
}
DRAFT = 102
# A push the catalog has not read: the scan reports a head its row does not name.
PUSHED = 113
# A retarget the catalog has not read, as GitHub makes when the layer below in a stack
# merges: the scan reports the same head into a base its row does not name.
RETARGETED = 115
# Closed on GitHub after the scans read it, before the catalog's next scan.
GONE = 111
CLOSED = 114
NOT_LISTED = 999
PUSHED_HEAD = "f" * 40


def _items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for number in (*VERDICTS, PUSHED, RETARGETED, CLOSED):
        item = {**generated_item(number), "draft": number == DRAFT}
        if number == CLOSED:
            item.update(state="closed", closed_at="2026-09-17T11:00:00Z")
        items.append(item)
    return items


def _nodes(items: list[dict[str, Any]], *, settled: bool) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for item in items:
        number = item["number"]
        if item["state"] != "open":
            continue
        if number == PUSHED:
            pushed = {**item, "head": {**item["head"], "sha": PUSHED_HEAD}}
            nodes.append(scan_node(pushed, shape={}))
            continue
        if number == RETARGETED:
            retargeted = {**item, "base": {**item["base"], "ref": "layer-1"}}
            nodes.append(scan_node(retargeted, shape={}))
            continue
        _verdict, shape, rollup = VERDICTS[number]
        if settled and number == 112:
            shape = {}
        nodes.append(scan_node(item, rollup=rollup, shape=shape))
    return nodes


def _updated_at(items: list[dict[str, Any]]) -> dict[int, str]:
    return {item["number"]: item["updated_at"] for item in items}


def _answers(items: list[dict[str, Any]]) -> dict[str, Any]:
    first = statuses_entries(_nodes(items, settled=False), updated_at=_updated_at(items))
    settled = statuses_entries(_nodes(items, settled=True), updated_at=_updated_at(items))
    api = {**catalog_entries(items)}
    # Each scan page is answered in turn: GitHub computes the unknown answer after the first
    # ask, so a later read of the page has it.
    api.update({key: [entry, settled[key]] for key, entry in first.items()})
    return {"auth": account(), "api": api, "api_failure": None}


def _verdicts(result: Invocation) -> str:
    """Each row's state, reason, lifecycle, and verdict with its requirements, one a line,
    and how the last scan ended."""

    envelope = result.payload()
    lines = [f"scanning={json.dumps(envelope['scanning'])} scan={json.dumps(envelope['scan'])}"]
    for row in envelope["rows"]:
        readiness = row["readiness"]
        verdict = (
            "-"
            if readiness is None
            else f"{readiness['verdict']}/{readiness['tone']} "
            + ",".join(f"{part['kind']}:{part['status']}" for part in readiness["requirements"])
        )
        lines.append(
            f"#{row['number']} {row['state']} reason={row['reason'] or '-'} "
            f"lifecycle={row['lifecycle'] or '-'} observed_by="
            f"{row['status']['observed_by'] if row['status'] else '-'} verdict={verdict}"
        )
    header = result.stdout[: result.stdout.index("{")]
    return header + "\n".join(lines) + "\n"


def _asked(result: Invocation) -> str:
    """A list ask's answer: what it started for the list and for the statuses."""

    header = result.stdout[: result.stdout.index("{")]
    answer = json.loads(result.stdout[result.stdout.index("{") :].split("\nafter: ", 1)[0])
    return header + f"refresh={answer['refresh']} status_scan={answer['status_scan']}\n"


def test_golden_pull_statuses_scan_settle_and_refuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    home = isolate_cli(tmp_path, monkeypatch).home
    local = pull_origin.url

    def remote(source: GitSource) -> str:
        return local if source.normalized == CANONICAL else source.normalized

    monkeypatch.setattr("metabrowser.cache.acquire.remote_url_for", remote)
    clock = [FETCHED_AT]
    monkeypatch.setattr(pull_list, "utc_now", lambda: clock[0])
    monkeypatch.setattr(pulls, "utc_now", lambda: clock[0])
    gh_budget.forget()
    items = _items()
    answers = _answers(items)

    def answer(scenario: dict[str, Any]) -> None:
        for key, value in install_fake_gh(tmp_path, scenario).items():
            monkeypatch.setenv(key, value)

    answer(answers)
    blocks: list[str] = []

    def say(text: str) -> None:
        blocks.append(f"## {text}\n")

    def advance(seconds: float) -> None:
        clock[0] += timedelta(seconds=seconds)
        say(f"The clock moves on {seconds:g} s, to {clock[0]:%Y-%m-%dT%H:%M:%SZ}.")

    def run(*args: str, project: Callable[[Invocation], str] | None = None) -> Invocation:
        result = run_metab(args)
        assert result.exit_code == 0 or "status: 400" in result.stdout, result.stderr
        shown = (
            result
            if project is None
            else Invocation(result.exit_code, project(result), result.stderr)
        )
        calls = in_a_stable_order(logged_gh_calls(tmp_path))
        named = [arg.removeprefix(f"{tmp_path}/") for arg in args]
        blocks.append(shown.block(" ".join(quoted(arg) for arg in named), gh=calls))
        return result

    def statuses(numbers: tuple[int, ...], *, whole: bool = False) -> Invocation:
        query = ",".join(str(number) for number in numbers)
        result = run(
            CANONICAL, "--api", f"{ROUTE}?numbers={query}", project=None if whole else _verdicts
        )
        gh = blocks[-1].rsplit("--- gh ---\n", 1)[1].splitlines()
        assert gh in ([], FIRST_CLONE_GH_CALLS), "the route asked GitHub"
        return result

    def ask(body: dict[str, Any]) -> Invocation:
        request = tmp_path / "request.json"
        request.write_text(json.dumps(body) + "\n", encoding="utf-8")
        return run(CANONICAL, "--api", REFRESH, "--data", str(request), project=_asked)

    every = (*VERDICTS, PUSHED, CLOSED, RETARGETED, NOT_LISTED)
    say("Nothing is cached: no pull request named has a row or a status, and none asks GitHub.")
    nothing = statuses((101, NOT_LISTED), whole=True).payload()
    assert [row["reason"] for row in nothing["rows"]] == ["not_cached", "not_cached"]

    say(
        "The list's first ask reads the catalog. The scan waits for it: the ask found no "
        "catalog before the list's job started."
    )
    first = ask({})
    assert "status_scan=not_due" in blocks[-1] and "graphql statuses" not in blocks[-1]
    assert first.exit_code == 0

    advance(20)
    say(
        "The next ask probes the list, which is unchanged, and starts the first scan: one page "
        "of the newest open pull requests, one GraphQL point, with no account check."
    )
    ask({"background": True})
    assert blocks[-1].rsplit("--- gh ---\n", 1)[1].splitlines()[-1] == (
        "gh api graphql statuses cursor=start"
    )
    assert "status_scan=started" in blocks[-1]

    say(
        "One pull request for each verdict, judged on the lifecycle, head, and base of its "
        "catalog row; #112's mergeability GitHub had not finished computing. The scan lists "
        "no check."
    )
    scanned = statuses(every).payload()
    verdicts = {
        row["number"]: row["readiness"]["verdict"] for row in scanned["rows"] if row["readiness"]
    }
    assert verdicts == {number: verdict for number, (verdict, _, _) in VERDICTS.items()}
    reasons = {row["number"]: row["reason"] for row in scanned["rows"] if row["reason"]}
    assert reasons == {
        PUSHED: "other_head",
        RETARGETED: "other_base",
        CLOSED: "no_status",
        NOT_LISTED: "not_cached",
    }
    scan = scanned["scan"]
    assert (scan["trigger"], scan["pages"], scan["cost"], scan["unknown"]) == (
        "periodic",
        1,
        1,
        1,
    )
    assert (
        scan["settle_at"]
        == f"{clock[0] + timedelta(seconds=MERGEABLE_SETTLE_S):%Y-%m-%dT%H:%M:%SZ}"
    )
    say("The route's whole answer for one pull request with a status and one without.")
    whole = statuses((104, PUSHED), whole=True).payload()
    assert whole["rows"][0]["status"]["checks"]["listed_at"] is None

    advance(10)
    say("An ask inside the settle wait starts nothing: the scan's spacing holds it.")
    ask({"background": True})
    assert "status_scan=not_due" in blocks[-1]

    advance(MERGEABLE_SETTLE_S - 10)
    say(
        f"{MERGEABLE_SETTLE_S:g} s after the scan, the next ask reads the page that held the "
        "unknown answer once more, inside the spacing, and GitHub has it."
    )
    ask({"background": True})
    assert blocks[-1].rsplit("--- gh ---\n", 1)[1].splitlines()[-1] == (
        "gh api graphql statuses cursor=start"
    )
    settled = statuses((112,)).payload()
    assert settled["rows"][0]["readiness"]["verdict"] == "ready"
    assert (
        settled["scan"]["trigger"],
        settled["scan"]["unknown"],
        settled["scan"]["settle_at"],
    ) == (
        "settle",
        0,
        None,
    )

    advance(SCAN_POINT_GAP_S + 1)
    say("Once only: past the spacing, nothing is due until the periodic scan.")
    ask({"background": True})
    assert "status_scan=not_due" in blocks[-1]

    advance(60)
    refused = {
        **answers,
        "api": {
            **answers["api"],
            "graphql:statuses:start": ok(
                "graphql:statuses:start",
                {"errors": [{"type": "RESOURCE_LIMITS_EXCEEDED", "message": "too much"}]},
            ),
        },
    }
    answer(refused)
    say(
        "The periodic scan is due, and GitHub refuses its page. The list's answer stands, every "
        "status the scans kept is still answered, and the route says how the scan ended."
    )
    ask({"background": True})
    after = statuses((101, 112)).payload()
    assert after["scan"]["outcome"] == "gh_failed"
    assert [row["state"] for row in after["rows"]] == ["status", "status"]

    advance(FRESHNESS_WINDOW_S + 1)
    listed = [node for node in _nodes(items, settled=True) if node["number"] != GONE]
    rescanned = statuses_entries(listed, updated_at=_updated_at(items))
    answer({**answers, "api": {**answers["api"], **rescanned}})
    say(
        f"GitHub no longer lists #{GONE} among the open pull requests. The next periodic walk "
        "does not read it, so the status an older scan kept of it is not_scanned, with no "
        "verdict, while its catalog row is still open."
    )
    ask({"background": True})
    walked = statuses((GONE, 101)).payload()
    assert [(row["reason"], row["lifecycle"]) for row in walked["rows"]] == [
        ("not_scanned", "open"),
        (None, "open"),
    ]

    say("A request that names anything but the pull requests' numbers is refused.")
    bad = run(CANONICAL, "--api", f"{ROUTE}?numbers=101&extra=1")
    assert bad.exit_code != 0 and "status: 400" in bad.stdout

    rendered = label_home("".join(blocks), home)
    assert str(tmp_path) not in rendered and "file://" not in rendered
    check_golden("cli-github-pull-statuses.txt", rendered)
