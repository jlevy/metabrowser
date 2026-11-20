"""The delimited-text table source: a `.csv` or `.tsv` file as one table.

The file parses with the standard library's ``csv`` under these rules:

- The extension sets the delimiter, comma or tab; quoting is RFC 4180's double quote.
- Bytes are UTF-8, with a leading byte-order mark dropped. Invalid bytes are replaced
  and the cell holding them is marked ``invalid_utf8``.
- The first row is the header. An empty name becomes ``column_<n>``, counting columns
  from 1, and a repeated name gains ``_<n>`` for its nth use.
- A blank line is not a row. A short row's missing cells are absent, which the wire
  shows apart from empty; a long row's extra cells go to one trailing ``extra`` field,
  a list.
- Types are inferred from the first ``DELIMITED_TYPE_SAMPLE_ROWS`` rows' nonempty
  values; a later value that contradicts its column's type is a ``{value, stored}``
  cell. An empty value is null in a column of any type but text, where it is the empty
  string.
- Rows have no key; a row is named by its 1-based position in the file, so a name
  survives any change of sort or filter.
- The generation is the file's identity, size, and modification time.

A file is parsed whole, up to ``DELIMITED_PARSE_MAX_BYTES``, and held in a cache keyed
by its generation and bounded in bytes and entries; a sort index is built on demand and
kept with it. A larger file shows its leading rows, and its count, sort, and filter say
they cover only those rows (``complete: false``, ``truncated: true``).
"""

from __future__ import annotations

import csv
import io
import operator
import re
import threading
from bisect import bisect_left, bisect_right
from collections import OrderedDict
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from metabrowser.plugin_api import (
    TABLE_CARD_MAX_FIELDS,
    TABLE_CELL_PREVIEW_CHARS,
    TABLE_RECORD_VALUE_BYTES,
    Budget,
    Cell,
    FieldType,
    Filter,
    RecordNotFoundError,
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
    coerce_filter_value,
    content_generation,
    decode_cursor,
    encode_cursor,
    integer_cell,
    page_columns,
    parse_position_key,
    parse_positional_cursor,
    position_key,
    positional_cursor,
    real_cell,
    stored_cell,
    text_cell,
)

# The most bytes of a file parsed; past it the file shows its leading rows. A parse is
# not interruptible, so this bounds the first request's latency and the cache's memory.
# Measured with `devtools/bench_table_source.py`, as the bounds in
# `metabrowser.table_source` are: 16 MiB of a 12-column CSV (about 150,000 rows) parsed
# in 0.30 to 0.46 s and held 118 MB of Python objects, 7.0 bytes per byte of file; a
# first sort index then took 0.26 to 0.53 s. At 32 MiB the parse took 1.2 s and a sort
# 0.7 s, so a first sorted page approached two seconds.
DELIMITED_PARSE_MAX_BYTES = 16 * 1024 * 1024

# Rows whose values decide each column's type. Inference checks every sampled value
# against at most five patterns, so it costs little at this size; a later value that
# contradicts the type is shown as stored, not hidden.
DELIMITED_TYPE_SAMPLE_ROWS = 1000

# The parse cache's bounds: entries, and the bytes the parsed files are estimated to
# hold, at the measured 7 bytes per byte of file, so two files at the parse cap fit.
DELIMITED_CACHE_MAX_ENTRIES = 8
DELIMITED_CACHE_MAX_BYTES = 256 * 1024 * 1024
_HELD_BYTES_PER_FILE_BYTE = 7

# How often a scan checks its budget, in rows: often enough to stop within a few
# milliseconds, rarely enough to cost nothing measurable.
_BUDGET_CHECK_ROWS = 4096

_DELIMITERS = {".csv": ",", ".tsv": "\t"}
_BOM = b"\xef\xbb\xbf"
_EXTRA = "extra"
# Decoding with `surrogateescape` turns each invalid byte into one of these.
_ESCAPED_BYTE = re.compile("[\udc80-\udcff]")

# A cell longer than the `csv` module's default field limit (131,072 characters) is a
# parse error there; one parse is bounded by the cap above, so the limit can be that.
csv.field_size_limit(max(csv.field_size_limit(), DELIMITED_PARSE_MAX_BYTES))

