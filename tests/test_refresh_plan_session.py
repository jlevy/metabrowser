"""The navigation's one Refresh (static/refresh-plan.js), held to its invariants.

tests/dom/refresh-plan-session.js runs the production module without a browser, and
cli-ui-refresh-plan.tryscript.md pins its record. These tests say what the record must
show whatever else changes: a press refreshes every part the page holds, the parts on
screen before any part behind another tab, the button waits while the parts on screen
refresh and only then, a press while it waits does nothing, and one part's failure does
not stop the rest (docs/design-system.md, "Refresh, Retry, and Reload Page").
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tests.required_tools import require_node

ROOT = Path(__file__).resolve().parents[1]
SESSION = ROOT / "tests" / "dom" / "refresh-plan-session.js"
# The session runs in well under a second; the bound leaves room for a loaded CI runner,
# under the suite's own timeout (tests/test_suite_gates.py, MAX_INNER_BOUND_S).
SESSION_TIMEOUT_S = 30
PARTS = ["source", "page", "files", "pulls", "git"]


@pytest.fixture(scope="module")
def steps() -> dict[str, dict[str, Any]]:
    require_node()
    result = subprocess.run(
        ["node", str(SESSION)],
        capture_output=True,
        text=True,
        timeout=SESSION_TIMEOUT_S,
        check=False,
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stderr
    return {step["step"]: step for step in json.loads(result.stdout)["steps"]}


def _starts(events: list[str]) -> list[str]:
    return [event.split(" ", 1)[0].rstrip(":,") for event in events if event.endswith(" starts")]


def _visible_first(events: list[str], waits: str, offered: str) -> list[str]:
    """The parts a press ran while the button waited, checking each settled before it was
    offered and that nothing behind another tab started before then."""

    assert events[0] == waits, events
    at = events.index(offered)
    visible = _starts(events[:at])
    for part in visible:
        settled = [event for event in events[:at] if event.startswith(part) and "settles" in event]
        failed = [event for event in events[:at] if event.startswith(f"{part} failed")]
        assert settled or failed, (part, events)
    return visible


def test_each_screen_refreshes_what_it_shows_first(steps: dict[str, dict[str, Any]]) -> None:
    order = steps[
        "each screen's order: the parts on screen, then the rest, each half in plan order"
    ]
    assert order["parts"] == PARTS
    expected = {
        "Files in front, a file in the pane": ["source", "files"],
        "Files in front, nothing chosen": ["source", "files"],
        "Files in front, a pull request still in the pane": ["source", "page", "files"],
        "Pulls in front, a pull request in the pane": ["source", "page", "pulls"],
        "Pulls in front, a file still in the pane": ["source", "files", "pulls"],
        "Commits in front, a commit in the pane": ["source", "git"],
        "Commits in front, a file still in the pane": ["source", "files", "git"],
    }
    assert {screen["screen"]: screen["visible"] for screen in order["screens"]} == expected
    for screen in order["screens"]:
        # Every part runs once, the visible half first, each half in plan order.
        assert screen["visible"] + screen["hidden"] == sorted(
            PARTS, key=lambda part: (part not in screen["visible"], PARTS.index(part))
        ), screen


def test_a_press_refreshes_the_visible_parts_before_the_hidden(
    steps: dict[str, dict[str, Any]],
) -> None:
    press = steps["a press runs the parts on screen while the button waits, then the rest"]
    events = press["events"]
    assert _visible_first(events, "waits", "offered") == ["source", "page", "pulls"]
    assert _starts(events) == ["source", "page", "pulls", "files", "git"]
    assert events.count("waits") == events.count("offered") == 1
    assert press["a second press while it waits"] is False
    assert press["the first press"] is True
    assert press["waiting after"] is False


def test_a_failing_part_leaves_the_rest(steps: dict[str, dict[str, Any]]) -> None:
    events = steps["a part that fails leaves the rest to run"]["events"]
    assert "source failed: source could not be read" in events
    assert _starts(events) == ["source", "files", "page", "pulls", "git"]


def test_a_released_part_is_not_run(steps: dict[str, dict[str, Any]]) -> None:
    released = steps["a released part is not run, and a stale release keeps the newer refresh"]
    assert released["parts"] == "source, files, git"
    assert "git, provided again, starts" in released["events"]
    assert not any(event.startswith(("page", "pulls")) for event in released["events"])


def test_a_later_press_supersedes_the_rest_of_an_earlier(
    steps: dict[str, dict[str, Any]],
) -> None:
    events = steps["a press while the hidden parts run supersedes the rest of the first"]["events"]
    # Each part ran once for the second press, and the first stopped behind the tabs at the
    # part it was running when the second began.
    assert _starts(events).count("page") == 2
    assert _starts(events).count("pulls") == _starts(events).count("git") == 1


@pytest.mark.parametrize(
    ("front", "owner", "store", "visible"),
    [
        ("pulls", "pull-request", True, ["source", "page", "pulls"]),
        ("files", "file", True, ["source", "files"]),
        ("git", "git", True, ["source", "git"]),
        ("files", "file", False, ["files"]),
    ],
)
def test_a_click_on_the_page_runs_the_shells_parts_in_order(
    steps: dict[str, dict[str, Any]], front: str, owner: str, store: bool, visible: list[str]
) -> None:
    suffix = "" if store else ", a local repository with no store and no Pulls tab"
    click = steps[f'a click with {front} in front and the pane\'s owner "{owner}"{suffix}']
    asked = click["asked"]
    assert _visible_first(
        asked, "the button: aria-disabled=true", "the button: no aria-disabled"
    ) == (visible)
    assert sorted(_starts(asked)) == sorted(click["parts"])
    if not store:
        assert click["parts"] == ["files", "git"]
