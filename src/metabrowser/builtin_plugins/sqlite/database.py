"""One database as the server reaches it: where its file is, its generation, and its
reader process requests.

The server never connects to a database it does not own (Decision 13 of the tabular-data
plan): every read is a request to a reader process (:mod:`metabrowser.sqlite_readers`),
which runs :mod:`metabrowser.sqlite_access` and this plugin's ``reader.py``, registered
here as a worker module. On a served folder a reader opens the file's real path; on a Git
pin the blob is written once to a private file named by its object id, under
:data:`~metabrowser.sqlite_readers.BLOB_MAX_BYTES`, and read with ``immutable=1``.

A table's address is ``<database>/<segment>``. The segment is the table's name when the
name is nonempty, is not ``.`` or ``..``, holds only ASCII letters, digits, ``_``,
``.``, and ``-``, and does not start with ``~`` or with ``g1-``, the prefix of a Git
path's segments; any other name is ``~`` followed by the hexadecimal of its UTF-8 bytes,
so every name SQLite allows has exactly one segment and every segment one name.
"""

from __future__ import annotations

import re
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from metabrowser.builtin_plugins.sqlite import reader
from metabrowser.capabilities import capabilities_for
from metabrowser.source import ContentRef, get_source_session
from metabrowser.sqlite_access import TOO_LARGE_MESSAGE, SqliteAccessError, sqlite_generation
from metabrowser.sqlite_readers import (
    BLOB_MAX_BYTES,
    reader_pool,
    register_worker_module,
)

READER_MODULE: Final = "metabrowser.builtin_plugins.sqlite.reader"
register_worker_module(READER_MODULE, Path(__file__).with_name("reader.py"))

# What one server process keeps of databases' catalogs and descriptions, keyed by the
# database, its generation, and whether it reads virtual tables, so the schema a page is
# checked against, and its references' targets, cost no request after the first. A description is one object's
# columns, keys, foreign keys, and indexes: the nine-column `users` table of the test
# fixtures (tests/fixtures/sqlite-tables/app.sql) is 1.5 KB of JSON and a table of 200
# columns 21 KB, so a full cache of the widest tables a reader is likely to meet holds a
# few megabytes. The bound is in entries; a catalog is one entry, a list of names.
DESCRIPTION_CACHE_ENTRIES: Final = 256

_SAFE_SEGMENT: Final = re.compile(r"[A-Za-z0-9_.-]+")


def table_segment(name: str) -> str:
    """The address segment of the table named *name*."""
    if name not in ("", ".", "..") and _SAFE_SEGMENT.fullmatch(name) and not name.startswith("g1-"):
        return name
    return "~" + name.encode("utf-8", "surrogatepass").hex()


def segment_name(segment: str) -> str | None:
    """The table name a segment names, or None for one no name encodes to."""
    if segment.startswith("~"):
        try:
            name = bytes.fromhex(segment[1:]).decode("utf-8")
        except ValueError:
            return None
        return name if table_segment(name) == segment else None
    return segment if table_segment(segment) == segment else None


@dataclass(frozen=True, slots=True)
class Database:
    """A database file a reader can open, and how."""

    file: Path
    immutable: bool
    subject: str
    generation: str
    # Whether a virtual table may be queried: never under the untrusted profile, which a
    # pinned revision always runs under. Sent with every request, where the reader
    # refuses, for the whole read, the virtual tables and their shadow tables when false.
    virtual_ok: bool

    def call(self, op: str, args: dict[str, Any], *, deadline: float) -> Any:
        """Ask a reader process for *op* on this database, with a private folder."""
        pool = reader_pool()
        with pool.scratch() as scratch:
            return pool.call(
                op,
                {
                    "path": str(self.file),
                    "scratch": str(scratch),
                    "immutable_content": self.immutable,
                    "virtual_ok": self.virtual_ok,
                    **args,
                },
                deadline=deadline,
                subject=self.subject,
            )


def subject_key() -> str:
    """The subject a reader process serves: one served folder or pin at a time."""
    session = get_source_session()
    return f"{session.subject.kind}:{session.generation}"


def served_database(real: Path, subject: str) -> Database:
    """A database on the served folder at its real path. Raises ``OSError`` when the
    file is gone."""
    return Database(
        file=real,
        immutable=False,
        subject=subject,
        generation=sqlite_generation(real),
        virtual_ok=capabilities_for(pinned_revision=False).active_content,
    )


def pinned_database(ref: ContentRef, data: bytes, subject: str) -> Database:
    """A database in a pinned revision: its blob, written once to a private file."""
    if len(data) > BLOB_MAX_BYTES:
        raise blob_too_large()
    file = reader_pool().blob(ref.fingerprint, lambda: data)
    return _pinned_database(ref, file, subject)


def written_pinned_database(ref: ContentRef, subject: str) -> Database | None:
    """Find the pin's private file before reading its blob from Git again."""
    file = reader_pool().written_blob(ref.fingerprint)
    return _pinned_database(ref, file, subject) if file is not None else None


def _pinned_database(ref: ContentRef, file: Path, subject: str) -> Database:
    generation = re.sub(r"[^A-Za-z0-9_-]", "_", ref.fingerprint) or "0"
    return Database(
        file=file, immutable=True, subject=subject, generation=generation, virtual_ok=False
    )


def blob_too_large(limit: int = BLOB_MAX_BYTES) -> SqliteAccessError:
    """The refusal of a revision's database past *limit* bytes."""
    return SqliteAccessError(
        "unreadable",
        TOO_LARGE_MESSAGE,
        detail=f"This database is larger than the {limit:,} bytes read from a revision.",
    )


class _Cache:
    """A bounded least-recently-used map of request answers."""

    def __init__(self, entries: int) -> None:
        self._entries = entries
        self._items: OrderedDict[tuple[str, ...], Any] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: tuple[str, ...]) -> Any:
        with self._lock:
            if key not in self._items:
                return None
            self._items.move_to_end(key)
            return self._items[key]

    def put(self, key: tuple[str, ...], value: Any) -> None:
        with self._lock:
            self._items[key] = value
            self._items.move_to_end(key)
            while len(self._items) > self._entries:
                self._items.popitem(last=False)


_CACHE: Final = _Cache(DESCRIPTION_CACHE_ENTRIES)


def cached(database: Database, what: str, name: str, *, deadline: float) -> Any:
    """The catalog (*what* ``catalog``) or one object's description (``describe``) of a
    database, from the cache while its generation holds."""
    key = (str(database.file), database.generation, str(database.virtual_ok), what, name)
    found = _CACHE.get(key)
    if found is not None:
        return found
    if what == "catalog":
        value = database.call("sqlite_catalog", {}, deadline=deadline)
    else:
        value = database.call(
            "sqlite_describe",
            {"table": name, "sort_rows": reader.SORT_UNINDEXED_MAX_ROWS},
            deadline=deadline,
        )
        if value is None:
            return None
    _CACHE.put(key, value)
    return value
