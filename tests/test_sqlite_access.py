"""The guest access helper's rules that need no owner process: the access table row by
row, the connection settings and authorizer, error states, and the reader pool's
subjects. The scenarios with real owners are ``tests/test_sqlite_guest_access.py``."""

from __future__ import annotations

import os
import sqlite3
import stat
import time
from dataclasses import replace
from pathlib import Path

import pytest

from metabrowser import sqlite_access
from metabrowser.sqlite_access import (
    FileState,
    Observation,
    ReadFn,
    SqliteAccessError,
    choose,
    deny_reads,
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
        shm_in_use=False,
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
    assert plan(header=_wal_header(), wal=frames, shm=shm, shm_in_use=True) == (
        "read_only",
        "current",
    )
    # An index no connection holds: a crashed owner or a copied folder, whose `-shm` a
    # `mode=ro` connection would rewrite.
    assert plan(header=_wal_header(), wal=frames, shm=shm) == ("private_copy", "current")
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


def test_a_time_far_ahead_of_the_clock_is_not_racy() -> None:
    now = 10**18
    window = int(sqlite_access.RACY_MTIME_SECONDS * 1e9)
    skewed = FileState(1, 2, 8192, now + 3600 * 10**9, 1)
    assert not _observation(header=_wal_header(), main=skewed, observed_ns=now).racy()
    just_ahead = FileState(1, 2, 8192, now + window // 2, 1)
    assert _observation(header=_wal_header(), main=just_ahead, observed_ns=now).racy()


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
        return (
            *tuple(
                connection.execute(f"PRAGMA {name}").fetchone()[0]
                for name in ("query_only", "trusted_schema", "cell_size_check", "mmap_size")
            ),
            connection.getlimit(sqlite3.SQLITE_LIMIT_LENGTH),
            connection.getlimit(sqlite3.SQLITE_LIMIT_ATTACHED),
            connection.getconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE),
        )

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
            assert arguments[-4].endswith(b"sqlite_access.py")
        assert Path(f"/proc/{pid}/cwd").resolve() == Path("/") or not Path("/proc").exists()
    finally:
        pool.close()


# ── Worker modules ─────────────────────────────────────────────

_PROBE_MODULE = """
import sys

from metabrowser import sqlite_access


def probe(args, deadline):
    return {
        "doubled": args["x"] * 2,
        "name": __name__,
        "version": VERSION,
        "metabrowser": sorted(name for name in sys.modules if name.startswith("metabrowser")),
    }


sqlite_access.OPS["probe"] = probe
"""


def test_a_registered_module_answers_in_the_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser import sqlite_readers

    monkeypatch.setattr(sqlite_readers, "_worker_modules", {})
    first = tmp_path / "probe_one.py"
    first.write_text(_PROBE_MODULE + "VERSION = 1\n")
    second = tmp_path / "probe_two.py"
    second.write_text(_PROBE_MODULE + "VERSION = 2\n")
    sqlite_readers.register_worker_module("metabrowser.builtin_plugins.probe.reader", first)
    pool = ReaderPool(size=1, temporary_root=tmp_path)
    try:
        answer = pool.call("probe", {"x": 21}, deadline=_deadline(), subject="s")
        assert answer == {
            "doubled": 42,
            "name": "metabrowser.builtin_plugins.probe.reader",
            "version": 1,
            "metabrowser": [
                "metabrowser",
                "metabrowser.builtin_plugins",
                "metabrowser.builtin_plugins.probe",
                "metabrowser.builtin_plugins.probe.reader",
                "metabrowser.sqlite_access",
            ],
        }
        [before] = pool.workers()
        # The same registration again changes nothing; another path replaces the worker.
        sqlite_readers.register_worker_module("metabrowser.builtin_plugins.probe.reader", first)
        pool.call("probe", {"x": 1}, deadline=_deadline(), subject="s")
        assert pool.workers() == [before]
        sqlite_readers.register_worker_module("metabrowser.builtin_plugins.probe.reader", second)
        answer = pool.call("probe", {"x": 1}, deadline=_deadline(), subject="s")
        assert answer["version"] == 2
        assert pool.workers() != [before]
        assert pool.started == 2
    finally:
        pool.close()


def test_worker_module_registrations_are_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser import sqlite_readers

    monkeypatch.setattr(sqlite_readers, "_worker_modules", {})
    module = tmp_path / "m.py"
    module.write_text("")
    with pytest.raises(ValueError, match="dotted import name"):
        sqlite_readers.register_worker_module("not a name", module)
    with pytest.raises(ValueError, match="not a Python file"):
        sqlite_readers.register_worker_module("m", tmp_path / "missing.py")
    for index in range(sqlite_readers.MAX_WORKER_MODULES):
        sqlite_readers.register_worker_module(f"m{index}", module)
    with pytest.raises(ValueError, match="more than"):
        sqlite_readers.register_worker_module("one_more", module)


# ── Schema pragmas and bounded attempts ────────────────────────


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT name FROM pragma_table_xinfo('t')",
        "SELECT * FROM pragma_foreign_key_list('child')",
        "SELECT * FROM pragma_index_list('t')",
        "SELECT * FROM pragma_index_xinfo('t_name')",
        "SELECT name FROM pragma_table_list WHERE schema = 'main'",
        "SELECT name FROM pragma_table_list('t')",
        "PRAGMA table_xinfo(t)",
        "PRAGMA index_list(t)",
    ],
)
def test_schema_pragmas_answer_with_an_argument(tmp_path: Path, sql: str) -> None:
    db = _database(tmp_path / "app.db")
    connection = sqlite3.connect(db)
    connection.execute("CREATE INDEX t_name ON t(name)")
    connection.execute("CREATE TABLE child(id INTEGER PRIMARY KEY, parent REFERENCES t(id))")
    connection.close()
    os.utime(db, (time.time() - 60, time.time() - 60))
    assert _run(db, sql, tmp_path)


