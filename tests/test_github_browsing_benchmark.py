"""A scripted session of browsing pull requests, held to the plan's invariants (mb-ulvg).

``explorations/performance-loop/github_browsing.py`` is the session: open the Pulls tab
and at once its top pull request, switch to the closed pull requests and open one, come
back and scroll, open a prefetched pull request, and revisit the first. Here it runs
against the in-process stand-in (``tests/github_browsing.py``), whose fake ``gh`` answers
each kind of read after the time GitHub took to answer it in the session's live run
(:data:`LATENCY_MS`), and the request report over the session, read through its route, is
held to what the merge readiness plan's GitHub request performance work asks of browsing:

- **Visible work is not overtaken.** No call of a less urgent lane starts while a more
  urgent call asked before it still waits for a network slot (the report's ``order``).
- **What is in flight stays within its bounds**: the spans holding a network slot within
  ``MAX_CONCURRENT_REFRESHES``, and every span with a call in flight within
  :data:`SPANS_BOUND`.
- **Nothing is read twice in a window** but the account check, which every pull request's
  job asks before and after its reads (the report's ``repeats``), a finding for the tuning.
- **A revisit is answered from the cache**: the revisit's calls are all ``304``.
- **The session spends at most** :data:`SPEND_BOUND`, REST ``core`` and GraphQL points.

``tests/golden/github-browsing-benchmark.txt`` pins the report's summary of each lane and
of each burst of steps, so a read added or taken away moves it. What runs at once, and how
long anything waited, are timing and left out; the bounds above hold them.

The stand-in's two open pull requests with records, 10 and 7, are updated last, so they head
the Pulls tab as the rows a reader opens first.
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import re
import sys
import time
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any, Final

import pytest

from metabrowser.builtin_plugins.github.gh_lanes import LANES
from metabrowser.builtin_plugins.github.pull_catalog import MAX_CATALOG_MEMBERS, PAGE_SIZE
from metabrowser.builtin_plugins.github.pull_list_probe import LIST_PROBE_S
from metabrowser.builtin_plugins.github.pull_prefetch import POINTS_PER_RECORD
from metabrowser.builtin_plugins.github.pull_status_scan import MAX_SCAN_PAGES
from metabrowser.builtin_plugins.github.served_pull import FULL_REFRESH_S, MAX_PROBES_IN_FLIGHT
from metabrowser.mirror_refresh import FRESHNESS_WINDOW_S, MAX_CONCURRENT_REFRESHES
from tests.github_browsing import Browsing, browsing
from tests.github_pull_fixture import (
    READER,
    Origin,
    catalog_entries,
    generated_item,
    graph_core_data,
    list_page,
    ok,
    scenario,
)
from tests.golden_harness import check_golden
from tests.required_tools import needs_git

pytestmark = [
    needs_git,
    pytest.mark.skipif(os.name != "posix", reason="the fake gh is a POSIX script"),
]

ROOT: Final = Path(__file__).resolve().parents[1]
SESSION_SCRIPT: Final = ROOT / "explorations" / "performance-loop" / "github_browsing.py"
GOLDEN: Final = "github-browsing-benchmark.txt"
# How long GitHub took to answer each kind of read, in milliseconds, by the key the stand-in
# answers it by: the median of each kind in the session's live run against this repository
# on 2026-11-27 with gh 2.97.0 (run 4 of explorations/performance-loop/github-requests/,
# whose README tabulates them), and run 2's for a pull request's checks pages, which run 4
# did not probe. The status scan's first page is its own kind: GitHub took over four times
# as long for it as for a later one.
LATENCY_MS: Final = [
    (r"user", 216),
    (r"repos/octo/demo/issues\?.*", 342),
    (r"repos/octo/demo/issues/\d+", 295),
    (r"repos/octo/demo/commits/.*", 403),
    (r"repos/octo/demo/pulls/\d+", 368),
    (r"repos/octo/demo/(issues|pulls)/\d+/(comments|reviews)\?.*", 282),
    (r"graphql:status:.*", 669),
    (r"graphql:visible-cores:.*", 655),
    (r"graphql:(open|closed|activity|all|updated):.*", 645),
    (r"graphql:statuses:start", 2167),
    (r"graphql:statuses:.*", 479),
]
# The two open pull requests with records, updated last so they head the open list.
UPDATED_LAST: Final = {10: "2026-09-17T11:50:00Z", 7: "2026-09-17T11:40:00Z"}
# Closed pull requests the stand-in lists beside its own, updated before any of them, so the
# catalog's backfill reads pages while the top row's Fetch waits, as a real repository's
# hundreds do (this repository's took nine pages in the live run).
OLD_CLOSED: Final = range(107, 407)
# The stand-in's catalog: its 102 pull requests and those, read a page of PAGE_SIZE at a time.
CATALOG_ROWS: Final = 102 + len(OLD_CLOSED)
# Every span with a call in flight at once: those holding a network slot, the probes, the
# one job of the repository's prefetch lane, which holds none, and a catalog job before it
# takes its first slot, for its account check.
SPANS_BOUND: Final = MAX_CONCURRENT_REFRESHES + MAX_PROBES_IN_FLIGHT + 1 + 1
# What the session may spend, REST ``core`` calls and GraphQL points together: what each of
# its reads costs when every list fits one page, at the prices beside their constants. The
# process's first account check is unconditional (1); the catalog reads the open filter's
# first page and backfills every row, a point a page of PAGE_SIZE rows; three cores batches, a
# point each; the status scan's MAX_SCAN_PAGES pages, a point each; the two pull requests
# opened with Fetch, each in full and its status (POINTS_PER_RECORD and 1); the prefetched
# one, which reads no status (POINTS_PER_RECORD), and the status its page reads when shown
# (1); and the first answers of the list's probe and of the first pull request's, its issue
# (1 each), a draft with no checks to probe. Every other read is conditional and answered
# 304, so a paid read more than these crosses it.
SPEND_BOUND: Final = (
    1
    + (1 + math.ceil(CATALOG_ROWS / PAGE_SIZE))
    + 3
    + MAX_SCAN_PAGES
    + 2 * (POINTS_PER_RECORD + 1)
    + (POINTS_PER_RECORD + 1)
    + 2
)
# The fields of a report's row the golden keeps: what was asked and what it cost, which the
# session decides, and not how long it took or what ran beside it, which load moves.
KEPT: Final = (
    "requests",
    "commands",
    "statuses",
    "no_status",
    "core",
    "graphql_points",
    "share_304",
    "conditional",
    "cache_hits",
    "duplicates",
)


def _session_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("github_browsing_session", SESSION_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SESSION: Final = _session_module()


class _InProcess:
    """The session's driver for the in-process stand-in: a dwell lets every job end and then
    moves the session's clock on, so the dwell is the stand-in's as well as the reader's."""

    def __init__(self, served: Browsing) -> None:
        self.served = served

    def post(self, route: str, body: Mapping[str, Any]) -> Any:
        response = self.served.post(route, body)
        return SESSION.Answer(response.status_code, response.json())

    def get(self, route: str, params: Mapping[str, str]) -> Any:
        response = self.served.get(route, **params)
        return SESSION.Answer(response.status_code, response.json())

    def settle(self) -> None:
        self.served.settle()

    def dwell(self, seconds: float) -> None:
        self.served.settle()
        self.served.clock.advance(seconds)

    def pause(self, seconds: float) -> None:
        time.sleep(seconds)

    def now(self) -> float:
        return self.served.clock.event_time()

    def begin(self) -> float:
        # Every window the benchmark reads begins after a dwell, when nothing runs.
        return self.now()


