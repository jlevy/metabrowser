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
import errno
import hashlib
import json
import os
import sqlite3
import stat
import struct
import sys
import threading
import time
from collections.abc import Callable, Generator, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, get_args

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows has no POSIX locks; see `_index_in_use`
    fcntl = None

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
# The `-shm` byte every connection to a write-ahead-log database holds a shared lock on
# while it is open (SQLite's `UNIX_SHM_DMS`, its "dead-man switch": the 8 lock bytes from
# offset 120, then this one). A lock held there is a live connection; none is an owner
# that crashed or a folder copied with its sidecars, whose index the next connection
# rebuilds by rewriting `-shm`.
SHM_DMS_BYTE: Final = 128
# The wal-index header at the start of `-shm`: its change counter, frame count, page
# count, salts, and checksums (https://sqlite.org/walformat.html, section 2.1). A commit
# changes it even when the log is overwritten in place and keeps its size and salts.
SHM_HEADER_BYTES: Final = 48

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
    "too_large",
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
# Terms in a compound SELECT, a LIKE or GLOB pattern's bytes, and opcodes in one compiled
# statement, at SQLite's compiled defaults for the same reason: a schema's views are
# compiled under them, and a library built with larger ones cannot widen them.
COMPOUND_SELECT_LIMIT: Final = 500
LIKE_PATTERN_LIMIT: Final = 50_000
VDBE_OP_LIMIT: Final = 250_000_000
# No database may be attached; the authorizer refuses ATTACH too.
ATTACHED_LIMIT: Final = 0
# The progress handler runs every this many virtual-machine opcodes, as `pull_catalog`
# sets it. A `count(*)` runs a handful of opcodes and never reaches it, which is why a
# watchdog interrupts at the deadline as well (the exploration's Budget record).
PROGRESS_OPCODES: Final = 1000
# The most heap SQLite may allocate in a reader process (`PRAGMA hard_heap_limit`, which
# is process-wide, so a reader process sets it once as it starts, in `serve`). A failed
# allocation is `SQLITE_NOMEM`, answered `busy`. It bounds SQLite's own memory on
# macOS, where the reader's `RLIMIT_AS` (`READER_ADDRESS_SPACE_BYTES`) is not enforced:
# half of that address space, with the other half for Python's heap and the reader's
# mapped interpreter, whose measured share (112 MiB mapped after 50 Info reads, peaking
# at 176 MiB) sits beside that constant.
HEAP_LIMIT_BYTES: Final = 512 * 1024 * 1024
# The opcodes one request may run. The exploration's Budget record: a 100-row page in
# key order costs about 700 opcodes, an indexed sort about 1,200, an unindexed sort over
# 200,000 rows 1.4 to 1.9 million, and a capped count of a million rows 7 million. Ten
# million admits each of those once and stops a crafted view's runaway recursion.
READ_OPCODE_BUDGET: Final = 10_000_000

