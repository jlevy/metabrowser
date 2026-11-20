"""The delimited-text table source: a `.csv` or `.tsv` file as one table.

The file parses with the standard library's ``csv`` under these rules:

- The extension sets the delimiter, comma or tab; quoting is RFC 4180's double quote.
- Bytes are UTF-8, with a leading byte-order mark dropped. Invalid bytes are replaced
  and the cell holding them is marked ``invalid_utf8``.
- The first row is the header. An empty name becomes ``column_<n>``, counting columns
  from 1, and a repeated name gains ``_<n>`` for its nth use (the next number whose
  name is free).
- A blank line is not a row. A short row's missing cells are absent, which the wire
  shows apart from empty; a long row's extra cells go to one trailing ``extra`` field,
  a list.
- Types are inferred from the first ``DELIMITED_TYPE_SAMPLE_ROWS`` rows' nonempty
  values; a later value that contradicts its column's type is a ``{value, stored}``
  cell. An empty value is null in a column of any type but text, where it is the empty
  string. A date or datetime sorts as its text, which for a datetime is not its instant
  when values mix separators or offsets; its field says so in ``sort_note``.
- Rows have no key; a row is named by its 1-based position in the file, so a name
  survives any change of sort or filter. A sort breaks ties by that position, and a
  cursor names a sort value and a position, so a page under a new generation continues
  from the same place in the order; a row inserted above another in the file moves it.
- The generation is the file's identity, size, and modification time.

A file is parsed whole, up to ``DELIMITED_PARSE_MAX_BYTES``, ``DELIMITED_MAX_ROWS``
rows, and ``DELIMITED_MAX_CELLS`` cells, and held in a cache keyed by its generation and
bounded in the bytes its shape is measured to hold and in entries; a sort index is built
on demand, counted in those bytes, and kept with it. One parse of a file runs at a time,
and a request that arrives during it waits for it. A larger file shows its leading rows,
and its count, sort, and filter say they cover only those rows (``complete: false``,
``truncated: true``). A row's cells past ``DELIMITED_MAX_COLUMNS``, the header's among
them, are not read, and the file says so the same way.
"""

from __future__ import annotations

import csv
import io
import re
import threading
from array import array
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from metabrowser.builtin_plugins.table import memory
from metabrowser.builtin_plugins.table.memory import (
    BUDGET_CHECK_ROWS,
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
    stored_cell,
    text_cell,
)

# ── Bounds ─────────────────────────────────────────────────────
#
# A parse is not interruptible, so these bound the first request's latency and the
# cache's memory. What a parse costs follows the file's rows and cells, not its bytes, so
# each has its own bound; past any of them the file shows its leading rows and says so.
# Measured with `devtools/bench_table_source.py`, as the bounds in
# `metabrowser.table_source` are (a shared 4-processor Linux container, Python 3.12,
# 2026-11-20); rerun it for the current numbers.
#
# With no row or cell bound, a 16 MiB file was far dearer narrow than wide. Twelve
# columns (151,000 rows) parsed in 0.31 s and held 118 MB, 7 bytes per byte of file; one
# column of integer IDs (2.1 million rows) parsed in 1.44 s, held 302 MB, and took 1.65 s
# for its first sort index and 1.59 s for each filtered and sorted page after it; one
# column of one character (8.4 million rows) parsed in 4.8 s, held 805 MB, and took
# 6.7 s to sort. Under the bounds below, every shape the bench builds parsed in at most
# 0.29 s and took at most 0.51 s for a first sort index and 0.35 s for a filtered and
# sorted page, so a first filtered and sorted page cost about one second, half of
# `TABLE_REQUEST_DEADLINE_SECONDS`, and held at most 129 MB (six columns of two-digit
# integers, cut at the cell bound after 333,000 rows).

# The most bytes of a file parsed: 16 MiB of the 12-column shape, about 150,000 rows.
DELIMITED_PARSE_MAX_BYTES = 16 * 1024 * 1024

# The most rows of a file parsed, the header's excepted. At this bound one column of
# integer IDs parsed in 0.25 s and held 72 MB, its first sort index took 0.43 s, and a
# filtered and sorted page 0.35 s; one column of one character parsed in 0.18 s.
DELIMITED_MAX_ROWS = 500_000

