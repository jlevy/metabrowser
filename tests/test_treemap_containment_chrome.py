"""Every Treemap cell lies inside its parent folder and inside the map's border, in Chrome.

The layout's rectangles are contained by construction, which
``tests/dom/treemap-layout-behavior.js`` holds browserlessly. What only a browser can say is
what the stylesheet draws from them: a border-box cell is never smaller than its padding and
its edge, and that floor once drew a 2 px cell 10 px wide, over its neighbours and past its
folder's edge (mb-coqj). ``tests/dom/treemap-containment-chrome.mjs`` serves a wide, deep
folder of files whose sizes span four orders of magnitude, opens the Treemap tab, and reads
every drawn cell's box at a wide and a narrow window. This holds that:

- the map draws hundreds of cells, many of them under 8 px on a side, and nests past two
  levels, so the reading covers the cells the floor used to widen;
- no cell is drawn wider than the width the map gave it;
- no cell passes its parent folder's cell or the viewport's padding box;
- the keyboard reaches every actionable cell by exactly one ``data-tm-index``, and a framed
  folder, which has no label, by its own cell.

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``), and CI runs
it. The session leads a process group of its own, which Chrome and the server join, and the
whole group is stopped however it ends (tests/process_group.py).
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

SESSION = Path(__file__).resolve().parent / "dom" / "treemap-containment-chrome.mjs"
# A server start, one Chrome, a page load, a switch to the Treemap tab, and two readings,
# as the Treemap legend's Chrome test does (its bound is set out there); this session waits
# on nothing longer than that one does.
SESSION_TIMEOUT_S = 90
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)
_METAB = Path(sys.executable).with_name("metab")

# Six top-level folders, three levels deep, three subfolders and six files in each, with
# sizes from 1 byte to 30 KB: 1,500 files, enough to fill the map's cell budget with cells
# from a few pixels on a side to a few hundred.
_TOP = 6
_DEPTH = 3
_FANOUT = 3
_FILES = 6


def _tree(folder: Path, depth: int, seed: int) -> int:
    folder.mkdir(parents=True, exist_ok=True)
    written = 0
    for n in range(_FILES):
        size = 1 + ((seed * 7919 + n * 104729) % 30_000) // (1 + (n % 4) * 40)
        (folder / f"f{n}.py").write_bytes(b"x" * size)
        written += 1
    if depth > 0:
        for d in range(_FANOUT):
            written += _tree(folder / f"d{d}", depth - 1, seed * 31 + d + 1)
    return written


def _served_folder(root: Path) -> int:
    (root / ".git").mkdir(parents=True)
    return sum(_tree(root / f"top{t}", _DEPTH, t + 1) for t in range(_TOP))


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _contained(reading: dict[str, Any], label: str) -> None:
    assert reading["cells"] >= 300, (label, reading)
    assert reading["tiny"] >= 50, (label, reading)
    assert reading["deepest"] >= 3, (label, reading)
    assert reading["escapes"] == 0, (label, reading)
    assert reading["framed"] >= 10, (label, reading)
    assert reading["misindexed"] == 0, (label, reading)


def test_every_treemap_cell_lies_inside_its_folder_and_the_border_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    root = tmp_path / "served"
    assert _served_folder(root) > 1000
    state = tmp_path / "state"
    state.mkdir()
    result = run_in_own_group(
        [require_node(), str(SESSION), str(_METAB), str(root), str(_free_port()), str(state)],
        timeout_s=SESSION_TIMEOUT_S,
        env={**os.environ, "CHROME_BIN": chrome, "CHROME_PROFILES": str(chrome_profile)},
    )
    assert not result.timed_out, (
        f"the session ran past {SESSION_TIMEOUT_S} s: {result.stderr or result.stdout}"
    )
    assert result.returncode == 0, result.stderr or result.stdout
    # Shown with a failure: every reading, and each phase's time.
    print(result.stdout, result.stderr)
    measured: dict[str, Any] = json.loads(result.stdout.strip().splitlines()[-1])
    _contained(measured["wide"], "1280 by 900")
    _contained(measured["narrow"], "760 by 600")
