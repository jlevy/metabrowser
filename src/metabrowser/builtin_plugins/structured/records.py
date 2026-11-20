"""The record-list table source: a JSON or YAML file whose top level is a list of mappings.

The structured kind's Table view (plan Decision 12) draws a file through the table
plugin's routes, which ask this source. It reads the file as the Tree view does, through
the structured plugin's own parse and its bound (``load_structured_payload``,
``STRUCTURED_PARSE_MAX_BYTES``), so a file opened in one view is not parsed again for the
other, and builds one table from the parse:

- The table is the top-level list; each mapping in it is a row. A document whose top
  level is anything else, or a list holding anything but mappings, is not a list of
  records, and every route refuses it with ``source_unreadable`` and says why. So is a
  file the structured parse refused or cut at its bound.
- The fields are the mappings' keys, in the order each first appears. A key that is not
  text is named by its JSON text (``1``, ``true``, ``null``); an empty name becomes
  ``field_<n>``, counting fields from 1, and a repeated name gains ``_<n>``, as a
  delimited header's does.
- A field's type is the one its values in the first ``RECORDS_TYPE_SAMPLE_ROWS`` rows
  share, an integer counting as a real; text whose sampled values are all dates or
  datetimes is a ``date`` or ``datetime``, and a nested mapping or list is ``json``. A
  field whose sampled values disagree is ``unknown``, and each value is shown as its own
  type. A later value that contradicts a known type is a ``{value, stored}`` cell.
- A key a mapping lacks is absent, which the wire shows apart from null.
- A nested value is ``{json}``, the value itself, when its JSON text fits the bound the
  cell is read under (a page's ``TABLE_CELL_PREVIEW_CHARS``, a record's
  ``TABLE_RECORD_VALUE_BYTES``), and otherwise its JSON text cut there, a ``{text,
  length}`` envelope in a ``json`` field. A value JSON has no form for (a YAML date, a
  binary value, a non-finite number inside a nested value) is shown as its text.
- Rows have no key and are named by their 1-based position in the list, and the
  generation is the file's identity, size, and modification time, as for delimited text.

The table answers through the table plugin's memory engine
(``metabrowser.builtin_plugins.table.memory``), and a built table is held in a cache
keyed by the generation, bounded in entries and in the bytes the parse is estimated to
hold. Past ``RECORDS_MAX_ROWS`` rows, ``RECORDS_MAX_CELLS`` values, or
``RECORDS_MAX_FIELDS`` fields, the rest is not read, and the count, sort, and filter say
they cover only what was (``complete: false``, ``truncated: true``).
"""

from __future__ import annotations

import asyncio
import json
import math
import threading
from array import array
from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from metabrowser.builtin_plugins.structured import load_structured_payload
from metabrowser.builtin_plugins.structured.parser import (
    STRUCTURED_PARSE_MAX_BYTES,
    StructuredPayload,
)
from metabrowser.builtin_plugins.table import memory
from metabrowser.builtin_plugins.table.memory import (
    NULL_KEY,
    MemoryCache,
    SortKey,
    index_bytes,
)
from metabrowser.plugin_api import (
    TABLE_CARD_MAX_FIELDS,
    TABLE_CELL_PREVIEW_CHARS,
    TABLE_RECORD_VALUE_BYTES,
    Budget,
    Cell,
    FieldType,
    SourceUnreadableError,
    TableCard,
    TableField,
    TableHandle,
    TableInfo,
    TableNotFoundError,
    TablePage,
    TableQuery,
    TableRecord,
    TableSchema,
    coerce_filter_value,
    content_generation,
    integer_cell,
    real_cell,
    resolve_content,
    stored_cell,
    text_cell,
)

# ── Bounds ─────────────────────────────────────────────────────
#
# The parse is the structured plugin's, under its byte bound, and is held whatever the
# table reads of it; these bound what building and querying the table costs, which
# follows its rows and values, not its bytes. Measured with
# `devtools/bench_record_lists.py` on a shared 4-processor Linux container (Python 3.13,
# 2026-11-20); rerun it for the current numbers.

