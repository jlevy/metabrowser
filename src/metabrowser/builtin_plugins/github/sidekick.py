"""The pull routes: one pull request's, ``pull`` and ``pull-refresh``, the lists', ``pulls``
and ``pulls-refresh``, and a pull request's changed files, ``pull-files`` and
``pull-files-refresh``, all under ``/api/plugin/github/``.

:mod:`metabrowser.builtin_plugins.github.pull_route`,
:mod:`metabrowser.builtin_plugins.github.pull_list_route`, and
:mod:`metabrowser.builtin_plugins.github.pull_files_route` build the answers; this module is
the data hooks the manifest names. The loader imports it at startup, so like the
``/api/cache/`` route table it imports nothing from the cache or the application home
itself: each handler imports the envelope builder, which reaches both, only when it is
requested. Browsing a local directory therefore never loads the cache.

A refresh route starts or joins a refresh job in the refresh coordinator and returns
``202`` at once, never waiting on the network, or says why it started none. It starts work, so it is a ``POST`` with a
JSON object body: the application's same-origin guard and its JSON content-type rule keep
content inside an untrusted page from reaching it with a link, an image, or a form, and a
page for a pin the server no longer serves is refused
``pin_changed`` by the pin guard. Plugin data routes are one path segment, so the
refresh is ``pull-refresh`` beside ``pull``.
"""

from __future__ import annotations

import asyncio
import json
from functools import partial
from typing import TYPE_CHECKING, Any, Final

from starlette.responses import JSONResponse, Response

from metabrowser.http_caching import matches_if_none_match
from metabrowser.source import get_source_session

if TYPE_CHECKING:
    from starlette.requests import Request

# The answer changes as the record ages and as a refresh replaces it.
_NO_STORE: Final = {"cache-control": "no-store"}
# A refresh request carries a few short parameters; a JSON object of any size worth reading fits.
MAX_REFRESH_REQUEST_BYTES: Final = 1024
# A job started or joined is on its way. A request that started none has its answer now,
# which past the bound on jobs is a refusal.
_REFRESH_STATUS: Final = {
    "started": 202,
    "joined": 202,
    "not_due": 200,
    "not_cached": 200,
    "too_many": 429,
}
_TOO_MANY: Final = {
    "error": "too many pull requests are being fetched; try again when one has finished",
    "code": "too_many",
}


async def _resolve(request: Request) -> None:
    """On a folder, find the served checkout's repository off the loop, once per root.

    A route reads it from memory after this, as it reads a mirror's. Nothing before a
    route is asked for resolves it, so a folder whose Pulls tab is never opened reads none
    of its checkout for this.
    """

    from metabrowser.builtin_plugins.github.checkout import ensure_resolved

    await ensure_resolved(request.app)


def _without_store(envelope: Any) -> bool:
    """Whether the record an envelope carries was written with no store."""

    record = envelope.get("record")
    unavailable = record.get("unavailable") if isinstance(record, dict) else None
    return isinstance(unavailable, dict) and unavailable.get("comparison") == "no_store"


async def pull_handler(request: Request) -> Response:
    """``GET /api/plugin/github/pull?number=<n>`` — see :mod:`.pull_route`.

    The answer carries an entity tag, and a request whose ``If-None-Match`` names it is
    answered ``304`` without the record, so a page can poll it as cheaply as the status
    route. The tag covers everything but the record, which changes only with
    ``fetched_at``.
    """

    from metabrowser.builtin_plugins.github.pull_route import (
        PullRequestError,
        envelope_etag,
        pull_envelope,
        pull_host,
        pull_view,
        record_stamp,
        requested_number,
    )

    try:
        number = requested_number(request.query_params)
    except PullRequestError as exc:
        return _invalid_request(str(exc))
    await _resolve(request)
    view = pull_view(pull_host(request.app), get_source_session().subject, number)
    stamp = await asyncio.to_thread(record_stamp, view)
    envelope = await asyncio.to_thread(pull_envelope, view)
    if view.kept is not None:
        view.kept.saw_record(envelope["fetched_at"], without_store=_without_store(envelope))
    etag = envelope_etag(envelope, stamp)
    headers = {**_NO_STORE, "etag": etag}
    if matches_if_none_match(request, etag):
        return Response(status_code=304, headers=headers)
    return JSONResponse(dict(envelope), headers=headers)


