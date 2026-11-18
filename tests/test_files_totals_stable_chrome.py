"""Nothing in the Files nav panel moves from first paint to settled, in headless Chrome.

The owner, 2026-11-16 (mb-h3hc): the "+ N ignored" line on the Files panel appeared
later, so the view shifted; "this should never happen. if something is slow it should be
laid out in a stable way with a progress box to show it is filling in". The ignored count
came with the server's pass over every file, half a second to seconds after the tree,
and as half of the totals line it took a second line in the default pane: the tree moved
down 19.5 px when it arrived, measured on this repository in Chrome on 2026-11-16.

The count is now a line of its own, the shell inlines the root's totals with its first
rows, and a line drawn without them holds the ignored line with the pending placeholder
(docs/design-system.md, "Navigation Metadata Line"). ``tests/dom/files-totals-stable-
chrome.mjs`` serves a folder with ignored files, the same with a longer tracked count,
and one with nothing ignored, each dated days back so that no age on the page changes its
label during the session (``_AGE_S``), and records each load frame by frame from the
document's start, in both themes, with the tally answered at once and held 2 s, in the
default pane and the narrowest. This judges it:

- from first paint, the first frame with rows shown, to the settled frame, no box in the
  navigation (the filter bar, each metadata line, the first twelve rows) moves or changes
  size, and Chrome records no layout shift without input from the document's start. In
  the narrowest pane the filter bar wraps to two lines as it is filled, and the tree
  under it moved 30 px, the rows with it when they were shown first (mb-a5pa), so the
  tree holds its first paint until the bar is filled (styles.css, the rule after
  ``.nav-filter-bar``). Every shift counts, the move into first paint too: CI reported
  that one up to 111 ms after the frame it moved into (mb-kiqm), so no window after first
  paint can set it apart;
- the line is its settled self from first paint: the ignored count's line for the folder
  with ignored files, and no ignored line for the folder with none;
- a shell drawn before the walk finished the root, its inlined totals taken out and the
  event stream, whose snapshot carries them in the root's entry, held until first paint,
  holds the ignored line from first paint and no load moves: the count fills it in
  place, in the narrowest pane too, where it is cut short on its one line rather than
  wrapped; a first tally answered as the server does mid-walk, provisional and counting
  nothing ignored yet, does not release it; and for a folder with nothing ignored it
  keeps its box as "No ignored files";
- the tracked and ignored lines' tooltips, each its line's whole phrase, show only while
  the line is cut short, and in the narrowest pane the ignored line is;
- the tree's hold is bounded: a load whose ``filter-controls.js`` fails never fills the
  bar, and the tree is shown at the bound in the hold's rule, which this reads from
  styles.css, with nothing moved.

The browserless states of the line are pinned by
``tests/golden/cli-ui-tree-summary-line.tryscript.md``. Where text sits is computed
layout, so this needs a browser; it skips without Chrome (``docs/e2e-testing.md``), and
CI runs it. The session leads a process group of its own, which Chrome and both servers
join, and the whole group is stopped however it ends (``tests/process_group.py``).
Each server searches for a port from the one after the last server's and the session
reads the one it took from its banner, so a port taken meanwhile moves it, not the test.
"""

from __future__ import annotations

import json
import os
import re
import socket
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_node

