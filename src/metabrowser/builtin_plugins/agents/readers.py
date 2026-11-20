"""Bounded readers shared by the providers: JSONL files and read-only SQLite.

Nothing here reads past a byte budget, and every SQLite database opens read-only. A
provider checks a table's columns with :func:`check_table` instead of assuming them,
because both agents' schemas change faster than Metabrowser releases.
"""

from __future__ import annotations

import gzip
import json
import re
import sqlite3
import zlib
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


# The longest single line a reader materializes. A longer line is skipped, counted as an
# invalid record, and still counts against the byte budget, so one huge line or a gzip
# stream with no newline cannot grow memory past the budget.
MAX_LINE_BYTES: Final = 16 * 1024 * 1024

# What a summary must not carry. Each pattern replaces a secret-looking value, applied
# before a summary is clipped so a cut cannot leave half of a token behind.
_REDACTIONS: Final = (
    (re.compile(r"(?i)\b(authorization\s*[:=]\s*)(?:bearer\s+)?[^\s\"']+"), r"\1[redacted]"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+"), "Bearer [redacted]"),
    (
        re.compile(
            r"(?i)\b([\w-]*(?:key|token|password|passwd|secret))\s*[=:]\s*(\"[^\"]*\"|'[^']*'|[^\s\"']+)"
        ),
        r"\1=[redacted]",
    ),
    (
        re.compile(r"(?i)(--[\w-]*(?:token|password|passwd|secret|key))[ =]+[^\s\"']+"),
        r"\1 [redacted]",
    ),
    (re.compile(r"\b[0-9a-fA-F]{32,}\b"), "[redacted]"),
    (
        re.compile(r"\b(?=[A-Za-z0-9_-]*\d)(?=[A-Za-z0-9_-]*[A-Za-z])[A-Za-z0-9_-]{40,}\b"),
        "[redacted]",
    ),
    (
        re.compile(r"(?=[A-Za-z0-9+/]*\d)(?=[A-Za-z0-9+/]*[A-Za-z])[A-Za-z0-9+/]{40,}={0,2}"),
        "[redacted]",
    ),
)


def redact(text: str) -> str:
    """*text* with credential-looking values replaced by ``[redacted]``."""

    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def clip(text: str, limit: int = 120) -> str:
    """The first line of *text*, redacted, cut to *limit* characters."""

    line = redact(text.strip()).split("\n", 1)[0]
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
        number = 0
        try:
            with opener(self.path, "rb") as handle:
                while True:
                    line = handle.readline(MAX_LINE_BYTES + 1)
                    if not line:
                        return
                    number += 1
                    spent += len(line)
                    oversize = len(line) > MAX_LINE_BYTES and not line.endswith(b"\n")
                    while oversize:
                        rest = handle.readline(MAX_LINE_BYTES)
                        spent += len(rest)
                        if spent > self.budget:
                            self.truncated = True
                            return
                        oversize = bool(rest) and not rest.endswith(b"\n")
                    if spent > self.budget:
                        self.truncated = True
                        return
                    if len(line) > MAX_LINE_BYTES:
                        yield number, None
                        continue
                    text = line.strip()
                    if text:
                        yield number, _decode_line(text)
        except (OSError, EOFError, zlib.error):
            self.truncated = True


def _decode_line(text: bytes) -> dict[str, object] | None:
    try:
        return as_dict(json.loads(text))
    except (ValueError, RecursionError):
        return None


def edge_records(path: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """The records in the first and last :data:`EDGE_BYTES` of a plain JSONL file.

    A partial line at a cut is dropped, so a record is returned only whole. The two lists
    may overlap on a small file. Returns empty lists for an unreadable file.
    """

    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            head = handle.read(EDGE_BYTES)
            tail_lines: list[bytes] = []
            if size > EDGE_BYTES:
                start = size - EDGE_BYTES
                handle.seek(start - 1)
                tail = handle.read(EDGE_BYTES + 1)
                # The tail starts mid-line unless the byte before it ends a line.
                tail_lines = tail[1:].split(b"\n") if tail[:1] == b"\n" else tail.split(b"\n")[1:]
    except OSError:
        return [], []
    head_lines = head.split(b"\n")
    if size > EDGE_BYTES:
        head_lines = head_lines[:-1]  # the last line is cut, or empty after a newline
    else:
        tail_lines = head_lines
    return _decode(head_lines), _decode(tail_lines)


def _decode(lines: list[bytes]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for line in lines:
        text = line.strip()
        if not text:
            continue
        record = _decode_line(text)
        if record is not None:
            records.append(record)
    return records


def _decode_text(raw: bytes) -> str:
    return raw.decode("utf-8", "replace")


def open_readonly(path: Path, drift: DriftCollector | None = None) -> sqlite3.Connection | None:
    """Open a SQLite database for reading without creating or changing any file.

    Codex's databases are WAL. A read-only connection to an idle WAL database creates
    ``-wal`` and ``-shm`` beside it, so those are used only when both already exist,
    which means a writer has the database open and ``mode=ro`` is the safe way to see its
    latest commits. When neither exists no process has it open and ``immutable=1`` reads
    the file as it is and touches nothing. A ``-wal`` without a ``-shm`` is a crash
    leftover whose content ``immutable=1`` does not see; that read can be stale.

    Text is decoded tolerantly, so one undecodable value cannot fail a query. Returns
    ``None`` when the file is absent or cannot be opened; an open that fails is a read
    error in *drift*.
    """

    if not path.is_file():
        return None
    live = (
        path.with_name(path.name + "-wal").exists() and path.with_name(path.name + "-shm").exists()
    )
    mode = "mode=ro" if live else "mode=ro&immutable=1"
    try:
        conn = sqlite3.connect(
            f"file:{quote(str(path))}?{mode}", uri=True, timeout=SQLITE_BUSY_SECONDS
        )
        conn.text_factory = _decode_text
        conn.execute("PRAGMA query_only = 1")
        return conn
    except sqlite3.Error:
        if drift is not None:
            drift.read_error(f"open.{path.name}")
        return None


def table_columns(
    conn: sqlite3.Connection, table: str, *, strict: bool = False
) -> frozenset[str] | None:
    """The columns of *table* from ``PRAGMA table_info``, or ``None`` if it is absent.

    A failed read is ``None`` too, unless *strict*, which lets the error through.
    """

    try:
        rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    except sqlite3.Error:
        if strict:
            raise
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

    try:
        actual = table_columns(conn, table, strict=True)
    except sqlite3.Error:
        drift.read_error(f"{db}.{table}")
        return None
    if actual is None:
        for column in sorted(required):
            drift.missing(f"{db}.{table}.{column}")
        return None
    for column in sorted(actual - expected):
        drift.unexpected(f"{db}.{table}.{column}")
    for column in sorted(required - actual):
        drift.missing(f"{db}.{table}.{column}")
    return actual
