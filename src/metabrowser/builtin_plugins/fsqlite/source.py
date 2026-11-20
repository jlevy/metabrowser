"""Where an fsqlite store's tables come from: the SQLite source, over its snapshot.

A store is a thin source over the SQLite adapter (the plan's "fsqlite stores"): its
tables are the tables of the snapshot ``current`` names, read with
``immutable_content``, under the store's own generation, with the format's reserved
tables grouped as internal. This module is the one place the store meets that adapter,
so the store's container hook and, once declared, its ``[[table_source]]`` both go
through it.

The SQLite source (the plan's "SQLite Tables") is not part of this layer yet. Until it is,
:func:`snapshot_children` answers no tables, and the store is a container whose
children hook has its full shape (``{children: [{name, path}]}``, store errors, the
retry when garbage collection removes a snapshot) and an empty list. Plugging the
adapter in replaces that function's body with the adapter's ``tables()`` over
*snapshot*, passed through :func:`group_reserved`, each table named by its segment
under the store's marker path, and adds ``[[table_source]] kind = "sqlite-store"`` to
this plugin's manifest, with ``requires`` gaining ``table``.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable
from typing import Any

from metabrowser.builtin_plugins.fsqlite.store import RESERVED_TABLES, Snapshot
from metabrowser.table_source import TableInfo


def group_reserved(tables: Iterable[TableInfo]) -> list[TableInfo]:
    """*tables* with the format's reserved tables (:data:`RESERVED_TABLES`) grouped as
    ``internal``, as the plan's "What it shows" lists them for an fsqlite snapshot."""
    return [
        dataclasses.replace(table, group="internal") if table.id in RESERVED_TABLES else table
        for table in tables
    ]


def snapshot_children(
    path: str, snapshot: Snapshot, *, deadline: float, subject: str
) -> list[dict[str, Any]]:
    """The children rows of the store whose marker is at *path*: one per table of
    *snapshot*, ``{name, path}``, names only.

    The seam where the SQLite source plugs in (see the module docstring): it raises
    :class:`~metabrowser.builtin_plugins.fsqlite.store.SnapshotGone` when the snapshot
    disappeared before it was opened, and :class:`~metabrowser.sqlite_access.SqliteAccessError`
    for a snapshot it could not read.
    """
    del path, snapshot, deadline, subject
    return []
