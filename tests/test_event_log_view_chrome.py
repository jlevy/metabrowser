"""Metabrowser's own event log, browsed in Metabrowser, laid out by headless Chrome.

``tests/dom/event-log-view-chrome.mjs`` serves a folder holding one event log segment (the
fixture ``cli-api-event-log-views.tryscript.md`` pins), opens it in the shell's own page,
and measures what no browserless DOM computes:

- the file's tabs are the four views and Raw JSON, in the manifest's order, with Timeline
  in front, and the keys V, L, B, and E switch between the views;
- every row is one height, the shell's row height, and its bar sits where the log's time
  axis puts it: a request that began 4.9 s into 229.9 s starts at about 2% of the track
  and is about 1% long, and a request of a few milliseconds is still drawn;
- an outcome is drawn in the shell's own status inks, success, failure, and a request
  that was cancelled in three that differ, and the Errors view's cause in the failure ink;
- a job nests under its request and a process under its job, each one indent from the
  last, its chevron turned and its detail shown;
- a row a key reaches has a focus ring, and Enter on it opens it;
- the distribution's tallest column is the full height of its track and the others are
  their counts' shares of it;
- nothing overflows the pane at the default width, and in a pane of 260 px, which a window
  of 560 px leaves beside the navigation pane, a row drops its bar and its offset and
  keeps its name and its ending, with nothing overflowing;
- a chip of the filter bar narrows the timeline to the jobs and the requests that started
  them, which are drawn in the muted ink as context; and Raw JSON is the JSONL view.

The session's own state, requests, and filters run browserless in
``tests/dom/event-log-view-session.js``. Without Chrome this skips (``require_chrome`` in
``tests/required_tools.py``), and CI runs it. ``EVENT_LOG_VIEW_SHOTS`` names a directory to
save a screenshot of each view to.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_node

SESSION = Path(__file__).resolve().parent / "dom" / "event-log-view-chrome.mjs"
LOG = "events-20261119T220000Z-p7007-000.jsonl"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "event-log-views" / LOG
# A server start, one Chrome, four views, and a narrow window took 3.2 s on a Mac at a load
# average near 20 (2026-11-19). A cold Chrome start in CI has taken 28.2 s (the Overview
# alignment test, 2026-11-14), and the server's own start is bounded at 30 s inside the
# session, so the bound leaves room for both, and fires before the module's limit.
SESSION_TIMEOUT_S = 90
# The longest the test can take: the session's bound, its process group stopped after it
# (Chrome and the server are in it), and the profile's teardown (tests/process_group.py),
# with 10 s more for the rest of the setup.
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)
_METAB = Path(sys.executable).with_name("metab")
# Layout rounds to fractions of a pixel, and a share is read off a rounded width.
TOLERANCE = 0.03


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _measure(tmp_path: Path, chrome_profile: Path) -> dict[str, Any]:
    chrome = require_chrome()
    root = tmp_path / "served"
    root.mkdir()
    shutil.copy(FIXTURE, root / LOG)
    state = tmp_path / "state"
    state.mkdir()
    shots = os.environ.get("EVENT_LOG_VIEW_SHOTS")
    # The session leads a process group of its own, which Chrome and the server join, and
    # the whole group is stopped however it ends; the profile is the fixture's to remove.
    result = run_in_own_group(
        [
            require_node(),
            str(SESSION),
            str(_METAB),
            str(root),
            LOG,
            str(_free_port()),
            str(state),
            *([shots] if shots else []),
        ],
        timeout_s=SESSION_TIMEOUT_S,
        env={**os.environ, "CHROME_BIN": chrome, "CHROME_PROFILES": str(chrome_profile)},
    )
    assert not result.timed_out, (
        f"the session ran past {SESSION_TIMEOUT_S} s: {result.stderr or result.stdout}"
    )
    assert result.returncode == 0, result.stderr or result.stdout
    # Shown with the failure: every measurement, and each phase's time.
    print(result.stdout, result.stderr)
    return json.loads(result.stdout.strip().splitlines()[-1])


def _check_the_views_are_the_files_tabs_and_their_keys_switch_them(
    measured: dict[str, Any],
) -> None:
    assert [tab["text"] for tab in measured["tabs"]] == [
        "Timeline",
        "Latency",
        "By kind",
        "Errors",
        "Raw JSON",
    ]
    assert [tab["text"] for tab in measured["tabs"] if tab["selected"]] == ["Timeline"]
    assert measured["keys"] == {
        "latency": "Latency",
        "kinds": "By kind",
        "errors": "Errors",
        "timeline": "Timeline",
    }
    assert measured["exceptions"] == []


def _check_a_row_is_the_shells_row_height_and_its_bar_is_on_the_time_axis(
    measured: dict[str, Any],
) -> None:
    timeline = measured["timeline"]
    assert timeline["rows"] == 44
    assert timeline["headHeights"] == [float(timeline["rowHeightToken"].removesuffix("px"))]
    # The request at +4.9 s of 229.9 s, 2.41 s long.
    assert timeline["barLeftShare"] == pytest.approx(4.9 / 229.9, abs=0.005)
    assert timeline["barWidthShare"] == pytest.approx(2.4125 / 229.9, abs=0.005)
    assert timeline["hairline"] > 0, "a request of a few milliseconds is still drawn"
    assert timeline["noOverflow"] is True
    assert timeline["chipsDrawn"] == 7 + 6 + 6
    assert timeline["noticeSeverity"] == "warning"


def _check_an_outcome_is_drawn_in_the_shells_status_inks(measured: dict[str, Any]) -> None:
    inks = measured["timeline"]["outcomeInks"]
    tokens = measured["timeline"]["tokens"]
    assert inks == {"ok": tokens["success"], "failed": tokens["error"], "quiet": tokens["muted"]}
    assert len({inks["ok"], inks["failed"], inks["quiet"]}) == 3
    assert measured["errors"]["causeInk"] == measured["errors"]["errorInk"] == tokens["error"]


def _check_a_job_nests_under_its_request_and_a_process_under_its_job(
    measured: dict[str, Any],
) -> None:
    nesting = measured["nesting"]
    assert nesting["jobFromRequest"] == nesting["processFromJob"] == nesting["indentToken"] > 0
    assert nesting["nameStepsRight"] is True
    assert nesting["expanded"] == ["true", "true"]
    assert nesting["detailShown"] is True
    assert nesting["chevronTurned"] is True


def _check_a_row_a_key_reaches_has_a_focus_ring_and_enter_opens_it(
    measured: dict[str, Any],
) -> None:
    keyboard = measured["keyboard"]
    assert keyboard["onRow"] is True
    assert keyboard["outlineStyle"] != "none"
    assert float(keyboard["outlineWidth"].removesuffix("px")) > 0
    assert (keyboard["expanded"], keyboard["afterEnter"]) == ("false", "true")


def _check_the_distribution_is_drawn_in_proportion(measured: dict[str, Any]) -> None:
    latency = measured["latency"]
    assert latency["columns"] == 7
    assert sum(latency["counts"]) == latency["rows"] == 49
    assert latency["tallestPx"] == 64
    for share, expected in zip(latency["shares"], latency["expectedShares"], strict=True):
        # An empty column keeps a hairline, so it reads as a column and not a gap.
        assert share == pytest.approx(expected, abs=TOLERANCE)
    assert latency["barsInFirstRows"][0] == 1.0
    assert latency["noOverflow"] is True


def _check_by_kind_tables_fit_and_numbers_align_right(measured: dict[str, Any]) -> None:
    assert measured["kinds"] == {"sections": 7, "tablesFit": True, "numbersAlignRight": True}


def _check_the_errors_view_has_no_filter_bar_and_four_parts(measured: dict[str, Any]) -> None:
    errors = measured["errors"]
    assert errors["causes"] == 2
    assert errors["filterBar"] is False
    assert [heading.split(" · ")[0] for heading in errors["headings"]] == [
        "Failures by cause",
        "Last failed connectivity probe",
        "Still running when the log ended",
        "What the pages reported",
    ]


def _check_a_narrow_pane_drops_the_bar_and_the_offset_and_keeps_the_name(
    measured: dict[str, Any],
) -> None:
    assert measured["narrow"] == {
        "barShown": False,
        "whenShown": False,
        "noOverflow": True,
        "nameShown": True,
    }


def _check_a_chip_narrows_the_timeline_and_the_requests_above_a_match_are_context(
    measured: dict[str, Any],
) -> None:
    filtered = measured["filtered"]
    assert (filtered["rows"], filtered["pressed"], filtered["context"]) == (3, "true", 3)
    assert filtered["contextInk"] == measured["timeline"]["tokens"]["muted"]


def _check_raw_json_is_the_jsonl_view(measured: dict[str, Any]) -> None:
    assert measured["raw"] is True


def test_the_event_log_views_in_chrome(tmp_path: Path, chrome_profile: Path) -> None:
    measured = _measure(tmp_path, chrome_profile)
    _check_the_views_are_the_files_tabs_and_their_keys_switch_them(measured)
    _check_a_row_is_the_shells_row_height_and_its_bar_is_on_the_time_axis(measured)
    _check_an_outcome_is_drawn_in_the_shells_status_inks(measured)
    _check_a_job_nests_under_its_request_and_a_process_under_its_job(measured)
    _check_a_row_a_key_reaches_has_a_focus_ring_and_enter_opens_it(measured)
    _check_the_distribution_is_drawn_in_proportion(measured)
    _check_by_kind_tables_fit_and_numbers_align_right(measured)
    _check_the_errors_view_has_no_filter_bar_and_four_parts(measured)
    _check_a_narrow_pane_drops_the_bar_and_the_offset_and_keeps_the_name(measured)
    _check_a_chip_narrows_the_timeline_and_the_requests_above_a_match_are_context(measured)
    _check_raw_json_is_the_jsonl_view(measured)