_INTEGER = re.compile(r"[+-]?(?:0|[1-9][0-9]*)\Z")
_REAL = re.compile(r"[+-]?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_DATETIME = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]{1,6})?)?"
    r"(?:Z|[+-][0-9]{2}:?[0-9]{2})?\Z"
)


def _is_integer(value: str) -> bool:
    return _INTEGER.match(value) is not None


def _is_real(value: str) -> bool:
    return _REAL.match(value) is not None


def _is_boolean(value: str) -> bool:
    return value.lower() in ("true", "false")


def _is_date(value: str) -> bool:
    if _DATE.match(value) is None:
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _is_datetime(value: str) -> bool:
    if _DATETIME.match(value) is None:
        return False
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True


# Most specific first: an integer column is also a real one.
_INFERENCE: tuple[tuple[FieldType, Callable[[str], bool]], ...] = (
    ("boolean", _is_boolean),
    ("integer", _is_integer),
    ("real", _is_real),
    ("date", _is_date),
    ("datetime", _is_datetime),
)
_CONFORMS: dict[FieldType, Callable[[str], bool]] = dict(_INFERENCE)


def _infer_type(values: Sequence[str]) -> FieldType:
    present = [value for value in values if value]
    if not present:
        return "text"
    for name, conforms in _INFERENCE:
        if all(conforms(value) for value in present):
            return name
    return "text"


# A sort key: (0,) for null or absent, (1, value) for a value of the column's type, and
# (2, text) for text, including a value that contradicts its column's type: SQLite's
# order of storage classes, so every source sorts mixed columns alike.
SortKey = tuple[Any, ...]


def _typed(column_type: FieldType, value: str) -> int | float | bool | str | None:
    """A conforming value as its type, or None when it does not conform."""

    if not _CONFORMS[column_type](value):
        return None
    if column_type == "integer":
        try:
            return int(value)
        except ValueError:  # past the interpreter's digit limit for int()
            return None
    if column_type == "real":
        return float(value)
    if column_type == "boolean":
        return value.lower() == "true"
    return value


@dataclass(frozen=True, slots=True)
class _Column:
    name: str
    type: FieldType

    def sort_key(self, value: str | None) -> SortKey:
        if value is None:
            return (0,)
        if self.type == "text":
            return (2, value)
        if not value:
            return (0,)
        typed = _typed(self.type, value)
        return (2, value) if typed is None else (1, typed)


@dataclass
class _Parsed:
    """One generation of one file, parsed."""

    generation: str
    columns: tuple[_Column, ...]
    rows: list[list[str]]
    has_extra: bool
    truncated: bool
    held_bytes: int
    invalid: frozenset[tuple[int, int]]
    sort_indexes: dict[str, list[int]] = field(default_factory=dict[str, list[int]])
    lock: threading.Lock = field(default_factory=threading.Lock)

    def value(self, index: int, column: int) -> str | None:
        row = self.rows[index]
        return row[column] if column < len(row) else None

    def extra(self, index: int) -> list[str] | None:
        row = self.rows[index]
        return row[len(self.columns) :] if len(row) > len(self.columns) else None

    def sort_index(self, column: int) -> list[int]:
        """Row indexes in ascending order of one column, ties by position."""

        name = self.columns[column].name
        with self.lock:
            found = self.sort_indexes.get(name)
            if found is None:
                key = self.columns[column].sort_key
                keys = [key(self.value(index, column)) for index in range(len(self.rows))]
                found = sorted(range(len(self.rows)), key=lambda index: (keys[index], index))
                self.sort_indexes[name] = found
            return found


def _column_names(header: Sequence[str]) -> list[str]:
    names: list[str] = []
    for number, raw in enumerate(header, start=1):
        base = raw or f"column_{number}"
        name, uses = base, 1
        while name in names:
            uses += 1
            name = f"{base}_{uses}"
        names.append(name)
    return names


