"""The one way Metabrowser opens a SQLite database it does not own.

A viewer pointed at another application's database is a guest: it must never write to
the database or its log, create or delete a file beside it, roll back another process's
journal, or take a lock that can refuse the owner's commit.
`explorations/sqlite-guest-reads/README.md` records the measurements every rule here
rests on, and the plan's access table
(`docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md`, "Choosing
how to open") is what :func:`choose` implements, row for row.

Every connection made here runs in a reader process (:mod:`metabrowser.sqlite_readers`),
never in the server: a POSIX lock belongs to a process and a file, so closing any handle
on a database or its ``-shm`` drops every lock its process holds there, and the server
opens files for reasons of its own. A reader process opens and closes a database's files
only while it has no connection, with one exception that is the point of it: the race
check's ``-shm`` handle, opened before connecting and closed after the connection is.

This module imports only the standard library: a reader process loads this one file and
nothing else of the package (:func:`serve`). The server imports it for the generation
token (:func:`sqlite_generation`), which only stats files and reads bounded headers.

One request is: observe the files (stat, read the header, the journal's and the log's
headers), choose how to open, connect, read in one short transaction, close, and, for a
lock-free read, observe again and compare. A live journal or a read that failed
validation is retried with backoff, each retry choosing again from the top, until the
request's deadline; then a rollback-journal database is ``writer_busy`` and any other is
``changing``.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sqlite3
import stat
import sys
import threading
import time
from collections.abc import Callable, Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, get_args

# ── The file format ────────────────────────────────────────────

SQLITE_MAGIC: Final = b"SQLite format 3\x00"
# The database header (https://sqlite.org/fileformat.html, section 1.3).
HEADER_BYTES: Final = 100
# A write-ahead log's own header; a log no longer than it holds no frames.
WAL_HEADER_BYTES: Final = 32
# A rollback journal's header. `journal_mode=PERSIST` zeroes it between transactions and
# SQLite does not treat a journal whose header is zero as hot; one with any byte set is
# live: a writer is inside a transaction, or one died there.
JOURNAL_HEADER_BYTES: Final = 28
SIDECAR_SUFFIXES: Final = ("-journal", "-wal", "-shm")

type JournalKind = Literal["rollback", "wal"]
type AccessMode = Literal["immutable", "read_only", "private_copy"]
type ShownState = Literal["current", "another_name", "without_log"]
type ErrorState = Literal[
    "not_sqlite",
    "unsupported",
    "unreadable",
    "busy",
    "writer_busy",
    "changing",
    "damaged",
    "another_name",
    "without_log",
    "refused",
    "reader_stopped",
]
ERROR_STATES: Final[frozenset[str]] = frozenset(get_args(ErrorState.__value__))


def error_state(value: object) -> ErrorState:
    """*value* as an error state; anything else a reader answered is ``reader_stopped``."""
    for state in get_args(ErrorState.__value__):
        if value == state:
            return state
    return "reader_stopped"


# ── Library versions ───────────────────────────────────────────

# `octet_length()` sizes a value without reading it (the exploration's Values record:
# `length()` on a 200 MiB text peaked at 221 MiB, `octet_length()` at 20 MiB), and the
# table reads guard every expression with it, so it sets the reader's minimum.
READER_MINIMUM_LIBRARY: Final = (3, 43, 0)


@dataclass(frozen=True, slots=True)
class LibraryVersion:
    """One SQLite release that changes what a reader of other applications' files can do."""

    version: tuple[int, int, int]
    meaning: str


# What each release means for a reader, oldest first. Release notes: sqlite.org/changes.html.
LIBRARY_VERSIONS: Final = (
    LibraryVersion((3, 7, 0), "write-ahead-log databases"),
    LibraryVersion((3, 8, 2), "WITHOUT ROWID tables"),
    LibraryVersion((3, 26, 0), "SQLITE_DBCONFIG_DEFENSIVE and PRAGMA table_xinfo"),
    LibraryVersion((3, 31, 0), "PRAGMA trusted_schema and generated columns"),
    LibraryVersion((3, 37, 0), "STRICT tables"),
    LibraryVersion((3, 43, 0), "octet_length(), the reader's minimum for reading tables"),
    LibraryVersion((3, 45, 0), "JSONB values"),
)


