"""The guest access helper's rules that need no owner process: the access table row by
row, the connection settings and authorizer, error states, and the reader pool's
subjects. The scenarios with real owners are ``tests/test_sqlite_guest_access.py``."""

from __future__ import annotations

import os
import sqlite3
import time
from dataclasses import replace
from pathlib import Path

import pytest

from metabrowser import sqlite_access
from metabrowser.sqlite_access import (
    FileState,
    Observation,
    SqliteAccessError,
    choose,
    library_report,
    observe,
    read,
    sqlite_generation,
)
from metabrowser.sqlite_readers import ReaderPool


def _database(path: Path, *, wal: bool = False) -> Path:
    connection = sqlite3.connect(path)
    if wal:
        connection.execute("PRAGMA journal_mode=wal")
    connection.executescript(
        "CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT);"
        "INSERT INTO t(name) VALUES ('ada'), ('bob');"
        "CREATE VIEW shout AS SELECT upper(name) AS name FROM t;"
    )
    connection.close()
    then = time.time() - 60
    os.utime(path, (then, then))
    return path


def _observation(**changes: object) -> Observation:
    header = bytearray(sqlite_access.SQLITE_MAGIC + bytes(84))
    header[16:18] = (4096).to_bytes(2)
    header[18:20] = b"\x01\x01"
    base = Observation(
        path=Path("/nowhere/app.db"),
        main=FileState(1, 2, 8192, 0, 1),
        header=bytes(header),
        journal=None,
        journal_live=False,
        wal=None,
        wal_header=b"",
        shm=None,
        observed_ns=10**18,
    )
    return replace(base, **changes)  # type: ignore[arg-type]


def _wal_header() -> bytes:
    header = bytearray(_observation().header)
    header[18:20] = b"\x02\x02"
    return bytes(header)


def _deadline() -> float:
    return time.monotonic() + 2


# ── The access table ───────────────────────────────────────────


def test_access_table_rows() -> None:
    shm = FileState(1, 9, 32768, 0, 1)
    frames = FileState(1, 8, 32 + 3 * (24 + 4096), 0, 1)
    empty = FileState(1, 8, 0, 0, 1)

    def plan(**changes: object) -> tuple[str, str] | None:
        chosen = choose(_observation(**changes), immutable_content=False, copy_failures=0)
        return None if chosen is None else (chosen.mode, chosen.state)

    assert plan(main=FileState(1, 2, 8192, 0, 2)) == ("private_copy", "another_name")
    assert plan() == ("immutable", "current")
    assert plan(journal_live=True) is None
    assert plan(header=_wal_header()) == ("immutable", "current")
    assert plan(header=_wal_header(), wal=empty) == ("immutable", "current")
    assert plan(header=_wal_header(), wal=frames, shm=shm) == ("read_only", "current")
    assert plan(header=_wal_header(), wal=frames) == ("private_copy", "current")
    huge = FileState(1, 8, sqlite_access.COPY_MAX_BYTES + 1, 0, 1)
    assert plan(header=_wal_header(), wal=huge) == ("immutable", "without_log")
    many_names_huge = FileState(1, 2, sqlite_access.COPY_MAX_BYTES + 1, 0, 3)
    assert plan(main=many_names_huge) == ("immutable", "another_name")
    pinned = choose(_observation(header=_wal_header()), immutable_content=True, copy_failures=0)
    assert pinned is not None and (pinned.mode, pinned.state) == ("immutable", "current")
    assert "without its log" in pinned.reason


def test_copy_that_fails_validation_twice_reads_the_main_file_alone() -> None:
    frames = FileState(1, 8, 32 + 24 + 4096, 0, 1)
    obs = _observation(header=_wal_header(), wal=frames)
    chosen = choose(obs, immutable_content=False, copy_failures=sqlite_access.COPY_ATTEMPTS)
    assert chosen is not None and (chosen.mode, chosen.state) == ("immutable", "without_log")


