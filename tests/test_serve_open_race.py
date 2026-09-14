"""The CLI's auto-open path must wait for the index route to be healthy.

Regression for the user-reported "first request 404 / refresh works" race:
``webbrowser.open(url)`` used to fire BEFORE ``uvicorn.run(...)`` bound
the socket, so the browser's first GET could land on connection-refused.
Refresh worked because by then uvicorn had bound.

Fix: ``_wait_for_http_ok_then_open`` polls the index route and only opens
the browser once it serves a non-error HTTP response.

These tests decide what the port serves at each of the helper's attempts
instead of racing a sleeping thread against the helper's timeout, which failed
under heavy machine load. ``_PollClock`` stands in for the helper's clock, so
its deadline counts poll intervals rather than wall time, and it can park the
helper between attempts while the test changes the server. What each attempt
sees is decided by the test, not by how quickly a thread is scheduled. Each
attempt still waits on a real connection with its own 0.2 s timeout, so tests
that talk to a real server keep the helper's default 10 s budget (200 attempts):
a merely slow server thread spends a few attempts, not the whole budget.
"""

from __future__ import annotations

import http.client
import math
import threading
import webbrowser
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from metabrowser.cli import http_readiness
from metabrowser.cli import serve as serve_module
from metabrowser.cli.main import _app

# Breaks a deadlock in a broken build; it is not a latency budget. A passing
# run never waits on it, and a slow machine waits far less than this.
_DEADLOCK_BREAKER_S = 30.0

runner = CliRunner()


class _PollClock:
    """Stands in for ``time`` inside ``http_readiness``.

    Time advances only when the helper sleeps between attempts, by the interval
    it asks for, so its timeout is a budget of attempts rather than of wall time.
    A descheduled test thread cannot run it out; an attempt that waits on a slow
    server connection still spends one attempt. While held, each sleep also
    parks the helper until the test grants another attempt, which lets the test
    change the server between attempts and know the helper has acted on each
    state before asserting.
    """

    def __init__(self, *, held: bool) -> None:
        self._condition = threading.Condition()
        self._now = 0.0
        self._held = held
        self._granted = 0
        self._sleeps = 0
        self._finished = False

    def monotonic(self) -> float:
        with self._condition:
            return self._now

    def sleep(self, seconds: float) -> None:
        with self._condition:
            self._now += seconds
            self._sleeps += 1
            self._condition.notify_all()
            granted = self._condition.wait_for(
                lambda: not self._held or self._granted >= self._sleeps,
                timeout=_DEADLOCK_BREAKER_S,
            )
        if not granted:
            raise AssertionError("the test never granted the readiness helper another attempt")

    @property
    def finished(self) -> bool:
        with self._condition:
            return self._finished

    def finish(self) -> None:
        """Record that the helper stopped polling: it opened, gave up, or raised."""
        with self._condition:
            self._finished = True
            self._condition.notify_all()

    def wait_until_finished(self) -> None:
        with self._condition:
            finished = self._condition.wait_for(lambda: self._finished, timeout=_DEADLOCK_BREAKER_S)
        if not finished:
            raise AssertionError("the readiness helper never stopped polling")

    def wait_until_parked(self) -> None:
        """Block until the helper is parked after its latest attempt, or has finished."""
        with self._condition:
            settled = self._condition.wait_for(
                lambda: self._finished or self._sleeps > self._granted,
                timeout=_DEADLOCK_BREAKER_S,
            )
        if not settled:
            raise AssertionError("the readiness helper never completed an attempt")

    def attempt(self) -> None:
        """Let the parked helper make one more attempt, then wait for it to settle."""
        with self._condition:
            self._granted = self._sleeps
            self._condition.notify_all()
        self.wait_until_parked()

    def release(self) -> None:
        """Stop parking the helper; its remaining attempts run freely."""
        with self._condition:
            self._held = False
            self._condition.notify_all()

    def expire(self) -> None:
        """Release the helper with its deadline already passed."""
        with self._condition:
            self._now = math.inf
            self._held = False
            self._condition.notify_all()


class _IndexServer:
    """A stand-in for uvicorn serving the index route on a port it holds throughout.

    The socket is bound before the helper starts, so no other process can take
    the port, but nothing accepts a connection until ``listen``. ``ok_sent`` is
    set before a 2xx response is written, so a browser that opens while it is
    unset opened on something other than an OK response.
    """

    def __init__(self, *, status: int, listening: bool) -> None:
        self.status = status
        self.ok_sent = threading.Event()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                status = owner.status
                if 200 <= status < 300:
                    owner.ok_sent.set()
                self.send_response(status)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"ok")

            def log_message(self, format: str, *_args: object) -> None:
                return

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler, bind_and_activate=False)
        self._serving: threading.Thread | None = None
        try:
            self._httpd.server_bind()
        except OSError:
            self._httpd.server_close()
            raise
        self.port: int = self._httpd.server_address[1]
        if listening:
            try:
                self.listen()
            except BaseException:
                self._httpd.server_close()
                raise

    def listen(self) -> None:
        self._httpd.server_activate()
        # A short poll interval only makes ``close`` return sooner.
        self._serving = threading.Thread(
            target=self._httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        )
        self._serving.start()

    def close(self) -> None:
        if self._serving is not None:
            self._httpd.shutdown()
            self._serving.join(_DEADLOCK_BREAKER_S)
        self._httpd.server_close()


