"""The pull routes: ``GET /api/plugin/github/pull`` and ``POST /api/plugin/github/pull-refresh``.

:mod:`metabrowser.builtin_plugins.github.pull_route` builds the answer; this module is
the pair of data hooks the manifest names. The loader imports it at startup, so like the
``/api/cache/`` route table it imports nothing from the cache or the application home
itself: each handler imports the envelope builder, which reaches both, only when it is
requested. Browsing a local directory therefore never loads the cache.

The refresh route starts or joins the pull request's refresh job in the refresh
coordinator and returns ``202`` at once, never waiting on the network. It starts work,
so it is a ``POST`` with a JSON object body: the application's same-origin guard and its
JSON content-type rule keep content inside an untrusted page from reaching it with a
link, an image, or a form, and a page for a pin the server no longer serves is refused
``pin_changed`` by the pin guard. Plugin data routes are one path segment, so the
refresh is ``pull-refresh`` beside ``pull``.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Final

from starlette.responses import JSONResponse, Response

from metabrowser.mirror_refresh import mirror_session
from metabrowser.source import get_source_session

if TYPE_CHECKING:
    from starlette.requests import Request

# The answer changes as the record ages and as a refresh replaces it.
_NO_STORE: Final = {"cache-control": "no-store"}
# A refresh request carries no parameters; a JSON object of any size worth reading fits.
MAX_REFRESH_REQUEST_BYTES: Final = 1024


async def pull_handler(request: Request) -> Response:
    """``GET /api/plugin/github/pull`` — see :mod:`.pull_route`.

    The answer carries an entity tag, and a request whose ``If-None-Match`` names it is
    answered ``304`` without the record, so a page can poll it as cheaply as the status
    route. The tag covers everything but the record, which changes only with
    ``fetched_at``.
    """

    from metabrowser.builtin_plugins.github.pull_route import (
        envelope_etag,
        served_pull_envelope,
        served_pull_view,
    )

    view = served_pull_view(mirror_session(request.app), get_source_session().subject)
    envelope = await asyncio.to_thread(served_pull_envelope, view)
    etag = envelope_etag(envelope)
    headers = {**_NO_STORE, "etag": etag}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return JSONResponse(dict(envelope), headers=headers)


async def pull_markdown_handler(request: Request) -> JSONResponse:
    """``GET /api/plugin/github/pull-markdown?part=<part>`` — see :mod:`.pull_markdown`."""

    from metabrowser.builtin_plugins.github.pull_markdown import render_part
    from metabrowser.builtin_plugins.github.pull_route import served_pull_view

    view = served_pull_view(mirror_session(request.app), get_source_session().subject)
    status_code, body = await asyncio.to_thread(
        render_part, view, request.query_params.get("part", "")
    )
    return JSONResponse(body, status_code=status_code, headers=_NO_STORE)


async def _body_problem(request: Request) -> tuple[str, int] | None:
    """Why the body is not a JSON object of at most :data:`MAX_REFRESH_REQUEST_BYTES`.

    ``None`` when it is one; otherwise the message and status ``POST /api/source/refresh``
    answers the same body with.
    """

    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_REFRESH_REQUEST_BYTES:
        return "the request body is too large", 413
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_REFRESH_REQUEST_BYTES:
            return "the request body is too large", 413
        chunks.append(chunk)
    try:
        decoded = json.loads(b"".join(chunks) or b"{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "the request body is not JSON", 400
    if not isinstance(decoded, dict):
        return "the request body must be a JSON object", 400
    return None


async def pull_refresh_handler(request: Request) -> JSONResponse:
    """``POST /api/plugin/github/pull-refresh`` — start or join the pull request's refresh.

    ``refresh`` says whether this request started the job or joined one that was
    running, and ``pull`` is the envelope as of that moment, with ``refreshing`` true:
    ``pending`` while no record is cached yet.
    """

    from metabrowser.builtin_plugins.github.pull_route import (
        served_pull_envelope,
        served_pull_of,
        served_pull_view,
    )

    problem = await _body_problem(request)
    if problem is not None:
        message, status_code = problem
        return JSONResponse({"error": message, "code": "invalid_request"}, status_code=status_code)
    mirror = mirror_session(request.app)
    if mirror is None or served_pull_of(mirror) is None:
        return JSONResponse(
            {"error": "this server serves no pull request", "code": "no_pull_request"},
            status_code=409,
        )
    started = mirror.request_companion_refresh()
    # Read after the start, on the loop: the job is running, whatever it does next.
    view = served_pull_view(mirror, get_source_session().subject)
    envelope = await asyncio.to_thread(served_pull_envelope, view)
    return JSONResponse(
        {"refresh": started, "pull": dict(envelope)}, status_code=202, headers=_NO_STORE
    )


__all__ = [
    "MAX_REFRESH_REQUEST_BYTES",
    "pull_handler",
    "pull_markdown_handler",
    "pull_refresh_handler",
]
