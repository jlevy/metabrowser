"""Where an fsqlite store's tables come from: the SQLite source, over its snapshot.

A store is a thin source over the SQLite adapter (the plan's "fsqlite stores"): its
tables are the tables of the snapshot ``current`` names, read with
``immutable_content``, under the store's own generation
(:func:`~metabrowser.builtin_plugins.fsqlite.store.store_generation`), with the format's
reserved tables grouped as internal (:func:`group_reserved`). Each table is
``<marker>/<segment>``, the segment as the SQLite plugin escapes a table's name
(:func:`~metabrowser.builtin_plugins.sqlite.database.table_segment`), so the store's
tables are addressed as a database's are, with its marker standing for the database.

The store's routes and adapter verify the snapshot's f1.0 identity. Each request fixes
its snapshot version at the first successful open. If garbage collection removes the
snapshot before the initial read finishes, the reader follows the pointer once more.
If a later table operation needs the collected file, it reports a moved snapshot so
the caller can retry the whole request.
"""

from __future__ import annotations

import dataclasses
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from metabrowser.builtin_plugins.fsqlite.store import (
    CURRENT_NAME,
    RESERVED_TABLES,
    SNAPSHOTS_DIR,
    Marker,
    Snapshot,
    SnapshotGone,
    StoreError,
    check_application_id,
    read_marker,
    read_snapshot,
    store_generation,
)
from metabrowser.builtin_plugins.sqlite.database import Database, cached, subject_key
from metabrowser.builtin_plugins.sqlite.source import SqliteSource, catalog_tables
from metabrowser.capabilities import capabilities_for
from metabrowser.plugin_api import TableHandle, TableInfo
from metabrowser.source import resolve_session_identity
from metabrowser.sqlite_access import JOURNAL_HEADER_BYTES, SqliteAccessError, _read_head
from metabrowser.sqlite_readers import register_worker_module, request_deadline

register_worker_module(
    "metabrowser.builtin_plugins.fsqlite.reader", Path(__file__).with_name("reader.py")
)


class StoreFiles:
    """One store's files, each resolved by identity through the served folder's gate.

    *identity* is the marker's. On a Git pin resolving any of them raises
    :class:`~metabrowser.source.UnsupportedSourceCapabilityError`: a store's files are
    found beside its marker by path, which a pin's identities do not offer.
    """

    def __init__(self, identity: str, marker: Path) -> None:
        self.identity = identity
        self.marker = marker
        self._prefix = identity.rpartition("/")[0]

    @classmethod
    def at(cls, identity: str) -> StoreFiles:
        """The store whose marker has *identity*. Raises ``FileNotFoundError`` when no
        file is there."""
        marker = resolve_session_identity(identity)
        if marker is None or not marker.is_file():
            raise FileNotFoundError(identity)
        return cls(identity, marker)

    def locate(self, name: str) -> Path | None:
        """The store file *name* (``current``, ``tx/pending``) names, or None."""
        identity = f"{self._prefix}/{name}" if self._prefix else name
        return resolve_session_identity(identity)

    def snapshot(self, name: str) -> Path | None:
        directory = self.locate(SNAPSHOTS_DIR)
        if directory is None:
            return None
        expected = directory / name
        resolved = self.locate(f"{SNAPSHOTS_DIR}/{name}")
        if expected.is_symlink() or (resolved is not None and resolved != expected):
            raise StoreError("corrupt", "The current pointer names a linked snapshot file.")
        return resolved


