"""The SQLite table source: a database's tables, views, and virtual tables.

The ``[[table_source]]`` adapter for the ``sqlite`` kind. A database is a navigation
container (Decision 9 of the tabular-data plan): each table is ``<database>/<segment>``
(:func:`~metabrowser.builtin_plugins.sqlite.database.table_segment`), and a table's id
in every answer is that segment, so a reference, a ``ref=`` filter, and the table view
address a table as the tree does. The database itself is no table; its tables route
lists them.

Every read is a reader process request (``reader.py`` holds the SQL); this module turns
what a request answers into the protocol's descriptors, cells, keys, and cursors.

- **Keys.** A rowid table's rows are keyed by the rowid: its integer primary key, or a
  hidden ``rowid`` field (``_rowid_`` or ``oid`` when a column takes the name). A
  ``WITHOUT ROWID`` table's by its primary key. A view's and a virtual table's rows have
  no key and are named by their position in the object's own order. A key whose token
  would pass ``TABLE_TOKEN_MAX_CHARS`` is named by its position in key order instead.
- **Types.** A field's type comes from its declared type, as SQLite gives it an
  affinity, with ``BOOL``, ``DATE``, ``DATETIME``/``TIMESTAMP``, and ``JSON`` named; a
  value whose stored type its affinity would not hold is ``{value, stored}``.
- **Sorting.** Every field sorts while the object holds at most
  :data:`~metabrowser.builtin_plugins.sqlite.reader.SORT_UNINDEXED_MAX_ROWS` rows; past
  that, only the key and fields an index leads with, and the rest say why in
  ``sort_note``.
- **Counts** are exact up to :data:`~metabrowser.builtin_plugins.sqlite.reader.COUNT_CAP`
  and otherwise a lower bound. The first page counts separately. If that count fails,
  the filtered page reports the matches it found and the unfiltered page can use the
  catalog's estimate. A search continues from the last row it examined, even if it
  had no matches in that window.
- **References** are the declared foreign keys, resolved for a page in one batch; a
  value no row of the referenced table holds is a reference drawn as missing.
- **Values.** A text or blob past the inline bound is previewed through ``blobopen`` in
  a rowid table (``{text, bytes}`` or a blob's hex, with its size) and otherwise sent as
  its size alone (``{length, preview: false}``).
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Sequence
from typing import Any, Final, cast

from metabrowser.builtin_plugins.sqlite import reader
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
from metabrowser.builtin_plugins.sqlite.reader import COUNT_CAP, PAGE_INLINE_BYTES
from metabrowser.plugin_api import (
    TABLE_CARD_MAX_FIELDS,
    TABLE_CELL_PREVIEW_CHARS,
    TABLE_RECORD_VALUE_BYTES,
    TABLE_TOKEN_MAX_CHARS,
    BackrefCount,
    Budget,
    Cell,
    FieldRef,
    FieldType,
    RecordNotFoundError,
    RefFilter,
    SourceUnreadableError,
    TableCard,
    TableField,
    TableHandle,
    TableInfo,
    TableNotFoundError,
    TablePage,
    TableQuery,
    TableQueryError,
    TableRecord,
    TableRow,
    TableSchema,
    TableSourceError,
    blob_cell,
    coerce_filter_value,
    cut_utf8,
    decode_cursor,
    decode_key,
    encode_cursor,
    encode_key,
    integer_cell,
    page_columns,
    page_row_limit,
    parse_position_key,
    parse_positional_cursor,
    position_key,
    positional_cursor,
    text_cell,
)
from metabrowser.sqlite_access import VALUE_MAX_BYTES, SqliteAccessError
from metabrowser.sqlite_readers import BLOB_MAX_BYTES, request_deadline

# Bytes of a stored text a page previews through `blobopen`: the preview's characters at
# four bytes each, the most UTF-8 or UTF-16 spends on one, so the cut is the
# characters', not the bytes'.
_PAGE_TEXT_BYTES: Final = TABLE_CELL_PREVIEW_CHARS * 4
# Bytes of a blob a page shows as hex: as many hex digits as a text cell's characters.
_PAGE_BLOB_BYTES: Final = TABLE_CELL_PREVIEW_CHARS // 2
# A record's previews: its value bound, in UTF-8 for text and in bytes for a blob, whose
# hex is twice as long.
_RECORD_TEXT_BYTES: Final = TABLE_RECORD_VALUE_BYTES * 2
_RECORD_BLOB_BYTES: Final = TABLE_RECORD_VALUE_BYTES // 2

_BUSY_STATES: Final = frozenset({"busy", "writer_busy", "changing", "reader_stopped"})

# Why a described object is not read, as its refusal says it (`reader.describe`).
_GUEST: Final = (
    "which is listed but not read here: a virtual table's module code would run on this "
    "file's content, which is not trusted"
)
_UNREAD: Final = {
    "virtual": f"is a virtual table, {_GUEST}",
    "shadow": f"may be a virtual table's shadow table, {_GUEST}",
    "reads_virtual": f"reads a virtual table, {_GUEST}",
    "key_collation": "has a primary key that uses an unavailable SQLite collation",
    "module": (
        "is a virtual table whose module prepares write statements when it opens, as "
        "SQLite's R-tree module does, and this reader allows read statements only; an "
        "R-tree is an index over tables that are read"
    ),
}


class SourceBusyError(TableSourceError):
    """An expected conflict with the database or reader's current state."""

    code = "source_busy"
    # Data hooks reserve 5xx statuses for failures of the plugin itself.
    http_status = 409


