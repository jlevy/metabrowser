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
import random
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Generator
from pathlib import Path
from typing import cast

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

    def ask(self, command: str) -> str:
        """Send one command and return the owner's one-line reply."""

        self.send(command)
        assert self.process.stdout is not None
        return self.process.stdout.readline().strip()

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
    elif role == "driven":
        _driven_owner(path)
    elif role == "wal-fill":
        # Write many pages into -wal with no checkpoint, then die, leaving -wal and -shm.
        connection = sqlite3.connect(path, isolation_level=None)
        connection.execute("PRAGMA wal_autocheckpoint=0")
        connection.execute("UPDATE t SET v = 'rewritten ' || id || ' ' || hex(randomblob(40))")
        print("ready", flush=True)
        os._exit(0)
    elif role == "checkpoint":
        connection = sqlite3.connect(path, isolation_level=None)
        print("ready", flush=True)
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        print("checkpointed", flush=True)
        sys.stdin.readline()
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


def _driven_owner(path: Path) -> None:
    """An owner with no busy timeout that runs one command per stdin line and reports it."""

    connection = sqlite3.connect(path, isolation_level=None, timeout=0)
    connection.execute("PRAGMA busy_timeout=0")
    connection.execute("PRAGMA wal_autocheckpoint=0")
    print("ready", flush=True)
    for line in sys.stdin:
        command, _, argument = line.strip().partition(" ")
        try:
            if command == "commit":
                connection.execute("INSERT INTO small(v) VALUES ('owner')")
                reply = "ok"
            elif command == "fill":
                connection.execute("BEGIN")
                connection.execute(
                    "WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n WHERE i < ?) "
                    "INSERT INTO big(v) SELECT hex(randomblob(500)) FROM n",
                    (int(argument),),
                )
                connection.execute("COMMIT")
                reply = "ok"
            elif command == "restart":
                busy, frames, done = connection.execute("PRAGMA wal_checkpoint(RESTART)").fetchone()
                reply = f"ok busy={busy} frames={frames} checkpointed={done}"
            elif command == "close":
                connection.close()
                print("closed", flush=True)
                return
            else:
                reply = f"unknown {command}"
        except sqlite3.Error as exc:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            reply = f"error {_error(exc)}"
        print(reply, flush=True)


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
    out["lock_cancelled_by_a_closed_handle"] = _lock_cancellation(scratch)
    out["interrupted_checkpoint"] = _interrupted_checkpoint(scratch)
    out["hard_link_hides_a_hot_journal"] = _hard_link_hot_journal(scratch)
    out["persist_journal_at_rest"] = _persist_journal_at_rest(scratch)
    return out


def _changed_rows(db: Path, query: str = "mode=ro&immutable=1") -> Result:
    try:
        connection = sqlite3.connect(_uri(db, query), uri=True, timeout=0)
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
        case: Result = {}
        # Each access mode gets its own freshly staged folder, so one mode's read cannot
        # leave a sidecar the other then sees.
        for mode, query in (("mode_ro", "mode=ro"), ("immutable", "mode=ro&immutable=1")):
            with _case(scratch, f"{name}-{mode}") as folder:
                db = folder / "app.db"
                _make_db(db, wal=True)
                Owner("wal-commits", str(db), "5").finish("crash")
                if drop_shm:
                    (folder / "app.db-shm").unlink()
                if read_only:
                    _make_read_only(folder)
                shm = folder / "app.db-shm"
                shm_before = _digest(shm)
                case["before"] = _listing(folder)
                case[mode] = _read(db, query)
                if mode == "mode_ro":
                    case["shm_rewritten_by_mode_ro"] = (
                        shm_before is not None and _digest(shm) != shm_before
                    )
        out[name] = case
    return out


def _open_and_close(path: Path, opener: str) -> None:
    """Read 100 bytes of *path* from this process, from another process, or not at all."""

    if opener == "this_process":
        with path.open("rb") as handle:
            handle.read(100)
    elif opener == "another_process":
        subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                "import sys; open(sys.argv[1], 'rb').read(100)",
                str(path),
            ],
            check=True,
        )


LOCK_OPENERS = ("no_one", "another_process", "this_process")


