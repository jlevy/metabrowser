"""The SQLite table reads, as they run in a reader process.

Every connection to a database Metabrowser does not own runs in a reader process
(:mod:`metabrowser.sqlite_readers`), which loads :mod:`metabrowser.sqlite_access` and the
modules registered with it, and nothing else of the package. This is one of those
modules: it imports only the standard library and ``sqlite_access``, and it adds the
requests below to ``sqlite_access.OPS`` when it is loaded. The server side of the
source (``source.py``) asks for them through the reader pool, turns what they answer
into the table protocol's cells and tokens, and owns every rule a token or a cell
follows; this module owns the SQL.

Requests, each one short read through :func:`sqlite_access.read`:

- ``sqlite_catalog``: the database's tables, views, and virtual tables with an estimate
  of each one's rows, its ``application_id``, and its encoding.
- ``sqlite_describe``: one object's columns, key, foreign keys in both directions,
  indexes, triggers, DDL, and whether it holds more rows than an unindexed sort may
  read.
- ``sqlite_rows``: one page in a query's order, keyset paged by region (below), the
  references its cells hold resolved in one batch, and the query's capped count, read
  apart with no wait.
- ``sqlite_record``: one row in full, previewed past the record bound, with the rows of
  other tables that reference it counted.
- ``sqlite_ddl``: every object's DDL and every table's foreign keys, for the Schema
  view.

**Values.** ``SQLITE_LIMIT_LENGTH`` fails a whole statement, not one value, so no
statement here reads a value it has not sized: a value is read as
``CASE WHEN octet_length(v) <= :inline THEN v END`` with its ``typeof`` and
``octet_length`` beside it, and a filter or search reads it only under
``octet_length(v) <= VALUE_MAX_BYTES``. A text or blob longer than the inline bound is
previewed through ``Connection.blobopen`` where the object has a rowid, which reads part
of the value whatever its size; elsewhere its size alone is sent. A value travels to the
server as :func:`_wire` encodes it.

**Order.** A page is in the order of its sort field, then the key, both ascending or
both descending. Nulls sort first ascending and last descending, and a row-value
comparison with null is unknown, so a sorted page reads the null rows by key
(``s IS NULL AND k > ?``) and the rest by row value (``(s, k) > (?, ?)``), each with its
own seek and each mirrored descending; a cursor names its region and the next page
continues into the next region (the exploration's Encoding record:
``explorations/sqlite-guest-reads/README.md#encoding``). An object with no key (a view, a
virtual table) is ordered by its rows' positions in its own order, numbered by
``row_number() OVER ()``; with no sort, filter, or search the positions are read by
``OFFSET`` without numbering them.
"""

from __future__ import annotations

import codecs
import json
import math
import re
import sqlite3
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any, Final

from metabrowser import sqlite_access

# ── Bounds ─────────────────────────────────────────────────────
#
# Measured with `uv run python -m devtools.bench_sqlite_tables` (a shared 4-processor
# Linux container, Python 3.13, SQLite 3.53, 2026-11-20) over a 12-column shape; rerun it
# for the current numbers. A statement's cost is in opcodes as well as time, since the
# work budget (`sqlite_access.READ_OPCODE_BUDGET`) counts opcodes.

# The rows past which an object's fields sort only where an index leads with them, or
# they are its key. An unindexed sort reads and sorts every row before it returns the
# first, so it cannot stop part-way with a useful answer. At this many rows an unindexed
# first page of 100 rows ran 1.25 million opcodes in 19 ms, an eighth of the budget,
# which leaves a filter in the same statement room; at a million rows it ran 12 million,
# past the budget, so the sort would be refused part-way anyway. A page in key order ran
# 12,700 opcodes in under a millisecond at every size.
SORT_UNINDEXED_MAX_ROWS: Final = 100_000

# The most rows a count reads: a count up to this is exact, and past it the page says
# "at least" this many (Decision 6). A capped count at this cap ran 7.0 million opcodes
# in 54 ms, within the budget a count has of its own, as it is read apart from the page.
COUNT_CAP: Final = 1_000_000

# Rows one filtered page may examine before it hands the caller a continuation.
FILTER_SCAN_ROWS: Final = 8192
# Exact small-table sizes for the overview, within one short scan per table.
OVERVIEW_COUNT_ROWS: Final = 1000

# Distinct referenced rows one page resolves, across its references: a page's most rows
# (`TABLE_PAGE_ROWS_MAX`). Resolving that many by the referenced table's key, in one
# statement per reference, added 8 ms to a 1,000-row page that took 2 ms without them.
REFS_PER_PAGE: Final = 1000

# Bytes of a text or blob read whole into a page; a longer one is previewed through
# `blobopen`. A page's text cell shows `TABLE_CELL_PREVIEW_CHARS` characters, at most four
# bytes each in UTF-8 or UTF-16, so a value up to this size is read whole and its length
# in characters is exact. The page cells bound (`TABLE_PAGE_CELLS_MAX`) admits 12,000
# values: read whole at this size they took 155 ms, and previewed through `blobopen`,
# whatever their size, 627 ms, 52 µs a value. Reading whole up to this size keeps the
# dearer preview to values whose whole read would cost more still.
PAGE_INLINE_BYTES: Final = 4096

# The name a keyless object's row position takes in the statements below, with `_`
# appended until no column of the object has it (`position_name`).
POSITION: Final = "__metabrowser_position"

_TOOBIG: Final = 18  # SQLITE_TOOBIG
_AUTH: Final = 23  # SQLITE_AUTH
_INTERRUPT: Final = sqlite3.SQLITE_INTERRUPT
_ROWID_ALIASES: Final = ("rowid", "_rowid_", "oid")
_FSQLITE_ID: Final = 0x4653514C
_FSQLITE_TABLES: Final = frozenset({"fsqlite_meta", "applied_tx"})
_ENCODINGS: Final = {"UTF-8": "utf-8", "UTF-16le": "utf-16-le", "UTF-16be": "utf-16-be"}

type Wire = Any
type Row = tuple[Any, ...]


# ── Values ─────────────────────────────────────────────────────


def quote(name: str) -> str:
    """An identifier as SQL text."""
    return '"' + name.replace('"', '""') + '"'


def _wire(kind: str, value: Any) -> Wire:
    """A value read with ``text_factory = bytes`` as it travels to the server.

    ``None``, an integer, a finite real, and valid UTF-8 text are themselves; a real JSON
    cannot carry is ``{"real": "inf" | "-inf" | "nan"}``, text that is not valid UTF-8 is
    ``{"tx": <hex of its bytes>}``, and a blob is ``{"x": <hex>}``.
    """
    if value is None:
        return None
    if kind == "real" or isinstance(value, float):
        number = float(value)
        if math.isfinite(number):
            return number
        return {"real": "nan" if math.isnan(number) else ("inf" if number > 0 else "-inf")}
    if isinstance(value, int):
        return value
    if isinstance(value, bytes):
        if kind == "text":
            try:
                return value.decode("utf-8")
            except UnicodeDecodeError:
                return {"tx": value.hex()}
        return {"x": value.hex()}
    return str(value)


