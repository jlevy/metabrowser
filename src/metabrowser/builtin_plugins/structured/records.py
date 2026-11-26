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
(``metabrowser.builtin_plugins.table.memory``), and a built table, or the refusal that
is a file's answer, is held in a cache keyed by the generation, bounded in entries and
in the bytes the parse is estimated to hold. A nested value is counted and written only
as far as the bound it is read under, so what a query costs follows its bounds and the
file's bytes, not how far YAML aliases expand the document. Past ``RECORDS_MAX_ROWS`` rows, ``RECORDS_MAX_CELLS`` values, or
``RECORDS_MAX_FIELDS`` fields, the rest is not read, and the count, sort, and filter say
they cover only what was (``complete: false``, ``truncated: true``).
"""

from __future__ import annotations

import asyncio
import json
import math
import re
import threading
from array import array
from collections.abc import Hashable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from json.encoder import encode_basestring
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
# The parse is the structured plugin's, under its byte bound, `STRUCTURED_PARSE_MAX_BYTES`
# (an environment setting); these bound what building and querying the table costs,
# which follows its rows and values, not its bytes. Measured with
# `devtools/bench_record_lists.py` over JSON lists at that byte bound, 8 MiB, on a
# shared 4-processor Linux container at a load average of 3 to 9 (Python 3.13,
# 2026-11-20). Under that load they are upper figures, wider and slower than a quiet
# machine gives, so the bounds they set are safe but not tight; rerun it on a quiet
# machine for figures to tighten them by.
#
# The parse the table reads costs 0.07 to 0.29 s for 8 MiB of JSON, without the Tree
# view's YAML, which took 26 s for the 12-field shape and which the table never writes
# (`load_structured_payload`). YAML parses about thirty times slower than JSON: 1 MiB of
# a four-field list took 5 s, so a large YAML file's first open, in either view, is the
# structured plugin's cost, not this source's.

# The most rows read. With no row bound, one field of one character (838,860 rows at the
# byte bound) took 0.29 s to build, 0.82 s for a first sort index, and 0.67 s for a
# filtered and sorted page; at this bound 0.21 s, 0.45 s, and 0.38 s, about one second
# for a first filtered and sorted page, half of `TABLE_REQUEST_DEADLINE_SECONDS`, as the
# delimited source's `DELIMITED_MAX_ROWS` keeps.
RECORDS_MAX_ROWS = 500_000

# The most values read, the mappings' top-level values. 8 MiB of JSON holds at most
# about 1.4 million (a one-character key and a one-digit value is six bytes), so this
# bound is met only where the byte bound is raised; six fields of two-digit integers,
# 1.1 million values, built in 0.07 s.
RECORDS_MAX_CELLS = 2_000_000

# The most fields read; a key first seen past it is not read. At this width, 283
# records of datetimes, the dearest values to infer, built in 0.26 s, the schema encoded
# in 2 ms as 0.42 MB of JSON, and a page carried 11 rows (`TABLE_PAGE_CELLS_MAX`).
RECORDS_MAX_FIELDS = 1024

# How much of a nested value's JSON text a filter, a search, and a sort read, in
# characters: as much as a record carries of it (`TABLE_RECORD_VALUE_BYTES`), so a filter
# matches what the record can show; a longer value is compared by its start. Its text is
# written only this far (`_json_text`), so what reading it costs is bounded here and not
# by the value, which YAML aliases can make far larger than the file. Writing this far
# into a list of 50,000 integers (about 290,000 characters) took 5 ms, as writing the
# whole list with `json.dumps` took 4.3 ms. Over 3,000 records that each alias that list,
# a `contains` filter read about 350 of them in its 2 s budget and said so
# (`complete: false`), where before it read the whole list in each and answered after
# 5.6 s as if complete (at a load average of 2 to 4, 2026-11-20).
RECORDS_NESTED_READ_CHARS = TABLE_RECORD_VALUE_BYTES

# How often a scan of a record list, and the build of its sort index, read the request's
# budget, in rows. A delimited cell costs at most its bytes, so that source reads it every
# `memory.BUDGET_CHECK_ROWS` rows; a record's values cost up to
# `RECORDS_NESTED_READ_CHARS` of text each, whatever the file's size, so this one reads
# it every few, which past its budget a scan overruns by at most this many rows'
# reading, 90 ms at the 5 ms per row above. Reading it is a clock read: a `notnull`
# filter over 500,000 records took 0.18 to 0.20 s at this spacing and at the delimited
# one alike, and 0.23 s reading it every row.
RECORDS_BUDGET_CHECK_ROWS = 16

# Rows whose values decide each field's type, as `DELIMITED_TYPE_SAMPLE_ROWS`; a later
# value that contradicts the type is shown as stored. Its dearest case is in the
# measurement above.
RECORDS_TYPE_SAMPLE_ROWS = 1000

# The table cache's bounds, as the delimited source's: entries, and the bytes the parses
# it holds are estimated to hold with their sort indexes (`_Records.held_bytes`).
RECORDS_CACHE_MAX_ENTRIES = 8
RECORDS_CACHE_MAX_BYTES = 256 * 1024 * 1024

# What a parse holds, as an upper fit over the bench's shapes: `tracemalloc` measured
# from 3.0 to 19.3 bytes a byte of JSON and 40 to 110 bytes a node (a mapping, a list,
# or a value), and this estimate came to 1.1 to 3.4 times what it measured, never less.
_HELD_BYTES_PER_SOURCE_BYTE = 8
_HELD_BYTES_PER_NODE = 64

_DATE_SORT_NOTE = (
    "sorted as text: a value's date and time as written, not its instant, so values "
    "that mix separators or offsets sort by their spelling"
)
_UNKNOWN_SORT_NOTE = (
    "values of several types: nulls first, then numbers, then text, then nested values;"
    " a filter value that reads as a number matches numbers only"
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
        # A binary value or a set is text too, and none is a date: over no text at all,
        # `all` would be true.
        texts = [value for value in values if isinstance(value, str)]
        if texts and all(_is_date_text(value) for value in texts):
            return "date"
        if texts and all(_is_datetime_text(value) for value in texts):
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


_LONE_SURROGATE = re.compile("[\ud800-\udfff]")


def _valid_text(text: str) -> str:
    """*text* with each lone surrogate, which a JSON escape can write and UTF-8 cannot
    carry, as U+FFFD, so its length is unchanged; *text* itself when it has none."""

    if text.isascii():
        return text
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return _LONE_SURROGATE.sub("\ufffd", text)
    return text


def _json_safe(value: Any) -> Any:
    """A parsed value with only what JSON can carry: a value JSON has no form for (a YAML
    date, a binary value, a non-finite number) is its text, every key is text, and a lone
    surrogate is U+FFFD. It is written whole, so it is asked only of a value whose JSON
    text fits a cell's bound."""

    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, str):
        return _valid_text(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else _text_of(value)
    if isinstance(value, Mapping):
        mapping: Mapping[Any, Any] = value  # pyright: ignore[reportUnknownVariableType]
        return {_valid_text(_key_text(key)): _json_safe(item) for key, item in mapping.items()}
    if isinstance(value, list):
        items: list[Any] = value  # pyright: ignore[reportUnknownVariableType]
        return [_json_safe(item) for item in items]
    return _valid_text(_text_of(value))


# ── A nested value's JSON text, written and counted within bounds ──
#
# A nested value's JSON text is written a member at a time, so writing can stop at a
# bound, and counted without being written, each mapping, list, and long text once
# however many times YAML aliases repeat it. Both read the text as
# `json.dumps(_json_safe(value), ensure_ascii=False, separators=(",", ":"))` writes it,
# and both walk the value with their own stack, so its depth costs no recursion. The
# parse is a tree: a document that refers to itself is refused before it reaches a table
# (`_TOO_DEEP`), so neither walk meets a cycle.

_CONTAINERS = (Mapping, list)
_END: Any = object()

# Text longer than this many characters is counted once per object, as a mapping or list
# is; shorter text costs less to count again than to remember.
_COUNTED_ONCE_CHARS = 64


def _json_string(text: str, limit: int | None = None) -> str:
    """Text as a JSON string; past *limit* characters, the string of its first
    `limit + 1`, whose text up to its closing quote begins the whole string's."""

    return encode_basestring(text if limit is None else text[: limit + 1])


def _scalar_json(value: Any, limit: int | None = None) -> str:
    """A value that is not a mapping or list as JSON text, cut as `_json_string` cuts."""

    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return int.__repr__(value)
    if isinstance(value, float) and math.isfinite(value):
        return float.__repr__(value)
    if isinstance(value, str):
        return _json_string(value, limit)
    return _json_string(_text_of(value), limit)


def _json_text(value: Any, limit: int) -> str:
    """A value's JSON text, written only until it passes *limit* characters: the whole
    text when it fits, and otherwise its first `limit + 1`, so a caller can tell it was
    cut. What it costs follows *limit*, not the value."""

    parts: list[str] = []
    written = 0
    # The containers being written, innermost last: each one's members, whether it is a
    # mapping, whether its next member is its first, and its closing bracket.
    members: list[Iterator[Any]] = []
    mappings: list[bool] = []
    firsts: list[bool] = []
    closes: list[str] = []
    item = value
    while True:
        if isinstance(item, Mapping):
            mapping: Mapping[Any, Any] = item  # pyright: ignore[reportUnknownVariableType]
            members.append(iter(mapping.items()))
            mappings.append(True)
            firsts.append(True)
            closes.append("}")
            piece = "{"
        elif isinstance(item, list):
            items: list[Any] = item  # pyright: ignore[reportUnknownVariableType]
            members.append(iter(items))
            mappings.append(False)
            firsts.append(True)
            closes.append("]")
            piece = "["
        else:
            piece = _scalar_json(item, max(limit - written, 0))
        parts.append(piece)
        written += len(piece)
        # The next member to write, closing each container whose members are written.
        while members:
            if written > limit:
                return "".join(parts)[: limit + 1]
            member = next(members[-1], _END)
            if member is _END:
                members.pop()
                mappings.pop()
                firsts.pop()
                parts.append(closes.pop())
                written += 1
                continue
            before = "" if firsts[-1] else ","
            firsts[-1] = False
            if mappings[-1]:
                key, item = member
                before += _json_string(_key_text(key), limit) + ":"
            else:
                item = member
            if before:
                parts.append(before)
                written += len(before)
            break
        else:
            return "".join(parts)[: limit + 1]


def _scalar_length(value: Any, known: dict[int, int]) -> int:
    if isinstance(value, (bytes, bytearray)):
        return 2 * len(value) + 2  # pyright: ignore[reportUnknownArgumentType]
    if isinstance(value, str) and len(value) > _COUNTED_ONCE_CHARS:
        found = known.get(id(value))
        if found is None:
            found = known[id(value)] = len(_json_string(value))
        return found
    return len(_scalar_json(value))


def _json_length(value: Any, known: dict[int, int]) -> int:
    """The length of a value's JSON text, counted without writing it. *known* holds the
    lengths counted so far by object, so a value that aliases repeat is counted once
    while the objects are alive; the caller keeps it for as long as that holds."""

    if not isinstance(value, _CONTAINERS):
        return _scalar_length(value, known)
    found = known.get(id(value))
    if found is not None:
        return found
    # The containers being counted, innermost last, with their members, whether each is
    # a mapping, and its count so far.
    nodes: list[Any] = []
    members: list[Iterator[Any]] = []
    mappings: list[bool] = []
    totals: list[int] = []
    item = value
    while True:
        container: Mapping[Any, Any] | list[Any] = item
        nodes.append(container)
        if isinstance(container, Mapping):
            members.append(iter(container.items()))
            mappings.append(True)
        else:
            members.append(iter(container))
            mappings.append(False)
        totals.append(2 + max(len(container) - 1, 0))  # its brackets and commas
        # The next container not counted yet, closing each whose members are counted.
        while True:
            member = next(members[-1], _END)
            if member is _END:
                node = nodes.pop()
                members.pop()
                mappings.pop()
                total = totals.pop()
                known[id(node)] = total
                if not nodes:
                    return total
                totals[-1] += total
                continue
            if mappings[-1]:
                key, child = member
                totals[-1] += len(_json_string(_key_text(key))) + 1
            else:
                child = member
            if not isinstance(child, _CONTAINERS):
                totals[-1] += _scalar_length(child, known)
                continue
            found = known.get(id(child))
            if found is None:
                item = child
                break
            totals[-1] += found


def _nested_text(value: Any) -> str:
    """What a filter, a search, and a sort read of a nested value."""

    return _json_text(value, RECORDS_NESTED_READ_CHARS)[:RECORDS_NESTED_READ_CHARS]


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
        # As much of it as a filter reads of a nested value; a cell counts the rest.
        start = value[: RECORDS_NESTED_READ_CHARS // 2]  # pyright: ignore[reportUnknownVariableType]
        return bytes(start).hex()  # pyright: ignore[reportUnknownArgumentType]
    if isinstance(value, _CONTAINERS):
        return _nested_text(value)
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
    if isinstance(value, _CONTAINERS):
        return (3, _nested_text(value))
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

    @property
    def budget_check_rows(self) -> int:
        return RECORDS_BUDGET_CHECK_ROWS

    def is_null(self, index: int, column: int) -> bool:
        value = self.raw(index, column)
        return value is _ABSENT or value is None or _is_nan(value)

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
        known: dict[int, int] | None = None,
    ) -> dict[str, Cell]:
        """One row's cells. *known* holds the nested values' lengths counted so far, so a
        page counts a value that aliases repeat across its rows once."""

        known = {} if known is None else known
        cells: dict[str, Cell] = {}
        for name in names:
            number = self.position(name)
            if number is None:
                continue
            value = self.raw(index, number)
            if value is _ABSENT:
                continue
            cells[name] = _cell(
                self.columns[number].type,
                value,
                max_chars=max_chars,
                max_bytes=max_bytes,
                known=known,
            )
        return cells

    def page_cells(
        self, indexes: Sequence[int], names: Sequence[str], *, max_chars: int
    ) -> list[dict[str, Cell]]:
        known: dict[int, int] = {}
        return [self.cells(index, names, max_chars=max_chars, known=known) for index in indexes]


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


def _bound(max_chars: int | None, max_bytes: int | None) -> int | None:
    """The characters a cell's bound can hold at most: a UTF-8 byte holds at most one."""

    bounds = [bound for bound in (max_chars, max_bytes) if bound is not None]
    return min(bounds) if bounds else None


def _shown(
    text: str, *, max_chars: int | None, max_bytes: int | None, length: int | None = None
) -> Cell:
    """Text as a cell, cut at the bound, where *text* may be only the start of a value
    *length* characters long. A lone surrogate is shown as U+FFFD and the cell marked
    `invalid_utf8`, as text that does not decode is."""

    whole = len(text) if length is None else length
    bound = _bound(max_chars, max_bytes)
    start = text if bound is None else text[: bound + 1]
    valid = _valid_text(start)
    cell = text_cell(valid, max_chars=max_chars, max_bytes=max_bytes)
    shown: str = cell if isinstance(cell, str) else cell["text"]
    if valid is start and len(shown) == whole:
        return shown
    envelope: dict[str, Any] = {"text": shown}
    if len(shown) != whole:
        envelope["length"] = whole
    if valid is not start:
        envelope["invalid_utf8"] = True
    return envelope


def _nested_cell(
    value: Any, *, max_chars: int | None, max_bytes: int | None, known: dict[int, int]
) -> Cell:
    """A mapping or list as `{json}` when its JSON text fits the cell's bound, and as that
    text cut there otherwise. It is counted, not written, to learn whether it fits, and
    written only as far as the bound."""

    length = _json_length(value, known)
    bound = _bound(max_chars, max_bytes)
    fits = bound is None or length <= bound
    if fits and max_bytes is not None and 4 * length > max_bytes:
        text = _json_text(value, length)
        fits = len(text.encode("utf-8", errors="surrogatepass")) <= max_bytes
    if fits:
        return {"json": _json_safe(value)}
    return _shown(
        _json_text(value, bound if bound is not None else length),
        max_chars=max_chars,
        max_bytes=max_bytes,
        length=length,
    )


def _value_cell(
    value: Any, *, max_chars: int | None, max_bytes: int | None, known: dict[int, int]
) -> Cell:
    """One non-null value as a cell of its own type."""

    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return integer_cell(value)
    if isinstance(value, float):
        return real_cell(value)
    if isinstance(value, _CONTAINERS):
        return _nested_cell(value, max_chars=max_chars, max_bytes=max_bytes, known=known)
    if isinstance(value, (bytes, bytearray)):
        bound = _bound(max_chars, max_bytes)
        start = value if bound is None else value[: bound // 2 + 1]  # pyright: ignore[reportUnknownVariableType]
        return _shown(
            bytes(start).hex(),  # pyright: ignore[reportUnknownArgumentType]
            max_chars=max_chars,
            max_bytes=max_bytes,
            length=2 * len(value),  # pyright: ignore[reportUnknownArgumentType]
        )
    return _shown(_text_of(value), max_chars=max_chars, max_bytes=max_bytes)


def _cell(
    field_type: FieldType,
    value: Any,
    *,
    max_chars: int | None,
    max_bytes: int | None,
    known: dict[int, int],
) -> Cell:
    if value is None:
        return None
    cell = _value_cell(value, max_chars=max_chars, max_bytes=max_bytes, known=known)
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
        base = _valid_text(_key_text(key)) or f"field_{number}"
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


# Why a parse that recursed past the interpreter's limit is refused: the structured
# plugin's walk of the parse (`parser._count_nodes_and_depth`) recurses, so a document
# nested thousands deep, or a YAML anchor that refers to itself, fails there.
_TOO_DEEP = "This document is nested too deeply or refers to itself, so its records are not read."


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
            "This file is too large to show as a table.",
            detail="This file is larger than the "
            f"{STRUCTURED_PARSE_MAX_BYTES / 2**20:g} MiB of structured data read at once, "
            "so its records are not read.",
        )
    if payload.parse_error is not None:
        raise SourceUnreadableError("This file could not be parsed.", detail=payload.parse_error)
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
        # The parse's walk counts a node once per alias to it, but each object it holds
        # took at least one of the file's bytes.
        parsed_bytes=payload.source_bytes * _HELD_BYTES_PER_SOURCE_BYTE
        + min(payload.node_count, payload.source_bytes) * _HELD_BYTES_PER_NODE,
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


@dataclass(frozen=True, slots=True)
class _Refusal:
    """A generation of a file that is not a list of records, and why, kept so that the
    Table tab's every request on it costs a cache lookup and not a parse."""

    generation: str
    reason: str
    # What an agent reads beside the reason (docs/design-system-messages.md): a parser's
    # own words, which the page does not show.
    detail: str = ""

    @property
    def held_bytes(self) -> int:
        return len(self.reason) + len(self.detail)


RECORDS_CACHE: MemoryCache[_Records | _Refusal] = MemoryCache(
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
            return await load_structured_payload(ref, serialize=False)

        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self._handle.loop:
            raise RuntimeError("RecordListSource reads block; call them off the event loop")
        return asyncio.run_coroutine_threadsafe(load(), self._handle.loop).result()

    def _build(self, generation: str) -> _Records | _Refusal:
        """The table of the file's parse, or the refusal that is its answer for this
        generation. A file that cannot be read now is not an answer to remember."""

        try:
            payload = self._payload()
        except RecursionError:
            return _Refusal(generation=generation, reason=_TOO_DEEP)
        try:
            return build_records(payload, generation)
        except SourceUnreadableError as exc:
            detail = exc.details.get("detail")
            return _Refusal(
                generation=generation,
                reason=str(exc),
                detail=detail if isinstance(detail, str) else "",
            )

    def _records(self) -> _Records:
        generation = self.generation()
        found = RECORDS_CACHE.load(
            self._handle.ref.identity, generation, lambda: self._build(generation)
        )
        if isinstance(found, _Refusal):
            raise SourceUnreadableError(
                found.reason, **({"detail": found.detail} if found.detail else {})
            )
        return found

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