@pytest.mark.parametrize(
    "sql",
    [
        "PRAGMA journal_mode = wal",
        "PRAGMA user_version = 1",
        "PRAGMA writable_schema = 1",
        "PRAGMA writable_schema",
        "PRAGMA query_only = 0",
        "PRAGMA trusted_schema = 1",
        "SELECT * FROM pragma_writable_schema",
        "SELECT * FROM pragma_query_only",
        "SELECT * FROM pragma_trusted_schema",
        "SELECT * FROM pragma_wal_checkpoint",
        "SELECT * FROM pragma_journal_mode('wal')",
        "SELECT * FROM pragma_user_version(1)",
    ],
)
def test_pragmas_that_write_or_set_stay_refused(tmp_path: Path, sql: str) -> None:
    db = _database(tmp_path / "app.db", wal=True)
    before = db.read_bytes()
    with pytest.raises(SqliteAccessError) as caught:
        _run(db, sql, tmp_path)
    assert caught.value.state in {"refused", "unreadable"}
    assert db.read_bytes() == before
    assert sorted(path.name for path in tmp_path.iterdir()) == ["app.db"]


def test_bounded_attempts_answer_without_waiting(tmp_path: Path) -> None:
    db = _database(tmp_path / "app.db")
    journal = tmp_path / "app.db-journal"
    journal.write_bytes(b"\xd9\xd5\x05\xf9\x20\xa1\x63\xd7" + bytes(512))
    started = time.monotonic()
    with pytest.raises(SqliteAccessError) as caught:
        read(db, lambda c: None, deadline=time.monotonic() + 5, scratch=tmp_path, attempts=1)
    assert caught.value.state == "writer_busy"
    assert time.monotonic() - started < 1
    journal.unlink()
    value, access = read(
        db,
        lambda c: c.execute("SELECT count(*) FROM t").fetchone()[0],
        deadline=_deadline(),
        scratch=tmp_path,
        attempts=1,
    )
    assert (value, access.attempts) == (2, 1)


# ── Bounds, ownerless indexes, and passing states ──────────


def _crafted_schema(path: Path, rows: int) -> Path:
    """A database whose schema rows claim *rows* types that each read as `table` up to a
    NUL, and a blob `table`, beside one real table."""
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE seed(a)")
    connection.setconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE, False)
    connection.execute("PRAGMA writable_schema=ON")
    insert = "INSERT INTO sqlite_schema(type, name, tbl_name, rootpage, sql) VALUES (?, ?, ?, 2, ?)"
    connection.executemany(
        insert,
        [
            (f"table\x00{index:07d}", f"t{index}", f"t{index}", f"CREATE TABLE t{index}(a)")
            for index in range(rows)
        ],
    )
    connection.execute(insert, (b"table", "blob", "blob", "CREATE TABLE blob(a)"))
    connection.commit()
    connection.close()
    then = time.time() - 60
    os.utime(path, (then, then))
    return path


