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
  one step more, at every depth to five, in a patch's toolbar (the commit page's and the pull
  request header's are held by ``tests/test_git_commit_summary_chrome.py`` and
  ``tests/test_github_pull_header_chrome.py``);
- opened, the tree has no scroll bar and no scroll of its own: it is as tall as its rows, in
  the page's flow;
- on 600 files only the window's view of the tree and the overscan are in the document, at
  the top and with the page scrolled to its middle, where every row in view is drawn;
- the header starts collapsed with no tree, and the arrows move the focus ring along the rows.

Before, the first level started 4 px in from the header, with nested levels 16 px apart, and
the tree scrolled in a box at most 60vh tall.

The served folder is a Git repository too, and on the patch and on a commit's page, where
the diff's toolbar holds the layout control alone, the session reads the chrome around the
diff, and this holds:

- the toolbar draws no rule under itself, and the first file card, with its own border,
  starts the cards' gap, 12 px, below it (docs/design-system.md, "Diff Layout Control";
  mb-a073); before, a 1px rule ran 12 px above the card's border;
- in the Diff summary's header, the Files totals, and the Commits tally, every number is a
  bold number, ``.summary-number``, at 700, and every word, parenthesis, and separator is at
  400, the line's weight ("Count Summaries Bold Their Numbers"; mb-roa9); before, the
  numbers were at 400, and only the change stats were bold.
Where text starts and what a hover paints are layout and paint, so this needs a browser; it
skips without Chrome (``require_chrome`` in ``tests/required_tools.py``), and CI runs it.
"""

from __future__ import annotations

import json
import math
import os
import re
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_git, require_node

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


def _git(root: Path, *args: str) -> str:
    """Run git in *root* with a pinned identity and none of the caller's Git settings."""

    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env.update(
        {
            "GIT_AUTHOR_NAME": "Fixture Author",
            "GIT_AUTHOR_EMAIL": "author@example.invalid",
            "GIT_COMMITTER_NAME": "Fixture Committer",
            "GIT_COMMITTER_EMAIL": "committer@example.invalid",
            "GIT_CONFIG_GLOBAL": str(root / ".gitconfig-absent"),
            "GIT_CONFIG_SYSTEM": str(root / ".gitconfig-absent"),
        }
    )
    done = subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True, env=env
    )
    return done.stdout.strip()


def _commit_of_several_files(root: Path) -> str:
    """Make *root* a repository whose second commit adds one file, deletes one, and changes two."""

    for path in ("src/one.py", "src/two.py", "docs/three.md", "old.txt"):
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text("x\n", encoding="utf-8")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", "src", "docs", "old.txt")
    _git(root, "commit", "-q", "-m", "base")
    for path in ("src/one.py", "src/two.py"):
        (root / path).write_text("x\ny\n", encoding="utf-8")
    (root / "src/four.py").write_text("new\n", encoding="utf-8")
    (root / "old.txt").unlink()
    _git(root, "add", "-A", "src", "old.txt")
    _git(root, "commit", "-q", "-m", "change")
    return _git(root, "rev-parse", "HEAD")


# The weight of a count summary's bold number, `--weight-bold`, and of its words, the line's.
BOLD, REGULAR = "700", "400"


def _counts_read_bold(runs: list[dict[str, Any]] | None, where: str) -> list[str]:
    """What breaks the count-summary rule in one line's runs of text, as Chrome computes them.

    Every number is a bold number, `.summary-number`, at `--weight-bold`, inline with its
    words rather than an item of a flex line, which would part them by its gap; every other
    run, a word, a parenthesis, or a separator, is at the line's regular weight; a change
    stat or an age keeps the weight of its own primitive.
    """

    if not runs:
        return [f"{where}: no line"]
    broken = []
    for run in runs:
        if run["own"]:
            continue
        if run["number"]:
            if run["weight"] != BOLD:
                broken.append(f"{where}: number {run['text']!r} at {run['weight']}")
            if re.search(r"flex|grid", run["within"]):
                broken.append(f"{where}: number {run['text']!r} is an item of a {run['within']}")
        elif re.search(r"\d", run["text"]):
            broken.append(f"{where}: {run['text']!r} holds a number outside a bold number")
        elif run["weight"] != REGULAR:
            broken.append(f"{where}: word {run['text']!r} at {run['weight']}")
    if not any(run["number"] for run in runs):
        broken.append(f"{where}: no bold number")
    return broken


# The token each status's letter takes (static/styles.css, `.file-change-status`).
STATUS_INK = {
    "added": "--git-status-added",
    "removed": "--git-status-deleted",
    "modified": "--git-status-modified",
    "renamed": "--git-status-renamed",
}


