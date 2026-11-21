"""The fsqlite store's Table and Schema views' session runs production browser code on what
the routes answer.

``tests/dom/fsqlite-tables-session.js`` mounts the store's Table and Schema views
(``builtin_plugins/fsqlite/store-tables.js``), which draw with the SQLite plugin's
``tables-view.js`` and ``tables-model.js``, and checks their lifecycle.
``tests/golden/cli-ui-fsqlite-tables.tryscript.md`` pins its transcript. So that the
answers are the server's and not envelopes a test wrote by hand, the session plays
``tests/fixtures/fsqlite-tables-responses.json``: what the in-process application
answered for each request below. The first test records them again and fails when the
recording drifts; ``make golden-update`` rewrites it and then the transcript.

A generation names the identities of a store's files, which differ between checkouts,
so the recording holds `G` for it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.builtin_plugins.fsqlite.store import snapshot_name
from metabrowser.source import reset_source_session
from tests.golden_harness import check_recording, run_session
from tests.test_fsqlite_info_session import GENERATION, _marker, _snapshot

TRANSCRIPT = "cli-ui-fsqlite-tables.tryscript.md"

# Each request the session makes: the plugin, its route, and the address it asks about.
REQUESTS = (
    ("table", "tables", "notes/fsqlite.json"),
    ("table", "tables", "torn/fsqlite.json"),
    ("fsqlite", "schema", "notes/fsqlite.json"),
    ("fsqlite", "schema", "notes/fsqlite.json/notes"),
    ("fsqlite", "schema", "torn/fsqlite.json"),
)


def _stores(root: Path) -> None:
    """A store to draw, and one whose pointer is torn."""
    notes = root / "notes"
    notes.mkdir(parents=True)
    (notes / "fsqlite.json").write_text(_marker())
    (notes / "current").write_text("1")
    _snapshot(notes / "snapshots" / snapshot_name(1))

    torn = root / "torn"
    torn.mkdir()
    (torn / "fsqlite.json").write_text(_marker())
    (torn / "current").write_text("one")


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            name: GENERATION if name == "generation" and item is not None else _normalize(item)
            for name, item in cast(dict[str, Any], value).items()
        }
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
        for plugin, route, address in REQUESTS:
            response = client.get(f"/api/plugin/{plugin}/{route}", params={"path": address})
            answers[f"{plugin}/{route} {address}"] = {
                "status": response.status_code,
                "body": _normalize(response.json()),
            }
    return {"answers": answers}


def test_the_recorded_answers_are_what_the_routes_answer(tmp_path: Path) -> None:
    check_recording("fsqlite-tables-responses.json", _record(tmp_path), transcript=TRANSCRIPT)


def test_the_session_draws_every_recorded_answer() -> None:
    transcript = run_session("fsqlite-tables-session.js")
    overview = transcript["Table view of notes/fsqlite.json"]
    assert list(overview) == ["Tables", "Internal tables"]
    assert transcript["Schema view of notes/fsqlite.json/notes"] == {
        "notes": ["CREATE TABLE notes (id INTEGER PRIMARY KEY, title TEXT NOT NULL)"]
    }
