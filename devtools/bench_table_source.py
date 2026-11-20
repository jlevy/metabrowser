"""Measure the costs the table source bounds cap, and print them.

The bounds in ``metabrowser.table_source`` and ``builtin_plugins/delimited/source.py``
record the numbers this prints beside their constants. It builds a synthetic CSV of 12
columns (text, integers, reals, dates, booleans) in memory, then times and sizes:

- parsing it at the delimited parse cap, and the Python objects the parse holds;
- building a sort index on an integer column, and a filter and a search scan;
- encoding pages of rows as JSON at the page bounds, with short cells and with every
  text cell filled to the preview bound;
- encoding one record whose values are filled to the record value bound.

Run it with ``uv run python -m devtools.bench_table_source``. It writes nothing.
"""

from __future__ import annotations

import json
import random
import time
import tracemalloc
from collections.abc import Callable

from metabrowser.builtin_plugins.delimited.source import (
    DELIMITED_PARSE_MAX_BYTES,
    _cells,  # pyright: ignore[reportPrivateUsage]
    _page,  # pyright: ignore[reportPrivateUsage]
    _Parsed,  # pyright: ignore[reportPrivateUsage]
    parse_delimited,
)
from metabrowser.table_source import (
    TABLE_CELL_PREVIEW_CHARS,
    TABLE_PAGE_ROWS_DEFAULT,
    TABLE_PAGE_ROWS_MAX,
    TABLE_RECORD_VALUE_BYTES,
    Budget,
    Filter,
    TableQuery,
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


def _csv(max_bytes: int, width: int) -> bytes:
    rng = random.Random(7)
    lines = [_HEADER]
    size = len(_HEADER) + 1
    number = 0
    while size < max_bytes:
        line = _row(rng, number, width)
        lines.append(line)
        size += len(line) + 1
        number += 1
    return ("\n".join(lines) + "\n").encode()[:max_bytes]


def _timed[T](work: Callable[[], T]) -> tuple[T, float]:
    started = time.perf_counter()
    result = work()
    return result, time.perf_counter() - started


def _page_json(parsed: _Parsed, limit: int) -> tuple[int, float]:
    def encode() -> int:
        page = _page(parsed, TableQuery(limit=limit), Budget.start(60))
        rows = [{"key": row.key, "cells": dict(row.cells)} for row in page.rows]
        return len(json.dumps({"rows": rows}))

    return _timed(encode)


def main() -> None:
    data = _csv(DELIMITED_PARSE_MAX_BYTES, width=24)
    parsed, parse_seconds = _timed(
        lambda: parse_delimited(data, has_more=False, delimiter=",", generation="g")
    )
    # Again under tracemalloc, which slows the parse, for what the parse holds.
    del parsed
    tracemalloc.start()
    parsed = parse_delimited(data, has_more=False, delimiter=",", generation="g")
    held, _peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    rows = len(parsed.rows)
    print(f"parse: {len(data) / 2**20:.0f} MiB, {rows} rows of 12 columns in {parse_seconds:.2f} s")
    print(f"  held {held / 1e6:.0f} MB, {held / len(data):.1f} bytes per byte of file")
    _index, sort_seconds = _timed(lambda: parsed.sort_index(5))
    print(f"sort index on an integer column: {sort_seconds:.2f} s")
    _index, sort_seconds = _timed(lambda: parsed.sort_index(2))
    print(f"sort index on a text column: {sort_seconds:.2f} s")
    filtered = TableQuery(filters=(Filter(field="count", op="gt", value="5000"),))
    page, filter_seconds = _timed(lambda: _page(parsed, filtered, Budget.start(60)))
    print(f"filter scan: {filter_seconds:.2f} s, {page.count} matches")
    page, search_seconds = _timed(lambda: _page(parsed, TableQuery(q="zeta"), Budget.start(60)))
    print(f"search scan: {search_seconds:.2f} s, {page.count} matches")
    for limit in (TABLE_PAGE_ROWS_DEFAULT, TABLE_PAGE_ROWS_MAX):
        size, seconds = _page_json(parsed, limit)
        print(f"page of {limit} short rows: {size / 1e6:.3f} MB of JSON in {seconds * 1e3:.0f} ms")
    wide_data = _csv(4 * 2**20, width=2 * TABLE_CELL_PREVIEW_CHARS)
    wide = parse_delimited(wide_data, has_more=False, delimiter=",", generation="g")
    wide.columns = tuple(type(column)(name=column.name, type="text") for column in wide.columns)
    wide.rows = [
        [value.ljust(2 * TABLE_CELL_PREVIEW_CHARS, "x") for value in row] for row in wide.rows
    ]
    size, seconds = _page_json(wide, TABLE_PAGE_ROWS_MAX)
    print(
        f"page of {TABLE_PAGE_ROWS_MAX} rows, every cell past the preview bound: "
        f"{size / 1e6:.1f} MB of JSON in {seconds * 1e3:.0f} ms"
    )
    wide.rows[0] = ["y" * (2 * TABLE_RECORD_VALUE_BYTES) for _ in wide.columns]
    names = [column.name for column in wide.columns]
    record, seconds = _timed(
        lambda: len(json.dumps(_cells(wide, 0, names, max_bytes=TABLE_RECORD_VALUE_BYTES)))
    )
    print(
        f"record of 12 values past the value bound: {record / 1e6:.2f} MB in {seconds * 1e3:.0f} ms"
    )


if __name__ == "__main__":
    main()
