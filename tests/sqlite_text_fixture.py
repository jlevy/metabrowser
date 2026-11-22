"""A SQLite database built from SQL text, for goldens that need one.

Goldens build their databases in a ``before:`` script from reviewable SQL text rather
than committing binaries (the tabular-data plan's Testing Strategy). There is no
``sqlite3`` command line on every machine that runs them, so this is that command's one
use here: it creates the database at the path it is given, runs the SQL text on stdin as
one script, and closes it, leaving a rollback-journal database with no file beside it.

    PYTHONPATH=<repository> python -m tests.sqlite_text_fixture <database> < schema.sql
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


def build(database: Path, script: str) -> None:
    """Create *database* (it must not exist) and run *script* on it."""
    if database.exists():
        raise SystemExit(f"{database} already exists")
    connection = sqlite3.connect(database, isolation_level=None)
    try:
        connection.executescript(script)
    finally:
        connection.close()


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m tests.sqlite_text_fixture <database> < script.sql", file=sys.stderr)
        return 2
    build(Path(argv[1]), sys.stdin.read())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