def library_version() -> tuple[int, int, int]:
    major, minor, patch = (int(part) for part in sqlite3.sqlite_version.split(".")[:3])
    return major, minor, patch


def _dotted(version: tuple[int, int, int]) -> str:
    return ".".join(str(part) for part in version)


def library_report() -> dict[str, Any]:
    """The loaded SQLite library against :data:`LIBRARY_VERSIONS` and the minimum."""

    loaded = library_version()
    return {
        "version": sqlite3.sqlite_version,
        "minimum": _dotted(READER_MINIMUM_LIBRARY),
        "meets_minimum": loaded >= READER_MINIMUM_LIBRARY,
        "versions": [
            {
                "version": _dotted(entry.version),
                "meaning": entry.meaning,
                "available": loaded >= entry.version,
            }
            for entry in LIBRARY_VERSIONS
        ],
    }


# ── Connection settings ────────────────────────────────────────

# A short busy timeout: a guest never waits on the owner's locks for long. A `mode=ro`
# read through a live log waits only while the owner rebuilds its wal-index or holds a
# checkpoint's exclusive moment; a rollback-journal database is never locked at all.
BUSY_TIMEOUT_SECONDS: Final = 0.1
# Page cache per connection, in KiB (negative, as `PRAGMA cache_size` takes it). Every
# connection lives for one request, so a small cache is all one request reuses.
CACHE_KIB: Final = 2048
# The longest value a statement may produce. SQLite fails the whole statement past it,
# not one cell, so table reads guard each value with `octet_length` (the exploration's
# Encoding record, at this same limit). The record bound (`TABLE_RECORD_VALUE_BYTES`)
# previews past it through `blobopen`, which this limit does not apply to.
VALUE_MAX_BYTES: Final = 1_000_000
# The longest SQL text a statement may be: the adapter's own statements, a few KiB.
SQL_MAX_BYTES: Final = 100_000
# Columns and expression depth stay at SQLite's compiled defaults, named so a library
# built with larger ones cannot widen them. Lower values would refuse a database whose
# schema declares a wider table or a deeper expression, since both limits apply while
# the schema is parsed.
COLUMN_LIMIT: Final = 2000
EXPR_DEPTH_LIMIT: Final = 1000
# No database may be attached; the authorizer refuses ATTACH too.
ATTACHED_LIMIT: Final = 0
# The progress handler runs every this many virtual-machine opcodes, as `pull_catalog`
# sets it. A `count(*)` runs a handful of opcodes and never reaches it, which is why a
# watchdog interrupts at the deadline as well (the exploration's Budget record).
PROGRESS_OPCODES: Final = 1000
# The opcodes one request may run. The exploration's Budget record: a 100-row page in
# key order costs about 700 opcodes, an indexed sort about 1,200, an unindexed sort over
# 200,000 rows 1.4 to 1.9 million, and a capped count of a million rows 7 million. Ten
# million admits each of those once and stops a crafted view's runaway recursion.
READ_OPCODE_BUDGET: Final = 10_000_000

# Functions the adapter's own SQL calls. Any function inside a view is admitted as well
# (the authorizer names the view), since `trusted_schema=OFF` already refuses there
# every function not marked innocuous (the exploration's Encoding record).
ADAPTER_FUNCTIONS: Final = frozenset({"count", "typeof", "octet_length", "max", "min"})
# Pragmas the adapter reads, never with a value.
ADAPTER_PRAGMAS: Final = frozenset(
    {
        "application_id",
        "encoding",
        "freelist_count",
        "journal_mode",
        "page_count",
        "page_size",
        "user_version",
    }
)

# ── Waiting out a writer ───────────────────────────────────────

# Backoff between attempts while a journal is live or a read fails validation: the first
# wait, doubling to the longest. A rollback-journal owner's commit takes milliseconds, so
# the first retry usually finds it done; the cap keeps a long transaction from costing
# more than a tenth of a second past its end.
RETRY_FIRST_SECONDS: Final = 0.005
RETRY_MAX_SECONDS: Final = 0.1
# A write-ahead-log checkpoint writes the main file and leaves its change counter as it
# was, so a lock-free read of a write-ahead-log database counts the main file or its log
# as changing while its modification time is within this of the first stat, as Git
# treats a racy index entry. File times come from a coarse clock: at most 10 ms on Linux
# (one jiffy at HZ=100) and on APFS, one second on HFS+. FAT's two seconds is not
# covered; SQLite's own locking is unreliable there anyway.
RACY_MTIME_SECONDS: Final = 1.0
# A private copy of a database and its log (a log with no `-shm`, or a file with more
# than one name) is made per request, so it is bounded by what one request can afford to
# copy. Measured with `uv run python devtools/bench_sqlite_access.py`: see
# `explorations/sqlite-guest-reads/README.md#private-copies`.
COPY_MAX_BYTES: Final = 64 * 1024 * 1024
# A copy that fails validation this many times gives way to the main file read alone.
COPY_ATTEMPTS: Final = 2
# Copy buffer size.
_COPY_CHUNK: Final = 1024 * 1024

