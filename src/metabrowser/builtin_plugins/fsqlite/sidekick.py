"""The fsqlite plugin's routes: a store's Info and Schema views and its container children.

Each takes a store's marker, ``<store>/fsqlite.json``, or for Info and Schema one of its
tables' addresses, ``<store>/fsqlite.json/<segment>``, and answers for the store.

``GET /api/plugin/fsqlite/info?path=``: the store as a reader sees
it (:mod:`metabrowser.builtin_plugins.fsqlite.store`): its marker, the version
``current`` names and that version's snapshot, the transaction envelopes waiting for
the next reconcile, and the snapshot as a reader process saw it, the same model as
``/api/plugin/sqlite/info`` answers for a database. A store that cannot be read answers
200 with ``error`` naming its state (``invalid``, ``unsupported``, ``corrupt``), since
that is what the view says about it; only a path with nothing readable there is 404.

``GET /api/plugin/fsqlite/schema?path=``: the snapshot's DDL, every object's or one
table's, in the shape ``/api/plugin/sqlite/schema`` answers for a database.

``GET /api/plugin/fsqlite/children?path=``: the store's tables as tree rows, each at
``<marker>/<segment>``, the reserved tables muted as internal
(:func:`metabrowser.builtin_plugins.fsqlite.source.open_store`).

Each reads only: the marker, the pointer, and a directory listing in the server, the
snapshot in a reader process with ``immutable=1``. None takes a read lease nor a lock,
so none writes anything in the store. A store is read on the served folder; a
Git pin answers ``unsupported_for_subject``, since a store's files are resolved beside
its marker by path.
"""

from __future__ import annotations

from typing import Any

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse

from metabrowser.builtin_plugins.fsqlite import source, store
from metabrowser.builtin_plugins.fsqlite.source import StoreFiles
from metabrowser.builtin_plugins.sqlite.database import segment_name
from metabrowser.builtin_plugins.sqlite.sidekick import child_rows, schema_objects
from metabrowser.content_errors import ContentReadError
from metabrowser.source import (
    get_source_session,
    resolve_content,
    resolve_content_container,
    resolve_session_identity,
)
from metabrowser.sqlite_access import SqliteAccessError
from metabrowser.sqlite_readers import request_deadline


