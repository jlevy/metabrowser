"""A SQLite database on a Git pin: claimed by its magic number from the blob, written once
to a private file named by its object id under ``BLOB_MAX_BYTES``, and read with
``immutable=1``, a committed write-ahead-log database without its log."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from metabrowser.builtin_plugins.sqlite import sidekick
from metabrowser.sqlite_readers import reader_pool
from tests.git_pin_harness import fast_import_store, pinned_client
from tests.required_tools import needs_git

APP = "g1-YXBwLmRi"  # app.db
HISTORY = "g1-SGlzdG9yeQ"  # History


def _database_bytes(tmp_path: Path, name: str, *, wal: bool, user_version: int = 0) -> bytes:
    """A small database; *user_version* makes its bytes, and so its blob, its own."""
    path = tmp_path / name
    connection = sqlite3.connect(path)
    if wal:
        connection.execute("PRAGMA journal_mode=wal")
    connection.executescript(
        f"CREATE TABLE t(x); INSERT INTO t VALUES (1), (2); PRAGMA user_version = {user_version};"
    )
    connection.close()
    return path.read_bytes()


def _ask(store: Path, commit: str, paths: list[str]) -> list[tuple[str, dict[str, Any]]]:
    async def run() -> list[tuple[str, dict[str, Any]]]:
        out: list[tuple[str, dict[str, Any]]] = []
        async with pinned_client(store, commit) as (client, _subject):
            for path in paths:
                kind = (await client.get("/api/file", params={"path": path})).json()["kind"]
                info = await client.get("/api/plugin/sqlite/info", params={"path": path})
                assert info.status_code == 200
                out.append((kind, info.json()))
        return out

    return asyncio.run(run())


@needs_git
def test_a_pinned_database_is_read_once_from_a_private_copy(tmp_path: Path) -> None:
    files = {
        b"app.db": _database_bytes(tmp_path, "wal.db", wal=True),
        b"History": _database_bytes(tmp_path, "plain.db", wal=False),
    }
    store, commit = fast_import_store(tmp_path, files)
    folder = reader_pool().folder() / "blobs"
    before = set(folder.iterdir()) if folder.exists() else set()
    answers = _ask(store, commit, [APP, HISTORY, APP])
    assert [kind for kind, _ in answers] == ["sqlite", "sqlite", "sqlite"]
    wal_info = answers[0][1]
    assert wal_info["access"]["mode"] == "immutable"
    assert wal_info["access"]["state"] == "current"
    assert "without its log" in wal_info["access"]["reason"]
    assert wal_info["journal_mode"] == "wal"
    assert wal_info["database"]["objects"] == {"table": 1}
    assert answers[1][1]["journal_mode"] == "rollback"
    # Each blob is written once, by its object id, and left read-only.
    blobs = sorted(set(folder.iterdir()) - before)
    assert len(blobs) == 2
    assert all(blob.stat().st_mode & 0o222 == 0 for blob in blobs)
    assert wal_info["generation"] != answers[1][1]["generation"]
    assert answers[2][1]["generation"] == wal_info["generation"]


@needs_git
def test_a_pinned_database_past_the_cap_is_not_copied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Bytes of its own, so no earlier test in this process has written its blob.
    store, commit = fast_import_store(
        tmp_path, {b"app.db": _database_bytes(tmp_path, "wal.db", wal=False, user_version=11)}
    )
    monkeypatch.setattr(sidekick, "BLOB_MAX_BYTES", 1024)
    [(kind, info)] = _ask(store, commit, [APP])
    assert kind == "sqlite"
    assert info["error"]["state"] == "unreadable"
    assert "larger than the 1,024 bytes" in info["error"]["message"]


@needs_git
def test_a_written_blob_is_not_read_from_git_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, commit = fast_import_store(
        tmp_path, {b"app.db": _database_bytes(tmp_path, "once.db", wal=False, user_version=12)}
    )
    reads: list[str] = []
    original = sidekick.read_content_window

    async def counted(ref: Any, *, max_bytes: int) -> Any:
        reads.append(ref.fingerprint)
        return await original(ref, max_bytes=max_bytes)

    monkeypatch.setattr(sidekick, "read_content_window", counted)
    answers = _ask(store, commit, [APP, APP, APP])
    assert [info["database"]["objects"] for _, info in answers] == [{"table": 1}] * 3
    # Read from Git once, by the first request; the others find the private file.
    assert len(reads) == 1
    assert reader_pool().written_blob(answers[0][1]["generation"]) is not None
