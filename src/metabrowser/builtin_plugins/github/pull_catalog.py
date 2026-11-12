"""Private, disposable PR metadata catalog with bounded indexed reads and page writes.

The SQLite database belongs to the GitHub plugin, not a served repository. GET opens
it read-only. A page's rows, counts and resume cursor commit together under the existing
source-alias lock; no network operation runs while that lock is held.

A catalog this release cannot use is one of two things, and a writer tells them apart
before it touches either. One a newer Metabrowser wrote declares it: a schema, checkpoint
schema, or row projection past this release's (:class:`NewerCatalogError`). Several
builds can share one cache, so a writer leaves it as it is and the refresh says to
upgrade; replacing it would have the two builds rebuild each other's catalog page by
page for as long as both run. Anything else, a damaged file, a schema with objects of
its own, or a checkpoint outside the model, is :class:`CatalogUnusableError`, and since
the catalog is disposable a writer replaces it with an empty one under the lock, as a
cached record another schema wrote is fetched again. Readers do neither and answer
nothing. ``tests/test_github_pull_list.py`` pins the shape each version names, so a
change to the tables, the checkpoint, or a row fails there until it raises one.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import sqlite3
import uuid
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, Self, TypedDict

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from metabrowser.builtin_plugins.github.pull_list import ListedRepository, PullListRow, parse_stamp
from metabrowser.builtin_plugins.github.pull_record import ensure_pulls_directory
from metabrowser.cache.locks import source_alias_lock
from metabrowser.cache.paths import (
    MAX_PULL_REQUEST_NUMBER,
    PULL_LIST_NAMES,
    PullListName,
    source_pulls_directory,
)
from metabrowser.home import PrivateStorageError, open_private_file, write_private_file_atomic

log = logging.getLogger(__name__)

# The tables and index, as ``PRAGMA user_version``.
CATALOG_SCHEMA = 1
# The checkpoint's own fields, as the ``schema_version`` CatalogState writes.
CHECKPOINT_SCHEMA = 1
# 2 added each row's head commit, which a cached record and file list are checked against.
CATALOG_PROJECTION = 2
_SIDECARS: Final = ("-journal", "-wal", "-shm")
# SQLite's primary result codes for a file that is not a database or is damaged.
_DAMAGED_CODES: Final = frozenset({sqlite3.SQLITE_CORRUPT, sqlite3.SQLITE_NOTADB})
PAGE_SIZE = 100
MAX_WINDOW = 1000
MAX_CATALOG_MEMBERS = 8
_SEARCH_RESULT_LIMIT = 12
# Production cache reads on a Mac took 3–4 ms for a sparse title match at 1,375 rows
# and 62–69 ms at the 50k candidate limit, including the cutoff for a 100k catalog.
# Recent pulls and numeric queries use the primary key at any catalog size.
_SEARCH_TITLE_ROWS = 50_000
_SEARCH_READ_OPCODES = 500_000

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


class CatalogUnusableError(ValueError):
    """The catalog cannot be used as it is, and nothing in it says a newer release wrote it."""


class NewerCatalogError(ValueError):
    """A newer Metabrowser wrote the catalog; ``str()`` says what it declares."""


def failure_line(exc: BaseException) -> str:
    """*exc* and the chain of causes under it, on one line, for a server log.

    One line, because a log line is what a transcript drops: a traceback or a
    validation error's own lines would be printed into it.
    """

    links: list[str] = []
    current: BaseException | None = exc
    while current is not None and len(links) < 4:
        links.append(f"{type(current).__name__}: {' '.join(str(current).split())}")
        current = current.__cause__
    return " <- ".join(links)


def _refuse_newer(what: str, found: object, supported: int) -> None:
    if type(found) is int and found > supported:
        raise NewerCatalogError(f"{what} {found}, where this release reads up to {supported}")


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
    # When the running delta scan asked for its first page, which its fetched_at becomes:
    # a row changed later can sit on a page already read.
    delta_started_at: str | None = None
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
        for stamp in (
            self.fetched_at,
            self.count_at,
            self.watermark,
            self.delta_watermark,
            self.delta_started_at,
        ):
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
        for suffix in _SIDECARS:
            try:
                side = open_private_file(home, relative + suffix, flags, shared="refuse")
            except FileNotFoundError:
                continue
            else:
                os.close(side)
        header = os.pread(fd, 100, 0)
        if header and (not header.startswith(b"SQLite format 3\x00") or len(header) < 100):
            raise CatalogUnusableError("the catalog is not an SQLite database")
        if header and header[18:20] != b"\x01\x01":
            # The header holds ``user_version`` too, so a newer schema is known unopened.
            _refuse_newer("catalog schema", int.from_bytes(header[60:64]), CATALOG_SCHEMA)
            raise CatalogUnusableError("the catalog is not a rollback-journal database")
        if not header and not write:
            raise CatalogUnusableError("the catalog is empty")
        return fd, os.fstat(fd)
    except BaseException:
        os.close(fd)
        raise


@contextlib.contextmanager
def _database(
    home: Path, slug: str, *, write: bool = False, read_opcodes: int = 100_000
) -> Generator[sqlite3.Connection]:
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
                steps += 1000
                return int(steps > read_opcodes)

            connection.set_progress_handler(bounded_read, 1000)
        yield connection
    finally:
        if connection is not None:
            connection.close()
        os.close(fd)


def _state(db: sqlite3.Connection) -> CatalogState | None:
    """The checkpoint, or ``None`` for none, after admitting the exact schema.

    Raises :class:`NewerCatalogError` for a version past this release's and
    :class:`CatalogUnusableError` for anything else this release cannot use.
    """
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version != CATALOG_SCHEMA:
        _refuse_newer("catalog schema", version, CATALOG_SCHEMA)
        raise CatalogUnusableError("unknown catalog schema")
    schema = db.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_schema LIMIT ?", (len(_SCHEMA) + 1,)
    ).fetchall()
    if set(schema) != set(_SCHEMA):
        raise CatalogUnusableError("unsupported catalog schema")
    row = db.execute("SELECT value FROM checkpoint WHERE id=1").fetchone()
    if row is None:
        return None
    try:
        return CatalogState.model_validate_json(row[0])
    except ValidationError as exc:
        _refuse_newer_checkpoint(row[0])
        raise CatalogUnusableError("the catalog's checkpoint is outside its model") from exc


def _refuse_newer_checkpoint(value: object) -> None:
    """Raise :class:`NewerCatalogError` when a checkpoint declares a newer version.

    Only the two version fields are read, so a checkpoint is judged by what it says it is
    and not by fields this release has never seen. *value* is at most the connection's
    32 KiB value limit.
    """
    try:
        declared = json.loads(value) if isinstance(value, str) else None
    except ValueError:
        return
    if isinstance(declared, dict):
        fields: dict[str, object] = declared  # pyright: ignore[reportUnknownVariableType]
        _refuse_newer("checkpoint schema", fields.get("schema_version"), CHECKPOINT_SCHEMA)
        _refuse_newer("row projection", fields.get("projection_version"), CATALOG_PROJECTION)


def newer_catalog(home: Path, slug: str) -> str | None:
    """What a newer Metabrowser's catalog here declares, or ``None``. Blocking and bounded.

    It reads as :func:`read_catalog` does, creating and changing nothing, so a refresh can
    stop before it asks GitHub for a page it could not publish.
    """
    try:
        with _database(home, slug) as db:
            _state(db)
    except NewerCatalogError as exc:
        return str(exc)
    except (FileNotFoundError, PrivateStorageError, OSError, sqlite3.Error, ValueError):
        return None
    return None


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


class PullSearchRow(TypedDict):
    number: int
    title: str
    state: Literal["open", "closed", "merged", "draft"]


class PullSearchEnvelope(TypedDict):
    rows: list[PullSearchRow]
    complete: bool
    limited: bool
    truncated: bool


def _search_numbers(
    db: sqlite3.Connection, digits: str, *, include_prefix: bool
) -> list[tuple[str]]:
    canonical = digits.lstrip("0")
    max_width = len(str(MAX_PULL_REQUEST_NUMBER))
    if not canonical or len(canonical) > max_width:
        return []
    number = int(canonical)
    if number > MAX_PULL_REQUEST_NUMBER:
        return []
    rows: list[tuple[str]] = db.execute(
        "SELECT body FROM pulls WHERE number = ?", (number,)
    ).fetchall()
    if include_prefix and digits == canonical:
        # A decimal prefix gives one disjoint primary-key range per additional
        # digit. Longer numbers sort first and the exact number stays at the top.
        for width in range(max_width - len(canonical), 0, -1):
            scale = 10**width
            remaining = _SEARCH_RESULT_LIMIT + 1 - len(rows)
            rows.extend(
                db.execute(
                    "SELECT body FROM pulls WHERE number BETWEEN ? AND ? "
                    "ORDER BY number DESC LIMIT ?",
                    (
                        number * scale,
                        min((number + 1) * scale - 1, MAX_PULL_REQUEST_NUMBER),
                        remaining,
                    ),
                )
            )
            if len(rows) > _SEARCH_RESULT_LIMIT:
                break
    return rows


def catalog_search(repository: ListedRepository | None, query: str) -> PullSearchEnvelope:
    """Read recent pulls or search local metadata across open and closed PRs."""
    empty = PullSearchEnvelope(rows=[], complete=False, limited=False, truncated=False)
    if repository is None:
        return empty
    explicit = query.startswith("#")
    text = query[1:].strip() if explicit else query
    try:
        with _database(repository.home, repository.slug, read_opcodes=_SEARCH_READ_OPCODES) as db:
            db.execute("BEGIN")
            state = _state(db)
            if state is None or state.source != repository.source:
                return empty
            complete = state.done["all"]
            limited = False
            matches: list[tuple[str]] | sqlite3.Cursor
            if text.isascii() and text.isdecimal():
                matches = _search_numbers(db, text, include_prefix=explicit)
            elif not text:
                matches = db.execute(
                    "SELECT body FROM pulls ORDER BY number DESC LIMIT ?",
                    (_SEARCH_RESULT_LIMIT + 1,),
                )
            else:
                terms = tuple(dict.fromkeys(text.casefold().split()))

                def title_matches(title: object) -> bool:
                    if not isinstance(title, str):
                        return False
                    folded = title.casefold()
                    return all(term in folded for term in terms)

                db.create_function("title_matches", 1, title_matches, deterministic=True)
                limited = state.cached["all"] > _SEARCH_TITLE_ROWS
                oldest = 1
                if limited:
                    cutoff = db.execute(
                        "SELECT number FROM pulls ORDER BY number DESC LIMIT 1 OFFSET ?",
                        (_SEARCH_TITLE_ROWS - 1,),
                    ).fetchone()
                    if cutoff is not None:
                        oldest = cutoff[0]
                matches = db.execute(
                    "SELECT body FROM pulls WHERE number >= ? "
                    "AND title_matches(json_extract(body, '$.title')) "
                    "ORDER BY number DESC LIMIT ?",
                    (oldest, _SEARCH_RESULT_LIMIT + 1),
                )
            rows: list[PullSearchRow] = []
            for (body,) in matches:
                row = PullListRow.model_validate_json(body)
                rows.append(
                    {
                        "number": row.number,
                        "title": row.title,
                        "state": "merged"
                        if row.merged
                        else "draft"
                        if row.state == "open" and row.draft
                        else row.state,
                    }
                )
            return {
                "rows": rows[:_SEARCH_RESULT_LIMIT],
                "complete": complete,
                "limited": limited,
                "truncated": len(rows) > _SEARCH_RESULT_LIMIT,
            }
    except (FileNotFoundError, PrivateStorageError, OSError, sqlite3.Error, ValueError):
        return empty


@dataclass(frozen=True, slots=True)
class CatalogMember:
    updated_at: str
    fingerprint: bytes


def catalog_members(
    home: Path, slug: str, name: PullListName, numbers: tuple[int, ...]
) -> tuple[CatalogState | None, dict[int, CatalogMember]]:
    """Fingerprint the bounded summaries found by number in one checkpoint snapshot."""
    if not numbers or len(numbers) > MAX_CATALOG_MEMBERS or name not in PULL_LIST_NAMES:
        raise ValueError("invalid catalog membership request")
    try:
        with _database(home, slug) as db:
            db.execute("BEGIN")
            state = _state(db)
            placeholders = ",".join("?" for _ in numbers)
            query = f"SELECT number,updated_at,body FROM pulls WHERE number IN ({placeholders})"
            values: tuple[int | str, ...] = numbers
            if name != "all":
                query += " AND state = ?"
                values = (*numbers, name)
            members: dict[int, CatalogMember] = {}
            for number, stamp, summary in db.execute(query, values):
                if not isinstance(stamp, str) or not isinstance(summary, str):
                    return None, {}
                parse_stamp(stamp)
                members[number] = CatalogMember(stamp, hashlib.sha256(summary.encode()).digest())
            return state, members
    except (FileNotFoundError, PrivateStorageError, OSError, sqlite3.Error, ValueError):
        return None, {}


def catalog_titles(
    repository: ListedRepository, reader: str, numbers: tuple[int, ...]
) -> dict[int, str]:
    """Read one indexed title batch, using the catalog's existing window bound."""
    if not numbers or len(numbers) > MAX_WINDOW:
        raise ValueError("invalid catalog title request")
    try:
        with _database(repository.home, repository.slug) as db:
            db.execute("BEGIN")
            state = _state(db)
            if state is None or (state.source, state.reader) != (repository.source, reader):
                return {}
            placeholders = ",".join("?" for _ in numbers)
            rows = db.execute(
                f"SELECT number,body FROM pulls WHERE number IN ({placeholders})", numbers
            )
            titles: dict[int, str] = {}
            for number, body in rows:
                row = PullListRow.model_validate_json(body)
                if row.number != number:
                    return {}
                titles[number] = row.title
            return titles
    except (FileNotFoundError, PrivateStorageError, OSError, sqlite3.Error, ValueError):
        return {}