# application_id values worth naming (the header's bytes 68 to 72, big-endian). From
# SQLite's `magic.txt`, and fsqlite's own.
APPLICATION_IDS: Final = {
    0x4653514C: "fsqlite snapshot",
    0x47504B47: "GeoPackage",
    0x4D504258: "MBTiles",
}


class SqliteAccessError(Exception):
    """A read that could not be answered, and the state it is shown as."""

    def __init__(self, state: ErrorState, message: str) -> None:
        super().__init__(message)
        self.state: ErrorState = state


# ── Observing the files ────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class FileState:
    """One stat of a file: what a validated read compares before and after."""

    dev: int
    ino: int
    size: int
    mtime_ns: int
    nlink: int

    @classmethod
    def of(cls, info: os.stat_result) -> FileState:
        return cls(info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_nlink)

    def same_content(self, other: FileState | None) -> bool:
        return other is not None and (self.dev, self.ino, self.size, self.mtime_ns) == (
            other.dev,
            other.ino,
            other.size,
            other.mtime_ns,
        )


@dataclass(frozen=True, slots=True)
class Observation:
    """What one look at a database and the sidecars beside its real path saw.

    Taken with no connection open: it stats every file and reads three bounded headers.
    """

    path: Path
    main: FileState
    header: bytes
    journal: FileState | None
    journal_live: bool
    wal: FileState | None
    wal_header: bytes
    shm: FileState | None
    observed_ns: int

    @property
    def journal_kind(self) -> JournalKind:
        return "wal" if 2 in (self.header[18], self.header[19]) else "rollback"

    @property
    def change_counter(self) -> int:
        return int.from_bytes(self.header[24:28])

    @property
    def page_size(self) -> int:
        raw = int.from_bytes(self.header[16:18])
        return 65536 if raw == 1 else raw

    @property
    def wal_frames(self) -> int:
        """The log's frames by its size: frames it holds, valid or not."""
        if self.wal is None or self.wal.size <= WAL_HEADER_BYTES or self.page_size <= 0:
            return 0
        return (self.wal.size - WAL_HEADER_BYTES) // (24 + self.page_size)

    @property
    def wal_has_frames(self) -> bool:
        return self.wal is not None and self.wal.size > WAL_HEADER_BYTES

    def unchanged(self, after: Observation) -> bool:
        """Whether *after* saw the same files, so a lock-free read between them is valid.

        The main file's identity, size, modification time, and change counter, and the
        log's size, modification time, and header, match; no journal went live.
        """
        if not self.main.same_content(after.main) or self.change_counter != after.change_counter:
            return False
        if after.journal_live or self.journal_live:
            return False
        if (self.wal is None) != (after.wal is None):
            return False
        if self.wal is not None and not self.wal.same_content(after.wal):
            return False
        return self.wal_header == after.wal_header

    def racy(self) -> bool:
        """Whether a write-ahead-log database's main file or log was modified within
        :data:`RACY_MTIME_SECONDS` of this look, so a checkpoint could hide in it."""
        if self.journal_kind != "wal":
            return False
        window = int(RACY_MTIME_SECONDS * 1e9)
        stamps = [self.main.mtime_ns] + ([self.wal.mtime_ns] if self.wal is not None else [])
        return any(self.observed_ns - stamp < window for stamp in stamps)


def _stat(path: Path) -> FileState | None:
    try:
        return FileState.of(os.stat(path))
    except FileNotFoundError:
        return None


def _read_head(path: Path, size: int) -> bytes:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        return os.pread(fd, size, 0)
    finally:
        os.close(fd)


def sidecar(path: Path, suffix: str) -> Path:
    return path.with_name(path.name + suffix)


