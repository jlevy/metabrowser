"""Focused tests for the shared in-process ASGI client."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

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
