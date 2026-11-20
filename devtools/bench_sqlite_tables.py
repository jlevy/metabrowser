"""Measure the costs the SQLite table source's bounds cap, and print them.

The bounds in ``builtin_plugins/sqlite/reader.py`` record the numbers this prints beside
their constants. It builds databases of a 12-column shape (an integer key, text,
integers, reals, and dates) in a temporary folder, reads them in this process through the
reader's own statements under the guest connection settings
(``sqlite_access.apply_settings``), and prints, for each read, its median wall time over
a few runs and the virtual-machine opcodes it ran, counted by a progress handler called
every opcode:

- a first page of 100 rows sorted by an unindexed field, at 10,000, 100,000, and
  1,000,000 rows, against ``SORT_UNINDEXED_MAX_ROWS`` and the opcode budget
  (``sqlite_access.READ_OPCODE_BUDGET``);
- a capped count at 1,000,000 rows, against ``COUNT_CAP``;
- the references of a page of 1,000 rows resolved in one statement by the referenced
  table's key, against ``REFS_PER_PAGE``;
- a page of 1,000 rows of 12 texts read whole at ``PAGE_INLINE_BYTES``, and the same page
  previewed through ``blobopen`` when every text is far longer;
- a filtered scan's window statement per row, with one, five, and eleven terms, against
  ``SCAN_WINDOW_OPCODES``, and a search for the last of 1,000,000 rows walked window by
  window;
- the catalog and one description of a database of 300 tables, one with 20 foreign keys,
  which the description cache (``DESCRIPTION_CACHE_ENTRIES``) holds a generation.

Run it with ``uv run python -m devtools.bench_sqlite_tables``. It writes only to a
temporary folder it removes.
"""

from __future__ import annotations

import sqlite3
import statistics
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from metabrowser import sqlite_access
from metabrowser.builtin_plugins.sqlite import reader

_RUNS = 5


def _shape(path: Path, rows: int, *, text_bytes: int = 12) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        "CREATE TABLE t (id INTEGER PRIMARY KEY, a TEXT, b TEXT, c TEXT, d INTEGER, "
        "e INTEGER, f REAL, g REAL, h TEXT, i TEXT, j DATE, k INTEGER);"
    )
    connection.execute(
        "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n LIMIT ?) "
        "INSERT INTO t SELECT x, substr(hex(randomblob(?)), 1, ?), 'b' || (x % 97), "
        "'c' || x, x % 1000, abs(random() % 100000), x / 7.0, random() / 3.0, "
        "'h' || (x % 13), 'i', date('2020-01-01', '+' || (x % 2000) || ' days'), x FROM n",
        (rows, text_bytes, text_bytes),
    )
    connection.commit()
    connection.close()


def _texts(path: Path, rows: int, size: int) -> list[str]:
    """A table of twelve text columns, each value *size* characters."""
    names = [f"t{index}" for index in range(1, 13)]
    connection = sqlite3.connect(path)
    connection.execute(f"CREATE TABLE t (id INTEGER PRIMARY KEY, {', '.join(names)})")
    value = f"substr(hex(randomblob({size})), 1, {size})"
    connection.execute(
        "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n LIMIT ?) "
        f"INSERT INTO t SELECT x, {', '.join([value] * 12)} FROM n",
        (rows,),
    )
    connection.commit()
    connection.close()
    return names


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    sqlite_access.apply_settings(connection)
    connection.text_factory = bytes
    return connection


def _measure(path: Path, work: Callable[[sqlite3.Connection], Any]) -> tuple[float, int]:
    """Median milliseconds over the runs, and the opcodes of one run."""
    times: list[float] = []
    for _ in range(_RUNS):
        connection = _connect(path)
        started = time.perf_counter()
        work(connection)
        times.append((time.perf_counter() - started) * 1000)
        connection.close()
    connection = _connect(path)
    steps = 0

    def count() -> int:
        nonlocal steps
        steps += 1
        return 0

    connection.set_progress_handler(count, 1)
    work(connection)
    connection.close()
    return statistics.median(times), steps


def _report(label: str, measured: tuple[float, int]) -> None:
    millis, steps = measured
    share = steps / sqlite_access.READ_OPCODE_BUDGET
    print(f"{label:<62} {millis:9.1f} ms {steps:>12,} opcodes ({share:.2f} of the budget)")


def _page_spec(columns: list[str], **extra: Any) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "table": "t",
        "key": ["id"],
        "rowid": "id",
        "columns": columns,
        "order": "asc",
        "limit": 100,
        "inline": reader.PAGE_INLINE_BYTES,
        "preview": {"text": 1600, "blob": 200},
        "encoding": "UTF-8",
        "refs": [],
    }
    spec.update(extra)
    return spec


