"""Python sidekick for the structured (JSON/YAML) plugin.

Mounts ``/api/plugin/structured/parsed``: parses a JSON / YAML file
once per ``(identity, fingerprint)`` and ships a JSON envelope with the
parsed structure, a canonical YAML re-serialization, and tree-shape
metadata (node count, max depth) the client uses for budget
decisions.

Failure modes are surfaced explicitly:
- ``parse_error`` is set on malformed input; the client falls back to
  the Source view and renders the error in a banner.
- ``truncated`` is set when the content exceeds STRUCTURED_PARSE_MAX_BYTES;
  same fallback behavior.

One handler serves every source kind. The content reader answers an attached
folder and a pinned revision through the same bounded calls, runs the blocking
part off the event loop, and reports the fingerprint the cache is keyed on, so
nothing here branches on which subject is active.
"""

from __future__ import annotations

import asyncio

from starlette.requests import Request
from starlette.responses import JSONResponse

from metabrowser.builtin_plugins.structured.parser import (
    STRUCTURED_PARSE_MAX_BYTES,
    StructuredPayload,
    lookup_structured_payload,
    parse_structured_bytes,
    remember_structured_payload,
    truncated_payload,
)
from metabrowser.http_caching import build_scoped_etag
from metabrowser.plugin_api import (
    ContentReadError,
    ContentRef,
    read_content_window,
    resolve_content,
)

_STRUCTURED_EXTS = (".json", ".yaml", ".yml")


def _envelope(
    *,
    path: str,
    ext: str,
    fingerprint: str,
    size: int,
    payload: StructuredPayload,
) -> JSONResponse:
    return JSONResponse(
        {
            "type": "structured",
            "path": path,
            "ext": ext,
            "mtime_hash": fingerprint,
            "size": size,
            "parsed": payload.parsed,
            "pretty_yaml": payload.pretty_yaml,
            "node_count": payload.node_count,
            "max_depth": payload.max_depth,
            "comments_supported": False,
            "parse_error": payload.parse_error,
            "truncated": payload.truncated,
        },
        headers={"ETag": build_scoped_etag(fingerprint)},
    )


async def parsed_handler(request: Request) -> JSONResponse:
    """``GET /api/plugin/structured/parsed?path=<identity>``.

    Returns the parsed structure plus a canonical YAML re-serialization. The
    client mounts the Tree view from this; the Source view goes through
    ``/api/file`` like every other text kind. The path is whatever identity the
    client holds, an inventory path or a GitPath wire.
    """

    raw_path = request.query_params.get("path", "")
    try:
        ref = await resolve_content(raw_path)
        if ref is None:
            return JSONResponse({"error": "Not found", "path": raw_path}, status_code=404)
        ext = ref.logical_ext
        if ext not in _STRUCTURED_EXTS:
            return JSONResponse(
                {"error": "Unsupported extension", "path": raw_path, "ext": ext},
                status_code=400,
            )
        cached = lookup_structured_payload(ref.identity, ext, ref.fingerprint)
        if cached is not None:
            payload, size = cached
        else:
            payload, size = await _parse(ref, ext)
            remember_structured_payload(ref.identity, ext, ref.fingerprint, (payload, size))
    except ContentReadError as exc:
        return JSONResponse(
            {"error": str(exc), "code": exc.code, "path": raw_path},
            status_code=exc.http_status,
        )
    return _envelope(
        path=ref.identity,
        ext=ext,
        fingerprint=ref.fingerprint,
        size=size,
        payload=payload,
    )


async def _parse(ref: ContentRef, ext: str) -> tuple[StructuredPayload, int]:
    """Bounded read plus parse, with the byte count that was parsed.

    Content past the cap is ``truncated``, not an error: the Tree view falls
    back to Source on that flag, which is a better answer for a reader than a
    failed request, and it is the same answer for content too large to read at
    all. The cap is enforced by the read, not by a declared size, because a
    compressed artifact's declared size is a trailer nothing verifies.
    """

    try:
        window = await read_content_window(ref, max_bytes=STRUCTURED_PARSE_MAX_BYTES)
    except ContentReadError as exc:
        if exc.http_status != 413:
            raise
        return truncated_payload(), 0
    if window.has_more:
        return truncated_payload(), len(window.data)
    parsed = await asyncio.to_thread(parse_structured_bytes, window.data, ext)
    return parsed, len(window.data)
