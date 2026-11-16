"""The folder's name goes home, in a real Chrome, and `0` does the same.

Home is the served folder's home view as a fresh load of `/view/` shows it
(docs/design-system.md, "Home"). What Home resets and the address it lands on are
browserless (``goingHome`` in ``tests/dom/preview-pane-state-session.js``). What only a
browser can tell is held here: that after a click on the name, `0`, or Shift-0, from a pull
request's Changes tab, a file's Source view, Commits, and a Files tab with a grouping, a
filter, open folders, and a scroll, the page is what a fresh load of `/view/` shows; that
Pulls then opens its list; that the name's tooltip neither appears nor goes because of a
click; and that the name is named "Home: <folder>" to assistive technology.

So this serves a checkout of the GitHub stand-in with a fake ``gh``, and
``tests/dom/folder-home-chrome.mjs`` drives each route in the running app.
``METABROWSER_FOLDER_HOME_SHOTS`` names a directory for its screenshots.

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``). The test owns
everything it starts: the server stops when its stdin closes, and the measuring Node
process leads a process group of its own, which Chrome joins, so a run stopped at its
bound stops all of it (tests/process_group.py).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.github_pull_fixture import Origin, clone_checkout, files_scenario, install_fake_gh
from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_git, require_node
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
from tests.test_nav_reveal_chrome import add_reveal_files

SESSION = Path(__file__).resolve().parent / "dom" / "folder-home-chrome.mjs"
_METAB = Path(sys.executable).with_name("metab")
# A cold Chrome start, which tests/dom/chrome-session.mjs bounds at 30 s, then its routes,
# each a page load, a key, or a click, each bounded at 30 s in the script.
_MEASUREMENT_BUDGET_S = 150.0
LIFECYCLE_S = (
    _BANNER_BUDGET_S
    + _SERVING_BUDGET_S
    + _MEASUREMENT_BUDGET_S
    + GROUP_STOP_S
    + 2 * _SERVER_STOP_S
    + PROFILE_TEARDOWN_S
)
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)


def test_the_folder_name_and_zero_go_home_as_a_fresh_load_shows_it(
    tmp_path: Path, pull_origin: Origin, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    node = require_node()
    checkout = clone_checkout(pull_origin, tmp_path / "checkout")
    # A folder longer than a first paint opens, so the tree can be opened and scrolled.
    add_reveal_files(checkout)
    fake = install_fake_gh(tmp_path, files_scenario(pull_origin))
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env.update(fake)
    tools = _private(tmp_path / "tools")
    (tools / "git").symlink_to(require_git())
    env["PATH"] = f"{tmp_path / 'fake-gh-bin'}{os.pathsep}{tools}"
    env["METABROWSER_CACHE_DIR"] = str(_private(tmp_path / "cache"))
    env["METABROWSER_CONFIG_DIR"] = str(_private(tmp_path / "config"))
    env["METABROWSER_LOG_LEVEL"] = "WARNING"
    log = tmp_path / "server.log"
    with log.open("w", encoding="utf-8") as output:
        # --exit-on-eof: closing stdin stops the server however this test ends.
        server = subprocess.Popen(
            [str(_METAB), str(checkout), "--no-open", "--port", str(_free_port()), "--exit-on-eof"],
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
        shots = os.environ.get("METABROWSER_FOLDER_HOME_SHOTS")
        run = run_in_own_group(
            [node, str(SESSION), f"http://127.0.0.1:{port}"],
            timeout_s=_MEASUREMENT_BUDGET_S,
            env={
                **os.environ,
                "CHROME_BIN": chrome,
                "CHROME_PROFILES": str(chrome_profile),
                **({"SHOTS_DIR": shots} if shots else {}),
            },
        )
    finally:
        _stop_server(server)
    if run.timed_out:
        pytest.fail(f"ran past {_MEASUREMENT_BUDGET_S:g} s; its steps:\n{run.stderr}")
    # Each step's time and the measurements, shown with the output when it fails.
    print(run.stderr)
    print(run.stdout)
    assert run.returncode == 0, f"{run.stderr[-6000:]}\nserver: {_log_tail(log)}"
    passed = re.fullmatch(r"folder home in Chrome: (\d+) checks passed\n", run.stdout)
    assert passed is not None and int(passed.group(1)) > 0, run.stdout
