"""File Overview's legend hovers its family's marks, under Chrome's own pointer.

A legend entry is a handle on its family's marks in every bar on screen, and a segment is a
handle on itself (docs/design-system.md, "Aggregate Distributions"). Which marks a handle
names, the tooltip it shows, and when the hover is put away run browserlessly in
``tests/dom/file-overview-session.js`` (``cli-ui-file-overview.tryscript.md``). What only a
browser can say is held here: ``tests/dom/overview-legend-hover-chrome.mjs`` serves a folder
of seven file-type families, three of them partly ignored, so the legend names five and
Other and each tally row has segments, and moves Chrome's pointer onto an entry's name and
then its dot, off the legend, onto a segment itself, and onto Other, opens and closes
Details under the entry, and reads the entry again on the dark page and under reduced
motion. This holds that:

- the entry's name and its dot each lift and grow its family's segment in every tally row,
  Files, Ignored, and Total, and its Details row while Details is open, and nothing else,
  grown twice over on the axis that carries no data;
- the entry is marked: its dot lifted, its name in its family's ink at 4.5:1 or better on
  both pages, and every other entry at rest;
- each marked bar and the entry's dot shimmer, by opacity alone, entered together in step;
- the tooltip shows the counts of the family's Total segment, the name the entry shows
  left out, centered on the entry and clear of it; moving from the name to the dot changes
  nothing;
- pointing at a segment lifts and grows it alone, marks its family's entry, and shows the
  same counts under the family's name, centered on the segment and clear of it;
- every grown bar clears the tracks beside it and the legend, no layout box moves under
  the hover, and every entry keeps its size;
- under ``prefers-reduced-motion: reduce`` the marks still lift and grow, at once, with no
  transition and no shimmer;
- Other draws nothing;
- each Details group's heading leads with its category's icon, the glyph size and in the
  heading's ink, standing in its rows' icon box, so its icon and name start where its
  family rows' do (docs/design-system.md, "File-Type Category Icons").

What the shimmer costs on the main thread, which it does not, is measured beside the tokens
in ``static/styles.css``.

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``), and CI runs
it. The session leads a process group of its own, which Chrome and the server join, and the
whole group is stopped however it ends (tests/process_group.py).
"""

from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_node

SESSION = Path(__file__).resolve().parent / "dom" / "overview-legend-hover-chrome.mjs"
# A server start, one Chrome, a page load, and thirteen readings, each taken once the
# shell's tooltip appear delay or fade (TOOLTIP_APPEAR_DELAY and TOOLTIP_FADE_OUT in
# static/app.js) and the section's transitions have settled, took 12.7 s on a 10-core Mac
# at a load average near 12 (2026-11-18). A cold Chrome start in CI has taken
# 28.2 s (the Overview alignment test, 2026-11-14), and the server's own start is bounded
# at 30 s inside the session, so the bound leaves room for both, and fires before the
# module's limit.
SESSION_TIMEOUT_S = 90
# The session's bound, its process group stopped after it (Chrome and the server are in
# it), and the profile's teardown (tests/process_group.py), with 10 s more for the rest of
# the setup; tests/test_process_group.py holds the sum under the module's limit.
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)
_METAB = Path(sys.executable).with_name("metab")

# Seven families, so the legend names the five largest and Other holds the last two, and an
# ignored build directory holding three of them, so the Ignored row has segments too.
_FAMILIES = {"md": 8, "py": 4, "json": 3, "yaml": 2, "ts": 2, "css": 1, "rs": 1}
_IGNORED = {"py": 2, "json": 3, "md": 1}


def _served_folder(root: Path) -> None:
    (root / ".git").mkdir(parents=True)
    (root / ".gitignore").write_text("build/\n", encoding="utf-8")
    for extension, count in _FAMILIES.items():
        for n in range(1, count + 1):
            (root / f"f{n}.{extension}").write_text(f"x{n}\n", encoding="utf-8")
    (root / "build").mkdir()
    for extension, count in _IGNORED.items():
        for n in range(1, count + 1):
            (root / "build" / f"g{n}.{extension}").write_text(f"y{n}\n", encoding="utf-8")


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


