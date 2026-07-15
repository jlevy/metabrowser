"""The CLI's auto-open path must wait for the index route to be healthy.

Regression for the user-reported "first request 404 / refresh works" race:
``webbrowser.open(url)`` used to fire BEFORE ``uvicorn.run(...)`` bound
the socket, so the browser's first GET could land on connection-refused.
Refresh worked because by then uvicorn had bound.

Fix: ``_wait_for_http_ok_then_open`` polls the index route and only opens
the browser once it serves a non-error HTTP response.
"""

from __future__ import annotations

import socket
import threading
import time
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from metabrowser.cli import serve as serve_module


class _ReadyHandler(BaseHTTPRequestHandler):
    status = 200

    def do_GET(self) -> None:
        self.send_response(self.status)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format: str, *_args: object) -> None:
        return


def _start_http_server(
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    status: int = 200,
) -> tuple[ThreadingHTTPServer, int]:
    class Handler(_ReadyHandler):
        pass

    Handler.status = status
    server = ThreadingHTTPServer((host, port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, server.server_address[1]


def test_wait_for_http_ok_then_open_invokes_webbrowser_when_index_ready() -> None:
    """Once the index route returns OK, the helper opens exactly once."""
    server, port = _start_http_server()
    try:
        with patch.object(serve_module, "webbrowser") as wb:
            wb.Error = Exception
            serve_module._wait_for_http_ok_then_open(
                "127.0.0.1",
                port,
                "http://x",
                timeout_s=2.0,
            )
            wb.open.assert_called_once_with("http://x", new=2)
    finally:
        server.shutdown()
        server.server_close()


def test_wait_for_http_ok_then_open_blocks_until_http_ok() -> None:
    """Helper blocks while HTTP is not ready, then opens once it is OK.

    The realistic race the fix addresses: webbrowser.open used to fire
    first; this test confirms the helper now correctly waits.
    """
    delay_s = 0.4
    open_times: list[float] = []
    bind_times: list[float] = []

    server_holder: dict[str, ThreadingHTTPServer] = {}

    def _delayed_bind(port: int) -> None:
        time.sleep(delay_s)
        server, _ = _start_http_server(port=port)
        server_holder["server"] = server
        bind_times.append(time.monotonic())

    # Pick a random ephemeral port up front (small race window — fine for a test).
    with closing(socket.socket()) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    binder = threading.Thread(target=_delayed_bind, args=(port,), daemon=True)
    binder.start()

    try:
        with patch.object(serve_module, "webbrowser") as wb:
            wb.Error = Exception

            def _record_open(*args, **kwargs):
                open_times.append(time.monotonic())

            wb.open.side_effect = _record_open
            serve_module._wait_for_http_ok_then_open(
                "127.0.0.1",
                port,
                "http://x",
                timeout_s=5.0,
            )
            assert open_times, "webbrowser.open should have been called"
            assert bind_times, "test bind helper should have run"
            # Open happened AFTER HTTP became healthy — that's the whole point.
            assert open_times[0] >= bind_times[0]
    finally:
        binder.join(timeout=2.0)
        server = server_holder.get("server")
        if server is not None:
            server.shutdown()
            server.server_close()


def test_wait_for_http_ok_then_open_times_out_without_opening() -> None:
    """If the port never serves HTTP OK, the helper must not open a broken tab."""
    # Pick an ephemeral port; nothing binds it.
    with closing(socket.socket()) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    with patch.object(serve_module, "webbrowser") as wb:
        wb.Error = Exception
        start = time.monotonic()
        serve_module._wait_for_http_ok_then_open(
            "127.0.0.1",
            port,
            "http://x",
            timeout_s=0.3,
        )
        elapsed = time.monotonic() - start
        assert not wb.open.called, "browser must not open after timeout"
        # Don't fully wait timeout_s + slop; just assert we tried for > 0
        assert elapsed >= 0.3


def test_wait_for_http_ok_then_open_does_not_open_on_404() -> None:
    """A 404 is a hard readiness failure; never auto-open it."""
    server, port = _start_http_server(status=404)
    try:
        with patch.object(serve_module, "webbrowser") as wb:
            wb.Error = Exception
            serve_module._wait_for_http_ok_then_open(
                "127.0.0.1",
                port,
                "http://x",
                timeout_s=2.0,
            )
            assert not wb.open.called
    finally:
        server.shutdown()
        server.server_close()


def test_wait_for_http_ok_then_open_does_not_open_on_redirect() -> None:
    """A redirect is not proof that the MetaBrowser shell is ready."""
    server, port = _start_http_server(status=302)
    try:
        with patch.object(serve_module, "webbrowser") as wb:
            wb.Error = Exception
            serve_module._wait_for_http_ok_then_open(
                "127.0.0.1",
                port,
                "http://x",
                timeout_s=0.2,
            )
            assert not wb.open.called
    finally:
        server.shutdown()
        server.server_close()
