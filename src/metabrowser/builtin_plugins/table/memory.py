"""In-memory tables: the query engine of the built-in sources that read a whole file.

A source that holds one table's rows in memory, as the delimited source holds a parsed
CSV file and the structured plugin's record-list source holds a parsed JSON or YAML
list, answers the rows route through :func:`page` here: a filter and search scan within
the request's budget, a sort through an index built on demand and kept with the rows, and
cursors that name a sort position. The source supplies what differs between files
through the :class:`MemoryTable` protocol, chiefly each value's sort key and text, and
keeps the rows, its parse bounds, and its cache (:class:`MemoryCache`) to itself.

Every row of a memory table has no key and is named by its 1-based position in the file
(`@<n>`), so a name survives any change of sort or filter. A sort breaks ties by that
position, and a cursor names a sort value and a position, so a page under a new
generation continues from the same place in the order; a row inserted above another in
the file moves it.

A sort key is a tuple whose first element ranks the value's storage class: ``(0,)`` for
null or absent, ``(1, value)`` for a number or a value of the column's own type, ``(2,
text)`` for text, and ``(3, text)`` for a nested value by its JSON text, a source's own
rank past text. SQLite orders storage classes alike, so every source sorts mixed columns
the same way.

This module is the built-in sources' own, not SDK surface: an installed source answers
the protocol in :mod:`metabrowser.table_source` however it likes.
"""

from __future__ import annotations

import json
import operator
import threading
from array import array
from bisect import bisect_left, bisect_right
from collections import OrderedDict
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from metabrowser.plugin_api import (
    TABLE_CELL_PREVIEW_CHARS,
    Budget,
    Cell,
    FieldType,
    Filter,
    PageReason,
    RecordNotFoundError,
    TablePage,
    TableQuery,
    TableQueryError,
    TableRow,
    TableSchema,
    decode_cursor,
    encode_cursor,
    page_columns,
    page_row_limit,
    parse_position_key,
    parse_positional_cursor,
    position_key,
    positional_cursor,
    real_cell,
)

# How often a scan checks its budget, in rows: often enough to stop within a few
# milliseconds, rarely enough to cost nothing measurable.
BUDGET_CHECK_ROWS = 4096

SortKey = tuple[Any, ...]
NULL_KEY: SortKey = (0,)


