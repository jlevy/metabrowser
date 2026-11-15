"""A changed file's path shows the same in a diff's Diff summary as the server shows it.

The Pulls tab's tree of a pull request's files paints each path's ``display``, which the
``pull-files`` route writes with ``display_path``: control, format, and invisible characters
become U+FFFD (``invisible_chars.py``). A diff's manifest carries only paths, so the Diff
summary takes the display from ``displayPath`` in ``static/changed-files-tree.js``, the same
rule in the browser. This holds the two to one answer: every code point of every table the
rule reads and its neighbours, in each place a variation selector's base can put it, and the
paths a pull request's author could use to pass one name off as another.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from metabrowser.builtin_plugins.github.pull_files_route import display_path
from metabrowser.invisible_chars import (
    BLANK_BRAILLE,
    DEFAULT_IGNORABLE,
    FORMAT,
    SPACE_SEPARATORS,
    VARIATION_SELECTORS,
)
from tests.required_tools import require_node

REPO = Path(__file__).resolve().parents[1]
_DRIVER = """
const { changedFilesTree } = require("./tests/dom/changed-files-tree-fixture.js");
const tree = changedFilesTree();
let input = "";
process.stdin.on("data", (chunk) => { input += chunk; });
process.stdin.on("end", () => {
  process.stdout.write(JSON.stringify(JSON.parse(input).map((path) => tree.displayPath(path))));
});
"""

# Paths a pull request's author controls, each one passing for another name.
_PATHS = [
    "src/evil\u202egnp.js",
    "docs/zero\u200bwidth.md",
    "docs/README\u3164.md",
    "a\u00a0b/c\u200ad.txt",
    "\u2764\ufe0f.md",
    "README\ufe0f.md",
    "1\ufe0f\u20e3.txt",
    "x\ufe0f\u20e3.txt",
    "\ufe0fstart.md",
    "bell\u0007name.txt",
    "csi\u009bname.txt",
    "line\u2028break.md",
    "blank\u2800braille.md",
    "lone\ud800surrogate.md",
    "\u6f22\ufe00\u5b57.md",
    "plain/path.py",
    "",
]


def _code_points() -> list[int]:
    """Every code point the rule's tables name, with the one below and above each range."""

    ranges = [
        *DEFAULT_IGNORABLE,
        *VARIATION_SELECTORS,
        *FORMAT,
        *SPACE_SEPARATORS,
        (BLANK_BRAILLE, BLANK_BRAILLE),
        (0x00, 0x20),
        (0x7E, 0xA0),
    ]
    points = {point for low, high in ranges for point in range(max(0, low - 1), high + 2)}
    return sorted(point for point in points if point <= 0x10FFFF)


def _names() -> list[str]:
    names = list(_PATHS)
    for point in _code_points():
        ch = chr(point)
        # Alone, inside ASCII, after a printable non-ASCII base, after a space, doubled, and
        # as an emoji keycap's selector would sit.
        names += [ch, f"a{ch}b", f"\u2764{ch}", f" {ch}", f"{ch}{ch}", f"1{ch}\u20e3"]
    return names


def test_the_diff_summary_shows_a_path_as_the_server_does() -> None:
    node = require_node()
    names = _names()
    run = subprocess.run(
        [node, "-e", _DRIVER],
        input=json.dumps(names),
        capture_output=True,
        text=True,
        cwd=REPO,
        check=True,
    )
    shown = json.loads(run.stdout)
    differing = [
        (name.encode("unicode_escape").decode(), browser, server)
        for name, browser, server in zip(names, shown, map(display_path, names), strict=True)
        if browser != server
    ]
    assert differing == []


def test_a_bidi_control_and_a_zero_width_character_show_as_replacement() -> None:
    """The two a reviewer cannot see: one reorders the name, and one is not drawn."""

    node = require_node()
    run = subprocess.run(
        [node, "-e", _DRIVER],
        input=json.dumps(["src/evil\u202egnp.js", "docs/zero\u200bwidth.md"]),
        capture_output=True,
        text=True,
        cwd=REPO,
        check=True,
    )
    assert json.loads(run.stdout) == ["src/evil\ufffdgnp.js", "docs/zero\ufffdwidth.md"]