def test_crafted_schema_types_group_as_other(tmp_path: Path) -> None:
    db = _crafted_schema(tmp_path / "crafted.db", 200)
    answer = sqlite_access.info(db, deadline=_deadline(), scratch=tmp_path)
    assert answer["database"]["objects"] == {"other": 201, "table": 1}


def test_an_answer_past_the_cap_stops_its_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _database(tmp_path / "app.db")
    pool = ReaderPool(size=1, temporary_root=tmp_path)
    original = sqlite_access.ANSWER_MAX_BYTES
    try:
        # The worker keeps its own cap; the parent's, lowered here, stops it mid-answer.
        monkeypatch.setattr(sqlite_access, "ANSWER_MAX_BYTES", 256)
        with pool.scratch() as scratch, pytest.raises(SqliteAccessError) as caught:
            pool.call(
                "info",
                {"path": str(db), "scratch": str(scratch)},
                deadline=_deadline(),
                subject="s",
            )
        # Its own state, not `busy`: asking again would answer the same length.
        assert caught.value.state == "too_large"
        assert "256 bytes" in caught.value.detail
        assert pool.workers() == []
        monkeypatch.setattr(sqlite_access, "ANSWER_MAX_BYTES", original)
        with pool.scratch() as scratch:
            answer = pool.call(
                "info",
                {"path": str(db), "scratch": str(scratch)},
                deadline=_deadline(),
                subject="s",
            )
        assert answer["database"]["objects"] == {"table": 1, "view": 1}
    finally:
        pool.close()


def test_a_reader_refuses_an_answer_past_the_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sqlite_access, "ANSWER_MAX_BYTES", 64)
    small = sqlite_access._encode_answer({"ok": True, "result": 1})  # pyright: ignore[reportPrivateUsage]
    assert small == b'{"ok":true,"result":1}'
    refused = sqlite_access._encode_answer({"ok": True, "result": "x" * 100})  # pyright: ignore[reportPrivateUsage]
    assert b'"state":"too_large"' in refused and b"x" * 100 not in refused
    assert sqlite_access.error_state("too_large") == "too_large"


_ANSWER_MODULE = """
import sqlite3

from metabrowser import sqlite_access


def long_answer(args, deadline):
    return "x" * (sqlite_access.ANSWER_MAX_BYTES + 1)


def heap_limit(args, deadline):
    connection = sqlite3.connect(":memory:")
    try:
        return connection.execute("PRAGMA hard_heap_limit").fetchone()[0]
    finally:
        connection.close()


sqlite_access.OPS["long_answer"] = long_answer
sqlite_access.OPS["heap_limit"] = heap_limit
"""


def test_a_reader_answers_busy_in_place_of_a_long_answer_and_bounds_its_heap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser import sqlite_readers

    monkeypatch.setattr(sqlite_readers, "_worker_modules", {})
    module = tmp_path / "answers.py"
    module.write_text(_ANSWER_MODULE)
    sqlite_readers.register_worker_module("metabrowser.builtin_plugins.answers.reader", module)
    pool = ReaderPool(size=1, temporary_root=tmp_path)
    try:
        with pytest.raises(SqliteAccessError) as caught:
            pool.call("long_answer", {}, deadline=time.monotonic() + 10, subject="s")
        assert caught.value.state == "too_large"
        assert "longer than" in caught.value.detail
        # Asked again, it answers the same: nothing about it passes with time.
        with pytest.raises(SqliteAccessError) as again:
            pool.call("long_answer", {}, deadline=time.monotonic() + 10, subject="s")
        assert again.value.state == "too_large"
        # The refusal is an answer: the reader stays.
        [pid] = pool.workers()
        limit = pool.call("heap_limit", {}, deadline=_deadline(), subject="s")
        assert limit == sqlite_access.HEAP_LIMIT_BYTES
        assert pool.workers() == [pid]
    finally:
        pool.close()


def test_a_request_that_cannot_be_sent_gives_its_reader_back(tmp_path: Path) -> None:
    pool = ReaderPool(size=1, temporary_root=tmp_path)
    try:
        with pytest.raises(TypeError):
            pool.call("ping", {"value": object()}, deadline=_deadline(), subject="s")
        # The pool's only place is free again.
        assert pool.call("ping", {}, deadline=_deadline(), subject="s") is None
    finally:
        pool.close()


