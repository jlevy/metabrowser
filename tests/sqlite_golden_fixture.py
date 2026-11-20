"""The SQLite databases ``tests/golden/cli-api-sqlite.tryscript.md`` reads, from SQL text.

Usage: ``python -m tests.sqlite_golden_fixture <folder>``. Each database is built here
from the SQL below, not committed as a binary, and its owner, where it has one, runs in
a process of its own (``tests/sqlite_guest_scenarios.py``). Every file's time is set to
one instant, so the transcript does not depend on when it ran.
"""

from __future__ import annotations

import gzip
import os
import sqlite3
import sys
from pathlib import Path

from tests import sqlite_guest_scenarios as scenarios

# 2023-11-14 22:13:20 UTC, the instant the other goldens' fixtures use.
INSTANT = 1_700_000_000

APP_SQL = """
CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE posts(id INTEGER PRIMARY KEY, author INTEGER REFERENCES users(id), body TEXT);
CREATE INDEX posts_author ON posts(author);
CREATE VIEW shouting AS SELECT upper(name) AS name FROM users;
CREATE TRIGGER posts_touch AFTER UPDATE ON posts BEGIN SELECT 1; END;
INSERT INTO users(name) VALUES ('ada'), ('bob');
INSERT INTO posts(author, body) VALUES (1, 'hello'), (2, 'hi');
PRAGMA user_version = 3;
PRAGMA application_id = 1179865420;
"""


# Schema rows whose `type` reads as `table` up to a NUL, each with its own suffix, and
# one whose `type` is a blob: SQLite accepts them, and the Info view counts them as
# `other` rather than as a group each.
CRAFTED_TYPES = 40


def crafted(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE seed(a)")
    connection.setconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE, False)
    connection.execute("PRAGMA writable_schema=ON")
    insert = "INSERT INTO sqlite_schema(type, name, tbl_name, rootpage, sql) VALUES (?, ?, ?, 2, ?)"
    for index in range(CRAFTED_TYPES):
        name = f"t{index}"
        connection.execute(insert, (f"table\x00{index:04d}", name, name, f"CREATE TABLE {name}(a)"))
    connection.execute(insert, (b"table", "blob", "blob", "CREATE TABLE blob(a)"))
    connection.commit()
    connection.close()


def main() -> None:
    root = Path(sys.argv[1])
    root.mkdir(parents=True, exist_ok=True)
    app = sqlite3.connect(root / "app.db")
    app.executescript(APP_SQL)
    app.close()
    scenarios.create(root / "History")
    scenarios.crashed_with_frames(root / "live.db")
    scenarios.crashed_with_frames(root / "copied.sqlite3")
    (root / "copied.sqlite3-shm").unlink()
    crafted(root / "crafted.db")
    notes = sqlite3.connect(root / "notes.dat")
    notes.executescript("CREATE TABLE note(text TEXT); INSERT INTO note VALUES ('kept');")
    notes.close()
    (root / "fake.db").write_bytes(b"not a database, though it is named like one\n\x00")
    (root / "packed.sqlite.gz").write_bytes(
        gzip.compress((root / "notes.dat").read_bytes(), mtime=0)
    )
    for path in root.iterdir():
        os.utime(path, (INSTANT, INSTANT))


if __name__ == "__main__":
    main()
