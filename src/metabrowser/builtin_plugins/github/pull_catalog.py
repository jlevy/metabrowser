"""Private, disposable PR metadata catalog with bounded indexed reads and page writes.

The SQLite database belongs to the GitHub plugin, not a served repository. GET opens
it read-only. A page's rows, counts and resume cursor commit together under the existing
source-alias lock; no network operation runs while that lock is held.
"""

from __future__ import annotations

import contextlib
import os
import sqlite3
import uuid
from collections.abc import Generator
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from metabrowser.builtin_plugins.github.pull_list import ListedRepository, PullListRow, parse_stamp
from metabrowser.builtin_plugins.github.pull_record import ensure_pulls_directory
from metabrowser.cache.locks import source_alias_lock
from metabrowser.cache.paths import PULL_LIST_NAMES, PullListName, source_pulls_directory
from metabrowser.home import PrivateStorageError, open_private_file, write_private_file_atomic

CATALOG_SCHEMA = 1
CATALOG_PROJECTION = 1
PAGE_SIZE = 100
MAX_WINDOW = 1000

# One exact disposable schema: no user triggers, views, or missing query indexes.
# Initialization and admission share the same SQL so neither can drift independently.
_SCHEMA = (
    (
        "table",
        "checkpoint",
        "checkpoint",
        "CREATE TABLE checkpoint(id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL)",
    ),
    (
        "table",
        "pulls",
        "pulls",
        "CREATE TABLE pulls(number INTEGER PRIMARY KEY, state TEXT NOT NULL, updated_at TEXT NOT NULL, body TEXT NOT NULL)",
    ),
    (
        "index",
        "pulls_state_number",
        "pulls",
        "CREATE INDEX pulls_state_number ON pulls(state, number DESC)",
    ),
)