RECORDS_MAX_ROWS = 500_000
RECORDS_MAX_CELLS = 2_000_000
RECORDS_MAX_FIELDS = 1024
RECORDS_TYPE_SAMPLE_ROWS = 1000
RECORDS_CACHE_MAX_ENTRIES = 4
RECORDS_CACHE_MAX_BYTES = 256 * 1024 * 1024
_HELD_BYTES_PER_SOURCE_BYTE = 8
_HELD_BYTES_PER_NODE = 64

_DATE_SORT_NOTE = (
    "sorted as text: a value's date and time as written, not its instant, so values "
    "that mix separators or offsets sort by their spelling"
)
_UNKNOWN_SORT_NOTE = (
    "values of several types: nulls first, then numbers, then text, then nested values"
)
_JSON_SORT_NOTE = "a nested mapping or list has no order"


# ── Values ─────────────────────────────────────────────────────

# What a value of each Python type the structured parse produces is, as a field type.
# Text is refined to a date or datetime per field, from its sample.


def _value_type(value: Any) -> FieldType | None:
    """The type of one parsed value as a table field's, or None for null."""

    if value is None:
        return None
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "real"
    if isinstance(value, datetime):
        return "datetime"
    if isinstance(value, date):
        return "date"
    if isinstance(value, (Mapping, list)):
        return "json"
    return "text"


def _is_date_text(value: str) -> bool:
    if len(value) != 10:
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _is_datetime_text(value: str) -> bool:
    # Python's parser accepts a bare date and compact forms; a datetime here has a
    # separator and a time.
    if len(value) < 16 or value[10] not in "T ":
        return False
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True


def _infer_type(values: Sequence[Any]) -> FieldType:
    """The type a field's sampled values share: an integer counts as a real, and text
    that is all dates or all datetimes is that; values that disagree are `unknown`."""

    types: set[FieldType] = {kind for kind in map(_value_type, values) if kind is not None}
    if not types:
        return "text"
    if types <= {"integer", "real"}:
        return "real" if "real" in types else "integer"
    if len(types) > 1:
        return "unknown"
    (only,) = types
    if only == "text":
        texts = [value for value in values if isinstance(value, str)]
        if all(_is_date_text(value) for value in texts):
            return "date"
        if all(_is_datetime_text(value) for value in texts):
            return "datetime"
    return only


def _is_nan(value: Any) -> bool:
    return isinstance(value, float) and math.isnan(value)


def _conforms(field_type: FieldType, value: Any) -> bool:
    """Whether a non-null value is of its field's type, so it is shown as that type."""

    if field_type == "unknown":
        return True
    kind = _value_type(value)
    if kind == field_type:
        return True
    if field_type == "real" and kind == "integer":
        return True
    if isinstance(value, str) and field_type == "date":
        return _is_date_text(value)
    if isinstance(value, str) and field_type == "datetime":
        return _is_datetime_text(value)
    return False


def _json_safe(value: Any) -> Any:
    """A parsed value with only what JSON can carry: a value JSON has no form for (a YAML
    date, a binary value, a non-finite number) is its text, and every key is text."""

    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else _text_of(value)
    if isinstance(value, Mapping):
        mapping: Mapping[Any, Any] = value  # pyright: ignore[reportUnknownVariableType]
        return {
            key if isinstance(key, str) else _key_text(key): _json_safe(item)
            for key, item in mapping.items()
        }
    if isinstance(value, list):
        items: list[Any] = value  # pyright: ignore[reportUnknownVariableType]
        return [_json_safe(item) for item in items]
    return _text_of(value)


def _compact(value: Any) -> str:
    return json.dumps(_json_safe(value), ensure_ascii=False, separators=(",", ":"))


def _text_of(value: Any) -> str:
    """One value as text: what a search and a `contains` filter read, and how a value
    JSON has no form for is shown."""

    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        return json.dumps(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).hex()  # pyright: ignore[reportUnknownArgumentType]
    if isinstance(value, (Mapping, list)):
        return _compact(value)
    return str(value)


def _key_text(key: Any) -> str:
    """A mapping key as a field name: text as it is, a JSON scalar as its JSON text."""

    if isinstance(key, str):
        return key
    if key is None or isinstance(key, (bool, int, float)):
        return json.dumps(key) if not _is_nan(key) else "NaN"
    return _text_of(key)