# The most cells of a file parsed, the header's among them: above the 1.8 million the
# 12-column shape holds at the byte cap, so that file is read whole. Six columns of
# two-digit integers reached it after 333,000 rows, parsed in 0.29 s, and held 129 MB.
DELIMITED_MAX_CELLS = 2_000_000

# The most cells of one row read, the header's among them; a cell past it is not read.
# A row's cells are what a schema, a record, and the type sample scale with: at this
# width the schema encoded in 3 ms as 0.42 MB of JSON, and the sample of 1,000 rows of
# datetimes, the dearest values to infer, took 0.37 s of a 0.62 s parse. A page carries
# fewer wide rows (`TABLE_PAGE_CELLS_MAX`): 11 at this width, 0.36 MB in 10 ms.
DELIMITED_MAX_COLUMNS = 1024

# Rows whose values decide each column's type. A later value that contradicts the type
# is shown as stored, not hidden. Inference tries at most five patterns a value, and
# stops a pattern at the first value that fails it; its dearest case is measured at
# `DELIMITED_MAX_COLUMNS` above.
DELIMITED_TYPE_SAMPLE_ROWS = 1000

# The parse cache's bounds: entries, and the bytes the parsed files and their sort
# indexes are estimated to hold (`_Parsed.held_bytes`). Two files of the 12-column shape
# at the byte cap fit (133 MB estimated each), as does one file at the row and cell
# bounds whose text is not ASCII, the dearest estimate the bounds admit (about 230 MB).
DELIMITED_CACHE_MAX_ENTRIES = 8
DELIMITED_CACHE_MAX_BYTES = 256 * 1024 * 1024

# What a parse holds, measured with `tracemalloc` over the bench's shapes, from one
# column of one character to 1,024 columns of datetimes: each row's list, each cell's string and
# its slot in the row, and the text itself, one byte a character when the text is ASCII
# and at most four otherwise. A cell marked invalid UTF-8 costs its entry in the set
# that marks it and its wider replaced string: 200,000 rows of two such cells held
# 60 MB more than the same rows valid, 149 bytes a cell. These are upper fits: the bench
# prints each shape's measured and estimated bytes, and no estimate is below what was
# measured.
_HELD_BYTES_PER_ROW = 96
_HELD_BYTES_PER_CELL = 56
_HELD_BYTES_PER_INVALID_CELL = 160

_DELIMITERS = {".csv": ",", ".tsv": "\t"}
_BOM = b"\xef\xbb\xbf"
_EXTRA = "extra"
# Decoding with `surrogateescape` turns each invalid byte into one of these.
_ESCAPED_BYTE = re.compile("[\udc80-\udcff]")

# One parse at a time, process-wide, which bounds the transient memory of first opens to
# one file's. A cell longer than the `csv` module's default field limit (131,072
# characters) is a parse error there, and a parse is bounded by the byte cap above, so a
# parse raises the limit to that cap and restores it after. The limit is global to the
# `csv` module: this lock serializes the parses that change it, and another thread's
# `csv` reader that runs during a parse sees the raised limit.
_PARSE_LOCK = threading.Lock()


@contextmanager
def _parsing() -> Generator[None]:
    with _PARSE_LOCK:
        previous = csv.field_size_limit(max(csv.field_size_limit(), DELIMITED_PARSE_MAX_BYTES))
        try:
            yield
        finally:
            csv.field_size_limit(previous)


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


