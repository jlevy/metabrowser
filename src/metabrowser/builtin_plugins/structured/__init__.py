"""Python sidekick for the structured (JSON/YAML) plugin.

Mounts ``/api/plugin/structured/parsed``: parses a JSON / YAML file
once per ``(path, mtime_hash)`` and ships a JSON envelope with the
parsed structure, a canonical YAML re-serialization, and tree-shape
metadata (node count, max depth) the client uses for budget
decisions.

Failure modes are surfaced explicitly:
- ``parse_error`` is set on malformed input; the client falls back to
  the Source view and renders the error in a banner.
- ``truncated`` is set when the file exceeds STRUCTURED_PARSE_MAX_BYTES;
  same fallback behavior.

The handler is async so a pinned Git blob read stays on the event loop
and does not deadlock the shared cat-file pool. Filesystem reads run in
the thread pool. On a pin the cache key is the object id, not mtime.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from starlette.requests import Request
from starlette.responses import JSONResponse
from strif import file_mtime_hash

from metabrowser.builtin_plugins.structured.parser import (
    StructuredPayload,
    parse_structured,
    parse_structured_bytes,
)
from metabrowser.git.content_routes import resolve_git_blob_entry
from metabrowser.git.tree_source import (
    GitBlobTooLargeError,
    GitObjectUnavailableError,
    GitPath,
    GitPathError,
    GitRevisionSubject,
)
from metabrowser.gz_io import ArtifactPath
from metabrowser.http_caching import build_scoped_etag
from metabrowser.plugin_api import relativize_path, resolve_path
from metabrowser.source import get_source_session

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


def _logical_ext(git_path: GitPath) -> str:
    if not git_path.segments:
        return ""
    return Path(git_path.segments[-1].decode("utf-8", "replace")).suffix.lower()


def _filesystem_parsed(request: Request) -> JSONResponse:
    raw_path = request.query_params.get("path", "")
    target = resolve_path(raw_path)
    if target is None or not target.is_file():
        return JSONResponse({"error": "Not found", "path": raw_path}, status_code=404)

    # ArtifactPath.logical_ext strips supported compression suffixes before
    # the server passes the extension to classifiers.
    artifact = ArtifactPath(target)
    ext = artifact.logical_ext
    if ext not in _STRUCTURED_EXTS:
        return JSONResponse(
            {"error": "Unsupported extension", "path": raw_path, "ext": ext},
            status_code=400,
        )

    mtime_hash = file_mtime_hash(target)
    payload = parse_structured(target, ext, mtime_hash)
    return _envelope(
        path=relativize_path(str(target)) or raw_path,
        ext=ext,
        fingerprint=mtime_hash,
        size=target.stat().st_size,
        payload=payload,
    )


async def _git_parsed(request: Request, subject: GitRevisionSubject) -> JSONResponse:
    raw_path = request.query_params.get("path", "")
    try:
        path = GitPath.from_wire(raw_path)
    except GitPathError:
        return JSONResponse({"error": "Not found", "path": raw_path}, status_code=404)
    try:
        entry = await resolve_git_blob_entry(subject.tree_source, path)
        if entry is None:
            return JSONResponse({"error": "Not found", "path": raw_path}, status_code=404)
        ext = _logical_ext(entry.path)
        if ext not in _STRUCTURED_EXTS:
            return JSONResponse(
                {"error": "Unsupported extension", "path": raw_path, "ext": ext},
                status_code=400,
            )
        data = await subject.tree_source.read_blob(entry.path)
    except GitObjectUnavailableError:
        return JSONResponse({"error": "Not found", "path": raw_path}, status_code=404)
    except GitBlobTooLargeError as exc:
        return JSONResponse(
            {"error": "File too large", "path": raw_path, "max_bytes": exc.max_bytes},
            status_code=413,
        )
    payload = await asyncio.to_thread(parse_structured_bytes, data, ext)
    return _envelope(
        path=path.to_wire(),
        ext=ext,
        fingerprint=entry.oid,
        size=len(data),
        payload=payload,
    )


async def parsed_handler(request: Request) -> JSONResponse:
    """``GET /api/plugin/structured/parsed?path=<rel-path>``.

    Returns the parsed structure plus a canonical YAML
    re-serialization. The client mounts the Tree view from this; the
    Source view goes through ``/api/file`` like every other text kind.
    On a pinned revision the path is a GitPath wire identity.
    """
    subject = get_source_session().subject
    if isinstance(subject, GitRevisionSubject):
        return await _git_parsed(request, subject)
    return await asyncio.to_thread(_filesystem_parsed, request)