# The refusal of a sort or filter on a table with no row key to read it by in parts.
_UNSORTABLE: Final = (
    "This table is too large to sort or filter. Open it in its original order without a filter."
)


def access_error(exc: SqliteAccessError) -> TableSourceError:
    """A reader's refusal as the table routes answer it, naming its state."""
    detail = {"detail": exc.detail} if exc.detail else {}
    if exc.state in _BUSY_STATES:
        return SourceBusyError(str(exc), state=exc.state, **detail)
    return SourceUnreadableError(str(exc), state=exc.state, **detail)


# ── Types ──────────────────────────────────────────────────────

type Affinity = str


def affinity(declared: str) -> Affinity:
    """The affinity SQLite gives a declared type (sqlite.org/datatype3.html, 3.1)."""
    upper = declared.upper()
    if "INT" in upper:
        return "integer"
    if any(part in upper for part in ("CHAR", "CLOB", "TEXT")):
        return "text"
    if "BLOB" in upper or not upper.strip():
        return "blob"
    # SQLite's rule matches the first four letters of each; the names in use spell them out.
    if any(part in upper for part in ("REAL", "FLOAT", "DOUBLE")):
        return "real"
    return "numeric"


def field_type(declared: str) -> FieldType:
    upper = declared.upper()
    if "BOOL" in upper:
        return "boolean"
    if "DATETIME" in upper or "TIMESTAMP" in upper:
        return "datetime"
    if "DATE" in upper:
        return "date"
    if "JSON" in upper:
        return "json"
    found = affinity(declared)
    if found == "integer":
        return "integer"
    if found == "text":
        return "text"
    if found == "real" or found == "numeric":
        return "real" if upper.strip() not in ("ANY",) else "unknown"
    return "blob" if upper.strip() else "unknown"


# The stored types a column of each affinity holds as itself; any other is shown as
# stored. A blob is stored as itself under every affinity, so it differs from all but
# `blob`'s.
_HELD: Final[dict[Affinity, frozenset[str]]] = {
    "integer": frozenset({"integer"}),
    "real": frozenset({"real"}),
    "numeric": frozenset({"integer", "real"}),
    "text": frozenset({"text"}),
    "blob": frozenset({"integer", "real", "text", "blob"}),
}
_STORED: Final[dict[str, FieldType]] = {
    "integer": "integer",
    "real": "real",
    "text": "text",
    "blob": "blob",
}


def _held(declared: str, kind: FieldType) -> frozenset[str]:
    if kind in ("date", "datetime", "json"):
        return frozenset({"text", "integer", "real"})
    if kind == "boolean":
        # 0 and 1 are drawn as false and true before this is asked; any other value is
        # not a boolean, whatever its type.
        return frozenset()
    if declared.strip().upper() == "ANY":
        return _HELD["blob"]
    return _HELD[affinity(declared)]


# ── The source ─────────────────────────────────────────────────