def _header_inks(paint: dict[str, Any]) -> list[str]:
    """What breaks the Diff summary header's inks in one theme, as Chrome computes them.

    Each status is its letter in its status's ink, each dot between the groups and each
    comma between the statuses the muted punctuation, the dots hidden from a screen reader,
    and the file count, its words, and the statuses' counts the line's own ink; the
    accessible name says it all in words (mb-vb51).
    """

    where = f"commit's Diff summary, {paint['theme']}"
    tokens = paint["tokens"]
    broken = []
    # Distinct inks, or a letter at the line's ink would pass as its status's.
    inks = [tokens[name] for name in ("--text", "--muted", *STATUS_INK.values())]
    if len(set(inks)) != len(inks):
        broken.append(f"{where}: the tokens are not distinct, {tokens}")
    if [(text, status) for text, status, _ in paint["letters"]] != [
        ("A", "added"),
        ("D", "removed"),
        ("M", "modified"),
    ]:
        broken.append(f"{where}: letters {paint['letters']}")
    for text, status, color in paint["letters"]:
        if color != tokens[STATUS_INK[status]]:
            broken.append(f"{where}: {text} at {color}, not {STATUS_INK[status]}")
    if [(text, hidden) for text, hidden, _ in paint["marks"]] != [
        ("·", "true"),
        (",", None),
        (",", None),
        ("·", "true"),
    ]:
        broken.append(f"{where}: marks {paint['marks']}")
    for text, _, color in paint["marks"]:
        if color != tokens["--muted"]:
            broken.append(f"{where}: {text!r} at {color}, not --muted")
    if paint["words"] != tokens["--text"]:
        broken.append(f"{where}: the words at {paint['words']}, not --text")
    for text, color in paint["numbers"]:
        if color != tokens["--text"]:
            broken.append(f"{where}: number {text} at {color}, not --text")
    if (
        paint["label"]
        != "4 files changed: 1 added, 1 deleted, 2 modified; 3 lines added, 1 deleted"
    ):
        broken.append(f"{where}: label {paint['label']!r}")
    return broken


def _toolbar_draws_no_rule(toolbar: dict[str, Any], where: str) -> list[str]:
    """What breaks the diff toolbar's rule: no line under it, and the cards' gap to the first card."""

    broken = []
    if toolbar["rule"].split()[-1] != "0px":
        broken.append(f"{where}: the toolbar draws a rule, {toolbar['rule']}")
    if toolbar["position"] != "static":
        broken.append(f"{where}: the toolbar is {toolbar['position']}")
    if abs(toolbar["gapToCard"] - float(toolbar["cardMarginTop"].removesuffix("px"))) > TOLERANCE:
        broken.append(f"{where}: the first card is {toolbar['gapToCard']} px below the toolbar")
    if toolbar["cardRule"] != "1px":
        broken.append(f"{where}: the first card draws no border of its own")
    return broken


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
    # The served folder is a repository too, for a commit's page (mb-a073, mb-roa9).
    require_git()
    commit = _commit_of_several_files(served)
    state = tmp_path / "state"
    state.mkdir()
    result = run_in_own_group(
        [
            require_node(),
            str(APP_SESSION),
            str(_METAB),
            str(served),
            str(_free_port()),
            str(state),
            commit,
        ],
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
    # The rows a view of the page's height can show part of, the overscan each way, and the
    # row that takes Tab; the view is the page's, which new-headless Chrome draws shorter than
    # the window it was asked for.
    window_rows = math.ceil(long_open["viewHeight"] / long_open["rowHeight"]) + 1 + 2 * overscan + 1
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

    # The diff's toolbar draws no rule under itself: the first card's border, the cards' gap
    # below it, is the line, on a patch, where the toolbar leads with the Diff summary, and
    # on a commit's page, where it holds the layout control alone (mb-a073). Before, both
    # drew a 1px rule 12 px above the card's.
    patch = measured["nested"]["collapsed"]["chrome"]
    commit_page = measured["commit"]
    assert patch["toolbar"]["holds"] == ["diff-summary", "diff-layout-control"], patch
    assert commit_page["toolbar"]["holds"] == ["diff-layout-control"], commit_page
    broken = _toolbar_draws_no_rule(patch["toolbar"], "patch") + _toolbar_draws_no_rule(
        commit_page["toolbar"], "commit"
    )
    # Every number of a count summary is bold and every word regular (mb-roa9): the Diff
    # summary's header on the patch and on the commit's page, the Files totals, and the
    # Commits tally. Before, only the line totals, the change stats, were bold.
    broken += _counts_read_bold(patch["counts"]["summary"], "patch's Diff summary")
    broken += _counts_read_bold(patch["counts"]["files"], "Files totals")
    broken += _counts_read_bold(commit_page["counts"]["summary"], "commit's Diff summary")
    broken += _counts_read_bold(commit_page["counts"]["commits"], "Commits tally")
    assert broken == [], (broken, patch, commit_page)
    # The commit's header bolds its file count and each status's: 4 files changed, 1 A, 1 D,
    # 2 M.
    numbers = [run["text"] for run in commit_page["counts"]["summary"] if run["number"]]
    assert numbers == ["4", "1", "1", "2"], commit_page["counts"]["summary"]
    # It reads "4 files changed · 1 A, 1 D, 2 M · +3 −1", each letter in its status's ink and
    # its dots and commas muted, in both themes (mb-vb51). Before, it read "4 changed files (1
    # added, 1 removed, 2 modified)", its statuses in words and all of them muted.
    paints = commit_page["paint"]
    assert [paint["theme"] for paint in paints] == ["light", "dark"], paints
    assert all(paint["text"] == "4 files changed·1 A, 1 D, 2 M·+3−1" for paint in paints), paints
    inks = [problem for paint in paints for problem in _header_inks(paint)]
    assert inks == [], (inks, paints)
    # The two themes ink the letters apart, so each was read in its own.
    assert paints[0]["letters"] != paints[1]["letters"], paints