def test_a_newer_file_format_is_unsupported() -> None:
    header = bytearray(_observation().header)
    header[19] = 3
    with pytest.raises(SqliteAccessError) as caught:
        choose(_observation(header=bytes(header)), immutable_content=False, copy_failures=0)
    assert caught.value.state == "unsupported"


def test_validation_compares_counter_log_and_journal() -> None:
    before = _observation()
    assert before.unchanged(_observation())
    counter = bytearray(before.header)
    counter[24:28] = (7).to_bytes(4)
    assert not before.unchanged(_observation(header=bytes(counter)))
    assert not before.unchanged(_observation(journal_live=True))
    assert not before.unchanged(_observation(wal=FileState(1, 8, 0, 0, 1)))
    assert not before.unchanged(_observation(main=FileState(1, 3, 8192, 0, 1)))


def test_racy_applies_to_write_ahead_log_databases_only() -> None:
    now = 10**18
    fresh = FileState(1, 2, 8192, now - 1000, 1)
    assert _observation(header=_wal_header(), main=fresh, observed_ns=now).racy()
    assert not _observation(main=fresh, observed_ns=now).racy()
    aged = FileState(1, 2, 8192, now - 2 * 10**9, 1)
    assert not _observation(header=_wal_header(), main=aged, observed_ns=now).racy()


# ── Files and states ───────────────────────────────────────────


def test_a_file_that_is_not_sqlite(tmp_path: Path) -> None:
    (tmp_path / "fake.db").write_bytes(b"not a database\x00" * 10)
    with pytest.raises(SqliteAccessError) as caught:
        observe(tmp_path / "fake.db")
    assert caught.value.state == "not_sqlite"


def test_a_fifo_is_never_opened(tmp_path: Path) -> None:
    os.mkfifo(tmp_path / "pipe.db")
    with pytest.raises(SqliteAccessError) as caught:
        observe(tmp_path / "pipe.db")
    assert caught.value.state == "unreadable"


def test_a_missing_file_is_unreadable(tmp_path: Path) -> None:
    with pytest.raises(SqliteAccessError) as caught:
        read(tmp_path / "gone.db", lambda c: None, deadline=_deadline(), scratch=tmp_path)
    assert caught.value.state == "unreadable"


def test_a_damaged_database_is_damaged(tmp_path: Path) -> None:
    db = _database(tmp_path / "app.db")
    data = bytearray(db.read_bytes())
    data[4096:8192] = b"\xff" * 4096
    db.write_bytes(bytes(data))
    os.utime(db, (time.time() - 60, time.time() - 60))
    with pytest.raises(SqliteAccessError) as caught:
        read(
            db,
            lambda c: c.execute("SELECT count(*) FROM t").fetchall(),
            deadline=_deadline(),
            scratch=tmp_path,
        )
    assert caught.value.state == "damaged"


def test_generation_is_stable_and_follows_the_file(tmp_path: Path) -> None:
    db = _database(tmp_path / "app.db")
    first = sqlite_generation(db)
    assert sqlite_generation(db) == first
    connection = sqlite3.connect(db)
    connection.execute("INSERT INTO t(name) VALUES ('cy')")
    connection.commit()
    connection.close()
    assert sqlite_generation(db) != first


def test_library_report_names_the_minimum() -> None:
    report = library_report()
    assert report["minimum"] == "3.43.0"
    versions = [entry["version"] for entry in report["versions"]]
    assert "3.43.0" in versions
    assert report["meets_minimum"] == (sqlite_access.library_version() >= (3, 43, 0))


# ── Connection settings and the authorizer ─────────────────────


def _run(db: Path, sql: str, scratch: Path) -> object:
    return read(db, lambda c: c.execute(sql).fetchall(), deadline=_deadline(), scratch=scratch)[0]