async def pull_markdown_handler(request: Request) -> JSONResponse:
    """``GET /api/plugin/github/pull-markdown?number=<n>&part=<part>`` — see :mod:`.pull_markdown`."""

    from metabrowser.builtin_plugins.github.pull_markdown import render_part
    from metabrowser.builtin_plugins.github.pull_route import (
        PullRequestError,
        pull_host,
        pull_view,
        requested_number,
    )

    try:
        number = requested_number(request.query_params)
    except PullRequestError as exc:
        return _invalid_request(str(exc))
    await _resolve(request)
    view = pull_view(pull_host(request.app), get_source_session().subject, number)
    status_code, body = await asyncio.to_thread(
        render_part, view, request.query_params.get("part", "")
    )
    return JSONResponse(body, status_code=status_code, headers=_NO_STORE)


async def pull_comparison_handler(request: Request) -> Response:
    """Read a checkout's pinned PR comparison from its store; never acquire on GET."""

    from metabrowser.builtin_plugins.diff.sidekick import comparison_at
    from metabrowser.builtin_plugins.github.pull_manifest import load_pull_manifest
    from metabrowser.builtin_plugins.github.pull_route import (
        PullRequestError,
        cached_pull_record,
        pull_host,
        requested_number,
    )
    from metabrowser.cache.acquire import PublishedSource
    from metabrowser.git.process import GitLocation, repository_store_target
    from metabrowser.git.wire import is_full_revision

    try:
        number = requested_number(request.query_params)
    except PullRequestError as exc:
        return _invalid_request(str(exc))
    left = request.query_params.get("left", "")
    right = request.query_params.get("right", "")
    if (
        request.query_params.get("base_policy") != "merge_base"
        or not is_full_revision(left)
        or not is_full_revision(right)
        or "revision" in request.query_params
    ):
        return _invalid_request("a pull comparison requires two full commit IDs")
    await _resolve(request)
    host = pull_host(request.app)
    if host is None or host.pulls.git_dir is None:
        return JSONResponse(
            {"error": "this comparison has no available repository store", "code": "no_store"},
            status_code=409,
            headers=_NO_STORE,
        )
    published = host.pulls.published
    if not isinstance(published, PublishedSource):
        raise AssertionError("a store-backed pull host has no published source")
    from metabrowser.builtin_plugins.github.pull_record import PullRecord

    record, _dumped = await asyncio.to_thread(
        cached_pull_record, published.home, published.slug, number
    )
    if not isinstance(record, PullRecord):
        return JSONResponse(
            {"error": "this pull request has not been fetched", "code": "not_cached"},
            status_code=404,
            headers=_NO_STORE,
        )
    target = repository_store_target(git_dir=published.git_dir)
    return await comparison_at(
        request,
        GitLocation.revision(target, right),
        manifest_loader=partial(load_pull_manifest, published),
    )


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
    """``POST /api/plugin/github/pull-refresh`` — start or join one pull request's refresh.

    The body names ``number``, and may name ``retry``, a reader's own click. ``refresh``
    says whether this request ``started`` the job or ``joined`` one that was running,
    answered ``202``, or why an automatic request started nothing: the record is not due
    (``not_due``), or there is none (``not_cached``), answered ``200``. Past the bound on
    jobs it is refused, ``too_many``, answered ``429``, and nothing starts. ``pull`` is the
    envelope as of that moment: with a job running, ``refreshing`` is true, and it is
    ``pending`` while no record is cached yet.
    """

    from metabrowser.builtin_plugins.github.pull_route import (
        PullRequestError,
        pull_envelope,
        pull_host,
        pull_view,
        refresh_request,
        start_refresh,
        status_route,
    )

    body = await _json_body(request)
    if isinstance(body, tuple):
        return _invalid_request(*body)
    try:
        ask = refresh_request(body)
    except PullRequestError as exc:
        return _invalid_request(str(exc))
    await _resolve(request)
    host = pull_host(request.app)
    if host is None:
        return JSONResponse(
            {"error": "this server serves no GitHub repository", "code": "not_github"},
            status_code=409,
        )
    started = await start_refresh(host, ask)
    # Read after the start, on the loop: a job is running, whatever it does next.
    view = pull_view(host, get_source_session().subject, ask.number)
    envelope = await asyncio.to_thread(pull_envelope, view)
    if view.kept is not None:
        view.kept.saw_record(envelope["fetched_at"], without_store=_without_store(envelope))
    # ``status_route`` is where a one-shot ``--api`` reads how the refresh ended.
    answer = {"refresh": started, "pull": dict(envelope), "status_route": status_route(ask.number)}
    if started == "too_many":
        answer.update(_TOO_MANY)
    return JSONResponse(answer, status_code=_REFRESH_STATUS[started], headers=_NO_STORE)


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
    await _resolve(request)
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
    await _resolve(request)
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


