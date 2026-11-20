"""Measure how a guest reader can open another application's SQLite database.

Each suite stages real databases, owners in separate processes, and readers, and
writes ``results/<suite>.json`` with no machine paths in it. Run it as an unprivileged
user: a superuser ignores the folder and file permissions several cases depend on.
See ``README.md`` beside this file for the command, the recorded run, and what each
result decides in the tabular data plan.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import os
import platform
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Generator
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
SCRIPT = Path(__file__).resolve()

Result = dict[str, object]


# ---- Shared helpers ----


def _uri(path: Path, query: str) -> str:
    return f"{path.as_uri()}?{query}"


def _listing(folder: Path) -> dict[str, int]:
    """Every file in *folder* with its size, so a case shows what a read left behind."""

    return {
        entry.name: entry.stat().st_size for entry in sorted(folder.iterdir()) if entry.is_file()
    }


def _digest(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return None


def _error(exc: sqlite3.Error) -> str:
    return str(getattr(exc, "sqlite_errorname", "")) or type(exc).__name__


def _count(path: Path, query: str, table: str = "t") -> Result:
    """Open *path* with the URI *query*, count *table*'s rows, and close."""

    try:
        connection = sqlite3.connect(_uri(path, query), uri=True, timeout=0)
        try:
            rows = connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        finally:
            connection.close()
    except sqlite3.Error as exc:
        return {"error": _error(exc), "message": str(exc)}
    return {"rows": rows}


def _read(path: Path, query: str) -> Result:
    """A count through one access mode, and the folder listing after the connection closed."""

    result = _count(path, query)
    result["after"] = _listing(path.parent)
    return result


def _make_db(path: Path, *, wal: bool, rows: int = 100) -> None:
    connection = sqlite3.connect(path)
    if wal:
        connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, v TEXT)")
    connection.executemany("INSERT INTO t(v) VALUES (?)", [(f"row {i}",) for i in range(rows)])
    connection.commit()
    connection.close()


@contextlib.contextmanager
def _case(scratch: Path, name: str) -> Generator[Path]:
    folder = scratch / name
    if folder.exists():
        _make_writable(folder)
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    try:
        yield folder
    finally:
        _make_writable(folder)
        shutil.rmtree(folder, ignore_errors=True)


def _make_writable(folder: Path) -> None:
    folder.chmod(0o755)
    for entry in folder.iterdir():
        if entry.is_file() and not entry.is_symlink():
            entry.chmod(0o644)


def _make_read_only(folder: Path) -> None:
    for entry in folder.iterdir():
        if entry.is_file() and not entry.is_symlink():
            entry.chmod(0o444)
    folder.chmod(0o555)