_DATETIME_SORT_NOTE = (
    "sorted as text: a value's date and time as written, not its instant, so values "
    "that mix separators or offsets sort by their spelling"
)


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
    """One generation of one file, parsed.

    `rows_cut` says rows past a parse bound were not read, so a count, sort, or filter
    covers only those read; `cells_cut` says a row's cells past `DELIMITED_MAX_COLUMNS`
    were not read. `width` is the most cells any row holds. `parsed_bytes` is what the
    rows hold before any sort index (:attr:`held_bytes` adds those)."""

    generation: str
    columns: tuple[_Column, ...]
    rows: list[list[str]]
    width: int
    rows_cut: bool
    cells_cut: bool
    parsed_bytes: int
    invalid: frozenset[tuple[int, int]]
    sort_indexes: dict[str, array[int]] = field(default_factory=dict[str, array[int]])
    lock: threading.Lock = field(default_factory=threading.Lock)
    _schema: TableSchema | None = None
    _positions: dict[str, int] | None = None

    @property
    def truncated(self) -> bool:
        return self.rows_cut or self.cells_cut

    @property
    def has_extra(self) -> bool:
        return self.width > len(self.columns)

    @property
    def held_bytes(self) -> int:
        return self.parsed_bytes + index_bytes(self)

    def value(self, index: int, column: int) -> str | None:
        row = self.rows[index]
        return row[column] if column < len(row) else None

    def extra(self, index: int) -> list[str] | None:
        row = self.rows[index]
        return row[len(self.columns) :] if len(row) > len(self.columns) else None

    def schema(self) -> TableSchema:
        if self._schema is None:
            self._schema = _schema(self)
        return self._schema

    # ── The memory table (metabrowser.builtin_plugins.table.memory) ──

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def budget_check_rows(self) -> int:
        return BUDGET_CHECK_ROWS

    def is_null(self, index: int, column: int) -> bool:
        return self.sort_key(index, column) == NULL_KEY

    def sort_key(self, index: int, column: int) -> SortKey:
        return self.columns[column].sort_key(self.value(index, column))

    def text(self, index: int, column: int) -> str | None:
        return self.value(index, column)

    def operand_key(self, column: int, raw: str) -> SortKey:
        found = self.columns[column]
        if found.type == "text":
            return (2, raw)
        return (1, coerce_filter_value(TableField(name=found.name, type=found.type), raw))

    def cursor_key(self, column: int, rank: int, value: Any) -> SortKey | None:
        found = self.columns[column]
        if rank == 1 and found.type != "text":
            return (1, _cursor_value(found, value))
        if rank == 2 and type(value) is str:
            return (2, value)
        return None

    def cells_per_row(self, names: Sequence[str]) -> int:
        return _cells_per_row(self, _plan(self, names))

    def cells(
        self,
        index: int,
        names: Sequence[str],
        *,
        max_chars: int | None = None,
        max_bytes: int | None = None,
    ) -> dict[str, Cell]:
        return _cells(self, index, _plan(self, names), max_chars=max_chars, max_bytes=max_bytes)

    def page_cells(
        self, indexes: Sequence[int], names: Sequence[str], *, max_chars: int
    ) -> list[dict[str, Cell]]:
        plan = _plan(self, names)
        return [_cells(self, index, plan, max_chars=max_chars) for index in indexes]


def _column_names(header: Sequence[str]) -> list[str]:
    """Each header cell's column name, in time linear in the header: a repeated name
    takes the next free `_<n>`, remembering per name where its search stopped."""

    names: list[str] = []
    taken: set[str] = set()
    next_use: dict[str, int] = {}
    for number, raw in enumerate(header, start=1):
        base = raw or f"column_{number}"
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


def _read_records(
    text: str, *, delimiter: str, has_more: bool
) -> tuple[list[list[str]], bool, bool, int]:
    """(records, rows_cut, cells_cut, cells): the file's nonblank records, the header's
    first, up to the row and cell bounds, each cut at the column bound."""

    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, quotechar='"')
    records: list[list[str]] = []
    cells = 0
    cells_cut = False
    stopped = False
    try:
        for record in reader:
            if not record:
                continue
            if len(record) > DELIMITED_MAX_COLUMNS:
                del record[DELIMITED_MAX_COLUMNS:]
                cells_cut = True
            if len(records) > DELIMITED_MAX_ROWS or cells + len(record) > DELIMITED_MAX_CELLS:
                stopped = True
                break
            records.append(record)
            cells += len(record)
    except csv.Error as exc:
        if not has_more:
            raise SourceUnreadableError(f"not readable as delimited text: {exc}") from exc
    if has_more and not stopped and records:
        # The read stopped at the byte cap, so the last record may be cut.
        cells -= len(records.pop())
    return records, has_more or stopped, cells_cut, cells


def parse_delimited(data: bytes, *, has_more: bool, delimiter: str, generation: str) -> _Parsed:
    """Parse one bounded read of a delimited file. ``has_more`` says the read stopped at
    the byte cap, so the last record may be cut and is dropped."""

    with _parsing():
        return _parse(data, has_more=has_more, delimiter=delimiter, generation=generation)