def test_the_budget_is_installed_before_the_settings_read_the_schema() -> None:
    calls: list[str] = []

    class Recorder:
        def __getattr__(self, name: str) -> object:
            def record(*args: object, **kwargs: object) -> None:
                calls.append(name if name != "execute" else str(args[0]))

            return record

    sqlite_access.configure(Recorder(), deadline=_deadline(), opcodes=10)  # type: ignore[arg-type]
    assert calls.index("set_progress_handler") < calls.index(
        f"PRAGMA cache_size=-{sqlite_access.CACHE_KIB}"
    )
    assert calls[-1] == "set_authorizer"


def test_the_named_limits_are_applied(tmp_path: Path) -> None:
    db = _database(tmp_path / "app.db")

    def limits(connection: sqlite3.Connection) -> tuple[int, ...]:
        return tuple(
            connection.getlimit(limit)
            for limit in (
                sqlite3.SQLITE_LIMIT_COMPOUND_SELECT,
                sqlite3.SQLITE_LIMIT_LIKE_PATTERN_LENGTH,
                sqlite3.SQLITE_LIMIT_VDBE_OP,
            )
        )

    value, _ = read(db, limits, deadline=_deadline(), scratch=tmp_path)
    assert value == (
        sqlite_access.COMPOUND_SELECT_LIMIT,
        sqlite_access.LIKE_PATTERN_LIMIT,
        sqlite_access.VDBE_OP_LIMIT,
    )


def _ownerless_log(folder: Path) -> Path:
    """A write-ahead-log database with frames and its `-shm`, copied while its owner had
    it open, so no process holds the copy: a folder copied with its sidecars."""
    source = folder / "source"
    source.mkdir()
    owner = sqlite3.connect(source / "app.db", isolation_level=None)
    owner.execute("PRAGMA journal_mode=wal")
    owner.execute("PRAGMA wal_autocheckpoint=0")
    owner.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT)")
    owner.execute("INSERT INTO t(name) VALUES ('ada'), ('bob'), ('cy')")
    copied = folder / "copied"
    copied.mkdir()
    for suffix in ("", "-wal", "-shm"):
        (copied / f"app.db{suffix}").write_bytes((source / f"app.db{suffix}").read_bytes())
    owner.close()
    then = time.time() - 60
    for path in copied.iterdir():
        os.utime(path, (then, then))
    return copied / "app.db"


def _snapshot(folder: Path) -> dict[str, tuple[bytes, int, int]]:
    return {
        path.name: (
            path.read_bytes() if path.is_file() else b"",
            path.stat().st_mtime_ns,
            path.stat().st_mode,
        )
        for path in sorted(folder.iterdir())
    }


def test_an_index_no_connection_holds_is_never_rewritten(tmp_path: Path) -> None:
    db = _ownerless_log(tmp_path)
    shm = db.with_name("app.db-shm")
    shm.write_bytes(os.urandom(shm.stat().st_size))
    then = time.time() - 60
    os.utime(shm, (then, then))
    before = _snapshot(db.parent)
    obs = observe(db)
    assert obs.shm is not None and obs.wal_has_frames and not obs.shm_in_use
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    rows, access = read(
        db,
        lambda c: c.execute("SELECT count(*) FROM t").fetchone()[0],
        deadline=_deadline(),
        scratch=scratch,
    )
    assert (rows, access.plan.mode, access.plan.state) == (3, "private_copy", "current")
    assert "no application has it open" in access.plan.reason
    assert _snapshot(db.parent) == before


def test_a_fifo_named_like_a_sidecar_never_blocks_a_read(tmp_path: Path) -> None:
    db = _ownerless_log(tmp_path)
    shm = db.with_name("app.db-shm")
    shm.unlink()
    os.mkfifo(shm)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    started = time.monotonic()
    rows, access = read(
        db,
        lambda c: c.execute("SELECT count(*) FROM t").fetchone()[0],
        deadline=_deadline(),
        scratch=scratch,
    )
    assert (rows, access.plan.mode) == (3, "private_copy")
    assert time.monotonic() - started < 1
    assert stat.S_ISFIFO(shm.lstat().st_mode)
    # Asked directly, the race check refuses it as unreadable rather than waiting.
    with pytest.raises(OSError):
        sqlite_access._open_regular(shm)  # pyright: ignore[reportPrivateUsage]
    # And the generation does not wait on it either.
    assert sqlite_generation(db)