class Owner:
    """A database owner in its own process, driven one command line at a time."""

    def __init__(self, role: str, *args: str) -> None:
        self.process = subprocess.Popen(
            [sys.executable, "-I", str(SCRIPT), "_owner", role, *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        self.wait_for("ready")

    def wait_for(self, word: str) -> str:
        assert self.process.stdout is not None
        line = self.process.stdout.readline().strip()
        if not line.startswith(word):
            raise RuntimeError(f"owner said {line!r}, expected {word!r}")
        return line[len(word) :].strip()

    def send(self, command: str) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()

    def finish(self, command: str) -> str:
        self.send(command)
        assert self.process.stdout is not None
        rest = self.process.stdout.read()
        self.process.wait(timeout=60)
        return rest.strip()


def _owner_main(role: str, args: list[str]) -> None:
    """The owner side of a case. It prints ``ready`` and then follows stdin commands."""

    path = Path(args[0])
    if role == "wal-commits":
        # Commit rows one at a time with no automatic checkpoint, so they stay in -wal.
        connection = sqlite3.connect(path, isolation_level=None)
        connection.execute("PRAGMA wal_autocheckpoint=0")
        for i in range(int(args[1])):
            connection.execute("INSERT INTO t(v) VALUES (?)", (f"owner {i}",))
        print("ready", flush=True)
        for line in sys.stdin:
            command = line.strip()
            if command == "crash":
                os._exit(0)
            if command == "close":
                connection.close()
                print("closed", flush=True)
                return
            if command == "commit":
                connection.execute("INSERT INTO t(v) VALUES ('one more')")
                print("committed", flush=True)
    elif role == "wal-new-schema":
        connection = sqlite3.connect(path, isolation_level=None)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA wal_autocheckpoint=0")
        connection.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, v TEXT)")
        connection.execute("INSERT INTO t(v) VALUES ('first')")
        print("ready", flush=True)
        sys.stdin.readline()
        connection.close()
    elif role == "interrupted-write":
        # Spill a large update into the main file, then die before committing.
        connection = sqlite3.connect(path, isolation_level=None)
        connection.execute("PRAGMA cache_size=5")
        connection.execute("BEGIN")
        connection.execute("UPDATE t SET v = 'changed ' || id")
        print("ready", flush=True)
        os._exit(0)
    elif role == "commit-loop":
        _commit_loop(path, float(args[1]), float(args[2]))
    else:
        raise SystemExit(f"unknown owner role {role}")


def _commit_loop(path: Path, seconds: float, pause: float) -> None:
    """Commit one row, then wait *pause* seconds, with no busy timeout; count refusals."""

    connection = sqlite3.connect(path, isolation_level=None, timeout=0)
    connection.execute("PRAGMA busy_timeout=0")
    print("ready", flush=True)
    commits = busy = 0
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            connection.execute("BEGIN")
            connection.execute("INSERT INTO t(a, b) VALUES (?, 'owner')", (commits % 1000,))
            connection.execute("COMMIT")
            commits += 1
        except sqlite3.OperationalError as exc:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            if _error(exc) != "SQLITE_BUSY":
                raise
            busy += 1
        time.sleep(pause)
    sys.stdin.readline()
    print(json.dumps({"commits": commits, "busy": busy}), flush=True)


# ---- Suite: access ----


def suite_access(scratch: Path) -> Result:
    """Which access mode reads correctly, and what it leaves beside the database."""

    out: Result = {}

    with _case(scratch, "wal-idle") as folder:
        db = folder / "app.db"
        _make_db(db, wal=True)
        out["wal_idle_writable_folder"] = {
            "before": _listing(folder),
            "immutable": _read(db, "mode=ro&immutable=1"),
            "mode_ro": _read(db, "mode=ro"),
        }

    with _case(scratch, "wal-idle-ro") as folder:
        db = folder / "app.db"
        _make_db(db, wal=True)
        _make_read_only(folder)
        out["wal_idle_read_only_folder"] = {
            "mode_ro": _read(db, "mode=ro"),
            "immutable": _read(db, "mode=ro&immutable=1"),
        }

    with _case(scratch, "wal-live") as folder:
        db = folder / "app.db"
        _make_db(db, wal=True)
        owner = Owner("wal-commits", str(db), "5")
        out["wal_live_owner"] = {
            "before": _listing(folder),
            "mode_ro": _read(db, "mode=ro"),
            "immutable": _read(db, "mode=ro&immutable=1"),
        }
        owner.finish("close")

    with _case(scratch, "wal-live-new-schema") as folder:
        db = folder / "app.db"
        owner = Owner("wal-new-schema", str(db))
        out["wal_live_schema_not_checkpointed"] = {
            "mode_ro": _count(db, "mode=ro"),
            "immutable": _count(db, "mode=ro&immutable=1"),
        }
        owner.finish("close")

    with _case(scratch, "rollback-interrupted") as folder:
        db = folder / "app.db"
        _make_db(db, wal=False, rows=20_000)
        Owner("interrupted-write", str(db)).process.wait(timeout=60)
        journal = folder / "app.db-journal"
        before = _digest(journal)
        changed = _changed_rows(db)
        out["rollback_hot_journal"] = {
            "before": _listing(folder),
            "mode_ro": _read(db, "mode=ro"),
            "immutable_changed_rows_of_20000": changed,
            "journal_untouched": _digest(journal) == before,
        }

    out.update(_stale_wal_cases(scratch))
    out.update(_race_cases(scratch))
    out["held_read_starves_checkpoint"] = _held_read(scratch)
    out["wal_commit_leaves_main_file"] = _wal_commit_main_file(scratch)
    return out


def _changed_rows(db: Path) -> Result:
    try:
        connection = sqlite3.connect(_uri(db, "mode=ro&immutable=1"), uri=True)
        try:
            changed = connection.execute(
                "SELECT count(*) FROM t WHERE v LIKE 'changed %'"
            ).fetchone()[0]
        finally:
            connection.close()
    except sqlite3.Error as exc:
        return {"error": _error(exc)}
    return {"rows": changed}


def _stale_wal_cases(scratch: Path) -> Result:
    """A crashed owner's -wal with frames, with and without -shm, writable or read-only."""

    out: Result = {}
    for name, drop_shm, read_only in (
        ("crashed_owner_wal_and_shm_writable_folder", False, False),
        ("crashed_owner_wal_and_shm_read_only_folder", False, True),
        ("wal_with_frames_no_shm_writable_folder", True, False),
        ("wal_with_frames_no_shm_read_only_folder", True, True),
    ):
        with _case(scratch, name) as folder:
            db = folder / "app.db"
            _make_db(db, wal=True)
            Owner("wal-commits", str(db), "5").finish("crash")
            if drop_shm:
                (folder / "app.db-shm").unlink()
            if read_only:
                _make_read_only(folder)
            shm = folder / "app.db-shm"
            shm_before = _digest(shm)
            before = _listing(folder)
            mode_ro = _read(db, "mode=ro")
            out[name] = {
                "before": before,
                "mode_ro": mode_ro,
                "shm_rewritten_by_mode_ro": shm_before is not None and _digest(shm) != shm_before,
                "immutable": _read(db, "mode=ro&immutable=1"),
            }
    return out


def _race_cases(scratch: Path) -> Result:
    out: Result = {}

    # The owner checkpoints and exits between the reader's stat and its open.
    with _case(scratch, "owner-exits-before-open") as folder:
        db = folder / "app.db"
        _make_db(db, wal=True)
        owner = Owner("wal-commits", str(db), "1")
        seen = _listing(folder)
        owner.finish("close")
        out["owner_exits_between_stat_and_open"] = {
            "stat_saw": seen,
            "at_open": _listing(folder),
            "mode_ro": _read(db, "mode=ro"),
        }

    # The owner closes while a mode=ro reader is open; the reader closes last.
    with _case(scratch, "reader-closes-last") as folder:
        db = folder / "app.db"
        _make_db(db, wal=True)
        owner = Owner("wal-commits", str(db), "3")
        reader = sqlite3.connect(_uri(db, "mode=ro"), uri=True)
        reader.execute("SELECT count(*) FROM t").fetchone()
        owner.finish("close")
        reader.close()
        after_reader = _listing(folder)
    with _case(scratch, "owner-closes-alone") as folder:
        db = folder / "app.db"
        _make_db(db, wal=True)
        Owner("wal-commits", str(db), "3").finish("close")
        out["reader_closes_last"] = {
            "with_reader": after_reader,
            "without_reader": _listing(folder),
        }

    # A symlink in another folder: the sidecars live beside the target.
    with _case(scratch, "symlink") as folder:
        (folder / "data").mkdir()
        (folder / "links").mkdir()
        db = folder / "data" / "app.db"
        _make_db(db, wal=True)
        owner = Owner("wal-commits", str(db), "1")
        link = folder / "links" / "app.db"
        link.symlink_to(db)
        out["symlink_in_another_folder"] = {
            "beside_link": sorted(p.name for p in (folder / "links").iterdir()),
            "mode_ro": _count(link, "mode=ro"),
            "immutable": _count(link, "mode=ro&immutable=1"),
        }
        owner.finish("close")

    # A second hard link to a live write-ahead-log database.
    with _case(scratch, "hard-link") as folder:
        db = folder / "app.db"
        _make_db(db, wal=True)
        owner = Owner("wal-commits", str(db), "1")
        hard = folder / "hard.db"
        os.link(db, hard)
        out["hard_link_to_live_database"] = {
            "nlink": db.stat().st_nlink,
            "mode_ro": _read(hard, "mode=ro"),
        }
        owner.finish("close")
    return out


def _held_read(scratch: Path) -> Result:
    with _case(scratch, "held-read") as folder:
        db = folder / "app.db"
        _make_db(db, wal=True)
        owner = sqlite3.connect(db, isolation_level=None)
        owner.execute("PRAGMA wal_autocheckpoint=0")
        reader = sqlite3.connect(_uri(db, "mode=ro"), uri=True, isolation_level=None)
        reader.execute("BEGIN")
        reader.execute("SELECT count(*) FROM t").fetchone()
        for i in range(300):
            owner.execute("INSERT INTO t(v) VALUES (?)", ("x" * 4000 + str(i),))
        held = owner.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        held_wal = (folder / "app.db-wal").stat().st_size
        reader.execute("COMMIT")
        released = owner.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        released_wal = (folder / "app.db-wal").stat().st_size
        reader.close()
        owner.close()
    return {
        "while_held": {"busy": held[0], "wal_bytes": held_wal},
        "after_release": {"busy": released[0], "wal_bytes": released_wal},
    }


def _wal_commit_main_file(scratch: Path) -> Result:
    with _case(scratch, "wal-commit-main") as folder:
        db = folder / "app.db"
        _make_db(db, wal=True)
        owner = sqlite3.connect(db, isolation_level=None)
        owner.execute("PRAGMA wal_autocheckpoint=0")
        owner.execute("INSERT INTO t(v) VALUES ('warm')")
        main_before = (db.stat().st_size, db.stat().st_mtime_ns, _digest(db))
        wal_before = (folder / "app.db-wal").stat().st_size
        time.sleep(0.05)
        owner.execute("INSERT INTO t(v) VALUES ('commit')")
        main_after = (db.stat().st_size, db.stat().st_mtime_ns, _digest(db))
        wal_after = (folder / "app.db-wal").stat().st_size
        owner.close()
    return {"main_file_unchanged": main_before == main_after, "wal_bytes": [wal_before, wal_after]}


# ---- Suite: contention ----


CONTENTION_ROWS = 200_000
CONTENTION_SECONDS = 4.0
CONTENTION_READS_PER_SECOND = 4
# Seconds an owner waits between commits: back to back, and an application that writes
# twenty times a second.
CONTENTION_OWNER_PAUSES = {"back_to_back": 0.0, "every_50_ms": 0.05}


def suite_contention(scratch: Path) -> Result:
    """An owner committing with no busy timeout while a viewer reads a rollback database."""

    reads: dict[str, Callable[[Path], bool] | None] = {
        "none": None,
        "key_ordered_page": lambda db: _locked_read(db, "SELECT * FROM t ORDER BY id LIMIT 100"),
        "count": lambda db: _locked_read(db, "SELECT count(*) FROM t"),
        "unindexed_sort_page": lambda db: _locked_read(
            db, "SELECT * FROM t ORDER BY b, a, id LIMIT 100"
        ),
        "validated_immutable_key_ordered_page": lambda db: _validated_read(
            db, "SELECT * FROM t ORDER BY id LIMIT 100"
        ),
        "validated_immutable_unindexed_sort": lambda db: _validated_read(
            db, "SELECT * FROM t ORDER BY b, a, id LIMIT 100"
        ),
    }
    out: Result = {}
    with _case(scratch, "contention") as folder:
        db = folder / "app.db"
        connection = sqlite3.connect(db)
        connection.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, a INTEGER, b TEXT)")
        connection.execute(
            "WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n WHERE i < ?) "
            "INSERT INTO t(a, b) SELECT i % 1000, printf('text %d', (i * 7919) % 100003) FROM n",
            (CONTENTION_ROWS,),
        )
        connection.commit()
        connection.close()
        for pace, pause in CONTENTION_OWNER_PAUSES.items():
            out[pace] = _contend(db, reads, pause)
    return out


