"""Server-side data hooks for the built-in agent-log plugin.

One handler for every source kind: the content reader answers an attached
folder and a pinned revision through the same bounded calls, so nothing here
knows which one is active.

The payload is memoized on the content's fingerprint rather than on a host
path, so the Charts tab does not re-parse an unchanged log -- the property
:mod:`metabrowser.charts` measures -- and a pinned blob gets the same
treatment. Resolution establishes that fingerprint, so a cache hit costs no
read at all.
"""

from __future__ import annotations

import asyncio

from starlette.requests import Request
from starlette.responses import JSONResponse

from metabrowser import jsonl_view
from metabrowser.charts import (
    extract_agent_charts_bytes,
    lookup_agent_charts,
    remember_agent_charts,
)
from metabrowser.plugin_api import (
    ContentReadError,
    JsonlParseLimitError,
    read_content_window,
    resolve_content,
)


def _too_large() -> JSONResponse:
    return JSONResponse(
        {"error": f"JSONL content exceeds {jsonl_view._JSONL_PARSE_MAX_BYTES} decompressed bytes"},
        status_code=413,
    )


async def charts_handler(request: Request) -> JSONResponse:
    """Return tally and chart data for a supported coding-agent JSONL log.

    The path is whatever identity the client holds: an inventory path under an
    attached folder, a GitPath wire on a pinned revision.
    """

    subpath = request.query_params.get("path", "")
    parse_max_bytes = jsonl_view._JSONL_PARSE_MAX_BYTES
    try:
        ref = await resolve_content(subpath)
        if ref is None:
            return JSONResponse({"error": "Not found"}, status_code=404)
        if ref.logical_ext != ".jsonl":
            return JSONResponse({"error": "Not a JSONL file"}, status_code=400)
        cached = lookup_agent_charts(ref.identity, ref.fingerprint)
        if cached is not None:
            return JSONResponse(cached)
        window = await read_content_window(ref, max_bytes=parse_max_bytes)
    except ContentReadError as exc:
        if exc.http_status == 413:
            return _too_large()
        return JSONResponse({"error": str(exc), "code": exc.code}, status_code=exc.http_status)
    if window.has_more:
        # The cap is on bytes and the read is what enforces it. A compressed
        # log declares its length in a trailer nothing verifies, so asking for
        # the cap and seeing more remain is the only answer that cannot be
        # forged.
        return _too_large()
    try:
        payload = await asyncio.to_thread(extract_agent_charts_bytes, window.data)
    except JsonlParseLimitError as exc:
        return JSONResponse({"error": str(exc)}, status_code=413)
    except (TypeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
    remember_agent_charts(ref.identity, ref.fingerprint, payload)
    return JSONResponse(payload)
