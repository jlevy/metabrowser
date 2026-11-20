"""File Overview's bars start at one place, a label column wide, and its legend wraps whole.

The bars stand to the right of a label column, in the totals rows (Files, Ignored, Total)
and in Details alike, and the column was 24% of the table, 184 px of the default pane's
767 px, to hold labels that are 129 px at the widest: the Documentation heading and the
Markdown, No extension, and Other types rows. ``--file-type-summary-label-width`` in ``file_type_summary.css`` is now that
width, measured in this browser's two font sets and recorded beside the constant. Where
the bars start is layout, and which labels fit it is the font's, so this needs a browser:
``tests/dom/overview-label-column-chrome.mjs`` serves a folder of eleven file-type
families, opens its Overview at window widths that put the section's host in each regime
of the rule, and reads each row's label column and bar. This holds that:

- every row of both tables, Files, Ignored, Total, and every Details row, ends its label
  column at one place and starts its bar at one place, with Details closed or open and
  with Files or Bytes, in both font sets, at every width;
- the column is the label width from the host content width the rule names (566 px), so
  the bars sit 56 px left of where 24% put them in the default pane, and below it a share
  of the table, 24%, or 28% in the narrow pane, which no width makes wider than it was;
- the bar starts the metric cell's padding, value, and gap after the column;
- in the default font set the Documentation heading and the Markdown, No extension, and
  Other types rows, the labels the width is sized for, each fit the column on one line, and
  in either set they stay inside it;
- a label longer than the column, words that wrap at a space and one word wider than the
  column, wraps inside the column: no bar moves and the table does not overflow;
- the legend names nine families and Other, and its entries wrap whole: each entry's dot
  and name on one line, in reading order, inside the legend, in two lines at most in the
  default pane and in more in a narrow one.

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``), and CI runs
it. The session leads a process group of its own, which Chrome and the server join, and the
whole group is stopped however it ends (tests/process_group.py).
"""

from __future__ import annotations

import json
import os
import socket
import sys
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest

from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_node

SESSION = Path(__file__).resolve().parent / "dom" / "overview-label-column-chrome.mjs"
# A server start, one Chrome, and five page loads, each read in two font sets, with Details
# closed and open and Files and Bytes (and two long labels at the default pane), took 21.2 s
# on a 10-core Mac at a load average of 18 (the 15 minutes' average 88, 2026-11-20), 2.3 s
# of it the server and Chrome's start. A cold Chrome start in CI has taken 28.2 s (the
# Overview alignment test, 2026-11-14), and the server's own start is bounded at 30 s
# inside the session, so the bound leaves room for both, and fires before the module's limit.
SESSION_TIMEOUT_S = 90
# The session's bound, its process group stopped after it (Chrome and the server are in
# it), and the profile's teardown (tests/process_group.py), with 10 s more for the rest of
# the setup; tests/test_process_group.py holds the sum under the module's limit.
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)
_METAB = Path(sys.executable).with_name("metab")

# Eleven families, so the legend names the nine largest and Other holds the last two, and an
# ignored build directory, so the Ignored row has segments too. Markdown is the largest, so
# its row is the first of Details' Documentation group.
_FAMILIES = {
    "md": 8,
    "py": 4,
    "json": 3,
    "yaml": 2,
    "ts": 2,
    "css": 1,
    "rs": 1,
    "go": 1,
    "html": 1,
    "sh": 1,
    "toml": 1,
}
_IGNORED = {"py": 2, "json": 3, "md": 1}

# The Overview host's width, its box, at which its content is the 566 px from which the
# label column is one width (the container rule at the end of file_type_summary.css), and
# the padding the host takes from its box on each side (overview.css's text inset is inside
# it): the host is 24 px short of its content each side.
_HOST_PADDING = 24
_ONE_WIDTH_FROM = 566
# The narrow pane's container condition in file_type_summary.css, on the same content.
_NARROW_UP_TO = 460
# What the label column was a share of the table, 24%, and in the narrow pane 28%.
_SHARE = 0.24
_NARROW_SHARE = 0.28
# How far left of where 24% put them the bars are in the default pane: the table is 767 px
# there, so 24% is 184 px, and the label width 130 px, and a gap of 50 leaves the claim room
# for a layout that shifts by a pixel or two.
_DEFAULT_PANE = "1280"
_MOVED_LEFT_PX = 50
# Sub-pixel layout, and the metric cell's rounding.
_TOLERANCE_PX = 0.6


def _served_folder(root: Path) -> None:
    (root / ".git").mkdir(parents=True)
    (root / ".gitignore").write_text("build/\n", encoding="utf-8")
    for extension, count in _FAMILIES.items():
        for n in range(1, count + 1):
            (root / f"f{n}.{extension}").write_text(f"x{n}\n", encoding="utf-8")
    # A file with no extension and one with a type no family claims, so Details has its two
    # special rows.
    (root / "LICENSE").write_text("x\n", encoding="utf-8")
    (root / "f1.zzq").write_text("x\n", encoding="utf-8")
    (root / "build").mkdir()
    for extension, count in _IGNORED.items():
        for n in range(1, count + 1):
            (root / "build" / f"g{n}.{extension}").write_text(f"y{n}\n", encoding="utf-8")


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _share_of(host: float) -> float:
    return _NARROW_SHARE if host - 2 * _HOST_PADDING <= _NARROW_UP_TO else _SHARE


