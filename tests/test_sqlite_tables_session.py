"""The SQLite overview, Schema view, and table cells run production browser code on what
the routes answer.

``tests/dom/sqlite-tables-session.js`` draws the database overview and the Schema view
(``builtin_plugins/sqlite/tables-view.js`` and ``tables-model.js``), mounts the Table view
at a table's address through the table plugin, and presents every cell of recorded SQLite
pages with the table plugin's ``presentCell``, from the answers in
``tests/fixtures/sqlite-tables-responses.json``: what the in-process application answered
for the databases built from ``tests/fixtures/sqlite-tables/``.
``tests/golden/cli-ui-sqlite-tables.tryscript.md`` pins its transcript. The first test
records the answers again and fails when the recording drifts; ``make golden-update``
rewrites it. A generation names a file's identity and time, recorded as `G`.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.source import reset_source_session
from tests.golden_harness import check_recording, run_session
from tests.sqlite_fixture import build

TRANSCRIPT = "cli-ui-sqlite-tables.tryscript.md"
RECORDING = "sqlite-tables-responses.json"
FIXTURES = Path(__file__).parent / "fixtures" / "sqlite-tables"

# What the session asks, by the name it asks it under: (plugin, route, params).
REQUESTS: dict[str, tuple[str, str, dict[str, str]]] = {
    "overview app.db": ("table", "tables", {"path": "app.db"}),
    "overview snapshot.db": ("table", "tables", {"path": "snapshot.db"}),
    "schema app.db": ("sqlite", "schema", {"path": "app.db"}),
    "schema app.db/grants": ("sqlite", "schema", {"path": "app.db/grants"}),
    "schema fake.db": ("sqlite", "schema", {"path": "fake.db"}),
    "rows app.db/users": ("table", "rows", {"path": "app.db/users"}),
    "rows app.db/orders": ("table", "rows", {"path": "app.db/orders"}),
    "rows app.db/grants": ("table", "rows", {"path": "app.db/grants"}),
    "rows app.db/huge": ("table", "rows", {"path": "app.db/huge"}),
    "schema-of app.db/users": ("table", "schema", {"path": "app.db/users"}),
    "schema-of app.db/orders": ("table", "schema", {"path": "app.db/orders"}),
    "schema-of app.db/grants": ("table", "schema", {"path": "app.db/grants"}),
    "schema-of app.db/huge": ("table", "schema", {"path": "app.db/huge"}),
}


def _normalize(body: Any) -> Any:
    if isinstance(body, dict):
        return {
            name: ("G" if name == "generation" and value is not None else _normalize(value))
            for name, value in body.items()
        }
    if isinstance(body, list):
        return [_normalize(item) for item in body]
    return body


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    root = tmp_path / "root"
    root.mkdir()
    for name in ("app", "snapshot"):
        build(root / f"{name}.db", (FIXTURES / f"{name}.sql").read_text(encoding="utf-8"))
    (root / "fake.db").write_bytes(b"not a database at all\x00\x01\x02")
    reset_source_session()
    server._set_root_dir(root)  # pyright: ignore[reportPrivateUsage]
    with TestClient(server.app) as test_client:
        yield test_client


def test_the_recorded_answers_are_what_the_routes_answer(client: TestClient) -> None:
    answers: dict[str, Any] = {}
    for name, (plugin, route, params) in REQUESTS.items():
        response = client.get(f"/api/plugin/{plugin}/{route}", params=params)
        answers[name] = {"status": response.status_code, "body": _normalize(response.json())}
    assert all(answer["status"] == 200 for answer in answers.values())
    check_recording(RECORDING, {"answers": answers}, transcript=TRANSCRIPT)


def test_the_session_draws_every_recorded_answer() -> None:
    transcript = run_session("sqlite-tables-session.js")
    assert transcript["overview of app.db"]["Tables"]
    assert "a view disposed before its answer" in transcript
