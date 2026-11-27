"""The navigation metadata line under Files, Commits, and Pulls, in a real Chrome.

The Files totals, the Commits tally, and the Pulls count and connection lines are one
component, ``.nav-metadata`` (docs/design-system.md, "Navigation Metadata Line"). What it
promises is layout: one type on every line, the same distance from the rule above and
the rule below on every tab, the toolbar slot (Commits) as under a toolbar (Files,
Pulls), a pending tally where its figures will be, and one height in every state a line
passes through while its text fits. So this serves a checkout of the GitHub stand-in with
a fake ``gh``, and ``tests/dom/nav-metadata-chrome.mjs`` measures each tab at the default
pane width and at a wide one: Files settled, pending, counting, filtered, and with its two
other remarks; Commits settled, as the server ships it pending, and failed; and Pulls
while its list loads, once it has rows, and when a refresh can reach neither GitHub nor a
signed-in gh, nor any gh. On every line, count numerals are bold and inline with their
words. The Files filter's remark reads as one run, and the Pulls state tally remains
visible as the repository total clips (docs/design-system.md, "Count Summaries Bold Their
Numbers"; mb-roa9).
``tests/test_nav_metadata_line.py`` holds the markup and the
stylesheets to the component without a browser. In a pane too narrow for it, the
Commits tally wraps between its phrases and the tab bar between its tabs: at every pane
width from the narrowest, in both font sets, each is held to the navigation toolbars'
wrap rule (``tests/dom/nav-toolbar-wrap.mjs``; docs/design-system.md, "Navigation
Toolbars Wrap"). The navigation's header holds still in every one of those states: the
navigation's Refresh shows under every tab from the first paint.

The fake ``gh`` waits while a hold file exists, so the Pulls list is still loading when
it is measured; the measurement removes the file, rewrites the scenario the fake answers
from so the next refresh fails as each failure state needs, and last takes the fake's
execute bit away. The server's ``PATH`` holds the fake and Git and nothing else, so no
other ``gh`` answers for it.

Where text sits is computed layout, so this needs a browser; it skips without Chrome, as
``docs/e2e-testing.md`` lists, and CI runs it. The test owns everything it starts: the
server stops when its stdin closes, and the measuring Node process leads a process group
of its own, which Chrome joins, so a run stopped at its bound stops all of it
(tests/process_group.py). The browser profile is the ``chrome_profile`` fixture's.
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from metabrowser.cli.http_readiness import wait_for_http_ok_then
from tests.github_pull_fixture import Origin, clone_checkout, files_scenario, install_fake_gh
from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_git, require_node

SESSION = Path(__file__).resolve().parent / "dom" / "nav-metadata-chrome.mjs"
_METAB = Path(sys.executable).with_name("metab")
# The server's first line names the port it took, which a port in use moves.
_SERVING_LINE = re.compile(r"^Serving .* at http://127\.0\.0\.1:(\d+)/view/", re.MULTILINE)
# The server's banner, then its first HTTP answer: about 1.5 s and 0.1 s on a 10-core Mac,
# with room for a loaded machine, as tests/test_folder_overview_alignment.py allows.
_BANNER_BUDGET_S = 30.0
_SERVING_BUDGET_S = 15.0
# The measurement: a cold Chrome start, which tests/dom/chrome-session.mjs bounds at 30 s
# (a CI runner's first has taken 28.2 s), then its steps, each a paint or a fake gh
# refresh of the stand-in's catalog, each bounded at 30 s in the script. On a 10-core Mac
# at a load average near 10 the whole measurement took 5 s, and the test 9 s.
_MEASUREMENT_BUDGET_S = 120.0
# Closing the server's stdin, then SIGKILL.
_SERVER_STOP_S = 5.0
LIFECYCLE_S = (
    _BANNER_BUDGET_S
    + _SERVING_BUDGET_S
    + _MEASUREMENT_BUDGET_S
    + GROUP_STOP_S
    + 2 * _SERVER_STOP_S
    + PROFILE_TEARDOWN_S
)
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)

# The fake gh, held while the file at $GH_HOLD exists. The server's PATH holds it and
# Git and nothing else, so taking its execute bit away leaves the server no gh at all.
_HELD_GH = """#!/bin/sh
while [ -e "$GH_HOLD" ]; do /bin/sleep 0.05; done
exec "{gh}" "$@"
"""


def _free_port() -> int:
    """A port to start the server's search from; the banner says where it went."""

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _log_tail(log: Path) -> str:
    return log.read_text(encoding="utf-8", errors="replace")[-2000:]


