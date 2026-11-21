"""The SQLite plugin's routes: a database's Info view, its Schema view, and its tables as
container children.

- ``GET /api/plugin/sqlite/info?path=``: what a reader process saw through
  :mod:`metabrowser.sqlite_access`: the database as its connection reads it (pragmas,
  since the main file's header is stale while a log holds frames), its sidecars, how it
  was opened and why, and the SQLite library against the reader's minimum.
- ``GET /api/plugin/sqlite/schema?path=``: every object's DDL, indexes, triggers, and
  foreign keys, or one table's at a table's address.
- ``GET /api/plugin/sqlite/children?path=``: the tree's rows for a database's tables,
  views, and virtual tables, each at its address ``<database>/<segment>``
  (:mod:`~metabrowser.builtin_plugins.sqlite.database`); internal tables are muted. A
  file the kind's extensions name that is not a database has none.

Every route takes a database's path or a table's address inside it, and answers for the
database. A database that could not be read answers 200 with ``error``, naming the state
it is shown as (``writer_busy``, ``changing``, ``damaged``, and the rest of
:data:`metabrowser.sqlite_access.ERROR_STATES`), since that is what the view says about
the file; only a path with nothing readable there is 404.

On a served folder the reader opens the file's real path. On a Git pin the blob is
written once to a private file named by its object id, under
:data:`~metabrowser.sqlite_readers.BLOB_MAX_BYTES`, and read with ``immutable=1``: a
committed write-ahead-log database is shown without its log. A blob already written is
not read from Git again.
"""

from __future__ import annotations

import asyncio
from typing import Any

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse

from metabrowser.builtin_plugins.sqlite.database import (
    Database,
    blob_too_large,
    cached,
    pinned_database,
    segment_name,
    served_database,
    subject_key,
    table_segment,
    written_pinned_database,
)
from metabrowser.content_errors import ContentReadError
from metabrowser.source import (
    ContentRef,
    get_source_session,
    read_content_window,
    resolve_content,
    resolve_content_container,
    resolve_session_identity,
)
from metabrowser.sqlite_access import SqliteAccessError
from metabrowser.sqlite_readers import BLOB_MAX_BYTES, request_deadline


