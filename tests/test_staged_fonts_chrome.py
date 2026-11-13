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

from tests.required_tools import require_chrome, require_node

SESSION = Path(__file__).resolve().parent / "dom" / "staged-fonts-chrome.mjs"
# The whole test, the server's start and the session together, took 11.2 s on a Mac at a
# load average of 9 to 13. Each bound fires before the suite's 60 s, and the two together
# do too.
SERVER_START_TIMEOUT_S = 20
SESSION_TIMEOUT_S = 35
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


def test_no_document_moves_when_its_faces_land(tmp_path: Path) -> None:
    chrome = require_chrome()
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
        deadline = time.monotonic() + SERVER_START_TIMEOUT_S
        while not found and time.monotonic() < deadline and server.poll() is None:
            time.sleep(0.05)
        assert found, "the server did not say where it serves"
        result = subprocess.run(
            [require_node(), str(SESSION), found[0]],
            capture_output=True,
            text=True,
            timeout=SESSION_TIMEOUT_S,
            check=False,
            env={**os.environ, "CHROME_BIN": chrome},
        )
        assert result.returncode == 0, result.stderr or result.stdout
        assert re.fullmatch(r"staged fonts in Chrome: \d+ checks passed\n", result.stdout), (
            result.stdout
        )
    finally:
        server.terminate()
        try:
            server.wait(timeout=20)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=20)
