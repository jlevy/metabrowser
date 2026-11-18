"""The shortcut strip stays one row, Shift first, at every pane width, in a real Chrome.

The owner asked for the strip at the foot of the navigation pane to list Shift, Reveal
keys, first, ahead of ``?`` for Help, and to stay one row: where its items do not all fit,
it drops them from the end, Quick Search first, then Help, and Shift always shows
(mb-k8am). Which items show at a width is layout, so this serves a plain folder and
``tests/dom/shortcut-strip-chrome.mjs`` sweeps the pane from its 180 px minimum to its
300 px default, one pixel at a time, in both interface font sets. At each width it holds
what the strip shows to the longest prefix of Shift, Help, and Quick Search whose widths
and gaps fit, every item shown to the strip's one line inside its box, a dropped item to
not being drawn, and the strip to the height of the slot the server reserves for it.
In the narrowest pane, holding Shift shows the revealed layer over the panel, listing
what the resting strip dropped. ``tests/dom/shortcut-strip-session.js`` runs the same
production code browserlessly on injected widths, and its golden records what it shows.

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``). The test
owns everything it starts: the server stops when its stdin closes, and the measuring Node
process leads a process group of its own, which Chrome joins, so a run stopped at its
bound stops all of it (tests/process_group.py). The browser profile is the
``chrome_profile`` fixture's.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_node
from tests.test_nav_metadata_chrome import (
    _BANNER_BUDGET_S,
    _SERVER_STOP_S,
    _SERVING_BUDGET_S,
    _free_port,
    _log_tail,
    _private,
    _read_port,
    _stop_server,
    _wait_until_serving,
)

SESSION = Path(__file__).resolve().parent / "dom" / "shortcut-strip-chrome.mjs"
_METAB = Path(sys.executable).with_name("metab")
# A cold Chrome start, which tests/dom/chrome-session.mjs bounds at 30 s (a CI runner's first
# has taken 28.2 s), then 242 widths, a frame each, and a held Shift. On a 10-core Mac the
# session took 5 s.
_MEASUREMENT_BUDGET_S = 90.0
LIFECYCLE_S = (
    _BANNER_BUDGET_S
    + _SERVING_BUDGET_S
    + _MEASUREMENT_BUDGET_S
    + GROUP_STOP_S
    + 2 * _SERVER_STOP_S
    + PROFILE_TEARDOWN_S
)
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)


def test_the_shortcut_strip_stays_one_row_with_shift_first_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    node = require_node()
    folder = tmp_path / "folder"
    (folder / "docs").mkdir(parents=True)
    (folder / "README.md").write_text("# A folder\n\nIts strip is measured.\n", encoding="utf-8")
    (folder / "docs" / "notes.txt").write_text("notes\n", encoding="utf-8")
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env["METABROWSER_CACHE_DIR"] = str(_private(tmp_path / "cache"))
    env["METABROWSER_CONFIG_DIR"] = str(_private(tmp_path / "config"))
    env["METABROWSER_LOG_LEVEL"] = "WARNING"
    log = tmp_path / "server.log"
    with log.open("w", encoding="utf-8") as output:
        # --exit-on-eof: closing stdin stops the server however this test ends.
        server = subprocess.Popen(
            [str(_METAB), str(folder), "--no-open", "--port", str(_free_port()), "--exit-on-eof"],
            stdin=subprocess.PIPE,
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            start_new_session=True,
        )
    try:
        port = _read_port(server, log)
        _wait_until_serving(server, port, log)
        run = run_in_own_group(
            [node, str(SESSION), f"http://127.0.0.1:{port}"],
            timeout_s=_MEASUREMENT_BUDGET_S,
            env={**os.environ, "CHROME_BIN": chrome, "CHROME_PROFILES": str(chrome_profile)},
        )
    finally:
        _stop_server(server)
    if run.timed_out:
        pytest.fail(f"ran past {_MEASUREMENT_BUDGET_S:g} s; its steps:\n{run.stderr}")
    # Each step's time, and the widths at which each set of items showed, with the output.
    print(run.stderr)
    assert run.returncode == 0, f"{run.stderr[-6000:]}\nserver: {_log_tail(log)}"
    passed = re.fullmatch(r"shortcut strip in Chrome: (\d+) checks passed\n", run.stdout)
    assert passed is not None and int(passed.group(1)) > 0, run.stdout
