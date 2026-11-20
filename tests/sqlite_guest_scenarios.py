"""Nondestructive access, lock-hazard, and contention scenarios for SQLite guest reads.

Each scenario stages a database with a real owner in a second process, reads it the way
Metabrowser does (through ``metabrowser.sqlite_access``, and through the reader
processes of ``metabrowser.sqlite_readers`` where the scenario is about them), and
checks what the read answered and what it left beside the file: the names, and the main
file's, journal's, and log's bytes, before and after. A ``-shm`` is the log's shared
index, whose read marks every reader updates, so only whether it exists is compared.

``tests/test_sqlite_guest_access.py`` runs each scenario in a process of its own as an
unprivileged user, since a superuser ignores the folder and file permissions several
scenarios depend on: as the test's own user when that is not root, and as ``nobody``
otherwise. Usage::

    python tests/sqlite_guest_scenarios.py <scenario> <empty folder>

It prints ``ok <scenario>`` and a JSON line of what it measured, and exits 1 on a
failed check. The cases grow from `explorations/sqlite-guest-reads/README.md#access`.
"""

from __future__ import annotations

import hashlib
import json
import os
import signal
import sqlite3
import stat
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from metabrowser import sqlite_access
from metabrowser.sqlite_access import SqliteAccessError, read, sqlite_generation
from metabrowser.sqlite_readers import ReaderPool

ROWS = 100
_OWNER = r"""
import json, sqlite3, sys
db = None
path = sys.argv[1]
for line in sys.stdin:
    command, _, rest = line.strip().partition(" ")
    answer = None
    try:
        if command == "open":
            db = sqlite3.connect(path, isolation_level=None, timeout=0)
            db.execute(f"PRAGMA journal_mode={rest}")
            db.execute("PRAGMA wal_autocheckpoint=0")
        elif command == "busy":
            db.execute(f"PRAGMA busy_timeout={int(rest)}")
        elif command == "exec":
            db.executescript(rest)
        elif command == "query":
            answer = db.execute(rest).fetchall()
        elif command == "spill":
            db.execute("PRAGMA cache_size=1")
            db.execute("BEGIN")
            db.execute(rest)
        elif command == "close":
            db.close()
            db = None
        print(json.dumps({"ok": True, "answer": answer}), flush=True)
    except sqlite3.Error as exc:
        print(json.dumps({"ok": False, "error": str(exc), "code": exc.sqlite_errorcode}), flush=True)
"""


