"""The table view, laid out by headless Chrome.

``tests/dom/table-view-chrome.mjs`` serves a folder of delimited files, opens each in the
shell's own page, and measures what no browserless DOM computes:

- every row of a table is one height, of one line or two as its longest values need, and
  a value longer than its column is cut there, with its whole text in the shared tooltip,
  which a value shown whole does not get;
- null is drawn in the muted ink, a number right-aligned in tabular numerals, and a date
  in the monospaced face;
- the grid's own box scrolls, not the page, and its header stays at the box's top;
- default columns too many for the pane hide from the right with a note saying how many;
  columns the reader chose all show, and the first stays in place as they scroll
  sideways;
- each row height the view estimates before it measures (``ROW_HEIGHT_ESTIMATE_PX``) is
  within half a pixel of the height Chrome lays out, the threshold past which the view
  draws its first window again;
- a windowed table printed before its last page was read says on the page which rows it
  printed, and the toolbar is not printed; one read past ``PRINT_MAX_ROWS`` prints that
  many and says so;
- the browser's own history: a run of key presses past Chrome's bound on history calls
  (200 in 10 seconds) writes the place once, after the keys stop, so Enter still pushes
  the record's address; its Back link returns to the grid at the row and scroll the keys
  left; and a reload returns there too.
- the structured kind's Table tab draws a JSON record list and its nested values in the
  shared grid, and presents a mapping and a mixed list in the structured node table;
- an embedded Markdown Source excerpt reports its original line and preserves CRLF
  in the copy payload after expanding branches in the frontmatter table;
- the Files scan and a plugin's index status use the same type and spinner paint;
- a real SQLite table refreshes after a WAL-only commit and after its file is replaced at
  the same path.

What the address holds, which rows and cells exist, and what a key does run browserless
in ``tests/dom/table-view-session.js``. Without Chrome this skips (``require_chrome`` in
``tests/required_tools.py``), and CI runs it. ``TABLE_VIEW_SHOTS`` names a directory to
save a screenshot of each table to.
"""

from __future__ import annotations

import json
import os
import re
import socket
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_node

SESSION = Path(__file__).resolve().parent / "dom" / "table-view-chrome.mjs"
VIEW = (
    Path(__file__).resolve().parent.parent / "src/metabrowser/builtin_plugins/table/table-view.js"
)
# A server start, one Chrome, and seven opens and a reload, as the event-log views'
# session is bounded:
# a cold Chrome start in CI has taken 28.2 s (the Overview alignment test, 2026-11-14),
# and the server's own start is bounded at 30 s inside the session.
SESSION_TIMEOUT_S = 90
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)
_METAB = Path(sys.executable).with_name("metab")
LONG_VALUE = "a value long enough that no column of the table holds it on one line, " * 2
# Forty characters, the widest a column is, but of a glyph wider than the zero a column is
# measured in, as an ideograph is, so a one-line row cuts it.
WIDE_VALUE = "表" * 40


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _write_folder(root: Path) -> None:
    root.mkdir()
    # One line a row: no value is longer than its column in characters, but one is wider in
    # its glyphs, and a typed column's empty value is null.
    (root / "short.csv").write_text(
        "name,score,joined,label\n"
        "Ada,1.5,2020-01-02,first\n"
        f"Bob,,2021-03-04,{WIDE_VALUE}\n"
        "Cy,10,2019-12-31,third\n",
        encoding="utf-8",
    )
    # Two lines a row: a value holding a line break.
    (root / "long-text.csv").write_text(
        f'name,note\nAda,"first line\nsecond line\nthird line"\nBob,"{LONG_VALUE.strip()}"\n',
        encoding="utf-8",
    )
    many = ["n,word"] + [f"{index},word {index}" for index in range(1, 701)]
    (root / "many.csv").write_text("\n".join(many) + "\n", encoding="utf-8")
    printed = ["n,word"] + [f"{index},word {index}" for index in range(1, 2501)]
    (root / "printed.csv").write_text("\n".join(printed) + "\n", encoding="utf-8")
    header = ",".join(f"column_name_{index}" for index in range(1, 25))
    rows = [",".join(f"value {row}-{index}" for index in range(1, 25)) for row in range(1, 4)]
    (root / "wide.csv").write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")
    records = [
        {"name": "Ada", "tags": ["math", "engines"], "meta": {"born": 1815}},
        {"name": "Bob", "tags": []},
    ]
    (root / "records.json").write_text(json.dumps(records), encoding="utf-8")
    (root / "mapping.json").write_text('{"name": "metabrowser"}', encoding="utf-8")
    (root / "mixed.json").write_text('[{"name": "Ada"}, "Grace"]', encoding="utf-8")
    (root / "frontmatter.md").write_bytes(
        b"---\r\ntitle: " + b"unbroken" * 30 + b"\r\n"
        b"person: {section: {slot: {roles: [host,\r\n editor]}}}\r\n"
        b"---\r\n# Body\r\n"
        b"\r\n~~~yaml\r\nroles: [host, editor]\r\n~~~\r\n"
        b'\r\n```json\r\n{"roles": ["host", "editor"]}\r\n```\r\n'
    )