def _contend(db: Path, reads: dict[str, Callable[[Path], bool] | None], pause: float) -> Result:
    out: Result = {}
    for name, read in reads.items():
        owner = Owner("commit-loop", str(db), str(CONTENTION_SECONDS), str(pause))
        valid = invalid = 0
        deadline = time.monotonic() + CONTENTION_SECONDS
        while time.monotonic() < deadline:
            if read is not None:
                if read(db):
                    valid += 1
                else:
                    invalid += 1
            time.sleep(1 / CONTENTION_READS_PER_SECOND)
        result: Result = json.loads(owner.finish("report"))
        result["viewer_reads"] = valid + invalid
        result["viewer_reads_failed_or_rejected"] = invalid
        out[name] = result
    return out


def _locked_read(db: Path, sql: str) -> bool:
    try:
        connection = sqlite3.connect(_uri(db, "mode=ro"), uri=True, timeout=0.25)
        try:
            connection.execute(sql).fetchall()
        finally:
            connection.close()
    except sqlite3.Error:
        return False
    return True


def _fingerprint(db: Path) -> tuple[int, int, int, bytes, bool]:
    """Identity, size, mtime, the header's change counter, and whether a journal exists."""

    stat = db.stat()
    with db.open("rb") as handle:
        handle.seek(24)
        counter = handle.read(4)
    journal = db.with_name(db.name + "-journal")
    return (stat.st_ino, stat.st_size, stat.st_mtime_ns, counter, journal.exists())


