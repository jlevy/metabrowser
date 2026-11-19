"""A pull request's description never shows as Markdown source, in headless Chrome.

The owner opened pull requests from the Pulls tab and saw the description as raw Markdown
for 3 to 4 s before it rendered (mb-d59o). A pull request with no record cached opens on
its core preview, the description prepared ahead of selection, and the page asked for no
Markdown while it showed one: its description stayed source until the full record's fetch
through gh landed and the page's next poll read it. Measured in headless Chrome 152 on
jlevy/metabrowser through the Pulls tab, at a load average of 14 to 19 (2026-11-18), the
source showed for 1.0 and 2.0 s.

So this serves a checkout of the GitHub stand-in with a fake ``gh`` that holds each pull
request's record fetch until the script releases it, and prepares the cores of pull
requests 7 and 10 through ``pull-cores-prepare`` alone, as a Pulls row's view does, so
the server's Markdown child is still cold. ``tests/dom/github-pull-core-markdown-chrome.mjs``
opens 7's page by its address, where it shows the core and its own first read starts the
child, releases 7's record and watches it land, then opens 10 from its row in the Pulls
tab with the description's render held past the page's first-paint hold, so the page
shows with the placeholder, and last releases 10's record. A sampler reads every
animation frame from navigation start. The description must never be on screen as source
while its Markdown is on its way, and its render must arrive within the Markdown route's
own bound. Which texts are placeholders, and when, is
browserless (``tests/dom/github-pull-first-paint-behavior.js`` and
``tests/dom/github-pull-core-preview-behavior.js``); what is on screen each frame is the
browser's.

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``). The test
owns everything it starts: the server stops when its stdin closes, and the measuring Node
process leads a process group of its own, which Chrome joins (tests/process_group.py).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from tests.github_pull_fixture import (
    Origin,
    clone_checkout,
    graph_core_data,
    install_fake_gh,
    ok,
    pull_bodies,
    scenario,
)
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

SESSION = Path(__file__).resolve().parent / "dom" / "github-pull-core-markdown-chrome.mjs"
_METAB = Path(sys.executable).with_name("metab")
# The pull requests whose cores are prepared, each from a GraphQL batch of its own.
_NUMBERS = (7, 10)
# The catalog refresh and each core's preparation, through the fake gh. Each took under a
# second here at a load average of 20 to 40 (2026-11-18); a loaded CI runner has more room.
_PREPARE_BUDGET_S = 30.0
# A cold Chrome start, which tests/dom/chrome-session.mjs bounds at 30 s, then three page
# loads and a fake gh fetch, each bounded at 30 s in the script.
_MEASUREMENT_BUDGET_S = 120.0
# A gh in front of the fake one that holds the record fetches of pull requests 7 and 10,
# every read of each one's pull, reviews, comments, timeline, and checks but its changed
# files, until the directory RECORD_RELEASE names holds a file named for its number, or for
# the measurement's budget at most. A page that opens on a core fetches its record at once,
# and the Pulls tab reads the records of rows near the one shown ahead of a click, so
# either record could land before its core is judged, or not, as the machine's load
# decides; held, each page opens on its core every run, as a pull request does whose record
# GitHub has not yet answered.
_HELD_GH = """#!/bin/sh
held=""
case " $* " in
  *"/pulls/7/files"*|*"/pulls/10/files"*) ;;
  *"/pulls/7 "*|*"/pulls/7/"*|*"/pulls/7?"*|*" number=7 "*) held=7 ;;
  *"/pulls/10 "*|*"/pulls/10/"*|*"/pulls/10?"*|*" number=10 "*) held=10 ;;
esac
if [ -n "$held" ]; then
  tries=0
  while [ ! -e "$RECORD_RELEASE/$held" ] && [ "$tries" -lt {tries} ]; do
    /bin/sleep 0.1
    tries=$((tries + 1))
  done
fi
exec {gh} "$@"
"""
LIFECYCLE_S = (
    _BANNER_BUDGET_S
    + _SERVING_BUDGET_S
    + _PREPARE_BUDGET_S
    + _MEASUREMENT_BUDGET_S
    + GROUP_STOP_S
    + 2 * _SERVER_STOP_S
    + PROFILE_TEARDOWN_S
)
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)


def _call(base: str, route: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
    """A GET, or a POST of *body* with the same-origin proof a page's request carries."""

    data = None if body is None else json.dumps(body).encode()
    headers = {} if body is None else {"content-type": "application/json", "origin": base}
    request = urllib.request.Request(f"{base}{route}", data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"null")