def _lock_cancellation(scratch: Path) -> Result:
    """Whether a file handle opened and closed beside a reader's connection drops its locks.

    POSIX record locks belong to a process and a file, so closing any handle on the file
    releases every lock the process holds on it. The reader is in this process; the owner,
    with no busy timeout, is in another.
    """

    out: Result = {}
    rollback: Result = {}
    for opener in LOCK_OPENERS:
        with _case(scratch, f"lock-rollback-{opener}") as folder:
            db = folder / "app.db"
            _make_owner_tables(db, wal=False)
            owner = Owner("driven", str(db))
            reader = sqlite3.connect(_uri(db, "mode=ro"), uri=True, isolation_level=None, timeout=0)
            reader.execute("BEGIN")
            reader.execute("SELECT count(*) FROM small").fetchone()
            _open_and_close(db, opener)
            rollback[f"main_file_opened_by_{opener}"] = {
                "owner_commit_during_read": owner.ask("commit")
            }
            reader.execute("COMMIT")
            reader.close()
            owner.finish("close")
    out["rollback_reader_inside_a_read"] = rollback

    wal: Result = {}
    for opener in LOCK_OPENERS:
        with _case(scratch, f"lock-wal-{opener}") as folder:
            db = folder / "app.db"
            _make_owner_tables(db, wal=True)
            owner = Owner("driven", str(db))
            owner.ask("fill 2000")
            reader = sqlite3.connect(_uri(db, "mode=ro"), uri=True, isolation_level=None, timeout=0)
            reader.execute("BEGIN")
            reader.execute("SELECT count(*) FROM small").fetchone()
            first = owner.ask("restart")
            _open_and_close(folder / "app.db-shm", opener)
            second = owner.ask("restart")
            refill = owner.ask("fill 2000")
            try:
                rows = reader.execute("SELECT count(*) FROM big").fetchone()[0]
                check = reader.execute("PRAGMA integrity_check").fetchone()[0]
                reader_saw: Result = {"big_rows": rows, "integrity_check": check}
            except sqlite3.Error as exc:
                reader_saw = {"error": _error(exc), "message": str(exc)}
            with contextlib.suppress(sqlite3.Error):
                reader.execute("COMMIT")
            reader.close()
            owner.finish("close")
            wal[f"shm_opened_by_{opener}"] = {
                "restart_before_open": first,
                "restart_after_open": second,
                "owner_rewrites_log": refill,
                "reader_snapshot_of_2000_rows": reader_saw,
            }
    out["wal_reader_inside_a_read"] = wal
    return out


def _make_owner_tables(db: Path, *, wal: bool) -> None:
    connection = sqlite3.connect(db)
    if wal:
        connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("CREATE TABLE small(id INTEGER PRIMARY KEY, v TEXT)")
    connection.execute("CREATE TABLE big(id INTEGER PRIMARY KEY, v TEXT)")
    connection.executemany("INSERT INTO small(v) VALUES (?)", [(f"row {i}",) for i in range(10)])
    connection.commit()
    connection.close()


INTERRUPTED_CHECKPOINT_ROWS = 400_000
# Milliseconds after the checkpoint starts at which its process is killed.
INTERRUPTED_CHECKPOINT_KILL_MS = (5, 10, 15, 20, 25, 30, 40, 60, 100)


def _interrupted_checkpoint(scratch: Path) -> Result:
    """A checkpoint killed part-way leaves the main file torn; the log still covers it."""

    out: Result = {}
    for kill_ms in INTERRUPTED_CHECKPOINT_KILL_MS:
        with _case(scratch, f"interrupted-checkpoint-{kill_ms}") as folder:
            db = folder / "app.db"
            _make_db(db, wal=True, rows=INTERRUPTED_CHECKPOINT_ROWS)
            Owner("wal-fill", str(db)).process.wait(timeout=120)
            checkpointer = Owner("checkpoint", str(db))
            time.sleep(kill_ms / 1000)
            checkpointer.process.kill()
            checkpointer.process.wait(timeout=60)
            # What a copy or a sync folder delivers: the main file and its log, no -shm.
            (folder / "app.db-shm").unlink(missing_ok=True)
            before = _listing(folder)
            copy_folder = scratch / f"private-copy-{kill_ms}"
            copy_folder.mkdir()
            shutil.copy2(db, copy_folder / "app.db")
            shutil.copy2(folder / "app.db-wal", copy_folder / "app.db-wal")
            out[f"killed_after_{kill_ms}_ms"] = {
                "before": before,
                "immutable_main_file_alone": _checked_read(db, "mode=ro&immutable=1"),
                "mode_ro_on_a_private_copy_with_its_log": _checked_read(
                    copy_folder / "app.db", "mode=ro"
                ),
                "after": _listing(folder),
            }
            shutil.rmtree(copy_folder)
    return out


