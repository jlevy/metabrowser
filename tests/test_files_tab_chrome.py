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
- Group by and Show ignored are the row and the three filters wait in the closed drawer;
  the row fits the default pane at its widest, under every Group by value with Clear and
  the chevron's badge showing, and the badge leaves Show ignored out; Group by's rows read
  as its trigger does, and its open menu's letters choose them while T stays Quick
  Search's with the menu closed; every key that opens a menu focuses its checked row,
  Escape and a choice that closes it give focus back to its trigger, and a pick in File
  type keeps focus on its row through the bar's rebuilds ("Keys in a Menu"); and the
  keyboard numbers follow what is on screen ("Grouping the Files Tree");
- in a narrower pane the row wraps by the toolbar rule, at every width from the narrowest
  in both font sets, read in Tab order, its numbers working, and the closed drawer adding
  nothing to it ("Navigation Toolbars Wrap");
- each File type section's heading starts on its tree's row inset and names its section
  and tree, Documentation first, and a folder opened in a section lists its group's
  files only;
- each section heading's tally sits beside its name after the separator, its dot one
  space's advance after the name, on its one line at the default pane and the 180 px
  minimum, its numeral at a count's numeral weight, and the section and its tree are
  named by the heading's words without the dot ("Heading Tallies"); at 180 px a name cut
  short shows its whole in its tooltip, and a whole one shows none ("Tooltips Add
  Information");
- a file written into a folder open in a section refreshes the sections in place, keeping
  that folder open, the scroll position, the focused row, and the heading, whose tally
  counts the new file;
- with the grouped requests held, a choice reads on the trigger in its click and takes
  the request its press asked for ahead; past the quiet period the tree dims to
  ``--loading-dim-opacity`` and the scan row says "Grouping by file type…", while the
  trigger does not breathe and a row already dimmed is not dimmed twice; a refresh waits
  for the sections on their way,
  and a reveal made meanwhile lands once they paint;
  and a newer choice, or No grouping, ends the wait at once ("Grouping the Files Tree",
  Waiting);
- a folder's chevron and a file's type icon take one slot, `--tree-icon-slot`, from the
  row's content edge, each glyph centred in it, so the names after them start on one
  column ("One Glyph Size", mb-hmv7).

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
_LIB_FILES = 12


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
    # A note beside the code, so src stands in Documentation and in Code.
    (root / "src" / "notes.md").write_text("# Notes\n", encoding="utf-8")
    # A folder two levels down, which the session opens and then writes a file into.
    (root / "src" / "lib").mkdir()
    for n in range(1, _LIB_FILES + 1):
        (root / "src" / "lib" / f"k{n:02d}.py").write_text(f"k{n}\n", encoding="utf-8")


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

    # Group by and Show ignored are the row; the three filters are in the drawer, which
    # starts closed and inert (mb-sogv, mb-x1h6).
    row = measured["row"]
    assert row["row"] == ["menu:group", "filter-check", "nav-filter-bar-end"], row
    assert row["drawer"] == ["recency", "types", "size"], row
    assert row["drawerOpen"] == "false" and row["drawerInert"] is True, row
    # The row fits the default pane at its widest, a filter set so Clear and the badge
    # show, under every Group by value: nothing overflows or is clipped, and the row's gap
    # is left between Show ignored and Clear. "No grouping" is the widest trigger, with
    # 1.89 px to spare on 2026-11-15 (the measurements are beside
    # `.nav-filter-bar-end > .chip-badge` in styles.css).
    for group, fit in measured["rowFit"].items():
        assert fit["content"] <= fit["row"], (group, fit)
        assert not fit["triggerClipped"] and not fit["checkClipped"], (group, fit)
        assert fit["spare"] >= 0, (group, fit)
        assert fit["clear"] and fit["badge"] == "1", (group, fit)
    assert [fit["trigger"] for fit in measured["rowFit"].values()] == [
        "No grouping",
        "By age",
        "By file type",
    ], measured["rowFit"]
    # Show ignored off alone: Clear shows, since it resets every filter, and the badge does
    # not count it, since the row shows it.
    off = measured["ignoredOff"]
    assert off["clear"] and off["badge"] is None, off
    # In a narrower pane the row wraps by the toolbar rule (tests/dom/nav-toolbar-wrap.mjs
    # says what it holds): at every width from the narrowest, 179 px, to 420, in both font
    # sets, with no filter set and with one set under each Group by value, nothing is cut,
    # it is one line exactly while its controls fit, it breaks in order and as late as it
    # can with Clear and the chevron last and at the line's end, and its lines are the
    # toolbar's line height and gap apart, the closed drawer adding nothing.
    wrap = measured["wrap"]
    assert set(wrap) == {
        f"{state}, {fonts}"
        for state in ("no filter", "No grouping", "By age", "By file type")
        for fonts in ("clean", "system")
    }, sorted(wrap)
    for case, verdict in wrap.items():
        assert verdict["failures"] == [], (case, verdict["failures"][:10])
        assert verdict["tokens"] == {"gap": 6, "line": 24}, (case, verdict["tokens"])
        # Group by leads at every width, and the narrowest pane wraps the row.
        assert verdict["narrowest"][0] == ["group"], (case, verdict["narrowest"])
        assert len(verdict["narrowest"]) >= 2, (case, verdict["narrowest"])
    # The default pane holds the row on one line in the default font set, at its widest.
    for state in ("no filter", "No grouping", "By age", "By file type"):
        assert wrap[f"{state}, clean"]["oneLineFrom"] <= 299, (state, wrap)
    assert measured["themesAlike"], "the themes lay the row out alike"
    # At the narrowest, a filter set, the row is three lines, read in Tab order; the numbers
    # still open Group by and, with the drawer, File type; and the drawer closes back to the
    # lines with no gap left standing.
    narrow = measured["narrow"]
    assert narrow["stops"] == ["group", "showIgnored", "clear", "drawer"], narrow
    assert narrow["lines"] == 3 and narrow["readInTabOrder"], narrow
    assert narrow["height"] == 3 * 24 + 2 * 6 + 2 * 6 + 1, narrow
    assert measured["narrowKeyOne"] == {"menu": "group", "drawerOpen": "false"}
    assert measured["narrowKeyThree"] == {"menu": "types", "drawerOpen": "true"}
    assert measured["narrowOpen"]["height"] > narrow["height"], measured["narrowOpen"]
    assert measured["narrowClosed"]["height"] == narrow["height"], measured["narrowClosed"]
    # A folder's chevron and a file's icon are one slot wide, from the row's content edge,
    # each glyph centred in it, and the names after them start on one column (mb-hmv7). At
    # 16 px the names started at 22 px; the slot is 14 px since, so they start at 20.
    slots = measured["slots"]
    assert slots["token"] == "14px", slots
    for kind, glyph in (("folder", 12), ("file", 14)):
        slot = slots[kind]
        assert slot["slot"] == 14 and slot["fromInset"] == 0, (kind, slot)
        assert slot["glyph"] == glyph and _close(slot["glyphFromSlot"], (14 - glyph) / 2), (
            kind,
            slot,
        )
        assert slot["name"] == 14 + slot["gap"] == 20, (kind, slot)

    # A tree row's tooltip leaves out what the row shows, its name, a file's size, and the
    # total a folder's chip holds, and gives the exact date and a folder's other total
    # (mb-8mpo). The row's chips here are sizes.
    tips = measured["treeTips"]
    assert tips["file"] == {
        "chip": "size",
        "visible": True,
        "size": False,
        "count": False,
        "lines": 1,
        "name": False,
    }, tips
    assert tips["folder"] == {
        "chip": "size",
        "visible": True,
        "size": False,
        "count": True,
        "lines": 2,
        "name": False,
    }, tips

    # 1 is Group by; the drawer's filters keep their numbers while it is closed, and 3
    # opens the drawer with File type's menu.
    assert measured["keyOneOpens"] == {"menu": "group", "drawerOpen": "false"}
    # Group by's rows read as its closed trigger does (mb-4mir).
    assert measured["groupRows"] == ["No grouping", "By age", "By file type"]
    # With the menu open from 1, A, T, and N choose its rows and close it; with the menu
    # closed, T is Quick Search and chooses nothing (mb-ibo4).
    letters = measured["letters"]
    assert letters["a"]["trigger"] == "By age" and letters["a"]["sections"] > 0, letters
    assert letters["t"]["trigger"] == "By file type" and letters["t"]["sections"] > 1, letters
    assert letters["n"] == {"trigger": "No grouping", "open": None, "sections": 0}, letters
    assert all(state["open"] is None for state in letters.values()), letters
    assert measured["closedT"] == {
        "focus": "combobox",
        "trigger": "No grouping",
        "open": None,
        "sections": 0,
    }
    # Every key that opens a menu focuses its checked row: the numbers, and ↓ and Enter on
    # a trigger. Escape, and a letter's choice that closes the menu, give focus back to the
    # trigger (mb-spqw).
    assert measured["focus"] == {
        "one": "group: No grouping, checked",
        "oneEscaped": "group trigger",
        "one before a": "group: No grouping, checked",
        "a": "group trigger",
        "one before t": "group: By age, checked",
        "t": "group trigger",
        "one before n": "group: By file type, checked",
        "n": "group trigger",
        "three": "types: Any type, checked",
        "threeEscaped": "types trigger",
        "two": "recency: Any age, checked",
        "twoEscaped": "recency trigger",
        "arrowDown": "group: No grouping, checked",
        "arrowDownEscaped": "group trigger",
        "enter": "group: No grouping, checked",
        "enterEscaped": "group trigger",
    }, measured["focus"]
    # Enter on a File type row picks it and the menu stays open; through the bar's rebuilds
    # as the filter answers, focus stays on that row, checked, and unchecked again.
    row = measured["typesRow"]
    assert row.startswith("types: ") and not row.endswith("checked"), row
    assert measured["typesPicked"] == f"{row}, checked", measured
    assert measured["typesUnpicked"] == row, measured
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
    tallies = [
        "10 files",
        f"{len(_CODE) * 3 + _LIB_FILES} files",
        "6 files",
        "1 file",
        "3 files",
    ]
    # Each heading's tally sits beside its name after the separator, never at the far end,
    # with its numeral bold at the numbers' weight and its words regular, and the dot
    # hidden from assistive technology (docs/design-system.md, "Heading Tallies").
    assert [section["tally"] for section in sections] == [f" · {tally}" for tally in tallies]
    for index, section in enumerate(sections):
        assert "group-heading" in section["headingClasses"], section
        assert _close(section["fromRowInset"], 0), section
        assert section["namesItsTree"], section
        assert section["divider"] == (0 if index == 0 else 1), section
        assert _close(section["tallyFromLabel"], 0), section
        # One space's advance at the tally's size: the tally keeps its spaces.
        assert 2 < section["dotFromLabel"] < 6, section
        assert section["tallyToEnd"] > 100, section
        assert section["lines"] == 1, section
        assert not section["nameCut"] and section["tallyWhole"], section
        assert section["weights"] == {
            "label": "700",
            "tally": "400",
            "figure": section["numeralWeight"],
        }, section
        assert section["numeralWeight"] == "700", section
        assert section["dotHidden"], section
    # A section and its tree read the heading's words, the dot left out. Chrome's name
    # carries the label register's capitals today; the contract is the words, so case is
    # not compared.
    expected_names = [
        f"{label} {tally}".casefold()
        for label, tally in zip(
            ["Documentation", "Code", "Data", "Archives", "Media"], tallies, strict=True
        )
    ]
    names = measured["byTypeNames"]
    assert [(name["section"] or "").casefold() for name in names] == expected_names, names
    assert [(name["tree"] or "").casefold() for name in names] == expected_names, names
    # At the narrowest pane, 180 px, each heading is still its one line, as tall as at the
    # default width, with its tally whole beside the name.
    narrow = measured["byTypeNarrow"]
    assert [section["tally"] for section in narrow] == [s["tally"] for s in sections]
    for wide, section in zip(sections, narrow, strict=True):
        assert section["lines"] == 1, section
        assert _close(section["headingHeight"], wide["headingHeight"]), (wide, section)
        assert section["tallyWhole"], section
        assert _close(section["tallyFromLabel"], 0), section
        assert 2 < section["dotFromLabel"] < 6, section
        assert section["tallyToEnd"] >= -TOLERANCE, section
    # There, a name cut short shows its whole in its tooltip, and a whole one shows none.
    assert measured["sectionTips"] == {
        "cut": {"cut": True, "visible": True, "text": "Documentation"},
        "whole": {"cut": False, "visible": False, "text": None},
    }, measured["sectionTips"]
    # A folder opened inside Code lists Code's files only (src/lib, inside it, stays closed).
    code = measured["codeFiles"]
    assert len(code) == len(_CODE) * 3, code
    assert {path.rsplit(".", 1)[1] for path in code} == set(_CODE), code
    # Keys that close and open Code's copy of src, which Documentation also holds, keep
    # focus on Code's copy.
    assert measured["focusAfterClose"] == {
        "section": "type:code",
        "path": "src",
        "expanded": "false",
    }
    assert measured["focusAfterOpen"] == {"section": "type:code", "path": "src", "expanded": "true"}
    # A file written into src/lib, open inside Code's src, refreshes the sections in place:
    # src/lib stays open with the new file in it, and the scroll position and the focused
    # row inside it are kept.
    refresh = measured["refresh"]
    focused = "type:code|file:src/lib/k06.py"
    assert refresh["before"]["focused"] == focused and refresh["before"]["scrollTop"] > 0, refresh
    assert not refresh["before"]["written"], refresh
    assert refresh["after"] == {**refresh["before"], "written": True}, refresh
    # Code's heading is the one it had, its tally counting the new file beside its name.
    assert measured["refreshedHeading"] == {
        "kept": True,
        "tally": f" · {len(_CODE) * 3 + _LIB_FILES + 1} files",
    }, measured["refreshedHeading"]
    # No grouping is the one Files tree again.
    assert measured["ungrouped"] == {"sections": 0, "trees": ["Files"]}

    # Waiting, with every grouped request held at the page (docs/design-system.md,
    # "Grouping the Files Tree"). The trigger reads the choice in the click that made it,
    # while the request its press asked for ahead is still on its way and a file has
    # changed since; the choice takes that request rather than asking again.
    waiting = measured["waiting"]
    assert waiting["chosenInFrame"] == "By file type", waiting
    assert waiting["requestsForChoice"] == {"prefetched": 1, "afterChoice": 1}, waiting
    # Past the quiet period the tree dims to the wait's own token and the scan row says what
    # is happening. The trigger does not breathe: only primary ink does ("Refreshing
    # Content"), and it reads the choice in the link's ink on the accent ground, so while
    # the choice waits it is drawn exactly as once its sections have painted, in both
    # themes. Measured 2026-11-15: 4.15:1 in light and 5.98:1 in dark, where breathing took
    # it to 3.03:1 and 4.45:1 at its dimmest (mb-xlla).
    slow = waiting["slow"]
    assert slow["trigger"] == "By file type" and not slow["breathing"], slow
    assert slow["progress"] == "Grouping by file type…" and slow["progressShown"], slow
    assert slow["treeOpacity"] == slow["loadingDimToken"] < 1, slow
    assert slow["busy"] == "true" and slow["sections"] == 0, slow
    assert waiting["triggerInk"] == waiting["triggerInkAfter"], waiting
    for theme, ink in waiting["triggerInk"].items():
        assert ink["active"] == "true" and ink["rest"] > ink["breathingDimmest"], (theme, ink)
    # A row already dimmed, as an ignored file's is, is held at the tree's dimmest under the
    # wait rather than dimmed twice: 0.45 of 0.45 drew its name at 0.2025, 1.54:1, where at
    # rest and now under the wait it is 0.45, 2.86:1.
    dimmed = slow["dimmedToken"]
    assert waiting["ignoredUnderDim"]["opacity"] == pytest.approx(dimmed, abs=0.001), waiting
    assert waiting["ignoredAtRest"]["opacity"] == pytest.approx(dimmed, abs=0.001), waiting
    assert waiting["ignoredUnderDim"]["contrast"] == waiting["ignoredAtRest"]["contrast"], waiting
    # The refresh the changed file asks for waits for the sections on their way, and
    # follows them once they paint.
    assert waiting["refreshWaits"] == {"requests": 1, "held": 1}, waiting
    painted = waiting["painted"]
    assert painted["sections"] > 1 and painted["progress"] is None, painted
    assert painted["treeOpacity"] == 1 and painted["busy"] == "false", painted
    assert waiting["refreshedAfter"], waiting
    # A reveal made while the sections were on their way lands once they paint: its row,
    # two folders down in Code, is shown and selected.
    assert waiting["revealed"] == {"shown": True, "row": True}, waiting
    # A newer choice cancels the load on its way, and No grouping ends the wait at once;
    # the answers left behind arrive and paint nothing.
    assert waiting["chosen"] == {"type": "By file type", "age": "By age", "none": "No grouping"}
    assert waiting["typeLoading"]["progress"] == "Grouping by file type…", waiting
    assert waiting["ageLoading"]["progress"] == "Grouping by age…", waiting
    for state in (waiting["cancelled"], waiting["stale"]):
        assert state["trigger"] == "No grouping" and state["sections"] == 0, state
        assert state["progress"] is None and state["treeOpacity"] == 1, state
        assert state["busy"] == "false" and not state["breathing"], state
