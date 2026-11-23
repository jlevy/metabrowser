"""What Chrome draws of the Treemap: painted cells, labels, the pointer, and the keys.

The layout's rectangles are contained by construction, and the paint list, mark ops, and hit
grid follow from them, which ``tests/dom/treemap-layout-behavior.js`` and
``tests/dom/treemap-paint-hit-behavior.js`` hold browserlessly. What only a browser can say
is what it draws: ``tests/dom/treemap-containment-chrome.mjs`` serves a wide, deep folder of
files whose sizes span four orders of magnitude, reads the Overview's compact map, then opens
the Treemap tab and reads it at a wide and a narrow window. This holds that:

- the map paints hundreds of cells, nested past two levels, and in the compact map and a
  narrow window many of them under 8 px on a side;
- the canvas holds each cell's fill at its center, and cells of different styles paint
  different colors;
- no label passes its cell or the viewport's padding box;
- the DOM stays small: one label per labelled cell, one focus proxy, no element per cell;
- the pointer on a small unlabelled file hovers it, names it in the tooltip, and a click
  opens it;
- the focus proxy is the one focusable element, named, and ArrowRight moves it.

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
# A server start, one Chrome, two page loads, two switches to the Treemap tab, three
# readings, a hover, a click, and a key: the Treemap legend's Chrome test's bound (set out
# there) for one load and switch, and as much again for the second, each wait inside it
# bounded at 30 s or less.
SESSION_TIMEOUT_S = 150
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
        # Three types, so cells of different styles sit side by side.
        (folder / f"f{n}.{('py', 'md', 'json')[n % 3]}").write_bytes(b"x" * size)
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


def _contained(reading: dict[str, Any], label: str, *, small: bool) -> None:
    assert reading["cells"] >= 300, (label, reading)
    assert reading["tiny"] >= (50 if small else 0), (label, reading)
    assert reading["deepest"] >= 3, (label, reading)
    assert reading["escapes"] == 0, (label, reading)
    assert reading["sampled"] >= 20, (label, reading)
    assert reading["wrongFill"] == 0, (label, reading)
    assert reading["distinct"] == reading["styles"] >= 2, (label, reading)
    assert reading["focusable"] == 1, (label, reading)
    assert reading["focusOrder"] == reading["actionable"], (label, reading)
    # Labels, the focus proxy, the canvases, and probes: far fewer elements than cells.
    assert reading["domElements"] < reading["cells"] / 2, (label, reading)


def test_treemap_paints_labels_and_answers_the_pointer_and_keys_in_chrome(
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
    # At 1280 by 900 every file of this folder has room; the compact map and the narrow
    # window draw most of them under 8 px.
    _contained(measured["compact"], "the Overview's compact map", small=True)
    _contained(measured["wide"], "1280 by 900", small=False)
    _contained(measured["narrow"], "760 by 600", small=True)
    assert measured["pointer"]["hovered"], measured["pointer"]
    assert measured["pointer"]["tooltip"], measured["pointer"]
    assert measured["pointer"]["opened"], measured["pointer"]
    assert measured["keyboard"] == {"focused": True, "moved": True, "named": True}, measured