class CatalogState(BaseModel):
    """Constant-size checkpoint; neither rows nor per-page history live here."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1] = 1
    # The ALL scan uses this projection; done["all"] separately records completion.
    projection_version: int = Field(default=0, ge=0, le=CATALOG_PROJECTION)
    source: str
    repository_id: str
    reader: str
    epoch: str = Field(default_factory=lambda: uuid.uuid4().hex)
    revision: int = 0
    generations: dict[str, int] = Field(default_factory=lambda: dict.fromkeys(PULL_LIST_NAMES, 0))
    totals: dict[str, int] = Field(default_factory=lambda: dict.fromkeys(PULL_LIST_NAMES, 0))
    cached: dict[str, int] = Field(default_factory=lambda: dict.fromkeys(PULL_LIST_NAMES, 0))
    cursors: dict[str, str | None] = Field(default_factory=lambda: dict.fromkeys(PULL_LIST_NAMES))
    covered: dict[str, int] = Field(default_factory=lambda: dict.fromkeys(PULL_LIST_NAMES, 0))
    done: dict[str, bool] = Field(default_factory=lambda: dict.fromkeys(PULL_LIST_NAMES, False))
    fetched_at: str
    count_at: str
    watermark: str | None = None
    delta_cursor: str | None = None
    delta_watermark: str | None = None
    delta_started: bool = False
    truncated: bool = False

    @model_validator(mode="after")
    def _valid_checkpoint(self) -> Self:
        for values in (self.generations, self.totals, self.cached, self.covered):
            if set(values) != set(PULL_LIST_NAMES) or any(value < 0 for value in values.values()):
                raise ValueError("invalid catalog counts")
        if set(self.cursors) != set(PULL_LIST_NAMES) or set(self.done) != set(PULL_LIST_NAMES):
            raise ValueError("invalid catalog scans")
        for cursor in (*self.cursors.values(), self.delta_cursor):
            if cursor is not None and not 1 <= len(cursor) <= 1024:
                raise ValueError("invalid catalog cursor")
        if self.revision < 0 or not self.epoch or len(self.epoch) > 64:
            raise ValueError("invalid catalog revision")
        if not self.source.startswith("https://github.com/") or not self.reader.startswith("gh:"):
            raise ValueError("invalid catalog identity")
        if not 1 <= len(self.repository_id) <= 256:
            raise ValueError("invalid repository identity")
        for stamp in (self.fetched_at, self.count_at, self.watermark, self.delta_watermark):
            if stamp is not None:
                parse_stamp(stamp)
        return self

    def generation(self, name: PullListName) -> str:
        return f"{self.epoch}:{self.generations[name]}"


def _relative(slug: str) -> str:
    return f"{source_pulls_directory(slug)}/catalog.sqlite3"


def _admit(home: Path, relative: str, *, write: bool) -> tuple[int, os.stat_result]:
    flags = os.O_RDWR if write else os.O_RDONLY
    fd = open_private_file(home, relative, flags, shared="refuse")
    try:
        for suffix in ("-journal", "-wal", "-shm"):
            try:
                side = open_private_file(home, relative + suffix, flags, shared="refuse")
            except FileNotFoundError:
                continue
            else:
                os.close(side)
        header = os.pread(fd, 100, 0)
        if header and (
            not header.startswith(b"SQLite format 3\x00")
            or len(header) < 100
            or header[18:20] != b"\x01\x01"
        ):
            raise ValueError("the catalog is not a supported rollback-journal database")
        if not header and not write:
            raise ValueError("the catalog is empty")
        return fd, os.fstat(fd)
    except BaseException:
        os.close(fd)
        raise


@contextlib.contextmanager
def _database(home: Path, slug: str, *, write: bool = False) -> Generator[sqlite3.Connection]:
    relative = _relative(slug)
    fd, held = _admit(home, relative, write=write)
    connection: sqlite3.Connection | None = None
    try:
        uri = (home / relative).as_uri() + ("?mode=rw" if write else "?mode=ro")
        connection = sqlite3.connect(uri, uri=True, timeout=0.25)
        current = os.lstat(home / relative)
        if (current.st_dev, current.st_ino) != (held.st_dev, held.st_ino):
            raise OSError("the catalog changed while it was opened")
        connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 32 * 1024)
        connection.execute("PRAGMA trusted_schema=OFF")
        connection.execute("PRAGMA cache_size=-1024")
        if not write:
            connection.execute("PRAGMA query_only=ON")
            steps = 0

            def bounded_read() -> int:
                nonlocal steps
                steps += 1
                return int(steps > 100)

            connection.set_progress_handler(bounded_read, 1000)
        yield connection
    finally:
        if connection is not None:
            connection.close()
        os.close(fd)


def _state(db: sqlite3.Connection) -> CatalogState | None:
    if db.execute("PRAGMA user_version").fetchone()[0] != CATALOG_SCHEMA:
        raise ValueError("unknown catalog schema")
    schema = db.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_schema LIMIT ?", (len(_SCHEMA) + 1,)
    ).fetchall()
    if set(schema) != set(_SCHEMA):
        raise ValueError("unsupported catalog schema")
    row = db.execute("SELECT value FROM checkpoint WHERE id=1").fetchone()
    return CatalogState.model_validate_json(row[0]) if row else None


def read_catalog(home: Path, slug: str) -> CatalogState | None:
    """Read a checkpoint without creating files or changing permissions."""
    try:
        with _database(home, slug) as db:
            return _state(db)
    except (FileNotFoundError, PrivateStorageError, OSError, sqlite3.Error, ValueError):
        return None


def catalog_window(
    home: Path, slug: str, name: PullListName, *, limit: int, after: int | None = None
) -> tuple[CatalogState | None, list[dict[str, Any]], int | None]:
    """Read one consistent indexed window, bounded independently of repository size."""
    if not 0 <= limit <= MAX_WINDOW or name not in PULL_LIST_NAMES:
        raise ValueError("invalid catalog window")
    try:
        with _database(home, slug) as db:
            db.execute("BEGIN")
            state = _state(db)
            where = ["number < ?"] if after is not None else []
            values: list[Any] = [after] if after is not None else []
            if name != "all":
                where.append("state = ?")
                values.append(name)
            clause = " WHERE " + " AND ".join(where) if where else ""
            cursor = db.execute(
                "SELECT body FROM pulls" + clause + " ORDER BY number DESC LIMIT ?",
                [*values, limit + 1 if limit else 0],
            )
            result: list[PullListRow] = []
            for row in cursor:
                result.append(PullListRow.model_validate_json(row[0]))
            rows = result[:limit]
            wire = [row.model_dump(mode="json") | {"merged": row.merged} for row in rows]
            return state, wire, rows[-1].number if len(result) > limit and rows else None
    except (FileNotFoundError, PrivateStorageError, OSError, sqlite3.Error, ValueError):
        return None, [], None


def catalog_row(home: Path, slug: str, number: int) -> PullListRow | None:
    try:
        with _database(home, slug) as db:
            _state(db)
            row = db.execute("SELECT body FROM pulls WHERE number=?", (number,)).fetchone()
            return PullListRow.model_validate_json(row[0]) if row else None
    except (FileNotFoundError, PrivateStorageError, OSError, sqlite3.Error, ValueError):
        return None


def _initialize(repository: ListedRepository) -> None:
    ensure_pulls_directory(repository.home, repository.slug)
    try:
        fd = open_private_file(
            repository.home, _relative(repository.slug), os.O_RDONLY, shared="refuse"
        )
    except FileNotFoundError:
        pass
    else:
        try:
            if os.fstat(fd).st_size:
                return
        finally:
            os.close(fd)
    # Publish a complete initialized database atomically, never a visible empty file.
    with sqlite3.connect(":memory:") as db:
        db.executescript(";".join(entry[3] for entry in _SCHEMA) + ";PRAGMA user_version=1;")
        data = db.serialize()
    write_private_file_atomic(repository.home, _relative(repository.slug), data)


def publish_page(
    repository: ListedRepository,
    expected: CatalogState | None,
    proposed: CatalogState,
    rows: tuple[PullListRow, ...],
) -> bool:
    """Commit one page and checkpoint, or reject a superseded publisher. Blocking.

    The caller uses run_lock_section, so a cancelled lock waiter cannot publish later.
    An account/repository change replaces the disposable catalog in one transaction.
    """
    if proposed.source != repository.source:
        raise ValueError("a catalog publication belongs to its source")
    if len(rows) > PAGE_SIZE:
        raise ValueError("a catalog transaction contains at most one page")
    # No orphan source is created by a failed claim.
    source = repository.home / f"sources/{repository.slug}/source.yml"
    if not source.is_file() or source.is_symlink():
        raise FileNotFoundError("no source is published under this slug")
    with source_alias_lock(repository.home, repository.slug):
        _initialize(repository)
        with _database(repository.home, repository.slug, write=True) as db, db:
            db.execute("BEGIN IMMEDIATE")
            current = _state(db)
            current_key = (current.epoch, current.revision) if current else None
            expected_key = (expected.epoch, expected.revision) if expected else None
            if current_key != expected_key:
                return False
            reset = current is None or (current.reader, current.repository_id, current.source) != (
                proposed.reader,
                proposed.repository_id,
                proposed.source,
            )
            if reset:
                db.execute("DELETE FROM pulls")
                counts = dict.fromkeys(PULL_LIST_NAMES, 0)
                generations = dict.fromkeys(PULL_LIST_NAMES, 0)
            else:
                assert current is not None
                counts = dict(current.cached)
                generations = dict(current.generations)
            minima = {
                name: db.execute(
                    "SELECT MIN(number) FROM pulls" + (" WHERE state=?" if name != "all" else ""),
                    (name,) if name != "all" else (),
                ).fetchone()[0]
                for name in PULL_LIST_NAMES
            }
            changed: set[PullListName] = set()
            for row in rows:
                body = row.model_dump_json()
                old = db.execute(
                    "SELECT state,updated_at,body FROM pulls WHERE number=?", (row.number,)
                ).fetchone()
                if old and (old[1] > row.updated_at or old[2] == body):
                    continue
                if old:
                    counts[old[0]] -= 1
                    changed.update(("all", old[0], row.state))
                else:
                    counts["all"] += 1
                    for name in ("all", row.state):
                        if not reset and (minima[name] is None or row.number > minima[name]):
                            changed.add(name)
                counts[row.state] += 1
                db.execute(
                    "INSERT INTO pulls VALUES(?,?,?,?) ON CONFLICT(number) DO UPDATE SET "
                    "state=excluded.state,updated_at=excluded.updated_at,body=excluded.body",
                    (row.number, row.state, row.updated_at, body),
                )
            for name in changed:
                generations[name] += 1
            final = proposed.model_copy(
                update={
                    "cached": counts,
                    "generations": generations,
                    "revision": (current.revision if current else 0) + 1,
                }
            )
            db.execute(
                "INSERT INTO checkpoint VALUES(1,?) ON CONFLICT(id) DO UPDATE SET value=excluded.value",
                (final.model_dump_json(),),
            )
            return True