# Functions the adapter's own SQL calls. Any function inside a view is admitted as well
# (the authorizer names the view), since `trusted_schema=OFF` already refuses there
# every function not marked innocuous (the exploration's Encoding record).
ADAPTER_FUNCTIONS: Final = frozenset({"count", "typeof", "octet_length", "max", "min"})
# Pragmas that describe the schema and take an argument, the object they describe, as a
# statement (`PRAGMA table_xinfo(t)`) or a table-valued function
# (`SELECT * FROM pragma_table_xinfo('t')`). None writes or changes the connection, so
# each is admitted with any argument; every other pragma with an argument is a setting
# and is refused.
ADAPTER_SCHEMA_PRAGMAS: Final = frozenset(
    {"foreign_key_list", "index_list", "index_xinfo", "table_list", "table_xinfo"}
)
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
# copy. `uv run python -m devtools.bench_sqlite_access` (2026-11-20, 4 CPUs at a load of
# 4, the temporary folder on the container's disk): copying the pair took a median 6 ms
# at 8 MiB, 18 ms at 32 MiB, and 60 ms at 129 MiB, and an Info read through the copy,
# which rebuilds the log's index, 12 ms at 8 MiB and 41 ms at 32 MiB. At this cap a read
# through a copy costs about 80 ms, a twenty-fifth of a request's deadline.
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
    # Whether a live connection holds `-shm` (:func:`_index_in_use`); asked only when the
    # log holds frames, the one state it decides.
    shm_in_use: bool
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
        :data:`RACY_MTIME_SECONDS` of this look, so a checkpoint could hide in it.

        A time further than the window ahead of the clock (skew, a restored or synced
        file) is not racy: any write sets the time to now, which differs from it, so
        validation sees the change.
        """
        if self.journal_kind != "wal":
            return False
        window = int(RACY_MTIME_SECONDS * 1e9)
        stamps = [self.main.mtime_ns] + ([self.wal.mtime_ns] if self.wal is not None else [])
        return any(-window < self.observed_ns - stamp < window for stamp in stamps)


def _stat(path: Path) -> FileState | None:
    try:
        return FileState.of(os.stat(path))
    except FileNotFoundError:
        return None


class NotRegularFileError(OSError):
    """A database or sidecar name that is not a regular file: a FIFO, a device, a folder."""


def _open_regular(path: Path) -> int:
    """Open *path* to read it, never following a symlink and never blocking on a FIFO,
    and refuse anything but a regular file. The caller closes the descriptor."""
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise NotRegularFileError(errno.EINVAL, "not a regular file", path.name)
    except BaseException:
        os.close(fd)
        raise
    return fd


def _read_head(path: Path, size: int) -> bytes:
    fd = _open_regular(path)
    try:
        return os.pread(fd, size, 0)
    finally:
        os.close(fd)


# `struct flock` as `F_GETLK` takes it: Linux orders it type, whence, start, length, pid
# (32 bytes with its padding); macOS and the BSDs start, length, pid, type, whence. A
# platform not named here is never asked, and its index is taken as unused.
_FLOCK_LAYOUTS: Final = {"linux": "hhqqi4x", "darwin": "qqihh"}


def _index_in_use(fd: int) -> bool:
    """Whether any other process holds a lock on the `-shm` byte :data:`SHM_DMS_BYTE`
    through *fd*, which this process opened read-only and holds no lock through.

    ``F_GETLK`` only asks: it takes no lock and changes nothing. When the platform's
    layout is unknown or the question fails, the answer is no, so the reader takes the
    private copy, which writes nothing beside the database.
    """
    layout = _FLOCK_LAYOUTS.get(sys.platform)
    if fcntl is None or layout is None:
        return False
    if layout.startswith("hh"):
        query = struct.pack(layout, fcntl.F_WRLCK, os.SEEK_SET, SHM_DMS_BYTE, 1, 0)
    else:
        query = struct.pack(layout, SHM_DMS_BYTE, 1, 0, fcntl.F_WRLCK, os.SEEK_SET)
    try:
        answer = struct.unpack(layout, fcntl.fcntl(fd, fcntl.F_GETLK, query))
    except OSError:
        return False
    kind = answer[0] if layout.startswith("hh") else answer[3]
    return kind != fcntl.F_UNLCK


def _shm_in_use(path: Path) -> bool:
    """Whether a live connection holds the `-shm` at *path*: opened read-only, asked with
    ``F_GETLK``, and closed, with no connection open in this process."""
    try:
        fd = _open_regular(path)
    except OSError:
        return False
    try:
        return _index_in_use(fd)
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
    shm_path = sidecar(path, "-shm")
    shm = _stat(shm_path)
    with_frames = wal is not None and wal.size > WAL_HEADER_BYTES
    return Observation(
        path=path,
        main=FileState.of(info),
        header=header,
        journal=journal,
        journal_live=journal_live,
        wal=wal,
        wal_header=wal_header,
        shm=shm,
        shm_in_use=shm is not None and with_frames and _shm_in_use(shm_path),
        observed_ns=time.time_ns(),
    )


# ── Generation ─────────────────────────────────────────────────


def sqlite_generation(path: Path) -> str:
    """A token that changes whenever a database's content may have changed.

    From stats and headers alone, never a connection: the main file's identity, size,
    modification time, and change counter, plus the log's size, modification time, and
    checkpoint sequence and salts (header bytes 12 to 24), which change every time the
    log restarts even when its size repeats (the exploration's Generation record), and
    the wal-index header (:data:`SHM_HEADER_BYTES`), whose change counter and frame count
    move on every commit, even one that overwrites a restarted log in place within one
    tick of the file clock. That header is read without a lock, so a read torn by a
    commit gives a token that changes once more than it had to, never one that misses
    the commit. Raises ``OSError`` when the file is gone.
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
    try:
        # The server holds no connection to a database it does not own, so opening and
        # closing its `-shm` here drops no lock.
        parts.append(_read_head(sidecar(real, "-shm"), SHM_HEADER_BYTES).hex())
    except OSError:
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
    if obs.shm is not None and obs.shm_in_use:
        return Plan(
            "read_only",
            "current",
            "the write-ahead log holds frames and an application has it open, so it is "
            "read through them as every reader does",
            validate=False,
        )
    if obs.shm is None:
        why = "the write-ahead log holds frames and has no index beside it"
    else:
        # No connection holds the index: a crashed owner or a copied folder. Opening it
        # would rebuild the index by rewriting `-shm`.
        why = "the write-ahead log holds frames and no application has it open"
    if copyable and copy_failures < COPY_ATTEMPTS:
        return Plan(
            "private_copy",
            "current",
            f"{why}, so the database and its log are read through a private copy",
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
    inside a view, the adapter's pragmas without a value, its schema pragmas with any
    argument, and transactions."""
    if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_RECURSIVE):
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_FUNCTION:
        if inside is not None or (arg2 or "").lower() in ADAPTER_FUNCTIONS:
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_PRAGMA:
        name = (arg1 or "").lower()
        if name in ADAPTER_SCHEMA_PRAGMAS or (arg2 is None and name in ADAPTER_PRAGMAS):
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_TRANSACTION:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def deny_reads(connection: sqlite3.Connection, names: Iterable[str]) -> None:
    """Refuse, from now on, every read of a table named in *names* on *connection*, a
    guest connection :func:`read` hands its ``fn``.

    A connection has one authorizer, so this installs :func:`_authorizer` composed with
    the denial: a column read or a whole-table read such as `count(*)` of a named table
    (compared casefolded, as SQLite compares names) in any statement or inside any view,
    and a schema pragma describing one, as a statement or a table-valued function, are
    refused at prepare time (``refused``). Call it inside ``fn``, after reading the schema
    in the same transaction, so the names come from the schema the read sees. A later
    call replaces the earlier names.

    It stops the query, not the virtual table's module: SQLite computes a view's column
    names with no authorizer (``xAuth = 0``, measured on SQLite 3.53), so preparing a
    statement over a view that names a virtual table still connects that table (FTS5's
    ``xConnect`` reads ``<table>_config``). Only ``sqlite3_drop_modules`` would stop
    that, and Python's ``sqlite3`` does not expose it.
    """
    denied = frozenset(name.casefold() for name in names)

    def authorizer(
        action: int, arg1: str | None, arg2: str | None, db: str | None, inside: str | None
    ) -> int:
        if action == sqlite3.SQLITE_READ and (arg1 or "").casefold() in denied:
            return sqlite3.SQLITE_DENY
        if (
            action == sqlite3.SQLITE_PRAGMA
            and (arg1 or "").lower() in ADAPTER_SCHEMA_PRAGMAS
            and (arg2 or "").casefold() in denied
        ):
            return sqlite3.SQLITE_DENY
        return _authorizer(action, arg1, arg2, db, inside)

    connection.set_authorizer(authorizer)


def apply_settings(
    connection: sqlite3.Connection,
    *,
    value_max_bytes: int = VALUE_MAX_BYTES,
    cache_kib: int = CACHE_KIB,
) -> None:
    """The settings every connection the product makes runs under, its own databases'
    included: the named limits, `DEFENSIVE`, `trusted_schema=OFF`, `cell_size_check`,
    no memory map, and a small cache. They run before the first statement reads the
    schema, so a crafted schema is parsed under them."""
    connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, value_max_bytes)
    connection.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, SQL_MAX_BYTES)
    connection.setlimit(sqlite3.SQLITE_LIMIT_COLUMN, COLUMN_LIMIT)
    connection.setlimit(sqlite3.SQLITE_LIMIT_EXPR_DEPTH, EXPR_DEPTH_LIMIT)
    connection.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, ATTACHED_LIMIT)
    connection.setlimit(sqlite3.SQLITE_LIMIT_COMPOUND_SELECT, COMPOUND_SELECT_LIMIT)
    connection.setlimit(sqlite3.SQLITE_LIMIT_LIKE_PATTERN_LENGTH, LIKE_PATTERN_LIMIT)
    connection.setlimit(sqlite3.SQLITE_LIMIT_VDBE_OP, VDBE_OP_LIMIT)
    connection.setconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE, True)
    connection.execute("PRAGMA trusted_schema=OFF")
    connection.execute("PRAGMA cell_size_check=ON")
    connection.execute("PRAGMA mmap_size=0")
    connection.execute(f"PRAGMA cache_size=-{cache_kib}")


def bound_work(connection: sqlite3.Connection, *, opcodes: int, deadline: float | None) -> None:
    """Stop a statement past *opcodes* virtual-machine steps or the *deadline*
    (``time.monotonic()``), through the progress handler."""
    steps = 0

    def bounded() -> int:
        nonlocal steps
        steps += PROGRESS_OPCODES
        late = deadline is not None and time.monotonic() >= deadline
        return int(steps > opcodes or late)

    connection.set_progress_handler(bounded, PROGRESS_OPCODES)


def configure(connection: sqlite3.Connection, *, deadline: float, opcodes: int) -> None:
    """Apply the work budget, the guest connection settings, `query_only`, and the
    reads-only authorizer.

    The budget comes first: `PRAGMA cache_size` loads the schema, so a crafted schema is
    parsed under it as well as under the watchdog. The authorizer comes last, since it
    refuses the settings' own pragmas.
    """
    bound_work(connection, opcodes=opcodes, deadline=deadline)
    apply_settings(connection)
    connection.execute("PRAGMA query_only=ON")
    connection.set_authorizer(_authorizer)


def is_database_header(header: bytes) -> bool:
    """Whether *header*, a file's first bytes, is a whole SQLite database header."""
    return len(header) >= HEADER_BYTES and header.startswith(SQLITE_MAGIC)


# ── The product's own databases ────────────────────────────────


class _ProcessHandles:
    """Handles this process opened on a database it also has connections to.

    A POSIX lock belongs to a process and a file, so closing any handle on a database
    drops every lock any connection in the process holds there (the exploration's
    Access record). A database the product owns is read and written in the server
    process, where one thread's handle may close while another thread's connection
    holds a lock; this defers that close until the last connection in the process to
    the same file has closed, as SQLite defers its own.

    Deferred handles accumulate while connections to one file overlap without a moment
    at zero, as SQLite's own deferred closes do: each request adds the few it opened (the
    catalog opens the file and two sidecars), bounded only by the process's descriptor
    limit, and all close when the last overlapping connection does.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._open: dict[tuple[int, int], int] = {}
        self._deferred: dict[tuple[int, int], list[int]] = {}

    @contextlib.contextmanager
    def connected(self, key: tuple[int, int]) -> Generator[None]:
        """Mark a connection to the file *key* (device, inode) open for the block."""
        with self._lock:
            self._open[key] = self._open.get(key, 0) + 1
        try:
            yield
        finally:
            with self._lock:
                left = self._open[key] - 1
                if left:
                    self._open[key] = left
                    closing: list[int] = []
                else:
                    del self._open[key]
                    closing = self._deferred.pop(key, [])
                for fd in closing:
                    os.close(fd)

    def close(self, fd: int, key: tuple[int, int]) -> None:
        """Close *fd*, a handle on the file *key* or one of its sidecars, now or, while a
        connection in this process is open on that file, after the last one closes."""
        with self._lock:
            if self._open.get(key):
                self._deferred.setdefault(key, []).append(fd)
                return
            os.close(fd)


PROCESS_HANDLES: Final = _ProcessHandles()


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
    source_fd = _open_regular(source)
    with os.fdopen(source_fd, "rb") as reader, open(target, "xb") as writer:
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


def _error_code(exc: sqlite3.Error) -> int:
    """*exc*'s primary result code."""
    return getattr(exc, "sqlite_errorcode", 0) & 0xFF


def _classify(exc: sqlite3.Error) -> SqliteAccessError:
    """The state an SQLite error on a read that was not in doubt is shown as.

    Only SQLite's own codes for a damaged file are damage; an authorizer's denial is
    reported at prepare time as a plain error naming it.
    """
    code = _error_code(exc)
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
    attempts: int | None = None,
) -> tuple[T, Access]:
    """Run *fn* in one short read transaction on the database at *path*.

    *deadline* is a ``time.monotonic()`` instant. *scratch* is a private folder the
    caller created and removes, where private copies go. *attempts*, when given, is the
    most attempts to make, with no wait after the last: one is a read validated apart
    with no wait, as a capped count is (Decision 10), whose caller falls back to an
    estimate. Raises :class:`SqliteAccessError` with the state the request is shown as.
    """
    real = Path(os.path.realpath(path))
    limit = attempts
    attempts = 0
    copy_failures = 0
    wait = RETRY_FIRST_SECONDS
    last_kind: JournalKind = "rollback"
    transient: _Transient | None = None
    while True:
        attempts += 1
        obs = observe(real)
        last_kind = obs.journal_kind
        transient = None
        plan = choose(obs, immutable_content=immutable_content, copy_failures=copy_failures)
        if plan is not None and not (plan.validate and plan.mode != "private_copy" and obs.racy()):
            try:
                outcome = _attempt(
                    real, obs, plan, fn, deadline=deadline, scratch=scratch, opcodes=opcodes
                )
            except _Transient as exc:
                transient, outcome = exc, None
            if outcome is not None:
                value, notices = outcome
                return value, Access(plan, obs, attempts, notices)
            if plan.mode == "private_copy":
                copy_failures += 1
        if limit is not None and attempts >= limit:
            break
        if time.monotonic() + wait >= deadline:
            break
        time.sleep(wait)
        wait = min(wait * 2, RETRY_MAX_SECONDS)
    if transient is not None:
        raise transient.error from transient.__cause__
    if last_kind == "rollback":
        raise SqliteAccessError(
            "writer_busy", "The application that owns this database is writing to it."
        )
    raise SqliteAccessError("changing", "This database changed during every read.")


class _LookAgain(Exception):
    """The files changed under this attempt; the caller looks again and chooses again."""


class _Transient(Exception):
    """A read through a live log met a passing state: looked at again until the
    deadline, then answered as *error*."""

    def __init__(self, error: SqliteAccessError) -> None:
        super().__init__(str(error))
        self.error = error


# What a `mode=ro` read through a live log can meet for a moment: the owner's recovery or
# a checkpoint's exclusive moment outlasting `BUSY_TIMEOUT_SECONDS` (`SQLITE_BUSY`), or
# the owner removing its log while the read opens it (`SQLITE_CANTOPEN`).
_TRANSIENT_CODES: Final = frozenset({sqlite3.SQLITE_BUSY, sqlite3.SQLITE_CANTOPEN})


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
        if plan.mode == "read_only" and _error_code(exc) in _TRANSIENT_CODES:
            raise _Transient(error) from exc
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

    Only a log that a live connection holds is read this way (:func:`_index_in_use`): with
    no owner, the first connection rebuilds the index by rewriting `-shm`. The `-shm` this
    look saw is opened before connecting and held until the connection
    has closed, so nothing in this process closes a handle on it while SQLite holds its
    locks there (the exploration's Process record). After connecting, its identity is
    compared with the path's: an owner that exited in between removed it, and this open
    then created a new log and index beside the database, which the answer says.
    """
    shm_path = sidecar(real, "-shm")
    try:
        held = _open_regular(shm_path)
    except FileNotFoundError as exc:
        # Gone since the look: the owner closed, and opening now would create the log
        # and its index.
        raise _LookAgain from exc
    except OSError as exc:
        raise SqliteAccessError(
            "unreadable", f"This database's log index cannot be read: {exc.strerror}"
        ) from exc
    try:
        held_state = FileState.of(os.fstat(held))
        if obs.shm is None or (held_state.dev, held_state.ino) != (obs.shm.dev, obs.shm.ino):
            raise _LookAgain
        if not _index_in_use(held):
            # The owner closed or crashed since the look. Connecting now would make this
            # read the first connection, which rebuilds the index by rewriting `-shm`;
            # the next look sees no owner and takes the private copy. An owner that
            # crashes between this question and the connection is the one window left,
            # as narrow as the one the notice below reports.
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


# Schema objects by kind, every `type` outside the four SQLite writes counted as `other`.
_OBJECT_KINDS_SQL: Final = (
    "SELECT CASE WHEN typeof(type) = 'text' AND type IN ('table', 'index', 'view', 'trigger') "
    "THEN type ELSE 'other' END AS kind, count(*) FROM sqlite_schema GROUP BY kind ORDER BY kind"
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
        # Grouped by a closed set in SQL: SQLite accepts a schema row whose `type` reads
        # as `table` up to a NUL, so a crafted file could otherwise name a group per row.
        objects = {str(kind): int(count) for kind, count in connection.execute(_OBJECT_KINDS_SQL)}
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

# The longest answer, as one JSON line, a reader returns; a longer one is answered
# `too_large` in its place, and the parent stops a reader that sends more
# (`_Worker.ask`) with the same state. Unlike `busy`, it is not worth asking again: the
# same request answers the same length. The parent parses an answer whole in the server:
# `uv run python -m devtools.bench_sqlite_access` (2026-11-20, 4 CPUs at a load of 6)
# measured a page-shaped answer's round trip at a median 50 ms for 8 MiB and 196 ms for
# 30 MiB, the parent's peak growing 17 and 53 MiB. The largest page the table bounds
# admit encoded as 5.3 MB (`TABLE_PAGE_CELLS_MAX` in `table_source.py`), so this leaves it
# six times that for escaping while keeping one answer near a tenth of a request's
# deadline and its parse near 60 MiB of the server's memory.
ANSWER_MAX_BYTES: Final = 32 * 1024 * 1024


def _limit_address_space(limit: int) -> None:
    """Bound this process's address space where the platform enforces one (Linux)."""
    if limit <= 0:
        return
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    except (ImportError, ValueError, OSError):
        return


def _limit_heap(limit: int) -> None:
    """Bound SQLite's heap in this whole process (`PRAGMA hard_heap_limit`)."""
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute(f"PRAGMA hard_heap_limit={int(limit)}")
    finally:
        connection.close()


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


def _load_worker_modules(modules: list[list[str]]) -> None:
    """Load each registered worker module (``sqlite_readers.register_worker_module``)
    under its import name. Its parent packages are empty stand-ins, so the module
    reaches nothing of the package but this file and the modules loaded before it."""
    import importlib.util
    import types

    for name, path in modules:
        parts = name.split(".")
        for depth in range(1, len(parts)):
            parent = ".".join(parts[:depth])
            if parent not in sys.modules:
                package = types.ModuleType(parent)
                package.__path__ = []
                sys.modules[parent] = package
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load worker module {name} from {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        if len(parts) > 1:
            setattr(sys.modules[".".join(parts[:-1])], parts[-1], module)


def serve() -> None:
    """A reader process's loop: one JSON request per line on stdin, one answer per line
    on stdout, one at a time, until stdin closes, which is how the parent stops it and
    how a worker whose parent died exits."""
    if len(sys.argv) > 2:
        _limit_address_space(int(sys.argv[2]))
    _limit_heap(HEAP_LIMIT_BYTES)
    if len(sys.argv) > 3:
        _load_worker_modules(json.loads(sys.argv[3]))
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
            response = _handle(request)
        stdout.write(_encode_answer(response) + b"\n")
        stdout.flush()


def _encode_answer(response: dict[str, Any]) -> bytes:
    """*response* as one JSON line's bytes, or a ``too_large`` answer in its place when it
    is longer than :data:`ANSWER_MAX_BYTES`."""
    encoded = json.dumps(response, allow_nan=False, separators=(",", ":")).encode()
    if len(encoded) <= ANSWER_MAX_BYTES:
        return encoded
    refusal = {
        "ok": False,
        "state": "too_large",
        "error": f"The answer was longer than the {ANSWER_MAX_BYTES:,} bytes a reader returns.",
    }
    return json.dumps(refusal, separators=(",", ":")).encode()