def main() -> None:
    columns = ["id", "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k"]
    deadline = time.monotonic() + 3600
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        for rows in (10_000, 100_000, 1_000_000):
            path = root / f"rows-{rows}.db"
            _shape(path, rows)
            spec = _page_spec(columns, sort="c")
            _report(
                f"unindexed sort, first 100-row page, {rows:,} rows",
                _measure(path, lambda c, s=spec: reader._page(c, s, deadline)),  # pyright: ignore[reportPrivateUsage]
            )
            spec = _page_spec(columns)
            _report(
                f"key order, first 100-row page, {rows:,} rows",
                _measure(path, lambda c, s=spec: reader._page(c, s, deadline)),  # pyright: ignore[reportPrivateUsage]
            )
        big = root / "rows-1000000.db"
        count = {"table": "t", "cap": reader.COUNT_CAP}
        _report(
            f"capped count at COUNT_CAP ({reader.COUNT_CAP:,}), 1,000,000 rows",
            _measure(big, lambda c: reader._count(c, count, deadline)),  # pyright: ignore[reportPrivateUsage]
        )
        refs = _page_spec(
            ["k"],
            limit=1000,
            refs=[{"fields": ["k"], "table": "t", "to": ["id"], "key": ["id"]}],
        )
        _report(
            "a 1,000-row page with its 1,000 references resolved",
            _measure(big, lambda c: reader._page(c, refs, deadline)),  # pyright: ignore[reportPrivateUsage]
        )
        unresolved = _page_spec(["k"], limit=1000)
        _report(
            "the same page without references",
            _measure(big, lambda c: reader._page(c, unresolved, deadline)),  # pyright: ignore[reportPrivateUsage]
        )
        inline = root / "inline.db"
        names = _texts(inline, 1000, reader.PAGE_INLINE_BYTES)
        whole = _page_spec(names, limit=1000)
        _report(
            f"1,000 rows of 12 texts of {reader.PAGE_INLINE_BYTES:,} bytes, read whole",
            _measure(inline, lambda c: reader._page(c, whole, deadline)),  # pyright: ignore[reportPrivateUsage]
        )
        _walk_search(big)
        _window_costs(root)
        _schema_costs(root)
        long = root / "long.db"
        names = _texts(long, 1000, 128 * 1024)
        previewed = _page_spec(names, limit=1000)
        _report(
            "1,000 rows of 12 texts of 128 KiB, previewed through blobopen",
            _measure(long, lambda c: reader._page(c, previewed, deadline)),  # pyright: ignore[reportPrivateUsage]
        )


def _window_costs(root: Path) -> None:
    """The statement that reads a window's matches, per row, by the terms it tests: run
    directly, since a page's own budget replaces the progress handler that counts."""
    path = root / "window.db"
    _shape(path, 300_000)
    rows = 100_000
    text = ["a", "b", "c", "h", "i"]
    for fields in (["a"], text, [*text, "j", "d", "e", "f", "g", "k"]):
        spec = _page_spec(["id"], search={"fields": fields, "needle": "zzzz"})
        where, params, _skips = reader._predicates(spec)  # pyright: ignore[reportPrivateUsage]
        sql = (
            f"SELECT id FROM t WHERE id > ? AND id <= ? AND {' AND '.join(where)} "
            "ORDER BY id LIMIT 100"
        )
        millis, steps = _measure(
            path, lambda c, q=sql, a=params: c.execute(q, [0, rows, *a]).fetchall()
        )
        print(
            f"{f'a {rows:,}-row window, {len(fields)} search terms':<62} {millis:9.1f} ms "
            f"{steps / rows:>9.1f} opcodes a row"
        )


def _walk_search(path: Path) -> None:
    """A search for the last row of *path*'s 1,000,000, walked window by window as the
    table view continues it."""
    spec = _page_spec(["id"], search={"fields": ["c"], "needle": "c1000000"}, limit=100)
    spec["window"] = reader.scan_window(1)
    connection = _connect(path)
    started = time.perf_counter()
    pages = 0
    while True:
        pages += 1
        page = reader._page(connection, spec, time.monotonic() + 3600)  # pyright: ignore[reportPrivateUsage]
        if page["rows"] or page["boundary"] is None:
            break
        boundary = page["boundary"]
        spec["after"] = {"region": "k", "value": None, "key": boundary["key"]}
    connection.close()
    millis = (time.perf_counter() - started) * 1000
    print(
        f"{'a search for the last of 1,000,000 rows, window by window':<62} {millis:9.1f} ms "
        f"{pages:>6} pages of {spec['window']:,} rows"
    )


def _schema_costs(root: Path) -> None:
    path = root / "tables.db"
    connection = sqlite3.connect(path)
    for index in range(300):
        connection.execute(f"CREATE TABLE t{index} (id INTEGER PRIMARY KEY, v TEXT)")
    references = ", ".join(f"r{index} REFERENCES t{index}(id)" for index in range(20))
    connection.execute(f"CREATE TABLE hub (id INTEGER PRIMARY KEY, {references})")
    connection.commit()
    connection.close()
    deadline = time.monotonic() + 3600
    _report(
        "the catalog of 300 tables, with every table's key and foreign keys",
        _measure(path, lambda c: reader.catalog(c, deadline)),
    )
    _report(
        "one description, of the table with 20 foreign keys",
        _measure(path, lambda c: reader.describe(c, "hub", deadline)),
    )


if __name__ == "__main__":
    main()
