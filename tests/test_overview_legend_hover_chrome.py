"""File Overview's legend hovers the bar segment it names, under Chrome's own pointer.

A legend entry is a second handle on its family's segment in the tally row the legend's
shares are of (docs/design-system.md, "Aggregate Distributions"). Which segment an entry
names, the tooltip it shows, and when the hover is put away run browserlessly in
``tests/dom/file-overview-session.js`` (``cli-ui-file-overview.tryscript.md``). What only a
browser can say is held here: ``tests/dom/overview-legend-hover-chrome.mjs`` serves a folder
of seven file-type families, so the legend names five and Other, and moves Chrome's pointer
onto an entry's name and then its dot, off the legend, onto the segment itself, and onto
Other, reading after each move the segments marked as hovered with their computed lift and
growth and the tooltip's words and place. This holds that:

- the entry's name and its dot each lift and grow the Total row's segment for that family,
  and no other, and show that segment's file count and byte size, the name the entry
  shows left out, centered on the entry and clear of it;
- moving from the name to the dot changes nothing, the tooltip included;
- moving off puts the tooltip and the segment's lift away;
- pointing at the segment lifts and grows the same segment alone, and shows the same
  counts under the family's name, centered on the segment and clear of it;
- Other draws nothing, and no legend entry is ever marked.

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
# A server start, one Chrome, a page load, and seven pointer moves, each read once the
# shell's tooltip appear delay or fade (TOOLTIP_APPEAR_DELAY and TOOLTIP_FADE_OUT in
# static/app.js) has settled, took 10.9 s on a 10-core Mac at a load average near 21
# (2026-11-17). A cold Chrome start in CI has taken 28.2 s (the Overview alignment test,
# 2026-11-14), and the server's own start is bounded at 30 s inside the session, so the
# bound leaves room for both, and fires before the module's limit.
SESSION_TIMEOUT_S = 90
# The session's bound, its process group stopped after it (Chrome and the server are in
# it), and the profile's teardown (tests/process_group.py), with 10 s more for the rest of
# the setup; tests/test_process_group.py holds the sum under the module's limit.
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)
_METAB = Path(sys.executable).with_name("metab")

# Seven families, so the legend names the five largest and Other holds the last two.
_FAMILIES = {"md": 8, "py": 4, "json": 3, "yaml": 2, "ts": 2, "css": 1, "rs": 1}


def _served_folder(root: Path) -> None:
    root.mkdir(parents=True)
    for extension, count in _FAMILIES.items():
        for n in range(1, count + 1):
            (root / f"f{n}.{extension}").write_text(f"x{n}\n", encoding="utf-8")


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


# The Python family's tooltip on its legend entry, which shows the name, and on its segment,
# which does not (docs/design-system.md, "Aggregate Distributions").
_PYTHON_TOOLTIP = {"legend": "4 files · 12 B", "segment": "Python 4 files · 12 B"}


def _python_hover(reading: dict[str, Any], label: str, anchor: str) -> None:
    """The Total row's Python segment alone lifted and grown, with its tooltip on *anchor*."""

    assert reading["marked"] == ["Total family:python"], (label, reading)
    (style,) = reading["markedStyle"]
    # Grown on the axis that carries no data, by --viz-hover-grow, and lifted by
    # --viz-data-mark-hover-filter (docs/design-system.md, "Hover Styles the Thing Under
    # the Pointer"); the width, which is the value, does not move.
    assert style["scaleY"] > 1 and style["scaleX"] == 1, (label, reading)
    assert style["filter"] != "none", (label, reading)
    assert reading["othersAtRest"], (label, reading)
    assert reading["legendMarked"] == 0, (label, reading)
    assert reading["tooltip"] == _PYTHON_TOOLTIP[anchor], (label, reading)
    placed = reading["tooltipOnAnchor"]
    # Centred on what the pointer is on, the legend entry or the segment, unless the
    # viewport's margin clamps it, and clear of it above or below.
    assert placed is not None and placed["anchor"] == anchor, (label, reading)
    assert placed["clear"], (label, reading)
    assert abs(placed["centerOffset"]) <= 1, (label, reading)


def _nothing(reading: dict[str, Any], label: str) -> None:
    assert reading["marked"] == [], (label, reading)
    assert reading["othersAtRest"], (label, reading)
    assert reading["legendMarked"] == 0, (label, reading)
    assert reading["tooltip"] is None, (label, reading)


def test_a_legend_entry_hovers_its_segment_in_chrome(tmp_path: Path, chrome_profile: Path) -> None:
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

    # TypeScript and YAML tie on both measures, so the family ID orders them
    # (file_type_legend.py).
    assert measured["legend"] == ["Markdown", "Python", "JSON", "TypeScript", "YAML", "Other"], (
        measured["legend"]
    )
    _nothing(measured["atRest"], "at rest")
    _python_hover(measured["entryName"], "the entry's name", "legend")
    _python_hover(measured["entryDot"], "the entry's dot", "legend")
    assert measured["entryDot"]["tooltipLeft"] == measured["entryName"]["tooltipLeft"], measured
    _nothing(measured["left"], "off the legend")
    _python_hover(measured["segment"], "the segment", "segment")
    # The same mark; the tooltip sits by what the pointer is on.
    assert measured["segment"]["marked"] == measured["entryName"]["marked"], measured
    _nothing(measured["segmentLeft"], "off the segment")
    _nothing(measured["other"], "Other")
