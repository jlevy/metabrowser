"""The fsqlite store Info view's session runs production browser code on what the route answers.

``tests/dom/fsqlite-info-session.js`` draws the store Info view (``store-view.js``) and
its model (``store-model.js``, over the SQLite plugin's ``info-model.js`` and
``info-view.js``) for every state ``/api/plugin/fsqlite/info`` answers, and checks that a
view disposed before its answer draws nothing and that a refused request or a provider
that failed to load is said. ``tests/golden/cli-ui-fsqlite-info.tryscript.md`` pins its
transcript. So that the answers are the server's and not envelopes a test wrote by hand,
the session plays ``tests/fixtures/fsqlite-info-responses.json``: what the in-process
application answered for each store below. The first test records them again and fails
when the recording drifts; ``make golden-update`` rewrites it and then the transcript.

A generation names the identities of a store's files, which differ between checkouts,
and the SQLite library is the machine's, so the recording holds `G` and `L` for them.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, cast

from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.builtin_plugins.fsqlite.store import FSQLITE_APPLICATION_ID, snapshot_name
from metabrowser.source import reset_source_session
from tests.golden_harness import check_recording, run_session

TRANSCRIPT = "cli-ui-fsqlite-info.tryscript.md"
GENERATION = "G"
LIBRARY = "L"
STORE_ID = "550e8400-e29b-41d4-a716-446655440000"
SNAPSHOT_SQL = """
CREATE TABLE applied_tx (tx_id TEXT PRIMARY KEY NOT NULL, applied_at TEXT NOT NULL);
CREATE TABLE fsqlite_meta (key TEXT PRIMARY KEY NOT NULL, value TEXT NOT NULL);
CREATE TABLE notes (id INTEGER PRIMARY KEY, title TEXT NOT NULL);
INSERT INTO notes VALUES (1, 'first'), (2, 'second');
"""


def _marker(version: str = "f1.0") -> str:
    return (
        f'{{"format": "fsqlite", "format_version": "{version}", '
        f'"required_features": [], "store_id": "{STORE_ID}"}}\n'
    )


def _snapshot(path: Path, application_id: int = FSQLITE_APPLICATION_ID) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, isolation_level=None)
    try:
        connection.executescript(
            f"PRAGMA application_id = {application_id}; PRAGMA user_version = 3;" + SNAPSHOT_SQL
        )
    finally:
        connection.close()


def _stores(root: Path) -> None:
    """One store for each state the view draws."""
    notes = root / "notes"
    notes.mkdir(parents=True)
    (notes / "fsqlite.json").write_text(_marker())
    (notes / "current").write_text("2")
    _snapshot(notes / "snapshots" / snapshot_name(2))
    pending = notes / "tx" / "pending"
    for index in range(3):
        (pending / f"00000000000{index}-000000000001-w-0123456789.txn").mkdir(parents=True)
    (pending / "000000000000-000000000001-w-0123456789.txn" / "COMMITTED").touch()
    (pending / "000000000001-000000000001-w-0123456789.txn" / "COMMITTED").touch()

    empty = root / "empty"
    empty.mkdir()
    (empty / "fsqlite.json").write_text(_marker())
    (empty / "current").write_text("0")
    _snapshot(empty / "snapshots" / snapshot_name(0))

    torn = root / "torn"
    torn.mkdir()
    (torn / "fsqlite.json").write_text(_marker())
    (torn / "current").write_bytes(b"\xef\xbb\xbf7")

    newer = root / "newer"
    newer.mkdir()
    (newer / "fsqlite.json").write_text(_marker("f2.0"))

    foreign = root / "foreign"
    foreign.mkdir()
    (foreign / "fsqlite.json").write_text(_marker())
    (foreign / "current").write_text("1")
    _snapshot(foreign / "snapshots" / snapshot_name(1), application_id=0)

    garbled = root / "garbled"
    (garbled / "snapshots").mkdir(parents=True)
    (garbled / "fsqlite.json").write_text(_marker())
    (garbled / "current").write_text("1")
    (garbled / "snapshots" / snapshot_name(1)).write_bytes(b"not a database\n" * 16)


STORES = ("notes", "empty", "torn", "newer", "foreign", "garbled")


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for name, item in cast(dict[str, Any], value).items():
            if name == "generation" and item is not None:
                out[name] = GENERATION
            elif name == "library":
                out[name] = {**cast(dict[str, Any], item), "version": LIBRARY}
            else:
                out[name] = _normalize(item)
        return out
    if isinstance(value, list):
        return [_normalize(item) for item in value]  # pyright: ignore[reportUnknownVariableType]
    return value


def _record(tmp_path: Path) -> dict[str, Any]:
    root = tmp_path / "root"
    _stores(root)
    reset_source_session()
    server._set_root_dir(root)  # pyright: ignore[reportPrivateUsage]
    answers: dict[str, Any] = {}
    with TestClient(server.app) as client:
        for name in STORES:
            path = f"{name}/fsqlite.json"
            response = client.get("/api/plugin/fsqlite/info", params={"path": path})
            answers[path] = {"status": response.status_code, "body": _normalize(response.json())}
    return {"answers": answers}


def test_the_recorded_answers_are_what_the_route_answers(tmp_path: Path) -> None:
    check_recording("fsqlite-info-responses.json", _record(tmp_path), transcript=TRANSCRIPT)


def test_the_session_draws_every_recorded_answer() -> None:
    transcript = run_session("fsqlite-info-session.js")
    assert sorted(transcript["stores"]) == sorted(f"{name}/fsqlite.json" for name in STORES)
