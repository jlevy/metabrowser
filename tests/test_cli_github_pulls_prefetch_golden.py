"""Golden CLI transcript: records checked against the catalog, and a prefetch that refreshes, skips, and defers.

Each command runs the production CLI in-process, as ``tests/test_cli_github_pull_golden.py``
does, with these substitutions and nothing else:

- ``metabrowser.cache.acquire.remote_url_for`` fetches ``https://github.com/octo/demo``,
  ``refs/pull/<n>/head`` included, from the local origin in ``tests/github_pull_fixture.py``;
- a fake ``gh`` first on ``PATH`` replays scrubbed real API responses, and logs every
  call, which the transcript lists after each command, so the requests each refresh made
  are its measured cost;
- one clock, fixed, which a block says where it moves, serves the records and the catalog;
- the rate-limit governor starts empty before each command, as a new process would, or,
  where a block says so, with what the process's speculative work spent earlier in the
  hour, as a server that has run a while has.

A pull envelope is printed as its freshness alone: ``state``, ``fetched_at``,
``verified_at``, ``verified_by``, ``head_moved``, and ``checks_pending``. The whole
envelope is in ``tests/golden/cli-github-pull.tryscript.md``.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from metabrowser.builtin_plugins.github import gh_budget, pull_list, pull_prefetch, pulls
from metabrowser.builtin_plugins.github.pull_catalog import read_catalog
from metabrowser.cache import pull_refs
from metabrowser.cache.urls import GitSource
from tests.github_pull_fixture import (
    CANONICAL,
    FETCHED_AT,
    LIST_PROBE_PATH,
    Origin,
    catalog_entries,
    generated_item,
    git_env,
    in_a_stable_order,
    install_fake_gh,
    list_item,
    logged_gh_calls,
    ok,
    page,
    pull_bodies,
    scenario,
)
from tests.golden_harness import (
    Invocation,
    Labels,
    check_golden,
    isolate_cli,
    label_home,
    mask_pushed_bytes,
    normalize_pull_comparison_scopes,
    origin_identity,
    quoted,
    run_metab,
)
from tests.required_tools import needs_git

pytestmark = [
    needs_git,
    pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only"),
]

PULL = "/api/plugin/github/pull"
PULLS_REFRESH = "/api/plugin/github/pulls-refresh"
PREFETCH = "/api/plugin/github/pulls-prefetch"
FRESHNESS = ("state", "fetched_at", "verified_at", "verified_by", "head_moved", "checks_pending")


def _stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


class _Session:
    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, origin: Origin) -> None:
        self.tmp_path = tmp_path
        self.monkeypatch = monkeypatch
        self.home = isolate_cli(tmp_path, monkeypatch).home
        self.origin = origin
        self.now = FETCHED_AT
        local = origin.url

        def remote_url_for(source: GitSource) -> str:
            return local if source.normalized == CANONICAL else source.normalized

        monkeypatch.setattr("metabrowser.cache.acquire.remote_url_for", remote_url_for)
        monkeypatch.setattr(pulls, "utc_now", lambda: self.now)
        monkeypatch.setattr(pull_list, "utc_now", lambda: self.now)
        self.blocks: list[str] = []
        # The catalog's epoch is minted at random; each one seen is labelled in order.
        self.labels = Labels()
        self.epochs: list[str] = []

    def answer(self, answers: dict[str, Any]) -> None:
        for name, value in install_fake_gh(self.tmp_path, answers).items():
            self.monkeypatch.setenv(name, value)

    def say(self, text: str) -> None:
        self.blocks.append(f"## {text}\n")

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)
        self.say(f"The clock moves on {seconds:g} s, to {_stamp(self.now)}.")

    def run(
        self,
        *args: str,
        body: dict[str, Any] | None = None,
        full: bool = False,
        spent: tuple[int, int] | None = None,
    ) -> Invocation:
        """Run one command; *spent* is what speculative work spent earlier in the hour, and
        how much of that was the cores walk's."""

        if body is not None:
            path = self.tmp_path / "request.json"
            path.write_text(json.dumps(body) + "\n", encoding="utf-8")
            args = (*args, "--data", str(path))
        # Each command is a new process: no budget spent, and no prefetch lane asked for.
        gh_budget.forget()
        pull_prefetch.forget_lanes()
        if spent is not None:
            spent_all, of_it_walk = spent
            with gh_budget.speculative(walk=True):
                gh_budget.spent(of_it_walk, now=self.now)
            with gh_budget.speculative():
                gh_budget.spent(spent_all - of_it_walk, now=self.now)
        result = run_metab(args)
        catalog = read_catalog(self.home, origin_identity(CANONICAL).slug)
        if catalog is not None and catalog.epoch not in self.epochs:
            self.epochs.append(catalog.epoch)
            self.labels.add(catalog.epoch, f"<CATALOG_EPOCH_{len(self.epochs)}>")
        shown = [arg.removeprefix(f"{self.tmp_path}/") for arg in args]
        stdout = result.stdout if full else _freshness(result.stdout)
        sections: dict[str, list[str]] = {"gh": in_a_stable_order(logged_gh_calls(self.tmp_path))}
        if body is not None:
            sections = {"body": [json.dumps(body)], **sections}
        self.blocks.append(
            replace(result, stdout=stdout).block(" ".join(quoted(arg) for arg in shown), **sections)
        )
        return result


