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
and one with nothing ignored, and records each load frame by frame from the document's
start, in both themes, with the tally answered at once and held 2 s, in the default pane
and the narrowest. This judges it:

- from first paint, the first frame with rows under a filled filter bar, to the settled
  frame, no box in the navigation (the filter bar, each metadata line, the first twelve
  rows) moves or changes size, and Chrome records no layout shift without input after
  that frame. In the narrowest pane the filter bar wraps to two lines as it is filled,
  which docs/design-system.md, "Regions Keep Their Boxes", exempts as a toolbar in a pane
  too narrow for it; the rows sometimes paint a frame before that and move 30 px with
  it (mb-h3hc's audit; the server rendering the bar, H52, would end it);
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
  the line is cut short, and in the narrowest pane the ignored line is.

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
import socket
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_node

SESSION = Path(__file__).resolve().parent / "dom" / "files-totals-stable-chrome.mjs"
_METAB = Path(sys.executable).with_name("metab")
# Three server starts, one Chrome, and thirty loads, eighteen of them holding the tally
# 2 s and two the event stream 1.5 s (eight more hold it only until first paint, inside
# their tally's 2 s): the session took 71 s, and the test 98 s, on a 10-core Mac at a
# load average near 30. A cold Chrome start in CI has taken 28.2 s, and each server's
# start is bounded at 30 s inside the session.
SESSION_TIMEOUT_S = 240
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)
# Layout rounds to fractions of a pixel; a box off by more than this has moved.
TOLERANCE_PX = 0.5
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


def _folders(root: Path) -> tuple[Path, Path, Path]:
    ignoring = _ignoring(root / "ignoring", _TRACKED_FILES)
    wide = _ignoring(root / "wide", _WIDE_TRACKED_FILES)
    clean = root / "clean"
    (clean / ".git").mkdir(parents=True)
    (clean / "src").mkdir()
    for index in range(40):
        (clean / "src" / f"m{index:02d}.py").write_text(f"x = {index}\n", encoding="utf-8")
    (clean / "README.md").write_text("# Clean\n", encoding="utf-8")
    return ignoring, wide, clean


def _free_port() -> int:
    """A port to start the first server's search from; the banner says where it went."""

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _still(result: dict[str, Any]) -> list[str]:
    return [f"{key} {px} px" for key, px in result["moved"].items() if px > TOLERANCE_PX]


def test_nothing_in_the_files_panel_moves_from_first_paint_to_settled(
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
    results: list[dict[str, Any]] = json.loads(run.stdout.strip().splitlines()[-1])["results"]
    assert len(results) == 30, [result["name"] for result in results]

    for result in results:
        name = result["name"]
        assert result["settled"], f"{name}: never settled: {result['trail']}"
        assert result["scheme"] == result["theme"], f"{name}: drawn in {result['scheme']}"
        assert result["paneWidth"] == result["width"], f"{name}: pane {result['paneWidth']} px"
        ignored = name.startswith("ignored")
        # Nothing moves from first paint to settled.
        assert not _still(result), f"{name}: {_still(result)}: {result['trail']}"
        assert result["shift"] == 0, f"{name}: layout shift {result['shift']}: {result['trail']}"
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