def _parse(data: bytes, *, has_more: bool, delimiter: str, generation: str) -> _Parsed:
    if data.startswith(_BOM):
        data = data[len(_BOM) :]
    try:
        text = data.decode("utf-8")
        dirty = False
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="surrogateescape")
        dirty = True
    records, rows_cut, cells_cut, cells = _read_records(
        text, delimiter=delimiter, has_more=has_more
    )
    ascii_text = text.isascii()
    del text
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
    width = max((len(row) for row in rows), default=0)
    parsed_bytes = (
        len(records) * _HELD_BYTES_PER_ROW
        + cells * _HELD_BYTES_PER_CELL
        + len(invalid) * _HELD_BYTES_PER_INVALID_CELL
        + len(data) * (1 if ascii_text else 4)
    )
    return _Parsed(
        generation=generation,
        columns=columns,
        rows=rows,
        width=max(width, len(columns)),
        rows_cut=rows_cut,
        cells_cut=cells_cut,
        parsed_bytes=parsed_bytes,
        invalid=invalid,
    )


CacheKey = tuple[str, str]

PARSE_CACHE: MemoryCache[_Parsed] = MemoryCache(
    max_entries=lambda: DELIMITED_CACHE_MAX_ENTRIES, max_bytes=lambda: DELIMITED_CACHE_MAX_BYTES
)


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

        def parse() -> _Parsed:
            window = self._handle.read_window(max_bytes=DELIMITED_PARSE_MAX_BYTES)
            return parse_delimited(
                window.data,
                has_more=window.has_more,
                delimiter=self._delimiter,
                generation=generation,
            )

        return PARSE_CACHE.load((self._handle.ref.identity, self._delimiter), generation, parse)

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
        return self._parsed().schema()

    def rows(self, table: str, query: TableQuery, budget: Budget) -> TablePage:
        self._require_table(table)
        parsed = self._parsed()
        indexes = len(parsed.sort_indexes)
        page = memory.page(parsed, query, budget)
        if len(parsed.sort_indexes) != indexes:
            PARSE_CACHE.trim()
        return page

    def record(self, table: str, key: str, budget: Budget) -> TableRecord:
        self._require_table(table)
        parsed = self._parsed()
        index = memory.row_index(parsed, key)
        names = parsed.schema().default_columns
        return TableRecord(
            key=key,
            cells=_cells(parsed, index, _plan(parsed, names), max_bytes=TABLE_RECORD_VALUE_BYTES),
            generation=parsed.generation,
            positional=True,
        )

    def card(self, table: str, key: str, budget: Budget) -> TableCard:
        self._require_table(table)
        parsed = self._parsed()
        index = memory.row_index(parsed, key)
        names = parsed.schema().default_columns[: TABLE_CARD_MAX_FIELDS + 1]
        cells = _cells(parsed, index, _plan(parsed, names), max_chars=TABLE_CELL_PREVIEW_CHARS)
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
            sort_note=_DATETIME_SORT_NOTE if column.type == "datetime" else None,
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


# The cells a page, record, or card carries: each name with its column number, or None
# for the `extra` list.
CellPlan = Sequence[tuple[str, int | None]]


def _plan(parsed: _Parsed, names: Sequence[str]) -> CellPlan:
    if parsed._positions is None:  # pyright: ignore[reportPrivateUsage]
        parsed._positions = {column.name: number for number, column in enumerate(parsed.columns)}  # pyright: ignore[reportPrivateUsage]
    positions = parsed._positions  # pyright: ignore[reportPrivateUsage]
    return [(name, positions.get(name)) for name in names]


def _cells_per_row(parsed: _Parsed, plan: CellPlan) -> int:
    """The most cells one row carries under *plan*, the `extra` list's counted each."""

    extra = parsed.width - len(parsed.columns)
    return sum(1 if number is not None else extra for _name, number in plan)


def _cells(
    parsed: _Parsed,
    index: int,
    plan: CellPlan,
    *,
    max_chars: int | None = None,
    max_bytes: int | None = None,
) -> dict[str, Cell]:
    cells: dict[str, Cell] = {}
    for name, number in plan:
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


def _cursor_value(column: _Column, value: Any) -> Any:
    """A rank-1 cursor value checked against the sort column's type, as its sort key
    holds it."""

    kind = column.type
    if kind == "integer" and type(value) is int:
        return value
    if kind == "real":
        number = memory.cursor_number(value)
        if number is not None:
            return float(number)
    if kind == "boolean" and type(value) is bool:
        return value
    if kind in ("date", "datetime") and type(value) is str:
        return value
    raise memory.bad_cursor(f"its value is not of {column.name!r}'s type, {kind}")
