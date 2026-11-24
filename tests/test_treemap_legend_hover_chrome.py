"""The Treemap's file-type legend and its shared hover, under Chrome's own pointer.

The Treemap shows File Overview's legend under its tally bars, and its cells, bars, and
legend share one hover (docs/design-system.md, "Folder Treemap"). Which marks a handle
names, the tooltip it shows, and when the hover is put away run browserlessly in
``tests/dom/treemap-legend-session.js`` (``cli-ui-treemap-legend.tryscript.md``). What only a
browser can say is held here: ``tests/dom/treemap-legend-hover-chrome.mjs`` serves a folder of
seven families with a folder of Python files and an ignored build folder, opens the
Treemap tab while the folder's first view still holds its first paint, and moves Chrome's
pointer onto the Python entry, off the legend, and onto a
Python file's cell. This holds that:

- the legend is File Overview's, under the tally bars, on a row one line tall, the line it
  holds while it has no entries, so the map does not move when they arrive;
- the entry marks every cell painted Python's color, the folder of Python files among
  them, the family's segment in every tally row, and itself, and nothing else, with the
  family's counts in a tooltip under the entry;
- a marked cell's pixels, and no other cell's, are copied onto the marks canvas, which
  lifts and does not grow, since a cell's area is its value; a marked bar grows twice
  over; the entry's dot lifts and its name reads at 4.5:1 or better;
- the entry's hover runs no cell's shimmer, only the bars' and the dot's, however many
  cells the family has (the cost at maxCells is measured beside the rule in
  builtin_plugins/folder/styles.css);
- a cell marks itself and its family's entry alone, with its own tooltip, and it alone
  of the cells shimmers, on the hover anchor over it, its sheen under the labels;
- every shimmer animates opacity alone, and no layout box in the view moves.

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

SESSION = Path(__file__).resolve().parent / "dom" / "treemap-legend-hover-chrome.mjs"
# A server start, one Chrome, a page load, a switch to the Treemap tab, and five readings,
# each taken once the shell's tooltip appear delay or fade (TOOLTIP_APPEAR_DELAY and
# TOOLTIP_FADE_OUT in static/app.js) and the view's transitions have settled, took 7.6 s on
# a 10-core Mac at a load average near 7 (2026-11-18). A cold Chrome start in CI has taken
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

# Seven families at the top, a folder of Python files the map draws as a Python folder, and
# an ignored build folder holding three families, so every tally row has segments.
_FAMILIES = {"md": 8, "py": 4, "json": 3, "yaml": 2, "ts": 2, "css": 1, "rs": 1}
_LIB = {"py": 3}
_IGNORED = {"py": 2, "json": 3, "md": 1}
_PYTHON_ENTRY = "legend family:python"
_PYTHON_BARS = ["Files family:python", "Ignored family:python", "Total family:python"]


def _files(folder: Path, counts: dict[str, int], stem: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for extension, count in counts.items():
        for n in range(1, count + 1):
            (folder / f"{stem}{n}.{extension}").write_text(f"{stem}{n}\n", encoding="utf-8")


def _served_folder(root: Path) -> None:
    (root / ".git").mkdir(parents=True)
    (root / ".gitignore").write_text("build/\n", encoding="utf-8")
    _files(root, _FAMILIES, "f")
    _files(root / "lib", _LIB, "m")
    _files(root / "build", _IGNORED, "g")


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _legend_in_place(reading: dict[str, Any], label: str) -> None:
    # Markdown and Python tie on files and bytes, so the family ID orders them
    # (file_type_legend.py), as it does CSS and Rust. All seven families clear the share
    # floor and the legend's limit, so they are all named and nothing is left for Other.
    assert reading["legend"] == [
        "Markdown",
        "Python",
        "JSON",
        "TypeScript",
        "YAML",
        "CSS",
        "Rust",
    ], (label, reading["legend"])
    assert reading["legendName"] == "Share of Total (30 files)", (label, reading)
    assert reading["legendUnderBars"] and reading["legendRowHeld"], (label, reading)


def _nothing(reading: dict[str, Any], label: str) -> None:
    _legend_in_place(reading, label)
    assert reading["marked"] == [], (label, reading)
    assert reading["canvas"]["liftedPixels"] == 0 and reading["anchor"] is None, (label, reading)
    assert reading["barsAtRest"], (label, reading)
    assert reading["shimmer"]["on"] == [], (label, reading)
    assert reading["tooltip"] is None, (label, reading)


def _cells_lifted(reading: dict[str, Any], label: str) -> None:
    """Every marked cell's pixels, and only theirs, lifted on the marks canvas, not grown."""

    canvas = reading["canvas"]
    assert canvas["sampled"] >= 20 and canvas["liftedPixels"] > 0, (label, reading)
    assert canvas["markedLifted"] and canvas["copied"], (label, reading)
    assert canvas["unmarkedClear"], (label, reading)
    lift = reading["lift"]
    assert lift["scaleY"] == 1 and lift["scaleX"] == 1 and lift["filter"] != "none", (
        label,
        reading,
    )