class Owner:
    """An application that owns a database, in a process of its own."""

    def __init__(self, path: Path) -> None:
        self.process = subprocess.Popen(
            [sys.executable, "-c", _OWNER, str(path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )

    def send(self, command: str) -> dict[str, Any]:
        assert self.process.stdin is not None and self.process.stdout is not None
        self.process.stdin.write(command.replace("\n", " ") + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError(f"the owner exited during {command!r}")
        return json.loads(line)

    def ok(self, command: str) -> Any:
        answer = self.send(command)
        if not answer["ok"]:
            raise RuntimeError(f"owner {command!r}: {answer}")
        return answer["answer"]

    def kill(self) -> None:
        self.process.kill()
        self.process.wait()

    def stop(self) -> None:
        if self.process.poll() is None:
            assert self.process.stdin is not None
            self.process.stdin.close()
            self.process.wait(timeout=10)


@contextmanager
def owner(path: Path, mode: str = "wal") -> Generator[Owner]:
    running = Owner(path)
    running.ok(f"open {mode}")
    try:
        yield running
    finally:
        if running.process.poll() is None:
            running.kill()


# ── Staging ────────────────────────────────────────────────────


def create(path: Path, mode: str = "wal", rows: int = ROWS) -> None:
    """A database of *rows* committed rows, in its main file, its owner closed."""
    with owner(path, mode) as app:
        app.ok("exec CREATE TABLE t(id INTEGER PRIMARY KEY, v TEXT)")
        app.ok(
            "exec WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i+1 FROM n WHERE i<"
            f"{rows}) INSERT INTO t(v) SELECT printf('row %d', i) FROM n"
        )
        app.ok("close")
        app.stop()
    age(path)


def age(*paths: Path) -> None:
    """Set modification times a minute back, past the racy window, as an owner that
    last wrote a while ago leaves them."""
    then = time.time() - 60
    for path in paths:
        if path.exists():
            os.utime(path, (then, then))


def crashed_with_frames(path: Path, extra: int = 5) -> None:
    """An owner that committed *extra* rows to its log and was killed: `-wal` and `-shm`
    stay beside the database."""
    create(path)
    with owner(path) as app:
        for index in range(extra):
            app.ok(f"exec INSERT INTO t(v) VALUES ('extra {index}')")
        app.kill()
    age(path, sidecar(path, "-wal"), sidecar(path, "-shm"))


def sidecar(path: Path, suffix: str) -> Path:
    return path.with_name(path.name + suffix)


def listing(folder: Path) -> dict[str, str]:
    """Every name in *folder* with a hash of its bytes; a `-shm` by its name alone."""
    out: dict[str, str] = {}
    for entry in sorted(folder.iterdir()):
        if entry.is_dir() or entry.name.endswith("-shm"):
            out[entry.name] = "present"
        else:
            out[entry.name] = hashlib.sha256(entry.read_bytes()).hexdigest()[:16]
    return out


def read_only(*paths: Path) -> None:
    for path in paths:
        mode = path.stat().st_mode
        path.chmod(mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def writable(folder: Path) -> None:
    for path in [folder, *folder.iterdir()]:
        path.chmod(path.stat().st_mode | stat.S_IWUSR)


def tear_checkpoint(path: Path) -> int:
    """Write the first half of the log's frames into the main file, as a checkpoint
    killed part-way leaves it, and remove `-shm`, as a copy or a sync folder delivers
    the pair. Returns the frames written."""
    wal = sidecar(path, "-wal").read_bytes()
    page_size = int.from_bytes(wal[8:12])
    frame = 24 + page_size
    frames = (len(wal) - 32) // frame
    written = frames // 2
    with open(path, "r+b") as main:
        for index in range(written):
            start = 32 + index * frame
            page = int.from_bytes(wal[start : start + 4])
            main.seek((page - 1) * page_size)
            main.write(wal[start + 24 : start + frame])
    sidecar(path, "-shm").unlink()
    age(path, sidecar(path, "-wal"))
    return written


# ── Reading ────────────────────────────────────────────────────


def count(connection: sqlite3.Connection) -> int:
    return int(connection.execute("SELECT count(*) FROM t").fetchone()[0])


def read_count(path: Path, scratch: Path, seconds: float = 2.0) -> tuple[int, sqlite_access.Access]:
    return read(path, count, deadline=time.monotonic() + seconds, scratch=scratch)


def scratch_folder(base: Path) -> Path:
    folder = base / "scratch"
    folder.mkdir(exist_ok=True)
    return folder


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def unchanged(before: dict[str, str], after: dict[str, str], what: str) -> None:
    check(before == after, f"{what}: the folder changed: {before} -> {after}")


# ── Scenarios ──────────────────────────────────────────────────

Result = dict[str, Any]
SCENARIOS: dict[str, Callable[[Path], Result]] = {}


def scenario(fn: Callable[[Path], Result]) -> Callable[[Path], Result]:
    SCENARIOS[fn.__name__] = fn
    return fn


@scenario
def idle_wal_creates_nothing(base: Path) -> Result:
    folder = base / "app"
    folder.mkdir()
    db = folder / "app.db"
    create(db)
    before = listing(folder)
    rows, access = read_count(db, scratch_folder(base))
    unchanged(before, listing(folder), "idle write-ahead-log database")
    check(rows == ROWS and access.plan.mode == "immutable", f"{rows} {access.plan}")
    return {"rows": rows, "mode": access.plan.mode}


@scenario
def idle_wal_just_closed_waits_out_the_racy_window(base: Path) -> Result:
    folder = base / "app"
    folder.mkdir()
    db = folder / "app.db"
    create(db)
    os.utime(db)  # as an owner that closed a moment ago leaves it
    before = listing(folder)
    rows, access = read_count(
        db, scratch_folder(base), seconds=sqlite_access.RACY_MTIME_SECONDS + 1.5
    )
    unchanged(before, listing(folder), "a database closed a moment ago")
    check(rows == ROWS and access.attempts > 1, f"{rows} after {access.attempts} attempts")
    return {"rows": rows, "waited": access.attempts > 1}


@scenario
def idle_wal_read_only_folder(base: Path) -> Result:
    folder = base / "app"
    folder.mkdir()
    db = folder / "app.db"
    create(db)
    read_only(db, folder)
    before = listing(folder)
    try:
        rows, access = read_count(db, scratch_folder(base))
    finally:
        writable(folder)
    unchanged(before, listing(folder), "read-only folder")
    check(rows == ROWS and access.plan.mode == "immutable", f"{rows} {access.plan}")
    return {"rows": rows}


@scenario
def live_owner_log_with_frames(base: Path) -> Result:
    folder = base / "app"
    folder.mkdir()
    db = folder / "app.db"
    create(db)
    with owner(db) as app:
        for index in range(5):
            app.ok(f"exec INSERT INTO t(v) VALUES ('extra {index}')")
        before = listing(folder)
        rows, access = read_count(db, scratch_folder(base))
        after = listing(folder)
        app.ok("close")
        app.stop()
    unchanged(before, after, "a live owner's log")
    check(rows == ROWS + 5 and access.plan.mode == "read_only", f"{rows} {access.plan}")
    return {"rows": rows, "mode": access.plan.mode}


@scenario
def owner_table_not_checkpointed(base: Path) -> Result:
    folder = base / "app"
    folder.mkdir()
    db = folder / "app.db"
    create(db)
    with owner(db) as app:
        app.ok("exec CREATE TABLE fresh(x); INSERT INTO fresh VALUES (1), (2)")
        value, access = read(
            db,
            lambda c: c.execute("SELECT count(*) FROM fresh").fetchone()[0],
            deadline=time.monotonic() + 2,
            scratch=scratch_folder(base),
        )
        app.ok("close")
        app.stop()
    check(value == 2, f"the owner's new table read {value} rows")
    return {"rows": value, "mode": access.plan.mode}


def _crashed(base: Path, *, keep_shm: bool, read_only_folder: bool) -> Result:
    folder = base / "app"
    folder.mkdir()
    db = folder / "app.db"
    crashed_with_frames(db)
    if not keep_shm:
        sidecar(db, "-shm").unlink()
    if read_only_folder:
        read_only(*folder.iterdir(), folder)
    before = listing(folder)
    try:
        rows, access = read_count(db, scratch_folder(base))
    finally:
        writable(folder)
    unchanged(before, listing(folder), "a crashed owner's log")
    expected = "read_only" if keep_shm else "private_copy"
    check(rows == ROWS + 5 and access.plan.mode == expected, f"{rows} {access.plan}")
    check(access.plan.state == "current", f"{access.plan}")
    return {"rows": rows, "mode": access.plan.mode}


@scenario
def crashed_owner_wal_and_shm(base: Path) -> Result:
    return _crashed(base, keep_shm=True, read_only_folder=False)


@scenario
def crashed_owner_wal_and_shm_read_only(base: Path) -> Result:
    return _crashed(base, keep_shm=True, read_only_folder=True)


@scenario
def crashed_owner_wal_without_shm(base: Path) -> Result:
    return _crashed(base, keep_shm=False, read_only_folder=False)


@scenario
def crashed_owner_wal_without_shm_read_only(base: Path) -> Result:
    return _crashed(base, keep_shm=False, read_only_folder=True)


def _rewritten(base: Path, db: Path) -> int:
    """A database every row of which its crashed owner rewrote in the log."""
    create(db, rows=20_000)
    with owner(db) as app:
        app.ok("exec UPDATE t SET v = 'rewritten ' || id")
        app.kill()
    return tear_checkpoint(db)


@scenario
def torn_checkpoint_reads_through_its_log(base: Path) -> Result:
    folder = base / "app"
    folder.mkdir()
    db = folder / "app.db"
    written = _rewritten(base, db)
    before = listing(folder)

    rows, access = read(
        db,
        lambda c: c.execute(
            "SELECT count(*) FROM t WHERE v >= 'rewritten ' AND v < 'rewrittf'"
        ).fetchone()[0],
        deadline=time.monotonic() + 5,
        scratch=scratch_folder(base),
    )
    unchanged(before, listing(folder), "a torn checkpoint")
    check(written > 0 and rows == 20_000, f"{rows} rows rewritten after {written} frames")
    check(access.plan.mode == "private_copy" and access.plan.state == "current", f"{access.plan}")
    return {"rewritten": rows, "frames_written": written}


@scenario
def owner_exits_between_look_and_open(base: Path) -> Result:
    folder = base / "app"
    folder.mkdir()
    db = folder / "app.db"
    create(db)
    app = Owner(db)
    app.ok("open wal")
    app.ok("exec INSERT INTO t(v) VALUES ('extra')")
    original = sqlite_access._connection

    @contextmanager
    def owner_closes_first(uri: str, **kwargs: Any) -> Generator[sqlite3.Connection]:
        # The owner checkpoints, removes its log and index, and exits after the look
        # chose a read through the log and before the connection opens.
        app.ok("close")
        app.stop()
        with original(uri, **kwargs) as connection:
            yield connection

    sqlite_access._connection = owner_closes_first
    try:
        rows, access = read_count(db, scratch_folder(base))
    finally:
        sqlite_access._connection = original
    check(rows == ROWS + 1, f"{rows}")
    check(len(access.notices) == 1 and "created" in access.notices[0], f"{access.notices}")
    return {"rows": rows, "notice": access.notices[0], "left": sorted(listing(folder))}


@scenario
def symlink_in_another_folder(base: Path) -> Result:
    folder = base / "app"
    elsewhere = base / "links"
    folder.mkdir()
    elsewhere.mkdir()
    db = folder / "app.db"
    create(db)
    link = elsewhere / "link.db"
    link.symlink_to(db)
    with owner(db) as app:
        app.ok("exec INSERT INTO t(v) VALUES ('extra')")
        before = listing(folder), listing(elsewhere)
        rows, access = read_count(link, scratch_folder(base))
        after = listing(folder), listing(elsewhere)
        app.ok("close")
        app.stop()
    unchanged(before[0], after[0], "the database's folder")
    unchanged(before[1], after[1], "the link's folder")
    check(rows == ROWS + 1 and access.plan.mode == "read_only", f"{rows} {access.plan}")
    return {"rows": rows}


def _another_name(base: Path, stage: Callable[[Path], None]) -> Result:
    folder = base / "app"
    folder.mkdir()
    db = folder / "app.db"
    stage(db)
    hard = folder / "hard.db"
    os.link(db, hard)
    before = listing(folder)
    try:
        rows, access = read_count(hard, scratch_folder(base))
        state, error = access.plan.state, None
    except SqliteAccessError as exc:
        rows, state, error = None, exc.state, str(exc)
    unchanged(before, listing(folder), "a second name")
    check(state == "another_name", f"read through a second name as {state}: {error}")
    return {"state": state, "rows": rows}


@scenario
def hard_link_to_live_wal(base: Path) -> Result:
    def stage(db: Path) -> None:
        crashed_with_frames(db)

    return _another_name(base, stage)


@scenario
def hard_link_to_hot_journal(base: Path) -> Result:
    def stage(db: Path) -> None:
        create(db, mode="delete", rows=20_000)
        hot_journal(db)

    return _another_name(base, stage)


@scenario
def hard_link_to_torn_checkpoint(base: Path) -> Result:
    def stage(db: Path) -> None:
        _rewritten(base, db)

    return _another_name(base, stage)


def hot_journal(db: Path) -> None:
    """A rollback-journal writer killed with half its rows written to the main file."""
    with owner(db, "delete") as app:
        app.ok("spill UPDATE t SET v = 'half ' || id")
        app.kill()
    age(db, sidecar(db, "-journal"))
    check(any(sidecar(db, "-journal").read_bytes()[:28]), "the journal is hot")


@scenario
def hot_journal_is_writer_busy(base: Path) -> Result:
    folder = base / "app"
    folder.mkdir()
    db = folder / "app.db"
    create(db, mode="delete", rows=20_000)
    hot_journal(db)
    before = listing(folder)
    try:
        read_count(db, scratch_folder(base), seconds=0.3)
    except SqliteAccessError as exc:
        state = exc.state
    else:
        state = "current"
    unchanged(before, listing(folder), "a hot journal")
    check(state == "writer_busy", f"a hot journal read as {state}")
    return {"state": state}


@scenario
def generation_follows_commits(base: Path) -> Result:
    folder = base / "app"
    folder.mkdir()
    db = folder / "app.db"
    create(db)
    seen = [sqlite_generation(db)]
    with owner(db) as app:
        app.ok("exec INSERT INTO t(v) VALUES ('a')")
        seen.append(sqlite_generation(db))
        app.ok("query PRAGMA wal_checkpoint(TRUNCATE)")
        seen.append(sqlite_generation(db))
        app.ok("exec INSERT INTO t(v) VALUES ('b')")
        seen.append(sqlite_generation(db))
        app.ok("query PRAGMA wal_checkpoint(TRUNCATE)")
        app.ok("exec INSERT INTO t(v) VALUES ('c')")
        # The restarted log has the size it had after 'b'; its salts differ.
        seen.append(sqlite_generation(db))
        app.ok("close")
        app.stop()
    check(len(set(seen)) == len(seen), f"a generation repeated: {seen}")
    return {"generations": len(seen)}


@scenario
def commit_during_a_validated_read_retries(base: Path) -> Result:
    folder = base / "app"
    folder.mkdir()
    db = folder / "app.db"
    create(db, mode="delete")
    app = Owner(db)
    app.ok("open delete")
    committed = []

    def read_while_owner_commits(connection: sqlite3.Connection) -> int:
        rows = count(connection)
        if not committed:
            app.ok("exec INSERT INTO t(v) VALUES ('during')")
            committed.append(True)
        return rows

    try:
        rows, access = read(
            db,
            read_while_owner_commits,
            deadline=time.monotonic() + 3,
            scratch=scratch_folder(base),
        )
    finally:
        app.stop()
    check(access.attempts >= 2 and rows == ROWS + 1, f"{rows} after {access.attempts} attempts")
    return {"rows": rows, "attempts": access.attempts}


# ── The lock hazard and reader processes ───────────────────────

_HELD_READER = r"""
import importlib.util, json, sys, time
from pathlib import Path
spec = importlib.util.spec_from_file_location("reader", sys.argv[1])
access = importlib.util.module_from_spec(spec)
sys.modules["reader"] = access
spec.loader.exec_module(access)

def held(connection):
    first = connection.execute("SELECT count(*) FROM t").fetchone()[0]
    print(json.dumps({"inside": first}), flush=True)
    sys.stdin.readline()
    second = connection.execute("SELECT count(*) FROM t").fetchone()[0]
    pages = connection.execute("SELECT count(*) FROM t WHERE v IS NOT NULL").fetchone()[0]
    return first, second, pages

value, used = access.read(Path(sys.argv[2]), held, deadline=time.monotonic() + 60, scratch=Path(sys.argv[3]))
print(json.dumps({"value": value, "mode": used.plan.mode, "attempts": used.attempts}), flush=True)
"""


class HeldReader:
    """A reader process inside one read transaction until it is released."""

    def __init__(self, db: Path, scratch: Path) -> None:
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-I",
                "-c",
                _HELD_READER,
                sqlite_access.__file__,
                str(db),
                str(scratch),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            cwd="/",
        )
        assert self.process.stdout is not None
        self.inside = json.loads(self.process.stdout.readline())["inside"]

    def release(self) -> dict[str, Any]:
        assert self.process.stdin is not None and self.process.stdout is not None
        self.process.stdin.write("\n")
        self.process.stdin.flush()
        answer = json.loads(self.process.stdout.readline())
        self.process.wait(timeout=10)
        return answer


@scenario
def server_handles_do_not_drop_a_readers_locks(base: Path) -> Result:
    folder = base / "app"
    folder.mkdir()
    db = folder / "app.db"
    create(db)
    with owner(db) as app:
        app.ok("exec INSERT INTO t(v) VALUES ('extra')")
        reader = HeldReader(db, scratch_folder(base))
        # The server process opens and closes the database and its index, as the magic
        # check, a header read, inventory sniffing, and hashing do.
        for _ in range(20):
            for path in (db, sidecar(db, "-shm")):
                with open(path, "rb") as handle:
                    handle.read(100)
        restart = app.ok("query PRAGMA wal_checkpoint(RESTART)")
        app.ok(
            "exec WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i+1 FROM n WHERE i<2000) "
            "INSERT INTO t(v) SELECT 'more' FROM n"
        )
        answer = reader.release()
        app.ok("close")
        app.stop()
    first, second, pages = answer["value"]
    check(restart[0][0] == 1, f"the owner's restart went through under a reader: {restart}")
    check(first == second == pages == ROWS + 1, f"the read changed under it: {answer}")
    check(answer["mode"] == "read_only", f"{answer}")
    return {"restart": restart[0], "rows": first}


@scenario
def immutable_read_refuses_no_commit(base: Path) -> Result:
    folder = base / "app"
    folder.mkdir()
    db = folder / "app.db"
    create(db, mode="delete")
    with owner(db, "delete") as app:
        reader = HeldReader(db, scratch_folder(base))
        commit = app.send("exec INSERT INTO t(v) VALUES ('while read')")
        # The read is released and, its validation failing, read again; the second pass
        # waits on stdin too.
        assert reader.process.stdin is not None and reader.process.stdout is not None
        reader.process.stdin.write("\n")
        reader.process.stdin.flush()
        reader.process.stdout.readline()
        answer = reader.release()
        app.ok("close")
        app.stop()
    check(commit["ok"], f"the owner's commit was refused under a lock-free read: {commit}")
    check(answer["attempts"] == 2 and answer["value"][0] == ROWS + 1, f"{answer}")
    return {"attempts": answer["attempts"]}


@scenario
def killed_reader_frees_the_owner(base: Path) -> Result:
    folder = base / "app"
    folder.mkdir()
    db = folder / "app.db"
    create(db)
    with owner(db) as app:
        app.ok("exec INSERT INTO t(v) VALUES ('extra')")
        reader = HeldReader(db, scratch_folder(base))
        held = app.ok("query PRAGMA wal_checkpoint(TRUNCATE)")
        reader.process.kill()
        reader.process.wait()
        freed = app.ok("query PRAGMA wal_checkpoint(TRUNCATE)")
        app.ok("exec INSERT INTO t(v) VALUES ('after')")
        app.ok("close")
        app.stop()
    check(held[0][0] == 1, f"the checkpoint went through under a reader: {held}")
    check(freed[0] == [0, 0, 0], f"a killed reader held the owner: {freed}")
    check(sorted(listing(folder)) == ["app.db"], f"left {sorted(listing(folder))}")
    return {"held": held[0], "freed": freed[0]}


@scenario
def reader_requests_never_stop_a_truncate(base: Path) -> Result:
    folder = base / "app"
    folder.mkdir()
    db = folder / "app.db"
    create(db)
    pool = ReaderPool(temporary_root=base)
    stop = threading.Event()
    reads: list[str] = []

    def keep_reading() -> None:
        while not stop.is_set():
            with pool.scratch() as scratch:
                try:
                    pool.call(
                        "info",
                        {"path": str(db), "scratch": str(scratch)},
                        deadline=time.monotonic() + 2,
                        subject="s",
                    )
                    reads.append("ok")
                except SqliteAccessError as exc:
                    reads.append(exc.state)

    worker = threading.Thread(target=keep_reading)
    try:
        with owner(db) as app:
            app.ok("busy 2000")
            worker.start()
            results = []
            index = 0
            # Until the reader has read through both kinds of state many times: a log
            # with frames, read through it, and a truncated one, read without a lock.
            while index < 30 or reads.count("ok") < 20:
                index += 1
                app.ok(f"exec INSERT INTO t(v) VALUES ('c {index}')")
                results.append(app.ok("query PRAGMA wal_checkpoint(TRUNCATE)")[0])
                time.sleep(0.005)
            stop.set()
            worker.join()
            app.ok("close")
            app.stop()
    finally:
        stop.set()
        pool.close()
    stopped = [result for result in results if result[0] != 0]
    check(not stopped, f"a checkpoint was stopped: {stopped}")
    return {"stopped": len(stopped), "reads": reads.count("ok") >= 20}


@scenario
def contention_refuses_no_commit(base: Path) -> Result:
    folder = base / "app"
    folder.mkdir()
    db = folder / "app.db"
    create(db, mode="delete", rows=20_000)
    pool = ReaderPool(temporary_root=base)
    outcome: dict[str, Any] = {}
    try:
        for pace in (0.0, 0.005, 0.05):
            stop = threading.Event()
            reads: list[str] = []

            def keep_reading(stop: threading.Event, reads: list[str]) -> None:
                while not stop.is_set():
                    with pool.scratch() as scratch:
                        try:
                            pool.call(
                                "info",
                                {"path": str(db), "scratch": str(scratch)},
                                deadline=time.monotonic() + 0.5,
                                subject="s",
                            )
                            reads.append("ok")
                        except SqliteAccessError as exc:
                            reads.append(exc.state)
                    time.sleep(0.01)

            viewer = threading.Thread(target=keep_reading, args=(stop, reads))
            with owner(db, "delete") as app:
                viewer.start()
                attempts = refused = 0
                end = time.monotonic() + 1.0
                while time.monotonic() < end:
                    attempts += 1
                    if not app.send(f"exec INSERT INTO t(v) VALUES ('{attempts}')")["ok"]:
                        refused += 1
                    if pace:
                        time.sleep(pace)
                stop.set()
                viewer.join()
                app.ok("close")
                app.stop()
            outcome[str(pace)] = {
                "attempts": attempts,
                "refused": refused,
                "reads": len(reads),
                "answered": reads.count("ok"),
            }
            check(
                refused == 0, f"at a pace of {pace} s, {refused} of {attempts} commits were refused"
            )
            check(bool(reads), f"the viewer read nothing at a pace of {pace} s")
    finally:
        pool.close()
    return outcome


@scenario
def pool_kills_a_worker_at_the_hard_deadline(base: Path) -> Result:
    folder = base / "app"
    folder.mkdir()
    db = folder / "app.db"
    create(db)
    pool = ReaderPool(temporary_root=base)
    try:
        with pool.scratch() as scratch:
            pool.call(
                "info",
                {"path": str(db), "scratch": str(scratch)},
                deadline=time.monotonic() + 2,
                subject="s",
            )
        [pid] = pool.workers()
        os.kill(pid, signal.SIGSTOP)
        started = time.monotonic()
        try:
            with pool.scratch() as scratch:
                pool.call(
                    "info",
                    {"path": str(db), "scratch": str(scratch)},
                    deadline=time.monotonic() + 0.2,
                    subject="s",
                )
        except SqliteAccessError as exc:
            state = exc.state
        else:
            state = "answered"
        took = time.monotonic() - started
        check(state == "busy", f"a stopped worker answered {state}")
        check(
            not os.path.exists(f"/proc/{pid}") or _zombie_or_gone(pid), "the worker was not killed"
        )
        with pool.scratch() as scratch:
            info = pool.call(
                "info",
                {"path": str(db), "scratch": str(scratch)},
                deadline=time.monotonic() + 2,
                subject="s",
            )
        check(pool.workers() != [pid] and info["access"]["state"] == "current", "no new worker")
        check(not any(base.glob("metabrowser-sqlite-*/request-*")), "a request folder was left")
    finally:
        pool.close()
    check(not any(base.glob("metabrowser-sqlite-*")), "the private folder was left")
    return {"state": state, "killed_after": round(took, 1)}


def _zombie_or_gone(pid: int) -> bool:
    try:
        return Path(f"/proc/{pid}/stat").read_text().split()[2] == "Z"
    except OSError:
        return True


@scenario
def pool_worker_crash_is_reader_stopped(base: Path) -> Result:
    folder = base / "app"
    folder.mkdir()
    db = folder / "app.db"
    create(db)
    pool = ReaderPool(temporary_root=base)
    try:
        with pool.scratch() as scratch:
            pool.call(
                "info",
                {"path": str(db), "scratch": str(scratch)},
                deadline=time.monotonic() + 2,
                subject="s",
            )
        [pid] = pool.workers()
        os.kill(pid, signal.SIGSTOP)
        outcome: list[str] = []

        def ask() -> None:
            try:
                with pool.scratch() as scratch:
                    pool.call(
                        "info",
                        {"path": str(db), "scratch": str(scratch)},
                        deadline=time.monotonic() + 5,
                        subject="s",
                    )
                outcome.append("answered")
            except SqliteAccessError as exc:
                outcome.append(exc.state)

        asking = threading.Thread(target=ask)
        asking.start()
        time.sleep(0.2)
        os.kill(pid, signal.SIGKILL)
        asking.join()
        check(outcome == ["reader_stopped"], f"a crashed worker answered {outcome}")
        with pool.scratch() as scratch:
            info = pool.call(
                "info",
                {"path": str(db), "scratch": str(scratch)},
                deadline=time.monotonic() + 2,
                subject="s",
            )
        check(info["access"]["state"] == "current", "no new worker")
    finally:
        pool.close()
    return {"state": outcome[0]}


@scenario
def pool_sweeps_folders_left_by_a_dead_process(base: Path) -> Result:
    left = base / "metabrowser-sqlite-left"
    left.mkdir()
    (left / "owner.lock").write_bytes(b"")
    (left / "request-0").mkdir()
    pool = ReaderPool(temporary_root=base)
    other = ReaderPool(temporary_root=base)
    try:
        mine = pool.folder()
        theirs = other.folder()
        check(not left.exists(), "a dead process's folder was kept")
        # A live pool's folder is locked, so another pool's sweep keeps it.
        third = ReaderPool(temporary_root=base)
        third.folder()
        third.close()
        check(mine.exists() and theirs.exists(), "a live pool's folder was swept")
    finally:
        pool.close()
        other.close()
    return {"swept": True}


def main() -> None:
    name, folder = sys.argv[1], Path(sys.argv[2])
    result = SCENARIOS[name](folder)
    print(f"ok {name}")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
