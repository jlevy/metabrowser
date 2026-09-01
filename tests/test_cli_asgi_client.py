"""Focused tests for the shared in-process ASGI client."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

import pytest
from starlette.types import ASGIApp, Receive, Scope, Send

from metabrowser.cli.asgi_client import ApiResponse, InProcessClient, wait_for_index


class _ProgressClient:
    def __init__(self, status: str) -> None:
        self._status = status

    async def get(
        self,
        _path: str,
        *,
        params: dict[str, str] | None = None,
    ) -> ApiResponse:
        del params
        return ApiResponse(200, f'{{"status":"{self._status}"}}'.encode())


def test_wait_for_index_reports_terminal_status() -> None:
    result = asyncio.run(
        wait_for_index(cast(InProcessClient, _ProgressClient("truncated")), timeout_s=1.0)
    )

    assert result.detail == "truncated"
    assert result.completed is True


def test_wait_for_index_reports_timeout_duration() -> None:
    result = asyncio.run(
        wait_for_index(cast(InProcessClient, _ProgressClient("scanning")), timeout_s=0.0)
    )

    assert result.detail == "timeout after 0s"
    assert result.completed is False


def test_in_process_client_logs_route_exception_after_500(caplog: Any) -> None:
    async def app(_scope: Scope, _receive: Receive, send: Send) -> None:
        await send({"type": "http.response.start", "status": 500, "headers": []})
        await send({"type": "http.response.body", "body": b"Internal Server Error"})
        raise RuntimeError("route exploded")

    with caplog.at_level(logging.DEBUG, logger="metabrowser.cli.asgi_client"):
        response = asyncio.run(InProcessClient(cast(ASGIApp, app)).get("/api/tree"))

    assert response.status_code == 500
    assert "API route raised after HTTP 500 path=/api/tree" in caplog.text
    assert "route exploded" in caplog.text


def test_caller_label_and_logger_are_used_for_diagnostics(caplog: Any) -> None:
    """A diagnostic mode keeps its own vocabulary while sharing this transport."""

    async def app(_scope: Scope, _receive: Receive, send: Send) -> None:
        await send({"type": "http.response.start", "status": 500, "headers": []})
        await send({"type": "http.response.body", "body": b""})
        raise RuntimeError("route exploded")

    logger = logging.getLogger("metabrowser.cli.check_api")
    with caplog.at_level(logging.DEBUG, logger="metabrowser.cli.check_api"):
        client = InProcessClient(cast(ASGIApp, app), label="navigation API", logger=logger)
        asyncio.run(client.get("/api/tree"))

    assert "navigation API route raised after HTTP 500 path=/api/tree" in caplog.text


def test_a_streaming_route_fails_instead_of_hanging() -> None:
    """A server-sent-event response never completes; an unbounded read would hang."""

    async def app(_scope: Scope, _receive: Receive, send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/event-stream")],
            }
        )
        while True:  # never terminates, like a real SSE route
            await send({"type": "http.response.body", "body": b": heartbeat\n", "more_body": True})
            await asyncio.sleep(0.01)

    from metabrowser.errors import CLIError

    client = InProcessClient(cast(ASGIApp, app))
    with pytest.raises(CLIError, match="did not complete within"):
        asyncio.run(client.request("GET", "/api/events", timeout_s=0.2))


def _echo_app_factory(seen: dict[str, object]):
    async def app(scope: Scope, _receive: Receive, send: Send) -> None:
        seen["path"] = scope["path"]
        seen["raw_path"] = scope["raw_path"]
        seen["query_string"] = scope["query_string"]
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    return app


def test_a_non_ascii_query_is_percent_encoded_not_crashed() -> None:
    """A route carrying a non-ASCII filename must reach the app, not raise."""

    seen: dict[str, object] = {}
    client = InProcessClient(cast(ASGIApp, _echo_app_factory(seen)))

    response = asyncio.run(client.get("/api/file?path=日本.md"))

    assert response.status_code == 200
    assert seen["query_string"] == b"path=%E6%97%A5%E6%9C%AC.md"


def test_a_non_ascii_route_segment_is_percent_encoded() -> None:
    seen: dict[str, object] = {}
    client = InProcessClient(cast(ASGIApp, _echo_app_factory(seen)))

    asyncio.run(client.get("/api/plugin/x/日本"))

    assert seen["raw_path"] == b"/api/plugin/x/%E6%97%A5%E6%9C%AC"
    # ASGI says `path` is the decoded form; Starlette routes on it.
    assert seen["path"] == "/api/plugin/x/日本"


def test_an_already_encoded_query_is_not_double_encoded() -> None:
    """A caller who percent-encoded already must not get %25 back."""

    seen: dict[str, object] = {}
    client = InProcessClient(cast(ASGIApp, _echo_app_factory(seen)))

    asyncio.run(client.get("/api/file?path=%E6%97%A5%E6%9C%AC.md"))

    assert seen["query_string"] == b"path=%E6%97%A5%E6%9C%AC.md"


def test_a_startup_failure_reports_its_reason_not_a_traceback() -> None:
    """The app's own exception must not escape in place of the failure message."""

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] == "lifespan"
        await receive()
        await send({"type": "lifespan.startup.failed", "message": "index unavailable"})
        raise RuntimeError("startup exploded")

    from metabrowser.errors import CLIError

    async def run() -> None:
        async with InProcessClient(cast(ASGIApp, app)):
            pass

    with pytest.raises(CLIError, match="index unavailable"):
        asyncio.run(run())


def test_a_route_raising_after_a_2xx_start_is_not_reported_as_success() -> None:
    """A truncated body with a 200 status would otherwise read as a clean answer."""

    async def app(_scope: Scope, _receive: Receive, send: Send) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b'{"partial":', "more_body": True})
        raise RuntimeError("route exploded mid-stream")

    client = InProcessClient(cast(ASGIApp, app))
    response = asyncio.run(client.get("/api/tree"))

    assert response.status_code == 200
    assert response.incomplete is True