def _checked_read(db: Path, query: str) -> Result:
    """Rows, rewritten rows, and the integrity check through one access mode."""

    try:
        connection = sqlite3.connect(_uri(db, query), uri=True, timeout=0)
        try:
            rows, rewritten = connection.execute(
                "SELECT count(*), sum(v LIKE 'rewritten %') FROM t"
            ).fetchone()
            check = connection.execute("PRAGMA quick_check").fetchone()[0]
        finally:
            connection.close()
    except sqlite3.Error as exc:
        return {"error": _error(exc), "message": str(exc)}
    return {"rows": rows, "rewritten_rows": rewritten, "quick_check": check}


def _hard_link_hot_journal(scratch: Path) -> Result:
    """A killed writer's journal sits beside one name; a second hard link cannot see it."""

    with _case(scratch, "hard-link-hot-journal") as folder:
        db = folder / "app.db"
        _make_db(db, wal=False, rows=20_000)
        Owner("interrupted-write", str(db)).process.wait(timeout=60)
        hard = folder / "hard.db"
        os.link(db, hard)
        before_fingerprint = _fingerprint(hard)
        hard_immutable = _changed_rows(hard)
        return {
            "nlink": db.stat().st_nlink,
            "before": _listing(folder),
            "mode_ro_through_app_db": _count(db, "mode=ro"),
            "mode_ro_through_hard_db_changed_rows_of_20000": _changed_rows(hard, "mode=ro"),
            "immutable_through_hard_db_changed_rows_of_20000": hard_immutable,
            "validation_passes_through_hard_db": _fingerprint(hard) == before_fingerprint
            and not before_fingerprint[4],
            "after": _listing(folder),
        }


def _persist_journal_at_rest(scratch: Path) -> Result:
    """``journal_mode=PERSIST`` keeps a non-empty journal between transactions."""

    with _case(scratch, "persist-journal") as folder:
        db = folder / "app.db"
        connection = sqlite3.connect(db)
        connection.execute("PRAGMA journal_mode=PERSIST")
        connection.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, v TEXT)")
        connection.executemany("INSERT INTO t(v) VALUES (?)", [(f"row {i}",) for i in range(100)])
        connection.commit()
        connection.close()
        journal = folder / "app.db-journal"
        head = journal.read_bytes()[:28]
        return {
            "journal_bytes": journal.stat().st_size,
            "header_all_zero": head == bytes(len(head)),
            "mode_ro": _read(db, "mode=ro"),
        }


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
# The viewer waits a random interval in this range between reads, from a fixed seed, so
# its reads do not lock into phase with an owner that commits on a fixed period.
CONTENTION_VIEWER_INTERVAL_S = (0.15, 0.35)
CONTENTION_SEED = 617
# Seconds an owner waits between commits: back to back, an application that writes two
# hundred times a second, and one that writes twenty times a second.
CONTENTION_OWNER_PAUSES = {"back_to_back": 0.0, "every_5_ms": 0.005, "every_50_ms": 0.05}

KEY_PAGE = "SELECT * FROM t ORDER BY id LIMIT 100"
UNINDEXED_SORT_PAGE = "SELECT * FROM t ORDER BY b, a, id LIMIT 100"
COUNT_STAR = "SELECT count(*) FROM t"
CAPPED_COUNT = "SELECT count(*) FROM (SELECT 1 FROM t LIMIT 1000001)"

# The plan's policy for a rollback-journal database: how long a read may wait for the
# owner's journal to clear or for a validated read to succeed before it takes a lock,
# and the backoff between attempts.
POLICY_DEADLINE_S = 0.25
POLICY_BACKOFF_S = (0.001, 0.016)

Read = Callable[[Path], str]


