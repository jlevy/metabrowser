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
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote, unquote, urlencode, urlsplit

from starlette.types import ASGIApp, Message, Scope

from metabrowser.errors import CLIError

LOG = logging.getLogger(__name__)

INDEX_READY_TIMEOUT_S = 60.0
INDEX_READY_POLL_S = 0.05
# A server-sent-event route never completes its response, so an unbounded read
# would hang rather than fail. This bounds every request instead of guessing
# which routes stream.
REQUEST_TIMEOUT_S = 30.0
LIFESPAN_TIMEOUT_S = 30.0

# A caller writes a route the way the browser would request it, which may carry
# a non-ASCII filename and may already be percent-encoded. Escaping with `%`
# itself marked safe encodes the former without double-encoding the latter.
_PATH_SAFE = "/%:@!$&'()*+,;=~-._"
_QUERY_SAFE = "?" + _PATH_SAFE


@dataclass(frozen=True, slots=True)
class ApiResponse:
    """One complete response captured from the ASGI stack."""

    status_code: int
    body: bytes
    headers: Mapping[str, str] = field(default_factory=dict)
    # The route raised after sending its status, so the body below is whatever
    # arrived before it stopped. The status alone would read as success.
    incomplete: bool = False

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
        try:
            message = await asyncio.wait_for(
                self._lifespan_output.get(), timeout=LIFESPAN_TIMEOUT_S
            )
        except TimeoutError as exc:
            # An app that neither completes nor fails startup would otherwise
            # leave the caller waiting with no output at all.
            await self._cancel_lifespan_task()
            raise CLIError(
                f"{self._label} application did not start within {LIFESPAN_TIMEOUT_S:g}s"
            ) from exc
        if message["type"] != "lifespan.startup.complete":
            detail = message.get("message", "application startup failed")
            # Draining the task re-raises whatever the app raised. That
            # traceback is the symptom; the failure message is the cause, so
            # report the cause and attach the exception to it.
            try:
                await self._finish_lifespan_task()
            except Exception as exc:
                raise CLIError(str(detail)) from exc
            raise CLIError(str(detail))
        return self

    async def _cancel_lifespan_task(self) -> None:
        if self._lifespan_task is not None:
            self._lifespan_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await self._lifespan_task

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
        timeout_s: float = REQUEST_TIMEOUT_S,
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
        incomplete = False

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

        raw_path = quote(route, safe=_PATH_SAFE).encode("ascii")
        scope: Scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.5"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            # ASGI says `path` is the decoded target and `raw_path` the bytes as
            # sent; Starlette routes on `path`.
            "path": unquote(route),
            "raw_path": raw_path,
            "query_string": quote(query, safe=_QUERY_SAFE).encode("ascii"),
            "root_path": "",
            "headers": request_headers,
            "client": ("127.0.0.1", 1),
            "server": ("testserver", 80),
            "state": self._state,
        }
        try:
            await asyncio.wait_for(self._app(scope, receive, send), timeout=timeout_s)
        except TimeoutError as exc:
            raise CLIError(
                f"{self._label} request for {route} did not complete within {timeout_s:g}s; "
                "a streaming route has no terminating response"
            ) from exc
        except Exception as exc:
            # Starlette sends its 500 response before re-raising the route
            # exception. Preserve that response so a caller reports a stable
            # failed step instead of exposing a diagnostic traceback.
            if status_code is None:
                raise CLIError(f"{self._label} request failed for {route}") from exc
            incomplete = True
            self._log.debug(
                "%s route raised after HTTP %d path=%s",
                self._label,
                status_code,
                route,
                exc_info=True,
            )
        if status_code is None:
            raise CLIError(f"{self._label} returned no response for {route}")
        return ApiResponse(
            status_code=status_code,
            body=b"".join(body_parts),
            headers=headers,
            incomplete=incomplete,
        )


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
