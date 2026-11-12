"""Named ``Server-Timing`` phases, and the request log for what a header cannot carry.

``Server-Timing`` used to be one ``srv`` metric taken at response start, so a slow
route could not say whether it read, rendered, waited on git, or compressed (research
2026-11-11: gzip ran on the event loop at about 33 MB/s and nothing reported it).
"""

from __future__ import annotations

import asyncio
import logging
import re
import subprocess
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from metabrowser import server, server_timing
from tests.required_tools import require_git

METRIC = re.compile(r"([a-z]+);dur=([0-9.]+)")


def _metrics(header: str) -> dict[str, float]:
    return {name: float(ms) for name, ms in METRIC.findall(header)}


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


@pytest.fixture
def served(tmp_path: Path) -> TestClient:
    (tmp_path / "a.md").write_text("# A\n\n" + "Some prose. " * 400 + "\n")
    server._set_root_dir(tmp_path)
    return TestClient(server.app)


def test_a_rendered_document_names_its_read_render_and_encode(served: TestClient) -> None:
    answer = served.get("/api/kpress/render", params={"path": "a.md"})
    assert answer.status_code == 200
    header = answer.headers["server-timing"]
    assert header.startswith("srv;dur="), "perf.js and the probes read `srv` first"
    metrics = _metrics(header)
    assert {"srv", "read", "render", "encode"} <= set(metrics)
    # The phases finished before the headers, so none is longer than the time to them.
    assert all(metrics[name] <= metrics["srv"] + 0.1 for name in ("read", "render", "encode"))


def test_a_file_envelope_names_its_read_and_encode(served: TestClient) -> None:
    metrics = _metrics(served.get("/api/file", params={"path": "a.md"}).headers["server-timing"])
    assert {"srv", "read", "encode"} <= set(metrics)
    assert "render" not in metrics


def test_a_git_route_names_its_git_time(tmp_path: Path) -> None:
    require_git()
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
    }
    (tmp_path / "a.txt").write_text("a\n")
    for args in (["init", "-q"], ["add", "a.txt"], ["commit", "-qm", "one"]):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, env=env)
    server._set_root_dir(tmp_path)
    client = TestClient(server.app)
    for route in ("/api/git/refs", "/api/git/log"):
        answer = client.get(route)
        assert answer.status_code == 200, route
        assert "git" in _metrics(answer.headers["server-timing"]), route


def _timed_app(handler: Callable[[Request], Awaitable[Response]]) -> Starlette:
    return Starlette(
        routes=[Route("/x", handler)],
        middleware=[
            Middleware(server._SlowRequestLogMiddleware, threshold_ms=0, verbose=True),
            Middleware(server_timing.TimedGZipMiddleware, minimum_size=16, compresslevel=6),
        ],
    )


def test_a_streamed_body_reports_later_work_in_the_log_and_not_the_header() -> None:
    """A header goes before the body: compression of later chunks reaches only the log."""
    chunk = b"metabrowser streams this body in several compressible chunks. " * 2000

    async def stream(_request: Request) -> StreamingResponse:
        async def body() -> AsyncIterator[bytes]:
            for _ in range(8):
                yield chunk

        return StreamingResponse(body(), media_type="text/plain")

    capture = _Capture()
    server.LOG.addHandler(capture)
    try:
        answer = TestClient(_timed_app(stream)).get("/x", headers={"accept-encoding": "gzip"})
    finally:
        server.LOG.removeHandler(capture)
    assert answer.headers["content-encoding"] == "gzip"
    header = _metrics(answer.headers["server-timing"])
    [line] = [message for message in capture.messages if "metabrowser request t=" in message]
    logged = re.search(r"start_ms=(\d+) phases=encode:([0-9.]+)", line)
    assert logged is not None, line
    # Eight chunks were compressed; the header saw the first.
    assert float(logged.group(2)) > header["encode"]


def test_phases_nest_without_counting_twice_and_count_in_threads() -> None:
    record, token = server_timing.begin()
    try:
        with server_timing.phase("read"), server_timing.phase("git"):
            pass

        def in_thread() -> None:
            with server_timing.phase("render"):
                pass

        asyncio.run(asyncio.to_thread(in_thread))
    finally:
        server_timing.end(record, token)
    assert [name for name, _ms in record.totals()] == ["read", "render"]
    # A task that outlives its request keeps the record, and adds nothing to it.
    record.add("git", 1.0)
    assert [name for name, _ms in record.totals()] == ["read", "render"]


def test_no_request_no_record() -> None:
    with server_timing.phase("read"):
        pass  # outside a request this records nothing and raises nothing


def test_a_response_with_no_phases_is_srv_alone() -> None:
    async def plain(_request: Request) -> Response:
        return Response("x")

    header = TestClient(_timed_app(plain)).get("/x").headers["server-timing"]
    assert re.fullmatch(r"srv;dur=[0-9.]+", header)