def observe(path: Path) -> Observation:
    """Stat *path*, a real path, and its sidecars, and read their headers.

    Raises :class:`SqliteAccessError` (``unreadable`` or ``not_sqlite``) for a file that
    cannot be read or is not a database. Opens files only for their headers; the caller
    holds no connection to this database while it runs.
    """
    try:
        info = os.stat(path)
        if not stat.S_ISREG(info.st_mode):
            raise SqliteAccessError("unreadable", "This is not a regular file.")
        header = _read_head(path, HEADER_BYTES)
    except FileNotFoundError as exc:
        raise SqliteAccessError("unreadable", "This file is no longer available.") from exc
    except PermissionError as exc:
        raise SqliteAccessError("unreadable", "This file cannot be read.") from exc
    except OSError as exc:
        raise SqliteAccessError("unreadable", f"This file cannot be read: {exc.strerror}") from exc
    if len(header) < HEADER_BYTES or not header.startswith(SQLITE_MAGIC):
        raise SqliteAccessError("not_sqlite", "This file is not a SQLite database.")
    journal_path = sidecar(path, "-journal")
    journal = _stat(journal_path)
    journal_live = False
    if journal is not None and journal.size > 0:
        try:
            journal_live = any(_read_head(journal_path, JOURNAL_HEADER_BYTES))
        except FileNotFoundError:
            journal = None
        except OSError:
            # A journal this reader cannot read is taken as live: waiting out a writer
            # that is not there costs a deadline, reading half-written rows costs more.
            journal_live = True
    wal_path = sidecar(path, "-wal")
    wal = _stat(wal_path)
    wal_header = b""
    if wal is not None and wal.size > 0:
        try:
            wal_header = _read_head(wal_path, WAL_HEADER_BYTES)
        except FileNotFoundError:
            wal = None
        except OSError as exc:
            raise SqliteAccessError(
                "unreadable", f"This database's log cannot be read: {exc.strerror}"
            ) from exc
    return Observation(
        path=path,
        main=FileState.of(info),
        header=header,
        journal=journal,
        journal_live=journal_live,
        wal=wal,
        wal_header=wal_header,
        shm=_stat(sidecar(path, "-shm")),
        observed_ns=time.time_ns(),
    )


# ── Generation ─────────────────────────────────────────────────


def sqlite_generation(path: Path) -> str:
    """A token that changes whenever a database's content may have changed.

    From stats and headers alone, never a connection: the main file's identity, size,
    modification time, and change counter, plus the log's size, modification time, and
    checkpoint sequence and salts (header bytes 12 to 24), which change every time the
    log restarts even when its size repeats (the exploration's Generation record).
    Raises ``OSError`` when the file is gone.
    """
    real = Path(os.path.realpath(path))
    info = os.stat(real)
    header = _read_head(real, HEADER_BYTES)
    parts = [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, header[24:28].hex()]
    wal_path = sidecar(real, "-wal")
    try:
        wal = os.stat(wal_path)
        wal_salts = _read_head(wal_path, 24)[12:24].hex() if wal.st_size else ""
        parts += [wal.st_size, wal.st_mtime_ns, wal_salts]
    except FileNotFoundError:
        parts.append("-")
    material = ":".join(str(part) for part in parts)
    return hashlib.sha256(material.encode()).hexdigest()[:16]


# ── Choosing how to open ───────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Plan:
    """How one attempt opens a database, and what its answer is shown as."""

    mode: AccessMode
    state: ShownState
    reason: str
    validate: bool


