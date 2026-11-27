"""Text is sized by its role, and secondary metadata by the text it accompanies, in Chrome.

The rule is in docs/design-system.md, "Type Scale": the main view's reading text is the body
size, the navigation column's list text one step under it, and metadata, an age, a size, a
count, an update or fetch time, a row's second line, a note, is the size of the text beside
it. Which rules may set the small size is browserless (``tests/test_design_vocabulary.py``,
``test_secondary_metadata_reads_at_its_texts_size``); the size each role computes to is the
cascade's, which only a browser resolves.

So this serves a checkout of the GitHub stand-in with a fake ``gh``, and
``tests/dom/type-scale-chrome.mjs`` reads one of each role on the Pulls, Files, and Commits
panels and the navigation column's foot, a file's and a folder's header, a commit's page,
its diff's file bars and its Diff summary's files, a pull request's Conversation and Checks,
a tooltip, the settings menu, Help, and Quick Search, holds each to the table, and holds each
piece of metadata to the size of the text it accompanies; a Pulls row's age column to holding
"12mo" whole; and, in the narrowest pane, a commit row's age to staying whole while its
author gives way.

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``). The test owns
everything it starts: the server stops when its stdin closes, and the measuring Node process
leads a process group of its own, which Chrome joins, so a run stopped at its bound stops
all of it (tests/process_group.py). The browser profile is the ``chrome_profile`` fixture's.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.github_pull_fixture import Origin, clone_checkout, install_fake_gh, scenario
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

SESSION = Path(__file__).resolve().parent / "dom" / "type-scale-chrome.mjs"
_METAB = Path(sys.executable).with_name("metab")
# A cold Chrome start, which tests/dom/chrome-session.mjs bounds at 30 s (a CI runner's first
# has taken 28.2 s), then its surfaces, each a click or a fake gh refresh, each bounded at
# 30 s in the script. On a 10-core Mac at a load average near 40 the session took 14 s.
_MEASUREMENT_BUDGET_S = 120.0
LIFECYCLE_S = (
    _BANNER_BUDGET_S
    + _SERVING_BUDGET_S
    + _MEASUREMENT_BUDGET_S
    + GROUP_STOP_S
    + 2 * _SERVER_STOP_S
    + PROFILE_TEARDOWN_S
)
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)


def test_text_is_sized_by_its_role_in_chrome(
    tmp_path: Path, pull_origin: Origin, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    node = require_node()
    checkout = clone_checkout(pull_origin, tmp_path / "checkout")
    fake = install_fake_gh(tmp_path, scenario(pull_origin))
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env.update(fake)
    tools = _private(tmp_path / "tools")
    (tools / "git").symlink_to(require_git())
    # The fake gh and Git, and nothing else, so no other gh answers for the server.
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
        run = run_in_own_group(
            [node, str(SESSION), f"http://127.0.0.1:{port}"],
            timeout_s=_MEASUREMENT_BUDGET_S,
            env={**os.environ, "CHROME_BIN": chrome, "CHROME_PROFILES": str(chrome_profile)},
        )
    finally:
        _stop_server(server)
    if run.timed_out:
        pytest.fail(f"ran past {_MEASUREMENT_BUDGET_S:g} s; its steps:\n{run.stderr}")
    # Each step's time, shown with the output when it fails.
    print(run.stderr)
    assert run.returncode == 0, f"{run.stderr[-6000:]}\nserver: {_log_tail(log)}"
    passed = re.fullmatch(r"type scale in Chrome: (\d+) checks passed\n", run.stdout)
    assert passed is not None and int(passed.group(1)) > 0, run.stdout
