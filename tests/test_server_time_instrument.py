"""The server-time instrument (explorations/performance-loop/server-time*.mjs).

Its pure logic runs browserless: request-log lines with and without the precise end of
the body, Server-Timing values, route families, pairing the log with Resource Timing,
a window's sums by phase, and the serial pass. Its driver is the transition harness's
own browser launcher, which tests/test_transitions_instrument.py runs in Chrome. The
line it reads is the server's own: a request the application logs here is parsed by the
instrument's parser, so a change to the log line that the instrument cannot read fails.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route
from starlette.testclient import TestClient

from metabrowser import server, server_timing
from tests.required_tools import require_node

DOM = Path(__file__).parent / "dom"
SUMS = (
    Path(__file__).resolve().parents[1]
    / "explorations"
    / "performance-loop"
    / "server-time-sums.mjs"
)


def test_server_time_instrument_logic() -> None:
    result = subprocess.run(
        [require_node(), str(DOM / "server-time-behavior.mjs")],
        capture_output=True,
        check=False,
        text=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "server-time instrument: 13 checks passed\n"


class _Lines(logging.Handler):
    """The log lines as the server's own stderr handler formats them."""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.setFormatter(logging.Formatter("%(asctime)s %(name)s | %(message)s", "%H:%M:%S"))
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))


def test_the_instrument_reads_the_line_the_server_writes() -> None:
    async def answer(_request: Request) -> Response:
        with server_timing.phase("read"):
            body = b"metabrowser " * 400
        return Response(body, media_type="text/plain")

    app = Starlette(
        routes=[Route("/static/a b.js", answer)],
        middleware=[
            Middleware(server._SlowRequestLogMiddleware, threshold_ms=0, verbose=True),  # pyright: ignore[reportPrivateUsage]
            Middleware(server_timing.TimedGZipMiddleware, minimum_size=1024, compresslevel=6),
        ],
    )
    capture = _Lines()
    server.LOG.addHandler(capture)
    try:
        TestClient(app).get("/static/a%20b.js?v=1", headers={"accept-encoding": "gzip"})
    finally:
        server.LOG.removeHandler(capture)
    [line] = [text for text in capture.lines if "metabrowser request t=" in text]
    result = subprocess.run(
        [
            require_node(),
            "--input-type=module",
            "-e",
            f"const m = await import({json.dumps(SUMS.as_uri())});"
            "process.stdout.write(JSON.stringify(m.parseRequestLine(process.argv[1])));",
            line,
        ],
        capture_output=True,
        check=True,
        text=True,
        timeout=20,
    )
    row = json.loads(result.stdout)
    assert row["path"] == "/static/a b.js?v=1"
    assert row["method"] == "GET"
    assert row["status"] == 200
    assert row["precise"] is True
    assert row["end_ms"] >= 0
    assert set(row["phases"]) == {"read", "encode"}