def _measure(tmp_path: Path, chrome_profile: Path) -> dict[str, Any]:
    chrome = require_chrome()
    root = tmp_path / "served"
    _write_folder(root)
    state = tmp_path / "state"
    state.mkdir()
    shots = os.environ.get("TABLE_VIEW_SHOTS")
    result = run_in_own_group(
        [
            require_node(),
            str(SESSION),
            str(_METAB),
            str(root),
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
    print(result.stdout, result.stderr)
    return json.loads(result.stdout.strip().splitlines()[-1])


def _check_rows_are_one_line_and_a_long_value_is_cut_with_its_tooltip(
    measured: dict[str, Any],
) -> None:
    short = measured["short"]
    assert short["lines"] == 1
    assert len(short["heights"]) == 1, "every row is one height"
    assert short["cellHeights"] == [short["line"]]
    assert short["cut"] == [WIDE_VALUE[:20]]
    assert short["tip"] == WIDE_VALUE
    assert short["wholeTip"] is None, "a value shown whole has no tooltip"


def _check_null_numbers_and_literals_are_painted_apart(measured: dict[str, Any]) -> None:
    paint = measured["short"]["paint"]
    assert paint["nullInk"] is True
    assert paint["textInk"] is True
    assert paint["numberAlign"] == "right"
    assert "tabular-nums" in paint["numberNumerals"]
    assert paint["dateFace"] is True


def _check_two_line_rows_are_one_height_and_clamp(measured: dict[str, Any]) -> None:
    two = measured["twoLines"]
    assert two["lines"] == 2
    assert len(two["heights"]) == 1
    assert two["cellHeights"] == [two["line"] * 2]
    assert len(two["cut"]) == 2, "three lines, and a value longer than two, are each cut"


def _check_the_header_stays_at_the_top_of_the_grids_own_box(measured: dict[str, Any]) -> None:
    sticky = measured["sticky"]
    assert sticky["scrolled"] == 2000
    assert sticky["boxScrolls"] is True
    assert sticky["paneStill"] is True, "the grid's box scrolls, not the page"
    assert sticky["boxInPane"] is True
    assert sticky["headAtTop"] is True
    assert sticky["headStill"] is True
    assert sticky["firstDrawn"] > 0, "the window moved with the scroll"


def _check_columns_fit_and_chosen_ones_pin_the_first(measured: dict[str, Any]) -> None:
    fit = measured["fit"]
    assert fit["note"] is not None and fit["note"].endswith("columns hidden to fit")
    hidden = int(fit["note"].split()[0])
    # The row's own column and the default columns that fit.
    assert fit["headers"] == 1 + 24 - hidden
    assert fit["overflows"] is False
    pinned = measured["pinned"]
    assert pinned["headers"] == 1 + 24
    assert pinned["note"] is None
    assert pinned["pinned"] is True
    assert pinned["scrolledLeft"] > 0
    assert pinned["firstStill"] is True
    assert pinned["secondMoved"] > 100


def _row_height_estimates() -> dict[int, float]:
    source = VIEW.read_text(encoding="utf-8")
    match = re.search(
        r"ROW_HEIGHT_ESTIMATE_PX = Object\.freeze\(\{ 1: ([\d.]+), 2: ([\d.]+) \}\)", source
    )
    assert match, "ROW_HEIGHT_ESTIMATE_PX is where the check reads it"
    return {1: float(match.group(1)), 2: float(match.group(2))}


def _check_the_row_height_estimates_are_what_chrome_lays_out(measured: dict[str, Any]) -> None:
    estimates = _row_height_estimates()
    for name, lines in (("short", 1), ("twoLines", 2)):
        (height,) = measured[name]["heights"]
        assert abs(height - estimates[lines]) <= 0.5, (lines, height, estimates[lines])


def _check_print_says_which_rows_it_printed(measured: dict[str, Any]) -> None:
    printed = measured["print"]
    assert printed["rows"] == 200, "every row held, and only those"
    assert printed["note"] == (
        "Rows 1 to 200 of 700. The rows after them were not read, so they are not printed."
    )
    assert printed["noteShown"] is True
    assert printed["toolbarShown"] is False
    bound = measured["printBound"]
    assert bound["held"] == 2500
    assert bound["rows"] == 2000, "PRINT_MAX_ROWS of them"
    assert bound["note"] == (
        "Rows 1 to 2,000 of 2,500. A printout holds at most 2,000 rows; "
        "search or filter for the ones to print."
    )


def _check_history_survives_a_run_of_keys(measured: dict[str, Any]) -> None:
    history = measured["history"]
    assert history["whilePressing"] == {"pushState": 0, "replaceState": 0}
    assert history["afterPause"] == {"pushState": 0, "replaceState": 1}
    row = history["row"]
    assert row > 0
    assert history["opened"] == f"Row {row + 1}"
    assert history["recordAddress"] == f"?record=%40{row + 1}"
    assert history["backAddress"] == ""
    assert history["gridShown"] is True
    assert history["tabStop"] == str(row)
    assert history["scrollTop"] > 0
    reload = measured["reload"]
    assert reload["tabStop"] == str(row)
    assert abs(reload["scrollTop"] - history["scrollTop"]) < 1


def _check_a_record_list_draws_its_records_and_their_trees(measured: dict[str, Any]) -> None:
    records = measured["records"]
    assert records["tab"] == "table"
    assert records["headers"] == ["#", "name", "tags", "meta"]
    assert records["rows"] == 2
    assert json.loads(records["copy"]) == {
        "name": "Ada",
        "tags": ["math", "engines"],
        "meta": {"born": 1815},
    }
    assert len(records["trees"]) == 2
    assert "math" in records["trees"][0] and "born" in records["trees"][1]
    assert measured["mappingTabs"] == ["table", "tree", "source"]
    assert measured["mappingRow"] == ["name", '"metabrowser"']
    assert measured["mappingCopy"] == '{"name": "metabrowser"}'
    assert measured["mixed"] == [["0", "Mapping (1)"], ["name", '"Ada"'], ["1", '"Grace"']]
    assert measured["branchLayout"] == {
        "usesTableTextSize": True,
        "iconAfterLabel": True,
        "iconCentered": True,
        "rowHeightMatches": True,
    }
    assert measured["initialFrontmatter"] == {
        "keys": ["title", "person", "section", "slot"],
        "pickers": 0,
        "slotOpen": "false",
    }
    assert measured["branchCopy"] == "{slot: {roles: [host,\r\n editor]}}"
    assert measured["inlineExpansion"] is True
    assert measured["frontmatterFits"] is True
    assert measured["frontmatter"] == {"firstLine": 3, "copy": "[host,\r\n editor]"}
    assert measured["fencedViews"] == {
        "firstLine": 13,
        "source": '{"roles": ["host", "editor"]}\r\n',
        "yamlTableStaysOpen": True,
        "jsonFallbackReturns": True,
    }


def test_the_table_view_in_chrome(tmp_path: Path, chrome_profile: Path) -> None:
    measured = _measure(tmp_path, chrome_profile)
    assert measured["progressPaint"] is True
    # Review A of #675, A11: the Live pill and the offer sit between the fit note and
    # Columns, and a hidden one keeps its slot, so neither moves those or the toolbar's
    # height, and with it the grid (Columns, then the fit note, then the toolbar height).
    toolbar = measured["toolbar"]
    assert toolbar["pillLive"] is True, toolbar
    assert toolbar["live"] == toolbar["waiting"] == toolbar["offered"] == toolbar["taken"], toolbar
    assert measured["exceptions"] == []
    assert measured["sqliteRefresh"] is True
    assert measured["sqliteSearch"] is True
    _check_rows_are_one_line_and_a_long_value_is_cut_with_its_tooltip(measured)
    _check_null_numbers_and_literals_are_painted_apart(measured)
    _check_two_line_rows_are_one_height_and_clamp(measured)
    _check_the_header_stays_at_the_top_of_the_grids_own_box(measured)
    _check_columns_fit_and_chosen_ones_pin_the_first(measured)
    _check_the_row_height_estimates_are_what_chrome_lays_out(measured)
    _check_print_says_which_rows_it_printed(measured)
    _check_history_survives_a_run_of_keys(measured)
    _check_a_record_list_draws_its_records_and_their_trees(measured)
