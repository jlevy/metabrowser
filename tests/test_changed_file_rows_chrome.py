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

``tests/dom/diff-summary-chrome.mjs`` opens the Diff summary in the running app, on a served
patch five folders deep and on one of 600 files, and this holds (mb-hi4l):

- the tree's first level starts one indentation step, ``--tree-indent``, in from the header,
  its chevron from the header's chevron and its name from the header's words, and each level
  one step more, at every depth to five;
- opened, the tree has no scroll bar and no scroll of its own: it is as tall as its rows, in
  the page's flow;
- on 600 files only the window's view of the tree and the overscan are in the document, at
  the top and with the page scrolled to its middle, where every row in view is drawn;
- the header starts collapsed with no tree, and the arrows move the focus ring along the rows.

Before, the first level started 4 px in from the header, with nested levels 16 px apart, and
the tree scrolled in a box at most 60vh tall.
Where text starts and what a hover paints are layout and paint, so this needs a browser; it
skips without Chrome (``require_chrome`` in ``tests/required_tools.py``), and CI runs it.
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

SESSION = Path(__file__).resolve().parent / "dom" / "changed-file-rows-chrome.mjs"
# A cold Chrome start in CI has taken 28.2 s (tests/test_github_pull_header_chrome.py); the
# measurement itself took under 2 s on a Mac.
SESSION_TIMEOUT_S = 48
# The bound, the session's process group stopped after it, and the profile's teardown
# (tests/process_group.py), with 10 s more for the rest of the setup.
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)
APP_SESSION = Path(__file__).resolve().parent / "dom" / "diff-summary-chrome.mjs"
# A server start, one Chrome, and two patches opened took 6 s on a Mac at a load average of
# 16; a cold Chrome start in CI has taken 28.2 s, and the server's start is bounded at 30 s
# inside the session.
APP_TIMEOUT_S = 90
APP_LIFECYCLE_S = APP_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
_METAB = Path(sys.executable).with_name("metab")
_DIFF_SUMMARY = (
    Path(__file__).resolve().parent.parent / "src/metabrowser/builtin_plugins/diff/diff-summary.js"
)
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


def _patch(paths: list[str], added: frozenset[str] = frozenset()) -> str:
    """A git patch that adds a line to each of *paths*, or adds the file, for those in *added*."""

    out = []
    for path in paths:
        if path in added:
            out.append(
                f"diff --git a/{path} b/{path}\nnew file mode 100644\n"
                f"index 0000000..0000001\n--- /dev/null\n+++ b/{path}\n@@ -0,0 +1 @@\n+new\n"
            )
        else:
            out.append(
                f"diff --git a/{path} b/{path}\nindex 0000001..0000002 100644\n"
                f"--- a/{path}\n+++ b/{path}\n@@ -1 +1,2 @@\n x\n+y\n"
            )
    return "".join(out)


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@pytest.mark.timeout(APP_LIFECYCLE_S + 10)
def test_the_diff_summary_opens_in_the_pages_flow_on_the_trees_step(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    served = tmp_path / "served"
    served.mkdir()
    # Five levels: a folder in a folder, four deep, each also holding files.
    nested = [
        f"{folder}{name}{n}.txt"
        for folder, name in (("", "top"), ("a/", "f"), ("a/b/", "g"), ("a/b/c/", "h"))
        for n in range(1, 4)
    ]
    nested += [f"a/b/c/d/k{n}.txt" for n in range(1, 4)] + ["a/b/c/d/new.md"]
    (served / "nested.patch").write_text(
        _patch(nested, frozenset({"a/b/c/d/new.md"})), encoding="utf-8"
    )
    # 600 files three folders deep: a tree some thirty times the window's height.
    long = [f"m{n % 23}/n{n % 5}/o{n % 2}/f{n:03d}.txt" for n in range(600)]
    (served / "long.patch").write_text(_patch(long), encoding="utf-8")
    state = tmp_path / "state"
    state.mkdir()
    result = run_in_own_group(
        [require_node(), str(APP_SESSION), str(_METAB), str(served), str(_free_port()), str(state)],
        timeout_s=APP_TIMEOUT_S,
        env={**os.environ, "CHROME_BIN": chrome, "CHROME_PROFILES": str(chrome_profile)},
    )
    assert not result.timed_out, (
        f"the session ran past {APP_TIMEOUT_S} s: {result.stderr or result.stdout}"
    )
    assert result.returncode == 0, result.stderr or result.stdout
    # Shown with the failure: every measurement, and each phase's time.
    print(result.stdout, result.stderr)
    measured: dict[str, Any] = json.loads(result.stdout.strip().splitlines()[-1])
    assert measured["errors"] == [], measured["errors"]
    overscan_found = re.search(
        r"export const SUMMARY_ROWS_OVERSCAN = (\d+);", _DIFF_SUMMARY.read_text(encoding="utf-8")
    )
    assert overscan_found is not None
    overscan = int(overscan_found[1])

    collapsed, opened = measured["nested"]["collapsed"], measured["nested"]["open"]
    # The header starts collapsed, with no tree.
    assert collapsed["expanded"] == "false" and not collapsed["mounted"], collapsed
    assert opened["expanded"] == "true", opened
    step = opened["step"]
    header = opened["header"]
    rows = opened["rows"]
    # Every depth from one to five, each one step in from the one above it, and the first one
    # step in from the header: its chevron from the header's chevron, its name from its words.
    assert {row["level"] for row in rows} >= {1, 2, 3, 4, 5}, rows
    for row in rows:
        assert abs(row["lead"] - header["chevron"] - step * row["level"]) <= TOLERANCE, (
            row,
            header,
        )
        assert abs(row["name"] - header["words"] - step * row["level"]) <= TOLERANCE, (
            row,
            header,
        )

    # Opened, the tree has no scroll bar and no scroll of its own: it is as tall as its rows,
    # in the page's flow, on both patches.
    for name in ("nested", "long"):
        body = measured[name]["open"]["body"]
        assert body["overflowY"] == "clip", (name, body)
        assert body["ownScroll"] == 0 and body["scrollBar"] == 0, (name, body)
        assert body["height"] >= body["listHeight"] > 0, (name, body)
        assert body["listHeight"] == body["rowCount"] * opened["rowHeight"], (name, body)
    # A short tree draws every row; a long one the window's view and the overscan, at the top
    # and scrolled to its middle, where every row in view is drawn.
    assert opened["drawn"] == opened["body"]["rowCount"], opened
    long_open = measured["long"]["open"]
    window_rows = 900 // int(opened["rowHeight"]) + 2 * overscan + 1
    assert long_open["body"]["rowCount"] > 600, long_open["body"]
    assert 0 < long_open["drawn"] <= window_rows, long_open["drawn"]
    scrolled = measured["long"]["scrolled"]
    assert scrolled["missing"] == 0 and scrolled["inView"] >= scrolled["viewRows"] - 1, scrolled
    assert scrolled["drawn"] <= scrolled["viewRows"] + 2 * overscan + 1, scrolled

    # The keys are the tree's: Down moves the focus ring along the rows.
    keys = measured["keys"]
    assert [key["id"] for key in keys] == ["a/", "a/b/", "a/b/c/", "a/b/c/d/"], keys
    for key in keys:
        assert key["focusVisible"] and key["ring"] == RING, key
