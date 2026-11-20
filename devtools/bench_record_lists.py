"""Measure what the record-list table source's bounds cap, and print it.

The bounds in ``builtin_plugins/structured/records.py`` record the numbers this prints
beside their constants. A record list is read through the structured plugin's parse, at
most ``STRUCTURED_PARSE_MAX_BYTES`` of JSON or YAML, and what building and querying its
table costs follows its rows and values, not its bytes, so it measures several shapes of
JSON built in memory at that byte bound:

- 12-field records (text, integers, reals, dates, booleans, a nested list and mapping);
- narrow records: one field of one character, one field of integer IDs, and six fields
  of two-digit integers, each past the row or value bound;
- records as wide as the field bound, and one YAML list, whose parse is the dearest.

For each it times the parse as the Tree view's route runs it (with its YAML
re-serialization), measures the Python objects the parsed value holds with
``tracemalloc`` beside the estimate the cache counts, and times building the table, a
first sort index, a filtered and sorted page once that index exists, a search, and a
page of 1,000 rows encoded as the route answers it.

Run it with ``uv run python -m devtools.bench_record_lists``. It writes nothing.
"""

from __future__ import annotations

import gc
import json
import random
import time
import tracemalloc
from collections.abc import Callable
from typing import Any

from metabrowser.builtin_plugins.structured.parser import (
    STRUCTURED_PARSE_MAX_BYTES,
    parse_structured_bytes,
)
from metabrowser.builtin_plugins.structured.records import (
    RECORDS_MAX_FIELDS,
    build_records,
)
from metabrowser.builtin_plugins.table.memory import page as memory_page
from metabrowser.builtin_plugins.table.memory import sort_index
from metabrowser.table_source import (
    TABLE_PAGE_ROWS_MAX,
    Budget,
    Filter,
    TableQuery,
    page_wire,
    schema_wire,
)


def _timed[T](work: Callable[[], T]) -> tuple[T, float]:
    started = time.perf_counter()
    result = work()
    return result, time.perf_counter() - started


def _fill(make: Callable[[int], Any], max_bytes: int) -> bytes:
    """A JSON list of `make(n)` records, as many as fit *max_bytes*."""

    parts: list[str] = []
    size = 2
    number = 0
    while True:
        text = json.dumps(make(number), separators=(",", ":"))
        if size + len(text) + 1 > max_bytes:
            break
        parts.append(text)
        size += len(text) + 1
        number += 1
    return ("[" + ",".join(parts) + "]").encode()


_WORDS = ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta"]


def _twelve(rng: random.Random) -> Callable[[int], dict[str, Any]]:
    def make(number: int) -> dict[str, Any]:
        return {
            "name": f"name{number}",
            "city": rng.choice(["Paris", "Lima", "Oslo", "Kyoto"]),
            "note": " ".join(rng.choice(_WORDS) for _ in range(4)),
            "id": number,
            "count": rng.randint(0, 10_000),
            "price": round(rng.uniform(0, 1000), 2),
            "ratio": rng.random(),
            "day": f"20{rng.randint(10, 29)}-0{rng.randint(1, 9)}-1{rng.randint(0, 9)}",
            "stamp": f"2024-01-0{rng.randint(1, 9)}T12:00:00",
            "flag": rng.random() < 0.5,
            "tags": rng.sample(_WORDS, 2),
            "meta": {"x": rng.randint(0, 9)},
        }

    return make


def _shapes() -> dict[str, tuple[bytes, str, int, Filter, str]]:
    """label: (bytes, extension, sort column, a filter, a search)."""

    rng = random.Random(7)
    cap = STRUCTURED_PARSE_MAX_BYTES
    wide_fields = RECORDS_MAX_FIELDS
    return {
        "12 fields": (_fill(_twelve(rng), cap), ".json", 4, Filter("count", "gt", "5000"), "zeta"),
        "1 field of 1 character": (
            _fill(lambda _n: {"c": rng.choice("abcdefgh")}, cap),
            ".json",
            0,
            Filter("c", "gt", "d"),
            "a",
        ),
        "1 field of integer IDs": (
            _fill(lambda n: {"id": 1_000_000 + n * 7 % 999_983}, cap),
            ".json",
            0,
            Filter("id", "gt", "1500000"),
            "a",
        ),
        "6 fields of 2-digit integers": (
            _fill(lambda _n: {k: rng.randint(10, 99) for k in "abcdef"}, cap),
            ".json",
            0,
            Filter("a", "gt", "50"),
            "a",
        ),
        f"{wide_fields} fields of datetimes": (
            _fill(lambda _n: {f"c{k}": "2024-01-01T10:00:00" for k in range(wide_fields)}, cap),
            ".json",
            0,
            Filter("c0", "contains", "10"),
            "x",
        ),
    }