SESSION = Path(__file__).resolve().parent / "dom" / "files-totals-stable-chrome.mjs"
STYLES = Path(__file__).resolve().parent.parent / "src" / "metabrowser" / "static" / "styles.css"
_METAB = Path(sys.executable).with_name("metab")
# Three server starts, one Chrome, and thirty-one loads, eighteen of them holding the tally
# 2 s and two the event stream 1.5 s (eight more hold it only until first paint, inside
# their tally's 2 s): the session took 71 s, and the test 98 s, on a 10-core Mac at a
# load average near 30. A cold Chrome start in CI has taken 28.2 s, and each server's
# start is bounded at 30 s inside the session.
SESSION_TIMEOUT_S = 240
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)
# Layout rounds to fractions of a pixel; a box off by more than this has moved.
TOLERANCE_PX = 0.5
# The tree's insertion is marked a moment before its first style, where the hold's bound
# starts, and an animation's start is a frame's time: at most a few frames either way.
BOUND_SLACK_MS = 50
# The folder with ignored files: "41 files (1.5 MB)" over "+ 2,000 ignored (133.5 MB)".
# As one line the two wrapped in the narrowest pane, so main's code moved the tree there;
# the tracked count is short enough to stay one line at 180 px in a wider font set than
# the Mac's, so the check measures the ignored line and not that (the design system's
# "The Files totals" names it). The wide folder is the same with "1,201 files (45.8 MB)",
# whose two halves outgrew one line in the default pane on main's code, the owner's case;
# it is loaded only there. The files are sparse, so they take no disk.
_TRACKED_FILES = 40
_WIDE_TRACKED_FILES = 1200
_TRACKED_BYTES = 40_000
_IGNORED_FILES = 2000
_IGNORED_BYTES = 70_000
# How old the served trees are dated. An age is drawn in buckets, and the main view's
# folder header shows the folder's: written as the test starts, a folder read "just now"
# for its first minute, then "1m ago", "2m ago" and on. The header refreshes its summary a
# debounce after the event stream's snapshot (`startFolderHeaderSubscription` in app.js,
# `ROLLUP_WATCH_DEBOUNCE_MS`), so a load in which a folder's age changed its label redrew
# it, and where the label's width changed the right-aligned summary moved (mb-j4ts,
# 2026-11-17). On CI it was the clean folder in "none unknown slow 180px dark", twice:
# "278 B 41 files just now" became "... 1m ago", the summary's left edge moved 7.9 px, and
# Chrome scored 1.77e-5. On a Mac it was the folder with ignored files in "ignored unknown
# slow 180px dark", in 2 of 5 runs, scored 1.2e-4 with the header's root crumb. Three days
# old, every age reads "3d" from 2.5 to 3.5 days (`AGE_TIERS` in formatters.js rounds),
# twelve hours either side of a session bounded at SESSION_TIMEOUT_S. So nothing here sees
# the header's values move when one of them changes width; whether the age should hold a
# slot against that is mb-v4u6.
_AGE_S = 3 * 24 * 60 * 60


def _sparse(path: Path, size: int) -> None:
    with path.open("wb") as handle:
        handle.truncate(size)


def _ignoring(root: Path, tracked: int) -> Path:
    (root / ".git").mkdir(parents=True)
    (root / ".gitignore").write_text("build/\n", encoding="utf-8")
    (root / "src").mkdir()
    for index in range(tracked):
        _sparse(root / "src" / f"m{index:04d}.py", _TRACKED_BYTES)
    (root / "build").mkdir()
    for index in range(_IGNORED_FILES):
        _sparse(root / "build" / f"o{index:04d}.bin", _IGNORED_BYTES)
    (root / "README.md").write_text("# Ignoring\n", encoding="utf-8")
    return root


def _dated(root: Path, when: float) -> None:
    """Give *root* and everything under it the access and modification time *when*."""

    for path in [root, *root.rglob("*")]:
        os.utime(path, (when, when))


def _folders(root: Path) -> tuple[Path, Path, Path]:
    ignoring = _ignoring(root / "ignoring", _TRACKED_FILES)
    wide = _ignoring(root / "wide", _WIDE_TRACKED_FILES)
    clean = root / "clean"
    (clean / ".git").mkdir(parents=True)
    (clean / "src").mkdir()
    for index in range(40):
        (clean / "src" / f"m{index:02d}.py").write_text(f"x = {index}\n", encoding="utf-8")
    (clean / "README.md").write_text("# Clean\n", encoding="utf-8")
    when = time.time() - _AGE_S
    for folder in (ignoring, wide, clean):
        _dated(folder, when)
    return ignoring, wide, clean


def _free_port() -> int:
    """A port to start the first server's search from; the banner says where it went."""

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _still(result: dict[str, Any]) -> list[str]:
    return [f"{key} {px} px" for key, px in result["moved"].items() if px > TOLERANCE_PX]


def _hold_bound_ms() -> float:
    """The bound on the tree's hold, read from its rule in styles.css."""

    css = STYLES.read_text(encoding="utf-8")
    rule = re.search(r'~ \.tree-content:not\(:has\(> \[role="alert"\]\)\) \{([^}]*)\}', css)
    assert rule is not None, "the tree's hold is not in styles.css"
    delay = re.search(r"mb-delayed-loading-reveal 0s linear ([\d.]+)(ms|s) forwards", rule.group(1))
    assert delay is not None, rule.group(1)
    return float(delay.group(1)) * (1 if delay.group(2) == "ms" else 1000)