class _Browser:
    """Stands in for ``webbrowser``, recording whether each open followed a 2xx."""

    Error = webbrowser.Error

    def __init__(self, clock: _PollClock, index: _IndexServer | None) -> None:
        self._clock = clock
        self._index = index
        self.opened: list[tuple[str, int, bool]] = []

    def open(self, url: str, new: int = 0) -> bool:
        after_ok = self._index is not None and self._index.ok_sent.is_set()
        self.opened.append((url, new, after_ok))
        self._clock.finish()
        return True


def _install_clock(monkeypatch: pytest.MonkeyPatch, *, held: bool) -> _PollClock:
    clock = _PollClock(held=held)
    monkeypatch.setattr(http_readiness, "time", clock)
    return clock


def _install_browser(
    monkeypatch: pytest.MonkeyPatch, clock: _PollClock, index: _IndexServer | None
) -> _Browser:
    browser = _Browser(clock, index)
    monkeypatch.setattr(serve_module, "webbrowser", browser)
    return browser


def _start_helper(
    clock: _PollClock, call: Callable[[], None]
) -> tuple[threading.Thread, list[BaseException]]:
    errors: list[BaseException] = []

    def run() -> None:
        try:
            call()
        except BaseException as exc:  # Reported by the test's assertions.
            errors.append(exc)
        finally:
            clock.finish()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread, errors


