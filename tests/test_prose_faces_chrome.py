"""The face rendered text is drawn in, in headless Chrome against a live server.

A document reads in the reading font and chrome prose in sans under either, as
docs/design-system.md's "Serif Is for Documents" says, under both reading fonts and both
font sets (tests/dom/prose-faces-chrome.mjs). A face is the cascade's answer, which only a
browser computes: a check of the stylesheets' text passed while a pull request's page set
the Markdown files in its Changes in sans. Which texts carry ``.chrome-prose`` is checked
browserless in tests/dom/github-pull-first-paint-behavior.js, and which rules may set a
face for a text in ``test_serif_is_only_for_documents``.

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
from pathlib import Path

from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_git, require_node

SESSION = Path(__file__).resolve().parent / "dom" / "prose-faces-chrome.mjs"
# The test runs against one deadline, which the server's start and the session share, the
# start at most SERVER_START_TIMEOUT_S of it. The whole test took 5.4 s on a Mac at a load
# average of 7, the session 2.5 s of it. What is left after the session is reserved for
# stopping its process group, the server, and the profile (tests/process_group.py).
RUN_BUDGET_S = 30
SERVER_START_TIMEOUT_S = 20
# The server stops on SIGTERM well inside this, and is killed after it.
SERVER_TERM_S = 5
SERVER_KILL_S = 2
# The longest the test can take; tests/test_process_group.py holds it under the suite's
# 60 s per-test timeout, which ends the whole run when it fires.
LIFECYCLE_S = RUN_BUDGET_S + GROUP_STOP_S + SERVER_TERM_S + SERVER_KILL_S + PROFILE_TEARDOWN_S
_METAB = Path(sys.executable).with_name("metab")


def _repository(root: Path) -> str:
    """A repository with a document, a README, and a commit with a body; its commit ID."""

    (root / "doc.md").write_text(
        "# Document\n\nA paragraph of document prose, in the Document view.\n", encoding="utf-8"
    )
    (root / "README.md").write_text(
        "# Faces\n\nA paragraph of README prose, on the Overview.\n", encoding="utf-8"
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


def test_documents_read_in_the_reading_font_and_chrome_prose_in_sans(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    served = tmp_path / "served"
    served.mkdir()
    commit = _repository(served)
    deadline = time.monotonic() + RUN_BUDGET_S
    server = subprocess.Popen(
        [
            str(_METAB),
            str(served),
            "--no-open",
            "--port",
            str(_free_port()),
            "--cache-dir",
            str(tmp_path / "cache"),
            "--config-dir",
            str(tmp_path / "config"),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env={**os.environ, "METABROWSER_LOG_LEVEL": "WARNING"},
    )
    try:
        assert server.stdout is not None
        found: list[str] = []
        reader = threading.Thread(
            target=lambda: found.extend(
                match.group(1)
                for line in server.stdout or ()
                if (match := re.search(r"Serving .* at (http://127\.0\.0\.1:\d+)/", line))
            ),
            daemon=True,
        )
        reader.start()
        start_deadline = min(deadline, time.monotonic() + SERVER_START_TIMEOUT_S)
        while not found and time.monotonic() < start_deadline and server.poll() is None:
            time.sleep(0.05)
        assert found, "the server did not say where it serves"
        # The session leads a process group of its own, which Chrome joins, and the whole
        # group is stopped however it ends; its profile is the fixture's to remove
        # (tests/process_group.py).
        result = run_in_own_group(
            [require_node(), str(SESSION), found[0], commit],
            timeout_s=max(0.0, deadline - time.monotonic()),
            env={**os.environ, "CHROME_BIN": chrome, "CHROME_PROFILES": str(chrome_profile)},
        )
        assert not result.timed_out, (
            f"the session ran past the test's {RUN_BUDGET_S} s: {result.stderr or result.stdout}"
        )
        assert result.returncode == 0, result.stderr or result.stdout
        passed = re.fullmatch(r"prose faces in Chrome: (\d+) checks passed\n", result.stdout)
        assert passed is not None and int(passed.group(1)) > 0, result.stdout
    finally:
        server.terminate()
        try:
            server.wait(timeout=SERVER_TERM_S)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=SERVER_KILL_S)