def choose(obs: Observation, *, immutable_content: bool, copy_failures: int) -> Plan | None:
    """The access table: how to open the database *obs* saw, or None to wait.

    None means a journal is live: a writer is inside a transaction, so the caller waits
    and looks again. *immutable_content* is content that cannot change, a Git blob.
    """
    version = obs.header[19]
    if version > 2:
        raise SqliteAccessError(
            "unsupported", f"This database's file format version {version} is newer than SQLite's."
        )
    wal = obs.journal_kind == "wal"
    if immutable_content:
        reason = "content that cannot change is read as it is"
        if wal:
            reason += "; a committed write-ahead-log database is read without its log"
        return Plan("immutable", "current", reason, validate=False)
    copyable = obs.main.size + (obs.wal.size if obs.wal else 0) <= COPY_MAX_BYTES
    if obs.main.nlink > 1:
        reason = (
            f"this file has {obs.main.nlink} names; a journal or log kept beside another "
            "name is not shown"
        )
        if copyable and copy_failures < COPY_ATTEMPTS:
            return Plan("private_copy", "another_name", reason, validate=True)
        return Plan("immutable", "another_name", reason, validate=True)
    if obs.journal_live:
        return None
    if not wal:
        return Plan(
            "immutable",
            "current",
            "a rollback-journal database is read without a lock, validated against a commit",
            validate=True,
        )
    if not obs.wal_has_frames:
        return Plan(
            "immutable",
            "current",
            "the write-ahead log holds no frames, so the main file is read without a lock, "
            "validated against a new frame or checkpoint",
            validate=True,
        )
    if obs.shm is not None:
        return Plan(
            "read_only",
            "current",
            "the write-ahead log holds frames and its index is present, so it is read "
            "through them as every reader does",
            validate=False,
        )
    if copyable and copy_failures < COPY_ATTEMPTS:
        return Plan(
            "private_copy",
            "current",
            "the write-ahead log holds frames and has no index beside it, so the database "
            "and its log are read through a private copy",
            validate=True,
        )
    size = obs.wal.size if obs.wal is not None else 0
    return Plan(
        "immutable",
        "without_log",
        f"without its {size:,}-byte log, which may be inconsistent",
        validate=True,
    )


# ── Connections ────────────────────────────────────────────────


def _authorizer(
    action: int, arg1: str | None, arg2: str | None, _db: str | None, inside: str | None
) -> int:
    """Admit reads only: SELECT, column reads, the adapter's functions and any function
    inside a view, the adapter's pragmas without a value, and transactions."""
    if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_RECURSIVE):
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_FUNCTION:
        if inside is not None or (arg2 or "").lower() in ADAPTER_FUNCTIONS:
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_PRAGMA:
        if arg2 is None and (arg1 or "").lower() in ADAPTER_PRAGMAS:
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_TRANSACTION:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def configure(connection: sqlite3.Connection, *, deadline: float, opcodes: int) -> None:
    """Apply the guest connection settings, the work budget, and the authorizer.

    Every setting runs before the first statement reads the schema, so a crafted schema
    is parsed under `trusted_schema=OFF` and `DEFENSIVE`.
    """
    connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, VALUE_MAX_BYTES)
    connection.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, SQL_MAX_BYTES)
    connection.setlimit(sqlite3.SQLITE_LIMIT_COLUMN, COLUMN_LIMIT)
    connection.setlimit(sqlite3.SQLITE_LIMIT_EXPR_DEPTH, EXPR_DEPTH_LIMIT)
    connection.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, ATTACHED_LIMIT)
    connection.setconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE, True)
    connection.execute("PRAGMA trusted_schema=OFF")
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA cell_size_check=ON")
    connection.execute("PRAGMA mmap_size=0")
    connection.execute(f"PRAGMA cache_size=-{CACHE_KIB}")
    steps = 0

    def bounded() -> int:
        nonlocal steps
        steps += PROGRESS_OPCODES
        return int(steps > opcodes or time.monotonic() >= deadline)

    connection.set_progress_handler(bounded, PROGRESS_OPCODES)
    connection.set_authorizer(_authorizer)


@contextlib.contextmanager
def _connection(uri: str, *, deadline: float, opcodes: int) -> Generator[sqlite3.Connection]:
    """A configured connection that a watchdog interrupts at *deadline*."""
    connection = sqlite3.connect(
        uri, uri=True, timeout=BUSY_TIMEOUT_SECONDS, isolation_level=None, cached_statements=0
    )
    lock = threading.Lock()
    open_ = True

    def interrupt() -> None:
        with lock:
            if open_:
                connection.interrupt()

    watchdog = threading.Timer(max(0.0, deadline - time.monotonic()), interrupt)
    watchdog.daemon = True
    watchdog.start()
    try:
        configure(connection, deadline=deadline, opcodes=opcodes)
        connection.execute("BEGIN")
        yield connection
    finally:
        watchdog.cancel()
        with lock:
            open_ = False
            connection.close()


def _uri(path: Path, mode: AccessMode) -> str:
    query = "?mode=ro&immutable=1" if mode == "immutable" else "?mode=ro"
    return path.as_uri() + query