def _sort_key(value: Any) -> SortKey:
    """A value's sort key: its storage class's rank, then the value (memory.py). A NaN
    is null, as SQLite stores it; a date sorts as its text."""

    if value is None or _is_nan(value):
        return NULL_KEY
    if isinstance(value, (bool, int, float)):
        return (1, value)
    if isinstance(value, (Mapping, list)):
        return (3, _compact(value))
    return (2, _text_of(value))


# ── The table ──────────────────────────────────────────────────

_ABSENT = object()


@dataclass(frozen=True, slots=True)
class _Field:
    name: str
    key: Hashable
    type: FieldType


@dataclass
class _Records:
    """One generation of one record list, read as a table: the memory engine's
    :class:`~metabrowser.builtin_plugins.table.memory.MemoryTable`.

    `rows` are the parse's own mappings, not copies. `rows_cut` says rows past a bound
    were not read; `fields_cut` says keys past `RECORDS_MAX_FIELDS` were not.
    `parsed_bytes` estimates what the parse holds (:attr:`held_bytes` adds the sort
    indexes)."""

    generation: str
    columns: tuple[_Field, ...]
    rows: list[Mapping[Hashable, Any]]
    rows_cut: bool
    fields_cut: bool
    parsed_bytes: int
    sort_indexes: dict[str, array[int]] = field(default_factory=dict[str, array[int]])
    lock: threading.Lock = field(default_factory=threading.Lock)
    _schema: TableSchema | None = None
    _positions: dict[str, int] | None = None

    @property
    def truncated(self) -> bool:
        return self.rows_cut or self.fields_cut

    @property
    def held_bytes(self) -> int:
        return self.parsed_bytes + index_bytes(self)

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def raw(self, index: int, column: int) -> Any:
        """One value as parsed, or `_ABSENT` when its mapping has no such key."""

        return self.rows[index].get(self.columns[column].key, _ABSENT)

    def schema(self) -> TableSchema:
        if self._schema is None:
            self._schema = _schema(self)
        return self._schema

    def sort_key(self, index: int, column: int) -> SortKey:
        value = self.raw(index, column)
        return NULL_KEY if value is _ABSENT else _sort_key(value)

    def text(self, index: int, column: int) -> str | None:
        value = self.raw(index, column)
        return None if value is _ABSENT or value is None else _text_of(value)

    def operand_key(self, column: int, raw: str) -> SortKey:
        found = self.columns[column]
        if found.type in ("integer", "real", "boolean"):
            return (1, coerce_filter_value(TableField(name=found.name, type=found.type), raw))
        if found.type == "json":
            return (3, raw)
        if found.type == "unknown":
            number = _number(raw)
            if number is not None:
                return (1, number)
        return (2, raw)

    def cursor_key(self, column: int, rank: int, value: Any) -> SortKey | None:
        if rank == 1:
            if type(value) is bool:
                return (1, value)
            number = memory.cursor_number(value)
            return None if number is None else (1, number)
        if rank in (2, 3) and type(value) is str:
            return (rank, value)
        return None

    def position(self, name: str) -> int | None:
        if self._positions is None:
            self._positions = {column.name: number for number, column in enumerate(self.columns)}
        return self._positions.get(name)

    def cells_per_row(self, names: Sequence[str]) -> int:
        return len(names)

    def cells(
        self,
        index: int,
        names: Sequence[str],
        *,
        max_chars: int | None = None,
        max_bytes: int | None = None,
    ) -> dict[str, Cell]:
        cells: dict[str, Cell] = {}
        for name in names:
            number = self.position(name)
            if number is None:
                continue
            value = self.raw(index, number)
            if value is _ABSENT:
                continue
            cells[name] = _cell(
                self.columns[number].type, value, max_chars=max_chars, max_bytes=max_bytes
            )
        return cells


def _number(raw: str) -> int | float | None:
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        number = float(raw)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _value_cell(value: Any, *, max_chars: int | None, max_bytes: int | None) -> Cell:
    """One non-null value as a cell of its own type."""

    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return integer_cell(value)
    if isinstance(value, float):
        return real_cell(value)
    if isinstance(value, (Mapping, list)):
        compact = _compact(value)
        fits = (max_chars is None or len(compact) <= max_chars) and (
            max_bytes is None or len(compact.encode("utf-8", errors="surrogatepass")) <= max_bytes
        )
        if fits:
            return {"json": _json_safe(value)}
        return text_cell(compact, max_chars=max_chars, max_bytes=max_bytes)
    return text_cell(_text_of(value), max_chars=max_chars, max_bytes=max_bytes)


