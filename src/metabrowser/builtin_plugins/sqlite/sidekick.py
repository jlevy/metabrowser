"""``GET /api/plugin/sqlite/info?path=``: a SQLite database's Info view.

The answer is what a reader process saw through :mod:`metabrowser.sqlite_access`: the
database as its connection reads it (pragmas, since the main file's header is stale
while a log holds frames), its sidecars, how it was opened and why, and the SQLite
library against the reader's minimum. A database that could not be read answers 200 with
``error``, naming the state it is shown as (``writer_busy``, ``changing``, ``damaged``,
and the rest of :data:`metabrowser.sqlite_access.ERROR_STATES`), since that is what the
view says about the file; only a path with nothing readable there is 404.

On a served folder the reader opens the file's real path. On a Git pin the blob is
written once to a private file named by its object id, under
:data:`~metabrowser.sqlite_readers.BLOB_MAX_BYTES`, and read with ``immutable=1``: a
committed write-ahead-log database is shown without its log. A blob already written is
not read from Git again.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse

from metabrowser.content_errors import ContentReadError
from metabrowser.source import (
    ContentRef,
    get_source_session,
    read_content_window,
    resolve_content,
    resolve_session_identity,
)
from metabrowser.sqlite_access import SqliteAccessError, sqlite_generation
from metabrowser.sqlite_readers import BLOB_MAX_BYTES, reader_pool, request_deadline


def _error(path: str, code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(
        {"type": "sqlite_error", "path": path, "code": code, "error": message}, status_code=status
    )


def _subject_key() -> str:
    session = get_source_session()
    return f"{session.subject.kind}:{session.generation}"


async def _blob_file(ref: ContentRef) -> Path:
    """The pinned blob *ref* as a private file, written once and read from Git only when
    it is not written yet."""
    pool = reader_pool()
    written = await run_in_threadpool(pool.written_blob, ref.fingerprint)
    if written is not None:
        return written
    if ref.stored_size is not None and ref.stored_size > BLOB_MAX_BYTES:
        raise SqliteAccessError(
            "unreadable",
            f"This database is larger than the {BLOB_MAX_BYTES:,} bytes read from a revision.",
        )
    window = await read_content_window(ref, max_bytes=BLOB_MAX_BYTES + 1)
    if len(window.data) > BLOB_MAX_BYTES:
        raise SqliteAccessError(
            "unreadable",
            f"This database is larger than the {BLOB_MAX_BYTES:,} bytes read from a revision.",
        )
    return await run_in_threadpool(pool.blob, ref.fingerprint, lambda: window.data)


def _info(path: Path, *, deadline: float, subject: str, immutable: bool) -> dict[str, Any]:
    pool = reader_pool()
    with pool.scratch() as scratch:
        result: dict[str, Any] = pool.call(
            "info",
            {"path": str(path), "scratch": str(scratch), "immutable_content": immutable},
            deadline=deadline,
            subject=subject,
        )
    return result


async def info_handler(request: Request) -> JSONResponse:
    """``GET /api/plugin/sqlite/info?path=``: the Info view's model."""
    path = request.query_params.get("path", "")
    deadline = request_deadline()
    try:
        ref = await resolve_content(path)
    except ContentReadError as exc:
        return _error(path, exc.code, str(exc), exc.http_status)
    if ref is None:
        return _error(path, "not_found", "Not found", 404)
    subject = _subject_key()
    filesystem = get_source_session().subject.filesystem_root is not None
    payload: dict[str, Any] = {"type": "sqlite_info", "path": path}
    try:
        if filesystem:
            target = resolve_session_identity(ref.identity)
            if target is None or not target.is_file():
                return _error(path, "not_found", "Not found", 404)
            real = await asyncio.to_thread(target.resolve)
            try:
                payload["generation"] = await asyncio.to_thread(sqlite_generation, real)
            except OSError:
                payload["generation"] = None
            immutable = False
        else:
            real = await _blob_file(ref)
            payload["generation"] = ref.fingerprint
            immutable = True
        payload |= await run_in_threadpool(
            _info, real, deadline=deadline, subject=subject, immutable=immutable
        )
    except SqliteAccessError as exc:
        payload.setdefault("generation", None)
        payload["error"] = {"state": exc.state, "message": str(exc)}
    return JSONResponse(payload)