def _answers(origin: Origin) -> dict[str, Any]:
    """The stand-in's answers, with 10 and 7 updated last, a cores batch for every one the
    session can ask (each screen's first two), and GitHub's latencies."""

    answers = scenario(origin)
    api = answers["api"]
    for number, when in UPDATED_LAST.items():
        path = f"repos/octo/demo/pulls/{number}"
        api[path] = ok(path, {**api[path]["body"], "updated_at": when})
    items = [
        {**item, "updated_at": UPDATED_LAST.get(item["number"], item["updated_at"])}
        for item in (*api[list_page("all")]["body"], *api[list_page("all", 2)]["body"])
    ]
    for number in OLD_CLOSED:
        when = (datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=number)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        closed = {"state": "closed", "created_at": when, "updated_at": when, "closed_at": when}
        items.append({**generated_item(number), **closed})
    assert len(items) == CATALOG_ROWS
    api.update(catalog_entries(items))
    pulls = {item["number"]: item for item in items} | {
        number: api[f"repos/octo/demo/pulls/{number}"]["body"] for number in UPDATED_LAST
    }
    rows = [
        item["number"]
        for item in sorted(
            (item for item in items if item["state"] == "open"),
            key=lambda item: (item["updated_at"], item["number"]),
            reverse=True,
        )
    ]
    batch = SESSION.CORE_BATCH
    for screen in range(0, len(rows), SESSION.SCREEN_ROWS):
        for start in (screen, screen + batch):
            numbers = rows[start : min(start + batch, screen + SESSION.SCREEN_ROWS)]
            if not numbers:
                continue
            repository: dict[str, Any] = {"id": "R_demo", "nameWithOwner": "octo/demo"}
            for index, number in enumerate(numbers):
                repository[f"p{index}"] = graph_core_data(pulls[number])["repository"]["pull"]
            key = "graphql:visible-cores:" + ",".join(map(str, numbers))
            body = {"data": {"viewer": {"login": READER}, "repository": repository}}
            api[key] = ok(key, body)
    answers["latency_ms"] = [list(each) for each in LATENCY_MS]
    return answers