# The Python family's tooltip on its legend entry, which shows the name, and on its segment,
# which does not: its Total segment, the row the legend's shares are of with Show ignored on
# (docs/design-system.md, "Aggregate Distributions").
_PYTHON_TOOLTIP = {"legend": "6 files · 18 B", "segment": "Python 6 files · 18 B"}
_PYTHON_BARS = ["Files family:python", "Ignored family:python", "Total family:python"]
_PYTHON_ENTRY = "legend family:python"
# --viz-hover-grow in static/styles.css.
_GROW = 2


def _bars_lifted(reading: dict[str, Any], label: str) -> None:
    """Every marked bar grown on the axis that carries no data, and lifted."""

    assert reading["barStyle"], (label, reading)
    for style in reading["barStyle"]:
        # The width, which is the value, does not move.
        assert style["scaleY"] == _GROW and style["scaleX"] == 1, (label, reading)
        assert style["filter"] != "none", (label, reading)
    assert reading["othersAtRest"], (label, reading)
    assert all(gap > 0 for gap in reading["clearance"]), (label, reading)


def _entry_marked(reading: dict[str, Any], label: str) -> None:
    """The Python entry alone marked: its dot lifted and its name inked at 4.5:1 or better."""

    (entry,) = reading["entries"]
    assert entry["dotFilter"] != "none", (label, reading)
    assert entry["inkContrast"] >= 4.5, (label, reading)
    assert reading["otherEntriesAtRest"], (label, reading)


def _tooltip_on(reading: dict[str, Any], label: str, anchor: str) -> None:
    assert reading["tooltip"] == _PYTHON_TOOLTIP[anchor], (label, reading)
    placed = reading["tooltipOnAnchor"]
    # Centred on what the pointer is on, the legend entry or the segment, unless the
    # viewport's margin clamps it, and clear of it above or below.
    assert placed is not None and placed["anchor"] == anchor, (label, reading)
    assert placed["clear"], (label, reading)
    assert abs(placed["centerOffset"]) <= 1, (label, reading)


def _shimmering(reading: dict[str, Any], label: str, together: bool = True) -> None:
    """Every marked bar and the marked entry's dot shimmer, and nothing else.

    Marks the hover enters together shimmer in step; one marked later, as a Details row
    opened under a held entry, starts its own cycle (docs/design-system.md, "Hover Styles
    the Thing Under the Pointer").
    """

    marks = reading["marked"]
    assert sorted(reading["shimmer"]["on"]) == sorted(f"{mark}::after" for mark in marks), (
        label,
        reading,
    )
    assert reading["shimmer"]["running"], (label, reading)
    assert reading["shimmer"]["animates"] == ["opacity"], (label, reading)
    assert reading["shimmer"]["oneStart"] == together, (label, reading)


def _nothing(reading: dict[str, Any], label: str) -> None:
    assert reading["marked"] == [], (label, reading)
    assert reading["othersAtRest"], (label, reading)
    assert reading["otherEntriesAtRest"], (label, reading)
    assert reading["shimmer"]["on"] == [], (label, reading)
    assert reading["tooltip"] is None, (label, reading)


