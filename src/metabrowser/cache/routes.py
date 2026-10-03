"""The read-only ``/api/cache/`` route table.

These routes make persisted cache state reachable through ``metab --api`` and pin it with
golden transcripts, so the cache needs no inspection command of its own. They project
logical records only; :mod:`metabrowser.cache.wire` states what they report and what they
never do.

The server imports this table at startup, and nothing else from the cache: each handler
imports :mod:`metabrowser.cache.projection`, which reaches the application home, only
when a cache route is requested. Ordinary local browsing therefore never resolves,
validates, creates, or imports the application home. Record reads and listings are
synchronous file-system work, so they run in a worker thread.

Numeric parameters are clamped, not rejected, as in :mod:`metabrowser.git.routes`; a
malformed page key is a 400, because silently restarting a page sequence would repeat
rows.

A server serving a pinned Git revision answers every one of these with
``unsupported_for_subject``. Its content was acquired from elsewhere and is
untrusted, and the home's records name every other cached source, so nothing
about them is served beside it. ``metab <url> --api /api/cache/...`` inspects
the cache from an empty filesystem root instead.
"""

from __future__ import annotations

import asyncio

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from metabrowser.source import (
    RepositorySubjectKind,
    UnsupportedSourceCapabilityError,
    get_source_session,
)


def _refuse_beside_acquired_content() -> None:
    if get_source_session().subject.kind == RepositorySubjectKind.git_revision.value:
        raise UnsupportedSourceCapabilityError("cache_inspection")


async def api_cache_layout(_request: Request) -> JSONResponse:
    """``GET /api/cache/layout`` — the home's format state and reclamation outcomes."""

    _refuse_beside_acquired_content()
    from metabrowser.cache.projection import layout_response

    status, body = await asyncio.to_thread(layout_response)
    return JSONResponse(body, status_code=status)


async def api_cache_sources(request: Request) -> JSONResponse:
    """``GET /api/cache/sources`` — one page of sources.

    Query parameters: ``limit`` (clamped page size) and ``after`` (the ``next_after``
    slug of the previous page).
    """

    _refuse_beside_acquired_content()
    from metabrowser.cache.projection import page_limit, sources_response

    limit = page_limit(request.query_params.get("limit"))
    after = request.query_params.get("after")
    status, body = await asyncio.to_thread(lambda: sources_response(limit=limit, after=after))
    return JSONResponse(body, status_code=status)


async def api_cache_source(request: Request) -> JSONResponse:
    """``GET /api/cache/source/{slug}`` — one source, its recency, and its store's head."""

    _refuse_beside_acquired_content()
    from metabrowser.cache.projection import source_response

    slug = str(request.path_params["slug"])
    status, body = await asyncio.to_thread(source_response, slug)
    return JSONResponse(body, status_code=status)


async def api_cache_stores(request: Request) -> JSONResponse:
    """``GET /api/cache/stores`` — one page of repository stores and their references.

    Query parameters: ``limit`` (clamped page size) and ``after`` (the ``next_after``
    store identity of the previous page).
    """

    _refuse_beside_acquired_content()
    from metabrowser.cache.projection import page_limit, stores_response

    limit = page_limit(request.query_params.get("limit"))
    after = request.query_params.get("after")
    status, body = await asyncio.to_thread(lambda: stores_response(limit=limit, after=after))
    return JSONResponse(body, status_code=status)


CACHE_ROUTES = [
    Route("/api/cache/layout", api_cache_layout),
    Route("/api/cache/sources", api_cache_sources),
    Route("/api/cache/source/{slug}", api_cache_source),
    Route("/api/cache/stores", api_cache_stores),
]


__all__ = [
    "CACHE_ROUTES",
    "api_cache_layout",
    "api_cache_source",
    "api_cache_sources",
    "api_cache_stores",
]
