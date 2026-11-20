"""The fsqlite plugin's routes: a store's Info view and its container children.

``GET /api/plugin/fsqlite/info?path=<store>/fsqlite.json``: the store as a reader sees
it (:mod:`metabrowser.builtin_plugins.fsqlite.store`): its marker, the version
``current`` names and that version's snapshot, the transaction envelopes waiting for
the next reconcile, and the snapshot as a reader process saw it, the same model as
``/api/plugin/sqlite/info`` answers for a database. A store that cannot be read answers
200 with ``error`` naming its state (``invalid``, ``unsupported``, ``corrupt``), since
that is what the view says about it; only a path with nothing readable there is 404.

``GET /api/plugin/fsqlite/children?path=<store>/fsqlite.json``: the store's tables as
tree rows, through :func:`metabrowser.builtin_plugins.fsqlite.source.snapshot_children`.

Both read only: the marker, the pointer, and a directory listing in the server, the
snapshot in a reader process with ``immutable=1``. Neither takes a read lease nor a
lock, so neither writes anything in the store. A store is read on the served folder; a
Git pin answers ``unsupported_for_subject``, since a store's files are resolved beside
its marker by path.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse

from metabrowser.builtin_plugins.fsqlite import source, store
from metabrowser.content_errors import ContentReadError
from metabrowser.source import get_source_session, resolve_content, resolve_session_identity
from metabrowser.sqlite_access import SqliteAccessError
from metabrowser.sqlite_readers import reader_pool, request_deadline


def _error(kind: str, path: str, code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(
        {"type": kind, "path": path, "code": code, "error": message}, status_code=status
    )


def _subject_key() -> str:
    session = get_source_session()
    return f"{session.subject.kind}:{session.generation}"


class _Store:
    """One store's files, each resolved by identity through the served folder's gate."""

    def __init__(self, identity: str, marker: Path) -> None:
        self.marker = marker
        self._prefix = identity.rpartition("/")[0]

    def locate(self, name: str) -> Path | None:
        """The store file *name* (``current``, ``tx/pending``) names, or None."""
        identity = f"{self._prefix}/{name}" if self._prefix else name
        return resolve_session_identity(identity)

    def snapshot(self, name: str) -> Path | None:
        return self.locate(f"{store.SNAPSHOTS_DIR}/{name}")


async def _open(path: str, kind: str) -> _Store | JSONResponse:
    try:
        ref = await resolve_content(path)
        if ref is None:
            return _error(kind, path, "not_found", "Not found", 404)
        marker = resolve_session_identity(ref.identity)
    except ContentReadError as exc:
        return _error(kind, path, exc.code, str(exc), exc.http_status)
    if marker is None or not marker.is_file() or marker.name != store.MARKER_NAME:
        return _error(kind, path, "not_found", "This is not an fsqlite store's marker.", 404)
    return _Store(ref.identity, marker)


def _gone_or(exc: SqliteAccessError, snapshot: store.Snapshot) -> Exception:
    """A reader's failure on *snapshot*: :class:`~store.SnapshotGone` when the file is no
    longer there, which sends the read back to the pointer, or the failure itself."""
    if exc.state == "unreadable" and not os.path.lexists(snapshot.path):
        return store.SnapshotGone()
    return exc


def _snapshot_info(snapshot: store.Snapshot, *, deadline: float, subject: str) -> dict[str, Any]:
    pool = reader_pool()
    with pool.scratch() as scratch:
        try:
            result: dict[str, Any] = pool.call(
                "info",
                {"path": str(snapshot.path), "scratch": str(scratch), "immutable_content": True},
                deadline=deadline,
                subject=subject,
            )
        except SqliteAccessError as exc:
            raise _gone_or(exc, snapshot) from exc
    return result


def _store_info(found: _Store, path: str, *, deadline: float, subject: str) -> dict[str, Any]:
    payload: dict[str, Any] = {"type": "fsqlite_info", "path": path, "generation": None}
    described: dict[str, Any] = {}
    payload["store"] = described
    try:
        marker = store.read_marker(found.marker)
    except store.StoreError as exc:
        payload["error"] = {"state": exc.state, "message": str(exc)}
        return payload
    except OSError as exc:
        payload["error"] = {
            "state": "invalid",
            "message": f"fsqlite.json cannot be read: {exc.strerror}",
        }
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
        return _snapshot_info(snapshot, deadline=deadline, subject=subject)

    try:
        snapshot_payload, snapshot = store.read_snapshot(current, found.snapshot, read)
    except store.StoreError as exc:
        payload["error"] = {"state": exc.state, "message": str(exc)}
        return payload
    except SqliteAccessError as exc:
        # The pointer named a snapshot the reader could not read: the store section still
        # says which, and the snapshot section shows the reader's state.
        last = tried[-1]
        described |= {"version": last.version, "snapshot": last.name, "attempts": last.attempts}
        payload["snapshot"] = {"error": {"state": exc.state, "message": str(exc)}}
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
    payload["snapshot"] = snapshot_payload
    try:
        store.check_application_id(int(snapshot_payload["database"]["application_id"]))
    except store.StoreError as exc:
        payload["error"] = {"state": exc.state, "message": str(exc)}
    return payload


async def info_handler(request: Request) -> JSONResponse:
    """``GET /api/plugin/fsqlite/info?path=``: the Info view's model."""
    path = request.query_params.get("path", "")
    deadline = request_deadline()
    found = await _open(path, "fsqlite_error")
    if isinstance(found, JSONResponse):
        return found
    subject = _subject_key()
    payload = await run_in_threadpool(_store_info, found, path, deadline=deadline, subject=subject)
    return JSONResponse(payload)


def _store_children(found: _Store, path: str, *, deadline: float, subject: str) -> dict[str, Any]:
    try:
        store.read_marker(found.marker)
        current = found.locate(store.CURRENT_NAME)

        def read(snapshot: store.Snapshot) -> list[dict[str, Any]]:
            return source.snapshot_children(path, snapshot, deadline=deadline, subject=subject)

        children, snapshot = store.read_snapshot(current, found.snapshot, read)
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
    return {"children": children, "version": snapshot.version, "snapshot": snapshot.name}


async def children_handler(request: Request) -> JSONResponse:
    """``GET /api/plugin/fsqlite/children?path=``: the store's tables as tree rows.

    A store that cannot be read has no children and says why, rather than failing the
    tree row, as a ``.db`` file that is not SQLite expands to nothing.
    """
    path = request.query_params.get("path", "")
    deadline = request_deadline()
    found = await _open(path, "fsqlite_children")
    if isinstance(found, JSONResponse):
        return found
    subject = _subject_key()
    payload = await run_in_threadpool(
        _store_children, found, path, deadline=deadline, subject=subject
    )
    return JSONResponse(payload)
