"""Measure the costs the SQLite reader bounds cap, and print them.

The constants in ``metabrowser.sqlite_access`` and ``metabrowser.sqlite_readers`` record
the numbers this prints beside them:

- a reader process's start to its first answer, and a warm Info round trip;
- a reader process's address space and resident memory after an Info read (Linux);
- a private copy of a database and its log (main file, then log) at several sizes, and
  an Info read through one, which is what one request pays in the copy states.

Run it with ``uv run python -m devtools.bench_sqlite_access``. It writes only under a
temporary folder it removes.
"""

from __future__ import annotations

import shutil
import sqlite3
import statistics
import tempfile
import time
from pathlib import Path

from metabrowser.sqlite_access import _copy_file  # pyright: ignore[reportPrivateUsage]
from metabrowser.sqlite_readers import ReaderPool

MIB = 1024 * 1024


def _database(path: Path, size: int, *, wal_frames: bool = False) -> sqlite3.Connection:
    """A database of about *size* bytes; with *wal_frames* every row is in its log, and
    the connection is returned open, so the log stays beside the file."""
    connection = sqlite3.connect(path, isolation_level=None)
    if wal_frames:
        connection.execute("PRAGMA journal_mode=wal")
        connection.execute("PRAGMA wal_autocheckpoint=0")
    connection.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, v BLOB)")
    rows = max(1, size // 4096)
    connection.execute("BEGIN")
    connection.executemany("INSERT INTO t(v) VALUES (randomblob(4000))", ([] for _ in range(rows)))
    connection.execute("COMMIT")
    if not wal_frames:
        connection.close()
    return connection


def _status(pid: int) -> dict[str, str]:
    try:
        lines = Path(f"/proc/{pid}/status").read_text().splitlines()
    except OSError:
        return {}
    return {
        line.split(":")[0]: line.split(":")[1].strip()
        for line in lines
        if line.split(":")[0] in {"VmPeak", "VmSize", "VmRSS", "VmHWM"}
    }


def main() -> None:
    base = Path(tempfile.mkdtemp(prefix="mb-bench-sqlite-"))
    try:
        db = base / "app.db"
        _database(db, MIB)
        starts: list[float] = []
        pool = ReaderPool(size=1, temporary_root=base)
        for index in range(5):
            if index:
                pool.close()
                pool = ReaderPool(size=1, temporary_root=base)
            started = time.perf_counter()
            with pool.scratch() as scratch:
                pool.call(
                    "info",
                    {"path": str(db), "scratch": str(scratch)},
                    deadline=time.monotonic() + 5,
                    subject="s",
                )
            starts.append(time.perf_counter() - started)
        trips: list[float] = []
        for _ in range(50):
            started = time.perf_counter()
            with pool.scratch() as scratch:
                pool.call(
                    "info",
                    {"path": str(db), "scratch": str(scratch)},
                    deadline=time.monotonic() + 5,
                    subject="s",
                )
            trips.append(time.perf_counter() - started)
        [pid] = pool.workers()
        memory = _status(pid)
        pool.close()
        print(f"start to first answer: median {statistics.median(starts) * 1000:.1f} ms of 5")
        print(f"warm Info round trip: median {statistics.median(trips) * 1000:.2f} ms of 50")
        print(f"worker memory after reads: {memory}")

        for size in (8 * MIB, 32 * MIB, 64 * MIB, 128 * MIB):
            folder = base / f"copy-{size // MIB}"
            folder.mkdir()
            source = folder / "app.db"
            owner = _database(source, size, wal_frames=True)
            copies: list[float] = []
            for index in range(5):
                target = folder / f"copy{index}"
                started = time.perf_counter()
                _copy_file(source, target, 1 << 40)
                _copy_file(
                    source.with_name("app.db-wal"), target.with_name(f"copy{index}-wal"), 1 << 40
                )
                copies.append(time.perf_counter() - started)
                target.unlink()
                target.with_name(f"copy{index}-wal").unlink()
            total = source.stat().st_size + source.with_name("app.db-wal").stat().st_size
            source.with_name("app.db-shm").unlink()
            pool = ReaderPool(size=1, temporary_root=base)
            reads: list[float] = []
            mode = ""
            try:
                for _ in range(5):
                    started = time.perf_counter()
                    with pool.scratch() as scratch:
                        answer = pool.call(
                            "info",
                            {"path": str(source), "scratch": str(scratch)},
                            deadline=time.monotonic() + 30,
                            subject="s",
                        )
                    reads.append(time.perf_counter() - started)
                    mode = answer["access"]["mode"]
            finally:
                pool.close()
            print(
                f"copy of {total / MIB:.0f} MiB (main and log): median {statistics.median(copies) * 1000:.0f} ms; "
                f"Info through it ({mode}): median {statistics.median(reads) * 1000:.0f} ms"
            )
            owner.close()
            shutil.rmtree(folder)
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    main()
