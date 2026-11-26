"""The file-watches session runs what a page's file watches do once registered.

``tests/dom/file-watches-session.js`` runs ``static/file-watches.js`` on the page
``tests/dom/page-connections-session.js`` builds, with ``app.js``'s ``watchContainer`` and
``loadContainerChildren`` extracted verbatim, against a server that holds each
connection's watched paths up to a bound and can hold its answers.
``tests/golden/cli-ui-file-watches.tryscript.md`` pins its transcript. Review A of #675
asked for each case: a watch released before its answer (A1), a refusal retried (A12), a
hidden page (A2), and a tree container that follows its file (A5, A6).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from tests.golden_harness import run_session


@pytest.fixture(scope="module")
def scenarios() -> dict[str, list[dict[str, Any]]]:
    transcript = run_session("file-watches-session.js")
    return {scenario["scenario"]: scenario["steps"] for scenario in transcript}


def _step(steps: list[dict[str, Any]], name: str) -> dict[str, Any]:
    found = [step for step in steps if step["step"] == name]
    assert len(found) == 1, f"{name!r} is in the scenario {len(found)} times"
    return found[0]


def _posts(step: dict[str, Any]) -> list[str]:
    return [line.split(" ", 3)[3] for line in step["did"] if "POST /api/events/watch" in line]


def test_the_session_runs_every_scenario(scenarios: dict[str, list[dict[str, Any]]]) -> None:
    assert list(scenarios) == [RELEASED, CONTAINER]


RELEASED = "a page's file watches are released, retried, and paused while hidden"
CONTAINER = "a tree container's children follow its file"


def _server(step: dict[str, Any]) -> str:
    """What the server watched for c1 when the step ended."""

    return [line for line in step["did"] if line.startswith("server: c1 watches")][-1]


def test_a_watch_released_before_its_answer_is_unregistered_after_it(
    scenarios: dict[str, list[dict[str, Any]]],
) -> None:
    """Review A of #675, A1: a registration still in flight is unregistered once it lands,
    so leaving views quickly never fills the connection's bound."""

    left = _step(
        scenarios[RELEASED],
        "a table watches a.csv and leaves before the slow answer: unregistered after it",
    )
    assert _posts(left) == [
        '{"connection":"c1","path":"a.csv","generation":"a1"}',
        '{"connection":"c1","path":"a.csv","watch":false}',
    ]
    assert _server(left) == "server: c1 watches []"
    assert left["after"]["watches"] == []


def test_a_watch_refused_for_room_registers_again_once_another_is_released(
    scenarios: dict[str, list[dict[str, Any]]],
) -> None:
    steps = scenarios[RELEASED]
    full = _step(steps, "tables watch b.csv, c.csv, and d.csv: past the bound of 2, d is refused")
    assert "d: watch refused (too_many_watches)" in full["did"]
    freed = _step(steps, "b's table leaves: once b is unregistered, d registers again and is live")
    # The unregistration reaches the server before the registration it makes room for.
    assert [json.loads(body)["path"] for body in _posts(freed)] == ["b.csv", "d.csv"]
    assert [watch["state"] for watch in freed["after"]["watches"]] == ["live", "live"]


def test_a_hidden_page_watches_nothing_and_hears_a_change_once_when_shown(
    scenarios: dict[str, list[dict[str, Any]]],
) -> None:
    steps = scenarios[RELEASED]
    hidden = _step(steps, "the page is hidden: every watch is unregistered, so none is polled")
    assert _server(hidden) == "server: c1 watches []"
    assert {watch["reason"] for watch in hidden["after"]["watches"]} == {"hidden"}
    assert _step(steps, "d.csv changes while the page is hidden: nothing is told")["did"] == []
    shown = _step(
        steps, "the page is shown: each registers again with what it holds, and d hears d2 once"
    )
    assert _posts(shown) == [
        '{"connection":"c1","path":"c.csv","generation":"c1"}',
        '{"connection":"c1","path":"d.csv","generation":"d1"}',
    ]
    assert shown["did"].count("d: d.csv is now d2") == 1


def _children_reads(step: dict[str, Any]) -> int:
    return sum("GET /api/plugin/sqlite/children" in line for line in step["did"])


def _drawn(step: dict[str, Any]) -> list[str]:
    return [line for line in step["did"] if line.startswith("tree: app.db's children drawn")]


def test_a_container_reads_its_children_once_a_window_one_read_at_a_time(
    scenarios: dict[str, list[dict[str, Any]]],
) -> None:
    """Review A of #675, A5 and A6: the tree's container refresh is coalesced, runs one
    read at a time, and draws only what differs."""

    steps = scenarios[CONTAINER]
    burst = _step(steps, "its file changes three times in a burst: one read is due")
    assert (_children_reads(burst), burst["after"]["timers"]) == (0, ["10000 ms", "300 ms"])
    read = _step(steps, "the window ends: the children read once and drawn again")
    assert _children_reads(read) == 1
    assert _drawn(read) == ["tree: app.db's children drawn: users | orders | items"]
    same = _step(steps, "a change that leaves the children as they were: read, not drawn")
    assert (_children_reads(same), _drawn(same)) == (1, [])
    slow = _step(steps, "a change while a slow read runs: it waits for that read")
    assert (_children_reads(slow), slow["after"]["timers"]) == (1, ["10000 ms"])
    answered = _step(steps, "the slow read answers and is drawn: one more read is due")
    assert answered["after"]["timers"] == ["10000 ms", "300 ms"]
    assert (
        _children_reads(
            _step(steps, "the next window ends: the children read again, unchanged since")
        )
        == 1
    )


def test_a_container_collapsed_reads_on_expand_and_a_dropped_row_releases_its_watch(
    scenarios: dict[str, list[dict[str, Any]]],
) -> None:
    steps = scenarios[CONTAINER]
    collapsed = _step(
        steps, "app.db collapsed, then changed: its children are read on the next expand"
    )
    assert _children_reads(collapsed) == 0
    assert "tree: children loaded: no" in collapsed["did"]
    dropped = _step(
        steps, "the tree drops the row: its watch released, though the file is unchanged"
    )
    assert _posts(dropped) == ['{"connection":"c1","path":"app.db","watch":false}']
    assert dropped["after"]["watches"] == []