def _row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {field: row[field] for field in KEPT}


def _bursts(served: Browsing, steps: list[Any]) -> list[tuple[str, dict[str, Any]]]:
    """Each burst of steps, those that follow one another with no dwell, with the report over
    it: a job one step starts can end in the next step of its burst, but not past a dwell."""

    groups: list[list[Any]] = []
    for step in steps:
        if groups and not step.dwelt:
            groups[-1].append(step)
        else:
            groups.append([step])
    ends = [group[0].started for group in groups[1:]] + [served.clock.event_time() + 1]
    return [
        (" / ".join(step.name for step in group), served.report(since=group[0].started, until=end))
        for group, end in zip(groups, ends, strict=True)
    ]


def test_the_scripted_session_holds_the_plans_invariants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    with browsing(tmp_path, monkeypatch, pull_origin, _answers(pull_origin)) as served:
        steps = SESSION.browse(_InProcess(served))
        report = served.report()
        bursts = _bursts(served, steps)
    notes = {step.name: dict(step.notes) for step in steps}
    # The session went as its story says.
    assert notes["open the Pulls tab"] == {"cores": "ready", "status_scan": "started"}
    assert notes["open the top row at once"]["refresh"] == "not_cached, then started"
    assert notes["switch to closed and open the first"]["refresh"] == "not_cached, then started"
    assert notes["come back to the open list and scroll"]["top"] == list(UPDATED_LAST)
    total = report["requests"]
    assert report["lanes"]["unknown"]["requests"] == 0
    assert all(report["lanes"][lane]["requests"] for lane in LANES), "a lane did no work"

    # Visible work is not overtaken: no less urgent call started while a more urgent one
    # asked before it waited for a slot.
    assert {
        (first, later): met["overtook"]
        for first, others in report["order"].items()
        for later, met in others.items()
        if met["overtook"]
    } == {}
    # What is in flight stays within its bounds.
    flight = report["in_flight"]
    assert flight["slotted_peak"] <= MAX_CONCURRENT_REFRESHES, flight
    assert flight["spans_peak"] <= SPANS_BOUND, flight
    # Nothing is read twice in a window but the account check.
    assert total["duplicates"]["in_flight"] == 0
    assert {repeat["asks"] for repeat in report["repeats"]} <= {"gh api user"}
    # A revisit is answered from the cache.
    revisit = bursts[-1][1]["requests"]
    assert set(revisit["statuses"]) <= {"304"} and revisit["core"] == revisit["graphql_points"] == 0
    assert revisit["no_status"] == {"failed": 0, "unread": 0, "unrecorded": 0}
    assert notes["revisit the first"] == {"number": 10, "refresh": "not_due"}
    # The session spends at most what its reads are priced at.
    assert total["core"] + total["graphql_points"] <= SPEND_BOUND

    summary = {
        "session": _row(total),
        "lanes": {lane: _row(row) for lane, row in report["lanes"].items() if lane != "unknown"},
        "repeats": [{**repeat, "fingerprint": "…"} for repeat in report["repeats"]],
        "bursts": [
            {"steps": name, **{lane: row["requests"] for lane, row in burst["lanes"].items()}}
            for name, burst in bursts
        ],
        "notes": notes,
    }
    check_golden(GOLDEN, json.dumps(summary, indent=2, ensure_ascii=False) + "\n")


def test_the_script_asks_as_the_pages_do_and_revisits_inside_the_windows() -> None:
    """The session's own sizes are the panel's and the server's; the revisit comes inside
    the first pull request's status window and its full read's from its Fetch, so a probe
    alone answers it; and each of the list's asks after the first two comes a probe's
    interval after the one before, so each probes."""

    panel = (ROOT / "src/metabrowser/builtin_plugins/github/pulls-panel.js").read_text("utf-8")
    shown = re.search(r"^export const DISPLAY_ROWS = (\d+);$", panel, re.MULTILINE)
    assert shown is not None and int(shown.group(1)) == SESSION.DISPLAY_ROWS
    batch = re.search(r"^const CORE_BATCH_SIZE = (\d+);$", panel, re.MULTILINE)
    assert batch is not None and int(batch.group(1)) == SESSION.CORE_BATCH == MAX_CATALOG_MEMBERS
    dwells = SESSION.DWELLS
    assert sum(dwells.values()) < min(FRESHNESS_WINDOW_S, FULL_REFRESH_S)
    assert min(dwells["switch to closed"], dwells["come back"]) > LIST_PROBE_S