class MemoryColumn(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def type(self) -> FieldType: ...


class MemoryTable(Protocol):
    """One generation of one file's rows, held in memory.

    `rows_cut` says rows past a parse bound were not read, so a count covers only those
    read; `truncated` says any of the content was not read. `sort_indexes` holds each
    built sort index by column name, under `lock`."""

    @property
    def generation(self) -> str: ...

    @property
    def rows_cut(self) -> bool: ...

    @property
    def truncated(self) -> bool: ...

    @property
    def row_count(self) -> int: ...

    @property
    def columns(self) -> Sequence[MemoryColumn]: ...

    @property
    def sort_indexes(self) -> dict[str, array[int]]: ...

    @property
    def lock(self) -> threading.Lock: ...

    def schema(self) -> TableSchema: ...

    def sort_key(self, index: int, column: int) -> SortKey:
        """The sort key of one value, by row index and column number."""
        ...

    def text(self, index: int, column: int) -> str | None:
        """One value as the text a `contains` filter and a search read, or None."""
        ...

    def operand_key(self, column: int, raw: str) -> SortKey:
        """A comparison filter's operand as a sort key of the column, refused with a
        `TableQueryError` when it is not of the column's type."""
        ...

    def cursor_key(self, column: int, rank: int, value: Any) -> SortKey | None:
        """The sort key a cursor's (rank, value) names in the column, or None when it is
        not a key the column's values can have."""
        ...

    def cells_per_row(self, names: Sequence[str]) -> int:
        """The most cells one row carries for the fields *names*, a list's counted each."""
        ...

    def cells(
        self,
        index: int,
        names: Sequence[str],
        *,
        max_chars: int | None = None,
        max_bytes: int | None = None,
    ) -> dict[str, Cell]:
        """One row's cells for the fields *names*; an absent value has no entry."""
        ...


def column_number(table: MemoryTable, name: str, param: str) -> int:
    """The column a query names, refused as a bad query when there is none, so a source
    answers correctly whatever the route checked against."""

    for number, column in enumerate(table.columns):
        if column.name == name:
            return number
    raise TableQueryError(f"no field named {name!r}", param=param, field=name)


def sort_index(table: MemoryTable, column: int, budget: Budget) -> array[int] | None:
    """Row indexes in ascending order of one column, ties by position, or None when the
    index is not built yet and the budget has run out."""

    name = table.columns[column].name
    with table.lock:
        found = table.sort_indexes.get(name)
        if found is None:
            if budget.expired():
                return None
            total = table.row_count
            keys = [table.sort_key(index, column) for index in range(total)]
            order = sorted(range(total), key=lambda index: (keys[index], index))
            del keys
            found = array("I", order)
            table.sort_indexes[name] = found
        return found


def index_bytes(table: MemoryTable) -> int:
    """What a table's sort indexes hold."""

    return sum(len(index) * index.itemsize for index in list(table.sort_indexes.values()))


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


def _filter_test(table: MemoryTable, item: Filter) -> RowTest:
    number = column_number(table, item.field, f"f.{item.field}")

    if item.op == "null":
        return lambda index: table.sort_key(index, number) == NULL_KEY
    if item.op == "notnull":
        return lambda index: table.sort_key(index, number) != NULL_KEY
    value = item.value or ""
    if item.op == "contains":
        needle = value.casefold()
        return lambda index: needle in (table.text(index, number) or "").casefold()
    wanted = table.operand_key(number, value)
    compare = _COMPARISONS[item.op]

    def test(index: int) -> bool:
        key = table.sort_key(index, number)
        # A null is unknown to every comparison, as in SQL; values of storage classes
        # that do not compare with each other are not equal and order by their rank.
        if key == NULL_KEY:
            return False
        try:
            return compare(key, wanted)
        except TypeError:
            return item.op == "ne"

    return test


def _search_test(table: MemoryTable, q: str) -> tuple[RowTest, tuple[str, ...]]:
    """A search reads the text fields only, and says which it read."""

    needle = q.casefold()
    columns = [number for number, column in enumerate(table.columns) if column.type == "text"]

    def test(index: int) -> bool:
        for number in columns:
            text = table.text(index, number)
            if text is not None and needle in text.casefold():
                return True
        return False

    return test, tuple(table.columns[number].name for number in columns)


@dataclass(frozen=True, slots=True)
class Scan:
    """The rows a scan matched, in the order it visited them, and how far it got."""

    matches: Sequence[int]
    complete: bool
    examined: int


def scan(table: MemoryTable, tests: Sequence[RowTest], budget: Budget, *, descending: bool) -> Scan:
    """Visit the rows in file order, or its reverse, keeping those every test passes,
    until the budget runs out."""

    total = table.row_count
    visit = range(total - 1, -1, -1) if descending else range(total)
    if not tests:
        return Scan(matches=visit, complete=True, examined=total)
    matches: list[int] = []
    for count, index in enumerate(visit):
        if count % BUDGET_CHECK_ROWS == 0 and count and budget.expired():
            return Scan(matches=matches, complete=False, examined=count)
        if all(test(index) for test in tests):
            matches.append(index)
    return Scan(matches=matches, complete=True, examined=total)


# ── Cursors ────────────────────────────────────────────────────
#
# A `c.` cursor is `[sort, order, *point]`: the field the query sorted by (null for file
# order) and its order, so a cursor sent with another sort is refused by name, then the
# point after which the next page starts: `[position]` in file order, and
# `[rank, value, position]` in a sort, where (rank, value) is the sort key and position
# counts from 1.


def _sort_cursor(query: TableQuery, key: SortKey, index: int) -> list[Any]:
    rank, *rest = key
    value = rest[0] if rest else None
    if isinstance(value, float):
        value = real_cell(value)
    return [query.sort, query.order, rank, value, index + 1]


def bad_cursor(detail: str) -> TableQueryError:
    return TableQueryError(f"after is not a cursor for this query: {detail}", param="after")


def cursor_number(value: Any) -> int | float | None:
    """A number a cursor carries, as `real_cell` wrote it, or None for any other value."""

    if type(value) in (int, float):
        return value
    if isinstance(value, dict) and value.get("real") in ("inf", "-inf", "nan"):  # pyright: ignore[reportUnknownMemberType]
        return float(str(value["real"]))  # pyright: ignore[reportUnknownArgumentType]
    return None


def _cursor_position(value: Any) -> int:
    if type(value) is not int or value < 1:
        raise bad_cursor("its position is not a positive integer")
    return value - 1


def _cursor_point(
    table: MemoryTable, values: list[Any], query: TableQuery, sorted_by: int | None
) -> tuple[SortKey, int]:
    """The (sort key, row index) a `c.` cursor names, refused unless it was minted for
    this query's sort and order and its point fits the sort column."""

    if len(values) < 3:
        raise bad_cursor("it has too few parts")
    sort, order, *point = values
    if sort != query.sort or order != query.order:
        made_for = f"sort={json.dumps(sort)} order={json.dumps(order)}"
        raise bad_cursor(f"it was made for {made_for}")
    if sorted_by is None:
        if len(point) != 1:
            raise bad_cursor("it is not a position")
        return (), _cursor_position(point[0])
    if len(point) != 3:
        raise bad_cursor("it is not a sort position")
    rank, value, position = point
    row = _cursor_position(position)
    if type(rank) is not int:
        raise bad_cursor("its rank is not an integer")
    if rank == 0 and value is None:
        return NULL_KEY, row
    key = table.cursor_key(sorted_by, rank, value)
    if key is None:
        raise bad_cursor("its sort key does not fit the sort column")
    return key, row


def _ordered(
    table: MemoryTable, query: TableQuery, matches: Sequence[int], budget: Budget
) -> tuple[Sequence[int], int | None] | None:
    """The matching rows in the query's order and the column it sorts by, or None when
    the sort's index is not built and the budget has run out. Matches of a query with
    no sort are already in its order (`scan` visits them so)."""

    if query.sort is None:
        return matches, None
    number = column_number(table, query.sort, "sort")
    index = sort_index(table, number, budget)
    if index is None:
        return None
    ordered: Sequence[int]
    if len(matches) == table.row_count:
        ordered = index
    else:
        wanted = bytearray(table.row_count)
        for match in matches:
            wanted[match] = 1
        ordered = [row for row in index if wanted[row]]
    if query.order == "desc":
        ordered = ordered[::-1]
    return ordered, number


def _start(
    table: MemoryTable, query: TableQuery, ordered: Sequence[int], sorted_by: int | None
) -> int | None:
    """Where in `ordered` the page starts, or None when a positional cursor expired."""

    if query.after is None:
        return 0
    positional = parse_positional_cursor(query.after)
    if positional is not None:
        served, generation = positional
        return served if generation == table.generation else None
    key, row = _cursor_point(table, decode_cursor(query.after), query, sorted_by)
    if sorted_by is None:
        point: Callable[[int], tuple[Any, ...]] = lambda index: (index,)
        target: tuple[Any, ...] = (row,)
    else:
        number = sorted_by
        point = lambda index: (table.sort_key(index, number), index)
        target = (key, row)
    try:
        if query.order == "asc":
            return bisect_right(ordered, target, key=point)
        # Descending: `ordered` falls, so search its rising mirror.
        return len(ordered) - bisect_left(_Reversed(ordered), target, key=point)
    except TypeError as exc:  # a key of a type the column's keys do not compare with
        raise bad_cursor("its sort key does not fit the sort column") from exc


class _Reversed(Sequence[int]):
    """A sequence read back to front without copying it."""

    def __init__(self, items: Sequence[int]) -> None:
        self._items = items

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, index: int) -> int:  # type: ignore[override]
        return self._items[len(self._items) - 1 - index]

    def __iter__(self) -> Iterator[int]:
        return reversed(self._items)