def test_nothing_in_the_files_panel_moves_from_document_start_to_settled(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    ignoring, wide, clean = _folders(tmp_path / "served")
    state = tmp_path / "state"
    for name in ("ignoring", "wide", "clean"):
        for part in ("cache", "config"):
            (state / name / part).mkdir(mode=0o700, parents=True)
    run = run_in_own_group(
        [
            require_node(),
            str(SESSION),
            str(_METAB),
            str(ignoring),
            str(wide),
            str(clean),
            str(_free_port()),
            str(state),
        ],
        timeout_s=SESSION_TIMEOUT_S,
        env={**os.environ, "CHROME_BIN": chrome, "CHROME_PROFILES": str(chrome_profile)},
    )
    assert not run.timed_out, f"the session ran past {SESSION_TIMEOUT_S} s: {run.stderr}"
    assert run.returncode == 0, run.stderr or run.stdout
    # Shown with a failure: every load's frames, and each phase's time.
    print(run.stdout, run.stderr)
    output = json.loads(run.stdout.strip().splitlines()[-1])
    results: list[dict[str, Any]] = output["results"]
    assert len(results) == 30, [result["name"] for result in results]

    for result in results:
        name = result["name"]
        assert result["settled"], f"{name}: never settled: {result['trail']}"
        assert result["scheme"] == result["theme"], f"{name}: drawn in {result['scheme']}"
        assert result["paneWidth"] == result["width"], f"{name}: pane {result['paneWidth']} px"
        ignored = name.startswith("ignored")
        # Nothing moves from first paint to settled.
        assert not _still(result), f"{name}: {_still(result)}: {result['trail']}"
        # Every shift from the document's start, each with its time and the node that
        # moved, which may be outside the panel.
        shift = f"layout shift {result['shift']}: {result['counted']}"
        assert result["shift"] == 0, f"{name}: {shift}: {result['trail']}"
        # And it is not luck: the line paints its settled shape from the first frame, from
        # the root's totals the shell inlined, or holding the ignored line without them,
        # which nothing but the root's totals settles.
        assert result["inline"] is not result["unknown"], f"{name}: inline {result['inline']}"
        if result["unknown"]:
            settled = "counted" if ignored else "no ignored files"
            assert result["lines"] == ["held", settled], f"{name}: {result['trail']}"
        else:
            settled = "counted" if ignored else "none"
            assert result["lines"] == [settled], f"{name}: {result['trail']}"
        # The ignored line's tooltip shows only while the line is cut short.
        tip = result["tip"]
        if ignored:
            assert tip is not None and tip["shows"] is tip["cut"], f"{name}: {tip}"
            assert tip["text"] == "+ 2,000 ignored (133.5 MB)", f"{name}: {tip}"
            if result["width"] == 180:
                assert tip["cut"], f"{name}: not cut short at 180 px: {tip}"
        else:
            assert tip is None, f"{name}: {tip}"
        # So does the tracked line's, its whole phrase too.
        tracked = result["trackedTip"]
        assert tracked is not None and tracked["shows"] is tracked["cut"], f"{name}: {tracked}"
    provisional = [result for result in results if result["provisional"]]
    assert len(provisional) == 2 and all(result["settled"] for result in provisional)

    # The hold is bounded: with filter-controls.js failed, the bar is never filled, and the
    # tree is shown at the bound, not hidden for good, and nothing moves.
    failed: dict[str, Any] = output["failOpen"]
    name = failed["name"]
    assert failed["settled"], f"{name}: the tree was never shown: {failed['trail']}"
    assert failed["barPending"], f"{name}: the filter bar was filled: {failed['trail']}"
    bound = _hold_bound_ms()
    shown = failed["shownAfter"]
    assert shown >= bound - BOUND_SLACK_MS, f"{name}: shown {shown} ms in, before {bound:.0f} ms"
    assert not _still(failed) and failed["shift"] == 0, f"{name}: {failed['counted']}"
