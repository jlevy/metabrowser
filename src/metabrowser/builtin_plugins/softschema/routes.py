"""Collection discovery and index progress for a folder's Table tab."""

from __future__ import annotations

from typing import Any

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse

from metabrowser.content_errors import ContentReadError, content_error_wire
from metabrowser.plugin_api import (
    FolderTableHandle,
    resolve_directory,
    served_root,
)

from .offer import offers_collection
from .source import CollectionSource


def _collection(path: str, *, wait: bool) -> dict[str, Any] | None:
    folder = resolve_directory(path)
    if folder is None or not offers_collection(folder):
        return None
    source = CollectionSource(FolderTableHandle(path, folder, served_root(), wait))
    version = source.version
    snapshot = version.snapshot
    return {
        "type": "softschema_collection",
        "path": path,
        "root": source.root.relative_to(source.index.served_root).as_posix()
        if source.root != source.index.served_root
        else "",
        "generation": version.generation,
        "state": "failed" if version.failed else "indexing" if version.indexing else "ready",
        "paths_checked": version.paths_checked,
        "cache_available": version.cache_available,
        "complete": snapshot.complete if snapshot is not None else False,
        "tables": [
            {"id": item.id, "label": item.label, "count": item.estimate} for item in source.tables()
        ],
        "summary": snapshot.summary() if snapshot is not None else None,
    }


async def collection_handler(request: Request) -> JSONResponse:
    path = request.query_params.get("path", "")
    try:
        output = await run_in_threadpool(
            _collection, path, wait=request.query_params.get("wait") == "1"
        )
    except ContentReadError as error:
        return JSONResponse(content_error_wire(error), status_code=error.http_status)
    if output is None:
        return JSONResponse({"code": "collection_not_found"}, status_code=404)
    return JSONResponse(output)
