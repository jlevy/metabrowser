"""Golden CLI transcript: records checked against the catalog, and a prefetch that refreshes, skips, and defers.

Each command runs the production CLI in-process, as ``tests/test_cli_github_pull_golden.py``
does, with these substitutions and nothing else:

- ``metabrowser.cache.acquire.remote_url_for`` fetches ``https://github.com/octo/demo``,
  ``refs/pull/<n>/head`` included, from the local origin in ``tests/github_pull_fixture.py``;
- a fake ``gh`` first on ``PATH`` replays scrubbed real API responses, and logs every
  call, which the transcript lists after each command, so the requests each refresh made
  are its measured cost;
- one clock, fixed, which a block says where it moves, serves the records and the catalog;
- the rate-limit governor starts empty before each command, as a new process would.

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

from metabrowser.builtin_plugins.github import gh_budget, pull_list, pulls
from metabrowser.builtin_plugins.github.pull_catalog import read_catalog
from metabrowser.cache.urls import GitSource
from tests.github_pull_fixture import (
    CANONICAL,
    FETCHED_AT,
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

    def run(self, *args: str, body: dict[str, Any] | None = None, full: bool = False) -> Invocation:
        if body is not None:
            path = self.tmp_path / "request.json"
            path.write_text(json.dumps(body) + "\n", encoding="utf-8")
            args = (*args, "--data", str(path))
        gh_budget.forget()
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
        "change is current; 7's docs check is still running, so its checks keep its own age."
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
    assert calls == ["gh auth status", "gh api graphql catalog state=updated cursor=start"]
    vouched = session.run(CANONICAL, "--api", f"{PULL}?number=8").payload()
    assert (vouched["state"], vouched["verified_by"], vouched["verified_at"]) == (
        "current",
        "catalog",
        _stamp(session.now),
    )
    pending = session.run(CANONICAL, "--api", f"{PULL}?number=7").payload()
    assert (pending["state"], pending["checks_pending"], pending["verified_by"]) == (
        "stale",
        True,
        "fetch",
    )

    session.say(
        "A visible page asks for 7, 8, and 10 and for 8's changed files: 7 has pending checks, "
        "which its own page refreshes; 8 is current; 10 has no record, so it is read; 8's "
        "files come from the store's comparison, with no request to GitHub."
    )
    prefetch = session.run(
        CANONICAL, "--api", PREFETCH, body={"records": [7, 8, 10], "files": [8]}, full=True
    )
    assert prefetch.exit_code == 0, prefetch.stderr
    report = json.loads(prefetch.stdout[prefetch.stdout.rindex("status: 200\n{") + 12 :])
    assert [(entry["number"], entry["outcome"]) for entry in report["recent"]] == [
        (7, "skipped:unverified"),
        (8, "skipped:current"),
        (10, "refreshed"),
        (8, "refreshed"),
    ]
    assert (report["records"]["hour_used"], report["files"]["hour_used"]) == (1, 0)

    session.say(
        "Pull request 7 is force-pushed back to its earlier commit, where CI has finished. The "
        "next scan shows the row newer with another head: the record is stale and its head "
        "moved, and a prefetch of 7 reads it and lists its files from the new comparison."
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
