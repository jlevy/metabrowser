"""Hiding the navigation pane, laid out and animated in a real Chrome.

The owner asked for a chevron on the main page's left edge that hides the navigation pane,
the page sliding over it, and turns to point back, with `\\` and Shift-`\\` doing the same
from anywhere (docs/design-system.md, "Hiding the Navigation Pane"); then, 2026-11-18, for
it to sit on the page's top row (mb-tl7p), and, 2026-11-19, back at the page's foot on the
shortcut strip's row, keeping its place in the gutter (mb-yw18). What the key and the click do to the
page's state, and which keys stay live while the pane is hidden, are browserless
(``cli-ui-nav-collapse.tryscript.md``). Where the chevron sits, the slide in every frame,
and real key input are a browser's, so ``tests/dom/nav-collapse-chrome.mjs`` measures
them against a live server.

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``). The test owns
everything it starts: the server stops when its stdin closes, and the measuring Node
process leads a process group of its own, which Chrome joins (tests/process_group.py).
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

SESSION = Path(__file__).resolve().parent / "dom" / "nav-collapse-chrome.mjs"
_METAB = Path(sys.executable).with_name("metab")
# A cold Chrome start, which tests/dom/chrome-session.mjs bounds at 30 s, then a page load
# and four toggles, each sampled for under a second.
_MEASUREMENT_BUDGET_S = 60.0
LIFECYCLE_S = (
    _BANNER_BUDGET_S
    + _SERVING_BUDGET_S
    + _MEASUREMENT_BUDGET_S
    + GROUP_STOP_S
    + 2 * _SERVER_STOP_S
    + PROFILE_TEARDOWN_S
)
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)


def test_the_chevron_and_backslash_hide_and_show_the_navigation_pane_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    node = require_node()
    folder = tmp_path / "folder"
    (folder / "docs").mkdir(parents=True)
    (folder / "README.md").write_text("# A folder\n\nIts pane is hidden.\n", encoding="utf-8")
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
    print(run.stderr)
    assert run.returncode == 0, f"{run.stderr[-6000:]}\nserver: {_log_tail(log)}"
    passed = re.fullmatch(r"nav collapse in Chrome: (\d+) checks passed\n", run.stdout)
    assert passed is not None and int(passed.group(1)) > 0, run.stdout
