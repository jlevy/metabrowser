"""Check the f1.0 metadata in the guarded SQLite worker."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any, Final

from metabrowser import sqlite_access

# The largest expected stamp is a 36-character UUID, at two bytes per character
# in a UTF-16 database. The informational tool_version only needs a type check.
_STAMP_MAX_BYTES: Final = 72
_SCHEMA_HASH = re.compile(r"[0-9a-f]{16}")
_OWNED_TABLES: Final = (
    ("applied_tx", "tx_id", "applied_at"),
    ("fsqlite_meta", "key", "value"),
)


def _has_owned_table(connection: sqlite3.Connection, name: str, key: str, value: str) -> bool:
    table = connection.execute(f"PRAGMA main.table_list('{name}')").fetchone()
    if table is None or (table[1], table[2]) != (name, "table"):
        return False
    columns = [
        (column, declared.upper(), not_null, primary_key, hidden)
        for _, column, declared, not_null, _, primary_key, hidden in connection.execute(
            f"PRAGMA main.table_xinfo('{name}')"
        )
    ]
    return columns == [(key, "TEXT", 1, 1, 0), (value, "TEXT", 1, 0, 0)]


def _stamp(
    connection: sqlite3.Connection, store_id: str, format_version: str
) -> tuple[int, str | None]:
    application_id = int(connection.execute("PRAGMA main.application_id").fetchone()[0])
    for name, key, value in _OWNED_TABLES:
        if not _has_owned_table(connection, name, key, value):
            return application_id, f"The snapshot is missing a valid {name} table."

    # Binary collation preserves exact stamp names. Fetch bounded values even if a
    # damaged or nonconforming snapshot puts an arbitrary document in a metadata row.
    metadata = dict(
        connection.execute(
            "SELECT key, CASE "
            "WHEN typeof(value) <> 'text' THEN NULL "
            "WHEN key COLLATE BINARY = 'tool_version' THEN '' "
            "WHEN octet_length(value) <= ? THEN value END "
            "FROM main.fsqlite_meta WHERE key COLLATE BINARY IN "
            "('store_id', 'format_version', 'schema_hash', 'tool_version') LIMIT 4",
            (_STAMP_MAX_BYTES,),
        )
    )
    if metadata.get("store_id") != store_id or metadata.get("format_version") != format_version:
        return (
            application_id,
            "The snapshot's store_id or format_version does not match fsqlite.json.",
        )
    schema_hash = metadata.get("schema_hash")
    if not isinstance(schema_hash, str) or _SCHEMA_HASH.fullmatch(schema_hash) is None:
        return application_id, "The snapshot's schema_hash is missing or invalid."
    if metadata.get("tool_version") is None:
        return application_id, "The snapshot's tool_version is missing or invalid."
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
