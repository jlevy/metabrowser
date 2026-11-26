"""A native stack's page, in a real Chrome: a pull request's page for the whole stack.

What the stack's page says is browserless, against the stack route's recorded answers: its
header's rows at first paint and settled, its member rows, and the diff drawings it asks
for, in ``tests/dom/github-stack-page-session.js`` and
``tests/dom/github-stack-guide-mount-session.js``. What only a browser can tell is held here
(docs/design-system.md, "The Stack Page"): that on a stack whose members' records are read,
nothing on the page moves from its first paint, opening the page or its Docs and Changes,
while the delayed loading block, on this page and on a pull request's, stays where it
shows; that the running app gives every member its author, merged 8 too, and marks no
member current, since none is the page; that the Diff summary is closed; that View on
GitHub opens the whole stack; that the tabs are a pull request's without Files; and that
the Pulls tab's Stack Overview row is current and in view while the page is open and opens it.
A stack still being fetched is not measured: its status line says what is being fetched
and then goes, which moves the lines under it. A member row is not measured against the
menu's either: the page draws it with the stack menu's builder (`stackMemberRow`), so it is
the menu's by construction; only its inset in the members' card, the page's own rule, is
measured, by the second test.

So this serves a checkout of the GitHub stand-in with a fake ``gh`` whose ``gh stack``
answers native stacks over the stand-in's pull requests, #70 (8, then 10) and #71 (8, 7,
then 10, where the top lacks 7), and ``tests/dom/github-stack-page-chrome.mjs`` measures the
running app. ``METABROWSER_STACK_PAGE_SHOTS`` names a directory for its screenshots.

The second test serves the stand-in with guides (``--guided-stack``): 7 carries its own, and
10 the guide of #70, whose top it is. ``tests/dom/github-stack-page-layout-chrome.mjs`` holds
each part the stack's page shares with a pull request's at a pull request's edges and padding,
border and ground, within the module's ``NEAR``: the header, the tab bar, Guided Review's
step list and step card against 7's, and the Docs and Changes bodies against 10's, in the
light and the dark scheme at a desktop width and a phone's, each tab loaded and after the
reader switches tabs in place; and the members' card a page card whose rows are inset as a
card's head is. ``METABROWSER_STACK_PAGE_SHOTS`` names a directory for its
screenshots too.

The third serves the stand-in and moves #70 under its page, to 10 alone and back, as
``tests/dom/github-stack-page-notice-chrome.mjs`` describes: before the reader does anything
the new comparison is drawn with no notice, after a wheel on the page it is offered with what
changed, "#8 joined the stack.", and its button draws it and clears the notice. Which answer
does what is the browserless session's (``answerAction``); this holds the page's glue to it.
``METABROWSER_STACK_PAGE_SHOTS`` names a directory for its screenshots too.

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``). The test owns
everything it starts: the server stops when its stdin closes, and the measuring Node
process leads a process group of its own, which Chrome joins, so a run stopped at its
bound stops all of it (tests/process_group.py).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from tests.github_pull_fixture import ok
from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, GroupRun, run_in_own_group
from tests.required_tools import require_chrome, require_node
from tests.test_nav_metadata_chrome import (
    _SERVER_STOP_S,
    _SERVING_BUDGET_S,
    _free_port,
    _log_tail,
    _private,
    _stop_server,
    _wait_until_serving,
)

FIXTURE = Path(__file__).resolve().parent / "github_pull_fixture.py"
SESSION = Path(__file__).resolve().parent / "dom" / "github-stack-page-chrome.mjs"
LAYOUT = Path(__file__).resolve().parent / "dom" / "github-stack-page-layout-chrome.mjs"
NOTICE = Path(__file__).resolve().parent / "dom" / "github-stack-page-notice-chrome.mjs"
# The stand-in's home, its mirror and the records of 7 to 10 fetched through the production
# CLI path, as tests/test_github_guided_review_chrome.py builds it.
_BUILD_BUDGET_S = 60.0
# A cold Chrome start, which tests/dom/chrome-session.mjs bounds at 30 s, then its steps,
# paints and recordings of the page settling, each bounded in the script.
_MEASUREMENT_BUDGET_S = 180.0
LIFECYCLE_S = (
    _BUILD_BUDGET_S
    + _SERVING_BUDGET_S
    + _MEASUREMENT_BUDGET_S
    + GROUP_STOP_S
    + 2 * _SERVER_STOP_S
    + PROFILE_TEARDOWN_S
)
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)

STACKS_PATH = "repos/octo/demo/stacks?per_page=100&page=1"
# Native stacks list their members from the base: 70's top contains 8, and 71's lacks 7,
# a fork, as tests/test_cli_github_stack_golden.py describes them.
STACKS = ((70, (8, 10)), (71, (8, 7, 10)))
# The same stacks once 8 has left #70.
MOVED_STACKS = ((70, (10,)), (71, (8, 7, 10)))


def with_stacks(
    answers: dict[str, Any], stacks: Sequence[tuple[int, Sequence[int]]] = STACKS
) -> dict[str, Any]:
    """The stand-in's answers, and its native *stacks* for ``gh stack``, by default
    :data:`STACKS`."""

    listed = [
        {
            "number": number,
            "url": f"https://api.github.com/repos/octo/demo/stacks/{number}",
            "base": {"ref": "main"},
            "open": True,
            "pull_requests": [{"number": pull} for pull in pulls],
        }
        for number, pulls in stacks
    ]
    return {
        **answers,
        "stack_version": "0.1.0",
        "api": {**answers["api"], STACKS_PATH: ok(STACKS_PATH, listed)},
    }


def run_measurement(
    tmp_path: Path,
    chrome_profile: Path,
    *,
    session: Path = SESSION,
    build: tuple[str, ...] = (),
    moves: bool = False,
) -> GroupRun:
    """Build the stand-in's home with stacks, serve it, and run *session* against it.

    *build* are the fixture's build flags, ``--guided-stack`` for the guides. With *moves*,
    the session is told the answers file the server's fake gh reads (``STACK_ANSWERS``) and
    the same answers with 8 gone from #70 (``STACK_MOVED``), which it writes over the first
    to move the stack."""

    chrome = require_chrome()
    node = require_node()
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env["METABROWSER_CONFIG_DIR"] = str(_private(tmp_path / "config"))
    env["METABROWSER_LOG_LEVEL"] = "WARNING"
    stand_in = tmp_path / "stand-in"
    stand_in.mkdir()
    built = subprocess.run(
        [sys.executable, str(FIXTURE), str(stand_in), *build],
        capture_output=True,
        text=True,
        env=env,
        timeout=_BUILD_BUDGET_S,
        check=False,
    )
    assert built.returncode == 0, built.stderr[-4000:]
    answers = stand_in / "fake-gh-scenario.json"
    built_answers = json.loads(answers.read_text(encoding="utf-8"))
    answers.write_text(json.dumps(with_stacks(built_answers)), encoding="utf-8")
    moved = tmp_path / "fake-gh-scenario-moved.json"
    moved.write_text(json.dumps(with_stacks(built_answers, MOVED_STACKS)), encoding="utf-8")
    port = _free_port()
    log = tmp_path / "server.log"
    with log.open("w", encoding="utf-8") as output:
        # --exit-on-eof: closing stdin stops the server however this test ends.
        server = subprocess.Popen(
            [
                sys.executable,
                str(FIXTURE),
                str(stand_in),
                "--serve",
                "10",
                str(port),
                "--exit-on-eof",
            ],
            stdin=subprocess.PIPE,
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            start_new_session=True,
        )
    try:
        _wait_until_serving(server, port, log)
        shots = os.environ.get("METABROWSER_STACK_PAGE_SHOTS")
        run = run_in_own_group(
            [node, str(session), f"http://127.0.0.1:{port}"],
            timeout_s=_MEASUREMENT_BUDGET_S,
            env={
                **os.environ,
                "CHROME_BIN": chrome,
                "CHROME_PROFILES": str(chrome_profile),
                **({"SHOTS_DIR": shots, "MEASURE_OUT": f"{shots}/measured.json"} if shots else {}),
                **({"STACK_ANSWERS": str(answers), "STACK_MOVED": str(moved)} if moves else {}),
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


def test_the_stack_page_is_a_pull_request_page_that_holds_still_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    run = run_measurement(tmp_path, chrome_profile)
    passed = re.fullmatch(r"stack page in Chrome: (\d+) checks passed\n", run.stdout)
    assert passed is not None and int(passed.group(1)) > 0, run.stdout


def test_the_stack_page_lays_out_as_a_pull_request_page_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    run = run_measurement(tmp_path, chrome_profile, session=LAYOUT, build=("--guided-stack",))
    passed = re.fullmatch(r"stack page layout in Chrome: (\d+) checks passed\n", run.stdout)
    assert passed is not None and int(passed.group(1)) > 0, run.stdout


def test_the_stack_page_says_what_changed_and_its_button_draws_it_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    run = run_measurement(tmp_path, chrome_profile, session=NOTICE, moves=True)
    passed = re.fullmatch(r"stack page notice in Chrome: (\d+) checks passed\n", run.stdout)
    assert passed is not None and int(passed.group(1)) > 0, run.stdout
