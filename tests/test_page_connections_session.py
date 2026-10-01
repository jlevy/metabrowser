"""A page the browser keeps for Back holds no connection, and gets its own back.

A browser keeps a page it may show again on Back, with its heap and its open requests,
and opens six connections to a host. Each kept page's ``/api/events`` stream held one,
so after five page loads in one tab the next page's requests waited for a connection:
55 to 56 s in Chrome 152 (``explorations/page-connections/README.md``). The shell now
parks its connections on a ``pagehide`` that says the page is kept and reopens them on
the ``pageshow`` that brings it back.

``tests/dom/page-connections-session.js`` runs that decision,
``createPageConnections`` in ``static/navigation.js``, with the declarations of
``static/app.js`` it decides about extracted verbatim: the event stream and its timers,
the live tail of a log, and the two listeners. The catalog feed is the production
module, so a restore's reconciliation is a count of the requests it makes.
``tests/golden/cli-ui-page-connections.tryscript.md`` pins the whole transcript; each
test here holds one behavior of it, and fails when that behavior is removed.

What only a browser does is not here: whether it keeps a page, when it fires the two
events, and how many connections it opens. The exploration records that.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.golden_harness import run_session

EVENTS = "/api/events?scope=root-depth-2"
CATALOG = "request: GET /api/catalog"
KEPT = "pagehide, kept for Back"
RESTORED = "pageshow, restored"


@pytest.fixture(scope="module")
def scenarios() -> dict[str, list[dict[str, Any]]]:
    transcript = run_session("page-connections-session.js")
    return {scenario["scenario"]: scenario["steps"] for scenario in transcript}


def _step(steps: list[dict[str, Any]], name: str) -> dict[str, Any]:
    found = [step for step in steps if step["step"] == name]
    assert len(found) == 1, f"{name!r} is in the scenario {len(found)} times"
    return found[0]


def _opened(step: dict[str, Any]) -> list[str]:
    return [line.split("opened ", 1)[1] for line in step["did"] if ": opened " in line]


def _closed(step: dict[str, Any]) -> list[str]:
    return [line for line in step["did"] if line.endswith(": closed")]


FOLDER = "a folder's page is kept for Back and restored"
RECONNECTING = "a page is kept for Back while its stream waits to reconnect"
LIVE_LOG = "a page tailing a live log is kept for Back and restored"
PIN = "a pin's page is kept for Back and restored"
UNLOADED = "a page is unloaded"


def test_the_session_runs_every_scenario(scenarios: dict[str, list[dict[str, Any]]]) -> None:
    assert list(scenarios) == [FOLDER, RECONNECTING, LIVE_LOG, PIN, UNLOADED]


def test_a_kept_page_closes_its_event_stream(scenarios: dict[str, list[dict[str, Any]]]) -> None:
    steps = scenarios[FOLDER]
    assert _step(steps, "stream 1 opens and sends its snapshot")["after"]["streams"] == [EVENTS]
    kept = _step(steps, KEPT)
    assert _closed(kept) == ["stream 1: closed"]
    assert kept["after"]["streams"] == []
    assert kept["after"]["parked"] == 1


def test_a_kept_page_cancels_the_stable_connection_timer(
    scenarios: dict[str, list[dict[str, Any]]],
) -> None:
    steps = scenarios[FOLDER]
    assert _step(steps, "stream 1 opens and sends its snapshot")["after"]["timers"] == ["10000 ms"]
    kept = _step(steps, KEPT)
    assert "timer 1: cancelled" in kept["did"]
    assert kept["after"]["timers"] == []


def test_a_kept_page_cancels_a_pending_reconnect(
    scenarios: dict[str, list[dict[str, Any]]],
) -> None:
    """Left pending, the reconnect would open a second stream beside the restored one."""

    steps = scenarios[RECONNECTING]
    failed = _step(steps, "stream 1 fails five times")
    assert failed["after"] == {"streams": [], "timers": ["2000 ms"], "parked": 0}
    kept = _step(steps, KEPT)
    assert kept["did"] == ["timer 2: cancelled"]
    assert kept["after"] == {"streams": [], "timers": [], "parked": 1}
    restored = _step(steps, RESTORED)
    assert _opened(restored) == [EVENTS]
    assert restored["after"] == {"streams": [EVENTS], "timers": [], "parked": 0}


def test_a_restore_reopens_the_event_stream_once(
    scenarios: dict[str, list[dict[str, Any]]],
) -> None:
    steps = scenarios[FOLDER]
    restored = _step(steps, RESTORED)
    assert _opened(restored) == [EVENTS]
    assert restored["after"] == {"streams": [EVENTS], "timers": [], "parked": 0}
    # A second pageshow with nothing parked opens nothing.
    again = _step(steps, "pageshow, restored, with no pagehide before it")
    assert _opened(again) == []
    assert again["after"]["streams"] == [EVENTS]


def test_a_restore_reconciles_once_as_a_reconnect_does(
    scenarios: dict[str, list[dict[str, Any]]],
) -> None:
    """One snapshot and one catalog request per stream, on the first and on the restored."""

    steps = scenarios[FOLDER]
    for name in ("stream 1 opens and sends its snapshot", "stream 2 opens and sends its snapshot"):
        did = _step(steps, name)["did"]
        assert did.count(CATALOG) == 1, did
        assert did.count("tree: snapshot of 1 entries applied") == 1, did
    # The restore itself asks for nothing; the stream it opened does.
    assert CATALOG not in _step(steps, RESTORED)["did"]
    # And the restored stream is live.
    assert _step(steps, "a file changes")["did"] == ["tree: 1 change applied"]


def test_a_page_can_be_kept_and_restored_again(scenarios: dict[str, list[dict[str, Any]]]) -> None:
    steps = scenarios[FOLDER]
    kept = _step(steps, "pagehide, kept for Back again")
    assert _closed(kept) == ["stream 2: closed"]
    assert kept["after"] == {"streams": [], "timers": [], "parked": 1}
    restored = _step(steps, "pageshow, restored again")
    assert _opened(restored) == [EVENTS]
    assert restored["after"]["parked"] == 0


def test_a_live_log_is_parked_and_reopened_where_it_stopped(
    scenarios: dict[str, list[dict[str, Any]]],
) -> None:
    steps = scenarios[LIVE_LOG]
    opened = _step(steps, "a live log is opened, read to byte 120")
    assert _opened(opened) == ["/api/stream?path=run.jsonl&cursor=120"]
    kept = _step(steps, KEPT)
    assert _closed(kept) == ["stream 1: closed", "stream 2: closed"]
    assert kept["after"] == {"streams": [], "timers": [], "parked": 2}
    restored = _step(steps, RESTORED)
    assert _opened(restored) == [EVENTS, "/api/stream?path=run.jsonl&cursor=300"]
    assert restored["after"]["parked"] == 0


def test_a_pin_parks_nothing_and_a_restore_asks_for_nothing(
    scenarios: dict[str, list[dict[str, Any]]],
) -> None:
    """A pin has no stream, so a landing asks only what it asked before: the served pin."""

    steps = scenarios[PIN]
    assert _step(steps, "the page starts")["did"] == [CATALOG]
    assert _step(steps, KEPT) == {
        "step": KEPT,
        "did": [],
        "after": {"streams": [], "timers": [], "parked": 0},
    }
    restored = _step(steps, RESTORED)
    assert _opened(restored) == []
    assert CATALOG not in restored["did"]


def test_an_unloaded_page_is_torn_down_and_closes_nothing(
    scenarios: dict[str, list[dict[str, Any]]],
) -> None:
    steps = scenarios[UNLOADED]
    assert _step(steps, "pageshow, the first load")["did"] == []
    unloaded = _step(steps, "pagehide, not kept")
    assert unloaded["did"] == ["page: keyboard and Quick File torn down"]
    assert unloaded["after"] == {"streams": [EVENTS], "timers": ["10000 ms"], "parked": 0}


def test_a_restore_rebuilds_what_a_teardown_removed(
    scenarios: dict[str, list[dict[str, Any]]],
) -> None:
    restored = _step(scenarios[UNLOADED], "pageshow, restored all the same")
    assert restored["did"] == [
        "page: keyboard rebuilt if torn down",
        "page: Quick File rebuilt if torn down",
    ]
    # Before the reopened stream, on a kept page too.
    kept = _step(scenarios[FOLDER], RESTORED)["did"]
    assert kept[:2] == restored["did"]
    assert kept[2].startswith("stream 2: opened")
