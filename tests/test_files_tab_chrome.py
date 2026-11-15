"""The Files tab's filter bar, filter menus, and Group by sections, in headless Chrome.

``tests/dom/files-tab-chrome.mjs`` serves a folder with dozens of file types, opens the
File type menu in a tall window and a short one, resizing under it and reopening it, and
opens the Modified within menu in both. This judges what it measured against
``docs/design-system.md``, "Groups in a Menu" and "Menu Height":

- a group heading starts on the menu's row inset, the edge its rows' check column starts
  on, and names its rows as an ARIA group;
- an open menu is its rows' natural height up to 16 rows, and stops 8 px short of the
  window's bottom edge, measured again when it opens and when the window resizes;
- the Modified within menu, with few rows, keeps its natural height in both windows;
- Group by is the row's one control, the filters wait in the closed drawer, and the
  keyboard numbers follow what is on screen ("Grouping the Files Tree");
- each File type section's heading starts on its tree's row inset and names its section
  and tree, Documentation first, and a folder opened in a section lists its group's
  files only.

Where text starts and how tall a box is drawn are layout, so this needs a browser; it
skips without Chrome (``require_chrome`` in ``tests/required_tools.py``), and CI runs it.
The height rule itself, ``menuMaxHeight``, is pinned without a browser in
``tests/dom/filter-controls-behavior.js``.
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

SESSION = Path(__file__).resolve().parent / "dom" / "files-tab-chrome.mjs"
# A server start, one Chrome, a page load, and six menu measurements took 4.4 s on a Mac at
# a load average near 9. A cold Chrome start in CI has taken 28.2 s (the Overview alignment
# test, 2026-11-14), and the server's own start is bounded at 30 s inside the session, so
# the bound leaves room for both, and fires before the module's limit.
SESSION_TIMEOUT_S = 90
# The longest the test can take: the session's bound, its process group stopped after it
# (Chrome and the server are in it), and the profile's teardown (tests/process_group.py),
# with 10 s more for the rest of the setup; tests/test_process_group.py holds the sum under
# the module's limit.
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)
_METAB = Path(sys.executable).with_name("metab")

# The rule's two constants, as filter-controls.js states them.
MAX_ROWS = 16
WINDOW_MARGIN = 8
# Layout rounds to fractions of a pixel; a menu off by more than this is a different menu.
TOLERANCE = 0.5

# Enough types that the File type menu has headed groups of families and more rows than
# either window shows, the way a real project's does.
_CODE = ("py", "js", "ts", "css", "html", "rs", "go", "java", "rb", "sh", "sql", "lua")
_DOCS = ("md", "txt", "rst", "adoc")
_DATA = ("json", "yaml", "toml", "ini", "csv", "xml")
_MEDIA = ("png", "jpg", "mp3")


def _served_folder(root: Path) -> None:
    for directory in ("src", "docs", "data", "media", "archives"):
        (root / directory).mkdir(parents=True)
    for ext in _CODE:
        for n in range(1, 4):
            (root / "src" / f"m{n}.{ext}").write_text(f"x{n}\n", encoding="utf-8")
    for ext in _DOCS:
        for n in range(1, 3):
            (root / "docs" / f"d{n}.{ext}").write_text(f"# d{n}\n", encoding="utf-8")
    for ext in _DATA:
        (root / "data" / f"c.{ext}").write_text("{}\n", encoding="utf-8")
    for ext in _MEDIA:
        (root / "media" / f"m.{ext}").write_bytes(b"x")
    (root / "archives" / "a.zip").write_bytes(b"x")
    (root / "README.md").write_text("# Fixture\n", encoding="utf-8")


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _close(actual: float, expected: float) -> bool:
    return abs(actual - expected) <= TOLERANCE


def _row(menu: dict[str, Any]) -> float:
    heights = menu["rowHeights"]
    assert isinstance(heights, list) and len(heights) == 1, (
        f"every row of a menu is one height: {heights}"
    )
    return float(heights[0])


def _cap(menu: dict[str, Any]) -> float:
    """The row cap: 16 rendered rows and the panel's padding and border."""

    return MAX_ROWS * _row(menu) + float(menu["frame"])


def _room(menu: dict[str, Any]) -> float:
    """The room between the menu's top and the window's bottom edge, less the margin."""

    return float(menu["windowHeight"]) - WINDOW_MARGIN - float(menu["top"])


