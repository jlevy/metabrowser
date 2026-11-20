"""Measure the costs the table source bounds cap, and print them.

The bounds in ``metabrowser.table_source`` and ``builtin_plugins/delimited/source.py``
record the numbers this prints beside their constants. A delimited file's costs follow
its rows and cells, not its bytes, so it measures several shapes built in memory:

- a 12-column CSV (text, integers, reals, dates, booleans) at the byte cap, the shape
  a byte cap alone favors;
- narrow files at the byte cap: one column of one character, one column of integer
  IDs, and six columns of two-digit integers, each cut at the row or cell bound;
- a file as wide as the column bound, a header of repeated names, and cells of invalid
  UTF-8.

For each it times the parse, measures the Python objects the parse holds with
``tracemalloc`` beside the estimate the cache counts (``held``), and times a first sort
index, a filtered and sorted page once that index exists, and a search. It then encodes
pages at the page bounds and a record at the record bound.

Run it with ``uv run python -m devtools.bench_table_source``. It writes nothing.
"""

from __future__ import annotations

import gc
import json
import random
import time
import tracemalloc
from collections.abc import Callable

from metabrowser.builtin_plugins.delimited.source import (
    DELIMITED_MAX_COLUMNS,
    DELIMITED_PARSE_MAX_BYTES,
    DELIMITED_TYPE_SAMPLE_ROWS,
    _cells,  # pyright: ignore[reportPrivateUsage]
    _column_names,  # pyright: ignore[reportPrivateUsage]
    _infer_type,  # pyright: ignore[reportPrivateUsage]
    _Parsed,  # pyright: ignore[reportPrivateUsage]
    _plan,  # pyright: ignore[reportPrivateUsage]
    parse_delimited,
)
from metabrowser.builtin_plugins.table.memory import page as memory_page
from metabrowser.builtin_plugins.table.memory import sort_index
from metabrowser.table_source import (
    TABLE_CELL_PREVIEW_CHARS,
    TABLE_PAGE_CELLS_MAX,
    TABLE_PAGE_ROWS_DEFAULT,
    TABLE_PAGE_ROWS_MAX,
    TABLE_RECORD_VALUE_BYTES,
    Budget,
    Filter,
    TableQuery,
    page_wire,
    schema_wire,
)

_HEADER = "name,city,note,tag,id,count,qty,price,ratio,day,stamp,flag"


