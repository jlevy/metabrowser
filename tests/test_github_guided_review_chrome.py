"""A pull request's Guided Review tab, key, and excerpts on the real shell, in headless Chrome.

The shell's highlighter runs over every ``pre code`` that does not carry ``no-highlight``
(``highlightCode`` in ``static/app.js``), one element at a time. Each row of an excerpt is a
``code`` in a ``pre``, so the first version of the tab had the highlighter take every one for a
snippet in some language: a word became SQL, and each row got the padding, block, and gray
background of ``pre code.hljs`` inside the tint of its own row (review A of #599, A3). Which
rows the highlighter touched, and what a row paints, are the browser's; so this serves the
GitHub stand-in, whose pull requests 7 to 9 have guides in their descriptions, 8's rewritten
into groups, and whose 10 has none, and ``tests/dom/github-guided-review-chrome.mjs`` drives it: the tab and
its key on a pull request with a guide and with none, the shell's own pass over the excerpt, a
row's layout, the steps and Open full diff, where a group's heading and note sit, how a note's
rendered Markdown is set, and a guide that cannot be read. Browserless, the tab's key and its
lazy mount are pinned in ``tests/dom/github-pull-page-mount-behavior.js`` and
``tests/dom/github-guided-review-mount-behavior.js``. An out-of-date guide's notice, its marks,
and where a list's markers fall against the bordered box around them are paint too, so they are
measured here: a marker on or past a border is what the first out-of-date notice drew (mb-u46w).

A step that cites past its pull request draws a pull request and a commit as rows, whose
height, borders, cut titles, and parts' order along the line are paint, so
``tests/dom/github-guided-review-kinds-chrome.mjs`` measures them, at a desktop width and a
phone's, and that another pull request's document draws from that pull request's own routes on
the real server, on a stand-in whose pull request 7's guide cites every kind of reference
(``--describe 7 kinds``), with the stack page's native stacks and 300 (``KINDS_STACKS``), so one
cited pull request has a place in its guide's own stack, one a place in another stack, which
its row names, and one none, each place named for assistive technology by its tip; and again
from a reader's clone of the repository, which lacks 7's head, so the commit's row says it is
not in this checkout and still ends in its age.

Where each row of the step list starts is paint too, so
``tests/dom/github-guided-review-outline-chrome.mjs`` measures it, in the light and the dark
scheme at a desktop width and a phone's, on a stand-in whose 7 has a guide with no group, 8
a group and then a step outside it (``--describe 8 mixed``), and 9 ten steps in no group
(``--describe 9 ten-steps``): a row outside any group, the overview's among them, starts on
the edge a group's heading starts on, and a group's steps keep their column under it.

A step's rendered document is the diff view's own drawing of a file over the server's
projection, so ``tests/dom/github-guided-review-documents-chrome.mjs`` compares a Markdown
document with the Docs tab's drawing of the same file, and a YAML document with the Changes
tab's, on a stand-in whose pull request 7's guide ends on a step that cites both whole
(``--guided-documents``).

Whether anything in the guide moves while a step lands is paint too, so
``tests/dom/github-guided-review-motion-chrome.mjs`` samples the guide every frame from a
press, or a page load, to the step it settles on, and holds that nothing moves from the
first frame a step shows and that the step the reader leaves stays as it was until then:
cold, on a page loaded on Guided Review and a step not read ahead, and warm, on a step read
ahead or kept, where no loading state shows either; on pull request 7's guide, which ends
on documents (``--guided-documents``), and on stack 70's (``--guided-stack``, with the
stack page's native stacks).

A step's file card folds by the diff view's own bar and chevron, and where the chevron sits
and how the bar is painted are the browser's, so
``tests/dom/github-guided-review-fold-chrome.mjs`` measures the card's bar against a file's
in the same server's Changes tab, open and folded, and folds and opens it with a real press.
Browserless, the bar's state machine is pinned in ``tests/dom/diff-view-behavior.js`` and the
card built from it in ``tests/dom/github-guided-review-mount-behavior.js``.

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``). The test owns
everything it starts: the server stops when its stdin closes, and the measuring Node process
leads a process group of its own, which Chrome joins (tests/process_group.py).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_node
from tests.test_github_stack_page_chrome import STACKS, with_stacks
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
SESSION = Path(__file__).resolve().parent / "dom" / "github-guided-review-chrome.mjs"
DOCUMENTS = Path(__file__).resolve().parent / "dom" / "github-guided-review-documents-chrome.mjs"
KINDS = Path(__file__).resolve().parent / "dom" / "github-guided-review-kinds-chrome.mjs"
OUTLINE = Path(__file__).resolve().parent / "dom" / "github-guided-review-outline-chrome.mjs"
MOTION = Path(__file__).resolve().parent / "dom" / "github-guided-review-motion-chrome.mjs"
FOLD = Path(__file__).resolve().parent / "dom" / "github-guided-review-fold-chrome.mjs"
# The stack page's native stacks, and 300, which holds 9 and then 50, so a pull request the
# kinds guide cites has a place in a stack other than 7's, which its row names.
KINDS_STACKS = (*STACKS, (300, (9, 50)))
# Building the stand-in's home runs the production CLI four times through a fake gh; it took
# about 5 s at a load average near 20 (2026-11-20).
_BUILD_BUDGET_S = 60.0
# A cold Chrome start, which tests/dom/chrome-session.mjs bounds at 30 s, then nine page loads
# and a few clicks, each bounded at 30 s in the script; the whole run took 12 s here.
_MEASUREMENT_BUDGET_S = 150.0
LIFECYCLE_S = (
    _BUILD_BUDGET_S
    + _SERVING_BUDGET_S
    + _MEASUREMENT_BUDGET_S
    + GROUP_STOP_S
    + 2 * _SERVER_STOP_S
    + PROFILE_TEARDOWN_S
)
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)


def _session(
    tmp_path: Path,
    chrome_profile: Path,
    mode: str,
    session: Path,
    describe: Sequence[tuple[str, str]] = (("8", "grouped"),),
    stacks: Sequence[tuple[int, Sequence[int]]] = (),
    checkout: bool = False,
    arguments: Sequence[str] = (),
) -> str:
    """Build the stand-in in fixture *mode*, write each guide *describe* names into its pull
    request's description, give it the native *stacks*, serve pull request 7, from a
    reader's clone of the repository with *checkout*, and run *session* on it, told
    `checkout` then too, and *arguments*."""
    chrome = require_chrome()
    node = require_node()
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env["METABROWSER_CONFIG_DIR"] = str(_private(tmp_path / "config"))
    env["METABROWSER_LOG_LEVEL"] = "WARNING"
    stand_in = tmp_path / "stand-in"
    stand_in.mkdir()
    # Guides are rewritten after the build, whichever mode built it: by default 8's, in groups.
    for build in ([mode], *(["--describe", *each] for each in describe)):
        built = subprocess.run(
            [sys.executable, str(FIXTURE), str(stand_in), *build],
            capture_output=True,
            text=True,
            env=env,
            timeout=_BUILD_BUDGET_S,
            check=False,
        )
        assert built.returncode == 0, built.stderr[-4000:]
    if stacks:
        answers = stand_in / "fake-gh-scenario.json"
        answers.write_text(
            json.dumps(with_stacks(json.loads(answers.read_text(encoding="utf-8")), stacks)),
            encoding="utf-8",
        )
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
                "7",
                str(port),
                *(["--checkout"] if checkout else []),
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
        run = run_in_own_group(
            [
                node,
                str(session),
                f"http://127.0.0.1:{port}",
                *(["checkout"] if checkout else []),
                *arguments,
            ],
            timeout_s=_MEASUREMENT_BUDGET_S,
            env={**os.environ, "CHROME_BIN": chrome, "CHROME_PROFILES": str(chrome_profile)},
        )
    finally:
        _stop_server(server)
    if run.timed_out:
        pytest.fail(f"ran past {_MEASUREMENT_BUDGET_S:g} s:\n{run.stderr}")
    assert run.returncode == 0, f"{run.stderr[-6000:]}\nserver: {_log_tail(log)}"
    return run.stdout


def test_guided_review_tab_and_excerpts_in_chrome(tmp_path: Path, chrome_profile: Path) -> None:
    stdout = _session(tmp_path, chrome_profile, "--guided", SESSION)
    passed = re.fullmatch(r"guided review in Chrome: (\d+) checks passed\n", stdout)
    assert passed is not None and int(passed.group(1)) > 0, stdout


def test_guided_review_documents_in_chrome(tmp_path: Path, chrome_profile: Path) -> None:
    stdout = _session(tmp_path, chrome_profile, "--guided-documents", DOCUMENTS)
    passed = re.fullmatch(r"guided review documents in Chrome: (\d+) checks passed\n", stdout)
    assert passed is not None and int(passed.group(1)) > 0, stdout


def test_guided_review_reference_rows_in_chrome(tmp_path: Path, chrome_profile: Path) -> None:
    stdout = _session(
        tmp_path, chrome_profile, "--guided", KINDS, describe=(("7", "kinds"),), stacks=KINDS_STACKS
    )
    passed = re.fullmatch(r"guided review references in Chrome: (\d+) checks passed\n", stdout)
    assert passed is not None and int(passed.group(1)) > 0, stdout


def test_guided_review_reference_rows_from_a_checkout_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    """The same rows served from a reader's clone, which lacks 7's head, so its commit row
    says so and still ends in its age (A5 of review A on #853)."""
    stdout = _session(
        tmp_path,
        chrome_profile,
        "--guided",
        KINDS,
        describe=(("7", "kinds"),),
        stacks=KINDS_STACKS,
        checkout=True,
    )
    passed = re.fullmatch(
        r"guided review references from a checkout in Chrome: (\d+) checks passed\n", stdout
    )
    assert passed is not None and int(passed.group(1)) > 0, stdout


def test_guided_review_outline_in_chrome(tmp_path: Path, chrome_profile: Path) -> None:
    stdout = _session(
        tmp_path,
        chrome_profile,
        "--guided",
        OUTLINE,
        describe=(("8", "mixed"), ("9", "ten-steps")),
    )
    passed = re.fullmatch(r"guided review outline in Chrome: (\d+) checks passed\n", stdout)
    assert passed is not None and int(passed.group(1)) > 0, stdout


def test_guided_review_holds_still_in_chrome(tmp_path: Path, chrome_profile: Path) -> None:
    stdout = _session(tmp_path, chrome_profile, "--guided-documents", MOTION, arguments=("pull",))
    passed = re.fullmatch(r"guided review motion in Chrome \(pull\): (\d+) checks passed\n", stdout)
    assert passed is not None and int(passed.group(1)) > 0, stdout


def test_a_stack_guide_holds_still_in_chrome(tmp_path: Path, chrome_profile: Path) -> None:
    stdout = _session(
        tmp_path, chrome_profile, "--guided-stack", MOTION, stacks=STACKS, arguments=("stack",)
    )
    passed = re.fullmatch(
        r"guided review motion in Chrome \(stack\): (\d+) checks passed\n", stdout
    )
    assert passed is not None and int(passed.group(1)) > 0, stdout


def test_a_guided_file_folds_as_a_changes_file_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    stdout = _session(tmp_path, chrome_profile, "--guided-documents", FOLD)
    passed = re.fullmatch(r"guided review fold in Chrome: (\d+) checks passed\n", stdout)
    assert passed is not None and int(passed.group(1)) > 0, stdout