def suite_contention(scratch: Path) -> Result:
    """An owner committing with no busy timeout while a viewer reads a rollback database."""

    reads: dict[str, Read | None] = {
        "none": None,
        "locked_key_ordered_page": lambda db: _locked_read(db, [KEY_PAGE]),
        "locked_count_star": lambda db: _locked_read(db, [COUNT_STAR]),
        "locked_capped_count": lambda db: _locked_read(db, [CAPPED_COUNT]),
        "locked_unindexed_sort_page": lambda db: _locked_read(db, [UNINDEXED_SORT_PAGE]),
        "validated_key_ordered_page": lambda db: _validated_read(db, [KEY_PAGE]),
        "validated_unindexed_sort_page": lambda db: _validated_read(db, [UNINDEXED_SORT_PAGE]),
        "review_a_policy_page_and_capped_count": lambda db: _review_a_policy(
            db, [KEY_PAGE, CAPPED_COUNT]
        ),
        "plan_policy_key_ordered_page_and_capped_count": lambda db: _plan_policy(
            db, [KEY_PAGE, CAPPED_COUNT]
        ),
        "plan_policy_unindexed_sort_page_and_capped_count": lambda db: _plan_policy(
            db, [UNINDEXED_SORT_PAGE, CAPPED_COUNT]
        ),
    }
    out: Result = {
        "viewer_interval_s": list(CONTENTION_VIEWER_INTERVAL_S),
        "policy_deadline_s": POLICY_DEADLINE_S,
    }
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


def _contend(db: Path, reads: dict[str, Read | None], pause: float) -> Result:
    out: Result = {}
    for name, read in reads.items():
        jitter = random.Random(CONTENTION_SEED)
        owner = Owner("commit-loop", str(db), str(CONTENTION_SECONDS), str(pause))
        outcomes: dict[str, int] = {}
        deadline = time.monotonic() + CONTENTION_SECONDS
        while time.monotonic() < deadline:
            if read is not None:
                outcome = read(db)
                outcomes[outcome] = outcomes.get(outcome, 0) + 1
            time.sleep(jitter.uniform(*CONTENTION_VIEWER_INTERVAL_S))
        result: Result = json.loads(owner.finish("report"))
        result["viewer_reads"] = outcomes
        out[name] = result
    return out


def _run(connection: sqlite3.Connection, statements: list[str]) -> None:
    for sql in statements:
        connection.execute(sql).fetchall()


def _locked_read(db: Path, statements: list[str]) -> str:
    """A ``mode=ro`` read, which takes a shared lock for as long as it runs."""

    try:
        connection = sqlite3.connect(_uri(db, "mode=ro"), uri=True, timeout=0)
        try:
            _run(connection, statements)
        finally:
            connection.close()
    except sqlite3.Error as exc:
        return f"locked_failed_{_error(exc)}"
    return "locked"


def _fingerprint(db: Path) -> tuple[int, int, int, bytes, bool]:
    """Identity, size, mtime, the header's change counter, and whether a live journal exists.

    A journal counts when it holds bytes and its header is not zeroed: ``journal_mode=PERSIST``
    keeps a zeroed journal between transactions, and SQLite does not treat that one as hot.
    """

    stat = db.stat()
    with db.open("rb") as handle:
        handle.seek(24)
        counter = handle.read(4)
    return (stat.st_ino, stat.st_size, stat.st_mtime_ns, counter, _live_journal(db))


def _live_journal(db: Path) -> bool:
    try:
        with db.with_name(db.name + "-journal").open("rb") as handle:
            first = handle.read(1)
    except FileNotFoundError:
        return False
    return first not in (b"", b"\x00")


def _validated_read(db: Path, statements: list[str]) -> str:
    """A lock-free ``immutable=1`` read, accepted only if nothing changed across it."""

    before = _fingerprint(db)
    if before[4]:
        return "journal_present"
    try:
        connection = sqlite3.connect(_uri(db, "mode=ro&immutable=1"), uri=True)
        try:
            _run(connection, statements)
        finally:
            connection.close()
    except sqlite3.Error:
        return "validation_failed"
    return "validated" if _fingerprint(db) == before else "validation_failed"


def _review_a_policy(db: Path, statements: list[str]) -> str:
    """The policy review A's dispositions wrote: a journal means ``mode=ro`` at once;
    otherwise a validated read, one retry, then ``mode=ro``."""

    if _live_journal(db):
        return _locked_read(db, statements)
    for _ in range(2):
        if _validated_read(db, statements) == "validated":
            return "validated"
    return _locked_read(db, statements)