class SqliteSource:
    """One database's tables, through reader processes.

    The database is the file *handle* names, unless *opener* finds it: the fsqlite
    plugin's store reads the snapshot its ``current`` names this way, under the store's
    generation. An opener raises ``OSError`` for a file that is gone,
    :class:`~metabrowser.sqlite_access.SqliteAccessError` for one a reader refused, or a
    :class:`TableSourceError` of its own.
    """

    def __init__(self, handle: TableHandle, opener: Callable[[], Database] | None = None) -> None:
        self._handle = handle
        self._subject = subject_key()
        self._database: Database | None = None
        self._opener = opener

    # ── The database ──

    def _open(self) -> Database:
        if self._database is not None:
            return self._database
        handle = self._handle
        try:
            if self._opener is not None:
                self._database = self._opener()
            elif handle.local_path is not None:
                self._database = served_database(handle.local_path, self._subject)
            else:
                if handle.ref.stored_size is not None and handle.ref.stored_size > BLOB_MAX_BYTES:
                    raise blob_too_large()
                self._database = written_pinned_database(handle.ref, self._subject)
                if self._database is None:
                    window = handle.read_window(max_bytes=BLOB_MAX_BYTES + 1)
                    self._database = pinned_database(handle.ref, window.data, self._subject)
        except OSError as exc:
            raise SourceUnreadableError("This file is no longer available.") from exc
        except SqliteAccessError as exc:
            raise access_error(exc) from exc
        return self._database

    def _call(self, op: str, args: dict[str, Any], deadline: float) -> Any:
        try:
            return self._open().call(op, args, deadline=deadline)
        except SqliteAccessError as exc:
            raise access_error(exc) from exc

    def _cached(self, what: str, name: str, deadline: float) -> Any:
        try:
            return cached(self._open(), what, name, deadline=deadline)
        except SqliteAccessError as exc:
            raise access_error(exc) from exc

    def _catalog(self, deadline: float) -> dict[str, Any]:
        return cast(dict[str, Any], self._cached("catalog", "", deadline))

    def _describe(self, table: str, deadline: float) -> dict[str, Any]:
        name = segment_name(table) if table else None
        if name is None:
            raise TableNotFoundError(f"no table {table!r} in this database", table=table)
        found = self._cached("describe", name, deadline)
        if found is None:
            raise TableNotFoundError(f"no table {table!r} in this database", table=table)
        description = cast(dict[str, Any], found)
        if not description["readable"]:
            raise SourceUnreadableError(
                f"{description['name']!r} {_UNREAD[str(description['unread'])]}.",
                table=table,
            )
        return description

    def _estimate(self, name: str, deadline: float) -> int | None:
        for item in self._catalog(deadline)["objects"]:
            if item["name"] == name:
                return cast(int | None, item["estimate"])
        return None

    # ── The protocol ──

    def generation(self) -> str:
        return self._open().generation

    def tables(self) -> Sequence[TableInfo]:
        return catalog_tables(self._catalog(request_deadline()))

    def schema(self, table: str) -> TableSchema:
        return _schema(self._describe(table, request_deadline()), table)

    def rows(self, table: str, query: TableQuery, budget: Budget) -> TablePage:
        deadline = budget.deadline
        description = self._describe(table, deadline)
        schema = _schema(description, table)
        generation = self.generation()
        columns = page_columns(query, schema)
        limit = page_row_limit(query.limit, max(1, len(columns)))
        spec = self._spec(description, schema, columns, deadline)
        spec.update(
            {
                "sort": query.sort if query.sort else None,
                "order": query.order,
                "filters": _filters(schema, description, query),
                "limit": limit,
                "inline": PAGE_INLINE_BYTES,
                "preview": {"text": _PAGE_TEXT_BYTES, "blob": _PAGE_BLOB_BYTES},
                "count": query.after is None,
                "cap": COUNT_CAP,
            }
        )
        searched: tuple[str, ...] | None = None
        if query.q is not None:
            fields = [
                item.name
                for item in schema.fields
                if item.type in ("text", "unknown") and not item.hidden
            ]
            searched = tuple(fields)
            spec["search"] = {
                "fields": list(fields),
                "needle": query.q,
            }
        if query.ref is not None:
            spec["ref"] = self._ref_filter(schema, query.ref, deadline)
        filtered = bool(spec["filters"] or query.q is not None or query.ref is not None)
        if filtered:
            spec["scan_rows"] = reader.FILTER_SCAN_ROWS
        rows_upto = description["rows_upto"]
        if (
            not description["key"]
            and (filtered or query.order == "desc" or query.sort is not None)
            and (rows_upto is None or rows_upto > reader.SORT_UNINDEXED_MAX_ROWS)
        ):
            raise SourceUnreadableError(
                _UNSORTABLE,
                table=table,
                detail="This object has no stable row key and is too large to sort or filter "
                "within one read.",
            )
        served = 0
        if query.after is not None:
            positional = parse_positional_cursor(query.after)
            if positional is not None:
                served, minted = positional
                if minted != generation:
                    return _empty(
                        columns, generation, limit, reason="cursor_expired", searched=searched
                    )
                spec["after"] = {"offset": served}
            else:
                spec["after"], served = _cursor_point(
                    decode_cursor(query.after), query, description
                )
        answer = cast(dict[str, Any], self._call("sqlite_rows", {"spec": spec}, deadline))
        if answer.get("toobig"):
            if query.sort is not None:
                raise TableQueryError(
                    f"Column {query.sort!r} holds a value too large to sort by.",
                    param="sort",
                    field=query.sort,
                    detail=f"field {query.sort!r} holds a value longer than "
                    f"{VALUE_MAX_BYTES:,} bytes, so it cannot be sorted",
                )
            # A keyless object is numbered in its own order by a statement that holds
            # every value of each row, so one past the limit stops it.
            raise SourceUnreadableError(
                _UNSORTABLE,
                table=table,
                detail=f"a row holds a value longer than {VALUE_MAX_BYTES:,} bytes, so rows "
                "with no key can be read only in their own order, unfiltered",
            )
        found = cast(list[dict[str, Any]], answer["rows"])
        counted = cast(dict[str, Any] | None, answer.get("count"))
        estimate = None if filtered else self._estimate(str(description["name"]), deadline)
        count = counted["count"] if counted is not None else None
        count_complete = bool(counted and counted["complete"])
        skipped = int(counted["skipped"]) if counted is not None else 0
        stopped = bool(answer["stopped"])
        point = cast(dict[str, Any] | None, answer.get("point"))
        examined = cast(int | None, answer.get("examined"))
        if stopped and point is None and not found and query.sort is not None:
            # A sort cannot be returned in part.
            return _empty(
                columns,
                generation,
                limit,
                reason="sort_budget",
                searched=searched,
                sort_refused=query.sort,
                count=count,
                count_complete=count_complete,
                estimate=estimate,
            )
        keys = self._row_keys(description, spec, found, deadline)
        fields = {item.name: item for item in schema.fields}
        refs = _ref_lookup(spec, answer.get("refs") or [])
        rows = tuple(
            TableRow(
                key=keys[index],
                cells=_cells(
                    row["cells"],
                    fields,
                    description,
                    refs,
                    max_chars=TABLE_CELL_PREVIEW_CHARS,
                    blob_bytes=_PAGE_BLOB_BYTES,
                ),
            )
            for index, row in enumerate(found)
        )
        next_after: str | None = None
        if point is None and found:
            point = found[-1]
        reached = served + (examined if examined is not None else len(found))
        if point is not None and (answer["more"] or stopped):
            next_after = _next_cursor(query, point, reached, generation)
        if filtered and counted is None and query.after is None:
            count = len(found)
            count_complete = not stopped and next_after is None
        return TablePage(
            rows=rows,
            columns=columns,
            next_after=next_after,
            complete=not stopped,
            truncated=False,
            generation=generation,
            count=count,
            count_complete=count_complete,
            estimate=estimate,
            skipped=skipped,
            searched=searched,
            examined=reached if filtered and (stopped or served) else None,
            reason="budget" if stopped else None,
            limit=limit,
        )

    def record(self, table: str, key: str, budget: Budget) -> TableRecord:
        description = self._describe(table, budget.deadline)
        schema = _schema(description, table)
        names = [item.name for item in schema.fields]
        found = self._read_record(
            description,
            schema,
            table,
            key,
            names,
            budget.deadline,
            inline=TABLE_RECORD_VALUE_BYTES,
            preview={"text": _RECORD_TEXT_BYTES, "blob": _RECORD_BLOB_BYTES},
            backrefs=True,
        )
        fields = {item.name: item for item in schema.fields}
        cells = _cells(
            found["cells"],
            fields,
            description,
            _ref_lookup(found["spec"], found.get("refs") or []),
            max_bytes=TABLE_RECORD_VALUE_BYTES,
            blob_bytes=_RECORD_BLOB_BYTES,
        )
        referenced_by = tuple(
            BackrefCount(
                ref=ref, count=int(counted["count"]), count_complete=bool(counted["complete"])
            )
            for ref, counted in zip(schema.referenced_by, found.get("backrefs") or [], strict=False)
        )
        label = cells.get(_label_field(schema))
        return TableRecord(
            key=key,
            cells=cells,
            generation=self.generation(),
            positional=key.startswith("@"),
            referenced_by=referenced_by,
            label=label[:TABLE_CELL_PREVIEW_CHARS]
            if isinstance(label, str) and label.strip()
            else None,
        )

    def card(self, table: str, key: str, budget: Budget) -> TableCard:
        description = self._describe(table, budget.deadline)
        schema = _schema(description, table)
        label = _label_field(schema)
        names = [label, *[name for name in schema.default_columns if name != label]]
        names = names[: TABLE_CARD_MAX_FIELDS + 1]
        found = self._read_record(
            description,
            schema,
            table,
            key,
            names,
            budget.deadline,
            inline=PAGE_INLINE_BYTES,
            preview={"text": _PAGE_TEXT_BYTES, "blob": _PAGE_BLOB_BYTES},
            backrefs=False,
        )
        fields = {item.name: item for item in schema.fields}
        cells = _cells(
            found["cells"],
            fields,
            description,
            _ref_lookup(found["spec"], found.get("refs") or []),
            max_chars=TABLE_CELL_PREVIEW_CHARS,
            blob_bytes=_PAGE_BLOB_BYTES,
        )
        label_cell = cells.pop(label, None)
        return TableCard(key=key, label=label_cell, cells=cells, generation=self.generation())

    # ── Reads ──

    def _spec(
        self,
        description: dict[str, Any],
        schema: TableSchema,
        names: Sequence[str],
        deadline: float,
    ) -> dict[str, Any]:
        """What every read of rows names: the object, its key, the columns read, the
        rowid that previews a long value, and the references to resolve."""
        refs: list[dict[str, Any]] = []
        wanted = set(names)
        catalog = self._catalog(deadline)
        by_name = {item["name"]: item for item in catalog["objects"]}
        for fk in description["foreign_keys"]:
            if not set(fk["from"]) <= wanted:
                continue
            target = by_name.get(fk["table"])
            if target is None or not target["key"]:
                continue
            refs.append(
                {
                    "fields": fk["from"],
                    "table": target["name"],
                    "to": fk["to"],
                    "key": target["key"],
                }
            )
        return {
            "table": description["name"],
            "key": description["key"],
            "rowid": _rowid(description),
            "position_name": reader.position_name(
                str(column["name"]) for column in description["columns"]
            ),
            "columns": list(names),
            "token_bytes": TABLE_TOKEN_MAX_CHARS,
            "encoding": str(catalog["encoding"]),
            "refs": refs,
        }

    def _ref_filter(
        self,
        schema: TableSchema,
        relationship: RefFilter,
        deadline: float,
    ) -> list[dict[str, Any]]:
        """Resolve the target values for each foreign key selected by the filter."""
        options: list[dict[str, Any]] = []
        target_table = relationship.table
        target = self._describe(target_table, deadline)
        target_schema = _schema(target, target_table)
        for ref in schema.references:
            if not relationship.matches(ref):
                continue
            found = self._read_record(
                target,
                target_schema,
                target_table,
                relationship.key,
                list(ref.to),
                deadline,
                inline=VALUE_MAX_BYTES,
                preview={"text": 0, "blob": 0},
                backrefs=False,
                resolve=False,
            )
            values = [found["cells"][name][2] for name in ref.to]
            if any(
                value is None or (isinstance(value, dict) and ("pt" in value or "pb" in value))
                for value in values
            ):
                continue
            options.append(
                {
                    "table": target["name"],
                    "to": list(ref.to),
                    "fields": list(ref.fields),
                    "values": values,
                }
            )
        return options

    def _read_record(
        self,
        description: dict[str, Any],
        schema: TableSchema,
        table: str,
        key: str,
        names: Sequence[str],
        deadline: float,
        *,
        inline: int,
        preview: dict[str, int],
        backrefs: bool,
        resolve: bool = True,
    ) -> dict[str, Any]:
        spec = self._spec(description, schema, names, deadline)
        if not resolve:
            spec["refs"] = []
        spec.update({"inline": inline, "preview": preview})
        position = parse_position_key(key)
        if position is not None:
            spec["position"] = position
        else:
            if not description["key"]:
                raise RecordNotFoundError(f"{key!r} names no row of this table", key=key)
            try:
                values = decode_key(key)
            except TableQueryError as exc:
                raise RecordNotFoundError(f"{key!r} names no row of this table", key=key) from exc
            if len(values) != len(description["key"]):
                raise RecordNotFoundError(f"{key!r} names no row of this table", key=key)
            spec["values"] = values
        if backrefs:
            spec["referenced_by"] = [
                {"table": item["table"], "fields": item["from"], "to": item["to"]}
                for item in description["referenced_by"]
            ]
        args: dict[str, Any] = {"spec": spec}
        if position is not None and not self._open().immutable:
            # A live positional key names a row only within the sampled generation.
            args["expected_generation"] = self.generation()
        found = self._call("sqlite_record", args, deadline)
        if found is None:
            raise RecordNotFoundError(f"{key!r} names no row of this table", key=key)
        record = cast(dict[str, Any], found)
        record["spec"] = spec
        return record

    def _row_keys(
        self,
        description: dict[str, Any],
        spec: dict[str, Any],
        rows: list[dict[str, Any]],
        deadline: float,
    ) -> list[str]:
        """Each row's name: its key token, or its position where it has no key or its key
        is too long for a token."""
        if not description["key"]:
            return [position_key(int(row["key"][0])) for row in rows]
        names: list[str | None] = []
        missing: list[int] = []
        for index, row in enumerate(rows):
            token = encode_key(row["key"]) if None not in row["key"] else None
            names.append(token)
            if token is None:
                missing.append(index)
        if missing:
            positions = cast(
                list[int | None],
                self._call(
                    "sqlite_positions",
                    {
                        "spec": {
                            "table": spec["table"],
                            "key": spec["key"],
                            "keys": [rows[index]["key"] for index in missing],
                        }
                    },
                    deadline,
                ),
            )
            for index, position in zip(missing, positions, strict=True):
                if position is None:
                    raise SourceUnreadableError(
                        "A row on this page has a key too large to link to.",
                        table=description["name"],
                        detail="A row's key is too large to name it by",
                    )
                names[index] = position_key(position)
        return [name or "" for name in names]