def _entry_marked(reading: dict[str, Any], label: str) -> None:
    (entry,) = reading["entries"]
    assert entry["dotFilter"] != "none" and entry["inkContrast"] >= 4.5, (label, reading)


def test_the_treemap_legend_hovers_its_familys_cells_in_chrome(
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

    # The Treemap was chosen on the staged bar, before the Overview had its data and before
    # any bar was committed to the pane, and it is the tab in front at the commit (mb-s588;
    # the orders a choice can arrive in run in tests/dom/view-tab-hold-session.js).
    assert measured["earlyChoice"] == {"staged": True, "committedTabs": 0, "front": "overview"}
    assert measured["frontAtCommit"] == "Treemap", measured

    rest = measured["atRest"]
    _nothing(rest, "at rest")

    entry = measured["entry"]
    _legend_in_place(entry, "the Python entry")
    cells = [mark for mark in entry["marked"] if mark.startswith("cell ")]
    # Every cell of the family's color and no other. The folder of Python files is not
    # among them: a nested folder's header and frame are neutral (mb-lzmo).
    assert cells == entry["familyCells"] and "cell lib (family)" not in cells, entry
    assert entry["marked"] == [*_PYTHON_BARS, _PYTHON_ENTRY, *cells], entry
    _cells_lifted(entry, "the Python entry")
    assert entry["anchor"] is None, entry
    assert entry["barStyle"] and all(
        style["scaleY"] == 2 and style["scaleX"] == 1 and style["filter"] != "none"
        for style in entry["barStyle"]
    ), entry
    assert entry["barsAtRest"], entry
    _entry_marked(entry, "the Python entry")
    # No cell shimmers: only the bars and the entry's dot, whatever the family's count.
    assert sorted(entry["shimmer"]["on"]) == sorted([*_PYTHON_BARS, _PYTHON_ENTRY]), entry
    assert entry["shimmer"]["animates"] == ["opacity"], entry
    assert entry["tooltip"] == "9 files · 27 B" and entry["tooltipBelowEntry"], entry
    assert entry["layout"] == rest["layout"], "the Python entry moved the view"
    _nothing(measured["left"], "off the legend")

    cell = measured["cell"]
    assert cell["marked"] == [_PYTHON_ENTRY, "cell f1.py (self)"], cell
    _cells_lifted(cell, "the f1.py cell")
    anchor = cell["anchor"]
    assert anchor["name"] == "cell f1.py (self)" and anchor["sheenUnderLabel"], cell
    assert anchor["scaleY"] == 1 and anchor["scaleX"] == 1, cell
    _entry_marked(cell, "the f1.py cell")
    assert sorted(cell["shimmer"]["on"]) == sorted(cell["marked"]), cell
    assert cell["tooltip"] is not None and cell["tooltip"].startswith("f1.py 3 B modified "), cell
    assert cell["layout"] == rest["layout"], "the f1.py cell moved the view"
    _nothing(measured["cellLeft"], "off the cell")