def _plan_policy(db: Path, statements: list[str]) -> str:
    """The plan's policy: wait out a journal or a failed validation with backoff until the
    deadline, then lock for the key-ordered page alone, with no sort and no count."""

    deadline = time.monotonic() + POLICY_DEADLINE_S
    delay, longest = POLICY_BACKOFF_S
    while True:
        if _validated_read(db, statements) == "validated":
            return "validated"
        if time.monotonic() + delay >= deadline:
            break
        time.sleep(delay)
        delay = min(delay * 2, longest)
    outcome = _locked_read(db, [KEY_PAGE])
    return "locked_key_page_only" if outcome == "locked" else outcome


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
        out["median_ms_of_5"] = {
            name: _median_ms(connection, sql)
            for name, sql in (
                ("count_star", "SELECT count(*) FROM big"),
                ("capped_count", "SELECT count(*) FROM (SELECT 1 FROM big LIMIT 1000001)"),
                ("max_rowid", "SELECT max(rowid) FROM big"),
            )
        }

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
    out["interrupt_stops_one_count_star"] = _interrupt_count(scratch)
    return out


def _median_ms(connection: sqlite3.Connection, sql: str) -> float:
    times: list[float] = []
    for _ in range(5):
        started = time.perf_counter()
        connection.execute(sql).fetchone()
        times.append((time.perf_counter() - started) * 1000)
    return round(sorted(times)[2], 2)


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


INTERRUPT_COUNT_ROWS = 20_000_000
INTERRUPT_AFTER_S = 0.01


def _interrupt_count(scratch: Path) -> Result:
    """A watchdog's ``interrupt()`` against one ``count(*)`` already running."""

    with _case(scratch, "interrupt") as folder:
        connection = sqlite3.connect(folder / "huge.db", check_same_thread=False)
        connection.execute("CREATE TABLE huge(id INTEGER PRIMARY KEY)")
        connection.execute(
            "WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n WHERE i < ?) "
            "INSERT INTO huge SELECT i FROM n",
            (INTERRUPT_COUNT_ROWS,),
        )
        connection.commit()
        outcome: Result = {
            "rows": INTERRUPT_COUNT_ROWS,
            "uninterrupted_ms": _median_ms(connection, "SELECT count(*) FROM huge"),
            "interrupt_after_ms": INTERRUPT_AFTER_S * 1000,
        }
        started = threading.Event()

        def run() -> None:
            began = time.perf_counter()
            started.set()
            try:
                connection.execute("SELECT count(*) FROM huge").fetchone()
                outcome["finished_ms"] = round((time.perf_counter() - began) * 1000, 1)
            except sqlite3.OperationalError as exc:
                outcome["error"] = str(exc)
                outcome["stopped_after_ms"] = round((time.perf_counter() - began) * 1000, 1)

        worker = threading.Thread(target=run)
        worker.start()
        started.wait()
        time.sleep(INTERRUPT_AFTER_S)
        connection.interrupt()
        worker.join()
        connection.close()
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
    "length_of_text_cast_to_blob": "SELECT length(CAST(v AS BLOB)) FROM big",
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
    out["views_under_the_authorizer"] = _views_under_authorizer()
    out["oversize_value"] = _oversize_value()
    out["storage_encoding"] = _storage_encoding(scratch)
    connection.close()
    return out


KEYSET_VALUES: tuple[object, ...] = (
    None, 1, 2, 10, 2.5, -3, "1", "10", "abc", "B", "", b"\x00", b"z", 1e300, "2.5", " 5", "0x10", "1e3", " 7 "
)  # fmt: skip


def _keyset(connection: sqlite3.Connection) -> Result:
    """Page an indexed mixed-type column with nulls, in both directions, and compare the
    pages with one ORDER BY."""

    out: Result = {}
    for declared in ("TEXT", "INTEGER", "REAL", "NUMERIC", "BLOB", "", "TEXT COLLATE NOCASE"):
        connection.execute("DROP TABLE IF EXISTS k")
        connection.execute(f"CREATE TABLE k(id INTEGER PRIMARY KEY, s {declared})")
        connection.execute("CREATE INDEX k_s ON k(s)")
        connection.executemany(
            "INSERT INTO k(s) VALUES (?)",
            [(KEYSET_VALUES[(i * 7) % len(KEYSET_VALUES)],) for i in range(500)],
        )
        ascending = [row[0] for row in connection.execute("SELECT id FROM k ORDER BY s, id")]
        descending = [
            row[0] for row in connection.execute("SELECT id FROM k ORDER BY s DESC, id DESC")
        ]
        descending_row_value = _pages(connection, _row_value_page_descending)
        out[declared or "no type"] = {
            "ascending_row_value_predicate": _pages(connection, _row_value_page) == ascending,
            "ascending_row_value_with_null_branch": _pages(connection, _null_branch_page)
            == ascending,
            "ascending_by_region": _pages(connection, _region_page_ascending) == ascending,
            "descending_row_value_rows_of_500": len(descending_row_value),
            "descending_by_region": _pages(connection, _region_page_descending) == descending,
        }
    out["null_heavy_page_opcodes"] = _null_heavy_opcodes()
    return out


