"""Bounded byte-chunk data hook for the built-in binary plugin.

Mounts ``GET /api/plugin/binary/chunk``: reads a bounded window of a file's
logical bytes and ships them base64-encoded so the transport stays exact.
The browser converts the payload straight to a ``Uint8Array``; nothing on
either side runs the content through a text decoder.

Reading is not the expensive part and the constants say so. Measured locally:
an 8 MiB plain read takes 4.6 ms and seeking to any offset is O(1), so a plain
file is bounded only by what the browser can paint. A compressed artifact is
different in kind: :meth:`ArtifactPath.open_binary` returns a non-seekable
stream, so reaching offset *N* costs decompressing *N* bytes and every request
restarts from zero. That is real but modest — gzip decodes at roughly 500 MB/s
here, and a read at a 12 MiB offset measured 29 ms, nowhere near the 5-second
per-open CPU budget in ``gz_io``.

The total cost of walking a compressed file is quadratic in the number of
requests, not in the file size: reading *S* bytes in chunks of *C* decompresses
``S²/2C`` in total. A larger chunk therefore makes compressed files cheaper,
not dearer, which is why both kinds share one ceiling and the chunk default is
generous.

The handler is synchronous on purpose: the data-hook dispatcher runs sync
sidekicks through ``run_in_threadpool``, so the read is already off the event
loop without a second offloading layer.
"""

from __future__ import annotations

import base64
import logging
import os
import time
from typing import IO, TYPE_CHECKING, Any

from starlette.responses import JSONResponse
from strif import file_mtime_hash

from metabrowser.http_caching import build_scoped_etag
from metabrowser.plugin_api import (
    ArtifactCompressionError,
    ArtifactDecompressionLimitError,
    ArtifactPath,
    relativize_path,
    resolve_path,
)

if TYPE_CHECKING:
    from pathlib import Path

    from starlette.requests import Request

LOG = logging.getLogger(__name__)

# Eligibility ceiling for a file's logical bytes, compressed or not.
#
# This is a browser memory budget, not a server one. Reading is cheap; the
# view keeps every loaded byte as real text in the DOM so find-in-page,
# select-all, and print cover the whole file, and that is what costs. Loading
# 32 MiB to completion measured 87k DOM nodes and about 306 MB of JS heap while
# scrolling stayed between 22 ms and 107 ms — interactive, and the largest size
# actually measured. A view that virtualized its window instead could raise
# this by orders of magnitude, at the cost of those native behaviors.
BINARY_PREVIEW_MAX_BYTES = int(
    os.environ.get("METABROWSER_BINARY_PREVIEW_MAX_BYTES", str(32 * 1024 * 1024))
)
# Default request size, used when a caller does not ask for one. The view
# itself opens with a smaller first chunk and grows from there; this is the
# fallback for direct callers.
BINARY_PREVIEW_CHUNK_BYTES = int(
    os.environ.get("METABROWSER_BINARY_PREVIEW_BYTES", str(1024 * 1024))
)
# Per-request clamp, so a caller cannot widen one request into an unbounded read.
BINARY_PREVIEW_MAX_CHUNK_BYTES = int(
    os.environ.get("METABROWSER_BINARY_PREVIEW_MAX_CHUNK_BYTES", str(16 * 1024 * 1024))
)

# Copying a decompressed stream forward to reach an offset.
_SKIP_CHUNK_BYTES = 64 * 1024


class _RangeError(ValueError):
    """A query parameter is not a usable byte range."""


def _preview_ceiling(artifact: ArtifactPath) -> int:
    """Return the byte ceiling that applies to this artifact.

    One expression, so the eligibility check, the reachable-window check, and
    the reported ``max_preview_bytes`` cannot drift apart. Compressed and plain
    artifacts share it: decompression is linear in the offset and fast enough
    that it does not warrant a lower bound of its own.
    """
    del artifact
    return BINARY_PREVIEW_MAX_BYTES