def _clean(rows: list[list[str]]) -> frozenset[tuple[int, int]]:
    """Replace escaped invalid bytes with U+FFFD in place, and return the cells that held
    them as (row, column) pairs, where row -1 is the header."""

    invalid: set[tuple[int, int]] = set()
    for row_index, row in enumerate(rows):
        for column, value in enumerate(row):
            if _ESCAPED_BYTE.search(value):
                row[column] = _ESCAPED_BYTE.sub("�", value)
                invalid.add((row_index - 1, column))
    return frozenset(invalid)


def parse_delimited(data: bytes, *, has_more: bool, delimiter: str, generation: str) -> _Parsed:
    """Parse one bounded read of a delimited file. ``has_more`` says the read stopped at
    the parse cap, so the last record may be cut and is dropped."""

    if data.startswith(_BOM):
        data = data[len(_BOM) :]
    try:
        text = data.decode("utf-8")
        dirty = False
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="surrogateescape")
        dirty = True
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, quotechar='"')
    records: list[list[str]] = []
    try:
        records.extend(record for record in reader if record)
    except csv.Error as exc:
        if not has_more:
            raise SourceUnreadableError(f"not readable as delimited text: {exc}") from exc
    if has_more and records:
        records.pop()
    invalid = _clean(records) if dirty else frozenset[tuple[int, int]]()
    header = records[0] if records else []
    rows = records[1:]
    names = _column_names(header)
    sample = rows[:DELIMITED_TYPE_SAMPLE_ROWS]
    columns = tuple(
        _Column(
            name=name,
            type=_infer_type([row[index] for row in sample if index < len(row)]),
        )
        for index, name in enumerate(names)
    )
    has_extra = any(len(row) > len(columns) for row in rows)
    return _Parsed(
        generation=generation,
        columns=columns,
        rows=rows,
        has_extra=has_extra,
        truncated=has_more,
        held_bytes=len(data) * _HELD_BYTES_PER_FILE_BYTE,
        invalid=invalid,
    )


class _ParseCache:
    """Parsed files by identity, each at the generation it was parsed under."""

    def __init__(self) -> None:
        self._entries: OrderedDict[tuple[str, str], _Parsed] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: tuple[str, str], generation: str) -> _Parsed | None:
        with self._lock:
            found = self._entries.get(key)
            if found is None or found.generation != generation:
                return None
            self._entries.move_to_end(key)
            return found

    def put(self, key: tuple[str, str], parsed: _Parsed) -> None:
        with self._lock:
            self._entries[key] = parsed
            self._entries.move_to_end(key)
            while len(self._entries) > 1 and (
                len(self._entries) > DELIMITED_CACHE_MAX_ENTRIES
                or sum(entry.held_bytes for entry in self._entries.values())
                > DELIMITED_CACHE_MAX_BYTES
            ):
                self._entries.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


PARSE_CACHE = _ParseCache()


def _name_of(index: int) -> str:
    return position_key(index + 1)


class DelimitedSource:
    """The table source for one delimited file."""

    def __init__(self, handle: TableHandle) -> None:
        self._handle = handle
        delimiter = _DELIMITERS.get(handle.ref.logical_ext)
        if delimiter is None:
            raise SourceUnreadableError(f"{handle.ref.logical_ext!r} is not a delimited format")
        self._delimiter = delimiter

    def generation(self) -> str:
        return content_generation(self._handle)

    def _parsed(self) -> _Parsed:
        generation = self.generation()
        key = (self._handle.ref.identity, self._delimiter)
        found = PARSE_CACHE.get(key, generation)
        if found is not None:
            return found
        window = self._handle.read_window(max_bytes=DELIMITED_PARSE_MAX_BYTES)
        parsed = parse_delimited(
            window.data, has_more=window.has_more, delimiter=self._delimiter, generation=generation
        )
        PARSE_CACHE.put(key, parsed)
        return parsed

    @staticmethod
    def _require_table(table: str) -> None:
        if table:
            raise TableNotFoundError(
                f"a delimited file is one table and has no table {table!r}", table=table
            )

    def tables(self) -> Sequence[TableInfo]:
        return (TableInfo(id="", label=self._handle.name, group="tables", keyed=False),)

    def schema(self, table: str) -> TableSchema:
        self._require_table(table)
        return _schema(self._parsed())

    def rows(self, table: str, query: TableQuery, budget: Budget) -> TablePage:
        self._require_table(table)
        return _page(self._parsed(), query, budget)

    def record(self, table: str, key: str, budget: Budget) -> TableRecord:
        self._require_table(table)
        parsed = self._parsed()
        index = _row_index(parsed, key)
        return TableRecord(
            key=key,
            cells=_cells(parsed, index, _all_columns(parsed), max_bytes=TABLE_RECORD_VALUE_BYTES),
            generation=parsed.generation,
            positional=True,
        )

    def card(self, table: str, key: str, budget: Budget) -> TableCard:
        self._require_table(table)
        parsed = self._parsed()
        index = _row_index(parsed, key)
        names = _all_columns(parsed)
        cells = _cells(
            parsed, index, names[: TABLE_CARD_MAX_FIELDS + 1], max_chars=TABLE_CELL_PREVIEW_CHARS
        )
        label = cells.pop(names[0], None) if names else None
        return TableCard(key=key, label=label, cells=cells, generation=parsed.generation)