Page = list[tuple[int, object]]
Cursor = tuple[int, object] | None
KEYSET_PAGE = 7


def _row_value_page(connection: sqlite3.Connection, last: Cursor) -> Page:
    if last is None:
        return connection.execute("SELECT id, s FROM k ORDER BY s, id LIMIT 7").fetchall()
    return connection.execute(
        "SELECT id, s FROM k WHERE (s, id) > (?, ?) ORDER BY s, id LIMIT 7", (last[1], last[0])
    ).fetchall()


def _row_value_page_descending(connection: sqlite3.Connection, last: Cursor) -> Page:
    if last is None:
        return connection.execute("SELECT id, s FROM k ORDER BY s DESC, id DESC LIMIT 7").fetchall()
    return connection.execute(
        "SELECT id, s FROM k WHERE (s, id) < (?, ?) ORDER BY s DESC, id DESC LIMIT 7",
        (last[1], last[0]),
    ).fetchall()


def _null_branch_page(connection: sqlite3.Connection, last: Cursor) -> Page:
    """Review A's form: a null cursor continues on its own branch of one predicate."""

    if last is None or last[1] is not None:
        return _row_value_page(connection, last)
    return connection.execute(
        "SELECT id, s FROM k WHERE (s IS NULL AND id > ?) OR s IS NOT NULL ORDER BY s, id LIMIT 7",
        (last[0],),
    ).fetchall()


def _query(connection: sqlite3.Connection, where: str, order: str, *params: object) -> Page:
    sql = f"SELECT id, s FROM k WHERE {where} ORDER BY {order} LIMIT ?"
    return connection.execute(sql, (*params, KEYSET_PAGE)).fetchall()


def _region_page_ascending(connection: sqlite3.Connection, last: Cursor) -> Page:
    """Nulls sort first: page the null region by key, then the rest by row value."""

    if last is not None and last[1] is not None:
        return _query(connection, "(s, id) > (?, ?)", "s, id", last[1], last[0])
    if last is None:
        rows = _query(connection, "s IS NULL", "id")
    else:
        rows = _query(connection, "s IS NULL AND id > ?", "id", last[0])
    if len(rows) < KEYSET_PAGE:
        rows += _query(connection, "s IS NOT NULL", "s, id")[: KEYSET_PAGE - len(rows)]
    return rows


def _region_page_descending(connection: sqlite3.Connection, last: Cursor) -> Page:
    """Nulls sort last: page the rest by row value, then the null region by key."""

    if last is not None and last[1] is None:
        return _query(connection, "s IS NULL AND id < ?", "id DESC", last[0])
    if last is None:
        rows = _query(connection, "s IS NOT NULL", "s DESC, id DESC")
    else:
        rows = _query(connection, "(s, id) < (?, ?)", "s DESC, id DESC", last[1], last[0])
    if len(rows) < KEYSET_PAGE:
        rows += _query(connection, "s IS NULL", "id DESC")[: KEYSET_PAGE - len(rows)]
    return rows


def _pages(
    connection: sqlite3.Connection, page: Callable[[sqlite3.Connection, Cursor], Page]
) -> list[int]:
    ids: list[int] = []
    rows = page(connection, None)
    while rows and len(ids) <= 500:
        ids.extend(row[0] for row in rows)
        rows = page(connection, rows[-1])
    return ids


NULL_HEAVY_ROWS = 200_000


