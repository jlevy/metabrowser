"""The staged view's font wait, in headless Chrome against a live server.

A cold landing on a plain document, then, in the same page, a document set in faces the
first did not use: neither document's paragraphs may move once it is shown. The faces'
requests wait 40 ms each, with the HTTP cache off, so every face lands after the stage
could have been shown (tests/dom/staged-fonts-chrome.mjs). Which faces the wait asks for
is checked browserless in tests/dom/staged-fonts-behavior.js.

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
from tests.required_tools import require_chrome, require_node

SESSION = Path(__file__).resolve().parent / "dom" / "staged-fonts-chrome.mjs"
# The test runs against one deadline. The whole test, the server's start and the session
# together, took 11.2 s on a Mac at a load average of 9 to 13, and 5.2 s in CI. The
# server's start and the session share RUN_BUDGET_S, the start at most
# SERVER_START_TIMEOUT_S of it; what is left after them is reserved for stopping the
# session's process group, the server, and the profile (tests/process_group.py).
RUN_BUDGET_S = 30
SERVER_START_TIMEOUT_S = 20
# The server stops on SIGTERM well inside this, and is killed after it.
SERVER_TERM_S = 5
SERVER_KILL_S = 2
# The longest the test can take; tests/test_process_group.py holds it under the suite's
# 60 s per-test timeout, which ends the whole run when it fires.
LIFECYCLE_S = RUN_BUDGET_S + GROUP_STOP_S + SERVER_TERM_S + SERVER_KILL_S + PROFILE_TEARDOWN_S
_METAB = Path(sys.executable).with_name("metab")
_TEXT = (
    "A reserved box keeps its place when the content that fills it arrives, and a face "
    "that lands after the text it sets is shown moves every line after the first one "
    "it changes, so the wait asks for the faces before the stage is shown. "
)


def _documents(root: Path) -> None:
    plain = ["PLAIN-DOCUMENT", "", *[f"{_TEXT * 2}{index}\n" for index in range(60)]]
    italic = ["*ITALIC-DOCUMENT*", "", *[f"*{_TEXT * 2}{index}*\n" for index in range(60)]]
    (root / "plain.md").write_text("\n".join(plain), encoding="utf-8")
    (root / "italic.md").write_text("\n".join(italic), encoding="utf-8")


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def test_no_document_moves_when_its_faces_land(tmp_path: Path, chrome_profile: Path) -> None:
    chrome = require_chrome()
    deadline = time.monotonic() + RUN_BUDGET_S
    served = tmp_path / "served"
    served.mkdir()
    _documents(served)
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
            [require_node(), str(SESSION), found[0]],
            timeout_s=max(0.0, deadline - time.monotonic()),
            env={**os.environ, "CHROME_BIN": chrome, "CHROME_PROFILES": str(chrome_profile)},
        )
        assert not result.timed_out, (
            f"the session ran past the test's {RUN_BUDGET_S} s: {result.stderr or result.stdout}"
        )
        assert result.returncode == 0, result.stderr or result.stdout
        assert re.fullmatch(r"staged fonts in Chrome: \d+ checks passed\n", result.stdout), (
            result.stdout
        )
    finally:
        server.terminate()
        try:
            server.wait(timeout=SERVER_TERM_S)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=SERVER_KILL_S)