def adapter(handle: TableHandle) -> DelimitedSource:
    """The `[[table_source]]` adapter for the `delimited` kind."""

    return DelimitedSource(handle)


def _all_columns(parsed: _Parsed) -> tuple[str, ...]:
    names = tuple(column.name for column in parsed.columns)
    return (*names, _extra_name(parsed)) if parsed.has_extra else names


def _extra_name(parsed: _Parsed) -> str:
    names = {column.name for column in parsed.columns}
    name, number = _EXTRA, 1
    while name in names:
        number += 1
        name = f"{_EXTRA}_{number}"
    return name


def _schema(parsed: _Parsed) -> TableSchema:
    fields = [
        TableField(
            name=column.name,
            type=column.type,
            sortable=True,
            filterable=True,
            numeric=column.type in ("integer", "real"),
        )
        for column in parsed.columns
    ]
    if parsed.has_extra:
        fields.append(
            TableField(
                name=_extra_name(parsed),
                type="text",
                title="Extra cells",
                list=True,
                sort_note="the cells of rows longer than the header, as a list",
            )
        )
    return TableSchema(
        table="",
        fields=tuple(fields),
        key=(),
        default_columns=_all_columns(parsed),
    )


def _row_index(parsed: _Parsed, key: str) -> int:
    position = parse_position_key(key)
    if position is None or position > len(parsed.rows):
        raise RecordNotFoundError(f"{key!r} names no row of this file", key=key)
    return position - 1


def _cell(
    parsed: _Parsed,
    index: int,
    column: int,
    *,
    max_chars: int | None,
    max_bytes: int | None,
) -> tuple[bool, Cell]:
    """(present, cell) for one cell; an absent cell is not present."""

    value = parsed.value(index, column)
    if value is None:
        return False, None
    invalid = (index, column) in parsed.invalid
    column_type = parsed.columns[column].type
    as_text = text_cell(value, max_chars=max_chars, max_bytes=max_bytes, invalid_utf8=invalid)
    if column_type == "text":
        return True, as_text
    if not value:
        return True, None
    typed = _typed(column_type, value)
    if typed is None:
        return True, stored_cell(as_text, "text")
    if isinstance(typed, bool):
        return True, typed
    if isinstance(typed, int):
        return True, integer_cell(typed)
    if isinstance(typed, float):
        return True, real_cell(typed)
    return True, typed


def _cells(
    parsed: _Parsed,
    index: int,
    names: Sequence[str],
    *,
    max_chars: int | None = None,
    max_bytes: int | None = None,
) -> dict[str, Cell]:
    positions = {column.name: number for number, column in enumerate(parsed.columns)}
    cells: dict[str, Cell] = {}
    for name in names:
        number = positions.get(name)
        if number is None:
            extra = parsed.extra(index)
            if extra is not None:
                offset = len(parsed.columns)
                cells[name] = [
                    text_cell(
                        value,
                        max_chars=max_chars,
                        max_bytes=max_bytes,
                        invalid_utf8=(index, offset + place) in parsed.invalid,
                    )
                    for place, value in enumerate(extra)
                ]
            continue
        present, cell = _cell(parsed, index, number, max_chars=max_chars, max_bytes=max_bytes)
        if present:
            cells[name] = cell
    return cells