def _null_heavy_opcodes() -> Result:
    """Opcodes for one 100-row page deep in a sparse indexed column: half its rows are null."""

    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE n(id INTEGER PRIMARY KEY, s INTEGER)")
    connection.execute(
        "WITH RECURSIVE r(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM r WHERE i < ?) "
        "INSERT INTO n SELECT i, CASE WHEN i % 2 THEN NULL ELSE (i * 7919) % 100003 END FROM r",
        (NULL_HEAVY_ROWS,),
    )
    connection.execute("CREATE INDEX n_s ON n(s)")
    null_cursor, value_cursor = 150_001, (50_000, 0)
    pages = {
        "ascending_null_branch_one_predicate": (
            "SELECT id, s FROM n WHERE (s IS NULL AND id > ?) OR s IS NOT NULL "
            "ORDER BY s, id LIMIT 100",
            (null_cursor,),
        ),
        "ascending_null_region_alone": (
            "SELECT id, s FROM n WHERE s IS NULL AND id > ? ORDER BY id LIMIT 100",
            (null_cursor,),
        ),
        "ascending_first_non_null_page": (
            "SELECT id, s FROM n WHERE s IS NOT NULL ORDER BY s, id LIMIT 100",
            (),
        ),
        "ascending_non_null_continuation": (
            "SELECT id, s FROM n WHERE (s, id) > (?, ?) ORDER BY s, id LIMIT 100",
            value_cursor,
        ),
        "descending_mirrored_one_predicate": (
            "SELECT id, s FROM n WHERE (s, id) < (?, ?) OR s IS NULL "
            "ORDER BY s DESC, id DESC LIMIT 100",
            value_cursor,
        ),
        "descending_non_null_continuation": (
            "SELECT id, s FROM n WHERE (s, id) < (?, ?) ORDER BY s DESC, id DESC LIMIT 100",
            value_cursor,
        ),
        "descending_null_region_alone": (
            "SELECT id, s FROM n WHERE s IS NULL AND id < ? ORDER BY id DESC LIMIT 100",
            (null_cursor,),
        ),
    }
    out: Result = {
        name: _opcodes(connection, sql, params)["opcodes"] for name, (sql, params) in pages.items()
    }
    connection.close()
    return out


# The functions an adapter's own SQL calls, as review A's authorizer rule admitted.
ADAPTER_FUNCTIONS = frozenset({"count", "octet_length", "typeof"})


def _authorizer(
    *, admit_views: bool
) -> Callable[[int, str | None, str | None, str | None, str | None], int]:
    """Reads only; functions from the adapter's list, and inside a view any function if
    *admit_views*. The last argument names the innermost view or trigger a call comes from."""

    def check(
        action: int, _arg1: str | None, arg2: str | None, _db: str | None, source: str | None
    ) -> int:
        if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ):
            return sqlite3.SQLITE_OK
        in_view = admit_views and source is not None
        if action == sqlite3.SQLITE_FUNCTION and (
            (arg2 or "").lower() in ADAPTER_FUNCTIONS or in_view
        ):
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    return check


def _views_under_authorizer() -> Result:
    """A view that calls built-in functions, read under each authorizer and schema setting."""

    out: Result = {}
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT, at INTEGER)")
    connection.execute("INSERT INTO t VALUES (1, 'ada', 0), (2, 'bo', 1700000000)")
    connection.execute(
        "CREATE VIEW v AS SELECT id, upper(name) AS u, strftime('%Y', at, 'unixepoch') AS y FROM t"
    )
    connection.execute("CREATE VIEW unsafe AS SELECT fts3_tokenizer('simple') AS x")
    connection.execute("PRAGMA trusted_schema=OFF")
    for name, authorizer in (
        ("no_authorizer", None),
        ("adapter_functions_only", _authorizer(admit_views=False)),
        ("adapter_functions_and_any_function_inside_a_view", _authorizer(admit_views=True)),
    ):
        connection.set_authorizer(authorizer)
        reads: Result = {}
        for sql in ("SELECT * FROM v", "SELECT * FROM unsafe", "SELECT upper('direct')"):
            try:
                reads[sql] = f"{len(connection.execute(sql).fetchall())} rows"
            except sqlite3.Error as exc:
                reads[sql] = f"refused: {exc}"
        out[name] = reads
    connection.close()
    return out


OVERSIZE_LIMIT = 1_000_000


