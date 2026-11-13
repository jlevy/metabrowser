"""A page holds one root-summary request at a time, however often it is asked.

Every root aggregate upsert, every tree load, and the recency menu ask the page for a
fresh ``/api/tree?depth=0``, and each answer costs the server a pass over the whole
index. A live tree upserts its root on every write, so the page sent a request per
ask: on a 303,000-file tree with writes every 250 ms, one WebKit page held up to ten of
them, five at the server at once, each answered in about 3.2 s, and the Commits tab
waited behind them; with four pages it never loaded
(``explorations/tree-summary-storm/README.md``).

``tests/dom/root-summary-refresh-session.js`` runs the shell's summary refresh, the
block of ``static/app.js`` from its introducing comment to the tree cache, verbatim
against ``static/navigation.js``, with only the clock, ``fetch``, and the document
doubled. ``tests/golden/cli-ui-root-summary-refresh.tryscript.md`` pins the whole
transcript; each test here holds one behavior of it, and fails when that behavior is
removed. Against the shell before this change the live-tree scenario sent 60 requests
in 30 s with seven in flight at once, and the hidden scenarios sent 20 each.

How many connections a browser opens to a host, and whether it sends identical
requests in parallel (WebKit) or one at a time behind its cache lock (Chrome), are the
browser's; the exploration records both.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from tests.golden_harness import run_session

LIVE = "a live tree upserts its root every 100 ms and each answer takes 3.2 s"
QUIET = "an isolated change on a quiet tree"
FAILING = "the server fails the first two requests"
HIDDEN = "a page that is hidden while its tree changes"
BEHIND = "a Files panel behind the Commits tab while its tree changes"
# The session's server answers each request in this long.
LIVE_SERVER_MS = 3200
QUIET_SERVER_MS = 300


@pytest.fixture(scope="module")
def scenarios() -> dict[str, list[dict[str, Any]]]:
    transcript = run_session("root-summary-refresh-session.js")
    return {scenario["scenario"]: scenario["steps"] for scenario in transcript}


def _sent_at(step: dict[str, Any]) -> list[int]:
    return [int(m.group(1)) for line in step["did"] if (m := re.match(r"t=(\d+) sent #", line))]


def _settled_at(step: dict[str, Any]) -> list[int]:
    return [
        int(m.group(1))
        for line in step["did"]
        if (m := re.match(r"t=(\d+) #\d+ (?:answered|failed)", line))
    ]


def test_the_session_runs_every_scenario(scenarios: dict[str, list[dict[str, Any]]]) -> None:
    assert list(scenarios) == [LIVE, QUIET, FAILING, HIDDEN, BEHIND]


def test_a_live_tree_holds_one_request_at_a_time(
    scenarios: dict[str, list[dict[str, Any]]],
) -> None:
    busy = scenarios[LIVE][0]
    assert busy["after"]["asks"] == 300
    assert busy["after"]["maxInFlight"] == 1, "every ask sent its own request"
    # One request per spacing interval, not one per debounce: 60 before.
    assert busy["after"]["requests"] <= 5


def test_requests_are_spaced_by_what_the_last_one_cost(
    scenarios: dict[str, list[dict[str, Any]]],
) -> None:
    busy = scenarios[LIVE][0]
    sent = _sent_at(busy)
    settled = _settled_at(busy)
    assert len(sent) >= 3
    for settled_at, next_sent in zip(settled, sent[1:], strict=False):
        assert next_sent - settled_at >= 2 * LIVE_SERVER_MS, (
            "the next request must wait twice what the last one cost"
        )


def test_the_last_ask_is_answered_after_the_writes_stop(
    scenarios: dict[str, list[dict[str, Any]]],
) -> None:
    busy, stopped = scenarios[LIVE]
    assert stopped["after"]["inFlight"] == 0
    assert stopped["after"]["requests"] == busy["after"]["requests"] + 1, (
        "asks made while a request was in flight need one more request"
    )
    assert stopped["did"][-1].endswith("files") and "painted" in stopped["did"][-1]


def test_an_isolated_change_waits_only_for_the_debounce(
    scenarios: dict[str, list[dict[str, Any]]],
) -> None:
    first, later = scenarios[QUIET]
    assert _sent_at(first) == [500]
    assert _sent_at(later) == [20500], "spacing must not delay a change after a quiet spell"


def test_a_failed_refresh_is_asked_again_after_a_growing_backoff(
    scenarios: dict[str, list[dict[str, Any]]],
) -> None:
    (step,) = scenarios[FAILING]
    sent = _sent_at(step)
    settled = _settled_at(step)
    assert len(sent) == 3, "a refresh that failed was not asked again"
    assert [b - a for a, b in zip(settled, sent[1:], strict=False)] == [4000, 8000]
    assert "answered" in step["did"][-2]


@pytest.mark.parametrize("scenario", [HIDDEN, BEHIND])
def test_a_summary_no_one_can_see_waits_until_it_can(
    scenarios: dict[str, list[dict[str, Any]]],
    scenario: str,
) -> None:
    unseen, shown = scenarios[scenario]
    assert unseen["after"]["asks"] == 100
    assert unseen["after"]["requests"] == 0, "a summary no one could see was requested"
    assert shown["after"]["requests"] == 1, "showing the summary again must refresh it once"
    assert _sent_at(shown) == [10000 + 500]