def _until(what: str, check: Any, last: Any) -> Any:
    """*check*'s first truthy answer; past the budget, fail with what *last* answers."""

    deadline = time.monotonic() + _PREPARE_BUDGET_S
    while time.monotonic() < deadline:
        found = check()
        if found:
            return found
        time.sleep(0.2)
    pytest.fail(f"{what} did not happen within {_PREPARE_BUDGET_S:g} s: {last()}"[:4000])


def _prepare_cores(base: str) -> None:
    """Fetch the catalog, then each core, as the Pulls tab's rows in view ask for them."""

    status, _ = _call(base, "/api/plugin/github/pulls-refresh", {})
    assert status in (200, 202), status
    # The window of the catalog that holds 7 and 10, which comes last, newest first.
    listing = "/api/plugin/github/pulls?state=all&limit=10&after=11"

    def generation() -> str | None:
        """The finished catalog's generation, which a batch is admitted against."""

        status, answer = _call(base, listing)
        if status != 200 or answer.get("complete") is not True:
            return None
        numbers = {row.get("number") for row in answer.get("rows", [])}
        return answer["generation"] if set(_NUMBERS) <= numbers else None

    _until("the catalog listing 7 and 10", generation, lambda: _call(base, listing))
    for number in _NUMBERS:
        asked: list[tuple[int, Any]] = []

        def prepared(number: int = number, asked: list[tuple[int, Any]] = asked) -> bool:
            # Asked until the batch answers it ready, its core written. Nothing here reads
            # the pull route, whose read starts the Markdown child for the page that follows
            # it (`pull_handler`), so the child is still cold when Chrome opens 7. A source
            # runs one core job at a time, so a batch can answer ``busy`` until the one
            # before it unwinds, and a catalog refresh still settling can move the
            # generation under it (``not_owner``); a batch on its way answers ``joined``.
            window = {"id": f"visible-{number}", "generation": generation() or ""}
            ask = {"state": "all", "window": window, "numbers": [number]}
            asked.append(_call(base, "/api/plugin/github/pull-cores-prepare", ask))
            status, answer = asked[-1]
            assert status in (200, 202), asked[-1]
            return answer.get("preparation") == "ready" and number in answer["ready_numbers"]

        _until(f"pull request {number}'s core", prepared, lambda asked=asked: asked[-1:])


def test_a_core_previews_description_never_shows_as_markdown_source_in_chrome(
    tmp_path: Path, pull_origin: Origin, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    node = require_node()
    checkout = clone_checkout(pull_origin, tmp_path / "checkout")
    answers = scenario(pull_origin)
    bodies = pull_bodies(pull_origin)
    for number in _NUMBERS:
        data = graph_core_data(bodies[number]["pull"])
        data["repository"]["p0"] = data["repository"].pop("pull")
        key = f"graphql:visible-cores:{number}"
        answers["api"][key] = ok(key, {"data": data})
    fake = install_fake_gh(tmp_path, answers)
    held = _private(tmp_path / "held-gh-bin")
    (held / "gh").write_text(
        _HELD_GH.format(tries=int(_MEASUREMENT_BUDGET_S * 10), gh=tmp_path / "fake-gh-bin" / "gh"),
        encoding="utf-8",
    )
    (held / "gh").chmod(0o700)
    release = _private(tmp_path / "released")
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env.update(fake)
    env["RECORD_RELEASE"] = str(release)
    tools = _private(tmp_path / "tools")
    (tools / "git").symlink_to(require_git())
    # The fake gh behind its hold, and Git, and nothing else, so no other gh answers for the
    # server.
    env["PATH"] = os.pathsep.join(map(str, (held, tmp_path / "fake-gh-bin", tools)))
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
        base = f"http://127.0.0.1:{port}"
        _prepare_cores(base)
        run = run_in_own_group(
            [node, str(SESSION), base],
            timeout_s=_MEASUREMENT_BUDGET_S,
            env={
                **os.environ,
                "CHROME_BIN": chrome,
                "CHROME_PROFILES": str(chrome_profile),
                "RECORD_RELEASE": str(release),
            },
        )
    finally:
        _stop_server(server)
    if run.timed_out:
        pytest.fail(f"ran past {_MEASUREMENT_BUDGET_S:g} s; its steps:\n{run.stderr}")
    # Each page's timeline, shown with the output when it fails.
    print(run.stderr)
    assert run.returncode == 0, f"{run.stderr[-6000:]}\nserver: {_log_tail(log)}"
    passed = re.fullmatch(r"core description in Chrome: (\d+) checks passed\n", run.stdout)
    assert passed is not None and int(passed.group(1)) > 0, run.stdout
