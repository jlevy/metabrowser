"""Python sidekick for the structured (JSON/YAML) plugin.

Mounts ``/api/plugin/structured/parsed``: parses a JSON / YAML file
once per ``(identity, fingerprint)`` and ships a JSON envelope with the
parsed structure, a canonical YAML re-serialization, and tree-shape
metadata (node count, max depth) the client uses for budget
decisions.

Failure modes are surfaced explicitly:
- ``parse_error`` is set on malformed input, and on a compressed file whose
  stream cannot be decoded; the client falls back to the Source view and
  renders the error in a banner.
- ``truncated`` is set when the content exceeds STRUCTURED_PARSE_MAX_BYTES;
  same fallback behavior.

One handler serves every source kind. The content reader answers an attached
folder and a pinned revision through the same bounded calls, runs the blocking
part off the event loop, and reports the fingerprint the cache is keyed on, so
nothing here branches on which subject is active.

``size`` is the size of the file as it is stored, whatever was read or parsed:
its size on disk under a folder, which for ``data.json.gz`` is the compressed
size, as ``/api/file`` reports it; and the blob's length on a pinned revision.
It is not capped at the parse limit.
"""

from __future__ import annotations

import asyncio

from starlette.requests import Request
from starlette.responses import JSONResponse

from metabrowser.builtin_plugins.structured.parser import (
    STRUCTURED_PARSE_MAX_BYTES,
    StructuredPayload,
    error_payload,
    lookup_structured_payload,
    parse_structured_bytes,
    remember_structured_payload,
    truncated_payload,
)
from metabrowser.http_caching import build_scoped_etag
from metabrowser.plugin_api import (
    ArtifactCompressionError,
    ArtifactDecompressionLimitError,
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
    size: int | None,
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
        payload = lookup_structured_payload(ref.identity, ext, ref.fingerprint)
        if payload is None:
            payload = await _parse(ref, ext)
            remember_structured_payload(ref.identity, ext, ref.fingerprint, payload)
    except ContentReadError as exc:
        return JSONResponse(
            {"error": str(exc), "code": exc.code, "path": raw_path},
            status_code=exc.http_status,
        )
    return _envelope(
        path=ref.identity,
        ext=ext,
        fingerprint=ref.fingerprint,
        size=ref.stored_size,
        payload=payload,
    )


async def _parse(ref: ContentRef, ext: str) -> StructuredPayload:
    """Bounded read plus parse.

    Content past the cap is ``truncated``, not an error: the Tree view falls
    back to Source on that flag, which is a better answer for a reader than a
    failed request, and it is the same answer for content too large to read at
    all. The cap is enforced by the read, not by a declared size, because a
    compressed artifact's declared size is a trailer nothing verifies.

    A compressed file whose stream cannot be decoded is a ``parse_error`` for the
    same reason: the file is there, and the Source view says what is wrong with
    it. Both are what 0.11.0 answered. Content that is gone or cannot be opened
    stays the read's own error.

    Under a negative cap nothing fits, so nothing is read and every file is
    ``truncated``. That is 0.11.0's answer for a file that is not compressed: it
    compared the file's size with the cap before opening it, and every size, an
    empty file's too, is past a negative cap. The read itself refuses a negative
    bound, so the setting is settled here and never reaches it.
    """

    if STRUCTURED_PARSE_MAX_BYTES < 0:
        return truncated_payload()
    try:
        window = await read_content_window(ref, max_bytes=STRUCTURED_PARSE_MAX_BYTES)
    except ContentReadError as exc:
        # A compressed artifact past a resource bound, its time budget included, and a
        # blob a pin will not read for its size.
        if isinstance(exc, ArtifactDecompressionLimitError) or exc.http_status == 413:
            return truncated_payload()
        if isinstance(exc, ArtifactCompressionError):
            return error_payload(exc)
        raise
    if window.has_more:
        return truncated_payload()
    return await asyncio.to_thread(parse_structured_bytes, window.data, ext)