def test_settings_are_applied(tmp_path: Path) -> None:
    db = _database(tmp_path / "app.db")

    def settings(connection: sqlite3.Connection) -> tuple[object, ...]:
        connection.set_authorizer(None)
        return (*tuple(connection.execute(f"PRAGMA {name}").fetchone()[0] for name in ("query_only", "trusted_schema", "cell_size_check", "mmap_size")), connection.getlimit(sqlite3.SQLITE_LIMIT_LENGTH), connection.getlimit(sqlite3.SQLITE_LIMIT_ATTACHED), connection.getconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE))

    value, _ = read(db, settings, deadline=_deadline(), scratch=tmp_path)
    assert value == (1, 0, 1, 0, sqlite_access.VALUE_MAX_BYTES, 0, True)


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO t(name) VALUES ('x')",
        "ATTACH DATABASE ':memory:' AS other",
        "SELECT upper(name) FROM t",
        "PRAGMA user_version = 5",
        "PRAGMA writable_schema",
        "CREATE TEMP TABLE scratch(x)",
    ],
)
def test_the_authorizer_refuses_all_but_reads(tmp_path: Path, sql: str) -> None:
    db = _database(tmp_path / "app.db")
    with pytest.raises(SqliteAccessError) as caught:
        _run(db, sql, tmp_path)
    assert caught.value.state == "refused"


def test_the_authorizer_admits_reads_and_functions_inside_views(tmp_path: Path) -> None:
    db = _database(tmp_path / "app.db")
    assert _run(db, "SELECT name FROM shout ORDER BY name", tmp_path) == [("ADA",), ("BOB",)]
    assert _run(db, "SELECT count(*) FROM t", tmp_path) == [(2,)]
    assert _run(db, "PRAGMA page_size", tmp_path) == [(4096,)]


def test_the_budget_interrupts_a_runaway_view(tmp_path: Path) -> None:
    db = tmp_path / "app.db"
    connection = sqlite3.connect(db)
    connection.execute(
        "CREATE VIEW forever AS WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i+1 FROM n) "
        "SELECT count(*) FROM n"
    )
    connection.close()
    os.utime(db, (time.time() - 60, time.time() - 60))
    started = time.monotonic()
    with pytest.raises(SqliteAccessError) as caught:
        read(
            db,
            lambda c: c.execute("SELECT * FROM forever").fetchall(),
            deadline=time.monotonic() + 0.5,
            scratch=tmp_path,
        )
    assert caught.value.state == "busy"
    assert time.monotonic() - started < 2


# ── The reader pool ────────────────────────────────────────────


def test_a_worker_serves_one_subject(tmp_path: Path) -> None:
    db = _database(tmp_path / "app.db")
    pool = ReaderPool(size=1, temporary_root=tmp_path)
    try:
        for subject in ("first", "first", "second"):
            with pool.scratch() as scratch:
                answer = pool.call(
                    "info",
                    {"path": str(db), "scratch": str(scratch)},
                    deadline=_deadline(),
                    subject=subject,
                )
            assert answer["database"]["objects"] == {"table": 1, "view": 1}
        assert pool.started == 2
    finally:
        pool.close()


def test_a_full_queue_is_busy(tmp_path: Path) -> None:
    pool = ReaderPool(size=1, queue_max=0, temporary_root=tmp_path)
    try:
        with pytest.raises(SqliteAccessError) as caught:
            pool.call("ping", {}, deadline=_deadline(), subject="s")
        assert caught.value.state == "busy"
    finally:
        pool.close()


def test_a_worker_loads_only_the_access_module(tmp_path: Path) -> None:
    pool = ReaderPool(size=1, temporary_root=tmp_path)
    try:
        pool.call("ping", {}, deadline=_deadline(), subject="s")
        [pid] = pool.workers()
        environ = Path(f"/proc/{pid}/cmdline")
        if environ.exists():
            arguments = environ.read_bytes().split(b"\0")
            assert b"-I" in arguments
            assert arguments[-3].endswith(b"sqlite_access.py")
        assert Path(f"/proc/{pid}/cwd").resolve() == Path("/") or not Path("/proc").exists()
    finally:
        pool.close()