# ── Queries ────────────────────────────────────────────────────

RowTest = Callable[[int], bool]
_COMPARISONS: dict[str, Callable[[SortKey, SortKey], bool]] = {
    "eq": operator.eq,
    "ne": operator.ne,
    "lt": operator.lt,
    "le": operator.le,
    "gt": operator.gt,
    "ge": operator.ge,
}


def _filter_test(parsed: _Parsed, item: Filter) -> RowTest:
    number = next(i for i, column in enumerate(parsed.columns) if column.name == item.field)
    column = parsed.columns[number]

    def raw(index: int) -> str | None:
        return parsed.value(index, number)

    if item.op == "null":
        return lambda index: column.sort_key(raw(index)) == (0,)
    if item.op == "notnull":
        return lambda index: column.sort_key(raw(index)) != (0,)
    value = item.value or ""
    if item.op == "contains":
        needle = value.casefold()
        return lambda index: needle in (raw(index) or "").casefold()
    target = TableField(name=column.name, type=column.type)
    coerced = coerce_filter_value(target, value)
    wanted: SortKey = (2, coerced) if column.type == "text" else (1, coerced)
    compare = _COMPARISONS[item.op]

    def test(index: int) -> bool:
        key = column.sort_key(raw(index))
        # A null is unknown to every comparison, as in SQL.
        return key != (0,) and compare(key, wanted)

    return test


def _search_test(parsed: _Parsed, q: str) -> tuple[RowTest, tuple[str, ...]]:
    needle = q.casefold()
    columns = [number for number, column in enumerate(parsed.columns) if column.type == "text"]

    def test(index: int) -> bool:
        row = parsed.rows[index]
        return any(number < len(row) and needle in row[number].casefold() for number in columns)

    return test, tuple(parsed.columns[number].name for number in columns)


@dataclass(frozen=True, slots=True)
class _Scan:
    matches: list[int]
    complete: bool
    examined: int


def _scan(parsed: _Parsed, tests: Sequence[RowTest], budget: Budget) -> _Scan:
    if not tests:
        return _Scan(
            matches=list(range(len(parsed.rows))), complete=True, examined=len(parsed.rows)
        )
    matches: list[int] = []
    for index in range(len(parsed.rows)):
        if index % _BUDGET_CHECK_ROWS == 0 and index and budget.expired():
            return _Scan(matches=matches, complete=False, examined=index)
        if all(test(index) for test in tests):
            matches.append(index)
    return _Scan(matches=matches, complete=True, examined=len(parsed.rows))


def _sort_cursor(key: SortKey, index: int) -> list[Any]:
    rank, *rest = key
    value = rest[0] if rest else None
    if isinstance(value, float):
        value = real_cell(value)
    return [rank, value, index + 1]


def _cursor_point(values: list[Any], sorted_by: _Column | None) -> tuple[SortKey, int]:
    """The (sort key, row index) a `c.` cursor names."""

    try:
        if sorted_by is None:
            (position,) = values
            return (), int(position) - 1
        rank, value, position = values
        if isinstance(value, dict):
            value = float(str(value["real"]))  # pyright: ignore[reportUnknownArgumentType]
        key: SortKey = (0,) if rank == 0 else (int(rank), value)
        return key, int(position) - 1
    except (TypeError, ValueError, KeyError) as exc:
        raise TableQueryError("after is not a cursor for this sort", param="after") from exc


def _ordered(
    parsed: _Parsed, query: TableQuery, matches: list[int]
) -> tuple[list[int], _Column | None]:
    """The matching rows in the query's order, and the column it sorts by."""

    if query.sort is None:
        ordered = matches
        sorted_by = None
    else:
        number = next(i for i, column in enumerate(parsed.columns) if column.name == query.sort)
        sorted_by = parsed.columns[number]
        index = parsed.sort_index(number)
        if len(matches) == len(parsed.rows):
            ordered = index
        else:
            wanted = bytearray(len(parsed.rows))
            for match in matches:
                wanted[match] = 1
            ordered = [row for row in index if wanted[row]]
    if query.order == "desc":
        ordered = ordered[::-1]
    return ordered, sorted_by