def _next_after(
    table: MemoryTable,
    query: TableQuery,
    ordered: Sequence[int],
    end: int,
    sorted_by: int | None,
) -> str | None:
    if end >= len(ordered):
        return None
    last = ordered[end - 1]
    if sorted_by is None:
        token = encode_cursor([None, query.order, last + 1])
    else:
        token = encode_cursor(_sort_cursor(query, table.sort_key(last, sorted_by), last))
    return token if token is not None else positional_cursor(end, table.generation)


def page(table: MemoryTable, query: TableQuery, budget: Budget) -> TablePage:
    """One page of a memory table's rows, in the collection envelope."""

    tests: list[RowTest] = [_filter_test(table, item) for item in query.filters]
    searched: tuple[str, ...] | None = None
    if query.q is not None:
        search, searched = _search_test(table, query.q)
        tests.append(search)
    columns = page_columns(query, table.schema())
    limit = page_row_limit(query.limit, table.cells_per_row(columns))
    # A query with no sort is in file order, so its scan visits rows in that order and
    # what it finds before the budget runs out is a prefix of the answer.
    found = scan(table, tests, budget, descending=query.sort is None and query.order == "desc")
    count_complete = found.complete and not table.rows_cut
    examined = None if found.complete else found.examined
    ordering = _ordered(table, query, found.matches, budget) if found.complete else None
    if ordering is None and query.sort is not None:
        # A sort cannot be returned in part.
        return TablePage(
            rows=(),
            columns=columns,
            next_after=None,
            complete=False,
            truncated=table.truncated,
            generation=table.generation,
            count=len(found.matches),
            count_complete=count_complete,
            examined=examined,
            searched=searched,
            reason="sort_budget",
            sort_refused=query.sort,
            limit=limit,
        )
    ordered, sorted_by = ordering if ordering is not None else (found.matches, None)
    start = _start(table, query, ordered, sorted_by)
    if start is None:
        return TablePage(
            rows=(),
            columns=columns,
            next_after=None,
            complete=False,
            truncated=table.truncated,
            generation=table.generation,
            count=len(ordered),
            count_complete=count_complete,
            examined=examined,
            searched=searched,
            reason="cursor_expired",
            limit=limit,
        )
    end = min(start + limit, len(ordered))
    rows = tuple(
        TableRow(
            key=position_key(index + 1),
            cells=table.cells(index, columns, max_chars=TABLE_CELL_PREVIEW_CHARS),
        )
        for index in ordered[start:end]
    )
    reason: PageReason | None = None
    if not found.complete:
        reason = "budget"
    elif table.truncated:
        reason = "source_truncated"
    return TablePage(
        rows=rows,
        columns=columns,
        next_after=_next_after(table, query, ordered, end, sorted_by),
        complete=found.complete and not table.truncated,
        truncated=table.truncated,
        generation=table.generation,
        count=len(ordered),
        count_complete=count_complete,
        examined=examined,
        searched=searched,
        reason=reason,
        limit=limit,
    )


