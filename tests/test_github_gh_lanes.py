"""Every ``gh`` call records the lane its work serves, set where the work starts (mb-6719).

``builtin_plugins/github/gh_lanes.py`` defines the four lanes and what each holds. Here each
kind of work the plugin starts is asked for through the route a page asks it by, against the
stand-in's fake ``gh`` (``tests/github_browsing.py``), and every call it made is read back
from the event log with the key the stand-in answered it by. Each step says, for each kind of
call it should make, the lane that call must record, so a call in the wrong lane fails, and
so does a kind the step no longer makes or a call no kind names.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from metabrowser.builtin_plugins.github.gh_lanes import LANES
from metabrowser.builtin_plugins.github.pull_list_probe import LIST_PROBE_S
from metabrowser.builtin_plugins.github.served_pull import FULL_REFRESH_S
from tests.github_browsing import Browsing, browsing
from tests.github_pull_fixture import (
    Origin,
    catalog_entries,
    graph_core_data,
    list_page,
    ok,
    pull_bodies,
    scenario,
)
from tests.required_tools import needs_git

pytestmark = [
    needs_git,
    pytest.mark.skipif(os.name != "posix", reason="the fake gh is a POSIX script"),
]

PULLS = "/api/plugin/github/pulls"
PULLS_REFRESH = "/api/plugin/github/pulls-refresh"
PULL_REFRESH = "/api/plugin/github/pull-refresh"
PREFETCH = "/api/plugin/github/pulls-prefetch"
CORES = "/api/plugin/github/pull-cores-prepare"
STACKS_REFRESH = "/api/plugin/github/stacks-refresh"
LABELS_REFRESH = "/api/plugin/github/labels-refresh"
SOURCE_REFRESH = "/api/source/refresh"
STACKS = "repos/octo/demo/stacks?per_page=100&page=1"
# The pull request a push moves, which the list's probe then finds.
PUSHED = 105

# Kinds of call, by the key the stand-in answers them by.
ACCOUNT = r"user"
LIST_PROBE = r"repos/octo/demo/issues\?state=all&sort=updated.*"
PREFIX = r"graphql:(open|activity):.*"
BACKFILL = r"graphql:all:.*"
DELTA = r"graphql:updated:.*"
STATUS_SCAN = r"graphql:statuses:.*"
CORE_BATCH = r"graphql:visible-cores:.*"


def _record_of(number: int) -> dict[str, str]:
    """A full read of pull request *number*: the pull, its parts, and its status after it."""

    return {
        rf"repos/octo/demo/pulls/{number}": "record",
        rf"repos/octo/demo/(issues|pulls)/{number}/(comments|reviews)\?.*": "record",
        rf"graphql:status:{number}:.*": "record",
    }


def _expect(session: Browsing, kinds: Mapping[str, str]) -> None:
    """Each call the last step made is of one of *kinds*, a pattern of the key the stand-in
    answered it by, and records that kind's lane; and each kind was made at least once."""

    calls = session.calls()
    assert calls, "the step asked gh nothing"
    seen: set[str] = set()
    for call in calls:
        assert call.key is not None, call.record
        kind = next((pattern for pattern in kinds if re.fullmatch(pattern, call.key)), None)
        assert kind is not None, f"{call.key} is of no kind this step names"
        assert call.lane == kinds[kind], f"{call.key} ({call.owner}) served {call.lane}"
        seen.add(kind)
    assert seen == set(kinds), f"no call of {sorted(set(kinds) - seen)}"


def _ask(session: Browsing, route: str, body: Mapping[str, Any]) -> dict[str, Any]:
    response = session.post(route, body)
    assert response.status_code in (200, 202), response.text
    session.settle()
    return response.json()


def _answers(origin: Origin) -> dict[str, Any]:
    answers = scenario(origin)
    bodies = pull_bodies(origin)
    for number in (7, 10):
        data = graph_core_data(bodies[number]["pull"])
        data["repository"]["p0"] = data["repository"].pop("pull")
        key = f"graphql:visible-cores:{number}"
        answers["api"][key] = ok(key, {"data": data})
    stack = {
        "number": 70,
        "url": "https://api.github.com/repos/octo/demo/stacks/70",
        "base": {"ref": "topic"},
        "open": True,
        "pull_requests": [{"number": 7}, {"number": 10}],
    }
    answers["api"][STACKS] = ok(STACKS, [stack])
    answers["stack_version"] = "0.1.0"
    return answers


