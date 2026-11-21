"""Build a SQLite database from reviewable SQL text, for goldens and tests.

The table goldens build their databases in their ``before:`` scripts from the SQL under
``tests/fixtures/sqlite-tables/`` rather than from committed binaries::

    uv run python tests/sqlite_fixture.py <database> <script.sql>

The database is written in rollback-journal mode and its modification time set to a
fixed instant, so a lock-free read never sees it as just changed (``RACY_MTIME_SECONDS``
in ``metabrowser.sqlite_access``) and a generation token is stable for one build.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

# 2023-11-14 22:13:20 UTC, the instant the other goldens' fixtures carry.
FIXED_MTIME = 1_700_000_000


def build(database: Path, script: str) -> Path:
    """Run *script* into a new database at *database*, then set its time."""
    if database.exists():
        raise FileExistsError(database)
    connection = sqlite3.connect(database)
    try:
        connection.executescript(script)
        connection.commit()
    finally:
        connection.close()
    os.utime(database, (FIXED_MTIME, FIXED_MTIME))
    return database


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: sqlite_fixture.py <database> <script.sql>", file=sys.stderr)
        return 2
    build(Path(argv[1]), Path(argv[2]).read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
