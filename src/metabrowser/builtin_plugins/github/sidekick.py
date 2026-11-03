"""The pull routes: one pull request's, ``pull`` and ``pull-refresh``, and the lists', ``pulls``
and ``pulls-refresh``, all under ``/api/plugin/github/``.

:mod:`metabrowser.builtin_plugins.github.pull_route` and
:mod:`metabrowser.builtin_plugins.github.pull_list_route` build the answers; this module is
the data hooks the manifest names. The loader imports it at startup, so like the
``/api/cache/`` route table it imports nothing from the cache or the application home
itself: each handler imports the envelope builder, which reaches both, only when it is
requested. Browsing a local directory therefore never loads the cache.

A refresh route starts or joins a refresh job in the refresh coordinator and returns
``202`` at once, never waiting on the network. It starts work, so it is a ``POST`` with a
JSON object body: the application's same-origin guard and its JSON content-type rule keep
content inside an untrusted page from reaching it with a link, an image, or a form, and a
page for a pin the server no longer serves is refused
``pin_changed`` by the pin guard. Plugin data routes are one path segment, so the
refresh is ``pull-refresh`` beside ``pull``.
"""

from __future__ import annotations

import asyncio
import json
import re
from functools import partial
from typing import TYPE_CHECKING, Any, Final

from starlette.responses import JSONResponse, Response

from metabrowser.http_caching import matches_if_none_match
from metabrowser.mirror_refresh import mirror_session
from metabrowser.source import get_source_session

if TYPE_CHECKING:
    from starlette.requests import Request

# The answer changes as the record ages and as a refresh replaces it.
_NO_STORE: Final = {"cache-control": "no-store"}
# A refresh request carries no parameters; a JSON object of any size worth reading fits.
MAX_REFRESH_REQUEST_BYTES: Final = 1024
PULL_ROUTE: Final = "/api/plugin/github/pull"
# Eight ready files covered the visible viewport in three paired browser runs on
# public Ruff PRs of 1,031 and 1,627 files (2026-11-03, Chrome 152, 1400x900). One
# left visible reserved space at 1,031. Hydrating fifty cost 112–181 ms in the
# route; eight cost 21 ms. Later files use the existing on-approach loader.
INITIAL_PULL_FILES: Final = 8


async def pull_handler(request: Request) -> Response:
    """``GET /api/plugin/github/pull`` — see :mod:`.pull_route`.

    The answer carries an entity tag, and a request whose ``If-None-Match`` names it is
    answered ``304`` without the record, so a page can poll it as cheaply as the status
    route. The tag covers everything but the record, which changes only with
    ``fetched_at``.
    """

    from metabrowser.builtin_plugins.github.pull_route import (
        envelope_etag,
        record_stamp,
        served_pull_envelope,
        served_pull_view,
    )

    view = served_pull_view(mirror_session(request.app), get_source_session().subject)
    stamp = await asyncio.to_thread(record_stamp, view)
    envelope = await asyncio.to_thread(served_pull_envelope, view)
    if view is not None:
        view.served.saw_record(envelope["fetched_at"])
    etag = envelope_etag(envelope, stamp)
    headers = {**_NO_STORE, "etag": etag}
    if matches_if_none_match(request, etag):
        return Response(status_code=304, headers=headers)
    return JSONResponse(dict(envelope), headers=headers)


async def pull_comparison_handler(request: Request) -> Response:
    """The selected PR's comparison, from its trusted store and no network."""
    from metabrowser.builtin_plugins.diff.sidekick import comparison_at
    from metabrowser.builtin_plugins.github.pull_manifest import load_pull_manifest
    from metabrowser.builtin_plugins.github.pull_route import served_pull_view
    from metabrowser.git.process import GitLocation, RepositoryStoreTarget

    view = served_pull_view(mirror_session(request.app), get_source_session().subject)
    if view is None or view.pin is None:
        return JSONResponse(
            {"error": "this server serves no pull request", "code": "no_pull_request"},
            status_code=409,
            headers=_NO_STORE,
        )
    if request.query_params.get("number", "") != str(view.served.number):
        return JSONResponse(
            {"error": "this pull request is not served here", "code": "no_pull_request"},
            status_code=404,
            headers=_NO_STORE,
        )
    query = request.query_params
    if (
        query.get("base_policy") != "merge_base"
        or query.get("revision")
        or any(
            re.fullmatch(r"[0-9a-f]{40}(?:[0-9a-f]{24})?", query.get(name, "")) is None
            for name in ("left", "right")
        )
    ):
        return JSONResponse(
            {"error": "name two full commit IDs and merge_base", "code": "invalid_comparison"},
            status_code=400,
            headers=_NO_STORE,
        )
    published = view.served.published
    location = GitLocation.revision(
        RepositoryStoreTarget(published.git_dir, published.object_format), view.pin
    )
    return await comparison_at(
        request,
        location,
        max_initial_files=INITIAL_PULL_FILES,
        manifest_loader=partial(load_pull_manifest, published),
    )


