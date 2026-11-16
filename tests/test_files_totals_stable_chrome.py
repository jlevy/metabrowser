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
chrome.mjs`` serves a folder with ignored files and one with none and records each load
frame by frame from the document's start, in both themes, with the tally answered at once
and held 2 s, in the default pane and the narrowest. This judges it:

- from the first frame with rows to the settled one, no box in the navigation (the filter
  bar, each metadata line, the first twelve rows) moves or changes size, and Chrome
  records no layout shift without input after that frame (in the narrowest pane the
  filter bar wraps to two lines as it is filled, before any row is drawn, which
  docs/design-system.md, "Regions Keep Their Boxes", exempts);
- the line is its settled self from first paint: the ignored count's line for the folder
  with ignored files, and no ignored line for the folder with none;
- a shell drawn before the walk finished the root, its inlined totals taken out, holds
  the ignored line from first paint; the count fills it in place, in the narrowest pane
  too, where it is cut short on its one line rather than wrapped, and for a folder with
  nothing ignored the held line goes away, the one move this keeps, which is measured
  here as exactly that line's height.

The browserless states of the line are pinned by
``tests/golden/cli-ui-tree-summary-line.tryscript.md``. Where text sits is computed
layout, so this needs a browser; it skips without Chrome (``docs/e2e-testing.md``), and
CI runs it. The session leads a process group of its own, which Chrome and both servers
join, and the whole group is stopped however it ends (``tests/process_group.py``).
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
# Two server starts, one Chrome, and seventeen loads, eleven of them holding the tally
# 2 s: about 40 s of a 60 s test on a 10-core Mac at a load average near 30. A cold Chrome start in CI has
# taken 28.2 s, and each server's start is bounded at 30 s inside the session.
SESSION_TIMEOUT_S = 240
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)
# Layout rounds to fractions of a pixel; a box off by more than this has moved.
TOLERANCE_PX = 0.5
# The folder with ignored files reads like a real repository's, "1,201 files (45.8 MB)
# + 2,000 ignored (133.5 MB)", long enough that as one line it wrapped in the default
# pane. Its files are sparse, so they take no disk.
_TRACKED_FILES = 1200
_TRACKED_BYTES = 40_000
_IGNORED_FILES = 2000
_IGNORED_BYTES = 70_000


def _sparse(path: Path, size: int) -> None:
    with path.open("wb") as handle:
        handle.truncate(size)


def _folders(root: Path) -> tuple[Path, Path]:
    ignoring = root / "ignoring"
    (ignoring / ".git").mkdir(parents=True)
    (ignoring / ".gitignore").write_text("build/\n", encoding="utf-8")
    (ignoring / "src").mkdir()
    for index in range(_TRACKED_FILES):
        _sparse(ignoring / "src" / f"m{index:04d}.py", _TRACKED_BYTES)
    (ignoring / "build").mkdir()
    for index in range(_IGNORED_FILES):
        _sparse(ignoring / "build" / f"o{index:04d}.bin", _IGNORED_BYTES)
    (ignoring / "README.md").write_text("# Ignoring\n", encoding="utf-8")
    clean = root / "clean"
    (clean / ".git").mkdir(parents=True)
    (clean / "src").mkdir()
    for index in range(40):
        (clean / "src" / f"m{index:02d}.py").write_text(f"x = {index}\n", encoding="utf-8")
    (clean / "README.md").write_text("# Clean\n", encoding="utf-8")
    return ignoring, clean


def _free_ports() -> int:
    """A port whose successor is free too: the session serves the two folders on both."""

    for _ in range(50):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = int(probe.getsockname()[1])
        with socket.socket() as second:
            try:
                second.bind(("127.0.0.1", port + 1))
            except OSError:
                continue
        return port
    pytest.fail("no two adjacent free ports")


def _still(result: dict[str, Any]) -> list[str]:
    return [f"{key} {px} px" for key, px in result["moved"].items() if px > TOLERANCE_PX]


def test_nothing_in_the_files_panel_moves_from_first_paint_to_settled(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    ignoring, clean = _folders(tmp_path / "served")
    state = tmp_path / "state"
    for name in ("ignoring", "clean"):
        for part in ("cache", "config"):
            (state / name / part).mkdir(mode=0o700, parents=True)
    run = run_in_own_group(
        [
            require_node(),
            str(SESSION),
            str(_METAB),
            str(ignoring),
            str(clean),
            str(_free_ports()),
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
    assert len(results) == 17, [result["name"] for result in results]

    for result in results:
        name = result["name"]
        assert result["settled"], f"{name}: never settled: {result['trail']}"
        assert result["scheme"] == result["theme"], f"{name}: drawn in {result['scheme']}"
        assert result["paneWidth"] == result["width"], f"{name}: pane {result['paneWidth']} px"
        ignored = name.startswith("ignored")
        assert result["last"]["ignoredLine"] == ("counted" if ignored else "none"), (
            f"{name}: settled as {result['last']}"
        )
        if result["unknown"] and not ignored:
            # The held line goes away once the root's totals say nothing is ignored: the
            # line loses exactly that line, and the rows under it rise by as much.
            assert result["first"]["ignoredLine"] == "held", f"{name}: {result['first']}"
            held, settled = result["first"]["line"][1], result["last"]["line"][1]
            line = held - settled
            assert line > 0, f"{name}: the held line was {held} px, settled {settled}"
            for key, px in result["moved"].items():
                assert (key == "bar" and px <= TOLERANCE_PX) or abs(px - line) <= TOLERANCE_PX, (
                    f"{name}: {key} moved {px} px, the held line is {line} px: {result['trail']}"
                )
            continue
        # Nothing moves from first paint to settled.
        assert not _still(result), f"{name}: {_still(result)}: {result['trail']}"
        assert result["shift"] == 0, f"{name}: layout shift {result['shift']}: {result['trail']}"
        # And it is not luck: the line paints its settled shape from the first frame, from
        # the root's totals the shell inlined, or holding the ignored line without them.
        assert result["inline"] is not result["unknown"], f"{name}: inline {result['inline']}"
        if result["unknown"]:
            assert result["first"]["ignoredLine"] == "held", f"{name}: {result['first']}"
        else:
            assert result["first"]["ignoredLine"] == result["last"]["ignoredLine"], (
                f"{name}: first {result['first']}, settled {result['last']}"
            )
