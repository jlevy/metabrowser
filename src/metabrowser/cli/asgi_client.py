"""In-process ASGI client shared by the ``metab`` CLI modes that drive routes.

The client runs one application lifecycle and issues complete HTTP requests
through the real middleware stack without binding a port. That is what lets a
CLI mode prove the wire -- parameters, envelope keys, status codes -- and not
only the library beneath a route.

``label`` names the caller in error messages so a diagnostic mode can keep its
own vocabulary while sharing this transport.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode, urlsplit

from starlette.types import ASGIApp, Message, Scope

from metabrowser.errors import CLIError

LOG = logging.getLogger(__name__)

INDEX_READY_TIMEOUT_S = 60.0
INDEX_READY_POLL_S = 0.05


@dataclass(frozen=True, slots=True)
class ApiResponse:
    """One complete response captured from the ASGI stack."""

    status_code: int
    body: bytes
    headers: Mapping[str, str] = field(default_factory=dict)

    def json(self) -> Any:
        return json.loads(self.body)

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


@dataclass(frozen=True, slots=True)
class IndexResult:
    """Terminal or failed outcome from waiting for the inventory."""

    detail: str
    completed: bool


class InProcessClient:
    """Drive one ASGI app lifecycle and requests without HTTP I/O."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        label: str = "API",
        logger: logging.Logger | None = None,
    ) -> None:
        self._app = app
        self._label = label
        self._log = logger if logger is not None else LOG
        self._lifespan_input: asyncio.Queue[Message] = asyncio.Queue()
        self._lifespan_output: asyncio.Queue[Message] = asyncio.Queue()
        self._lifespan_task: asyncio.Task[None] | None = None
        self._state: dict[str, Any] = {}

    async def __aenter__(self) -> InProcessClient:
        async def receive() -> Message:
            return await self._lifespan_input.get()

        async def send(message: Message) -> None:
            await self._lifespan_output.put(message)

        async def run_app() -> None:
            await self._app(scope, receive, send)

        scope: Scope = {
            "type": "lifespan",
            "asgi": {"version": "3.0", "spec_version": "2.0"},
            "state": self._state,
        }
        self._lifespan_task = asyncio.create_task(run_app())
        await self._lifespan_input.put({"type": "lifespan.startup"})
        message = await self._lifespan_output.get()
        if message["type"] != "lifespan.startup.complete":
            detail = message.get("message", "application startup failed")
            await self._finish_lifespan_task()
            raise CLIError(str(detail))
        return self

    async def __aexit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        await self._lifespan_input.put({"type": "lifespan.shutdown"})
        message = await self._lifespan_output.get()
        await self._finish_lifespan_task()
        if message["type"] != "lifespan.shutdown.complete" and exc is None:
            detail = message.get("message", "application shutdown failed")
            raise CLIError(str(detail))

    async def _finish_lifespan_task(self) -> None:
        if self._lifespan_task is not None:
            await self._lifespan_task

    async def get(
        self,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
    ) -> ApiResponse:
        """Issue one complete GET request through the ASGI middleware stack."""

        return await self.request("GET", path, params=params)

    async def post(
        self,
        path: str,
        *,
        body: bytes = b"",
        params: Mapping[str, str] | None = None,
        content_type: str = "application/json",
    ) -> ApiResponse:
        """Issue one complete POST request through the ASGI middleware stack."""

        return await self.request(
            "POST",
            path,
            params=params,
            body=body,
            content_type=content_type,
        )

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        body: bytes = b"",
        content_type: str = "application/json",
    ) -> ApiResponse:
        """Issue one complete request, splitting any query already in ``path``.

        ``path`` may carry its own query string, so a caller can pass a route
        exactly as the browser would request it.
        """

        split = urlsplit(path)
        route = split.path
        query = split.query
        if params:
            encoded = urlencode(dict(params))
            query = f"{query}&{encoded}" if query else encoded

        request_available = True
        status_code: int | None = None
        body_parts: list[bytes] = []
        headers: dict[str, str] = {}

        async def receive() -> Message:
            nonlocal request_available
            if request_available:
                request_available = False
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.disconnect"}

        async def send(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                for raw_name, raw_value in message.get("headers", []):
                    headers[raw_name.decode("latin-1").lower()] = raw_value.decode("latin-1")
            elif message["type"] == "http.response.body":
                body_parts.append(message.get("body", b""))

        request_headers: list[tuple[bytes, bytes]] = [(b"host", b"testserver")]
        if body:
            request_headers.append((b"content-type", content_type.encode("ascii")))
            request_headers.append((b"content-length", str(len(body)).encode("ascii")))

        scope: Scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.5"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": route,
            "raw_path": route.encode("ascii"),
            "query_string": query.encode("ascii"),
            "root_path": "",
            "headers": request_headers,
            "client": ("127.0.0.1", 1),
            "server": ("testserver", 80),
            "state": self._state,
        }
        try:
            await self._app(scope, receive, send)
        except Exception as exc:
            # Starlette sends its 500 response before re-raising the route
            # exception. Preserve that response so a caller reports a stable
            # failed step instead of exposing a diagnostic traceback.
            if status_code is None:
                raise CLIError(f"{self._label} request failed for {route}") from exc
            self._log.debug(
                "%s route raised after HTTP %d path=%s",
                self._label,
                status_code,
                route,
                exc_info=True,
            )
        if status_code is None:
            raise CLIError(f"{self._label} returned no response for {route}")
        return ApiResponse(status_code=status_code, body=b"".join(body_parts), headers=headers)


def _read_json(response: ApiResponse) -> Any:
    try:
        return response.json()
    except ValueError:
        return None


async def wait_for_index(
    client: InProcessClient,
    *,
    timeout_s: float = INDEX_READY_TIMEOUT_S,
) -> IndexResult:
    """Poll the cheap progress route until the inventory reaches a terminal state."""

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        response = await client.get("/api/index/progress")
        if response.status_code != 200:
            return IndexResult(f"HTTP {response.status_code}", False)
        payload = _read_json(response)
        if isinstance(payload, dict):
            status = payload.get("status")
            if status in ("done", "truncated"):
                return IndexResult(status, True)
            if status == "failed":
                return IndexResult("failed", False)
        else:
            return IndexResult("invalid progress response", False)
        await asyncio.sleep(INDEX_READY_POLL_S)
    return IndexResult(f"timeout after {timeout_s:g}s", False)