async def pull_files_handler(request: Request) -> Response:
    """``GET /api/plugin/github/pull-files?number=<n>&offset=&limit=`` — see :mod:`.pull_files_route`.

    From the cache alone, with an entity tag, so a tree that polls a list while it fills is
    answered ``304`` until the next page is published.
    """

    from metabrowser.builtin_plugins.github.pull_files_route import (
        FilesRequestError,
        envelope_etag,
        files_file_stamp,
        files_view,
        files_window,
        pull_files_envelope,
    )

    try:
        window = files_window(request.query_params)
    except FilesRequestError as exc:
        return _invalid_request(str(exc))
    await _resolve(request)
    view = files_view(request.app, window.number)
    stamp = await asyncio.to_thread(files_file_stamp, view)
    envelope = await asyncio.to_thread(pull_files_envelope, view, window)
    etag = envelope_etag(envelope, stamp)
    headers = {**_NO_STORE, "etag": etag}
    if matches_if_none_match(request, etag):
        return Response(status_code=304, headers=headers)
    return JSONResponse(dict(envelope), headers=headers)


async def pull_files_refresh_handler(request: Request) -> JSONResponse:
    """``POST /api/plugin/github/pull-files-refresh`` — start or join one file list's refresh.

    The body names ``number``, and may name ``retry``, a reader's own click. ``refresh``
    says whether this request ``started`` the job or ``joined`` one that was running,
    answered ``202``; that it is ``not_due``, answered ``200``: the list is whole and
    current, it was tried within the window, or GitHub's limit holds; or, past the bound on
    jobs, ``too_many``, answered ``429``, starting nothing. ``files`` is the envelope as of
    that moment without its rows.
    """

    from metabrowser.builtin_plugins.github.pull_files_route import (
        FilesRequestError,
        FilesWindow,
        files_refresh_request,
        files_refresh_wanted,
        files_view,
        pull_files_envelope,
        start_files_refresh,
        status_route,
    )

    body = await _json_body(request)
    if isinstance(body, tuple):
        return _invalid_request(*body)
    try:
        ask = files_refresh_request(body)
    except FilesRequestError as exc:
        return _invalid_request(str(exc))
    await _resolve(request)
    view = files_view(request.app, ask.number)
    if view.repository is None or view.coordinator is None:
        return JSONResponse(
            {"error": "this server serves no GitHub repository", "code": "not_github"},
            status_code=409,
        )
    wanted, local = await asyncio.to_thread(files_refresh_wanted, view, ask)
    started = start_files_refresh(view, ask, wanted=wanted, local=local)
    # Read after the start, on the loop: the job is running, whatever it does next.
    after = files_view(request.app, ask.number)
    envelope = await asyncio.to_thread(pull_files_envelope, after, FilesWindow(ask.number, limit=0))
    answer: dict[str, Any] = {
        "refresh": started,
        "files": dict(envelope),
        "status_route": status_route(ask.number),
    }
    if started == "too_many":
        answer.update(_TOO_MANY)
    return JSONResponse(answer, status_code=_REFRESH_STATUS[started], headers=_NO_STORE)


__all__ = [
    "MAX_REFRESH_REQUEST_BYTES",
    "pull_files_handler",
    "pull_files_refresh_handler",
    "pull_handler",
    "pull_markdown_handler",
    "pull_refresh_handler",
    "pull_comparison_handler",
    "pulls_handler",
    "pulls_refresh_handler",
]
