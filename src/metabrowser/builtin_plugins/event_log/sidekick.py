"""Server-side data hooks for the built-in event-log plugin.

Four handlers, one per view, each a query of one segment's records
(:mod:`metabrowser.event_log_views`). The reads go through the content reader, whose bounded
calls are the same for every source, so nothing here branches on the source. The kind is
picked for a file of an attached folder only (the manifest's ``path_glob`` is a filesystem
match), so the views open there.

A segment is read once and put together as a table keyed on the content's fingerprint,
which an attached folder takes from the file's mtime and a pin from the blob's ID, so a
page that asks for the next screen of a timeline, or opens a span, parses nothing again,
and a segment still being written is read again after each append.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from pathlib import PurePosixPath
from typing import Any, Final

from starlette.requests import Request
from starlette.responses import JSONResponse

from metabrowser import event_log
from metabrowser import event_log_views as views
from metabrowser.plugin_api import (
    ContentReadError,
    UnsupportedSourceCapabilityError,
    read_content_window,
    resolve_content,
    resolve_path,
)

# The entries of the folder looked through for a later segment of the same process: the log
# keeps at most MAX_TOTAL_BYTES in segments of MAX_FILE_BYTES, which is far fewer, so a
# folder with more is not the log's and the answer is "no later segment".
MAX_SIBLINGS: Final = 10_000
# The errors a file that is not the log can raise while it is put together or answered:
# a number or time out of range, nesting past the recursion limit. They are the file's
# fault, so the answer is a 422 that names it.
_UNREADABLE: Final = (ValueError, OverflowError, RecursionError)


def _refusal(message: str, code: str, status: int, *, detail: str = "") -> JSONResponse:
    """A view's refusal: *message* is the reader's sentence the view shows, *detail* the
    specifics for an agent (docs/design-system-messages.md)."""
    return JSONResponse(
        {"error": message, "code": code, **({"detail": detail} if detail else {})},
        status_code=status,
    )


async def _table(request: Request) -> views.Table | JSONResponse:
    """The table for ``?path=``, or the response that says why there is none.

    The path is whatever identity the client holds: an inventory path under an attached
    folder, a GitPath wire on a pinned revision.
    """

    subpath = request.query_params.get("path", "")
    try:
        ref = await resolve_content(subpath)
        if ref is None:
            return _refusal("This log file was not found.", "not_found", 404)
        if ref.logical_ext != ".jsonl":
            return _refusal("This file is not a JSONL log.", "not_jsonl", 400)
        cached = views.remembered(ref.identity, ref.fingerprint)
        if cached is not None:
            return cached
        window = await read_content_window(ref, max_bytes=views.MAX_VIEW_BYTES)
    except ContentReadError as exc:
        return _refusal(exc.reader_message, exc.code, exc.http_status, detail=str(exc))
    if window.has_more:
        # The cap is on bytes and the read enforces it: a compressed file declares its
        # length in a trailer nothing verifies, so asking for the cap and finding more is
        # the answer that cannot be forged.
        return _refusal(
            "This log is too large to show here. The Raw JSON view shows it.",
            "event_log_too_large",
            413,
            detail=f"The log is larger than one segment ({views.MAX_VIEW_BYTES} bytes)",
        )
    try:
        table = await asyncio.to_thread(views.build_table, window.data)
    except _UNREADABLE as exc:
        return _unreadable(subpath, exc)
    if table.records == 0 and table.skipped > 0:
        return _refusal(
            "This file is not an event log.",
            "not_an_event_log",
            415,
            detail=f"None of its {table.skipped} lines is an event log record of schema "
            f"version {views.event_log.SCHEMA_VERSION}",
        )
    views.remember(ref.identity, ref.fingerprint, table)
    return table


def _unreadable(subpath: str, exc: BaseException) -> JSONResponse:
    name = PurePosixPath(subpath).name or subpath
    return _refusal(
        f"{name} could not be read as an event log.",
        "unreadable_event_log",
        422,
        detail=f"{type(exc).__name__}: {exc}",
    )


def _later_segment(subpath: str) -> bool:
    """Whether the process that wrote this segment wrote a later one into its folder.

    A span still open when a segment rolls ends in the next one, so a segment with a
    successor says its unfinished work may have finished there. Filesystem only: a
    revision of a repository holds one blob and no sibling.
    """

    try:
        path = resolve_path(subpath)
    except UnsupportedSourceCapabilityError:
        return False
    parsed = event_log.parse_file_name(path.name) if path is not None else None
    if path is None or parsed is None:
        return False
    start, pid, number = parsed
    try:
        with os.scandir(path.parent) as entries:
            for count, entry in enumerate(entries):
                if count >= MAX_SIBLINGS:
                    break
                other = event_log.parse_file_name(entry.name)
                if other is not None and other[:2] == (start, pid) and other[2] > number:
                    return True
    except OSError:
        return False
    return False


async def _answer(request: Request, build: Callable[[views.Table, dict[str, str]], dict[str, Any]]):
    table = await _table(request)
    if isinstance(table, JSONResponse):
        return table
    params = dict(request.query_params)
    subpath = params.get("path", "")
    try:
        answer = await asyncio.to_thread(build, table, params)
    except views.ViewError as exc:
        return _refusal(str(exc), exc.code, exc.status, detail=exc.detail)
    except _UNREADABLE as exc:
        return _unreadable(subpath, exc)
    # Whether a later segment exists is read for each answer: the table is kept by the
    # fingerprint of this file, which a successor does not change.
    answer["log"]["continues"] = await asyncio.to_thread(_later_segment, subpath)
    try:
        return JSONResponse(answer)
    except _UNREADABLE as exc:
        return _unreadable(subpath, exc)


def _check(params: dict[str, str], allowed: set[str]) -> None:
    unknown = sorted(set(params) - allowed - {"path"})
    if unknown:
        raise views.ViewError(f"unknown parameter {', '.join(unknown)}", "invalid_query")


_FILTERS = {"kind", "outcome", "name", "client", "cause", "min_ms"}


def _timeline(table: views.Table, params: dict[str, str]) -> dict[str, Any]:
    _check(params, _FILTERS | {"parent", "offset", "limit", "order", "focus"})
    offset, limit = views.parse_page(params, default_limit=views.DEFAULT_TIMELINE_ROWS)
    return views.timeline(
        table,
        views.parse_filter(params),
        parent=params.get("parent") or None,
        offset=offset,
        limit=limit,
        order=views.parse_order(params.get("order")),
        focus=params.get("focus") or None,
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