def test_a_busy_read_through_a_log_is_tried_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _database(tmp_path / "app.db", wal=True)
    plan = sqlite_access.Plan("read_only", "current", "through the log", validate=False)
    monkeypatch.setattr(sqlite_access, "choose", lambda *_args, **_kwargs: plan)
    failures = [sqlite3.SQLITE_BUSY, sqlite3.SQLITE_CANTOPEN]

    def through_log(*_args: object, **_kwargs: object) -> int:
        if failures:
            exc = sqlite3.OperationalError("database is locked")
            exc.sqlite_errorcode = failures.pop(0)  # type: ignore[attr-defined]
            raise exc
        return 7

    monkeypatch.setattr(sqlite_access, "_read_through_log", through_log)
    value, access = read(db, lambda c: None, deadline=_deadline(), scratch=tmp_path)
    assert (value, access.attempts) == (7, 3)

    def always_busy(*_args: object, **_kwargs: object) -> int:
        exc = sqlite3.OperationalError("database is locked")
        exc.sqlite_errorcode = sqlite3.SQLITE_BUSY  # type: ignore[attr-defined]
        raise exc

    monkeypatch.setattr(sqlite_access, "_read_through_log", always_busy)
    with pytest.raises(SqliteAccessError) as caught:
        read(db, lambda c: None, deadline=time.monotonic() + 0.3, scratch=tmp_path)
    assert caught.value.state == "busy"


# ── Private folders and blobs ──────────────────────────────────