def _error(path: str, code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(
        {"type": "sqlite_error", "path": path, "code": code, "error": message}, status_code=status
    )


async def _resolve(path: str) -> tuple[ContentRef, str] | JSONResponse:
    """The database at *path* and the table segment it names inside it, "" for none."""
    try:
        ref = await resolve_content(path)
        inner = ""
        if ref is None:
            child = await resolve_content_container(path, suffixes=None)
            if child is None or not child[1] or "/" in child[1]:
                return _error(path, "not_found", "Not found", 404)
            ref, inner = child
    except ContentReadError as exc:
        return _error(path, exc.code, str(exc), exc.http_status)
    return ref, inner


async def _database(ref: ContentRef) -> Database | None:
    """The database *ref* names, or None when its file is gone. Raises
    :class:`SqliteAccessError` for a blob too large to read from a revision."""
    subject = subject_key()
    if get_source_session().subject.filesystem_root is not None:
        target = resolve_session_identity(ref.identity)
        if target is None or not target.is_file():
            return None
        real = await asyncio.to_thread(target.resolve)
        try:
            return await asyncio.to_thread(served_database, real, subject)
        except OSError:
            return None
    if ref.stored_size is not None and ref.stored_size > BLOB_MAX_BYTES:
        raise blob_too_large(BLOB_MAX_BYTES)
    written = await run_in_threadpool(written_pinned_database, ref, subject)
    if written is not None:
        return written
    window = await read_content_window(ref, max_bytes=BLOB_MAX_BYTES + 1)
    if len(window.data) > BLOB_MAX_BYTES:
        raise blob_too_large(BLOB_MAX_BYTES)
    return await run_in_threadpool(pinned_database, ref, window.data, subject)


async def info_handler(request: Request) -> JSONResponse:
    """``GET /api/plugin/sqlite/info?path=``: the Info view's model."""
    path = request.query_params.get("path", "")
    deadline = request_deadline()
    resolved = await _resolve(path)
    if isinstance(resolved, JSONResponse):
        return resolved
    ref, _inner = resolved
    payload: dict[str, Any] = {"type": "sqlite_info", "path": path}
    try:
        database = await _database(ref)
        if database is None:
            return _error(path, "not_found", "Not found", 404)
        payload["generation"] = database.generation
        payload |= await run_in_threadpool(database.call, "info", {}, deadline=deadline)
    except SqliteAccessError as exc:
        payload.setdefault("generation", None)
        payload["error"] = {"state": exc.state, "message": str(exc)}
    return JSONResponse(payload)


async def schema_handler(request: Request) -> JSONResponse:
    """``GET /api/plugin/sqlite/schema?path=``: the Schema view's model, for the whole
    database or the one table its address names."""
    path = request.query_params.get("path", "")
    deadline = request_deadline()
    resolved = await _resolve(path)
    if isinstance(resolved, JSONResponse):
        return resolved
    ref, inner = resolved
    name: str | None = None
    if inner:
        name = segment_name(inner)
        if name is None:
            return _error(path, "table_not_found", f"no table {inner!r} in this database", 404)
    payload: dict[str, Any] = {"type": "sqlite_schema", "path": path, "table": inner or None}
    try:
        database = await _database(ref)
        if database is None:
            return _error(path, "not_found", "Not found", 404)
        payload["generation"] = database.generation
        answer = await run_in_threadpool(
            database.call, "sqlite_ddl", {"table": name}, deadline=deadline
        )
    except SqliteAccessError as exc:
        payload.setdefault("generation", None)
        payload["error"] = {"state": exc.state, "message": str(exc)}
        return JSONResponse(payload)
    if name is not None and not answer["objects"]:
        return _error(path, "table_not_found", f"no table {inner!r} in this database", 404)
    payload["objects"] = [
        {**entry, "segment": table_segment(entry["table"]) if entry["table"] else None}
        for entry in answer["objects"]
    ]
    payload["foreign_keys"] = [
        {
            "table": table,
            "fields": item["from"],
            "references": item["table"],
            "to": item["to"],
        }
        for table, items in answer["foreign_keys"].items()
        for item in items
    ]
    return JSONResponse(payload)


_BADGES = {"views": "V", "virtual": "VT"}


async def children_handler(request: Request) -> JSONResponse:
    """``GET /api/plugin/sqlite/children?path=``: a database's tables as tree rows."""
    path = request.query_params.get("path", "")
    deadline = request_deadline()
    try:
        ref = await resolve_content(path)
    except ContentReadError as exc:
        return _error(path, exc.code, str(exc), exc.http_status)
    if ref is None:
        # A listing is asked of the database itself, never of one of its tables.
        return _error(path, "not_found", "Not found", 404)
    try:
        database = await _database(ref)
        if database is None:
            return _error(path, "not_found", "Not found", 404)
        catalog = await run_in_threadpool(cached, database, "catalog", "", deadline=deadline)
    except SqliteAccessError as exc:
        if exc.state == "not_sqlite":
            # A `.db` file that is not SQLite has the chevron its extension gives it, and
            # nothing under it.
            return JSONResponse({"children": []})
        return JSONResponse({"children": [], "error": {"state": exc.state, "message": str(exc)}})
    children: list[dict[str, Any]] = []
    for item in catalog["objects"]:
        entry: dict[str, Any] = {
            "name": item["name"],
            "path": f"{ref.identity}/{table_segment(str(item['name']))}",
        }
        badge = _BADGES.get(item["group"])
        if badge is not None:
            entry["badge"] = badge
        if item["group"] == "internal":
            entry["muted"] = True
        children.append(entry)
    return JSONResponse({"children": children})