def row_index(table: MemoryTable, key: str) -> int:
    """The row a record or card key names: a position no greater than the rows held."""

    position = parse_position_key(key)
    if position is None or position > table.row_count:
        raise RecordNotFoundError(f"{key!r} names no row of this file", key=key)
    return position - 1


# ── The cache ──────────────────────────────────────────────────


class Held(Protocol):
    """What a cache entry says of itself: the generation it was read under, and the
    bytes it is estimated to hold."""

    @property
    def generation(self) -> str: ...

    @property
    def held_bytes(self) -> int: ...


class MemoryCache[Entry: Held]:
    """Parsed files by a source's own key, each at the generation it was parsed under,
    bounded in entries and in the bytes the entries are estimated to hold; the most
    recently used entry is always kept.

    :meth:`load` is single-flight: while one request parses a file, another request for
    it waits for that parse instead of starting its own, then reads the cache again.
    """

    def __init__(self, *, max_entries: Callable[[], int], max_bytes: Callable[[], int]) -> None:
        # The bounds are read at each trim, so a test may lower a source's constant.
        self._max_entries = max_entries
        self._max_bytes = max_bytes
        self._held: OrderedDict[Any, Entry] = OrderedDict()
        self._loading: dict[Any, threading.Event] = {}
        self._lock = threading.Lock()

    def get(self, key: Any, generation: str) -> Entry | None:
        with self._lock:
            return self._get(key, generation)

    def _get(self, key: Any, generation: str) -> Entry | None:
        found = self._held.get(key)
        if found is None or found.generation != generation:
            return None
        self._held.move_to_end(key)
        return found

    def load(self, key: Any, generation: str, parse: Callable[[], Entry]) -> Entry:
        """The file parsed under *generation*: from the cache, from a parse another
        request has under way, or from *parse*, which runs once per key at a time."""

        while True:
            with self._lock:
                found = self._get(key, generation)
                if found is not None:
                    return found
                pending = self._loading.get(key)
                if pending is None:
                    done = threading.Event()
                    self._loading[key] = done
                    break
            pending.wait()
        try:
            parsed = parse()
            self.put(key, parsed)
            return parsed
        finally:
            with self._lock:
                del self._loading[key]
            done.set()

    def put(self, key: Any, parsed: Entry) -> None:
        with self._lock:
            self._held[key] = parsed
            self._held.move_to_end(key)
            self._trim()

    def trim(self) -> None:
        """Evict to the bounds again, after an entry has grown by a sort index."""

        with self._lock:
            self._trim()

    def _trim(self) -> None:
        while len(self._held) > 1 and (
            len(self._held) > self._max_entries()
            or sum(entry.held_bytes for entry in self._held.values()) > self._max_bytes()
        ):
            self._held.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._held.clear()

    def keys(self) -> list[Any]:
        with self._lock:
            return list(self._held)


__all__ = [
    "BUDGET_CHECK_ROWS",
    "NULL_KEY",
    "Held",
    "MemoryCache",
    "MemoryColumn",
    "MemoryTable",
    "Scan",
    "SortKey",
    "bad_cursor",
    "column_number",
    "cursor_number",
    "index_bytes",
    "page",
    "row_index",
    "scan",
    "sort_index",
]