def catalog_tables(catalog: dict[str, Any]) -> tuple[TableInfo, ...]:
    """The tables a reader's ``sqlite_catalog`` answer lists, each named by its segment."""
    return tuple(
        TableInfo(
            id=table_segment(str(item["name"])),
            label=str(item["name"]),
            group=item["group"],
            keyed=bool(item["keyed"]),
            estimate=item["estimate"],
        )
        for item in catalog["objects"]
    )


def adapter(handle: TableHandle) -> SqliteSource:
    """The `[[table_source]]` adapter for the `sqlite` kind."""
    return SqliteSource(handle)


# ── Schemas ────────────────────────────────────────────────────


def _rowid(description: dict[str, Any]) -> str | None:
    """The column whose value is a row's rowid, for `blobopen`: the rowid alias or the
    integer primary key; None for a table without one, a view, or a virtual table."""
    if description["type"] != "table" or description["without_rowid"] or not description["key"]:
        return None
    return str(description["key"][0])


def _sortable(description: dict[str, Any]) -> tuple[set[str], str | None]:
    """The fields that sort past the unindexed bound, and the note for the rest."""
    limit = reader.SORT_UNINDEXED_MAX_ROWS
    upto = description["rows_upto"]
    if upto is not None and upto <= limit:
        return {column["name"] for column in description["columns"]} | set(description["key"]), None
    fast = set(description["key"][:1])
    for index in description["indexes"]:
        if not index["partial"] and index["columns"] and index["columns"][0]:
            fast.add(str(index["columns"][0]))
    if upto is None:
        note = (
            "only indexed fields sort here: counting this object's rows to see whether a "
            "sort could read them all ran out of its budget"
        )
    else:
        note = (
            f"only indexed fields sort in an object of more than {limit:,} "
            "rows: a sort of this field would read and sort every row first"
        )
    return fast, note