def _validated_read(db: Path, sql: str) -> bool:
    """A lock-free ``immutable=1`` read, accepted only if nothing changed across it."""

    before = _fingerprint(db)
    if before[4]:
        return False
    try:
        connection = sqlite3.connect(_uri(db, "mode=ro&immutable=1"), uri=True)
        try:
            connection.execute(sql).fetchall()
        finally:
            connection.close()
    except sqlite3.Error:
        return False
    return _fingerprint(db) == before


# ---- Suite: budget ----


BUDGET_COUNT_ROWS = 1_500_000
BUDGET_PAGE_ROWS = 200_000


def suite_budget(scratch: Path) -> Result:
    """What a progress-handler budget sees, and what each kind of page costs in opcodes."""

    out: Result = {}
    with _case(scratch, "budget") as folder:
        db = folder / "app.db"
        connection = sqlite3.connect(db, check_same_thread=False)
        connection.execute("CREATE TABLE big(id INTEGER PRIMARY KEY, a INTEGER)")
        connection.execute(
            "WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n WHERE i < ?) "
            "INSERT INTO big SELECT i, i % 97 FROM n",
            (BUDGET_COUNT_ROWS,),
        )
        connection.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, a INTEGER, c INTEGER, b TEXT)")
        connection.execute(
            "WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n WHERE i < ?) "
            "INSERT INTO t SELECT i, (i * 7919) % 100003, (i * 104729) % 100019, printf('text %d', i) FROM n",
            (BUDGET_PAGE_ROWS,),
        )
        connection.execute("CREATE INDEX t_c ON t(c)")
        connection.commit()

        out["count_star"] = _opcodes(connection, "SELECT count(*) FROM big")
        out["count_star_with_1000_opcode_budget"] = _budgeted(
            connection, "SELECT count(*) FROM big", 1000
        )
        out["capped_count"] = _opcodes(
            connection, "SELECT count(*) FROM (SELECT 1 FROM big LIMIT 1000001)"
        )
        out["capped_count_with_1000_opcode_budget"] = _budgeted(
            connection, "SELECT count(*) FROM (SELECT 1 FROM big LIMIT 1000001)", 1000
        )
        out["interrupt_stops_repeated_count_star"] = _interrupt_count(connection)

        pages = {
            "key_ordered_page": ("SELECT * FROM t ORDER BY id LIMIT 100", ()),
            "key_ordered_continuation": (
                "SELECT * FROM t WHERE id > ? ORDER BY id LIMIT 100",
                (150_000,),
            ),
            "indexed_sort_page": ("SELECT * FROM t ORDER BY c, id LIMIT 100", ()),
            "indexed_sort_continuation": (
                "SELECT * FROM t WHERE (c, id) > (?, ?) ORDER BY c, id LIMIT 100",
                (50_000, 0),
            ),
            "unindexed_sort_page": ("SELECT * FROM t ORDER BY a, id LIMIT 100", ()),
            "unindexed_sort_continuation": (
                "SELECT * FROM t WHERE (a, id) > (?, ?) ORDER BY a, id LIMIT 100",
                (50_000, 0),
            ),
            "contains_filter_page": (
                "SELECT * FROM t WHERE b LIKE '%99999%' ORDER BY id LIMIT 100",
                (),
            ),
        }
        out["page_opcodes_over_200000_rows"] = {
            name: _opcodes(connection, sql, params)["opcodes"]
            for name, (sql, params) in pages.items()
        }
        connection.close()
    return out


