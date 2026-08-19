"""Data hook for the built-in diff plugin.

Mounts ``GET /api/plugin/diff/document?path=<rel>``: parses the patch
file into File Diff Format and returns the hydrated document — the same
shape ``metab --diff`` emits and the conformance corpus validates, so
the browser model never sees a plugin-specific envelope.

Synchronous on purpose: the data-hook dispatcher runs sync sidekicks in
the thread pool, and the parser is a bounded pure function.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.responses import JSONResponse

from metabrowser.diff.adapters.patch_file import MAX_PATCH_BYTES, parse_unified_patch
from metabrowser.diff.format import dump_document
from metabrowser.plugin_api import resolve_path

if TYPE_CHECKING:
    from starlette.requests import Request


def _error(message: str, status: int, *, path: str) -> JSONResponse:
    return JSONResponse(
        {"error": "diff_document", "message": message, "path": path}, status_code=status
    )


def document_handler(request: Request) -> JSONResponse:
    """Parse one patch file into a ChangeSetDocument envelope."""
    subpath = request.query_params.get("path", "")
    target = resolve_path(subpath)
    if target is None or not target.is_file():
        return _error("This file is not available.", 404, path=subpath)
    # One byte past the cap keeps the parser's own truncation reporting
    # authoritative: it sees that the input exceeded the bound and says so
    # in the manifest, rather than this handler inventing a second rule.
    data = target.read_bytes()[: MAX_PATCH_BYTES + 1]
    document = parse_unified_patch(data)
    return JSONResponse(dump_document(document))