def _row(rng: random.Random, number: int, width: int) -> str:
    words = ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta"]
    text = " ".join(rng.choice(words) for _ in range(max(1, width // 6)))[:width]
    return ",".join(
        [
            f"name{number}",
            rng.choice(["Paris", "Lima", "Oslo", "Kyoto"]),
            text,
            rng.choice(words),
            str(number),
            str(rng.randint(0, 10_000)),
            str(rng.randint(-50, 50)),
            f"{rng.uniform(0, 1000):.2f}",
            f"{rng.random():.6f}",
            f"20{rng.randint(10, 29)}-0{rng.randint(1, 9)}-1{rng.randint(0, 9)}",
            f"2024-01-0{rng.randint(1, 9)}T12:00:00",
            rng.choice(["true", "false"]),
        ]
    )


def _fill(header: str, line: Callable[[int], str], max_bytes: int) -> bytes:
    lines = [header]
    size = len(header) + 1
    number = 0
    while size < max_bytes:
        text = line(number)
        lines.append(text)
        size += len(text) + 1
        number += 1
    return ("\n".join(lines) + "\n").encode()[:max_bytes]


def _csv(max_bytes: int, width: int) -> bytes:
    rng = random.Random(7)
    return _fill(_HEADER, lambda number: _row(rng, number, width), max_bytes)


def _narrow_shapes() -> dict[str, tuple[bytes, Filter]]:
    rng = random.Random(11)
    return {
        "1 column of 1 character": (
            _fill("c", lambda _n: rng.choice("abcdefgh"), DELIMITED_PARSE_MAX_BYTES),
            Filter(field="c", op="gt", value="d"),
        ),
        "1 column of integer IDs": (
            _fill("id", lambda n: str(1_000_000 + n * 7 % 999_983), DELIMITED_PARSE_MAX_BYTES),
            Filter(field="id", op="gt", value="1500000"),
        ),
        "6 columns of 2-digit integers": (
            _fill(
                "a,b,c,d,e,f",
                lambda _n: ",".join(str(rng.randint(10, 99)) for _ in range(6)),
                DELIMITED_PARSE_MAX_BYTES,
            ),
            Filter(field="a", op="gt", value="50"),
        ),
    }


def _timed[T](work: Callable[[], T]) -> tuple[T, float]:
    started = time.perf_counter()
    result = work()
    return result, time.perf_counter() - started


def _parse(data: bytes) -> tuple[_Parsed, float, int]:
    """Parse *data*: the parsed file, the parse time, and what tracemalloc saw it hold."""

    parsed, seconds = _timed(
        lambda: parse_delimited(data, has_more=False, delimiter=",", generation="g")
    )
    del parsed
    gc.collect()
    # Again under tracemalloc, which slows the parse, for what the parse holds.
    tracemalloc.start()
    parsed = parse_delimited(data, has_more=False, delimiter=",", generation="g")
    held, _peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return parsed, seconds, held


def _shape(label: str, data: bytes, sort_column: int, scan: Filter, q: str) -> None:
    parsed, seconds, held = _parse(data)
    rows = len(parsed.rows)
    cut = " (cut at a bound)" if parsed.truncated else ""
    print(f"{label}: {len(data) / 2**20:.0f} MiB, {rows} rows{cut}")
    print(f"  parse {seconds:.2f} s")
    print(
        f"  held {held / 1e6:.0f} MB measured, {parsed.parsed_bytes / 1e6:.0f} MB estimated, "
        f"{held / len(data):.1f} bytes per byte of file"
    )
    index, sort_seconds = _timed(lambda: sort_index(parsed, sort_column, Budget.start(60)))
    size = len(index) * index.itemsize if index is not None else 0
    print(f"  first sort index {sort_seconds:.2f} s, {size / 1e6:.0f} MB")
    name = parsed.columns[sort_column].name
    query = TableQuery(sort=name, order="desc", filters=(scan,))
    page, page_seconds = _timed(lambda: memory_page(parsed, query, Budget.start(60)))
    print(f"  filtered and sorted page {page_seconds:.2f} s, {page.count} matches")
    page, search_seconds = _timed(lambda: memory_page(parsed, TableQuery(q=q), Budget.start(60)))
    print(f"  search {search_seconds:.2f} s, {page.count} matches")


def _page_json(parsed: _Parsed, query: TableQuery) -> tuple[int, int, float]:
    """(rows, bytes of JSON, seconds) for one page encoded as the route answers it."""

    def encode() -> tuple[int, int]:
        page = memory_page(parsed, query, Budget.start(60))
        return len(page.rows), len(json.dumps(page_wire("a.csv", "", page)))

    (rows, size), seconds = _timed(encode)
    return rows, size, seconds


def _wide() -> None:
    columns = DELIMITED_MAX_COLUMNS
    header = ",".join(f"c{n}" for n in range(columns))
    # Datetimes are the dearest values to infer: four patterns fail before one passes.
    line = ",".join("2024-01-01T10:00:00" for _ in range(columns))
    data = (header + "\n" + "\n".join([line] * DELIMITED_TYPE_SAMPLE_ROWS) + "\n").encode()
    parsed, seconds, held = _parse(data)
    print(
        f"{columns} columns of datetimes, {len(parsed.rows)} rows: parse {seconds:.2f} s, "
        f"held {held / 1e6:.0f} MB measured, {parsed.parsed_bytes / 1e6:.0f} MB estimated"
    )
    sample = [row[0] for row in parsed.rows]
    _type, infer_seconds = _timed(lambda: [_infer_type(sample) for _ in range(columns)])
    print(f"  type inference of {columns} columns of the sample: {infer_seconds:.2f} s")
    size, schema_seconds = _timed(
        lambda: len(json.dumps(schema_wire("a.csv", "g", parsed.schema())))
    )
    print(f"  schema: {size / 1e6:.2f} MB of JSON in {schema_seconds * 1e3:.0f} ms")
    rows, size, page_seconds = _page_json(parsed, TableQuery(limit=TABLE_PAGE_ROWS_MAX))
    print(
        f"  page asking {TABLE_PAGE_ROWS_MAX} rows: {rows} rows, "
        f"{size / 1e6:.2f} MB of JSON in {page_seconds * 1e3:.0f} ms"
    )
    names = [f"a{n % 4}" for n in range(20_000)]
    _names, naming_seconds = _timed(lambda: _column_names(names))
    print(f"naming 20,000 header cells of 4 repeated names: {naming_seconds * 1e3:.0f} ms")


def _invalid() -> None:
    rows = 200_000
    valid, _seconds, valid_held = _parse(b"a,b\n" + b"xz,yz\n" * rows)
    invalid, _seconds, invalid_held = _parse(b"a,b\n" + b"x\xff,y\xfe\n" * rows)
    extra = (invalid_held - valid_held) / len(invalid.invalid)
    print(
        f"{rows} rows of two invalid UTF-8 cells: held {invalid_held / 1e6:.0f} MB measured, "
        f"{invalid.parsed_bytes / 1e6:.0f} MB estimated; {valid_held / 1e6:.0f} MB when "
        f"valid ({valid.parsed_bytes / 1e6:.0f} MB estimated), {extra:.0f} bytes more a cell"
    )


def main() -> None:
    _shape(
        "12 columns",
        _csv(DELIMITED_PARSE_MAX_BYTES, width=24),
        5,
        Filter("count", "gt", "5000"),
        "zeta",
    )
    for label, (data, scan) in _narrow_shapes().items():
        _shape(label, data, 0, scan, "a")
    _wide()
    _invalid()
    parsed = parse_delimited(
        _csv(DELIMITED_PARSE_MAX_BYTES, width=24), has_more=False, delimiter=",", generation="g"
    )
    for limit in (TABLE_PAGE_ROWS_DEFAULT, TABLE_PAGE_ROWS_MAX):
        rows, size, seconds = _page_json(parsed, TableQuery(limit=limit))
        print(f"page of {rows} short rows: {size / 1e6:.3f} MB of JSON in {seconds * 1e3:.0f} ms")
    wide_data = _csv(4 * 2**20, width=2 * TABLE_CELL_PREVIEW_CHARS)
    wide = parse_delimited(wide_data, has_more=False, delimiter=",", generation="g")
    wide.columns = tuple(type(column)(name=column.name, type="text") for column in wide.columns)
    wide.rows = [
        [value.ljust(2 * TABLE_CELL_PREVIEW_CHARS, "x") for value in row] for row in wide.rows
    ]
    rows, size, seconds = _page_json(wide, TableQuery(limit=TABLE_PAGE_ROWS_MAX))
    print(
        f"page of {rows} rows ({rows * len(wide.columns)} cells, the most "
        f"TABLE_PAGE_CELLS_MAX = {TABLE_PAGE_CELLS_MAX} admits), every cell past the "
        f"preview bound: {size / 1e6:.1f} MB of JSON in {seconds * 1e3:.0f} ms"
    )
    wide.rows[0] = ["y" * (2 * TABLE_RECORD_VALUE_BYTES) for _ in wide.columns]
    plan = _plan(wide, [column.name for column in wide.columns])
    record, seconds = _timed(
        lambda: len(json.dumps(_cells(wide, 0, plan, max_bytes=TABLE_RECORD_VALUE_BYTES)))
    )
    print(
        f"record of 12 values past the value bound: {record / 1e6:.2f} MB in {seconds * 1e3:.0f} ms"
    )


if __name__ == "__main__":
    main()
