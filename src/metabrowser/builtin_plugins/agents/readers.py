"""Bounded readers shared by the providers: JSONL files and read-only SQLite.

Nothing here reads past a byte budget, and every SQLite database opens read-only. A
provider checks a table's columns with :func:`check_table` instead of assuming them,
because both agents' schemas change faster than Metabrowser releases.
"""

from __future__ import annotations

import gzip
import json
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from urllib.parse import quote

from .model import DriftCollector

# The most bytes of one transcript or rollout a summary or stream reads. A transcript
# line is read whole, so a budget is checked between lines. The figure is a placeholder
# set from the research brief's largest plain rollout (97 MB) with headroom; the catalog's
# whole-history measurement replaces it with the measured size and records it here.
MAX_READ_BYTES: Final = 256 * 1024 * 1024

# How much of each end of a file the fast pass reads for its first and last records.
EDGE_BYTES: Final = 64 * 1024

# A SQLite read waits at most this long for a writer's lock, in seconds, so a read never
# holds a WAL checkpoint back for long.
SQLITE_BUSY_SECONDS: Final = 1.0


def clip(text: str, limit: int = 120) -> str:
    """The first line of *text*, cut to *limit* characters."""

    line = text.strip().split("\n", 1)[0]
    return line if len(line) <= limit else line[: limit - 1] + "…"


def as_dict(value: object) -> dict[str, object] | None:
    return {str(k): v for k, v in value.items()} if isinstance(value, dict) else None  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType, reportUnknownMemberType]


def as_list(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else []  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]


def as_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def as_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def read_small_json(path: Path, limit: int = 64 * 1024) -> dict[str, object] | None:
    """A small JSON object file, or ``None`` when absent, large, or not an object."""

    try:
        with path.open("rb") as handle:
            raw = handle.read(limit + 1)
    except OSError:
        return None
    if len(raw) > limit:
        return None
    try:
        return as_dict(json.loads(raw))
    except ValueError:
        return None


@dataclass(slots=True)
class JsonlReader:
    """Iterate a JSONL file as (line number, object or ``None``), within a byte budget.

    ``None`` stands for a line that is not a JSON object. ``truncated`` is set when the
    budget ended the read. A ``.gz`` file is decompressed on the fly and the budget counts
    decompressed bytes.
    """

    path: Path
    budget: int = MAX_READ_BYTES
    truncated: bool = False

    def __iter__(self) -> Iterator[tuple[int, dict[str, object] | None]]:
        opener = gzip.open if self.path.suffix == ".gz" else open
        spent = 0
        try:
            with opener(self.path, "rb") as handle:
                for number, line in enumerate(handle, start=1):
                    spent += len(line)
                    if spent > self.budget:
                        self.truncated = True
                        return
                    text = line.strip()
                    if not text:
                        continue
                    try:
                        yield number, as_dict(json.loads(text))
                    except ValueError:
                        yield number, None
        except OSError:
            return


def edge_records(path: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """The records in the first and last :data:`EDGE_BYTES` of a plain JSONL file.

    A partial line at a cut is dropped, so a record is returned only whole. The two lists
    may overlap on a small file. Returns empty lists for an unreadable file.
    """

    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            head = handle.read(EDGE_BYTES)
            tail = b""
            if size > EDGE_BYTES:
                handle.seek(max(0, size - EDGE_BYTES))
                tail = handle.read(EDGE_BYTES)
    except OSError:
        return [], []
    head_lines = head.split(b"\n")
    if size > EDGE_BYTES and head_lines:
        head_lines = head_lines[:-1]
    tail_lines = tail.split(b"\n")[1:] if tail else head_lines
    return _decode(head_lines), _decode(tail_lines)


def _decode(lines: list[bytes]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for line in lines:
        text = line.strip()
        if not text:
            continue
        try:
            record = as_dict(json.loads(text))
        except ValueError:
            continue
        if record is not None:
            records.append(record)
    return records


def open_readonly(path: Path) -> sqlite3.Connection | None:
    """Open a SQLite database read-only, or ``None`` when it is absent or unreadable."""

    if not path.is_file():
        return None
    try:
        conn = sqlite3.connect(
            f"file:{quote(str(path))}?mode=ro", uri=True, timeout=SQLITE_BUSY_SECONDS
        )
        conn.execute("PRAGMA query_only = 1")
        return conn
    except sqlite3.Error:
        return None


def table_columns(conn: sqlite3.Connection, table: str) -> frozenset[str] | None:
    """The columns of *table* from ``PRAGMA table_info``, or ``None`` if it is absent."""

    try:
        rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    except sqlite3.Error:
        return None
    names = frozenset(str(row[1]) for row in rows)  # pyright: ignore[reportAny]
    return names or None


def check_table(
    conn: sqlite3.Connection,
    db: str,
    table: str,
    expected: frozenset[str],
    required: frozenset[str],
    drift: DriftCollector,
) -> frozenset[str] | None:
    """The actual columns of *table*, with drift recorded.

    A column outside *expected* is unexpected; a column in *required* but absent is
    missing, and so is the whole table when it is absent (one count per required column).
    """

    actual = table_columns(conn, table)
    if actual is None:
        for column in sorted(required):
            drift.missing(f"{db}.{table}.{column}")
        return None
    for column in sorted(actual - expected):
        drift.unexpected(f"{db}.{table}.{column}")
    for column in sorted(required - actual):
        drift.missing(f"{db}.{table}.{column}")
    return actual
