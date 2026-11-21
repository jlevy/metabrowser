"""Read the f1.0 identity stamp in the guarded SQLite worker."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from metabrowser import sqlite_access


def _stamp(
    connection: sqlite3.Connection, store_id: str, format_version: str
) -> tuple[int, str | None]:
    application_id = int(connection.execute("PRAGMA main.application_id").fetchone()[0])
    table = connection.execute("PRAGMA main.table_list('fsqlite_meta')").fetchone()
    if table is None or (table[1], table[2]) != ("fsqlite_meta", "table"):
        return application_id, "The snapshot has no fsqlite_meta table."
    columns = {
        name
        for _, name, _, _, _, _, hidden in connection.execute(
            "PRAGMA main.table_xinfo('fsqlite_meta')"
        )
        if not hidden
    }
    if columns != {"key", "value"}:
        return application_id, "The snapshot's fsqlite_meta table has invalid columns."

    # Compare inside the worker without fetching arbitrary metadata values. Require one
    # row per key and compare with binary collation even if the table declares another.
    rows = connection.execute(
        "SELECT key, typeof(value) = 'text' AND value COLLATE BINARY = "
        "CASE key COLLATE BINARY WHEN 'store_id' THEN ? ELSE ? END "
        "FROM main.fsqlite_meta WHERE key COLLATE BINARY IN ('store_id', 'format_version') LIMIT 3",
        (store_id, format_version),
    ).fetchall()
    if len(rows) != 2 or set(rows) != {("format_version", 1), ("store_id", 1)}:
        return (
            application_id,
            "The snapshot's store_id or format_version does not match fsqlite.json.",
        )
    return application_id, None


def _identity_op(args: dict[str, Any], deadline: float) -> tuple[int, str | None]:
    value, _ = sqlite_access.read(
        Path(str(args["path"])),
        lambda connection: _stamp(connection, str(args["store_id"]), str(args["format_version"])),
        deadline=deadline,
        scratch=Path(str(args["scratch"])),
        immutable_content=True,
    )
    return value


sqlite_access.OPS["fsqlite_identity"] = _identity_op