def _schema(description: dict[str, Any], table: str) -> TableSchema:
    columns = cast(list[dict[str, Any]], description["columns"])
    key = [str(name) for name in description["key"]]
    alias = description["rowid_alias"]
    sortable, note = _sortable(description)
    refs_by_field: dict[str, FieldRef] = {}
    references: list[FieldRef] = []
    for fk in description["foreign_keys"]:
        ref = FieldRef(
            table=table_segment(str(fk["table"])), fields=tuple(fk["from"]), to=tuple(fk["to"])
        )
        references.append(ref)
        for name in fk["from"]:
            refs_by_field.setdefault(name, ref)
    fields: list[TableField] = []
    if alias is not None:
        fields.append(
            TableField(
                name=alias,
                type="integer",
                title=alias,
                declared_type="INTEGER",
                nullable=False,
                key=True,
                hidden=True,
                sortable=True,
                filterable=True,
                numeric=True,
            )
        )
    defaults: list[str] = []
    for column in columns:
        name = str(column["name"])
        declared = str(column["declared"])
        kind = field_type(declared)
        hidden = column["hidden"] == 1
        if not hidden:
            defaults.append(name)
        fields.append(
            TableField(
                name=name,
                type=kind,
                declared_type=declared or None,
                nullable=not (column["notnull"] or name in key),
                key=name in key,
                hidden=hidden,
                generated=column["hidden"] in (2, 3),
                ref=refs_by_field.get(name),
                sortable=name in sortable,
                sort_note=None if name in sortable else note,
                filterable=kind != "blob",
                numeric=kind in ("integer", "real"),
            )
        )
    referenced_by = tuple(
        FieldRef(
            table=table_segment(str(item["table"])),
            fields=tuple(item["from"]),
            to=tuple(item["to"]),
        )
        for item in description["referenced_by"]
    )
    return TableSchema(
        table=table,
        fields=tuple(fields),
        key=tuple(key),
        default_columns=tuple(defaults),
        references=tuple(references),
        referenced_by=referenced_by,
    )