def _query_bounded_int(
    request: Request,
    name: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    """Parse one integer query parameter, rejecting anything unusable.

    Unlike the shell's text-preview helper this raises instead of falling back
    to the default: a malformed range on a byte window would otherwise return
    the wrong bytes under a 200, and the client has no way to notice.
    """
    raw = request.query_params.get(name, "")
    if raw == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise _RangeError(f"{name} must be an integer") from exc
    if value < minimum:
        raise _RangeError(f"{name} must be at least {minimum}")
    return min(value, maximum)


def _skip_forward(stream: IO[bytes], offset: int) -> None:
    """Advance a non-seekable decompressed stream to ``offset``."""
    remaining = offset
    while remaining > 0:
        skipped = stream.read(min(_SKIP_CHUNK_BYTES, remaining))
        if not skipped:
            return
        remaining -= len(skipped)


def read_byte_chunk(artifact: ArtifactPath, offset: int, limit: int) -> tuple[bytes, bool]:
    """Read ``limit`` logical bytes at ``offset``, plus whether more remain.

    Reads one byte past the window to answer "is there more?" without a second
    open, and clips it back off before returning. The output bound is the
    window itself, so a compressed artifact cannot expand past what the caller
    asked for.
    """
    with artifact.open_binary(max_output_bytes=offset + limit + 1) as stream:
        if artifact.is_compressed:
            _skip_forward(stream, offset)
        else:
            stream.seek(offset)
        raw = stream.read(limit + 1)
    return raw[:limit], len(raw) > limit


def _error(message: str, status_code: int, **fields: Any) -> JSONResponse:
    return JSONResponse({"type": "binary_chunk_error", "error": message, **fields}, status_code)


def _unavailable(subpath: str) -> JSONResponse:
    return _error("This file is no longer available.", 404, path=subpath)


def chunk_handler(request: Request) -> JSONResponse:
    """``GET /api/plugin/binary/chunk?path=<rel>&offset=<bytes>&limit=<bytes>``.

    Returns a ``binary_chunk`` envelope. Failures are bounded, public-safe 4xx
    responses the bytes view turns into concise inline states; no message
    carries raw byte content or an absolute local path.
    """
    started_at = time.monotonic()
    subpath = request.query_params.get("path", "")
    target: Path | None = resolve_path(subpath)
    if target is None or not target.is_file():
        return _unavailable(subpath)

    artifact = ArtifactPath(target)
    ceiling = _preview_ceiling(artifact)

    try:
        offset = _query_bounded_int(request, "offset", 0, minimum=0, maximum=ceiling)
        limit = _query_bounded_int(
            request,
            "limit",
            BINARY_PREVIEW_CHUNK_BYTES,
            minimum=1,
            maximum=BINARY_PREVIEW_MAX_CHUNK_BYTES,
        )
    except _RangeError as exc:
        return _error("Could not load these bytes.", 400, path=subpath, detail=str(exc))

    try:
        logical_size = artifact.logical_size
    except ArtifactDecompressionLimitError:
        return _error("Preview unavailable.", 413, path=subpath, max_preview_bytes=ceiling)
    except ArtifactCompressionError:
        return _error("This file could not be decompressed.", 422, path=subpath)
    except OSError:
        return _unavailable(subpath)

    # The ceiling caps how much may be *loaded*, not which files may be opened.
    # It used to refuse anything larger outright, which meant the view existed
    # for binaries but declined the large ones with nothing to look at; a bound
    # on browser memory is no reason to withhold the first megabyte.
    readable = min(logical_size, ceiling)
    # Past the ceiling there is nothing loadable, which is a range error. Past
    # the end of a file that fits under it there is simply nothing left, and
    # an empty chunk says so without the caller special-casing a status.
    if offset >= ceiling and offset > 0:
        return _error(
            "Preview unavailable.",
            416,
            path=subpath,
            logical_size=logical_size,
            max_preview_bytes=ceiling,
        )
    limit = min(limit, max(readable - offset, 0))

    try:
        payload, has_more = read_byte_chunk(artifact, offset, limit)
    except ArtifactDecompressionLimitError:
        return _error("Preview unavailable.", 413, path=subpath, max_preview_bytes=ceiling)
    except ArtifactCompressionError:
        return _error("This file could not be decompressed.", 422, path=subpath)
    except OSError:
        return _unavailable(subpath)

    elapsed = time.monotonic() - started_at
    if elapsed > 0.5:
        LOG.warning(
            "binary chunk read %s offset=%d limit=%d bytes=%d took %.2fs",
            subpath,
            offset,
            limit,
            len(payload),
            elapsed,
        )

    next_offset = offset + len(payload)
    mtime_hash = file_mtime_hash(target)
    return JSONResponse(
        {
            "type": "binary_chunk",
            "path": relativize_path(str(target)) or subpath,
            "offset": offset,
            "bytes_read": len(payload),
            "next_offset": next_offset,
            "logical_size": logical_size,
            "max_preview_bytes": ceiling,
            # More bytes exist *and* they are still inside the window. Past the
            # ceiling the answer is no, so the view stops offering Load more.
            "has_more": has_more and next_offset < readable,
            # The file continues past what may be loaded. Distinct from
            # `has_more`: both are false at the ceiling, and only this one
            # tells the reader that what they see is not the whole file.
            "preview_limited": logical_size > ceiling,
            "mtime_hash": mtime_hash,
            "content_base64": base64.b64encode(payload).decode("ascii"),
        },
        headers={"ETag": build_scoped_etag(mtime_hash)},
    )