def _opcodes(connection: sqlite3.Connection, sql: str, params: tuple[object, ...] = ()) -> Result:
    calls = 0

    def count() -> int:
        nonlocal calls
        calls += 1
        return 0

    connection.set_progress_handler(count, 1)
    try:
        rows = connection.execute(sql, params).fetchall()
    finally:
        connection.set_progress_handler(None, 1)
    return {"opcodes": calls, "rows": len(rows), "first": rows[0][0] if len(rows) == 1 else None}


def _budgeted(connection: sqlite3.Connection, sql: str, every: int) -> Result:
    """Run *sql* with a handler that aborts on its first call, as a spent budget would."""

    calls = 0

    def abort() -> int:
        nonlocal calls
        calls += 1
        return 1

    connection.set_progress_handler(abort, every)
    try:
        value = connection.execute(sql).fetchone()[0]
        result: Result = {"returned": value}
    except sqlite3.OperationalError as exc:
        result = {"error": str(exc)}
    finally:
        connection.set_progress_handler(None, every)
    result["handler_calls"] = calls
    return result


def _interrupt_count(connection: sqlite3.Connection) -> Result:
    """A watchdog's ``interrupt()`` against a thread running only ``count(*)``."""

    outcome: Result = {}

    def run() -> None:
        done = 0
        try:
            while done < 100_000:
                connection.execute("SELECT count(*) FROM big").fetchone()
                done += 1
            outcome["finished"] = done
        except sqlite3.OperationalError as exc:
            outcome["error"] = str(exc)
            outcome["counts_before_interrupt"] = done

    worker = threading.Thread(target=run)
    worker.start()
    time.sleep(0.2)
    connection.interrupt()
    worker.join()
    return outcome