def _copy_file(source: Path, target: Path, limit: int) -> int:
    """Copy at most *limit* bytes; the copy opens and closes the source with no
    connection open in this process."""
    copied = 0
    with open(source, "rb") as reader, open(target, "xb") as writer:
        while copied <= limit:
            chunk = reader.read(min(_COPY_CHUNK, limit + 1 - copied))
            if not chunk:
                break
            writer.write(chunk)
            copied += len(chunk)
    if copied > limit:
        raise OSError("the file grew past the copy limit while it was copied")
    return copied


def _private_copy(obs: Observation, scratch: Path) -> Path:
    """Copy the main file, then its log, into a fresh folder under *scratch*.

    The main file goes first: a checkpoint during the copy moves only pages the log still
    holds, so the pair stays consistent unless the log restarts, which validation sees.
    """
    folder = Path(_fresh_folder(scratch, "copy"))
    target = folder / "db"
    _copy_file(obs.path, target, COPY_MAX_BYTES)
    if obs.wal is not None:
        with contextlib.suppress(FileNotFoundError):
            _copy_file(sidecar(obs.path, "-wal"), sidecar(target, "-wal"), COPY_MAX_BYTES)
    return target


def _fresh_folder(scratch: Path, prefix: str) -> str:
    for index in range(1000):
        candidate = scratch / f"{prefix}-{index}"
        try:
            candidate.mkdir(mode=0o700)
        except FileExistsError:
            continue
        return str(candidate)
    raise OSError("no free private folder")


_DAMAGED_CODES: Final = frozenset({sqlite3.SQLITE_CORRUPT, sqlite3.SQLITE_NOTADB})


def _classify(exc: sqlite3.Error) -> SqliteAccessError:
    """The state an SQLite error on a read that was not in doubt is shown as.

    Only SQLite's own codes for a damaged file are damage; an authorizer's denial is
    reported at prepare time as a plain error naming it.
    """
    code = getattr(exc, "sqlite_errorcode", 0) & 0xFF
    if code in _DAMAGED_CODES:
        return SqliteAccessError("damaged", f"This database is damaged: {exc}")
    if code in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED, sqlite3.SQLITE_NOMEM):
        return SqliteAccessError("busy", f"The database is busy: {exc}")
    if code == sqlite3.SQLITE_INTERRUPT:
        return SqliteAccessError("busy", "The read ran past its deadline or its work budget.")
    if code == sqlite3.SQLITE_AUTH or "not authorized" in str(exc):
        return SqliteAccessError("refused", f"The read was refused: {exc}")
    return SqliteAccessError("unreadable", f"This database could not be read: {exc}")


@dataclass(frozen=True, slots=True)
class Access:
    """How a read was answered: the plan it used and what it noticed."""

    plan: Plan
    observation: Observation
    attempts: int
    notices: tuple[str, ...]


type ReadFn[T] = Callable[[sqlite3.Connection], T]


def read[T](
    path: Path,
    fn: ReadFn[T],
    *,
    deadline: float,
    scratch: Path,
    immutable_content: bool = False,
    opcodes: int = READ_OPCODE_BUDGET,
) -> tuple[T, Access]:
    """Run *fn* in one short read transaction on the database at *path*.

    *deadline* is a ``time.monotonic()`` instant. *scratch* is a private folder the
    caller created and removes, where private copies go. Raises
    :class:`SqliteAccessError` with the state the request is shown as.
    """
    real = Path(os.path.realpath(path))
    attempts = 0
    copy_failures = 0
    wait = RETRY_FIRST_SECONDS
    last_kind: JournalKind = "rollback"
    while True:
        attempts += 1
        obs = observe(real)
        last_kind = obs.journal_kind
        plan = choose(obs, immutable_content=immutable_content, copy_failures=copy_failures)
        if plan is not None and not (plan.validate and plan.mode != "private_copy" and obs.racy()):
            outcome = _attempt(
                real, obs, plan, fn, deadline=deadline, scratch=scratch, opcodes=opcodes
            )
            if outcome is not None:
                value, notices = outcome
                return value, Access(plan, obs, attempts, notices)
            if plan.mode == "private_copy":
                copy_failures += 1
        if time.monotonic() + wait >= deadline:
            break
        time.sleep(wait)
        wait = min(wait * 2, RETRY_MAX_SECONDS)
    if last_kind == "rollback":
        raise SqliteAccessError(
            "writer_busy", "The application that owns this database is writing to it."
        )
    raise SqliteAccessError("changing", "This database changed during every read.")