def test_each_kind_of_work_records_the_lane_it_serves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    record = dict.fromkeys(_record_of(7), "visible")
    answers = _answers(pull_origin)
    with browsing(tmp_path, monkeypatch, pull_origin, answers, attend=8) as session:
        # The Pulls tab's first ask: its filter's first page is the reader's, and the
        # backfill past it, in the same job, the background's.
        _ask(session, PULLS_REFRESH, {"state": "open", "target": 20})
        _expect(session, {ACCOUNT: "visible", PREFIX: "visible", BACKFILL: "background"})

        # The next ask probes the list it shows, and starts the scan of every open pull
        # request's status, which reads on its own clock.
        scan = _ask(session, PULLS_REFRESH, {"state": "open", "target": 20, "background": True})
        assert scan["status_scan"] == "started"
        _expect(session, {LIST_PROBE: "visible", STATUS_SCAN: "background"})

        # The catalog's delta scan, due by age, is the clock's: the job it starts is.
        session.clock.advance(FULL_REFRESH_S + 1)
        _ask(session, PULLS_REFRESH, {"state": "open", "target": 20, "background": True})
        _expect(session, {ACCOUNT: "background", DELTA: "background"})

        # A reader's Refresh reads the delta scan and the statuses for the tab.
        _ask(session, PULLS_REFRESH, {"state": "open", "target": 20, "retry": True})
        _expect(session, {ACCOUNT: "visible", DELTA: "visible", STATUS_SCAN: "visible"})

        # The rows on screen have their cores read; the walk past them is the background's.
        window = session.get(PULLS, state="open", limit="20").json()
        for number, batch in ((7, "visible"), (10, "background")):
            answer = _ask(
                session,
                CORES,
                {
                    "state": "open",
                    "window": {"id": f"rows-{number}", "generation": window["generation"]},
                    "numbers": [number],
                    "lane": batch,
                },
            )
            assert answer["preparation"] == "started", answer
            _expect(session, {CORE_BATCH: batch})
            _ask(
                session,
                CORES,
                {
                    "state": "open",
                    "window": {"id": f"rows-{number}", "generation": window["generation"]},
                    "numbers": [],
                    "lane": batch,
                },
            )

        # A pull request page's Fetch reads its record and status for the page.
        _ask(session, PULL_REFRESH, {"number": 7, "retry": True})
        _expect(session, {ACCOUNT: "visible", **record})

        # The page's own ask probes its pull request, and keeps the list behind it probed,
        # which no page shows.
        session.clock.advance(FULL_REFRESH_S / 2)
        _ask(session, PULL_REFRESH, {"number": 7})
        _expect(
            session,
            {
                r"repos/octo/demo/issues/7": "visible",
                r"repos/octo/demo/commits/[0-9a-f]+/(status|check-runs)\?.*": "visible",
                ACCOUNT: "visible",
                r"graphql:status:7:.*": "visible",
                LIST_PROBE: "attended",
            },
        )

        # The page's own ask for its list names the attended lane, and its probe serves it;
        # so does the delta scan a push the probe finds asks for.
        session.clock.advance(LIST_PROBE_S)
        _ask(session, PULLS_REFRESH, {"background": True, "lane": "attended"})
        _expect(session, {LIST_PROBE: "attended"})
        session.clock.advance(LIST_PROBE_S)
        items = [
            *answers["api"][list_page("all")]["body"],
            *answers["api"][list_page("all", 2)]["body"],
        ]
        pushed = [
            {**item, "updated_at": f"{session.clock.now():%Y-%m-%dT%H:%M:%SZ}"}
            if item["number"] == PUSHED
            else item
            for item in items
        ]
        catalog = {
            key: entry
            for key, entry in catalog_entries(pushed).items()
            if not key.startswith("graphql:statuses:")
        }
        session.answer({**answers, "api": {**answers["api"], **catalog}})
        _ask(session, PULLS_REFRESH, {"background": True, "lane": "attended"})
        _expect(session, {LIST_PROBE: "attended", ACCOUNT: "attended", DELTA: "attended"})
        session.answer(answers)

        # The source's refresh reads the attended pull request, which no page shows.
        _ask(session, SOURCE_REFRESH, {})
        _expect(session, {ACCOUNT: "attended", **dict.fromkeys(_record_of(8), "attended")})

        # The prefetch reads what the reader may open next.
        _ask(session, PREFETCH, {"records": [9], "files": [], "changed": False})
        _expect(
            session,
            {
                ACCOUNT: "prefetch",
                r"repos/octo/demo/pulls/9": "prefetch",
                r"repos/octo/demo/(issues|pulls)/9/(comments|reviews)\?.*": "prefetch",
            },
        )

        # A page's stacks and its label colors are the page's.
        _ask(session, STACKS_REFRESH, {})
        _expect(session, {r"stack": "visible", ACCOUNT: "visible", re.escape(STACKS): "visible"})
        _ask(session, LABELS_REFRESH, {})
        _expect(session, {ACCOUNT: "visible", r"repos/octo/demo/labels\?.*": "visible"})

        # Every lane recorded, and the report's lanes count each call once.
        report = session.report()
    assert all(report["lanes"][name]["requests"] for name in LANES), report["lanes"]
    assert report["lanes"]["unknown"]["requests"] == 0
    assert (
        sum(row["requests"] for row in report["lanes"].values()) == (report["requests"]["requests"])
    )
