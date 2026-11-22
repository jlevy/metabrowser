"""A view tab chosen while its file holds its first paint.

The shell stages a file out of sight with its tab bar and holds the first paint until
the view in front has its data (``renderFile`` in ``static/app.js``). A tab chosen
meanwhile used to be lost: the staged bar had no listeners and its other views no mounts
until the hold ended, and the commit put the first view in front whatever the bar said
(mb-s588). ``tests/dom/view-tab-hold-session.js`` runs the production functions through
each order a choice can arrive in, and ``cli-ui-view-tab-hold.tryscript.md`` pins its
whole output. The checks below hold the invariants in that output.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tests.required_tools import require_node

SESSION = Path(__file__).resolve().parent / "dom" / "view-tab-hold-session.js"


@pytest.fixture(scope="module")
def session() -> dict[str, Any]:
    result = subprocess.run(
        [require_node(), str(SESSION)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    scenarios: dict[str, Any] = json.loads(result.stdout)
    return scenarios


def test_the_first_view_comes_up_when_nothing_is_chosen(session: dict[str, Any]) -> None:
    scenario = session["noChoice"]
    assert scenario["held"] == {"staged": "src in overview", "pane": None, "mounts": "overview 1"}
    assert scenario["after"] == {
        "committed": True,
        "staged": None,
        "pane": "src in overview",
        "mounts": "overview 1",
    }


@pytest.mark.parametrize("scenario", ["clickDuringHold", "namedDuringHold"])
def test_a_tab_chosen_during_the_hold_is_in_front_at_the_commit(
    session: dict[str, Any], scenario: str
) -> None:
    held = session[scenario]["held"]
    # Chosen before the first view had its data: nothing is committed yet, and the chosen
    # view mounts at once, in the stage.
    assert held["pane"] is None
    assert held["staged"] == "src in treemap"
    assert held["mounts"] == "overview 1, treemap 1"
    after = session[scenario]["after"]
    assert after["committed"] is True and after["staged"] is None
    assert after["pane"] == "src in treemap"
    # Neither view mounts a second time for the commit.
    assert after["mounts"] == "overview 1, treemap 1"


def test_the_first_view_is_still_there_after_a_choice_during_the_hold(
    session: dict[str, Any],
) -> None:
    back = session["clickDuringHold"]["backToOverview"]
    assert back["pane"] == "src in overview"
    assert back["mounts"] == "overview 1, treemap 1"


def test_a_view_named_before_the_stage_is_the_one_the_file_opens_in(
    session: dict[str, Any],
) -> None:
    scenario = session["namedBeforeTheStage"]
    assert scenario["before"] == {"staged": None, "pane": None, "mounts": ""}
    assert scenario["after"]["pane"] == "src in treemap"
    # It is the render's first view, so the folder's default never mounts.
    assert scenario["after"]["mounts"] == "treemap 1"


def test_a_view_named_for_a_file_not_loading_is_not_kept(session: dict[str, Any]) -> None:
    assert session["namedForAnotherFile"]["pane"] == "src in overview"
    assert session["namedForAnotherFile"]["mounts"] == "overview 1"


def test_a_tab_picked_on_the_shown_file_reaches_its_own_stage(session: dict[str, Any]) -> None:
    scenario = session["choiceWhileStagedAgain"]
    assert scenario["shown"]["pane"] == "src in overview"
    assert scenario["held"]["pane"] == "src in treemap"
    assert scenario["held"]["staged"] == "src in treemap"
    assert scenario["after"]["pane"] == "src in treemap"


def test_a_tab_picked_on_the_shown_file_leaves_another_files_stage_alone(
    session: dict[str, Any],
) -> None:
    scenario = session["choiceWhileAnotherFileIsStaged"]
    assert scenario["held"]["pane"] == "src in treemap"
    # The staged file's bar and views are whole: a string, not the list of disagreements.
    assert scenario["held"]["staged"] == "docs in overview"
    assert scenario["after"]["pane"] == "docs in overview"
    # The other folder's Treemap was never chosen, so it never mounts.
    assert scenario["after"]["mounts"] == "overview 2, treemap 1"