# ---- Suite: values ----


def suite_values(scratch: Path, value_mb: int) -> Result:
    """Peak memory to preview one large value, each query in a fresh process."""

    out: Result = {"value_mb": value_mb}
    with _case(scratch, "values") as folder:
        db = folder / "big.db"
        connection = sqlite3.connect(db)
        connection.execute("CREATE TABLE big(id INTEGER PRIMARY KEY, v TEXT, b BLOB)")
        size = value_mb * 1024 * 1024
        connection.execute("INSERT INTO big VALUES (1, ?, ?)", ("x" * size, b"\x01" * size))
        connection.commit()
        connection.close()
        for name in MEMORY_QUERIES:
            completed = subprocess.run(
                [sys.executable, "-I", str(SCRIPT), "_memory", str(db), name],
                capture_output=True,
                text=True,
                check=True,
            )
            out[name] = json.loads(completed.stdout)
    return out


MEMORY_QUERIES: dict[str, str | None] = {
    "baseline": "SELECT id FROM big",
    "substr_and_length_text": "SELECT substr(v, 1, 100), length(v) FROM big",
    "substr_and_length_blob": "SELECT substr(b, 1, 16), length(b) FROM big",
    "length_text": "SELECT length(v) FROM big",
    "length_blob": "SELECT length(b) FROM big",
    "octet_length_text": "SELECT octet_length(v) FROM big",
    "typeof_text": "SELECT typeof(v) FROM big",
    "blobopen_100_bytes_text": None,
}


def _memory_main(db: Path, name: str) -> None:
    connection = sqlite3.connect(_uri(db, "mode=ro"), uri=True)
    sql = MEMORY_QUERIES[name]
    if sql is None:
        with connection.blobopen("big", "v", 1, readonly=True) as blob:
            value: object = len(blob.read(100))
    else:
        row: tuple[object, ...] = connection.execute(sql).fetchone()
        value = [len(item) if isinstance(item, (str, bytes)) else item for item in row]
    connection.close()
    peak = _peak_rss_mb()
    print(json.dumps({"peak_rss_mb": peak, "value": value}))


def _peak_rss_mb() -> int:
    """This process's peak resident memory since it started its program.

    Linux carries ``ru_maxrss`` across ``fork`` and ``exec``, so a child would report its
    parent's peak; the memory map's ``VmHWM`` starts afresh at ``exec``.
    """

    status = Path("/proc/self/status")
    if status.exists():
        for line in status.read_text(encoding="utf-8").splitlines():
            if line.startswith("VmHWM:"):
                return round(int(line.split()[1]) / 1024)
    import resource

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    scale = 1024 * 1024 if sys.platform == "darwin" else 1024
    return round(peak / scale)


# ---- Suite: encoding ----