class SnapshotDatabase(Database):
    """An immutable snapshot whose disappearance can invalidate any worker call."""

    __slots__ = ()

    def _require_snapshot_layout(self) -> None:
        if self.file.is_symlink():
            raise StoreError("corrupt", "The current pointer names a linked snapshot file.")
        for suffix in ("-wal", "-shm"):
            sidecar = self.file.with_name(self.file.name + suffix)
            if os.path.lexists(sidecar):
                raise StoreError(
                    "corrupt", f"The published snapshot has a SQLite {suffix} side file."
                )
        journal = self.file.with_name(self.file.name + "-journal")
        try:
            live = any(_read_head(journal, JOURNAL_HEADER_BYTES))
        except FileNotFoundError:
            return
        except OSError as exc:
            raise StoreError(
                "corrupt", "The published snapshot's SQLite journal is unreadable."
            ) from exc
        if live:
            raise StoreError(
                "corrupt", "The published snapshot has a live SQLite -journal side file."
            )

    def call(self, op: str, args: dict[str, Any], *, deadline: float) -> Any:
        self._require_snapshot_layout()
        try:
            result = super().call(op, args, deadline=deadline)
        except SqliteAccessError as exc:
            if exc.state == "unreadable":
                try:
                    self.file.lstat()
                except FileNotFoundError:
                    raise SnapshotGone() from exc
                except OSError:
                    pass
            raise
        self._require_snapshot_layout()
        return result


def group_reserved(tables: Iterable[TableInfo]) -> list[TableInfo]:
    """*tables* with the format's reserved tables (:data:`RESERVED_TABLES`) grouped as
    ``internal``, as the plan's "What it shows" lists them for an fsqlite snapshot."""
    return [
        dataclasses.replace(table, group="internal") if table.id in RESERVED_TABLES else table
        for table in tables
    ]


def snapshot_database(files: StoreFiles, snapshot: Snapshot, *, subject: str) -> Database:
    """*snapshot* as the SQLite source reads it: with ``immutable_content``, since a
    published snapshot never changes, under the store's generation. Raises ``OSError``
    when the marker or the pointer is gone."""
    current = files.locate(CURRENT_NAME)
    if current is None:
        raise FileNotFoundError(CURRENT_NAME)
    return SnapshotDatabase(
        file=snapshot.path,
        immutable=True,
        subject=subject,
        generation=store_generation(files.marker, current, snapshot.version),
        virtual_ok=capabilities_for(pinned_revision=False).active_content,
    )


def validate_snapshot(database: Database, marker: Marker, *, deadline: float) -> None:
    """Require the f1.0 application ID, reserved tables, and metadata (M4, S2–S3)."""
    application_id, error = database.call(
        "fsqlite_identity",
        {"store_id": marker.store_id, "format_version": marker.format_version},
        deadline=deadline,
    )
    check_application_id(application_id)
    if error is not None:
        raise StoreError("corrupt", error)


@dataclasses.dataclass(frozen=True, slots=True)
class OpenedStore:
    """A store's snapshot as one request reads it, and its tables."""

    database: Database
    snapshot: Snapshot
    tables: tuple[TableInfo, ...]


def open_store(files: StoreFiles, *, deadline: float, subject: str) -> OpenedStore:
    """Read the marker and the pointer, and list the tables of the snapshot it names.

    Raises :class:`~metabrowser.builtin_plugins.fsqlite.store.StoreError` for a store
    that cannot be read, :class:`~metabrowser.sqlite_access.SqliteAccessError` for a
    snapshot a reader refused, and ``OSError`` if the generation cannot be obtained.
    """
    marker = read_marker(files.marker)

    def read(snapshot: Snapshot) -> tuple[Database, tuple[TableInfo, ...]]:
        database = snapshot_database(files, snapshot, subject=subject)
        validate_snapshot(database, marker, deadline=deadline)
        catalog = cached(database, "catalog", "", deadline=deadline)
        return database, tuple(group_reserved(catalog_tables(catalog)))

    (database, tables), snapshot = read_snapshot(files.locate(CURRENT_NAME), files.snapshot, read)
    return OpenedStore(database, snapshot, tables)


class StoreSource(SqliteSource):
    """A store's tables: the SQLite source over its snapshot, the reserved tables
    grouped as internal."""

    def tables(self) -> tuple[TableInfo, ...]:
        return tuple(group_reserved(super().tables()))


def adapter(handle: TableHandle) -> StoreSource:
    """The ``[[table_source]]`` adapter for the ``sqlite-store`` kind: *handle* names the
    store's marker, and every table is read from the snapshot ``current`` names."""
    subject = subject_key()

    def opener() -> Database:
        files = StoreFiles.at(handle.ref.identity)
        return open_store(files, deadline=request_deadline(), subject=subject).database

    return StoreSource(handle, opener)