def catalog_member(
    home: Path, slug: str, number: int
) -> tuple[CatalogState | None, PullListRow | None]:
    """The checkpoint and one number's row, read in one transaction. Blocking and bounded.

    A record is checked against both together, so a scan that publishes between two reads
    cannot pair one scan's row with another's time. Every ``GET pull`` reads it: on the
    fixture's 102-row catalog it took a median 1.09 ms and at most 1.94 ms in 200 runs,
    at a load average of 23 (2026-11-11), half of reading the two apart.
    """
    try:
        with _database(home, slug) as db:
            db.execute("BEGIN")
            state = _state(db)
            row = db.execute("SELECT body FROM pulls WHERE number=?", (number,)).fetchone()
            return state, PullListRow.model_validate_json(row[0]) if row else None
    except (FileNotFoundError, PrivateStorageError, OSError, sqlite3.Error, ValueError):
        return None, None


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
    write_private_file_atomic(repository.home, _relative(repository.slug), _empty_catalog())


def _empty_catalog() -> bytes:
    with sqlite3.connect(":memory:") as db:
        db.executescript(
            ";".join(entry[3] for entry in _SCHEMA) + f";PRAGMA user_version={CATALOG_SCHEMA};"
        )
        return db.serialize()


def _replace(repository: ListedRepository) -> None:
    """Publish an empty catalog over one that cannot be used. Under the alias lock only.

    Its sidecars go first: SQLite would apply a journal left beside the old file to the
    new one. The old file is replaced, not written, so none of its SQL runs.
    """
    relative = _relative(repository.slug)
    for suffix in _SIDECARS:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(repository.home / (relative + suffix))
    write_private_file_atomic(repository.home, relative, _empty_catalog())