def _cell(
    field_type: FieldType, value: Any, *, max_chars: int | None, max_bytes: int | None
) -> Cell:
    if value is None:
        return None
    cell = _value_cell(value, max_chars=max_chars, max_bytes=max_bytes)
    if _conforms(field_type, value):
        return cell
    stored = _value_type(value)
    return stored_cell(cell, stored if stored is not None else "unknown")


def _field_names(keys: Sequence[Hashable]) -> list[str]:
    """Each key's field name, in time linear in the keys: an empty name becomes
    `field_<n>`, and a repeated one takes the next free `_<n>`."""

    names: list[str] = []
    taken: set[str] = set()
    next_use: dict[str, int] = {}
    for number, key in enumerate(keys, start=1):
        base = _key_text(key) or f"field_{number}"
        name = base
        if name in taken:
            uses = next_use.get(base, 2)
            name = f"{base}_{uses}"
            while name in taken:
                uses += 1
                name = f"{base}_{uses}"
            next_use[base] = uses + 1
        taken.add(name)
        names.append(name)
    return names


def _not_records(reason: str) -> SourceUnreadableError:
    return SourceUnreadableError(f"This document is not a list of records: {reason}.")


_TOP_LEVEL = {
    "text": "text",
    "integer": "a number",
    "real": "a number",
    "boolean": "a boolean",
    "date": "a date",
    "datetime": "a datetime",
}


def _describe(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, Mapping):
        return "a mapping"
    if isinstance(value, list):
        return "a list"
    return _TOP_LEVEL.get(_value_type(value) or "", "a value")


def build_records(payload: StructuredPayload, generation: str) -> _Records:
    """The table a parse holds, or a refusal saying why it holds none."""

    if payload.truncated:
        raise SourceUnreadableError(
            "This file is larger than the "
            f"{STRUCTURED_PARSE_MAX_BYTES / 2**20:g} MiB of structured data read at once, "
            "so its records are not read."
        )
    if payload.parse_error is not None:
        raise SourceUnreadableError(f"This file could not be parsed: {payload.parse_error}")
    parsed = payload.parsed
    if not isinstance(parsed, list):
        raise _not_records(f"its top level is {_describe(parsed)}, not a list")
    items: list[Any] = parsed  # pyright: ignore[reportUnknownVariableType]
    rows: list[Mapping[Hashable, Any]] = []
    keys: dict[Hashable, None] = {}
    cells = 0
    rows_cut = False
    fields_cut = False
    for number, item in enumerate(items, start=1):
        if not isinstance(item, Mapping):
            raise _not_records(f"item {number} of its list is {_describe(item)}, not a mapping")
        if rows_cut:
            continue  # every item is still checked, so a refusal never depends on a bound
        record: Mapping[Hashable, Any] = item  # pyright: ignore[reportUnknownVariableType]
        if len(rows) >= RECORDS_MAX_ROWS or cells + len(record) > RECORDS_MAX_CELLS:
            rows_cut = True
            continue
        rows.append(record)
        cells += len(record)
        for key in record:
            if key not in keys:
                if len(keys) >= RECORDS_MAX_FIELDS:
                    fields_cut = True
                    continue
                keys[key] = None
    ordered = list(keys)
    sample = rows[:RECORDS_TYPE_SAMPLE_ROWS]
    columns = tuple(
        _Field(
            name=name,
            key=key,
            type=_infer_type([row[key] for row in sample if key in row]),
        )
        for key, name in zip(ordered, _field_names(ordered), strict=True)
    )
    return _Records(
        generation=generation,
        columns=columns,
        rows=rows,
        rows_cut=rows_cut,
        fields_cut=fields_cut,
        parsed_bytes=payload.source_bytes * _HELD_BYTES_PER_SOURCE_BYTE
        + payload.node_count * _HELD_BYTES_PER_NODE,
    )