def _yaml(max_bytes: int) -> bytes:
    rng = random.Random(3)
    lines: list[str] = []
    size = 0
    number = 0
    while size < max_bytes:
        record = (
            f"- name: name{number}\n  city: {rng.choice(['Paris', 'Lima'])}\n"
            f"  count: {rng.randint(0, 10_000)}\n  flag: {str(rng.random() < 0.5).lower()}\n"
        )
        lines.append(record)
        size += len(record)
        number += 1
    return "".join(lines).encode()


def _measure(label: str, data: bytes, ext: str, sort_column: int, scan: Filter, q: str) -> None:
    payload, parse_seconds = _timed(lambda: parse_structured_bytes(data, ext))
    del payload
    gc.collect()
    # Again under tracemalloc, which slows it, for what the parsed value holds; the
    # re-serialized YAML is the Tree view's and is not held by the table.
    from metabrowser.builtin_plugins.structured.parser import (
        _parse_text,  # pyright: ignore[reportPrivateUsage]
    )
    from metabrowser.structured_text import decode_text

    text = decode_text(data)
    tracemalloc.start()
    parsed_only = _parse_text(text, ext)
    held, _peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    del parsed_only, text
    gc.collect()
    payload = parse_structured_bytes(data, ext)
    records, build_seconds = _timed(lambda: build_records(payload, "g"))
    cut = " (cut at a bound)" if records.truncated else ""
    print(f"{label}: {len(data) / 2**20:.1f} MiB, {records.row_count} rows{cut}")
    print(f"  structured parse {parse_seconds:.2f} s, {payload.node_count} nodes")
    print(
        f"  parse holds {held / 1e6:.0f} MB measured, {records.parsed_bytes / 1e6:.0f} MB "
        f"estimated; {held / len(data):.1f} bytes per byte, "
        f"{held / max(1, payload.node_count):.0f} per node"
    )
    print(f"  build table {build_seconds:.2f} s")
    index, sort_seconds = _timed(lambda: sort_index(records, sort_column, Budget.start(60)))
    size = len(index) * index.itemsize if index is not None else 0
    print(f"  first sort index {sort_seconds:.2f} s, {size / 1e6:.0f} MB")
    name = records.columns[sort_column].name
    query = TableQuery(sort=name, order="desc", filters=(scan,))
    page, page_seconds = _timed(lambda: memory_page(records, query, Budget.start(60)))
    print(f"  filtered and sorted page {page_seconds:.2f} s, {page.count} matches")
    page, search_seconds = _timed(lambda: memory_page(records, TableQuery(q=q), Budget.start(60)))
    print(f"  search {search_seconds:.2f} s, {page.count} matches")

    def encode() -> tuple[int, int]:
        answer = memory_page(records, TableQuery(limit=TABLE_PAGE_ROWS_MAX), Budget.start(60))
        return len(answer.rows), len(json.dumps(page_wire("a.json", "", answer)))

    (rows, size), seconds = _timed(encode)
    print(
        f"  page asking {TABLE_PAGE_ROWS_MAX} rows: {rows} rows, {size / 1e6:.2f} MB in {seconds * 1e3:.0f} ms"
    )
    schema, schema_seconds = _timed(
        lambda: len(json.dumps(schema_wire("a", "g", records.schema())))
    )
    print(f"  schema {schema / 1e6:.2f} MB of JSON in {schema_seconds * 1e3:.0f} ms")


def main() -> None:
    for label, (data, ext, column, scan, q) in _shapes().items():
        _measure(label, data, ext, column, scan, q)
    _measure(
        "YAML, 4 fields",
        _yaml(STRUCTURED_PARSE_MAX_BYTES // 8),
        ".yaml",
        2,
        Filter("count", "gt", "5000"),
        "Lima",
    )


if __name__ == "__main__":
    main()