def _start(
    parsed: _Parsed, query: TableQuery, ordered: list[int], sorted_by: _Column | None
) -> int | None:
    """Where in `ordered` the page starts, or None when a positional cursor expired."""

    if query.after is None:
        return 0
    positional = parse_positional_cursor(query.after)
    if positional is not None:
        served, generation = positional
        return served if generation == parsed.generation else None
    key, row = _cursor_point(decode_cursor(query.after), sorted_by)
    if sorted_by is None:
        point: Callable[[int], tuple[Any, ...]] = lambda index: (index,)
        target: tuple[Any, ...] = (row,)
    else:
        number = parsed.columns.index(sorted_by)
        point = lambda index: (sorted_by.sort_key(parsed.value(index, number)), index)
        target = (key, row)
    if query.order == "asc":
        return bisect_right(ordered, target, key=point)
    # Descending: `ordered` falls, so search its rising mirror.
    rising = _Reversed(ordered)
    return len(ordered) - bisect_left(rising, target, key=point)


class _Reversed(Sequence[int]):
    """A list read back to front without copying it."""

    def __init__(self, items: list[int]) -> None:
        self._items = items

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, index: int) -> int:  # type: ignore[override]
        return self._items[len(self._items) - 1 - index]

    def __iter__(self) -> Iterator[int]:
        return reversed(self._items)


def _next_after(
    parsed: _Parsed, ordered: list[int], end: int, sorted_by: _Column | None
) -> str | None:
    if end >= len(ordered):
        return None
    last = ordered[end - 1]
    if sorted_by is None:
        token = encode_cursor([last + 1])
    else:
        number = parsed.columns.index(sorted_by)
        token = encode_cursor(_sort_cursor(sorted_by.sort_key(parsed.value(last, number)), last))
    return token if token is not None else positional_cursor(end, parsed.generation)


def _page(parsed: _Parsed, query: TableQuery, budget: Budget) -> TablePage:
    tests: list[RowTest] = [_filter_test(parsed, item) for item in query.filters]
    searched: tuple[str, ...] | None = None
    if query.q is not None:
        search, searched = _search_test(parsed, query.q)
        tests.append(search)
    columns = page_columns(query, _schema(parsed))
    scan = _scan(parsed, tests, budget)
    if not scan.complete:
        # A partial scan cannot be sorted honestly; the rows it found come back in key
        # order, and the envelope says how far it got.
        rows = tuple(_row(parsed, index, columns) for index in scan.matches[: query.limit])
        return TablePage(
            rows=rows,
            columns=columns,
            next_after=None,
            complete=False,
            truncated=parsed.truncated,
            generation=parsed.generation,
            count=len(scan.matches),
            count_complete=False,
            examined=scan.examined,
            searched=searched,
            reason="budget",
        )
    ordered, sorted_by = _ordered(parsed, query, scan.matches)
    start = _start(parsed, query, ordered, sorted_by)
    if start is None:
        return TablePage(
            rows=(),
            columns=columns,
            next_after=None,
            complete=False,
            truncated=parsed.truncated,
            generation=parsed.generation,
            count=len(ordered),
            count_complete=not parsed.truncated,
            searched=searched,
            reason="cursor_expired",
        )
    end = min(start + query.limit, len(ordered))
    rows = tuple(_row(parsed, index, columns) for index in ordered[start:end])
    return TablePage(
        rows=rows,
        columns=columns,
        next_after=_next_after(parsed, ordered, end, sorted_by),
        complete=not parsed.truncated,
        truncated=parsed.truncated,
        generation=parsed.generation,
        count=len(ordered),
        count_complete=not parsed.truncated,
        searched=searched,
        reason="source_truncated" if parsed.truncated else None,
    )


def _row(parsed: _Parsed, index: int, columns: Sequence[str]) -> TableRow:
    return TableRow(
        key=_name_of(index),
        cells=_cells(parsed, index, columns, max_chars=TABLE_CELL_PREVIEW_CHARS),
    )