@pytest.fixture
def responses(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Statuses of the HTTP responses the helper actually received, in order."""
    statuses: list[int] = []

    class RecordingConnection(http.client.HTTPConnection):
        def getresponse(self) -> http.client.HTTPResponse:
            response = super().getresponse()
            statuses.append(response.status)
            return response

    monkeypatch.setattr(http.client, "HTTPConnection", RecordingConnection)
    return statuses


def test_readiness_closes_response_before_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed: list[str] = []

    class Response:
        status = 200

        def read(self, _limit: int) -> bytes:
            return b"ok"

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *_args: object) -> None:
            closed.append("response")

    class Connection:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def request(self, *_args: object, **_kwargs: object) -> None:
            pass

        def getresponse(self) -> Response:
            return Response()

        def close(self) -> None:
            closed.append("connection")

    monkeypatch.setattr(http.client, "HTTPConnection", Connection)
    ready: list[bool] = []
    errors: list[str] = []

    http_readiness.wait_for_http_ok_then(
        "127.0.0.1",
        8411,
        "http://localhost:8411/view/",
        on_ready=lambda: ready.append(True),
        on_error=errors.append,
    )

    assert ready == [True]
    assert errors == []
    assert closed == ["response", "connection"]


def test_the_browser_opens_only_after_the_index_route_answers_ok(
    monkeypatch: pytest.MonkeyPatch, responses: list[int]
) -> None:
    """Neither an unaccepted connection nor a listening server is readiness.

    The helper is stepped through the states uvicorn passes through: a port
    nothing accepts on, an index route that answers but not OK, and an OK
    index. The browser must stay closed through the first two, and open once,
    after an OK response was written.
    """
    clock = _install_clock(monkeypatch, held=True)
    index = _IndexServer(status=503, listening=False)
    browser = _install_browser(monkeypatch, clock, index)
    url = f"http://127.0.0.1:{index.port}/view/"
    helper, errors = _start_helper(
        clock, lambda: serve_module._wait_for_http_ok_then_open("127.0.0.1", index.port, url)
    )
    try:
        clock.wait_until_parked()
        assert browser.opened == [], "opened the browser before anything accepted a connection"
        assert not clock.finished, "stopped polling before anything accepted a connection"
        assert responses == []

        index.listen()
        while 503 not in responses and not clock.finished:
            clock.attempt()
        assert browser.opened == [], "opened the browser on a connection whose index was not OK"
        assert not clock.finished, "stopped polling while the index answered 503"

        index.status = 200
        clock.release()
        helper.join(_DEADLOCK_BREAKER_S)
        assert not helper.is_alive()
        assert errors == []
        assert browser.opened == [(url, 2, True)]
        assert responses[-1] == 200
    finally:
        clock.expire()
        helper.join(_DEADLOCK_BREAKER_S)
        index.close()


def test_the_cli_opens_the_browser_only_after_its_server_answers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, responses: list[int]
) -> None:
    """``metab`` must not open the browser before the server it starts answers.

    Uvicorn is replaced by a server on the port the CLI chose that accepts
    nothing until the CLI has handed control to uvicorn and the readiness
    thread has made an attempt, which is the order the original race broke.
    """
    clock = _install_clock(monkeypatch, held=True)
    index = _IndexServer(status=200, listening=False)
    browser = _install_browser(monkeypatch, clock, index)
    opened_before_serving: list[tuple[str, int, bool]] = []
    served: list[tuple[str, int]] = []
    readiness_threads: list[threading.Thread] = []
    quiet_server = MagicMock()
    wait_then_open = serve_module._wait_for_http_ok_then_open

    def wait_then_open_and_finish(host: str, port: int, url: str) -> None:
        readiness_threads.append(threading.current_thread())
        try:
            wait_then_open(host, port, url)
        finally:
            clock.finish()

    def run_in_place_of_uvicorn(_server: object) -> bool:
        # The address uvicorn was told to bind, which must be the one being polled.
        config = quiet_server.call_args.args[0]
        served.append((config.host, config.port))
        clock.wait_until_parked()
        opened_before_serving.extend(browser.opened)
        index.listen()
        clock.release()
        return False

    monkeypatch.setattr(serve_module, "find_available_local_port", lambda *_args: index.port)
    monkeypatch.setattr(serve_module, "_QuietForceExitServer", quiet_server)
    monkeypatch.setattr(serve_module, "_run_until_interrupted", run_in_place_of_uvicorn)
    monkeypatch.setattr(serve_module, "_wait_for_http_ok_then_open", wait_then_open_and_finish)
    try:
        result = runner.invoke(_app, [str(tmp_path)])
        assert result.exit_code == 0, f"{result.output}{result.exception!r}"
        assert opened_before_serving == [], "opened the browser before the server started"
        assert served == [("127.0.0.1", index.port)], "uvicorn must serve the polled port"
        clock.wait_until_finished()
        assert len(readiness_threads) == 1
        readiness_threads[0].join(_DEADLOCK_BREAKER_S)
        assert not readiness_threads[0].is_alive()
        assert browser.opened == [(f"http://127.0.0.1:{index.port}/view/", 2, True)]
        assert responses[-1] == 200
    finally:
        clock.expire()
        index.close()


def test_the_helper_opens_once_when_the_index_is_already_ok(
    monkeypatch: pytest.MonkeyPatch, responses: list[int]
) -> None:
    """An index that is already OK opens the browser on the first response."""
    clock = _install_clock(monkeypatch, held=False)
    index = _IndexServer(status=200, listening=True)
    browser = _install_browser(monkeypatch, clock, index)
    try:
        serve_module._wait_for_http_ok_then_open("127.0.0.1", index.port, "http://x")
    finally:
        index.close()

    assert browser.opened == [("http://x", 2, True)]
    assert responses[-1] == 200


def test_the_helper_gives_up_at_its_deadline_without_opening(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A port that never serves HTTP OK leaves the browser closed, after retrying."""
    attempts: list[str] = []

    class RefusedConnection:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def request(self, *_args: object, **_kwargs: object) -> None:
            attempts.append("refused")
            raise ConnectionRefusedError("nothing is listening")

        def close(self) -> None:
            pass

    monkeypatch.setattr(http.client, "HTTPConnection", RefusedConnection)
    clock = _install_clock(monkeypatch, held=False)
    browser = _install_browser(monkeypatch, clock, None)

    serve_module._wait_for_http_ok_then_open("127.0.0.1", 8411, "http://x", timeout_s=0.3)

    assert browser.opened == []
    assert len(attempts) > 1, "gave up on the first refused connection"
    assert clock.monotonic() >= 0.3, "gave up before its deadline"
    message = capsys.readouterr().err
    assert (
        "did not serve HTTP OK at http://x within 0.3s (no HTTP response; nothing is listening)"
        in message
    )


def test_the_helper_does_not_open_on_404(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    responses: list[int],
) -> None:
    """A 404 is a hard readiness failure; never auto-open it."""
    clock = _install_clock(monkeypatch, held=False)
    index = _IndexServer(status=404, listening=True)
    browser = _install_browser(monkeypatch, clock, index)
    try:
        serve_module._wait_for_http_ok_then_open("127.0.0.1", index.port, "http://x")
    finally:
        index.close()

    assert browser.opened == []
    assert responses[-1] == 404
    assert "Server returned HTTP 404 for http://x; not opening browser." in capsys.readouterr().err


def test_the_helper_does_not_open_on_redirect(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    responses: list[int],
) -> None:
    """A redirect is not proof that the Metabrowser shell is ready.

    It is retried rather than treated as final, and never opened.
    """
    clock = _install_clock(monkeypatch, held=True)
    index = _IndexServer(status=302, listening=True)
    browser = _install_browser(monkeypatch, clock, index)
    helper, errors = _start_helper(
        clock, lambda: serve_module._wait_for_http_ok_then_open("127.0.0.1", index.port, "http://x")
    )
    try:
        clock.wait_until_parked()
        while responses.count(302) < 2 and not clock.finished:
            clock.attempt()
        assert browser.opened == []
        assert not clock.finished, "treated a redirect as final"

        clock.expire()
        helper.join(_DEADLOCK_BREAKER_S)
        assert not helper.is_alive()
        assert errors == []
        assert browser.opened == []
        assert "last HTTP status 302" in capsys.readouterr().err
    finally:
        clock.expire()
        helper.join(_DEADLOCK_BREAKER_S)
        index.close()