def publish_page(
    repository: ListedRepository,
    expected: CatalogState | None,
    proposed: CatalogState,
    rows: tuple[PullListRow, ...],
) -> bool:
    """Commit one page and checkpoint, or reject a superseded publisher. Blocking.

    The caller uses run_lock_section, so a cancelled lock waiter cannot publish later.
    An account/repository change replaces the disposable catalog in one transaction.
    A catalog this release cannot use is replaced with an empty one first, and logged; a
    publisher that expected a checkpoint is then superseded, and rereads. A newer
    release's catalog raises :class:`NewerCatalogError` and is left as it is.
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
        try:
            return _commit(repository, expected, proposed, rows)
        except CatalogUnusableError as exc:
            log.warning(
                "replacing the pull-request catalog of %s, which this release cannot use "
                "(%s); its list is fetched again",
                repository.source,
                failure_line(exc),
            )
            _replace(repository)
        return _commit(repository, expected, proposed, rows)


def _commit(
    repository: ListedRepository,
    expected: CatalogState | None,
    proposed: CatalogState,
    rows: tuple[PullListRow, ...],
) -> bool:
    """One page's transaction. A file SQLite finds damaged is :class:`CatalogUnusableError`."""

    try:
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
    except sqlite3.DatabaseError as exc:
        # Extended result codes keep the primary code in their low byte.
        if exc.sqlite_errorcode & 0xFF in _DAMAGED_CODES:
            raise CatalogUnusableError(f"the catalog is damaged: {exc}") from exc
        raise