def suite_encoding(scratch: Path) -> Result:
    """Values JSON or Python's defaults cannot carry, keyset paging, and untrusted schemas."""

    out: Result = {}
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE r(id INTEGER PRIMARY KEY, v)")
    connection.execute(
        "INSERT INTO r VALUES (1, 13390000000000001), (2, 9e999), (3, CAST(x'ff41' AS TEXT))"
    )
    big = connection.execute("SELECT v FROM r WHERE id = 1").fetchone()[0]
    out["integer_past_2_53"] = {"stored": str(big), "as_a_browser_number": str(int(float(big)))}
    infinite = connection.execute("SELECT v FROM r WHERE id = 2").fetchone()[0]
    try:
        json.dumps(infinite, allow_nan=False)
        out["infinite_real"] = "serialized"
    except ValueError as exc:
        out["infinite_real"] = f"json refuses: {exc}"
    try:
        connection.execute("SELECT v FROM r WHERE id = 3").fetchone()
        out["invalid_utf8_text"] = "decoded"
    except sqlite3.OperationalError as exc:
        out["invalid_utf8_text"] = f"default text factory raises: {str(exc).split(' with ')[0]}"
    out["keyset"] = _keyset(connection)
    out["deserialize"] = _deserialize(scratch)
    out["untrusted_schema"] = _untrusted_schema()
    connection.close()
    return out


KEYSET_VALUES: tuple[object, ...] = (
    None, 1, 2, 10, 2.5, -3, "1", "10", "abc", "B", "", b"\x00", b"z", 1e300, "2.5", " 5", "0x10", "1e3", " 7 "
)  # fmt: skip


def _keyset(connection: sqlite3.Connection) -> Result:
    """Page an indexed mixed-type column with nulls and compare the pages with one ORDER BY."""

    out: Result = {}
    for declared in ("TEXT", "INTEGER", "REAL", "NUMERIC", "BLOB", "", "TEXT COLLATE NOCASE"):
        connection.execute("DROP TABLE IF EXISTS k")
        connection.execute(f"CREATE TABLE k(id INTEGER PRIMARY KEY, s {declared})")
        connection.execute("CREATE INDEX k_s ON k(s)")
        connection.executemany(
            "INSERT INTO k(s) VALUES (?)",
            [(KEYSET_VALUES[(i * 7) % len(KEYSET_VALUES)],) for i in range(500)],
        )
        full = [row[0] for row in connection.execute("SELECT id FROM k ORDER BY s, id")]
        out[declared or "no type"] = {
            "row_value_predicate": _pages(connection, _row_value_page) == full,
            "row_value_with_null_branch": _pages(connection, _null_branch_page) == full,
        }
    return out


Page = list[tuple[int, object]]


def _row_value_page(connection: sqlite3.Connection, last: tuple[int, object] | None) -> Page:
    if last is None:
        return connection.execute("SELECT id, s FROM k ORDER BY s, id LIMIT 7").fetchall()
    return connection.execute(
        "SELECT id, s FROM k WHERE (s, id) > (?, ?) ORDER BY s, id LIMIT 7", (last[1], last[0])
    ).fetchall()


def _null_branch_page(connection: sqlite3.Connection, last: tuple[int, object] | None) -> Page:
    """Null sorts first and compares as unknown, so a null cursor continues on its own branch."""

    if last is None or last[1] is not None:
        return _row_value_page(connection, last)
    return connection.execute(
        "SELECT id, s FROM k WHERE (s IS NULL AND id > ?) OR s IS NOT NULL ORDER BY s, id LIMIT 7",
        (last[0],),
    ).fetchall()


def _pages(
    connection: sqlite3.Connection,
    page: Callable[[sqlite3.Connection, tuple[int, object] | None], Page],
) -> list[int]:
    ids: list[int] = []
    rows = page(connection, None)
    while rows and len(ids) <= 500:
        ids.extend(row[0] for row in rows)
        rows = page(connection, rows[-1])
    return ids


def _deserialize(scratch: Path) -> Result:
    with _case(scratch, "deserialize") as folder:
        db = folder / "app.db"
        _make_db(db, wal=True, rows=3)
        data = bytearray(db.read_bytes())
    out: Result = {"header_bytes_18_19": data[18:20].hex()}
    for name, patch in (("as_committed", False), ("header_patched_to_rollback", True)):
        if patch:
            data[18:20] = b"\x01\x01"
        copy = sqlite3.connect(":memory:")
        copy.deserialize(bytes(data))
        try:
            out[name] = {"rows": copy.execute("SELECT count(*) FROM t").fetchone()[0]}
        except sqlite3.Error as exc:
            out[name] = {"error": _error(exc)}
        copy.close()
    return out


