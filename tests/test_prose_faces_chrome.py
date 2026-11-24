"""The face rendered text is drawn in, in headless Chrome against a live server.

A document reads in the reading font and chrome prose in sans under either, as
docs/design-system.md's "Serif Is for Documents" says, under both reading fonts and both
font sets (tests/dom/prose-faces-chrome.mjs). Each Markdown text's h2 is italic only in a
serif document; upright in the sans, it keeps its size, weight, and margins. A face is
the cascade's answer, which only a browser computes: a check of the stylesheets' text
passed while a pull request's page set the Markdown files in its Changes in sans. Which
texts carry ``.chrome-prose`` is checked browserless in
tests/dom/github-pull-first-paint-behavior.js, and which rules may set a face for a text
in ``test_serif_is_only_for_documents``.

A Markdown file among a pull request's Docs or Changes is also read on the page itself, a
pull request of the GitHub stand-in (tests/github_pull_fixture.py), where only the diff
loads KPress's stylesheets: the diff once dropped every one whose address held the `+` of
an editable KPress's version, and the file read in sans under the serif reading font
(mb-2r08). tests/dom/prose-faces-diff-chrome.mjs gives each projection's addresses such a
version.

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``).
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import pytest

from tests.github_pull_fixture import Origin, install_fake_gh, scenario
from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_git, require_node

SESSION = Path(__file__).resolve().parent / "dom" / "prose-faces-chrome.mjs"
DIFF_SESSION = Path(__file__).resolve().parent / "dom" / "prose-faces-diff-chrome.mjs"
FIXTURE = Path(__file__).resolve().parent / "github_pull_fixture.py"
# The documents test bounds the server's start, up to its "Serving" line, by
# SERVER_START_TIMEOUT_S, and then the session, from that line, by RUN_BUDGET_S. One
# deadline shared by both, set to 30 s from a 5.4 s run at a load average of 7, let a slow
# start take the session's time, and a loaded machine take all of it (mb-w8al). Measured
# on a 10-core Mac on 2026-11-23: alone at a load average near 95 the server started in
# 2.0 to 4.8 s and the session took 8.1 to 9.9 s; six at once, the load rising from 105 to
# 180, the session took 27.6 to 28.6 s (Chrome's start 4.3 to 4.8 s, its 12 pages 0.3 to
# 4.6 s each and 16.4 to 17.8 s together), and five of the six whole runs passed 30 s. A
# run at a load average near 400 beside two other Chrome sessions reached 6 of its 12
# pages, at 1.1 to 4.2 s each, inside the old 30 s; at that pace all 12 take about 60 s,
# which 90 s holds. The figures that bound each part, Chrome's start (START_BOUND_MS) and
# each page's waits (PROBE_WAIT_MS), are in the session (tests/dom/prose-faces-chrome.mjs).
# What is left after the session is reserved for stopping its process group, the server,
# and the profile (tests/process_group.py).
RUN_BUDGET_S = 90
SERVER_START_TIMEOUT_S = 20
# The server stops on SIGTERM well inside this, and is killed after it.
SERVER_TERM_S = 5
SERVER_KILL_S = 2
# The rendered diff's test: the stand-in's server, which fetches its mirror from the
# origin's file before it serves, and a session of 8 pull request pages. On a Mac with 10
# cores the whole test took 15.0 s at a load average near 210; at one near 300, with two
# other Chrome sessions running, the session alone took 37 s, a cold Chrome start among
# it, and each page from 0.9 to 4.2 s (its stderr names each page's time).
DIFF_RUN_BUDGET_S = 120
DIFF_SERVER_START_TIMEOUT_S = 40
# The longest either test can take; tests/test_process_group.py holds it under the
# module's timeout, which ends the whole run when it fires.
LIFECYCLE_S = (
    max(SERVER_START_TIMEOUT_S + RUN_BUDGET_S, DIFF_RUN_BUDGET_S)
    + GROUP_STOP_S
    + SERVER_TERM_S
    + SERVER_KILL_S
    + PROFILE_TEARDOWN_S
)
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)
_METAB = Path(sys.executable).with_name("metab")
# The session's checks, pinned so a probe or a pass that stops running is seen. Each of its
# four passes, a reading font and a font set, checks <html> on each of its 3 pages, the
# face of each of its 8 probes, the style of the h2 in each of the 6 that hold Markdown,
# and that chrome prose's KPress h2 has the Document view h2's size, weight and margins;
# in the clean set it also checks the face Chrome drew for each probe set in the sans,
# which is all 8 under the sans reading font and the 4 chrome probes under the serif one;
# and in each set, under the sans reading font, that each of the 6 h2s keeps its size,
# weight and margins: 4 * (3 + 8 + 6 + 1) + 8 + 4 + 2 * 6.
CHECKS = 96
# The rendered diff session's checks: in each of its four passes, on each of its 2 pages,
# that KPress's document.css loaded from the local version's address and that the diff
# warned of nothing, and the face of the added paragraph, which in the clean set under the
# sans reading font is also the face Chrome drew: 2 * (4 * 2 + 1 + 1 + 2 + 1).
DIFF_CHECKS = 26


def _repository(root: Path) -> str:
    """A repository with a document, a README, and a commit with a body; its commit ID."""

    (root / "doc.md").write_text(
        "# Document\n\nA paragraph of document prose, in the Document view.\n\n"
        "## A document section\n\nMore of the document.\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        "# Faces\n\nA paragraph of README prose, on the Overview.\n\n"
        "## A README section\n\nMore of the README.\n",
        encoding="utf-8",
    )
    git = [
        require_git(),
        "-C",
        str(root),
        "-c",
        "user.name=Faces",
        "-c",
        "user.email=faces@example.invalid",
    ]
    subprocess.run([*git, "init", "-q", "-b", "main"], check=True)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run(
        [
            *git,
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-q",
            "-m",
            "Add the documents",
            "-m",
            "A commit body paragraph, under the subject.",
        ],
        check=True,
    )
    head = subprocess.run(
        [*git, "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout
    return head.strip()


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@contextmanager
def _serving(command: list[str], env: dict[str, str], deadline: float) -> Generator[str]:
    """Start *command*, a Metabrowser server; yield the address it says it serves at."""

    server = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env
    )
    try:
        assert server.stdout is not None
        found: list[str] = []
        said: list[str] = []

        def read() -> None:
            for line in server.stdout or ():
                said.append(line)
                if match := re.search(r"Serving .* at (http://127\.0\.0\.1:\d+)/", line):
                    found.append(match.group(1))

        threading.Thread(target=read, daemon=True).start()
        while not found and time.monotonic() < deadline and server.poll() is None:
            time.sleep(0.05)
        assert found, f"the server did not say where it serves: {''.join(said)[-2000:]}"
        yield found[0]
    finally:
        server.terminate()
        try:
            server.wait(timeout=SERVER_TERM_S)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=SERVER_KILL_S)


def test_documents_read_in_the_reading_font_and_chrome_prose_in_sans(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    served = tmp_path / "served"
    served.mkdir()
    commit = _repository(served)
    command = [
        str(_METAB),
        str(served),
        "--no-open",
        "--port",
        str(_free_port()),
        "--cache-dir",
        str(tmp_path / "cache"),
        "--config-dir",
        str(tmp_path / "config"),
    ]
    env = {**os.environ, "METABROWSER_LOG_LEVEL": "WARNING"}
    with _serving(command, env, time.monotonic() + SERVER_START_TIMEOUT_S) as base:
        # The session leads a process group of its own, which Chrome joins, and the whole
        # group is stopped however it ends; its profile is the fixture's to remove
        # (tests/process_group.py).
        result = run_in_own_group(
            [require_node(), str(SESSION), base, commit],
            timeout_s=RUN_BUDGET_S,
            env={**os.environ, "CHROME_BIN": chrome, "CHROME_PROFILES": str(chrome_profile)},
        )
    assert not result.timed_out, (
        f"the session ran past its {RUN_BUDGET_S} s: {result.stderr or result.stdout}"
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout == f"prose faces in Chrome: {CHECKS} checks passed\n", result.stdout


def test_a_pull_requests_rendered_markdown_reads_in_the_reading_font(
    tmp_path: Path, pull_origin: Origin, chrome_profile: Path
) -> None:
    """Pull request 8 of the stand-in, served as ``serve_stand_in`` serves it: its own
    process takes the stand-in's seams, the origin's address and the Git floor, so this
    process keeps neither. Its Docs and Changes show docs/guide.md rendered."""

    chrome = require_chrome()
    assert pull_origin.path.parent == tmp_path, "serve_stand_in reads the origin beside its home"
    install_fake_gh(tmp_path, scenario(pull_origin))
    config = tmp_path / "config"
    config.mkdir(mode=0o700)
    deadline = time.monotonic() + DIFF_RUN_BUDGET_S
    command = [sys.executable, str(FIXTURE), str(tmp_path), "--serve", "8", str(_free_port())]
    env = {
        **os.environ,
        "METABROWSER_CONFIG_DIR": str(config),
        "METABROWSER_LOG_LEVEL": "WARNING",
    }
    start_deadline = min(deadline, time.monotonic() + DIFF_SERVER_START_TIMEOUT_S)
    with _serving(command, env, start_deadline) as base:
        result = run_in_own_group(
            [require_node(), str(DIFF_SESSION), base],
            timeout_s=max(0.0, deadline - time.monotonic()),
            env={**os.environ, "CHROME_BIN": chrome, "CHROME_PROFILES": str(chrome_profile)},
        )
    assert not result.timed_out, (
        f"the session ran past the test's {DIFF_RUN_BUDGET_S} s: {result.stderr or result.stdout}"
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout == f"rendered diff faces in Chrome: {DIFF_CHECKS} checks passed\n", (
        result.stdout
    )