def _freshness(stdout: str) -> str:
    """Each JSON answer in *stdout* with a pull envelope reduced to its freshness fields."""

    lines: list[str] = []
    decoder = json.JSONDecoder()
    rest = stdout
    while "{" in rest:
        head, _brace, _tail = rest.partition("{")
        start = len(head)
        payload, end = decoder.raw_decode(rest, start)
        lines.append(head)
        lines.append(json.dumps(_reduce(payload), indent=2) + "\n")
        rest = rest[end:].lstrip("\n")
    lines.append(rest)
    return "".join(lines)


def _reduce(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    if "record_revision" in payload:
        return {name: payload[name] for name in ("number", *FRESHNESS)}
    if "pull" in payload and isinstance(payload["pull"], dict):
        return {**payload, "pull": _reduce(payload["pull"])}
    if "pulls" in payload and isinstance(payload["pulls"], dict):
        pulls_envelope = payload["pulls"]
        return {
            **payload,
            "pulls": {name: pulls_envelope[name] for name in ("state", "fetched_at", "reader")},
        }
    if "list" in payload and "generation" in payload:
        return {name: payload[name] for name in ("state", "fetched_at", "reader", "last_refresh")}
    if "listed_from" in payload:
        return {
            name: payload[name]
            for name in ("number", "state", "listed_from", "head", "base_ref", "fetched")
        }
    return payload


def _catalog(origin: Origin, changes: dict[int, dict[str, Any]] | None = None) -> dict[str, Any]:
    """The catalog's GraphQL pages over pull requests 5 to 106, with *changes* applied."""

    known = {number: list_item(parts["pull"]) for number, parts in pull_bodies(origin).items()}
    items = [*(generated_item(number) for number in range(106, 10, -1))]
    items += [known[number] for number in (10, 9, 8, 7)]
    items += [generated_item(6), generated_item(5)]
    for item in items:
        change = dict((changes or {}).get(item["number"], {}))
        if "head_sha" in change:
            item["head"] = {**item["head"], "sha": change.pop("head_sha")}
        item.update(change)
    return catalog_entries(items)


def _with_catalog(answers: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    return {**answers, "api": {**answers["api"], **catalog}}


def _force_pushed(origin: Origin, answers: dict[str, Any], when: str) -> dict[str, Any]:
    """Pull request 7 force-pushed back to its earlier commit, with its CI settled there."""

    earlier = origin["fork_earlier"]
    body = copy.deepcopy(pull_bodies(origin)[7])
    body["pull"]["head"]["sha"] = earlier
    body["pull"]["updated_at"] = when
    base = "repos/octo/demo"
    runs = copy.deepcopy(body["check_runs"])
    for run in runs["check_runs"]:
        run.update(status="completed", conclusion=run["conclusion"] or "success", head_sha=earlier)
    entries = {
        f"{base}/pulls/7": body["pull"],
        page(f"{base}/commits/{earlier}/check-runs"): runs,
        page(f"{base}/commits/{earlier}/status"): body["status"],
    }
    api = {**answers["api"], **{path: ok(path, value) for path, value in entries.items()}}
    subprocess.run(
        ["git", "--git-dir", str(origin.path), "update-ref", "refs/pull/7/head", earlier],
        check=True,
        capture_output=True,
        env=git_env(origin.path.parent),
    )
    return {**answers, "api": api}


def _low_budget(answers: dict[str, Any], remaining: int) -> dict[str, Any]:
    """*answers* with every REST response reporting *remaining* of 5,000 core points."""

    api = {
        path: {
            **entry,
            "headers": {**entry.get("headers", {}), "X-Ratelimit-Remaining": str(remaining)},
        }
        if path.startswith("repos/")
        else entry
        for path, entry in answers["api"].items()
    }
    return {**answers, "api": api}


def test_golden_records_checked_against_the_catalog_and_a_budgeted_prefetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    session = _Session(tmp_path, monkeypatch, pull_origin)
    origin = session.origin
    online = _with_catalog(scenario(origin), _catalog(origin))
    session.answer(online)

    session.say(
        "Pull requests 7 and 8 are read, then the catalog. A record the catalog has not seen "
        "change is current; 7 is open, and its docs check is still running."
    )
    first = session.run(f"{CANONICAL}/pull/7", "--api", f"{PULL}?number=7")
    assert first.exit_code == 0, first.stderr
    assert first.payload()["checks_pending"] is True
    merged = session.run(CANONICAL, "--api", f"{PULL}-refresh", body={"number": 8, "retry": True})
    assert merged.exit_code == 0, merged.stderr
    scanned = session.run(CANONICAL, "--api", PULLS_REFRESH, body={})
    assert scanned.exit_code == 0, scanned.stderr

    session.advance(2 * 3600)
    delta = session.run(CANONICAL, "--api", PULLS_REFRESH, body={})
    assert delta.exit_code == 0, delta.stderr
    calls = session.blocks[-1].rsplit("--- gh ---\n", 1)[1].splitlines()
    # One scan of what changed: one account check and one GraphQL page.
    assert calls == ["gh api user", "gh api graphql catalog state=updated cursor=start"]
    vouched = session.run(CANONICAL, "--api", f"{PULL}?number=8").payload()
    assert (vouched["state"], vouched["verified_by"], vouched["verified_at"]) == (
        "current",
        "catalog",
        _stamp(session.now),
    )
    session.say(
        "The catalog vouches for open 7's conversation and head, not for its checks, statuses, "
        "or mergeability, which do not move `updated_at`: read two hours ago, it is stale."
    )
    pending = session.run(CANONICAL, "--api", f"{PULL}?number=7").payload()
    assert (pending["state"], pending["checks_pending"], pending["verified_by"]) == (
        "stale",
        True,
        "catalog",
    )

    session.say(
        "A visible page asks for 7, 8, and 10 and for 8's changed files. The store gives 8's "
        "list from its record's comparison, with no request to GitHub, so it goes first; then "
        "the records: only 7's checks are due, which its own page reads; 8 is current; 10 has "
        "no record, so it is read."
    )
    prefetch = session.run(
        CANONICAL, "--api", PREFETCH, body={"records": [7, 8, 10], "files": [8]}, full=True
    )
    assert prefetch.exit_code == 0, prefetch.stderr
    report = json.loads(prefetch.stdout[prefetch.stdout.rindex("status: 200\n{") + 12 :])
    assert [(entry["kind"], entry["number"], entry["outcome"]) for entry in report["recent"]] == [
        ("files", 8, "refreshed"),
        ("record", 7, "skipped:checks"),
        ("record", 8, "skipped:current"),
        ("record", 10, "refreshed"),
    ]
    assert (report["records"]["hour_used"], report["files"]["hour_used"]) == (1, 0)
    # The price the reserve counts a record at is what 10's read spent: the pull and five
    # parts, a page each (review A5 of #761). The page asked a moment ago, so the lane keeps
    # a scan's records from the cores walk.
    ceiling = report["governor"]["ceiling"]
    assert ceiling["speculative_hour_used"] == pull_prefetch.POINTS_PER_RECORD
    assert ceiling["prefetch_reserved"] == (
        pull_prefetch.RECORDS_PER_SCAN * pull_prefetch.POINTS_PER_RECORD
    )

    session.say(
        "7's page asks for its automatic refresh. Its checks alone are due, but its last full "
        "read was two hours ago, past FULL_REFRESH_S, and a visible page's record is read in "
        "full that often: every part is asked with its ETag, and GitHub answers 304 for all "
        "that did not change. A record read in full within that interval reads its checks alone. "
        "The same ask probes the repository's list, one read of the row updated last, "
        "as a visible Pulls tab's ask would."
    )
    checks = session.run(CANONICAL, "--api", f"{PULL}-refresh", body={"number": 7})
    assert checks.exit_code == 0, checks.stderr
    calls = session.blocks[-1].rsplit("--- gh ---\n", 1)[1].splitlines()
    assert f"gh api {LIST_PROBE_PATH}" in calls, calls
    api = [
        call for call in calls if call.startswith("gh api repos/") and LIST_PROBE_PATH not in call
    ]
    assert any("comments" in call for call in api), calls
    assert all(call.endswith("(If-None-Match)") for call in api), calls
    read = session.run(CANONICAL, "--api", f"{PULL}?number=7").payload()
    assert (read["state"], read["fetched_at"]) == ("current", _stamp(session.now))

    session.say(
        "Pull request 7 is force-pushed back to its earlier commit, where CI has finished. The "
        "next scan shows the row newer with another head: the record is stale and its head "
        "moved. A prefetch of 7 lists its files first, from the new head the row names against "
        "the mirror's base branch, then reads the record."
    )
    session.advance(61)
    pushed_at = _stamp(session.now - timedelta(seconds=30))
    earlier = origin["fork_earlier"]
    moved = _force_pushed(origin, online, pushed_at)
    moved = _with_catalog(
        moved, _catalog(origin, {7: {"updated_at": pushed_at, "head_sha": earlier}})
    )
    session.answer(moved)
    assert session.run(CANONICAL, "--api", PULLS_REFRESH, body={}).exit_code == 0
    stale = session.run(CANONICAL, "--api", f"{PULL}?number=7").payload()
    assert (stale["state"], stale["head_moved"]) == ("stale", True)
    refreshed = session.run(
        CANONICAL, "--api", PREFETCH, body={"records": [7], "files": [7]}, full=True
    )
    assert refreshed.exit_code == 0, refreshed.stderr
    after = session.run(CANONICAL, "--api", f"{PULL}?number=7").payload()
    assert (after["state"], after["verified_by"], after["head_moved"]) == (
        "current",
        "catalog",
        False,
    )
    files = session.run(CANONICAL, "--api", "/api/plugin/github/pull-files?number=7&limit=0")
    assert (files.payload()["state"], files.payload()["head"]) == ("current", earlier)

    session.say(
        "This server's cores walk has spent the whole of speculative work's share of the "
        "ceiling this hour, before any page asked for the prefetch, so the lane kept nothing "
        "back from it. The ceiling itself has two thirds left, which what is on screen keeps. "
        "A visible page asks for 9 and for 10's and 9's changed files. The record is refused "
        "at once with `self_ceiling`, and the lists go on: the store gives 10's, which costs "
        "GitHub nothing, and 9's, which GitHub would give, is refused when its turn comes. "
        "From this ask on, the lane keeps a scan's records from the walk."
    )
    share = (gh_budget.SPECULATIVE_CORE_PER_HOUR, gh_budget.SPECULATIVE_CORE_PER_HOUR)
    spent_share = session.run(
        CANONICAL,
        "--api",
        PREFETCH,
        body={"records": [9], "files": [10, 9]},
        full=True,
        spent=share,
    )
    assert spent_share.exit_code == 0, spent_share.stderr
    assert '"reason": "self_ceiling"' in spent_share.stdout
    report = json.loads(spent_share.stdout[spent_share.stdout.rindex("status: 200\n{") + 12 :])
    governor = report["governor"]
    assert (governor["admits"], governor["reason"]) == (False, "self_ceiling")
    ceiling = governor["ceiling"]
    assert ceiling["speculative_hour_used"] >= ceiling["speculative_per_hour"]
    assert (ceiling["walk_hour_used"], ceiling["prefetch_reserved"]) == (
        share[1],
        pull_prefetch.RECORDS_PER_SCAN * pull_prefetch.POINTS_PER_RECORD,
    )
    assert ceiling["hour_used"] < ceiling["per_hour"]
    assert [(entry["number"], entry["outcome"]) for entry in report["recent"]] == [
        (10, "refreshed"),
        (9, "deferred:self_ceiling"),
    ]
    assert not session.blocks[-1].rsplit("--- gh ---\n", 1)[1].strip()

    session.say(
        "Every REST answer now reports 1,000 of 5,000 core points left, below the 25% floor. "
        "Nothing was observed when the lane started, so 9 is read; its answers stop the lane "
        "before 106."
    )
    session.answer(_low_budget(moved, 1000))
    low = session.run(CANONICAL, "--api", PREFETCH, body={"records": [9, 106]}, full=True)
    assert low.exit_code == 0, low.stderr
    report = json.loads(low.stdout[low.stdout.rindex("status: 200\n{") + 12 :])
    assert [(entry["number"], entry["outcome"]) for entry in report["recent"]] == [
        (9, "refreshed"),
        (106, "deferred:below_floor"),
    ]
    assert report["governor"]["admits"] is False

    session.advance(5)
    session.say(
        "7 is retitled on GitHub while the budget is that low, and its page's automatic ask "
        "probes it. The probe's own answer shows the budget below the floor, and the change "
        "it found is read in full all the same: the floor stops the reads the clock asks "
        "for, not a change found on the page the reader is looking at."
    )
    pull_path = "repos/octo/demo/pulls/7"
    retitled = {
        **moved["api"][pull_path]["body"],
        "title": "Retitled below the floor",
        "updated_at": _stamp(session.now - timedelta(seconds=2)),
    }
    changed = {**moved, "api": {**moved["api"], pull_path: ok(pull_path, retitled)}}
    session.answer(_low_budget(changed, 1000))
    found = session.run(CANONICAL, "--api", f"{PULL}-refresh", body={"number": 7})
    assert found.exit_code == 0, found.stderr
    assert '"refresh": "started"' in found.stdout
    calls = session.blocks[-1].rsplit("--- gh ---\n", 1)[1].splitlines()
    # The list's probe runs beside the ask and is listed first; then the record's probe,
    # the whole record between its two account checks, and its status after it, which
    # the floor does not stop either.
    assert calls[0] == f"gh api {LIST_PROBE_PATH}", calls
    calls = calls[1:]
    assert calls[1] == "gh api user" and calls[-2] == "gh api user (If-None-Match)", calls
    assert calls[-1] == "gh api graphql status number=7 cursor=start", calls
    assert len(calls) == 10, calls
    reread = session.run(CANONICAL, "--api", f"{PULL}?number=7", full=True).payload()
    assert reread["record"]["pull"]["title"] == "Retitled below the floor"
    session.blocks.pop()

    session.say(
        "GitHub refuses the catalog's next scan with its rate limit exhausted. The hold it "
        "leaves beside the catalog defers any prefetch until it lifts, in this process or another."
    )
    limited_path = "graphql:updated:start"
    limited = {
        **moved,
        "api": {
            **moved["api"],
            limited_path: {
                "status": 403,
                "headers": {"X-Ratelimit-Remaining": "0", "X-Ratelimit-Reset": "1790181960"},
                "body": {"message": "API rate limit exceeded"},
            },
        },
    }
    session.answer(limited)
    session.advance(61)
    assert session.run(CANONICAL, "--api", PULLS_REFRESH, body={"retry": True}).exit_code == 1
    deferred = session.run(CANONICAL, "--api", PREFETCH, body={"records": [106]}, full=True)
    assert deferred.payload() == {"prefetch": "deferred", "queued": 0, "reason": "rate_hold"}
    assert not session.blocks[-1].rsplit("--- gh ---\n", 1)[1].strip()

    rendered = normalize_pull_comparison_scopes(
        label_home(session.labels.apply("".join(session.blocks)), session.home)
    )
    assert str(tmp_path) not in rendered and "file://" not in rendered
    check_golden("cli-github-pulls-prefetch.txt", rendered)


def test_golden_open_pull_requests_are_listed_from_one_head_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    session = _Session(tmp_path, monkeypatch, pull_origin)
    origin = session.origin
    # Merged 8 is still open in this catalog, as a catalog read before the merge is.
    stale = {8: {"state": "open", "merged_at": None, "closed_at": None}}
    session.answer(_with_catalog(scenario(origin), _catalog(origin, stale)))

    session.say(
        "The catalog is read. Each open pull request's row names its head and base branch, and "
        "none has a record, so none has a comparison. It still calls 8 open, merged since."
    )
    assert session.run(CANONICAL, "--api", PULLS_REFRESH, body={}).exit_code == 0

    fetches: list[list[str]] = []
    fetch = pull_refs.fetch_into_store

    async def counted(published: Any, specs: list[str], **options: Any) -> str | None:
        fetches.append(list(specs))
        return await fetch(published, specs, **options)

    monkeypatch.setattr(pull_refs, "fetch_into_store", counted)
    topic = "+refs/heads/topic:refs/remotes/origin/topic"

    session.say(
        "A visible page asks for open 10's changed files. Its head is on the mirrored `wip`, so "
        "the one fetch brings only its base branch, `topic`, as the origin has it now, and the "
        "list is the store's comparison of the head with it: no request goes to GitHub, and the "
        "hour's cap of lists is not charged."
    )
    first = session.run(CANONICAL, "--api", PREFETCH, body={"files": [10]}, full=True)
    assert first.exit_code == 0, first.stderr
    report = json.loads(first.stdout[first.stdout.rindex("status: 200\n{") + 12 :])
    assert [(entry["kind"], entry["number"], entry["outcome"]) for entry in report["recent"]] == [
        ("files", 10, "refreshed"),
    ]
    assert report["files"]["hour_used"] == 0
    assert not session.blocks[-1].rsplit("--- gh ---\n", 1)[1].strip()
    assert fetches == [[topic]]

    session.say(
        "It asks for open 7's too. 10's list is current, so it is left out; 7's head, from a "
        "fork, is not in the store, and one fetch brings it with its base branch."
    )
    fetches.clear()
    second = session.run(CANONICAL, "--api", PREFETCH, body={"files": [7, 10]}, full=True)
    report = json.loads(second.stdout[second.stdout.rindex("status: 200\n{") + 12 :])
    assert [(entry["kind"], entry["number"], entry["outcome"]) for entry in report["recent"]] == [
        ("files", 7, "refreshed"),
        ("files", 10, "skipped:not_due"),
    ]
    assert not session.blocks[-1].rsplit("--- gh ---\n", 1)[1].strip()
    assert fetches == [["+refs/pull/7/head:refs/pull/7/head", topic]]

    session.say(
        "Each list names the head and base branch it was listed for, which the row still names: "
        "current."
    )
    for number, head in ((7, origin["fork_head"]), (10, origin["draft_head"])):
        listed = session.run(
            CANONICAL, "--api", f"/api/plugin/github/pull-files?number={number}&limit=0"
        ).payload()
        assert (listed["state"], listed["listed_from"], listed["head"], listed["base_ref"]) == (
            "current",
            "comparison",
            head,
            "topic",
        )
        # Each refresh's generation is minted at random; the summary below names it.
        session.labels.add(listed["generation"], f"<GENERATION_{number}>")
    summary = session.run(
        CANONICAL, "--api", "/api/plugin/github/pull-files-summary?numbers=7,10", full=True
    )
    assert [row["state"] for row in summary.payload()["rows"]] == ["listed", "listed"]

    session.say(
        "It asks for 8's. `topic` already holds 8's head, so their merge base is the head and "
        "the store would list nothing. 8's list is asked of GitHub instead, which this "
        "stand-in does not answer."
    )
    fetches.clear()
    merged = session.run(CANONICAL, "--api", PREFETCH, body={"files": [8]}, full=True)
    report = json.loads(merged.stdout[merged.stdout.rindex("status: 200\n{") + 12 :])
    assert report["files"]["hour_used"] == 1
    # The price the reserve counts a list from GitHub at is what 8's spent: its one page
    # (review A5 of #761).
    assert (
        report["governor"]["ceiling"]["speculative_hour_used"]
        == pull_prefetch.POINTS_PER_FILES_LIST
    )
    assert fetches == [[topic]]
    listed = session.run(CANONICAL, "--api", "/api/plugin/github/pull-files?number=8&limit=0")
    assert listed.payload().get("listed_from") != "comparison"

    session.say("Asked again for 7 and 10, both lists are current: nothing is fetched or asked.")
    fetches.clear()
    again = session.run(CANONICAL, "--api", PREFETCH, body={"files": [7, 10]}, full=True)
    report = json.loads(again.stdout[again.stdout.rindex("status: 200\n{") + 12 :])
    assert [(entry["number"], entry["outcome"]) for entry in report["recent"]] == [
        (7, "skipped:not_due"),
        (10, "skipped:not_due"),
    ]
    assert not session.blocks[-1].rsplit("--- gh ---\n", 1)[1].strip()
    assert fetches == []

    rendered = normalize_pull_comparison_scopes(
        label_home(session.labels.apply("".join(session.blocks)), session.home)
    )
    assert str(tmp_path) not in rendered and "file://" not in rendered
    check_golden("cli-github-pulls-prefetch-local-lists.txt", mask_pushed_bytes(rendered))