def _read_port(server: subprocess.Popen[str], log: Path) -> int:
    deadline = time.monotonic() + _BANNER_BUDGET_S
    while time.monotonic() < deadline:
        if match := _SERVING_LINE.search(log.read_text(encoding="utf-8", errors="replace")):
            return int(match.group(1))
        if server.poll() is not None:
            pytest.fail(f"the server exited before its banner: {_log_tail(log)!r}")
        time.sleep(0.05)
    pytest.fail(f"no banner within {_BANNER_BUDGET_S:g} s: {_log_tail(log)!r}")


def _wait_until_serving(server: subprocess.Popen[str], port: int, log: Path) -> None:
    url = f"http://127.0.0.1:{port}/view/"
    outcome: list[str] = []
    wait_for_http_ok_then(
        "127.0.0.1",
        port,
        url,
        on_ready=lambda: outcome.append("ready"),
        on_error=outcome.append,
        is_cancelled=lambda: server.poll() is not None,
        timeout_s=_SERVING_BUDGET_S,
    )
    if outcome != ["ready"]:
        pytest.fail(f"{url} did not answer: {outcome} {_log_tail(log)!r}")


def _stop_server(server: subprocess.Popen[str]) -> None:
    assert server.stdin is not None
    server.stdin.close()
    try:
        server.wait(timeout=_SERVER_STOP_S)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait(timeout=_SERVER_STOP_S)


def _private(path: Path) -> Path:
    """A directory only its owner reads, as the cache and configuration homes must be."""

    path.mkdir(mode=0o700, parents=True)
    return path


def test_every_tabs_metadata_line_is_one_component_in_chrome(
    tmp_path: Path, pull_origin: Origin, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    node = require_node()
    checkout = clone_checkout(pull_origin, tmp_path / "checkout")
    fake = install_fake_gh(tmp_path, files_scenario(pull_origin))
    held = _private(tmp_path / "held-gh")
    gh = held / "gh"
    gh.write_text(_HELD_GH.format(gh=tmp_path / "fake-gh-bin" / "gh"), encoding="utf-8")
    gh.chmod(0o755)
    hold = tmp_path / "gh-hold"
    hold.touch()
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env.update(fake)
    tools = _private(tmp_path / "tools")
    (tools / "git").symlink_to(require_git())
    env["PATH"] = f"{held}{os.pathsep}{tools}"
    env["GH_HOLD"] = str(hold)
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
            env={
                **os.environ,
                "CHROME_BIN": chrome,
                "CHROME_PROFILES": str(chrome_profile),
                "GH_HOLD": str(hold),
                "GH_SCENARIO": fake["FAKE_GH_SCENARIO"],
                "GH_BIN": str(gh),
            },
        )
    finally:
        _stop_server(server)
    if run.timed_out:
        pytest.fail(f"ran past {_MEASUREMENT_BUDGET_S:g} s; its steps:\n{run.stderr}")
    # Each step's time, shown with the output when it fails.
    print(run.stderr)
    assert run.returncode == 0, f"{run.stderr[-6000:]}\nserver: {_log_tail(log)}"
    passed = re.fullmatch(r"nav metadata line in Chrome: (\d+) checks passed\n", run.stdout)
    assert passed is not None and int(passed.group(1)) > 0, run.stdout