def _oversize_value() -> Result:
    """One value past ``SQLITE_LIMIT_LENGTH`` among three rows, under each kind of statement."""

    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, v TEXT)")
    connection.execute(
        "INSERT INTO t VALUES (1, 'a needle'), (2, ?), (3, 'needle b')", ("x" * 3_000_000,)
    )
    connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, OVERSIZE_LIMIT)
    limit = OVERSIZE_LIMIT
    statements = {
        "search": "SELECT id FROM t WHERE v LIKE '%needle%'",
        "sort": "SELECT id FROM t ORDER BY v, id",
        "search_guarded_by_size": f"SELECT id FROM t WHERE octet_length(v) <= {limit} AND v LIKE '%needle%'",
        "select_guarded_by_size": f"SELECT id, CASE WHEN octet_length(v) <= {limit} THEN v END IS NULL FROM t",
        "skipped_values_counted": f"SELECT count(*) FROM t WHERE octet_length(v) > {limit}",
    }
    out: Result = {}
    for name, sql in statements.items():
        try:
            rows = connection.execute(sql).fetchall()
            out[name] = [" ".join(str(cell) for cell in row) for row in rows]
        except sqlite3.Error as exc:
            out[name] = f"refused: {exc}"
    connection.close()
    return out


def _storage_encoding(scratch: Path) -> Result:
    """``blobopen`` reads the stored bytes, which are UTF-16 in a UTF-16 database."""

    out: Result = {}
    text = "héllo wörld"
    with _case(scratch, "utf16") as folder:
        db = folder / "utf16.db"
        connection = sqlite3.connect(db)
        connection.execute("PRAGMA encoding='UTF-16le'")
        connection.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, v TEXT)")
        connection.execute("INSERT INTO t VALUES (1, ?)", (text,))
        connection.commit()
        with connection.blobopen("t", "v", 1, readonly=True) as blob:
            head = blob.read(8)
        characters, octets = connection.execute(
            "SELECT length(v), octet_length(v) FROM t"
        ).fetchone()
        out["utf16le"] = {
            "encoding": connection.execute("PRAGMA encoding").fetchone()[0],
            "characters": characters,
            "octet_length": octets,
            "blobopen_first_8_bytes": head.hex(" "),
        }
        connection.close()
    cut = "aé".encode()[:2]
    out["utf8_preview_cut_inside_a_character"] = {
        "bytes": cut.hex(" "),
        "decoded_with_replacement": cut.decode("utf-8", errors="replace"),
        "trailing_partial_trimmed": _trim_partial(cut).decode("utf-8", errors="strict"),
    }
    return out


def _trim_partial(data: bytes) -> bytes:
    """Drop an incomplete UTF-8 sequence at the end of a cut, so only real errors show."""

    for back in range(1, min(4, len(data)) + 1):
        lead = data[-back]
        if lead & 0xC0 != 0x80:
            width = 2 if lead >= 0xC0 else 1
            width = 3 if lead >= 0xE0 else width
            width = 4 if lead >= 0xF0 else width
            return data[:-back] if width > back else data
    return data


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
        (out / f"{name}.json").write_text(_biome_json(record) + "\n", encoding="utf-8")
        print(f"{name}: {record['seconds']} s")


JSON_LINE_WIDTH = 100  # The repository's Biome `lineWidth`, so the results pass `biome check`.


def _biome_json(value: object, indent: int = 0, column: int = 0) -> str:
    """Serialize *value* as Biome formats JSON: keys sorted, objects expanded, and a list of
    scalars on one line when it fits within :data:`JSON_LINE_WIDTH`."""

    pad = " " * (indent + 2)
    if isinstance(value, dict) and value:
        items = sorted(cast(dict[str, object], value).items())
        lines = [
            f"{pad}{json.dumps(key)}: {_biome_json(item, indent + 2, len(pad) + len(json.dumps(key)) + 2)}"
            for key, item in items
        ]
        return "{\n" + ",\n".join(lines) + "\n" + " " * indent + "}"
    if isinstance(value, list) and value:
        elements = cast(list[object], value)
        if all(not isinstance(element, (dict, list)) for element in elements):
            inline = "[" + ", ".join(json.dumps(element) for element in elements) + "]"
            if column + len(inline) + 1 <= JSON_LINE_WIDTH:
                return inline
        lines = [pad + _biome_json(element, indent + 2, len(pad)) for element in elements]
        return "[\n" + ",\n".join(lines) + "\n" + " " * indent + "]"
    return json.dumps(value)


SUITE_FUNCTIONS: dict[str, Callable[[Path], Result]] = {
    "access": suite_access,
    "contention": suite_contention,
    "budget": suite_budget,
    "encoding": suite_encoding,
    "generation": suite_generation,
}


if __name__ == "__main__":
    main()