def test_a_legend_entry_hovers_its_familys_marks_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    root = tmp_path / "served"
    _served_folder(root)
    state = tmp_path / "state"
    state.mkdir()
    result = run_in_own_group(
        [require_node(), str(SESSION), str(_METAB), str(root), str(_free_port()), str(state)],
        timeout_s=SESSION_TIMEOUT_S,
        env={**os.environ, "CHROME_BIN": chrome, "CHROME_PROFILES": str(chrome_profile)},
    )
    assert not result.timed_out, (
        f"the session ran past {SESSION_TIMEOUT_S} s: {result.stderr or result.stdout}"
    )
    assert result.returncode == 0, result.stderr or result.stdout
    # Shown with a failure: every reading, and each phase's time.
    print(result.stdout, result.stderr)
    measured: dict[str, Any] = json.loads(result.stdout.strip().splitlines()[-1])

    # JSON and Python tie on files and bytes, and TypeScript and YAML too, so the family ID
    # orders each pair (file_type_legend.py).
    assert measured["legend"] == ["Markdown", "JSON", "Python", "TypeScript", "YAML", "Other"], (
        measured["legend"]
    )
    rest = measured["atRest"]
    _nothing(rest, "at rest")

    for step in ("entryName", "entryDot"):
        reading = measured[step]
        assert reading["marked"] == [*_PYTHON_BARS, _PYTHON_ENTRY], (step, reading)
        _bars_lifted(reading, step)
        _entry_marked(reading, step)
        _shimmering(reading, step)
        _tooltip_on(reading, step, "legend")
        # Nothing moves under the hover, and the entry keeps its size.
        assert reading["layout"] == rest["layout"], step
        assert reading["entrySize"] == rest["entrySize"], step
    assert measured["entryDot"]["tooltipLeft"] == measured["entryName"]["tooltipLeft"], measured
    _nothing(measured["left"], "off the legend")

    segment = measured["segment"]
    assert segment["marked"] == ["Total family:python", _PYTHON_ENTRY], segment
    _bars_lifted(segment, "the segment")
    _entry_marked(segment, "the segment")
    _shimmering(segment, "the segment")
    _tooltip_on(segment, "the segment", "segment")
    assert segment["layout"] == rest["layout"], "the segment"
    _nothing(measured["segmentLeft"], "off the segment")

    # Each Details group's heading leads with its category's icon, in the heading's ink,
    # its icon and name on its family rows' columns (docs/design-system.md, "File-Type
    # Category Icons").
    headings = measured["detailsHeadings"]
    assert [heading["name"] for heading in headings["headings"]] == [
        "Documentation",
        "Code",
        "Data",
    ]
    for heading in headings["headings"]:
        icon = heading["icon"]
        assert icon is not None, heading
        assert icon["width"] == icon["height"] == headings["glyph"], heading
        assert icon["inHeadingInk"], heading
        assert icon["fromRowGlyph"] == 0 and icon["nameFromRowName"] == 0, heading

    # Details open, then the entry: the family's own row is marked with the bars.
    details_rest = measured["detailsAtRest"]
    _nothing(details_rest, "Details open at rest")
    details = measured["detailsEntry"]
    assert details["marked"] == [*_PYTHON_BARS, _PYTHON_ENTRY, "Details family:python"], details
    _bars_lifted(details, "Details open")
    _entry_marked(details, "Details open")
    _shimmering(details, "Details open")
    assert details["layout"] == details_rest["layout"], "Details open"
    # Details closed by a key under the entry: its row goes, and the rest stays marked.
    closed = measured["detailsClosedUnderEntry"]
    assert closed["marked"] == [*_PYTHON_BARS, _PYTHON_ENTRY], closed
    _shimmering(closed, "Details closed")
    # Details opened by a key under the held entry: its row joins the marks, a cycle behind.
    reopened = measured["detailsOpenedUnderEntry"]
    assert reopened["marked"] == details["marked"], reopened
    _bars_lifted(reopened, "Details opened under the entry")
    _shimmering(reopened, "Details opened under the entry", together=False)
    assert reopened["layout"] == details_rest["layout"], "Details opened under the entry"

    # The dark page lifts rather than deepens (--viz-data-mark-hover-filter's two values).
    dark = measured["darkEntry"]
    assert dark["marked"] == [*_PYTHON_BARS, _PYTHON_ENTRY], dark
    assert dark["barStyle"][0]["filter"] != measured["entryName"]["barStyle"][0]["filter"], dark
    _bars_lifted(dark, "the dark page")
    _entry_marked(dark, "the dark page")

    # Reduced motion keeps the stronger, wider highlight and drops the motion.
    reduced = measured["reducedMotion"]
    assert reduced["marked"] == [*_PYTHON_BARS, _PYTHON_ENTRY], reduced
    _bars_lifted(reduced, "reduced motion")
    _entry_marked(reduced, "reduced motion")
    assert reduced["shimmer"]["on"] == [], reduced
    assert measured["reducedMotionTransitions"] == ["0s"], measured["reducedMotionTransitions"]

    _nothing(measured["other"], "Other")
