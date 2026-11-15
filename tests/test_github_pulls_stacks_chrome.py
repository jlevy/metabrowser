"""The Pulls tab grouped by stack, and the stack menu, in a real Chrome.

The Pulls tab's stack groups and the pull request page's stack button and menu share one
design (docs/design-system.md, "Stacks"). Which rows group, in what order, and what the
keys do is browserless (``tests/dom/github-pulls-stack-groups-session.js``); what only a
browser can tell is held here: that a stack row's header and the stack menu's heading
resolve to the same label tokens, gray, all caps, and tracked; where a stack row and the
rows under it start; that both kinds of row hover and focus alike; that the option's chip
keeps the toolbar's height; that real keys move focus onto and off a stack row; that the
groups list a stack's pull requests in the menu's order; and that the choice persists.

It also holds the Pulls toolbar to the navigation toolbars' wrap rule (docs/design-system.md,
"Navigation Toolbars Wrap"): at every pane width from the narrowest, 179 px, to 420, in
both font sets, with three- and four-digit tallies, with the Stacks chip and without it,
nothing is cut, the toolbar is one line exactly while it fits and wraps in order otherwise,
Reload last and at the line's end, its lines a line height and a gap apart; the Show group
is joined where its line holds it and the chip cluster below, through the row's own
observers, holding one layout at the break and switching once across it, with no
ResizeObserver loop error; and a group bound and then disposed is fitted no more.

So this serves a checkout of the GitHub stand-in with a fake ``gh`` whose ``gh stack``
answers two native stacks, #286 (pull requests 7 to 10, from the base) and #300 (5 and
10, so 10 is in both), and ``tests/dom/github-pulls-stacks-chrome.mjs`` measures the
running app. ``METABROWSER_PULLS_STACKS_SHOTS`` names a directory for its screenshots.

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
from typing import Any

import pytest

from tests.github_pull_fixture import Origin, clone_checkout, files_scenario, install_fake_gh, ok
from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, GroupRun, run_in_own_group
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

SESSION = Path(__file__).resolve().parent / "dom" / "github-pulls-stacks-chrome.mjs"
_METAB = Path(sys.executable).with_name("metab")
# A cold Chrome start, which tests/dom/chrome-session.mjs bounds at 30 s, then its steps,
# each a paint, a fake gh refresh, or the page's load, each bounded at 30 s in the script.
# On a 10-core Mac at a load average of 6 to 20 the measurement took 9 to 14 s.
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

STACKS_PATH = "repos/octo/demo/stacks?per_page=100&page=1"
# Native stacks list their members from the base; #10 is in both.
STACKS = ((286, (7, 8, 9, 10)), (300, (5, 10)))


def stacks_scenario(origin: Origin) -> dict[str, Any]:
    """The stand-in's answers, and two native stacks for ``gh stack``."""

    answers = files_scenario(origin)
    stacks = [
        {
            "number": number,
            "url": f"https://api.github.com/repos/octo/demo/stacks/{number}",
            "base": {"ref": "main"},
            "open": True,
            "pull_requests": [{"number": pull} for pull in pulls],
        }
        for number, pulls in STACKS
    ]
    return {
        **answers,
        "stack_version": "0.1.0",
        "api": {**answers["api"], STACKS_PATH: ok(STACKS_PATH, stacks)},
    }


def run_measurement(
    tmp_path: Path, pull_origin: Origin, chrome_profile: Path, *, mode: list[str]
) -> GroupRun:
    """Serve the stand-in with stacks and run the measurement against it."""

    chrome = require_chrome()
    node = require_node()
    checkout = clone_checkout(pull_origin, tmp_path / "checkout")
    fake = install_fake_gh(tmp_path, stacks_scenario(pull_origin))
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
        shots = os.environ.get("METABROWSER_PULLS_STACKS_SHOTS")
        run = run_in_own_group(
            [node, str(SESSION), f"http://127.0.0.1:{port}", *mode],
            timeout_s=_MEASUREMENT_BUDGET_S,
            env={
                **os.environ,
                "CHROME_BIN": chrome,
                "CHROME_PROFILES": str(chrome_profile),
                **({"SHOTS_DIR": shots, "MEASURE_OUT": f"{shots}/measured.json"} if shots else {}),
            },
        )
    finally:
        _stop_server(server)
    if run.timed_out:
        pytest.fail(f"ran past {_MEASUREMENT_BUDGET_S:g} s; its steps:\n{run.stderr}")
    # Each step's time, shown with the output when it fails.
    print(run.stderr)
    assert run.returncode == 0, f"{run.stderr[-6000:]}\nserver: {_log_tail(log)}"
    return run


def test_the_pulls_stack_groups_share_the_stack_menus_design_in_chrome(
    tmp_path: Path, pull_origin: Origin, chrome_profile: Path
) -> None:
    run = run_measurement(tmp_path, pull_origin, chrome_profile, mode=[])
    passed = re.fullmatch(r"pulls stacks in Chrome: (\d+) checks passed\n", run.stdout)
    assert passed is not None and int(passed.group(1)) > 0, run.stdout
