"""Server-side data hooks for the built-in agent-log plugin.

The handler is async so a pinned Git blob read stays on the event loop
and does not deadlock the shared cat-file pool. Filesystem reads run in
the thread pool.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from starlette.requests import Request
from starlette.responses import JSONResponse

from metabrowser.charts import extract_agent_charts, extract_agent_charts_bytes
from metabrowser.git.content_routes import resolve_git_blob_entry
from metabrowser.git.tree_source import (
    GitBlobTooLargeError,
    GitObjectUnavailableError,
    GitPath,
    GitPathError,
    GitRevisionSubject,
)
from metabrowser.gz_io import ArtifactDecompressionLimitError, ArtifactPath
from metabrowser.jsonl_view import JsonlParseLimitError
from metabrowser.plugin_api import resolve_path
from metabrowser.source import get_source_session


def _logical_ext(git_path: GitPath) -> str:
    if not git_path.segments:
        return ""
    return Path(git_path.segments[-1].decode("utf-8", "replace")).suffix.lower()


def _filesystem_charts(request: Request) -> JSONResponse:
    subpath = request.query_params.get("path", "")
    target = resolve_path(subpath)
    if target is None or not target.is_file():
        return JSONResponse({"error": "Not found"}, status_code=404)
    if ArtifactPath(target).logical_ext != ".jsonl":
        return JSONResponse({"error": "Not a JSONL file"}, status_code=400)
    try:
        payload = extract_agent_charts(target)
    except (ArtifactDecompressionLimitError, JsonlParseLimitError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=413)
    except (OSError, TypeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
    return JSONResponse(payload)


async def _git_charts(request: Request, subject: GitRevisionSubject) -> JSONResponse:
    raw_path = request.query_params.get("path", "")
    try:
        path = GitPath.from_wire(raw_path)
    except GitPathError:
        return JSONResponse({"error": "Not found"}, status_code=404)
    try:
        entry = await resolve_git_blob_entry(subject.tree_source, path)
        if entry is None:
            return JSONResponse({"error": "Not found"}, status_code=404)
        if _logical_ext(entry.path) != ".jsonl":
            return JSONResponse({"error": "Not a JSONL file"}, status_code=400)
        data = await subject.tree_source.read_blob(entry.path)
    except GitObjectUnavailableError:
        return JSONResponse({"error": "Not found"}, status_code=404)
    except GitBlobTooLargeError as exc:
        return JSONResponse(
            {"error": "File too large", "path": raw_path, "max_bytes": exc.max_bytes},
            status_code=413,
        )
    try:
        payload = await asyncio.to_thread(extract_agent_charts_bytes, data)
    except JsonlParseLimitError as exc:
        return JSONResponse({"error": str(exc)}, status_code=413)
    except (TypeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
    return JSONResponse(payload)


async def charts_handler(request: Request) -> JSONResponse:
    """Return tally and chart data for a supported coding-agent JSONL log.

    On a pinned revision the path is a GitPath wire identity.
    """
    subject = get_source_session().subject
    if isinstance(subject, GitRevisionSubject):
        return await _git_charts(request, subject)
    return await asyncio.to_thread(_filesystem_charts, request)