def _error(kind: str, path: str, code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(
        {"type": kind, "path": path, "code": code, "error": message}, status_code=status
    )


def _subject_key() -> str:
    session = get_source_session()
    return f"{session.subject.kind}:{session.generation}"


async def _open(
    path: str, kind: str, *, tables: bool = False
) -> tuple[StoreFiles, str] | JSONResponse:
    """The store whose marker *path* names, and with *tables* the table segment it names
    inside the store, "" for none."""
    inner = ""
    try:
        ref = await resolve_content(path)
        if ref is None and tables:
            child = await resolve_content_container(path, suffixes=None)
            if child is not None and child[1] and "/" not in child[1]:
                ref, inner = child
        if ref is None:
            return _error(kind, path, "not_found", "Not found", 404)
        marker = resolve_session_identity(ref.identity)
    except ContentReadError as exc:
        return _error(kind, path, exc.code, str(exc), exc.http_status)
    if marker is None or not marker.is_file() or marker.name != store.MARKER_NAME:
        return _error(kind, path, "not_found", "This is not an fsqlite store's marker.", 404)
    return StoreFiles(ref.identity, marker), inner


def _store_info(found: StoreFiles, path: str, *, deadline: float, subject: str) -> dict[str, Any]:
    payload: dict[str, Any] = {"type": "fsqlite_info", "path": path, "generation": None}
    described: dict[str, Any] = {}
    payload["store"] = described
    try:
        marker = store.read_marker(found.marker)
    except store.StoreError as exc:
        payload["error"] = {"state": exc.state, "message": str(exc)}
        return payload
    described |= {
        "format_version": marker.format_version,
        "store_id": marker.store_id,
        "required_features": list(marker.required_features),
    }
    pending = store.count_pending(found.locate(store.PENDING_DIR))
    described["pending"] = {
        "committed": pending.committed,
        "uncommitted": pending.uncommitted,
        "complete": pending.complete,
    }
    current = found.locate(store.CURRENT_NAME)
    tried: list[store.Snapshot] = []

    def read(snapshot: store.Snapshot) -> dict[str, Any]:
        tried.append(snapshot)
        database = source.snapshot_database(found, snapshot, subject=subject)
        source.validate_snapshot(database, marker, deadline=deadline)
        result: dict[str, Any] = database.call("info", {}, deadline=deadline)
        return result

    snapshot_payload: dict[str, Any] | None = None
    try:
        snapshot_payload, snapshot = store.read_snapshot(current, found.snapshot, read)
    except store.StoreError as exc:
        payload["error"] = {"state": exc.state, "message": str(exc)}
        return payload
    except SqliteAccessError as exc:
        # The pointer named a snapshot the reader could not read: the store section still
        # says which, and the snapshot section shows the reader's state.
        snapshot = tried[-1]
        payload["snapshot"] = {"error": {"state": exc.state, "message": str(exc)}}
    except OSError as exc:
        payload["error"] = {
            "state": "invalid",
            "message": f"The store cannot be read: {exc.strerror or exc}",
        }
        return payload
    described |= {
        "version": snapshot.version,
        "snapshot": snapshot.name,
        "attempts": snapshot.attempts,
    }
    if current is not None:
        try:
            payload["generation"] = store.store_generation(found.marker, current, snapshot.version)
        except OSError:
            payload["generation"] = None
    if snapshot_payload is not None:
        payload["snapshot"] = snapshot_payload
    return payload


async def info_handler(request: Request) -> JSONResponse:
    """``GET /api/plugin/fsqlite/info?path=``: the Info view's model."""
    path = request.query_params.get("path", "")
    deadline = request_deadline()
    opened = await _open(path, "fsqlite_error", tables=True)
    if isinstance(opened, JSONResponse):
        return opened
    subject = _subject_key()
    payload = await run_in_threadpool(
        _store_info, opened[0], path, deadline=deadline, subject=subject
    )
    return JSONResponse(payload)


def _store_schema(
    found: StoreFiles, path: str, name: str | None, *, deadline: float, subject: str
) -> dict[str, Any] | None:
    """The Schema view's model, or None when the table *name* is not in the snapshot."""
    payload: dict[str, Any] = {"type": "fsqlite_schema", "path": path, "generation": None}
    try:
        marker = store.read_marker(found.marker)

        def read(snapshot: store.Snapshot) -> tuple[dict[str, Any], str]:
            database = source.snapshot_database(found, snapshot, subject=subject)
            source.validate_snapshot(database, marker, deadline=deadline)
            answer: dict[str, Any] = database.call("sqlite_ddl", {"table": name}, deadline=deadline)
            return answer, database.generation

        (answer, generation), _snapshot = store.read_snapshot(
            found.locate(store.CURRENT_NAME), found.snapshot, read
        )
    except (store.StoreError, SqliteAccessError) as exc:
        payload["error"] = {"state": exc.state, "message": str(exc)}
        return payload
    except OSError as exc:
        payload["error"] = {
            "state": "invalid",
            "message": f"The store cannot be read: {exc.strerror}",
        }
        return payload
    if name is not None and not answer["objects"]:
        return None
    payload["generation"] = generation
    return payload | schema_objects(answer)


async def schema_handler(request: Request) -> JSONResponse:
    """``GET /api/plugin/fsqlite/schema?path=``: the Schema view's model, for the whole
    snapshot or the one table its address names."""
    path = request.query_params.get("path", "")
    deadline = request_deadline()
    opened = await _open(path, "fsqlite_error", tables=True)
    if isinstance(opened, JSONResponse):
        return opened
    found, inner = opened
    name: str | None = None
    if inner:
        name = segment_name(inner)
        if name is None:
            return _error(
                "fsqlite_error", path, "table_not_found", f"no table {inner!r} in this store", 404
            )
    subject = _subject_key()
    payload = await run_in_threadpool(
        _store_schema, found, path, name, deadline=deadline, subject=subject
    )
    if payload is None:
        return _error(
            "fsqlite_error", path, "table_not_found", f"no table {inner!r} in this store", 404
        )
    return JSONResponse({**payload, "table": inner or None})


def _store_children(found: StoreFiles, *, deadline: float, subject: str) -> dict[str, Any]:
    try:
        opened = source.open_store(found, deadline=deadline, subject=subject)
    except (store.StoreError, SqliteAccessError) as exc:
        state = exc.state
        return {"children": [], "error": {"state": state, "message": str(exc)}}
    except OSError as exc:
        return {
            "children": [],
            "error": {
                "state": "invalid",
                "message": f"fsqlite.json cannot be read: {exc.strerror}",
            },
        }
    return {
        "children": child_rows(found.identity, opened.tables),
        "version": opened.snapshot.version,
        "snapshot": opened.snapshot.name,
    }


async def children_handler(request: Request) -> JSONResponse:
    """``GET /api/plugin/fsqlite/children?path=``: the store's tables as tree rows.

    A store that cannot be read has no children and says why, rather than failing the
    tree row, as a ``.db`` file that is not SQLite expands to nothing.
    """
    path = request.query_params.get("path", "")
    deadline = request_deadline()
    opened = await _open(path, "fsqlite_children")
    if isinstance(opened, JSONResponse):
        return opened
    subject = _subject_key()
    payload = await run_in_threadpool(
        _store_children, opened[0], deadline=deadline, subject=subject
    )
    return JSONResponse(payload)