class _LookAgain(Exception):
    """The files changed under this attempt; the caller looks again and chooses again."""


def _attempt[T](
    real: Path,
    obs: Observation,
    plan: Plan,
    fn: ReadFn[T],
    *,
    deadline: float,
    scratch: Path,
    opcodes: int,
) -> tuple[T, tuple[str, ...]] | None:
    """One read under *plan*: its value and notices, or None when it failed validation."""
    notices: list[str] = []
    lock_free = plan.validate and plan.mode == "immutable"
    try:
        if plan.mode == "read_only":
            value = _read_through_log(
                real, obs, fn, deadline=deadline, opcodes=opcodes, notices=notices
            )
        else:
            target = real
            if plan.mode == "private_copy":
                try:
                    target = _private_copy(obs, scratch)
                except OSError:
                    return None
                if not obs.unchanged(observe(real)):
                    return None
            uri = _uri(target, "read_only" if plan.mode == "private_copy" else "immutable")
            with _connection(uri, deadline=deadline, opcodes=opcodes) as connection:
                value = fn(connection)
    except _LookAgain:
        return None
    except sqlite3.Error as exc:
        error = _classify(exc)
        if lock_free and not obs.unchanged(observe(real)):
            # An error from a read that failed validation is the change, not damage.
            return None
        if error.state == "damaged" and plan.state != "current":
            raise SqliteAccessError(plan.state, f"{plan.reason}; reading it failed: {exc}") from exc
        raise error from exc
    if lock_free and not obs.unchanged(observe(real)):
        return None
    return value, tuple(notices)