async def pull_markdown_handler(request: Request) -> JSONResponse:
    """``GET /api/plugin/github/pull-markdown?part=<part>`` — see :mod:`.pull_markdown`."""

    from metabrowser.builtin_plugins.github.pull_markdown import render_part
    from metabrowser.builtin_plugins.github.pull_route import served_pull_view

    view = served_pull_view(mirror_session(request.app), get_source_session().subject)
    status_code, body = await asyncio.to_thread(
        render_part, view, request.query_params.get("part", "")
    )
    return JSONResponse(body, status_code=status_code, headers=_NO_STORE)


async def _json_body(request: Request) -> dict[str, Any] | tuple[str, int]:
    """The body, a JSON object of at most :data:`MAX_REFRESH_REQUEST_BYTES`.

    Otherwise the message and status ``POST /api/source/refresh`` answers the same body
    with.
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
    return decoded


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

    body = await _json_body(request)
    if isinstance(body, tuple):
        return _invalid_request(*body)
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
    if view is not None:
        view.served.saw_record(envelope["fetched_at"])
    # ``status_route`` is where a one-shot ``--api`` reads how the refresh ended.
    answer = {"refresh": started, "pull": dict(envelope), "status_route": PULL_ROUTE}
    return JSONResponse(answer, status_code=202, headers=_NO_STORE)


def _invalid_request(message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse({"error": message, "code": "invalid_request"}, status_code=status_code)


async def pulls_handler(request: Request) -> Response:
    """``GET /api/plugin/github/pulls?state=&limit=&after=`` — see :mod:`.pull_list_route`.

    From the cache alone. Like the pull route, the answer carries an entity tag, and a
    request whose ``If-None-Match`` names it is answered ``304`` without the rows, so a
    page can poll it cheaply.
    """

    from metabrowser.builtin_plugins.github.pull_list_route import (
        ListRequestError,
        envelope_etag,
        list_file_stamp,
        list_view,
        list_window,
        pull_list_envelope,
    )

    try:
        window = list_window(request.query_params)
    except ListRequestError as exc:
        return _invalid_request(str(exc))
    view = list_view(request.app, window.name)
    stamp = await asyncio.to_thread(list_file_stamp, view, window.name)
    envelope = await asyncio.to_thread(pull_list_envelope, view, window)
    etag = envelope_etag(envelope, stamp, window)
    headers = {**_NO_STORE, "etag": etag}
    if matches_if_none_match(request, etag):
        return Response(status_code=304, headers=headers)
    return JSONResponse(dict(envelope), headers=headers)


async def pulls_refresh_handler(request: Request) -> JSONResponse:
    """``POST /api/plugin/github/pulls-refresh`` — start or join one list's refresh.

    The body may name ``state`` (``all`` by default), ``more``, which extends the list by
    one GitHub page, after the running refresh if it joins one, and ``retry``, a reader's
    own click. ``refresh`` says whether this request ``started`` the job or ``joined`` one
    that was running, answered ``202``, or that it is ``not_due``, answered ``200``: before
    GitHub's limit lifts, whoever asked, or tried within the freshness window, for an
    automatic request or a ``more`` with no page to read. ``pulls`` is the envelope as of
    that moment without its rows.
    """

    from metabrowser.builtin_plugins.github.pull_list_route import (
        ListRequestError,
        ListWindow,
        list_view,
        pull_list_envelope,
        refresh_request,
        refresh_wanted,
        start_refresh,
        status_route,
    )

    body = await _json_body(request)
    if isinstance(body, tuple):
        return _invalid_request(*body)
    try:
        ask = refresh_request(body)
    except ListRequestError as exc:
        return _invalid_request(str(exc))
    view = list_view(request.app, ask.name)
    if view.repository is None or view.coordinator is None:
        return JSONResponse(
            {"error": "this server serves no GitHub repository", "code": "not_github"},
            status_code=409,
        )
    wanted = await asyncio.to_thread(refresh_wanted, view, ask)
    started = start_refresh(view, ask, wanted=wanted)
    # Read after the start, on the loop: the job is running, whatever it does next.
    after = list_view(request.app, ask.name)
    envelope = await asyncio.to_thread(pull_list_envelope, after, ListWindow(ask.name, limit=0))
    answer = {"refresh": started, "pulls": dict(envelope), "status_route": status_route(ask.name)}
    return JSONResponse(answer, status_code=200 if started == "not_due" else 202, headers=_NO_STORE)


__all__ = [
    "MAX_REFRESH_REQUEST_BYTES",
    "PULL_ROUTE",
    "pull_handler",
    "pull_markdown_handler",
    "pull_comparison_handler",
    "pull_refresh_handler",
    "pulls_handler",
    "pulls_refresh_handler",
]