def bind(value: Wire) -> tuple[str, Any]:
    """A wire value as a placeholder and its parameter, so it compares as it was read."""
    if isinstance(value, dict):
        if "real" in value:
            return "?", float(str(value["real"]))  # pyright: ignore[reportUnknownArgumentType]
        if "tx" in value:
            return "CAST(? AS TEXT)", bytes.fromhex(str(value["tx"]))  # pyright: ignore[reportUnknownArgumentType]
        if "x" in value:
            return "?", bytes.fromhex(str(value["x"]))  # pyright: ignore[reportUnknownArgumentType]
        raise ValueError("not a value")
    if value is None or isinstance(value, (int, float, str)):
        return "?", value
    raise ValueError("not a value")


def _binds(values: Sequence[Wire]) -> tuple[list[str], list[Any]]:
    marks: list[str] = []
    params: list[Any] = []
    for value in values:
        mark, param = bind(value)
        marks.append(mark)
        params.append(param)
    return marks, params


def _row_value(names: Sequence[str]) -> str:
    return "(" + ", ".join(quote(name) for name in names) + ")"


def _decode(raw: bytes, encoding: str) -> tuple[str, bool]:
    """Bytes of a value's stored text, dropping an incomplete trailing sequence, decoded
    with replacement characters where they are invalid."""
    decoder = codecs.getincrementaldecoder(encoding)("strict")
    try:
        return decoder.decode(raw, final=False), False
    except UnicodeDecodeError:
        lenient = codecs.getincrementaldecoder(encoding)("replace")
        return lenient.decode(raw, final=False), True


def _refused(exc: sqlite3.Error) -> bool:
    """Whether the authorizer refused *exc*'s statement: ``SQLITE_AUTH``, or a function
    it refused, which SQLite reports as an error naming it ("not authorized to use
    function"), as ``sqlite_access`` classifies a refusal."""
    code = getattr(exc, "sqlite_errorcode", 0) & 0xFF
    return code == _AUTH or "not authorized" in str(exc)


def _stopped(exc: sqlite3.Error) -> bool:
    return (getattr(exc, "sqlite_errorcode", 0) & 0xFF) == _INTERRUPT


def _toobig(exc: sqlite3.Error) -> bool:
    return (getattr(exc, "sqlite_errorcode", 0) & 0xFF) == _TOOBIG


def _budget(connection: sqlite3.Connection, deadline: float) -> None:
    """A fresh work budget for the next phase of one read."""
    sqlite_access.bound_work(
        connection, opcodes=sqlite_access.READ_OPCODE_BUDGET, deadline=deadline
    )


def _fetch(
    connection: sqlite3.Connection, sql: str, params: Sequence[Any], limit: int | None = None
) -> tuple[list[Row], bool]:
    """Rows of *sql* until *limit*, and whether the budget stopped it first."""
    rows: list[Row] = []
    try:
        cursor = connection.execute(sql, params)
        while limit is None or len(rows) < limit:
            row = cursor.fetchone()
            if row is None:
                break
            rows.append(tuple(row))
    except sqlite3.OperationalError as exc:
        if _stopped(exc):
            return rows, True
        raise
    return rows, False


# ── Virtual tables on a guest read ─────────────────────────────
#
# Where virtual tables are not read (a Git pin, the untrusted profile), every request
# refuses, at prepare time, any read of a virtual table or of a table that may be one of
# its shadow tables, in its own statements and inside any view, and any schema pragma
# that describes one. The names come from `sqlite_schema` in the request's own
# transaction, which connects no module, so the refusal is in place before anything
# could. A view over a virtual table is then refused when it is read, so the module's
# query code (`xBestIndex`, `xFilter`, `xNext` over its shadow tables) never runs.
#
# What remains: SQLite computes a view's column names with no authorizer (measured on
# SQLite 3.53), so listing the objects (`pragma_table_list`) or describing or reading a
# view that names a virtual table still connects that table: its module's `xConnect`
# runs and reads its configuration (FTS5's `<table>_config`; R-tree the size of its
# root node). Only `sqlite3_drop_modules` would stop that, and Python's `sqlite3` does
# not expose it. Shadow tables are refused too, so that a statement naming a virtual
# table directly, which connects it with the authorizer in place, fails at the connect.

_VIRTUAL_DDL: Final = re.compile(rb"\s*CREATE\s+VIRTUAL\s+TABLE\b", re.IGNORECASE)

# A quoted name can itself contain a USING token, so match it as one identifier.
_FTS_DDL: Final = re.compile(
    rb"""\s*CREATE\s+VIRTUAL\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"""
    rb"""(?:"(?:[^"]|"")*"|'(?:[^']|'')*'|`[^`]*`|\[[^\]]*\]|[^\s.'"\x60\[\]();]+)"""
    rb"""\s+USING\s+(fts[345])\s*(?:\(|$)""",
    re.IGNORECASE,
)
# SQLite's fts3ShadowName and fts5ShadowName callbacks define these suffixes.
_FTS34_SHADOWS: Final = frozenset({"content", "docsize", "segdir", "segments", "stat"})
_FTS_SHADOWS: Final = {
    b"fts3": _FTS34_SHADOWS,
    b"fts4": _FTS34_SHADOWS,
    b"fts5": frozenset({"config", "content", "data", "docsize", "idx"}),
}


def _guest_denied(connection: sqlite3.Connection) -> frozenset[str]:
    """Refuse virtual tables and possible shadows before connecting any module.

    SQLite identifies the built-in FTS modules' shadows by exact suffix. For other
    modules or ambiguous declarations, refuse every possible shadow.
    """
    virtual: dict[str, frozenset[str] | None] = {}
    tables: list[str] = []
    for name, sql in connection.execute(
        "SELECT name, sql FROM sqlite_schema WHERE type = 'table'"
    ).fetchall():
        text = _text(name) or ""
        ddl = sql if isinstance(sql, bytes) else str(sql or "").encode("utf-8", "replace")
        if _VIRTUAL_DDL.match(ddl):
            module = _FTS_DDL.match(ddl)
            virtual[text.casefold()] = _FTS_SHADOWS[module[1].lower()] if module else None
        else:
            tables.append(text.casefold())
    denied = set(virtual)
    for name in tables:
        prefix, separator, suffix = name.rpartition("_")
        if separator and prefix in virtual:
            suffixes = virtual[prefix]
            if suffixes is None or suffix in suffixes:
                denied.add(name)
    return frozenset(denied)