def test_a_sweep_never_removes_a_folder_being_made(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fcntl
    import threading

    from metabrowser import sqlite_readers

    first, second = ReaderPool(temporary_root=tmp_path), ReaderPool(temporary_root=tmp_path)
    real = fcntl.flock
    paused, go = threading.Event(), threading.Event()

    def slow(fd: int, operation: int) -> None:
        if threading.current_thread().name == "first" and not paused.is_set():
            paused.set()
            go.wait(5)
        real(fd, operation)

    monkeypatch.setattr(sqlite_readers.fcntl, "flock", slow)
    made: list[Path] = []
    making = threading.Thread(target=lambda: made.append(first.folder()), name="first")
    try:
        making.start()
        assert paused.wait(5)
        # The second pool starts, sweeping, while the first is between making its lock
        # file and locking it.
        second.folder()
        go.set()
        making.join()
        assert made[0].is_dir()
        with first.scratch() as scratch:
            assert scratch.is_dir()
    finally:
        go.set()
        first.close()
        second.close()


def test_a_removed_private_folder_is_made_again(tmp_path: Path) -> None:
    import shutil

    pool = ReaderPool(temporary_root=tmp_path)
    try:
        lost = pool.folder()
        shutil.rmtree(lost)
        with pool.scratch() as scratch:
            assert scratch.is_dir()
        assert pool.folder().is_dir()
        written = pool.blob("abc", lambda: b"x")
        shutil.rmtree(pool.folder())
        assert pool.written_blob("abc") is None
        assert pool.blob("abc", lambda: b"y").read_bytes() == b"y"
        assert written != pool.folder()
    finally:
        pool.close()


def test_a_private_folder_that_cannot_be_made_is_a_state(tmp_path: Path) -> None:
    not_a_folder = tmp_path / "file"
    not_a_folder.write_bytes(b"")
    pool = ReaderPool(temporary_root=not_a_folder)
    try:
        with pytest.raises(SqliteAccessError) as caught, pool.scratch():
            pass
        assert caught.value.state == "unreadable"
    finally:
        pool.close()


def test_staging_folders_are_swept_only_once_stale(tmp_path: Path) -> None:
    from metabrowser import sqlite_readers

    fresh = tmp_path / ".metabrowser-sqlite-fresh"
    stale = tmp_path / ".metabrowser-sqlite-stale"
    for folder in (fresh, stale):
        folder.mkdir()
        (folder / "owner.lock").write_bytes(b"")
    then = time.time() - 2 * sqlite_readers.STAGING_STALE_SECONDS
    os.utime(stale, (then, then))
    pool = ReaderPool(temporary_root=tmp_path)
    try:
        pool.folder()
        assert fresh.exists() and not stale.exists()
    finally:
        pool.close()


def test_blobs_are_kept_within_their_bound(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from metabrowser import sqlite_readers

    monkeypatch.setattr(sqlite_readers, "BLOBS_MAX_BYTES", 250)
    monkeypatch.setattr(sqlite_readers, "BLOB_HOLD_SECONDS", 0.0)
    pool = ReaderPool(temporary_root=tmp_path)

    def never() -> bytes:
        raise AssertionError("a written blob was loaded again")

    try:
        first = pool.blob("a1", lambda: b"a" * 100)
        second = pool.blob("b2", lambda: b"b" * 100)
        # A request reading the first keeps it past the bound.
        reading = pool._blob_in_use(str(first), +1)  # pyright: ignore[reportPrivateUsage]
        third = pool.blob("c3", lambda: b"c" * 100)
        assert first.exists() and not second.exists() and third.exists()
        pool._blob_in_use(reading, -1)  # pyright: ignore[reportPrivateUsage]
        assert pool.blob("c3", never) == third
        fourth = pool.blob("d4", lambda: b"d" * 100)
        assert not first.exists() and third.exists() and fourth.exists()
        assert pool.written_blob("a1") is None
        assert pool.written_blob("c3") == third
    finally:
        pool.close()


# ── Reads a caller denies ──────────────────────────────────────


def _virtual(path: Path) -> Path:
    connection = sqlite3.connect(path)
    connection.executescript(
        "CREATE VIRTUAL TABLE notes USING fts5(body);"
        "INSERT INTO notes VALUES ('hello world');"
        "CREATE VIEW note_bodies AS SELECT body FROM notes;"
        "CREATE VIEW note_count AS SELECT count(*) AS n FROM notes;"
        "CREATE VIRTUAL TABLE boxes USING rtree(id, x0, x1);"
        "CREATE TABLE plain(a); INSERT INTO plain VALUES (1);"
        "CREATE VIEW plain_view AS SELECT a FROM plain;"
    )
    connection.close()
    then = time.time() - 60
    os.utime(path, (then, then))
    return path


_VIRTUAL_NAMES: frozenset[str] = frozenset(
    {
        "notes",
        "notes_data",
        "notes_idx",
        "notes_content",
        "notes_docsize",
        "notes_config",
        "BOXES",
        "boxes_node",
        "boxes_parent",
        "boxes_rowid",
    }
)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM note_bodies",
        "SELECT n FROM note_count",
        "SELECT count(*) FROM notes",
        "SELECT * FROM notes_data",
        "SELECT * FROM boxes",
        "PRAGMA table_xinfo(boxes)",
        "SELECT name FROM pragma_table_xinfo('boxes')",
        "SELECT name FROM pragma_table_xinfo('Notes')",
    ],
)
def test_denied_reads_are_refused_everywhere(tmp_path: Path, sql: str) -> None:
    db = _virtual(tmp_path / "virtual.db")

    def denied_then(query: str) -> ReadFn[object]:
        def run(connection: sqlite3.Connection) -> object:
            # Inside the read's transaction, as a caller that has just read the schema.
            assert connection.execute("SELECT a FROM plain").fetchall() == [(1,)]
            deny_reads(connection, _VIRTUAL_NAMES)
            return connection.execute(query).fetchall()

        return run

    with pytest.raises(SqliteAccessError) as caught:
        read(db, denied_then(sql), deadline=_deadline(), scratch=tmp_path)
    assert caught.value.state == "refused"
    # The other tables still read under the same denial.
    value, _ = read(db, denied_then("SELECT a FROM plain"), deadline=_deadline(), scratch=tmp_path)
    assert value == [(1,)]


def test_without_a_denial_reads_are_as_before(tmp_path: Path) -> None:
    db = _virtual(tmp_path / "virtual.db")
    assert _run(db, "SELECT a FROM plain_view", tmp_path) == [(1,)]
    # A shadow table is an ordinary table, read as any other unless a caller denies it.
    assert _run(db, "SELECT count(*) FROM notes_data", tmp_path) == [(3,)]
    assert [row[1] for row in _run(db, "PRAGMA table_xinfo(notes_data)", tmp_path)] == [  # type: ignore[index, union-attr]
        "id",
        "block",
    ]