def _label_field(schema: TableSchema) -> str:
    """Prefer a descriptive column for a record and its card."""
    visible_text = {
        item.name.casefold(): item.name
        for item in schema.fields
        if item.type == "text" and not item.key and not item.hidden
    }
    for preferred in ("name", "title", "label"):
        if preferred in visible_text:
            return visible_text[preferred]
    if visible_text:
        return next(iter(visible_text.values()))
    return schema.default_columns[0] if schema.default_columns else schema.fields[0].name


def _filters(
    schema: TableSchema, description: dict[str, Any], query: TableQuery
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in query.filters:
        target = schema.field_named(item.field)
        if target is None:  # check_table_query refused it already
            continue
        value: Any = None
        if item.value is not None and item.op not in ("null", "notnull"):
            if item.op == "contains":
                value = item.value
            else:
                typed = coerce_filter_value(target, item.value)
                value = int(typed) if isinstance(typed, bool) else typed
        out.append({"field": item.field, "op": item.op, "value": value})
    return out


# ── Cursors ────────────────────────────────────────────────────
#
# A `c.` cursor is `[sort, order, region, value, key, served]`: the field the query sorted
# by (null for key order) and its order, so a cursor sent with another sort is refused by
# name; the region the last row was in (`n` the sort field's nulls, `v` its values, `k`
# key order); that row's sort value and key (its position for a keyless object); and the
# rows served before the next page, which a cursor past the token bound continues from.


def _cursor_point(
    values: list[Any], query: TableQuery, description: dict[str, Any]
) -> tuple[dict[str, Any], int]:
    def bad(detail: str) -> TableQueryError:
        return TableQueryError(f"after is not a cursor for this query: {detail}", param="after")

    if len(values) != 6:
        raise bad("it has the wrong number of parts")
    sort, order, region, value, key, served = values
    if sort != query.sort or order != query.order:
        raise bad(f"it was made for sort={json.dumps(sort)} order={json.dumps(order)}")
    regions = ("k",) if query.sort is None else ("n", "v")
    if region not in regions:
        raise bad("its region is not one of this query's")
    width = len(description["key"]) or 1
    if not isinstance(key, list) or len(cast(list[Any], key)) != width:
        raise bad("its key does not fit this table's")
    if type(served) is not int or served < 0:
        raise bad("its count of rows served is not a count")
    for item in [value, *cast(list[Any], key)]:
        if not _is_value(item):
            raise bad("it holds something that is not a value")
    if not description["key"] and type(cast(list[Any], key)[0]) is not int:
        raise bad("its position is not an integer")
    return {"region": region, "value": value, "key": key}, served


def _is_value(item: Any) -> bool:
    if item is None or type(item) in (int, float, str):
        return True
    if isinstance(item, dict):
        envelope = cast(dict[str, Any], item)
        if len(envelope) != 1:
            return False
        ((name, inner),) = envelope.items()
        if name == "real":
            return inner in ("inf", "-inf", "nan")
        if name in ("tx", "x") and isinstance(inner, str):
            try:
                bytes.fromhex(inner)
            except ValueError:
                return False
            return True
    return False


def _next_cursor(query: TableQuery, last: dict[str, Any], served: int, generation: str) -> str:
    if None in last["key"] or (last["region"] == "v" and last["sort"] is None):
        return positional_cursor(served, generation)
    token = encode_cursor(
        [query.sort, query.order, last.get("region", "k"), last.get("sort"), last["key"], served]
    )
    return token if token is not None else positional_cursor(served, generation)


def _empty(
    columns: tuple[str, ...],
    generation: str,
    limit: int,
    *,
    reason: Any,
    searched: tuple[str, ...] | None,
    sort_refused: str | None = None,
    count: int | None = None,
    count_complete: bool = False,
    estimate: int | None = None,
) -> TablePage:
    return TablePage(
        rows=(),
        columns=columns,
        next_after=None,
        complete=False,
        truncated=False,
        generation=generation,
        count=count,
        count_complete=count_complete,
        estimate=estimate,
        searched=searched,
        reason=reason,
        sort_refused=sort_refused,
        limit=limit,
    )


# ── Cells ──────────────────────────────────────────────────────

type RefLookup = dict[str, dict[str, Any]]


def _ref_lookup(spec: dict[str, Any], resolved: list[dict[str, Any]]) -> RefLookup:
    """For each referencing field, the referenced row's key by the values that name it:
    `{field: {"ref": FieldRef wire, "keys": {values json: key or None}}}`."""
    out: RefLookup = {}
    for ref, answer in zip(spec.get("refs") or [], resolved, strict=False):
        keys: dict[str, Any] = {}
        for values, key in zip(answer["values"], answer["keys"], strict=True):
            keys[json.dumps(values, sort_keys=True)] = key
        entry = {"table": table_segment(str(ref["table"])), "fields": ref["fields"], "keys": keys}
        for name in ref["fields"]:
            out.setdefault(name, entry)
    return out


def _cells(
    raw: dict[str, list[Any]],
    fields: dict[str, TableField],
    description: dict[str, Any],
    refs: RefLookup,
    *,
    max_chars: int | None = None,
    max_bytes: int | None = None,
    blob_bytes: int,
) -> dict[str, Cell]:
    declared = {str(column["name"]): str(column["declared"]) for column in description["columns"]}
    cells: dict[str, Cell] = {}
    for name, value in raw.items():
        item = fields.get(name)
        kind: FieldType = item.type if item is not None else "unknown"
        cell = _cell(
            value,
            kind,
            declared.get(name, "INTEGER" if item is not None and item.hidden else ""),
            max_chars=max_chars,
            max_bytes=max_bytes,
            blob_bytes=blob_bytes,
        )
        ref = refs.get(name)
        if ref is not None and value[0] != "null":
            cell = _reference(cell, ref, raw)
        cells[name] = cell
    return cells


def _reference(cell: Cell, ref: dict[str, Any], raw: dict[str, list[Any]]) -> Cell:
    values = [raw[name][2] if name in raw else None for name in ref["fields"]]
    marker = json.dumps(values, sort_keys=True)
    if marker not in ref["keys"]:
        return cell
    key = ref["keys"][marker]
    label = cell
    if isinstance(cell, dict) and "value" in cell and "stored" in cell:
        label = cast(dict[str, Any], cell)["value"]
    if key is None:
        return {"ref": {"table": ref["table"], "key": None, "label": label, "missing": True}}
    token = encode_key(key)
    if token is None:
        return cell
    return {"ref": {"table": ref["table"], "key": token, "label": label}}


def _cell(
    value: list[Any],
    kind: FieldType,
    declared: str,
    *,
    max_chars: int | None,
    max_bytes: int | None,
    blob_bytes: int,
) -> Cell:
    stored, size, wire = value
    if stored == "null":
        return None
    cell = _plain(
        stored, size, wire, kind, max_chars=max_chars, max_bytes=max_bytes, blob_bytes=blob_bytes
    )
    if kind == "boolean" and stored == "integer" and wire in (0, 1):
        return bool(wire)
    if stored not in _held(declared, kind) and stored in _STORED:
        return {"value": cell, "stored": _STORED[stored]}
    return cell


_NOT_JSON: Final = object()
# Match the structured diff projection's nesting limit for a bounded preview tree.
_JSON_CELL_MAX_DEPTH: Final = 64


def _refuse_constant(name: str) -> Any:
    raise ValueError(f"{name} is not JSON")


def _json_value_fits(value: Any, remaining_depth: int) -> bool:
    if isinstance(value, dict):
        return remaining_depth > 0 and all(
            _json_value_fits(item, remaining_depth - 1) for item in value.values()
        )
    if isinstance(value, list):
        return remaining_depth > 0 and all(
            _json_value_fits(item, remaining_depth - 1) for item in value
        )
    return not isinstance(value, float) or math.isfinite(value)


def _json(text: str) -> Any:
    """Keep malformed, overly nested, or nonfinite values as text."""
    try:
        value = json.loads(text, parse_constant=_refuse_constant)
    except (ValueError, RecursionError):
        return _NOT_JSON
    return value if _json_value_fits(value, _JSON_CELL_MAX_DEPTH) else _NOT_JSON


def _fits(text: str, *, max_chars: int | None, max_bytes: int | None) -> bool:
    """Whether *text* is shown whole under the cell's bound, the only case its JSON is
    parsed: a page's characters or a record's bytes."""
    if max_chars is not None and len(text) > max_chars:
        return False
    return max_bytes is None or len(text.encode("utf-8", "surrogatepass")) <= max_bytes


def _plain(
    stored: str,
    size: int,
    wire: Any,
    kind: FieldType,
    *,
    max_chars: int | None,
    max_bytes: int | None,
    blob_bytes: int,
) -> Cell:
    if stored == "integer" and type(wire) is int:
        return integer_cell(wire)
    if stored == "real":
        return wire  # a finite real, or already `{real: ...}`
    if stored == "text":
        if isinstance(wire, str):
            if kind == "json" and _fits(wire, max_chars=max_chars, max_bytes=max_bytes):
                parsed = _json(wire)
                if parsed is not _NOT_JSON:
                    return {"json": parsed, "preview": wire}
            return text_cell(wire, max_chars=max_chars, max_bytes=max_bytes)
        if isinstance(wire, dict):
            envelope = cast(dict[str, Any], wire)
            if "tx" in envelope:
                text = bytes.fromhex(str(envelope["tx"])).decode("utf-8", "replace")
                return text_cell(text, max_chars=max_chars, max_bytes=max_bytes, invalid_utf8=True)
            if "pt" in envelope:
                text = str(envelope["pt"])
                if max_chars is not None:
                    text = text[:max_chars]
                if max_bytes is not None:
                    text = cut_utf8(text, max_bytes)
                cut: dict[str, Any] = {"text": text, "bytes": size}
                if envelope.get("inv"):
                    cut["invalid_utf8"] = True
                return cut
        return {"length": size, "preview": False}
    if stored == "blob":
        if isinstance(wire, dict):
            envelope = cast(dict[str, Any], wire)
            if "x" in envelope:
                return blob_cell(bytes.fromhex(str(envelope["x"])), max_bytes=blob_bytes)
            if "pb" in envelope:
                return blob_cell(
                    bytes.fromhex(str(envelope["pb"])), length=size, max_bytes=blob_bytes
                )
        return {"length": size, "preview": False}
    return wire