def _objects(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    """The main schema's tables, views, and virtual tables, by `table_list`, with their
    DDL. `sqlite_schema` itself is not listed."""
    sql_by_name = {
        str(name, "utf-8", "replace") if isinstance(name, bytes) else str(name): sql
        for name, sql in connection.execute(
            "SELECT name, sql FROM sqlite_schema WHERE type IN ('table', 'view')"
        )
    }
    objects: list[dict[str, Any]] = []
    for name, kind, ncol, wr, strict in connection.execute(
        "SELECT name, type, ncol, wr, strict FROM pragma_table_list WHERE schema = 'main'"
    ):
        text = name.decode("utf-8", "replace") if isinstance(name, bytes) else str(name)
        if text.lower() in ("sqlite_schema", "sqlite_master"):
            continue
        sql = sql_by_name.get(text)
        objects.append(
            {
                "name": text,
                "type": kind.decode() if isinstance(kind, bytes) else str(kind),
                "columns": int(ncol),
                "without_rowid": bool(wr),
                "strict": bool(strict),
                "sql": sql.decode("utf-8", "replace") if isinstance(sql, bytes) else sql,
            }
        )
    objects.sort(key=lambda item: str(item["name"]).lower())
    return objects


def _pragma(connection: sqlite3.Connection, name: str) -> Any:
    value = connection.execute(f"PRAGMA {name}").fetchone()[0]
    return value.decode() if isinstance(value, bytes) else value


def _group(item: dict[str, Any], application_id: int) -> str:
    name = str(item["name"]).lower()
    kind = item["type"]
    if kind == "shadow" or name.startswith("sqlite_"):
        return "internal"
    if application_id == _FSQLITE_ID and name in _FSQLITE_TABLES:
        return "internal"
    if kind == "view":
        return "views"
    if kind == "virtual":
        return "virtual"
    return "tables"


def rowid_alias(columns: Sequence[str]) -> str | None:
    """The first rowid alias no column shadows, or None when every one is shadowed."""
    taken = {column.lower() for column in columns}
    return next((alias for alias in _ROWID_ALIASES if alias not in taken), None)


def _estimates(
    connection: sqlite3.Connection,
    objects: list[dict[str, Any]],
    deadline: float,
    denied: frozenset[str],
) -> dict[str, int]:
    """Small tables' actual sizes, or the row counts left by ANALYZE."""
    out: dict[str, int] = {}
    names = {str(item["name"]).lower() for item in objects}
    if "sqlite_stat1" in names:
        rows, _ = _fetch(
            connection,
            "SELECT tbl, stat FROM sqlite_stat1 WHERE octet_length(stat) <= 128 LIMIT 4096",
            (),
        )
        for table, stat in rows:
            text = stat.decode("ascii", "replace") if isinstance(stat, bytes) else str(stat)
            first = text.split(" ", 1)[0]
            if first.isascii() and first.isdecimal() and len(first) <= 19:
                key = table.decode("utf-8", "replace") if isinstance(table, bytes) else str(table)
                out[key.lower()] = max(out.get(key.lower(), 0), int(first))
    for item in objects:
        name = str(item["name"])
        if name.lower() in out or item["type"] != "table" or name.casefold() in denied:
            continue
        _budget(connection, deadline)
        try:
            rows, stopped = _fetch(
                connection,
                f"SELECT count(*) FROM (SELECT 1 FROM {quote(name)} LIMIT ?)",
                (OVERVIEW_COUNT_ROWS + 1,),
            )
        except sqlite3.OperationalError as exc:
            if item["without_rowid"] and str(exc) == "no query solution":
                # Its primary key may use a collation available only to its owner.
                continue
            raise
        if not stopped and rows and int(rows[0][0]) <= OVERVIEW_COUNT_ROWS:
            out[name.lower()] = int(rows[0][0])
    return out


def catalog(
    connection: sqlite3.Connection, deadline: float, denied: frozenset[str] = frozenset()
) -> dict[str, Any]:
    connection.text_factory = bytes
    application_id = int(_pragma(connection, "application_id"))
    encoding = str(_pragma(connection, "encoding"))
    objects = _objects(connection)
    estimates = _estimates(connection, objects, deadline, denied)
    for item in objects:
        item["group"] = _group(item, application_id)
        item["estimate"] = estimates.get(str(item["name"]).lower())
        name = str(item["name"])
        key: list[str] = []
        if item["type"] == "table" and name.casefold() not in denied:
            key, _ = _key(connection, item, _columns(connection, name))
        item["key"] = key
        item["keyed"] = bool(key)
    return {"application_id": application_id, "encoding": encoding, "objects": objects}


# ── One object ─────────────────────────────────────────────────


def _text(value: Any) -> str | None:
    if value is None:
        return None
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else str(value)


def _find(objects: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    """The object a foreign key names, as SQLite finds it: by its exact name, else
    ignoring case. An address names its object exactly (:func:`describe`)."""
    exact = next((item for item in objects if item["name"] == name), None)
    if exact is not None:
        return exact
    return next((item for item in objects if str(item["name"]).lower() == name.lower()), None)


def _primary_key(columns: list[dict[str, Any]]) -> list[str]:
    keyed = sorted((column for column in columns if column["pk"]), key=lambda c: c["pk"])
    return [column["name"] for column in keyed]


def _foreign_keys(
    connection: sqlite3.Connection,
    name: str,
    objects: list[dict[str, Any]],
    denied: frozenset[str] = frozenset(),
) -> list[dict[str, Any]]:
    """A table's declared foreign keys, one per constraint, with its target named as the
    catalog names it and an omitted target column list read as the target's primary
    key. A key whose target does not exist, or has no primary key to stand for an
    omitted list, is left out: SQLite refuses it too, when it is enforced. So is one
    whose omitted list would be read from a target this read may not describe."""
    if name.casefold() in denied:
        return []
    grouped: dict[int, dict[str, Any]] = {}
    for fk_id, _seq, target, source, to in connection.execute(
        'SELECT id, seq, "table", "from", "to" FROM pragma_foreign_key_list(?) ORDER BY id, seq',
        (name,),
    ):
        entry = grouped.setdefault(
            int(fk_id), {"target": _text(target) or "", "from": [], "to": []}
        )
        entry["from"].append(_text(source) or "")
        entry["to"].append(_text(to))
    out: list[dict[str, Any]] = []
    for entry in grouped.values():
        found = _find(objects, entry["target"])
        if found is None or found["type"] not in ("table", "virtual"):
            continue
        to = entry["to"]
        if any(item is None for item in to):
            if str(found["name"]).casefold() in denied:
                continue
            columns = _columns(connection, str(found["name"]))
            key = _primary_key(columns)
            if not key and not found["without_rowid"]:
                integer = [c["name"] for c in columns if c["pk"]]
                key = integer
            if len(key) != len(entry["from"]):
                continue
            to = key
        out.append({"table": found["name"], "from": entry["from"], "to": to})
    return out


def _columns(connection: sqlite3.Connection, name: str) -> list[dict[str, Any]]:
    return [
        {
            "name": _text(column_name) or "",
            "declared": _text(declared) or "",
            "notnull": bool(notnull),
            "default": _text(default),
            "pk": int(pk),
            "hidden": int(hidden),
        }
        for column_name, declared, notnull, default, pk, hidden in connection.execute(
            'SELECT name, type, "notnull", dflt_value, pk, hidden FROM pragma_table_xinfo(?)',
            (name,),
        )
    ]


def _indexes(connection: sqlite3.Connection, name: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    sql_by_name = {
        _text(index_name): _text(sql)
        for index_name, sql in connection.execute(
            "SELECT name, sql FROM sqlite_schema WHERE type = 'index' AND tbl_name = ?", (name,)
        )
    }
    for index_name, unique, origin, partial in connection.execute(
        'SELECT name, "unique", origin, partial FROM pragma_index_list(?)', (name,)
    ):
        text = _text(index_name) or ""
        columns = [
            _text(column) if int(cid) >= 0 else None
            for _seqno, cid, column in connection.execute(
                "SELECT seqno, cid, name FROM pragma_index_xinfo(?) WHERE key = 1 ORDER BY seqno",
                (text,),
            )
        ]
        out.append(
            {
                "name": text,
                "unique": bool(unique),
                "origin": _text(origin),
                "partial": bool(partial),
                "columns": columns,
                "sql": sql_by_name.get(text),
            }
        )
    return out


def _key(
    connection: sqlite3.Connection, item: dict[str, Any], columns: list[dict[str, Any]]
) -> tuple[list[str], str | None]:
    """An object's key columns and, for a rowid table whose rowid is not a column, the
    alias that names it: the rowid, the integer primary key that is its alias, or a
    `WITHOUT ROWID` table's primary key. A view's or a virtual table's rows have none,
    and nor does a table whose every rowid alias a column shadows and that has no
    integer primary key.

    An `INTEGER PRIMARY KEY` is the rowid's alias unless it was declared
    `INTEGER PRIMARY KEY DESC` in its column, SQLite's documented exception, which is an
    ordinary column that may hold nulls and has an index of its own: so a primary key
    with an index (`origin = 'pk'`) is no alias, and the table is keyed by its rowid."""
    if item["type"] != "table":
        return [], None
    if item["without_rowid"]:
        return _primary_key(columns), None
    keyed = [column for column in columns if column["pk"]]
    if len(keyed) == 1 and keyed[0]["declared"].upper() == "INTEGER":
        indexed = connection.execute(
            "SELECT 1 FROM pragma_index_list(?) WHERE origin = 'pk'", (str(item["name"]),)
        ).fetchone()
        if indexed is None:
            return [keyed[0]["name"]], None
    alias = rowid_alias([column["name"] for column in columns])
    return ([alias], alias) if alias is not None else ([], None)


def describe(
    connection: sqlite3.Connection,
    name: str,
    deadline: float,
    *,
    denied: frozenset[str] = frozenset(),
    sort_rows: int = SORT_UNINDEXED_MAX_ROWS,
) -> dict[str, Any] | None:
    """One object's description. Where *denied* names it (a virtual table, or a table
    that may be one's shadow table, on a guest read) it is described from the catalog
    alone, unread; a view that reads one is found so when its rows are counted."""
    connection.text_factory = bytes
    objects = _objects(connection)
    # One name, one address: a case variant of a table's segment names nothing.
    item = next((item for item in objects if item["name"] == name), None)
    if item is None:
        return None
    application_id = int(_pragma(connection, "application_id"))
    exact = str(item["name"])
    # Why the object is not read here: `virtual` (it is a virtual table), `shadow` (it
    # may be a virtual table's shadow table), `reads_virtual` (a view that reads one),
    # `module` (a virtual table whose module does more than read to open it: R-tree
    # prepares writes to its shadow tables when it connects, which a reader refuses).
    unread: str | None = None
    if exact.casefold() in denied:
        unread = "virtual" if item["type"] == "virtual" else "shadow"
    columns: list[dict[str, Any]] = []
    if not unread:
        try:
            columns = _columns(connection, exact)
        except sqlite3.DatabaseError as exc:
            if not (item["type"] == "virtual" and _refused(exc)):
                raise
            unread = "module"
    key, alias = _key(connection, item, columns) if not unread else ([], None)
    tabled = item["type"] == "table" and not unread
    outgoing = _foreign_keys(connection, exact, objects, denied) if tabled else []
    incoming: list[dict[str, Any]] = []
    for other in objects:
        if other["type"] != "table":
            continue
        for fk in _foreign_keys(connection, str(other["name"]), objects, denied):
            if fk["table"] == exact:
                incoming.append({"table": other["name"], "from": fk["from"], "to": fk["to"]})
    indexes = _indexes(connection, exact) if tabled else []
    triggers = [
        {"name": _text(trigger), "sql": _text(sql)}
        for trigger, sql in connection.execute(
            "SELECT name, sql FROM sqlite_schema WHERE type = 'trigger' AND tbl_name = ? "
            "ORDER BY name",
            (exact,),
        )
    ]
    rows_upto: int | None = None
    if not unread:
        _budget(connection, deadline)
        try:
            rows, stopped = _fetch(
                connection,
                f"SELECT count(*) FROM (SELECT 1 FROM {quote(exact)} LIMIT ?)",
                (sort_rows + 1,),
            )
        except sqlite3.DatabaseError as exc:
            if denied and _refused(exc):
                unread = "reads_virtual"
            elif item["without_rowid"] and str(exc) == "no query solution":
                unread = "key_collation"
            else:
                raise
            rows, stopped = [], True
        rows_upto = None if stopped or not rows else int(rows[0][0])
    readable = unread is None
    return {
        "name": exact,
        "type": item["type"],
        "group": _group(item, application_id),
        "without_rowid": item["without_rowid"],
        "strict": item["strict"],
        "sql": item["sql"],
        "readable": readable,
        "unread": unread,
        "columns": columns,
        "key": key,
        "rowid_alias": alias,
        "foreign_keys": outgoing,
        "referenced_by": incoming,
        "indexes": indexes,
        "triggers": triggers,
        "rows_upto": rows_upto,
    }


def ddl(
    connection: sqlite3.Connection, name: str | None, denied: frozenset[str] = frozenset()
) -> dict[str, Any]:
    """Every object's DDL, or one table's and its indexes' and triggers', with every
    table's foreign keys."""
    connection.text_factory = bytes
    objects = _objects(connection)
    rows = connection.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_schema ORDER BY tbl_name, "
        "CASE type WHEN 'table' THEN 0 WHEN 'view' THEN 0 WHEN 'index' THEN 1 ELSE 2 END, name"
    ).fetchall()
    entries = [
        {"type": _text(kind), "name": _text(entry), "table": _text(table), "sql": _text(sql)}
        for kind, entry, table, sql in rows
    ]
    if name is not None:
        entries = [entry for entry in entries if entry["table"] == name]
    keys: dict[str, list[dict[str, Any]]] = {}
    for item in objects:
        if item["type"] == "table" and (name is None or item["name"] == name):
            found = _foreign_keys(connection, str(item["name"]), objects, denied)
            if found:
                keys[str(item["name"])] = found
    return {"objects": entries, "foreign_keys": keys}


# ── Reading values ─────────────────────────────────────────────


def _value_exprs(column: str, inline: int) -> list[str]:
    q = quote(column)
    return [
        f"typeof({q})",
        f"octet_length({q})",
        f"CASE WHEN octet_length({q}) <= {int(inline)} THEN {q} END",
    ]


class _Previewer:
    """Previews of values longer than the inline bound, through `blobopen`, which reads
    part of a text or blob in a rowid table whatever its size. The bytes are the stored
    ones, so text is decoded by the database's encoding."""

    def __init__(
        self, connection: sqlite3.Connection, table: str, rowid: bool, encoding: str
    ) -> None:
        self._connection = connection
        self._table = table
        self._rowid = rowid
        self._encoding = _ENCODINGS.get(encoding, "utf-8")

    def preview(self, column: str, rowid: Any, kind: str, size: int, limit: int) -> Wire:
        if not self._rowid or not isinstance(rowid, int):
            return None
        try:
            with self._connection.blobopen(self._table, column, rowid, readonly=True) as blob:
                raw = blob.read(min(size, limit))
        except sqlite3.Error:
            return None
        if kind == "blob":
            return {"pb": raw.hex()}
        text, invalid = _decode(raw, self._encoding)
        return {"pt": text, "inv": invalid} if invalid else {"pt": text}


def _previewed(value: Wire) -> bool:
    return isinstance(value, dict) and ("pt" in value or "pb" in value)


def _cell(row: Row, start: int) -> list[Any]:
    kind = row[start].decode() if isinstance(row[start], bytes) else str(row[start])
    size = row[start + 1]
    return [kind, int(size) if size is not None else 0, _wire(kind, row[start + 2])]


# ── Queries ────────────────────────────────────────────────────


def _guard(column: str) -> str:
    return f"octet_length({quote(column)}) <= {sqlite_access.VALUE_MAX_BYTES}"


def _like(needle: str) -> str:
    escaped = needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


_OPERATORS: Final = {"eq": "=", "ne": "!=", "lt": "<", "le": "<=", "gt": ">", "ge": ">="}


def _predicates(spec: dict[str, Any]) -> tuple[list[str], list[Any], list[str]]:
    """The query's filters, search, and reference filter as SQL, their parameters, and
    the expressions that count a value too large to examine."""
    clauses: list[str] = []
    params: list[Any] = []
    skips: list[str] = []
    for item in spec.get("filters") or []:
        column = str(item["field"])
        q = quote(column)
        op = str(item["op"])
        if op == "null":
            clauses.append(f"typeof({q}) = 'null'")
        elif op == "notnull":
            clauses.append(f"typeof({q}) != 'null'")
        elif op == "contains":
            clauses.append(
                f"(typeof({q}) IN ('text', 'integer', 'real') AND {_guard(column)} "
                f"AND {q} LIKE ? ESCAPE '\\')"
            )
            params.append(_like(str(item["value"])))
            skips.append(f"(octet_length({q}) > {sqlite_access.VALUE_MAX_BYTES})")
        else:
            mark, param = bind(item["value"])
            typed = ""
            if op in ("lt", "le", "gt", "ge"):
                # An order compares values of the filter's own kind: SQLite orders every
                # text after every number, so text in a numeric column is no match.
                kinds = "'text'" if isinstance(param, str) else "'integer', 'real'"
                typed = f"typeof({q}) IN ({kinds}) AND "
            clauses.append(f"({typed}{_guard(column)} AND {q} {_OPERATORS[op]} {mark})")
            params.append(param)
            skips.append(f"(octet_length({q}) > {sqlite_access.VALUE_MAX_BYTES})")
    search = spec.get("search")
    if search:
        fields = [str(name) for name in search["fields"]]
        if fields:
            parts: list[str] = []
            for column in fields:
                q = quote(column)
                parts.append(
                    f"(typeof({q}) = 'text' AND {_guard(column)} AND {q} LIKE ? ESCAPE '\\')"
                )
                params.append(_like(str(search["needle"])))
                skips.append(f"(octet_length({q}) > {sqlite_access.VALUE_MAX_BYTES})")
            clauses.append("(" + " OR ".join(parts) + ")")
        else:
            clauses.append("0")
    ref = spec.get("ref")
    if ref is not None:
        options: list[str] = []
        for option in ref:
            match, values = _references(
                str(option["table"]),
                [str(name) for name in option["to"]],
                [str(name) for name in option["fields"]],
                option["values"],
            )
            options.append(match)
            params.extend(values)
        clauses.append("(" + " OR ".join(options) + ")" if options else "0")
    return clauses, params, skips


def position_name(columns: Iterable[str]) -> str:
    """The name of a keyless object's row position: :data:`POSITION`, with `_` appended
    until it is none of *columns*, compared as SQLite compares names."""
    taken = {column.casefold() for column in columns}
    name = POSITION
    while name.casefold() in taken:
        name += "_"
    return name


def _position(spec: dict[str, Any]) -> str:
    return str(spec.get("position_name") or POSITION)


# The alias of the object a statement reads rows of, so a correlated subquery can name
# its columns past a table of the same name inside it.
ROW: Final = quote("__metabrowser_row")
# The alias of a referenced table inside such a subquery.
_TARGET: Final = quote("__metabrowser_target")


def _references(
    target: str, to: Sequence[str], fields: Sequence[str], values: Sequence[Wire]
) -> tuple[str, list[Any]]:
    """Whether the row's *fields* name the *target* row whose *to* columns hold *values*,
    decided as a page's references resolve: by the target's columns, on the left, so
    their affinity and collation decide a match as they would for the foreign key."""
    marks, bound = _binds(values)
    joins = " AND ".join(
        f"{_TARGET}.{quote(column)} = {ROW}.{quote(field)}"
        for column, field in zip(to, fields, strict=True)
    )
    named = ", ".join(f"{_TARGET}.{quote(column)}" for column in to)
    sql = (
        f"EXISTS (SELECT 1 FROM {quote(target)} AS {_TARGET} WHERE {joins} "
        f"AND ({named}) = ({', '.join(marks)}))"
    )
    return sql, bound


def _relation(spec: dict[str, Any], positioned: bool) -> str:
    table = quote(str(spec["table"]))
    if positioned:
        return f"(SELECT row_number() OVER () AS {quote(_position(spec))}, * FROM {table}) AS {ROW}"
    return f"{table} AS {ROW}"


def _key_columns(spec: dict[str, Any], positioned: bool) -> list[str]:
    key = [str(name) for name in spec["key"]]
    return key if key else ([_position(spec)] if positioned else [])


def _regions(spec: dict[str, Any]) -> list[str]:
    if spec.get("sort") is None:
        return ["k"]
    return ["n", "v"] if spec["order"] == "asc" else ["v", "n"]


def _region_sql(
    spec: dict[str, Any],
    region: str,
    after: dict[str, Any] | None,
    select: str,
    where: list[str],
    params: list[Any],
    positioned: bool,
) -> tuple[str, list[Any]]:
    key = _key_columns(spec, positioned)
    desc = spec["order"] == "desc"
    direction = " DESC" if desc else ""
    compare = "<" if desc else ">"
    clauses = list(where)
    values = list(params)
    sort = str(spec.get("sort") or "")
    if region == "n":
        clauses.append(f"{quote(sort)} IS NULL")
        order = [quote(name) + direction for name in key]
    elif region == "v":
        clauses.append(f"{quote(sort)} IS NOT NULL")
        order = [quote(sort) + direction] + [quote(name) + direction for name in key]
    else:
        order = [quote(name) + direction for name in key]
    if after is not None and after["region"] == region:
        points = ([after["value"]] if region == "v" else []) + list(after["key"])
        names = ([sort] if region == "v" else []) + key
        marks, bound = _binds(points)
        clauses.append(f"{_row_value(names)} {compare} ({', '.join(marks)})")
        values.extend(bound)
    sql = f"SELECT {select} FROM {_relation(spec, positioned)}"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY " + ", ".join(order) + " LIMIT ?"
    return sql, values


def _select(spec: dict[str, Any], positioned: bool, inline: int) -> tuple[str, list[str]]:
    """The select list: the key's values with their types, the sort value's, then each
    read column's type, size, and value."""
    key = _key_columns(spec, positioned)
    parts: list[str] = []
    for name in key:
        q = quote(name)
        parts += [f"typeof({q})", f"CASE WHEN {_guard(name)} THEN {q} END"]
    sort = spec.get("sort")
    if sort is not None:
        q = quote(sort)
        # A sort value larger than a token can hold uses the positional cursor.
        token_bytes = int(spec["token_bytes"])
        parts += [f"typeof({q})", f"CASE WHEN octet_length({q}) <= {token_bytes} THEN {q} END"]
    if spec.get("rowid") is not None:
        parts.append(quote(spec["rowid"]))
    columns = [str(name) for name in spec["columns"]]
    for column in columns:
        parts += _value_exprs(column, inline)
    return ", ".join(parts), columns


def _split(
    row: Row,
    spec: dict[str, Any],
    positioned: bool,
    columns: list[str],
) -> dict[str, Any]:
    key = _key_columns(spec, positioned)
    at = 0
    key_values: list[Wire] = []
    for _ in key:
        kind = row[at].decode() if isinstance(row[at], bytes) else str(row[at])
        key_values.append(_wire(kind, row[at + 1]))
        at += 2
    sort_value: Wire = None
    # The region of the order the row is in: the sort field's nulls, its values, or the
    # key's order when nothing is sorted.
    region = "k"
    if spec.get("sort") is not None:
        kind = row[at].decode() if isinstance(row[at], bytes) else str(row[at])
        sort_value = _wire(kind, row[at + 1])
        region = "n" if kind == "null" else "v"
        at += 2
    rowid: Any = None
    if spec.get("rowid") is not None:
        rowid = row[at]
        at += 1
    cells: dict[str, Any] = {}
    for column in columns:
        cells[column] = _cell(row, at)
        at += 3
    return {
        "key": key_values,
        "sort": sort_value,
        "region": region,
        "rowid": rowid,
        "cells": cells,
    }


def _preview_cells(
    rows: list[dict[str, Any]], previewer: _Previewer, inline: int, limits: dict[str, int]
) -> None:
    for row in rows:
        for column, cell in row["cells"].items():
            kind, size, value = cell
            if value is None and kind in ("text", "blob") and size > inline:
                cell[2] = previewer.preview(column, row["rowid"], kind, size, limits[kind])


def _scan_matches(
    connection: sqlite3.Connection,
    spec: dict[str, Any],
    select: str,
    columns: list[str],
    positioned: bool,
) -> tuple[list[dict[str, Any]], bool, int, dict[str, Any] | None]:
    """Keep the last examined row even when a window contains no matches."""
    where, params, _ = _predicates(spec)
    match = " AND ".join(where)
    select = f"CASE WHEN {match} THEN 1 ELSE 0 END, {select}"
    limit = int(spec["limit"])
    scan_limit = int(spec["scan_rows"])
    after = spec.get("after")
    regions = _regions(spec)
    if after is not None and "region" in after:
        regions = regions[regions.index(after["region"]) :]

    found: list[dict[str, Any]] = []
    last: Row | None = None
    examined = 0
    stopped = False
    try:
        if after is not None and "offset" in after:
            sql, values = _offset_sql(spec, select, [], params, positioned)
            statements = [(sql, [*values, scan_limit, int(after["offset"])])]
        else:
            statements = [
                _region_sql(spec, region, after, select, [], params, positioned)
                for region in regions
            ]
        for sql, values in statements:
            if after is None or "offset" not in after:
                values.append(scan_limit - examined)
            for matched, *row in connection.execute(sql, values):
                last = tuple(row)
                examined += 1
                if matched:
                    found.append(_split(last, spec, positioned, columns))
                    if len(found) >= limit:
                        break
            if len(found) >= limit or examined >= scan_limit:
                stopped = len(found) < limit
                break
    except sqlite3.OperationalError as exc:
        if not _stopped(exc):
            raise
        stopped = True
    point = _split(last, spec, positioned, []) if last is not None else None
    return found, stopped, examined, point


def _page(connection: sqlite3.Connection, spec: dict[str, Any], deadline: float) -> dict[str, Any]:
    connection.text_factory = bytes
    keyless = not spec["key"]
    filtered = bool(spec.get("scan_rows"))
    sort = spec.get("sort")
    order = spec["order"]
    fast = keyless and sort is None and not filtered and order == "asc"
    positioned = keyless and not fast
    inline = int(spec["inline"])
    select, columns = _select(spec, positioned, inline)
    where, params, _skips = _predicates(spec)
    limit = int(spec["limit"])
    after = spec.get("after")
    found: list[dict[str, Any]] = []
    stopped = False
    toobig = False
    examined: int | None = None
    point: dict[str, Any] | None = None
    try:
        if filtered:
            found, stopped, examined, point = _scan_matches(
                connection, spec, select, columns, positioned
            )
        elif after is not None and "offset" in after:
            # A cursor past the token bound: the rows already served, in one statement in
            # the query's order, which is the regions' order concatenated.
            sql, values = _offset_sql(spec, select, where, params, positioned)
            start = int(after["offset"])
            rows, stopped = _fetch(connection, sql, [*values, limit, start])
            found = [_split(row, spec, positioned, columns) for row in rows]
            if keyless and not positioned:
                # Read in the object's own order, so its position is the offset's.
                for index, row in enumerate(found):
                    row["key"] = [start + index + 1]
        elif fast:
            start = int(after["key"][0]) if after is not None else 0
            sql = f"SELECT {select} FROM {quote(str(spec['table']))} LIMIT ? OFFSET ?"
            rows, stopped = _fetch(connection, sql, [limit, start])
            found = [_split(row, spec, False, columns) for row in rows]
            for index, row in enumerate(found):
                row["key"] = [start + index + 1]
        else:
            regions = _regions(spec)
            if after is not None and after["region"] in regions:
                regions = regions[regions.index(after["region"]) :]
            for region in regions:
                want = limit - len(found)
                if want <= 0:
                    break
                sql, values = _region_sql(spec, region, after, select, where, params, positioned)
                rows, stopped = _fetch(connection, sql, [*values, want])
                for row in rows:
                    found.append(_split(row, spec, positioned, columns))
                if stopped:
                    break
    except sqlite3.Error as exc:
        # A sorted value past the length limit fails the whole statement.
        if not _toobig(exc):
            raise
        toobig = True
    if toobig:
        return {"toobig": True, "rows": [], "stopped": False}
    _budget(connection, deadline)
    previewer = _Previewer(
        connection, str(spec["table"]), spec.get("rowid") is not None, str(spec["encoding"])
    )
    _preview_cells(found, previewer, inline, spec["preview"])
    refs = _resolve(connection, spec, found, deadline)
    return {
        "rows": found,
        "stopped": stopped,
        "more": len(found) >= limit,
        "examined": examined,
        "point": point,
        "refs": refs,
    }


def _offset_sql(
    spec: dict[str, Any], select: str, where: list[str], params: list[Any], positioned: bool
) -> tuple[str, list[Any]]:
    key = _key_columns(spec, positioned)
    direction = " DESC" if spec["order"] == "desc" else ""
    sort = spec.get("sort")
    order = ([quote(sort) + direction] if sort is not None else []) + [
        quote(name) + direction for name in key
    ]
    sql = f"SELECT {select} FROM {_relation(spec, positioned)}"
    if where:
        sql += " WHERE " + " AND ".join(where)
    if order:
        sql += " ORDER BY " + ", ".join(order)
    return sql + " LIMIT ? OFFSET ?", list(params)


def _positions(
    connection: sqlite3.Connection, spec: dict[str, Any], deadline: float
) -> list[int | None]:
    """Each named row's position in key order, counting from 1: a row whose key is too
    long for a token is named by it instead (`@<n>`). None for a key not read whole."""
    connection.text_factory = bytes
    key = [str(name) for name in spec["key"]]
    out: list[int | None] = []
    for values in spec["keys"]:
        if any(value is None for value in values):
            out.append(None)
            continue
        _budget(connection, deadline)
        marks, bound = _binds(values)
        found, stopped = _fetch(
            connection,
            f"SELECT count(*) FROM {quote(str(spec['table']))} "
            f"WHERE {_row_value(key)} < ({', '.join(marks)})",
            bound,
        )
        out.append(None if stopped or not found else int(found[0][0]) + 1)
    return out


def _resolve(
    connection: sqlite3.Connection,
    spec: dict[str, Any],
    rows: list[dict[str, Any]],
    deadline: float,
) -> list[dict[str, Any]]:
    """Each reference's target rows for the page's values, in one statement per
    reference: for each distinct value tuple, the target row's key, or nothing when no
    row holds it. Compared in SQL, so the target column's affinity and collation decide
    a match as they would for the foreign key."""
    out: list[dict[str, Any]] = []
    budget = REFS_PER_PAGE
    for ref in spec.get("refs") or []:
        fields = [str(name) for name in ref["fields"]]
        tuples: list[list[Wire]] = []
        seen: set[str] = set()
        for row in rows:
            values = [row["cells"][name][2] if name in row["cells"] else None for name in fields]
            if any(value is None or _previewed(value) for value in values):
                # A null names no row, and a value read only in part cannot be matched.
                continue
            marker = json.dumps(values, sort_keys=True)
            if marker in seen:
                continue
            seen.add(marker)
            tuples.append(values)
        tuples = tuples[:budget]
        budget -= len(tuples)
        if not tuples:
            out.append({"values": [], "keys": []})
            continue
        target = str(ref["table"])
        to = [str(name) for name in ref["to"]]
        target_key = [str(name) for name in ref["key"]]
        rows_sql: list[str] = []
        params: list[Any] = []
        for number, values in enumerate(tuples):
            marks, bound = _binds(values)
            rows_sql.append("(" + ", ".join(["?", *marks]) + ")")
            params.extend([number, *bound])
        joins = " AND ".join(
            f"t.{quote(column)} = v.column{index + 2}" for index, column in enumerate(to)
        )
        key_sql = ", ".join(f"typeof(t.{quote(name)}), t.{quote(name)}" for name in target_key)
        sql = (
            f"SELECT v.column1, {key_sql} FROM (VALUES {', '.join(rows_sql)}) AS v "
            f"JOIN {quote(target)} AS t ON {joins}"
        )
        _budget(connection, deadline)
        try:
            found, stopped = _fetch(connection, sql, params)
        except sqlite3.Error:
            # The target cannot be read as the key says (a target that is a view, a
            # value past the length limit): the values stay plain, never "missing".
            found, stopped = [], True
        if stopped:
            # A resolution cut short cannot say which targets are missing.
            out.append({"values": [], "keys": []})
            continue
        keys: list[Any] = [None] * len(tuples)
        for result in found:
            number = int(result[0])
            if keys[number] is not None:
                continue
            values = [
                _wire(result[1 + 2 * index].decode(), result[2 + 2 * index])
                for index in range(len(target_key))
            ]
            keys[number] = values
        out.append({"values": tuples, "keys": keys})
    return out


def _count(
    connection: sqlite3.Connection, spec: dict[str, Any], deadline: float
) -> dict[str, Any] | None:
    """The query's count, capped at :data:`COUNT_CAP`: exact up to it, and otherwise the
    matches among the rows read, a lower bound. Values a filter or search could not
    examine are counted among the same rows."""
    connection.text_factory = bytes
    where, params, skips = _predicates(spec)
    table = f"{quote(str(spec['table']))} AS {ROW}"
    cap = int(spec.get("cap") or COUNT_CAP)
    if not where:
        rows, stopped = _fetch(
            connection, f"SELECT count(*) FROM (SELECT 1 FROM {table} LIMIT ?)", (cap + 1,)
        )
        if stopped or not rows:
            return None
        total = int(rows[0][0])
        return {"count": min(total, cap), "complete": total <= cap, "skipped": 0}
    match = " AND ".join(where)
    skip = " + ".join(skips) if skips else "0"
    rows, stopped = _fetch(
        connection,
        f"SELECT count(*), sum(m), sum(s) FROM (SELECT CASE WHEN {match} THEN 1 ELSE 0 END AS m, "
        f"({skip}) AS s "
        f"FROM {table} LIMIT ?)",
        [*params, cap + 1],
    )
    if stopped or not rows:
        return None
    scanned, matched, skipped = (int(value or 0) for value in rows[0])
    return {"count": matched, "complete": scanned <= cap, "skipped": skipped}


def _record(
    connection: sqlite3.Connection, spec: dict[str, Any], deadline: float
) -> dict[str, Any] | None:
    connection.text_factory = bytes
    inline = int(spec["inline"])
    columns = [str(name) for name in spec["columns"]]
    table = quote(str(spec["table"]))
    parts = [expr for column in columns for expr in _value_exprs(column, inline)]
    rowid = spec.get("rowid")
    if rowid is not None:
        parts.append(quote(rowid))
    select = ", ".join(parts) if parts else "1"
    if "position" in spec:
        key = [str(name) for name in spec["key"]]
        order = f" ORDER BY {', '.join(quote(name) for name in key)}" if key else ""
        sql = f"SELECT {select} FROM {table}{order} LIMIT 1 OFFSET ?"
        params: list[Any] = [int(spec["position"]) - 1]
    else:
        key = [str(name) for name in spec["key"]]
        marks, params = _binds(spec["values"])
        sql = f"SELECT {select} FROM {table} WHERE {_row_value(key)} = ({', '.join(marks)})"
    rows, stopped = _fetch(connection, sql, params, limit=1)
    if stopped:
        raise sqlite3.OperationalError("interrupted")
    if not rows:
        return None
    row = rows[0]
    cells = {column: _cell(row, index * 3) for index, column in enumerate(columns)}
    found = {"cells": cells, "rowid": row[len(columns) * 3] if rowid is not None else None}
    _budget(connection, deadline)
    _preview_cells(
        [found],
        _Previewer(connection, str(spec["table"]), rowid is not None, str(spec["encoding"])),
        inline,
        spec["preview"],
    )
    found["refs"] = _resolve(connection, spec, [found], deadline)
    found["backrefs"] = _backrefs(connection, spec, cells, deadline)
    return found


def _backrefs(
    connection: sqlite3.Connection,
    spec: dict[str, Any],
    cells: dict[str, Any],
    deadline: float,
) -> list[dict[str, Any]]:
    """For each foreign key that points at this table, how many of its table's rows name
    this record, capped as a page's count is, matched as a page's references are."""
    out: list[dict[str, Any]] = []
    for incoming in spec.get("referenced_by") or []:
        to = [str(name) for name in incoming["to"]]
        values = [cells[name][2] if name in cells else None for name in to]
        if any(value is None for value in values):
            out.append({"count": 0, "complete": True})
            continue
        if any(_previewed(value) for value in values):
            out.append({"count": 0, "complete": False})
            continue
        fields = [str(name) for name in incoming["fields"]]
        match, params = _references(str(spec["table"]), to, fields, values)
        _budget(connection, deadline)
        rows, stopped = _fetch(
            connection,
            f"SELECT count(*) FROM (SELECT 1 FROM {quote(str(incoming['table']))} AS {ROW} "
            f"WHERE {match} LIMIT ?)",
            [*params, COUNT_CAP + 1],
        )
        if stopped or not rows:
            out.append({"count": 0, "complete": False})
            continue
        total = int(rows[0][0])
        out.append({"count": min(total, COUNT_CAP), "complete": total <= COUNT_CAP})
    return out


# ── Requests ───────────────────────────────────────────────────


def _require_generation(path: Path, expected: str) -> None:
    try:
        current = sqlite_access.sqlite_generation(path)
    except FileNotFoundError:
        current = None
    if current != expected:
        raise sqlite_access.SqliteAccessError(
            "refused", "The database changed while opening this position. Read the table again."
        )


def _read[T](
    args: dict[str, Any],
    deadline: float,
    fn: Callable[[sqlite3.Connection, frozenset[str]], T],
    *,
    attempts: int | None = None,
) -> tuple[T, sqlite_access.Access]:
    """Run *fn* in one read, with the names this read refuses: none where virtual tables
    are read (``virtual_ok``, sent with every request and false when absent), and
    otherwise the virtual tables and their possible shadow tables, refused before *fn*
    runs its first statement."""
    if sqlite_access.library_version() < sqlite_access.READER_MINIMUM_LIBRARY:
        library = sqlite_access.library_report()
        raise sqlite_access.SqliteAccessError(
            "unsupported",
            f"Browsing tables and schema needs SQLite {library['minimum']} or later.",
            detail=f"Bounded value reads need SQLite {library['minimum']}; "
            f"this reader uses SQLite {library['version']}.",
        )
    virtual_ok = bool(args.get("virtual_ok"))

    def guarded(connection: sqlite3.Connection) -> T:
        denied: frozenset[str] = frozenset()
        if not virtual_ok:
            denied = _guest_denied(connection)
            if denied:
                sqlite_access.deny_reads(connection, denied)
        return fn(connection, denied)

    path = Path(str(args["path"]))
    expected_generation = args.get("expected_generation")
    if expected_generation is not None:
        _require_generation(path, str(expected_generation))
    value, access = sqlite_access.read(
        path,
        guarded,
        deadline=deadline,
        scratch=Path(str(args["scratch"])),
        immutable_content=bool(args.get("immutable_content")),
        attempts=attempts,
    )
    if access.plan.state == "without_log":
        raise sqlite_access.SqliteAccessError(
            "without_log",
            "This database's tables cannot be read without its log. Open Info for details.",
            detail=f"Cannot browse tables or schema {access.plan.reason}.",
        )
    if expected_generation is not None:
        _require_generation(path, str(expected_generation))
    return value, access


def _access(access: sqlite_access.Access) -> dict[str, Any]:
    return {
        "mode": access.plan.mode,
        "state": access.plan.state,
        "reason": access.plan.reason,
        "notices": list(access.notices),
    }


def _catalog_op(args: dict[str, Any], deadline: float) -> dict[str, Any]:
    value, access = _read(
        args, deadline, lambda connection, denied: catalog(connection, deadline, denied)
    )
    return {**value, "access": _access(access)}


def _describe_op(args: dict[str, Any], deadline: float) -> dict[str, Any] | None:
    value, _unused = _read(
        args,
        deadline,
        lambda connection, denied: describe(
            connection,
            str(args["table"]),
            deadline,
            denied=denied,
            sort_rows=int(args.get("sort_rows") or SORT_UNINDEXED_MAX_ROWS),
        ),
    )
    return value


def _ddl_op(args: dict[str, Any], deadline: float) -> dict[str, Any]:
    table = args.get("table")
    value, _unused = _read(
        args,
        deadline,
        lambda connection, denied: ddl(connection, str(table) if table else None, denied),
    )
    return value


def _rows_op(args: dict[str, Any], deadline: float) -> dict[str, Any]:
    spec = dict(args["spec"])
    page, _unused = _read(
        args, deadline, lambda connection, _denied: _page(connection, spec, deadline)
    )
    if page.get("toobig") or not spec.get("count"):
        return {**page, "count": None}
    try:
        counted, _unused = _read(
            args,
            deadline,
            lambda connection, _denied: _count(connection, spec, deadline),
            attempts=1,
        )
    except sqlite_access.SqliteAccessError:
        counted = None
    return {**page, "count": counted}


def _positions_op(args: dict[str, Any], deadline: float) -> list[int | None]:
    spec = dict(args["spec"])
    value, _unused = _read(
        args, deadline, lambda connection, _denied: _positions(connection, spec, deadline)
    )
    return value


def _record_op(args: dict[str, Any], deadline: float) -> dict[str, Any] | None:
    spec = dict(args["spec"])
    value, _unused = _read(
        args, deadline, lambda connection, _denied: _record(connection, spec, deadline)
    )
    return value


sqlite_access.OPS.update(
    {
        "sqlite_catalog": _catalog_op,
        "sqlite_describe": _describe_op,
        "sqlite_ddl": _ddl_op,
        "sqlite_rows": _rows_op,
        "sqlite_record": _record_op,
        "sqlite_positions": _positions_op,
    }
)
