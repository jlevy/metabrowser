"""The SQLite Info view's session runs production browser code on what the route answers.

``tests/dom/sqlite-info-session.js`` draws the Info view (``builtin_plugins/sqlite/``)
from the answers in ``tests/fixtures/sqlite-info-responses.json``: what the in-process
application's ``/api/plugin/sqlite/info`` answered for databases in each state a reader
can find them in, staged here with real owners
(``tests/sqlite_guest_scenarios.py``). ``tests/golden/cli-ui-sqlite-info.tryscript.md``
pins its transcript. The first test records the answers again and fails when the
recording drifts; ``make golden-update`` rewrites it.

A generation names a file's identity and time, recorded as `G`. The library block names
the SQLite this interpreter loads, which differs between the interpreters CI runs, so it
is recorded as one library that meets the minimum; the session draws an older one from
it.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.source import reset_source_session
from metabrowser.sqlite_access import LIBRARY_VERSIONS, READER_MINIMUM_LIBRARY
from tests import sqlite_guest_scenarios as scenarios
from tests.golden_harness import check_recording, run_session

TRANSCRIPT = "cli-ui-sqlite-info.tryscript.md"
RECORDING = "sqlite-info-responses.json"

# The databases the recording names, in the order the session draws them.
FILES = ("app.db", "History", "live.db", "noshm.db", "linked.db", "busy.db", "fake.db")


def _dotted(version: tuple[int, int, int]) -> str:
    return ".".join(str(part) for part in version)


def _library() -> dict[str, Any]:
    return {
        "version": "L",
        "minimum": _dotted(READER_MINIMUM_LIBRARY),
        "meets_minimum": True,
        "versions": [
            {"version": _dotted(entry.version), "meaning": entry.meaning, "available": True}
            for entry in LIBRARY_VERSIONS
        ],
    }


def _normalize(body: dict[str, Any]) -> dict[str, Any]:
    out = dict(body)
    out["generation"] = "G" if body.get("generation") is not None else None
    if "library" in out:
        out["library"] = _library()
    return out


def _stage(root: Path) -> None:
    app = root / "app.db"
    scenarios.create(app, mode="delete")
    connection = sqlite3.connect(app)
    connection.executescript(
        "CREATE INDEX t_v ON t(v);"
        "CREATE VIEW shout AS SELECT upper(v) AS v FROM t;"
        "CREATE TRIGGER t_touch AFTER UPDATE ON t BEGIN SELECT 1; END;"
        "PRAGMA user_version = 7;"
        "PRAGMA application_id = 1179865420;"  # 0x4653514C, "FSQL": an fsqlite snapshot
    )
    connection.close()
    scenarios.age(app)
    scenarios.create(root / "History")
    scenarios.crashed_with_frames(root / "live.db")
    scenarios.crashed_with_frames(root / "noshm.db")
    (root / "noshm.db-shm").unlink()
    scenarios.create(root / "linked.db")
    os.link(root / "linked.db", root / "linked-too.db")
    scenarios.create(root / "busy.db", mode="delete", rows=20_000)
    scenarios.hot_journal(root / "busy.db")
    (root / "fake.db").write_bytes(b"not a database at all\x00\x01\x02")


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    root = tmp_path / "root"
    root.mkdir()
    _stage(root)
    reset_source_session()
    server._set_root_dir(root)  # pyright: ignore[reportPrivateUsage]
    with TestClient(server.app) as test_client:
        yield test_client


def test_the_recorded_answers_are_what_the_route_answers(client: TestClient) -> None:
    answers: dict[str, Any] = {}
    for name in FILES:
        response = client.get("/api/plugin/sqlite/info", params={"path": name})
        answers[name] = {"status": response.status_code, "body": _normalize(response.json())}
    states = {
        name: answer["body"].get("error", {}).get("state")
        or answer["body"]["access"]["state"] + ":" + answer["body"]["access"]["mode"]
        for name, answer in answers.items()
    }
    assert states == {
        "app.db": "current:immutable",
        "History": "current:immutable",
        "live.db": "current:read_only",
        "noshm.db": "current:private_copy",
        "linked.db": "another_name:private_copy",
        "busy.db": "writer_busy",
        "fake.db": "not_sqlite",
    }
    check_recording(RECORDING, {"answers": answers}, transcript=TRANSCRIPT)


def test_the_kind_is_claimed_by_magic_whatever_the_name(client: TestClient) -> None:
    kinds = {name: client.get("/api/file", params={"path": name}).json()["kind"] for name in FILES}
    assert kinds == {
        "app.db": "sqlite",
        "History": "sqlite",
        "live.db": "sqlite",
        "noshm.db": "sqlite",
        "linked.db": "sqlite",
        "busy.db": "sqlite",
        "fake.db": "binary",
    }


def test_the_session_draws_every_recorded_state() -> None:
    transcript = run_session("sqlite-info-session.js")
    assert set(transcript["answers"]) == set(FILES)
