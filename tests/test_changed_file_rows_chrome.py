"""The two trees of a change set's files draw one row, in headless Chrome.

A pull request's changed files under its Pulls row and a multi-file diff's Diff summary are
two plugins' trees on one model (``static/changed-files-tree.js``), and their rows are one
class set, the shell's ``.changed-file-row`` (docs/design-system.md, "Diff Summary").
``tests/dom/changed-file-rows-chrome.mjs`` mounts both with their production modules on one
list of files, under the shell's and both plugins' stylesheets, and measures a folder's row
and a file's in each. This holds that they are one row past the depth's indent:

- the same height, the content on the tree's 12 px row inset past the 2px bar, the
  chevron or change letter at the content's edge and as wide, the name and the counts'
  end at one place, one gap, one type, and the square corner;
- the same hover ground, and the 2px focus ring drawn 2px inside the row;
- a folder whose sums leave a file out says so in its tooltip with the counts alone, since
  its name is on the row, and its accessible name says both.

Before the shared rows the Diff summary's content started 2 px left of the Pulls tree's
(its rows' padding was 8 px, the Pulls rows' 10), and a folder's tooltip repeated its name.
Where text starts and what a hover paints are layout and paint, so this needs a browser; it
skips without Chrome (``require_chrome`` in ``tests/required_tools.py``), and CI runs it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_node

SESSION = Path(__file__).resolve().parent / "dom" / "changed-file-rows-chrome.mjs"
# A cold Chrome start in CI has taken 28.2 s (tests/test_github_pull_header_chrome.py); the
# measurement itself took under 2 s on a Mac.
SESSION_TIMEOUT_S = 48
# The bound, the session's process group stopped after it, and the profile's teardown
# (tests/process_group.py), with 10 s more for the rest of the setup.
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)
# Layout rounds to fractions of a pixel; a row off by more than this is a different row.
TOLERANCE = 0.5
RING = "solid 2px -2px"


def _same(first: dict[str, Any], second: dict[str, Any]) -> list[str]:
    """The measurements two rows differ in, past their depth's indent."""

    differ = []
    for key, value in first.items():
        if key in {"indent", "contentFromRow", "level"}:
            continue
        other = second[key]
        if isinstance(value, float | int) and isinstance(other, float | int):
            if abs(value - other) > TOLERANCE:
                differ.append(f"{key}: {value} against {other}")
        elif value != other:
            differ.append(f"{key}: {value!r} against {other!r}")
    inset = first["contentFromRow"] - first["indent"]
    other_inset = second["contentFromRow"] - second["indent"]
    if abs(inset - other_inset) > TOLERANCE:
        differ.append(f"inset: {inset} against {other_inset}")
    return differ


def test_both_trees_of_changed_files_draw_one_row_in_chrome(chrome_profile: Path) -> None:
    chrome = require_chrome()
    result = run_in_own_group(
        [require_node(), str(SESSION)],
        timeout_s=SESSION_TIMEOUT_S,
        env={**os.environ, "CHROME_BIN": chrome, "CHROME_PROFILES": str(chrome_profile)},
    )
    assert not result.timed_out, (
        f"the session ran past {SESSION_TIMEOUT_S} s: {result.stderr or result.stdout}"
    )
    assert result.returncode == 0, result.stderr or result.stdout
    # Shown with the failure: every measurement.
    print(result.stdout, result.stderr)
    measured: dict[str, Any] = json.loads(result.stdout.strip().splitlines()[-1])
    assert measured["errors"] == [], measured["errors"]
    rows = measured["rows"]
    pulls, summary = rows["pulls"], rows["summary"]
    # One list, one tree: the same rows in the same order, every folder open.
    assert (
        pulls["ids"]
        == summary["ids"]
        == [
            "docs/",
            "docs/new.md",
            "src/",
            "src/app.txt",
            "src/logo.png",
        ]
    ), rows
    for kind in ("folder", "file"):
        assert _same(pulls[kind], summary[kind]) == [], (kind, pulls[kind], summary[kind])
        # The content sits on the tree's 12px row inset, past the 2px bar.
        row = pulls[kind]
        assert abs(row["contentFromRow"] - row["indent"] - 12) <= TOLERANCE, row
        assert (row["bar"], row["radius"]) == ("2px", "0px"), row
    states = measured["states"]
    hover = states["pulls"]["docs/"]["hover"]
    for tree, by_row in states.items():
        for row_id, state in by_row.items():
            assert state["hover"] == hover != state["rest"]["background"], (tree, row_id, state)
            assert state["focus"]["focusVisible"], (tree, row_id, state)
            assert state["focus"]["outline"] == RING, (tree, row_id, state)
    # A folder's tooltip gives what its sums leave out, the counts alone; its accessible
    # name, which a screen reader hears in place of the row, says its name too.
    for tree in (pulls, summary):
        assert tree["tip"] == "1 file without line counts", tree
        assert tree["label"].startswith("src, 2 files"), tree
