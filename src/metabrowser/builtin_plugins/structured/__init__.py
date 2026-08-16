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
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from starlette.responses import JSONResponse
from strif import file_mtime_hash

from metabrowser.builtin_plugins.structured.parser import parse_structured
from metabrowser.gz_io import ArtifactPath
from metabrowser.http_caching import build_scoped_etag
from metabrowser.paths_safe import _rel_path, _safe_path

if TYPE_CHECKING:
    from starlette.requests import Request

LOG = logging.getLogger(__name__)


def parsed_handler(request: Request) -> JSONResponse:
    """``GET /api/plugin/structured/parsed?path=<rel-path>``.

    Returns the parsed structure plus a canonical YAML
    re-serialization. The client mounts the Tree view from this; the
    Source view goes through ``/api/file`` like every other text kind.
    """
    raw_path = request.query_params.get("path", "")
    target = _safe_path(raw_path)
    if target is None or not target.is_file():
        return JSONResponse({"error": "Not found", "path": raw_path}, status_code=404)

    # ArtifactPath.logical_ext strips supported compression suffixes before
    # the server passes the extension to classifiers.
    artifact = ArtifactPath(target)
    ext = artifact.logical_ext
    if ext not in (".json", ".yaml", ".yml"):
        return JSONResponse(
            {"error": "Unsupported extension", "path": raw_path, "ext": ext},
            status_code=400,
        )

    mtime_hash = file_mtime_hash(target)
    payload = parse_structured(target, ext, mtime_hash)

    rel = _rel_path(target)
    return JSONResponse(
        {
            "type": "structured",
            "path": rel,
            "ext": ext,
            "mtime_hash": mtime_hash,
            "size": target.stat().st_size,
            "parsed": payload.parsed,
            "pretty_yaml": payload.pretty_yaml,
            "node_count": payload.node_count,
            "max_depth": payload.max_depth,
            "comments_supported": False,
            "parse_error": payload.parse_error,
            "truncated": payload.truncated,
        },
        headers={"ETag": build_scoped_etag(mtime_hash)},
    )