def test_the_files_filter_menus_in_chrome(tmp_path: Path, chrome_profile: Path) -> None:
    chrome = require_chrome()
    root = tmp_path / "served"
    _served_folder(root)
    state = tmp_path / "state"
    state.mkdir()
    # The session leads a process group of its own, which Chrome and the server join, and
    # the whole group is stopped however it ends; the profile is the fixture's to remove.
    result = run_in_own_group(
        [require_node(), str(SESSION), str(_METAB), str(root), str(_free_port()), str(state)],
        timeout_s=SESSION_TIMEOUT_S,
        env={**os.environ, "CHROME_BIN": chrome, "CHROME_PROFILES": str(chrome_profile)},
    )
    assert not result.timed_out, (
        f"the session ran past {SESSION_TIMEOUT_S} s: {result.stderr or result.stdout}"
    )
    assert result.returncode == 0, result.stderr or result.stdout
    # Shown with the failure: every measurement, and each phase's time.
    print(result.stdout, result.stderr)
    measured: dict[str, Any] = json.loads(result.stdout.strip().splitlines()[-1])

    # The gear menu's title, labelled row, and foot start on one inset.
    gear = measured["gear"]
    assert gear["title"] is not None and gear["title"] == gear["labelledRow"] == gear["foot"], gear

    tall = measured["typesTall"]
    # The headings: "Groups", then one per taxonomy group with families in this folder.
    assert [heading["text"] for heading in tall["headings"]][:3] == [
        "Groups",
        "Documentation",
        "Code",
    ]
    for heading in tall["headings"]:
        # On the rows' inset, the edge the check column starts on, not the label column.
        assert _close(heading["fromRowInset"], 0), heading
        assert heading["namesItsGroup"], heading
        # Every group follows the "Any type" row, so each draws its own 1 px divider.
        assert heading["divider"] == 1, heading
    # The label column is well inside the inset, so the heading's place is not an accident
    # of a row with no check or icon.
    assert tall["labelFromRowInset"] >= 12, tall

    # Tall: 16 rows, which leaves room under the menu, and the rest scrolls.
    assert _cap(tall) < _room(tall), tall
    assert _close(tall["height"], _cap(tall)), tall
    assert tall["scrollHeight"] > tall["clientHeight"], tall
    # Scrolling, the menu keeps its separator's 1px rule.
    assert tall["separators"] == [1], tall

    # Short, whether the window shrank under the open menu or it opened there: the room
    # sets the height, and the menu stops the margin short of the window's edge.
    for short in (measured["typesShortResized"], measured["typesShortOpened"]):
        assert _room(short) < _cap(short), short
        assert _close(short["height"], _room(short)), short
        assert short["bottom"] <= short["windowHeight"] - WINDOW_MARGIN + TOLERANCE, short
        assert short["scrollHeight"] > short["clientHeight"], short

    # Grown back, the row cap applies again.
    again = measured["typesTallAgain"]
    assert _close(again["height"], _cap(again)), again

    # The age menu has few rows: its natural height, every row shown, in both windows.
    for age in (measured["ageTall"], measured["ageShort"]):
        assert age["headings"] == [], age
        assert age["scrollHeight"] <= age["clientHeight"], age
        assert _close(age["height"], age["rows"] * _row(age) + age["frame"]), age
    assert measured["ageTall"]["height"] == measured["ageShort"]["height"]

    # Group by is the row's one control; the filters and Show ignored are in the drawer,
    # which starts closed and inert (mb-sogv).
    row = measured["row"]
    assert row["row"] == ["menu:group", "nav-filter-bar-end"], row
    assert row["drawer"] == ["recency", "types", "size", "showIgnored"], row
    assert row["drawerOpen"] == "false" and row["drawerInert"] is True, row
    # The numbers follow what is on screen: 1 is Group by while the drawer is closed, and
    # once it is open its filters follow, so 3 is File type.
    assert measured["keyOneOpens"] == {"menu": "group", "drawerOpen": "false"}
    assert measured["keyThreeOpens"] == {"menu": "types", "drawerOpen": "true"}

    # File type sections: Documentation first, each headed in the menu group pattern at
    # the tree's row inset, naming its section and its tree, a divider above all but the
    # first. Other holds nothing in this folder, so it is not shown.
    sections = measured["byType"]
    assert [section["label"] for section in sections] == [
        "Documentation",
        "Code",
        "Data",
        "Archives",
        "Media",
    ]
    assert [section["count"] for section in sections] == [
        "9 files",
        "36 files",
        "6 files",
        "1 file",
        "3 files",
    ]
    for index, section in enumerate(sections):
        assert "group-heading" in section["headingClasses"], section
        assert _close(section["fromRowInset"], 0), section
        assert section["namesItsTree"], section
        assert section["divider"] == (0 if index == 0 else 1), section
    # A folder opened inside Code lists Code's files only.
    code = measured["codeFiles"]
    assert len(code) == len(_CODE) * 3, code
    assert {path.rsplit(".", 1)[1] for path in code} == set(_CODE), code
    # No grouping is the one Files tree again.
    assert measured["ungrouped"] == {"sections": 0, "trees": ["Files"]}
