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
row's layout, the steps and Open full diff, where a group's heading and note sit, and a guide
that cannot be read. Browserless, the tab's key and its
lazy mount are pinned in ``tests/dom/github-pull-page-mount-behavior.js`` and
``tests/dom/github-guided-review-mount-behavior.js``. An out-of-date guide's notice, its marks,
and where a list's markers fall against the bordered box around them are paint too, so they are
measured here: a marker on or past a border is what the first out-of-date notice drew (mb-u46w).

A step's rendered document is the diff view's own drawing of a file over the server's
projection, so ``tests/dom/github-guided-review-documents-chrome.mjs`` compares a Markdown
document with the Docs tab's drawing of the same file, and a YAML document with the Changes
tab's, on a stand-in whose pull request 7's guide ends on a step that cites both whole
(``--guided-documents``).

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``). The test owns
everything it starts: the server stops when its stdin closes, and the measuring Node process
leads a process group of its own, which Chrome joins (tests/process_group.py).
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


def _session(tmp_path: Path, chrome_profile: Path, mode: str, session: Path) -> str:
    """Build the stand-in in fixture *mode*, serve pull request 7, and run *session* on it."""
    chrome = require_chrome()
    node = require_node()
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env["METABROWSER_CONFIG_DIR"] = str(_private(tmp_path / "config"))
    env["METABROWSER_LOG_LEVEL"] = "WARNING"
    stand_in = tmp_path / "stand-in"
    stand_in.mkdir()
    # Pull request 8's guide is rewritten in groups after the build, whichever mode built it.
    for build in ([mode], ["--describe", "8", "grouped"]):
        built = subprocess.run(
            [sys.executable, str(FIXTURE), str(stand_in), *build],
            capture_output=True,
            text=True,
            env=env,
            timeout=_BUILD_BUDGET_S,
            check=False,
        )
        assert built.returncode == 0, built.stderr[-4000:]
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
            [node, str(session), f"http://127.0.0.1:{port}"],
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
