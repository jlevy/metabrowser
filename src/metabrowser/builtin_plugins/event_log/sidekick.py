"""Server-side data hooks for the built-in event-log plugin.

Four handlers, one per view, each a query of one segment's records
(:mod:`metabrowser.event_log_views`). One reader serves every source kind: the content
reader answers an attached folder and a pinned revision through the same bounded calls,
so nothing here knows which one is active.

A segment is read once and put together as a table keyed on the content's fingerprint,
which an attached folder takes from the file's mtime and a pin from the blob's ID, so a
page that asks for the next screen of a timeline, or opens a span, parses nothing again,
and a segment still being written is read again after each append.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse

from metabrowser import event_log_views as views
from metabrowser.plugin_api import ContentReadError, read_content_window, resolve_content


def _refusal(message: str, code: str, status: int) -> JSONResponse:
    return JSONResponse({"error": message, "code": code}, status_code=status)


async def _table(request: Request) -> views.Table | JSONResponse:
    """The table for ``?path=``, or the response that says why there is none.

    The path is whatever identity the client holds: an inventory path under an attached
    folder, a GitPath wire on a pinned revision.
    """

    subpath = request.query_params.get("path", "")
    try:
        ref = await resolve_content(subpath)
        if ref is None:
            return _refusal("Not found", "not_found", 404)
        if ref.logical_ext != ".jsonl":
            return _refusal("Not a JSONL file", "not_jsonl", 400)
        cached = views.remembered(ref.identity, ref.fingerprint)
        if cached is not None:
            return cached
        window = await read_content_window(ref, max_bytes=views.MAX_VIEW_BYTES)
    except ContentReadError as exc:
        return _refusal(str(exc), exc.code, exc.http_status)
    if window.has_more:
        # The cap is on bytes and the read enforces it: a compressed file declares its
        # length in a trailer nothing verifies, so asking for the cap and finding more is
        # the answer that cannot be forged.
        return _refusal(
            f"The log is larger than one segment ({views.MAX_VIEW_BYTES} bytes); "
            "the Raw JSON view reads it",
            "event_log_too_large",
            413,
        )
    table = await asyncio.to_thread(views.build_table, window.data)
    if table.records == 0 and table.skipped > 0:
        return _refusal(
            f"None of its {table.skipped} lines is an event log record of schema "
            f"version {views.event_log.SCHEMA_VERSION}",
            "not_an_event_log",
            415,
        )
    views.remember(ref.identity, ref.fingerprint, table)
    return table


async def _answer(request: Request, build: Callable[[views.Table, dict[str, str]], dict[str, Any]]):
    table = await _table(request)
    if isinstance(table, JSONResponse):
        return table
    params = dict(request.query_params)
    try:
        answer = await asyncio.to_thread(build, table, params)
    except views.ViewError as exc:
        return _refusal(str(exc), exc.code, exc.status)
    return JSONResponse(answer)


def _check(params: dict[str, str], allowed: set[str]) -> None:
    unknown = sorted(set(params) - allowed - {"path"})
    if unknown:
        raise views.ViewError(f"unknown parameter {', '.join(unknown)}", "invalid_query")


_FILTERS = {"kind", "outcome", "name", "client", "cause", "min_ms"}


def _timeline(table: views.Table, params: dict[str, str]) -> dict[str, Any]:
    _check(params, _FILTERS | {"parent", "offset", "limit"})
    offset, limit = views.parse_page(params, default_limit=views.DEFAULT_TIMELINE_ROWS)
    return views.timeline(
        table,
        views.parse_filter(params),
        parent=params.get("parent") or None,
        offset=offset,
        limit=limit,
    )


def _slowest(table: views.Table, params: dict[str, str]) -> dict[str, Any]:
    _check(params, _FILTERS | {"limit"})
    _, limit = views.parse_page(params, default_limit=views.DEFAULT_SLOWEST_ROWS)
    return views.slowest(table, views.parse_filter(params), limit=limit)


def _kinds(table: views.Table, params: dict[str, str]) -> dict[str, Any]:
    _check(params, _FILTERS)
    return views.by_kind(table, views.parse_filter(params))


def _errors(table: views.Table, params: dict[str, str]) -> dict[str, Any]:
    _check(params, {"kind"})
    return views.errors(table, views.parse_kinds(params.get("kind")))


async def timeline_handler(request: Request) -> JSONResponse:
    """A page of a segment's spans, nested: the roots, or the children of ``parent``."""

    return await _answer(request, _timeline)


async def slowest_handler(request: Request) -> JSONResponse:
    """The longest spans and page reports of a segment, with the distribution of times."""

    return await _answer(request, _slowest)


async def kinds_handler(request: Request) -> JSONResponse:
    """A segment's records by kind and name: counts, outcomes, and latency percentiles."""

    return await _answer(request, _kinds)


async def errors_handler(request: Request) -> JSONResponse:
    """A segment's failures by cause, the page's reports apart, and its unfinished work."""

    return await _answer(request, _errors)