def _read_through_log[T](
    real: Path,
    obs: Observation,
    fn: ReadFn[T],
    *,
    deadline: float,
    opcodes: int,
    notices: list[str],
) -> T:
    """A `mode=ro` read through a live log, with the race check.

    The `-shm` this look saw is opened before connecting and held until the connection
    has closed, so nothing in this process closes a handle on it while SQLite holds its
    locks there (the exploration's Process record). After connecting, its identity is
    compared with the path's: an owner that exited in between removed it, and this open
    then created a new log and index beside the database, which the answer says.
    """
    shm_path = sidecar(real, "-shm")
    try:
        held = os.open(shm_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError as exc:
        # Gone since the look: the owner closed, and opening now would create the log
        # and its index.
        raise _LookAgain from exc
    try:
        held_state = FileState.of(os.fstat(held))
        if obs.shm is None or (held_state.dev, held_state.ino) != (obs.shm.dev, obs.shm.ino):
            raise _LookAgain
        with _connection(_uri(real, "read_only"), deadline=deadline, opcodes=opcodes) as connection:
            value = fn(connection)
            path_state = _stat(shm_path)
            held_links = os.fstat(held).st_nlink
            main_state = _stat(real)
        if (
            path_state is None
            or (held_state.dev, held_state.ino) != (path_state.dev, path_state.ino)
            or held_links == 0
        ):
            notices.append(
                "the application that owns this database closed while it was opened; "
                "the read created a new log and index beside it, which that application "
                "removes when it next opens and closes the database"
            )
        if main_state is None or (main_state.dev, main_state.ino) != (obs.main.dev, obs.main.ino):
            raise _LookAgain
        return value
    finally:
        os.close(held)


# ── The Info view ──────────────────────────────────────────────

# Pragmas the Info view reads on the connection, since the main file's header is stale
# while a log holds frames.
_INFO_PRAGMAS: Final = (
    "page_size",
    "page_count",
    "encoding",
    "user_version",
    "application_id",
    "freelist_count",
)


def _application_name(value: int) -> str | None:
    if value in APPLICATION_IDS:
        return APPLICATION_IDS[value]
    raw = (value & 0xFFFFFFFF).to_bytes(4)
    if value and all(0x20 < byte < 0x7F for byte in raw):
        return f"“{raw.decode('ascii')}”"
    return None


def info(
    path: Path, *, deadline: float, scratch: Path, immutable_content: bool = False
) -> dict[str, Any]:
    """What the Info view shows: the database as the connection reads it, its sidecars,
    how it was opened and why, and the SQLite library against the reader's minimum."""

    def gather(connection: sqlite3.Connection) -> tuple[dict[str, Any], dict[str, int]]:
        pragmas: dict[str, Any] = {
            name: connection.execute(f"PRAGMA {name}").fetchone()[0] for name in _INFO_PRAGMAS
        }
        objects = {
            str(kind): int(count)
            for kind, count in connection.execute(
                "SELECT type, count(*) FROM sqlite_schema GROUP BY type ORDER BY type"
            )
        }
        return pragmas, objects

    (pragmas, objects), access = read(
        path, gather, deadline=deadline, scratch=scratch, immutable_content=immutable_content
    )
    obs = access.observation
    sidecars: list[dict[str, Any]] = []
    if obs.journal is not None:
        sidecars.append({"name": "-journal", "size": obs.journal.size, "live": obs.journal_live})
    if obs.wal is not None:
        sidecars.append({"name": "-wal", "size": obs.wal.size, "frames": obs.wal_frames})
    if obs.shm is not None:
        sidecars.append({"name": "-shm", "size": obs.shm.size})
    application_id = int(pragmas["application_id"])
    return {
        "access": {
            "mode": access.plan.mode,
            "state": access.plan.state,
            "reason": access.plan.reason,
            "attempts": access.attempts,
            "notices": list(access.notices),
        },
        "journal_mode": obs.journal_kind,
        "links": obs.main.nlink,
        "size": obs.main.size,
        "sidecars": sidecars,
        "database": {
            "page_size": pragmas["page_size"],
            "page_count": pragmas["page_count"],
            "encoding": pragmas["encoding"],
            "user_version": pragmas["user_version"],
            "application_id": application_id,
            "application_name": _application_name(application_id),
            "freelist_count": pragmas["freelist_count"],
            "objects": objects,
        },
        "library": library_report(),
    }


# ── The reader process ─────────────────────────────────────────


def _limit_address_space(limit: int) -> None:
    """Bound this process's address space where the platform enforces one (Linux)."""
    if limit <= 0:
        return
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    except (ImportError, ValueError, OSError):
        return


def _info_op(args: dict[str, Any], deadline: float) -> dict[str, Any]:
    return info(
        Path(args["path"]),
        deadline=deadline,
        scratch=Path(args["scratch"]),
        immutable_content=bool(args.get("immutable_content")),
    )


type Op = Callable[[dict[str, Any], float], Any]

# What a reader process answers, by request name: each takes the request's arguments
# (JSON) and its deadline (a ``time.monotonic()`` instant in the worker) and returns a
# JSON value, or raises :class:`SqliteAccessError`. The parent asks through
# ``ReaderPool.call(op, args, ...)``.
OPS: Final[dict[str, Op]] = {
    "ping": lambda _args, _deadline: None,
    "info": _info_op,
}


def _handle(request: dict[str, Any]) -> dict[str, Any]:
    op = OPS.get(str(request.get("op")))
    args = request.get("args") or {}
    deadline = time.monotonic() + float(request.get("seconds", 0))
    if op is None:
        return {"ok": False, "state": "refused", "error": f"unknown request {request.get('op')!r}"}
    try:
        return {"ok": True, "result": op(args, deadline)}
    except SqliteAccessError as exc:
        return {"ok": False, "state": exc.state, "error": str(exc)}
    except MemoryError:
        return {"ok": False, "state": "busy", "error": "The read ran out of memory."}
    except Exception as exc:
        return {
            "ok": False,
            "state": "unreadable",
            "error": f"The reader failed: {type(exc).__name__}: {exc}",
        }


def serve() -> None:
    """A reader process's loop: one JSON request per line on stdin, one answer per line
    on stdout, one at a time, until stdin closes, which is how the parent stops it and
    how a worker whose parent died exits."""
    if len(sys.argv) > 2:
        _limit_address_space(int(sys.argv[2]))
    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer
    for line in stdin:
        try:
            request = json.loads(line)
        except ValueError:
            response: dict[str, Any] = {
                "ok": False,
                "state": "refused",
                "error": "malformed request",
            }
        else:
            response = _handle(request) | {"id": request.get("id")}
        stdout.write(json.dumps(response, allow_nan=False, separators=(",", ":")).encode() + b"\n")
        stdout.flush()