def _untrusted_schema() -> Result:
    connection = sqlite3.connect(":memory:")
    out: Result = {
        "trusted_schema_default": connection.execute("PRAGMA trusted_schema").fetchone()[0]
    }
    options = {row[0] for row in connection.execute("PRAGMA compile_options")}
    out["virtual_table_modules"] = sorted(
        option.removeprefix("ENABLE_")
        for option in options
        if option
        in {
            "ENABLE_FTS3",
            "ENABLE_FTS4",
            "ENABLE_FTS5",
            "ENABLE_RTREE",
            "ENABLE_GEOPOLY",
            "ENABLE_DBSTAT_VTAB",
        }
    )
    connection.execute("CREATE VIRTUAL TABLE f USING fts5(body)")
    connection.execute("INSERT INTO f VALUES ('hello world')")
    connection.execute("CREATE VIEW v AS SELECT * FROM f WHERE f MATCH 'hello'")
    connection.execute("PRAGMA trusted_schema=OFF")
    reads: Result = {}
    for sql in (
        "SELECT * FROM f",
        "SELECT * FROM f_data",
        "SELECT * FROM f_config",
        "SELECT * FROM v",
    ):
        try:
            reads[sql] = f"{len(connection.execute(sql).fetchall())} rows"
        except sqlite3.Error as exc:
            reads[sql] = f"refused: {exc}"
    out["with_trusted_schema_off"] = reads
    out["python_exposes_defensive"] = hasattr(sqlite3, "SQLITE_DBCONFIG_DEFENSIVE")
    connection.close()
    return out


# ---- Suite: generation ----


GENERATION_CYCLES = 200


def suite_generation(scratch: Path) -> Result:
    """Whether a restarted log repeats its size, and whether its header salts change."""

    with _case(scratch, "generation") as folder:
        db = folder / "app.db"
        _make_db(db, wal=True)
        owner = sqlite3.connect(db, isolation_level=None)
        owner.execute("PRAGMA wal_autocheckpoint=0")
        wal = folder / "app.db-wal"
        sizes: set[int] = set()
        headers: set[bytes] = set()
        for i in range(GENERATION_CYCLES):
            owner.execute("INSERT INTO t(v) VALUES (?)", (f"cycle {i}",))
            sizes.add(wal.stat().st_size)
            with wal.open("rb") as handle:
                headers.add(handle.read(24)[12:24])
            owner.execute("PRAGMA wal_checkpoint(PASSIVE)")
        owner.close()
    return {
        "cycles": GENERATION_CYCLES,
        "distinct_wal_sizes": len(sizes),
        "distinct_header_salts": len(headers),
    }


# ---- Entry point ----


SUITES = ("access", "contention", "budget", "values", "encoding", "generation")


def _environment() -> Result:
    return {
        "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version,
        "system": f"{platform.system()} {platform.release()}",
        "machine": platform.machine(),
        "uid_is_superuser": os.geteuid() == 0,
    }


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "_owner":
        _owner_main(sys.argv[2], sys.argv[3:])
        return
    if len(sys.argv) > 1 and sys.argv[1] == "_memory":
        _memory_main(Path(sys.argv[2]), sys.argv[3])
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scratch", type=Path, required=True, help="an empty folder this user may write"
    )
    parser.add_argument("--out", type=Path, default=RESULTS)
    parser.add_argument("--value-mb", type=int, default=200)
    parser.add_argument(
        "suites", nargs="*", choices=SUITES, help="the suites to run; all when none is named"
    )
    options = parser.parse_args()
    if os.geteuid() == 0:
        raise SystemExit(
            "run as an unprivileged user: a superuser ignores the permissions measured here"
        )
    scratch: Path = options.scratch
    scratch.mkdir(parents=True, exist_ok=True)
    out: Path = options.out
    out.mkdir(parents=True, exist_ok=True)
    suites: list[str] = options.suites or list(SUITES)
    for name in suites:
        started = time.monotonic()
        if name == "values":
            result = suite_values(scratch, options.value_mb)
        else:
            result = SUITE_FUNCTIONS[name](scratch)
        record: Result = {"suite": name, "environment": _environment(), "results": result}
        record["seconds"] = math.ceil(time.monotonic() - started)
        (out / f"{name}.json").write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"{name}: {record['seconds']} s")


SUITE_FUNCTIONS: dict[str, Callable[[Path], Result]] = {
    "access": suite_access,
    "contention": suite_contention,
    "budget": suite_budget,
    "encoding": suite_encoding,
    "generation": suite_generation,
}


if __name__ == "__main__":
    main()