def _check_columns(width: str, font: str, state: str, reading: dict[str, Any]) -> None:
    where = (width, font, state)
    rows = reading["rows"]
    # Files, Ignored, Total; and with Details open, its family rows and its type rows.
    assert len(rows) >= (3 if state.endswith("closed") else 8), (where, rows)
    assert reading["detailsOpen"] == state.endswith("open"), where
    table, host = reading["table"], reading["host"]
    label_width = reading["labelWidthToken"]
    content = host - 2 * _HOST_PADDING
    expected = label_width if content >= _ONE_WIDTH_FROM else _share_of(host) * table
    for row in rows:
        assert abs(row["labelWidth"] - expected) <= _TOLERANCE_PX, (where, row, expected)
        # The bar starts the metric cell's padding, value, and gap after the column.
        start = (
            row["labelWidth"]
            + reading["metricPadding"]
            + reading["valueWidth"]
            + reading["metricGap"]
        )
        assert abs(row["barLeft"] - start) <= _TOLERANCE_PX, (where, row, start)
    # Never wider than the share it replaces made it.
    assert max(row["labelWidth"] for row in rows) <= _share_of(host) * table + _TOLERANCE_PX, where
    # The table is its pane's, whatever its rows hold.
    assert reading["tableScroll"][0] <= reading["tableScroll"][1] + 1, (where, reading)
    if reading["detailsScroll"]:
        assert reading["detailsScroll"][0] <= reading["detailsScroll"][1] + 1, (where, reading)


def _check_legend(width: str, font: str, state: str, reading: dict[str, Any]) -> None:
    where = (width, font, state)
    legend = reading["legend"]
    entries = legend["entries"]
    # Nine families and Other, with the six families of one file each ordered by ID: CSS, Go,
    # HTML, and Rust are named, and Shell and TOML are in Other (file_type_legend.py).
    assert len(entries) == 10, (where, [entry["text"] for entry in entries])
    assert entries[-1]["text"].startswith("Other"), (where, entries[-1])
    for entry in entries:
        # A dot and its name on one line, so an entry never breaks between them, and an
        # entry is one line tall.
        assert abs(entry["dotMiddle"] - entry["labelMiddle"]) <= 1.5, (where, entry)
        assert entry["height"] <= 1.6 * min(e["height"] for e in entries), (where, entry)
        # Inside the legend, so a narrow pane wraps entries and clips none.
        assert entry["left"] >= legend["left"] - 0.5, (where, entry)
        assert entry["right"] <= legend["right"] + 0.5, (where, entry)
    assert legend["scroll"][0] <= legend["scroll"][1] + 1, (where, legend)
    # Reading order, in the entries' order: each is to the right of the one before it on a
    # line, or starts the next line at or left of where the one before it started.
    for before, after in pairwise(entries):
        if abs(after["top"] - before["top"]) <= 1.5:
            assert after["left"] >= before["right"] - 0.5, (where, before, after)
        else:
            assert after["top"] > before["top"], (where, before, after)
            assert after["left"] <= before["left"] + 0.5, (where, before, after)


def test_the_overview_bars_start_at_one_place_and_the_legend_wraps_whole_in_chrome(
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
    measured: dict[str, dict[str, dict[str, Any]]] = json.loads(
        result.stdout.strip().splitlines()[-1]
    )
    assert _DEFAULT_PANE in measured, list(measured)

    for width, fonts in measured.items():
        for font, reading in fonts.items():
            starts = set()
            for state_name in ("Files closed", "Files open", "Bytes closed", "Bytes open"):
                at = reading[state_name]
                _check_columns(width, font, state_name, at)
                _check_legend(width, font, state_name, at)
                starts.update(round(row["barLeft"], 1) for row in at["rows"])
            # Every row, in every state of both toggles, starts its bar at one place.
            assert len(starts) == 1 or max(starts) - min(starts) <= _TOLERANCE_PX, (
                width,
                font,
                sorted(starts),
            )

    for font, reading in measured[_DEFAULT_PANE].items():
        at = reading["Files open"]
        table = at["table"]
        # Where 24% of the table and the same cell padding, value, and gap started the bars.
        before = _SHARE * table + at["metricPadding"] + at["valueWidth"] + at["metricGap"]
        start = at["rows"][0]["barLeft"]
        assert before - start >= _MOVED_LEFT_PX, (font, before, start)
        # In the default pane the legend of ten entries is two lines at most.
        if font == "clean":
            tops = {entry["top"] for entry in at["legend"]["entries"]}
            assert len(tops) <= 2, (font, sorted(tops))

    # The labels the width is sized for fit on one line in the default font set, the bundled
    # face, from the host width the label width applies at. The system set's face is the
    # platform's, so there they are held inside the column and no more.
    for width, fonts in measured.items():
        for font, reading in fonts.items():
            at = reading["Files open"]
            for name in ("documentation", "markdown", "noExtension", "otherTypes"):
                label = at[name]
                assert label is not None and label["inside"], (width, font, name, label)
                if font == "clean" and at["host"] - 2 * _HOST_PADDING >= _ONE_WIDTH_FROM:
                    assert label["lines"] == 1, (width, font, name, label)
                    assert label["contentRight"] <= at["labelWidthToken"] + 0.5, (
                        width,
                        font,
                        name,
                        label,
                    )

    # A label wider than the column wraps inside it and moves nothing.
    for font, reading in measured[_DEFAULT_PANE].items():
        before = reading["Files open"]
        bars = {round(row["barLeft"], 1) for row in before["rows"]}
        for name in ("longWords", "longWord"):
            long = reading[name]
            where = (font, name, long)
            assert abs(long["cellWidth"] - before["labelWidthToken"]) <= _TOLERANCE_PX, where
            assert long["lines"] >= 2, where
            assert long["inside"], where
            assert long["tableScroll"][0] <= long["tableScroll"][1] + 1, where
            assert {round(bar, 1) for bar in long["bars"]} == bars, where
