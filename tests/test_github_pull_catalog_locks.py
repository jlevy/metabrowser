"""The pull request catalog's own handles never drop a connection's locks (mb-cggp).

A POSIX lock belongs to a process and a file, so closing any handle on the catalog in
the server process drops every lock a connection there holds on it, and a second
process (another server sharing the cache, or a `metab` command) may then read or lock
while a commit is half written. The catalog's admission opens the file and its journal
for a header check and an identity check, so every close goes through
``metabrowser.sqlite_access.PROCESS_HANDLES``, which defers it until the last connection
in the process to that file has closed.
"""

from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path

import pytest

from metabrowser.builtin_plugins.github import pull_catalog
from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from tests.cache_home_fixture import (  # pyright: ignore[reportPrivateUsage]
    FixtureSource,
    _stage_and_publish_source,
    build_empty_home,
)
from tests.github_pull_fixture import CANONICAL

SOURCE = FixtureSource("https", CANONICAL)

_PROBE = """
import sqlite3, sys
connection = sqlite3.connect(sys.argv[1], isolation_level=None, timeout=0)
try:
    connection.execute("BEGIN IMMEDIATE")
except sqlite3.OperationalError:
    print("refused")
else:
    connection.execute("ROLLBACK")
    print("locked")
"""


def _another_process_locks(path: Path) -> str:
    done = subprocess.run(
        [sys.executable, "-c", _PROBE, str(path)], capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


@pytest.fixture
def repository(tmp_path: Path) -> ListedRepository:
    home = tmp_path / "home"
    build_empty_home(home)
    _stage_and_publish_source(home, SOURCE, opened=False)
    listed = ListedRepository(home, SOURCE.slug, "octo", "demo")
    pull_catalog._initialize(listed)  # pyright: ignore[reportPrivateUsage]
    return listed


def test_a_read_beside_a_writer_keeps_the_writers_lock(repository: ListedRepository) -> None:
    path = repository.home / pull_catalog._relative(repository.slug)  # pyright: ignore[reportPrivateUsage]
    with pull_catalog._database(repository.home, repository.slug, write=True) as writer:  # pyright: ignore[reportPrivateUsage]
        writer.isolation_level = None
        writer.execute("BEGIN IMMEDIATE")
        writer.execute("INSERT INTO pulls VALUES (1, 'open', '2026-01-01T00:00:00Z', '{}')")
        assert _another_process_locks(path) == "refused"
        # Readers on other threads of the server process admit, connect, and close.
        readers = [
            threading.Thread(
                target=pull_catalog.catalog_refusal, args=(repository.home, repository.slug)
            )
            for _ in range(4)
        ]
        for reader in readers:
            reader.start()
        for reader in readers:
            reader.join()
        pull_catalog.read_catalog(repository.home, repository.slug)
        pull_catalog._initialize(repository)  # pyright: ignore[reportPrivateUsage]
        assert _another_process_locks(path) == "refused"
        writer.execute("COMMIT")
    assert _another_process_locks(path) == "locked"


def test_the_hazard_is_real(repository: ListedRepository) -> None:
    """The probe sees a dropped lock: a plain close in this process drops the writer's."""
    path = repository.home / pull_catalog._relative(repository.slug)  # pyright: ignore[reportPrivateUsage]
    with pull_catalog._database(repository.home, repository.slug, write=True) as writer:  # pyright: ignore[reportPrivateUsage]
        writer.isolation_level = None
        writer.execute("BEGIN IMMEDIATE")
        assert _another_process_locks(path) == "refused"
        with open(path, "rb") as handle:
            handle.read(100)
        assert _another_process_locks(path) == "locked"
        writer.execute("ROLLBACK")