def _schema(records: _Records) -> TableSchema:
    fields: list[TableField] = []
    for column in records.columns:
        sort_note: str | None = None
        if column.type in ("date", "datetime"):
            sort_note = _DATE_SORT_NOTE
        elif column.type == "unknown":
            sort_note = _UNKNOWN_SORT_NOTE
        elif column.type == "json":
            sort_note = _JSON_SORT_NOTE
        fields.append(
            TableField(
                name=column.name,
                type=column.type,
                sortable=column.type != "json",
                sort_note=sort_note,
                filterable=True,
                numeric=column.type in ("integer", "real"),
            )
        )
    return TableSchema(
        table="",
        fields=tuple(fields),
        key=(),
        default_columns=tuple(column.name for column in records.columns),
    )


# ── The source ─────────────────────────────────────────────────

RECORDS_CACHE: MemoryCache[_Records] = MemoryCache(
    max_entries=lambda: RECORDS_CACHE_MAX_ENTRIES, max_bytes=lambda: RECORDS_CACHE_MAX_BYTES
)


class RecordListSource:
    """The table source for one JSON or YAML file of the structured kind."""

    def __init__(self, handle: TableHandle) -> None:
        self._handle = handle

    def generation(self) -> str:
        return content_generation(self._handle)

    def _payload(self) -> StructuredPayload:
        """The structured parse of the file as it is now.

        The path is resolved again, after the generation was sampled, so the parse
        looked up by the content's fingerprint is never older than the generation it is
        labelled with: a change during a read costs one extra refetch, never a lost one.
        The resolve and the read run on the server's event loop, as
        :meth:`TableHandle.read_window` runs its read.
        """

        identity = self._handle.ref.identity

        async def load() -> StructuredPayload:
            ref = await resolve_content(identity)
            if ref is None:
                raise SourceUnreadableError("This file is no longer available.")
            return await load_structured_payload(ref)

        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self._handle.loop:
            raise RuntimeError("RecordListSource reads block; call them off the event loop")
        return asyncio.run_coroutine_threadsafe(load(), self._handle.loop).result()

    def _records(self) -> _Records:
        generation = self.generation()
        return RECORDS_CACHE.load(
            self._handle.ref.identity,
            generation,
            lambda: build_records(self._payload(), generation),
        )

    @staticmethod
    def _require_table(table: str) -> None:
        if table:
            raise TableNotFoundError(
                f"a record list is one table and has no table {table!r}", table=table
            )

    def tables(self) -> Sequence[TableInfo]:
        return (TableInfo(id="", label=self._handle.name, group="tables", keyed=False),)

    def schema(self, table: str) -> TableSchema:
        self._require_table(table)
        return self._records().schema()

    def rows(self, table: str, query: TableQuery, budget: Budget) -> TablePage:
        self._require_table(table)
        records = self._records()
        indexes = len(records.sort_indexes)
        page = memory.page(records, query, budget)
        if len(records.sort_indexes) != indexes:
            RECORDS_CACHE.trim()
        return page

    def record(self, table: str, key: str, budget: Budget) -> TableRecord:
        self._require_table(table)
        records = self._records()
        index = memory.row_index(records, key)
        return TableRecord(
            key=key,
            cells=records.cells(
                index, records.schema().default_columns, max_bytes=TABLE_RECORD_VALUE_BYTES
            ),
            generation=records.generation,
            positional=True,
        )

    def card(self, table: str, key: str, budget: Budget) -> TableCard:
        self._require_table(table)
        records = self._records()
        index = memory.row_index(records, key)
        names = records.schema().default_columns[: TABLE_CARD_MAX_FIELDS + 1]
        cells = records.cells(index, names, max_chars=TABLE_CELL_PREVIEW_CHARS)
        label = cells.pop(names[0], None) if names else None
        return TableCard(key=key, label=label, cells=cells, generation=records.generation)


def adapter(handle: TableHandle) -> RecordListSource:
    """The `[[table_source]]` adapter for the `structured` kind."""

    return RecordListSource(handle)


__all__ = [
    "RECORDS_CACHE",
    "RECORDS_CACHE_MAX_BYTES",
    "RECORDS_CACHE_MAX_ENTRIES",
    "RECORDS_MAX_CELLS",
    "RECORDS_MAX_FIELDS",
    "RECORDS_MAX_ROWS",
    "RECORDS_TYPE_SAMPLE_ROWS",
    "RecordListSource",
    "adapter",
    "build_records",
]
