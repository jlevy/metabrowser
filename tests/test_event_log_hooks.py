"""The event-log plugin's routes, through the application: what they refuse, and how.

``tests/test_event_log_views.py`` holds the reading rules and ``tests/golden/cli-api-event-
log-views.tryscript.md`` the story the routes tell. This module holds what only a served
route can show: the bounds (a segment too large, a file that is not JSONL, a path out of
the served folder), a file the log did not write that must not raise, and the cache that
keeps three tables.
"""

from __future__ import annotations

import json
import os
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import event_log_views, server

SEGMENT = "events-20261119T220000Z-p7-000.jsonl"
LATER = "events-20261119T220000Z-p7-001.jsonl"
OTHER_PROCESS = "events-20261119T220000Z-p8-001.jsonl"


def _record(second: int, event: str, name: str, **fields: Any) -> str:
    record: dict[str, Any] = {
        "v": 1,
        "ts": f"2026-11-19T22:00:{second:02d}.000Z",
        "event": event,
        "kind": "request",
        "name": name,
        "pid": 7,
    }
    record.update(fields)
    return json.dumps(record) + "\n"


def _segment(*extra: str) -> str:
    return "".join(
        [
            _record(1, "end", "GET /a", span=1, outcome="ok", dur_ms=5),
            _record(2, "open", "GET /b", span=2, dur_ms=3000),
            *extra,
        ]
    )


@pytest.fixture
def served(tmp_path: Path) -> Generator[Path]:
    root = tmp_path / "root"
    root.mkdir()
    (root / SEGMENT).write_text(_segment(), encoding="utf-8")
    server._set_root_dir(root)
    yield root


@pytest.fixture
def client(served: Path) -> Generator[TestClient]:
    with TestClient(server.app) as test_client:
        yield test_client


def _get(client: TestClient, view: str, path: str, **params: str) -> Any:
    return client.get(f"/api/plugin/event-log/{view}", params={"path": path, **params})


# ── What the routes refuse ───────────────────────────────────────────────────────────


def test_a_segment_past_the_bound_is_refused_with_413_and_one_at_it_is_read(
    client: TestClient, served: Path
) -> None:
    bound = event_log_views.MAX_VIEW_BYTES
    line = _record(1, "end", "GET /a", span=1, outcome="ok", dur_ms=5)
    body = (line * (bound // len(line) + 2)).encode()
    (served / "events-20261119T230000Z-p9-000.jsonl").write_bytes(body[: bound + 1])
    (served / "events-20261119T230000Z-p9-001.jsonl").write_bytes(body[:bound])
    over = _get(client, "timeline", "events-20261119T230000Z-p9-000.jsonl")
    assert over.status_code == 413
    assert over.json()["code"] == "event_log_too_large"
    # The segment at the bound, its last line torn by the cut, is read whole.
    at = _get(client, "timeline", "events-20261119T230000Z-p9-001.jsonl")
    assert at.status_code == 200
    assert at.json()["log"]["skipped"] == 1


def test_a_file_that_is_not_jsonl_is_refused_with_400(client: TestClient, served: Path) -> None:
    (served / "notes.txt").write_text("hello\n", encoding="utf-8")
    response = _get(client, "timeline", "notes.txt")
    assert response.status_code == 400
    assert response.json()["code"] == "not_jsonl"


def test_a_jsonl_file_that_holds_no_record_of_this_schema_is_refused_with_415(
    client: TestClient, served: Path
) -> None:
    (served / "events.jsonl").write_text('{"other": true}\n{"also": 1}\n', encoding="utf-8")
    response = _get(client, "errors", "events.jsonl")
    assert response.status_code == 415
    assert response.json()["code"] == "not_an_event_log"


@pytest.mark.parametrize(
    "path",
    [
        "../outside.jsonl",
        "..%2Foutside.jsonl",
        "%2e%2e/outside.jsonl",
        "/etc/passwd",
        "",
        "a%00.jsonl",
        "dir.jsonl",
        "link.jsonl",
    ],
)
def test_a_path_out_of_the_served_folder_is_not_found(
    client: TestClient, served: Path, path: str
) -> None:
    (served.parent / "outside.jsonl").write_text(_segment(), encoding="utf-8")
    (served / "dir.jsonl").mkdir()
    os.symlink(served.parent / "outside.jsonl", served / "link.jsonl")
    response = client.get(f"/api/plugin/event-log/timeline?path={path}")
    assert response.status_code == 404, response.text
    assert response.json()["code"] == "not_found"


# ── A file the log did not write is the file's fault, and is answered ─────────────────


@pytest.mark.parametrize(
    "line",
    [
        # A time that is beyond any calendar, and one that is not a real year.
        _record(1, "end", "GET /a", span=1, outcome="ok", dur_ms=1e18),
        _record(1, "end", "GET /a", span=1, outcome="ok", dur_ms=1e300),
        _record(1, "end", "GET /a", span=1, outcome="ok", dur_ms=-1e18),
        json.dumps(
            {"v": 1, "ts": "0001-01-01T00:00:00Z", "event": "end", "kind": "job", "name": "x"}
        )
        + "\n",
        # What JSON allows and Python's serializer will not repeat.
        '{"v":1,"ts":"2026-11-19T22:00:01.000Z","event":"end","kind":"job","name":"x",'
        '"span":1,"outcome":"ok","dur_ms":5,"attrs":{"x":NaN,"y":1e999,"z":[Infinity]}}\n',
        # An integer past Python's 4,300 digits, and arrays nested past its recursion limit.
        '{"v":1,"ts":"2026-11-19T22:00:01.000Z","event":"end","kind":"job","name":"x",'
        f'"span":1,"outcome":"ok","dur_ms":5,"attrs":{{"x":{"9" * 5000}}}}}\n',
        '{"v":1,"ts":"2026-11-19T22:00:01.000Z","event":"end","kind":"job","name":"x",'
        '"span":1,"outcome":"ok","dur_ms":5,"attrs":' + "[" * 100_000 + "]" * 100_000 + "}\n",
    ],
    ids=[
        "duration-1e18",
        "duration-1e300",
        "duration-negative",
        "year-one",
        "non-finite-attrs",
        "4300-digit-integer",
        "deeply-nested-attrs",
    ],
)
@pytest.mark.parametrize("view", ["timeline", "slowest", "kinds", "errors"])
def test_a_value_a_file_may_hold_never_escapes_as_an_exception(
    client: TestClient, served: Path, line: str, view: str
) -> None:
    (served / "events-20261119T230000Z-p9-000.jsonl").write_text(
        line + _record(2, "end", "GET /ok", span=3, outcome="ok", dur_ms=4), encoding="utf-8"
    )
    response = _get(client, view, "events-20261119T230000Z-p9-000.jsonl")
    assert response.status_code == 200, response.text
    # What was sent is JSON a browser parses: no NaN, no Infinity.
    json.loads(response.text, parse_constant=_refuse_constant)


def _refuse_constant(name: str) -> None:
    raise AssertionError(f"{name} in an answer")


def test_a_failure_to_put_a_table_together_is_a_422_that_names_the_file(
    client: TestClient, served: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(_data: bytes) -> event_log_views.Table:
        raise OverflowError("timestamp out of range")

    monkeypatch.setattr(event_log_views, "build_table", broken)
    (served / "events-20261119T230000Z-p9-000.jsonl").write_text(_segment(), encoding="utf-8")
    response = _get(client, "timeline", "events-20261119T230000Z-p9-000.jsonl")
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "unreadable_event_log"
    assert "events-20261119T230000Z-p9-000.jsonl" in body["error"]
    assert "OverflowError" in body["error"]


def test_a_failure_in_a_view_is_a_422_that_names_the_file(
    client: TestClient, served: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise ValueError("year 0 is out of range")

    monkeypatch.setattr(event_log_views, "by_kind", broken)
    response = _get(client, "kinds", SEGMENT)
    assert response.status_code == 422
    assert response.json()["code"] == "unreadable_event_log"
    assert SEGMENT in response.json()["error"]


# ── A segment that is continued ──────────────────────────────────────────────────────


def test_a_segment_says_whether_the_same_process_wrote_a_later_one(
    client: TestClient, served: Path
) -> None:
    assert _get(client, "errors", SEGMENT).json()["log"]["continues"] is False
    # Another process's segment of the same number is not a continuation.
    (served / OTHER_PROCESS).write_text(_segment(), encoding="utf-8")
    assert _get(client, "errors", SEGMENT).json()["log"]["continues"] is False
    # The successor appears without the earlier segment changing, which the cached table
    # keeps its answer for: the answer is not.
    (served / LATER).write_text(_segment(), encoding="utf-8")
    for view in ("timeline", "slowest", "kinds", "errors"):
        assert _get(client, view, SEGMENT).json()["log"]["continues"] is True, view
    assert _get(client, "errors", LATER).json()["log"]["continues"] is False


# ── The timeline finds a row, and reads newest first ─────────────────────────────────


def test_the_timeline_says_where_a_row_is_so_a_page_can_open_down_to_it(
    client: TestClient, served: Path
) -> None:
    lines = [
        _record(1, "start", "refresh", kind="job", span=10, parent=9),
        _record(
            2, "end", "git fetch", kind="subprocess", span=11, parent=10, outcome="ok", dur_ms=900
        ),
        _record(3, "end", "refresh", kind="job", span=10, parent=9, outcome="failed", dur_ms=2500),
        _record(4, "end", "GET /pull", span=9, outcome="ok", dur_ms=3000),
    ]
    (served / "events-20261119T230000Z-p7-000.jsonl").write_text("".join(lines), encoding="utf-8")
    answer = _get(client, "timeline", "events-20261119T230000Z-p7-000.jsonl", focus="7:11").json()
    assert answer["focus"] == {
        "key": "7:11",
        "found": True,
        "steps": [
            {"parent": None, "key": "7:9", "index": 0},
            {"parent": "7:9", "key": "7:10", "index": 0},
            {"parent": "7:10", "key": "7:11", "index": 0},
        ],
    }
    missing = _get(client, "timeline", "events-20261119T230000Z-p7-000.jsonl", focus="7:99")
    assert missing.json()["focus"] == {
        "key": "7:99",
        "found": False,
        "reason": "missing",
        "steps": [],
    }
    # Under a filter that does not show the row, the answer says so rather than guess.
    hidden = _get(
        client, "timeline", "events-20261119T230000Z-p7-000.jsonl", focus="7:11", outcome="failed"
    ).json()["focus"]
    assert hidden == {"key": "7:11", "found": False, "reason": "filtered", "steps": []}


def test_the_roots_can_be_read_newest_first_and_a_focus_follows_that_order(
    client: TestClient, served: Path
) -> None:
    lines = [
        _record(second, "end", f"GET /{second}", span=second, outcome="ok", dur_ms=1)
        for second in range(1, 6)
    ]
    name = "events-20261119T230000Z-p7-000.jsonl"
    (served / name).write_text("".join(lines), encoding="utf-8")
    oldest = [row["name"] for row in _get(client, "timeline", name).json()["rows"]]
    newest = _get(client, "timeline", name, order="newest", focus="7:1").json()
    assert [row["name"] for row in newest["rows"]] == oldest[::-1]
    assert newest["order"] == "newest"
    assert newest["focus"]["steps"] == [{"parent": None, "key": "7:1", "index": 4}]
    refused = _get(client, "timeline", name, order="sideways")
    assert refused.status_code == 400
    assert refused.json()["code"] == "invalid_query"


# ── The tables the server keeps ──────────────────────────────────────────────────────


def test_the_server_keeps_the_most_recent_tables_and_lets_the_oldest_go(
    client: TestClient, served: Path
) -> None:
    kept = event_log_views.MAX_TABLES_KEPT
    names = [f"events-20261119T2300{n:02d}Z-p7-000.jsonl" for n in range(kept + 1)]
    for name in names:
        (served / name).write_text(_segment(), encoding="utf-8")
    event_log_views._TABLES.clear()  # pyright: ignore[reportPrivateUsage]
    for name in names:
        assert _get(client, "kinds", name).status_code == 200
    held = {identity for identity, _ in event_log_views._TABLES}  # pyright: ignore[reportPrivateUsage]
    assert len(held) == kept
    assert names[0] not in held, "the first one asked for was the first to go"
    assert set(names[1:]) == held
    # Asking for the evicted one again builds it, and lets the next oldest go.
    assert _get(client, "kinds", names[0]).status_code == 200
    held = {identity for identity, _ in event_log_views._TABLES}  # pyright: ignore[reportPrivateUsage]
    assert names[0] in held and names[1] not in held


def test_a_changed_segment_is_read_again_and_an_unchanged_one_is_not(
    client: TestClient, served: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    built: list[int] = []
    real = event_log_views.build_table

    def counting(data: bytes) -> event_log_views.Table:
        built.append(len(data))
        return real(data)

    monkeypatch.setattr(event_log_views, "build_table", counting)
    event_log_views._TABLES.clear()  # pyright: ignore[reportPrivateUsage]
    for _ in range(3):
        assert _get(client, "timeline", SEGMENT).status_code == 200
    assert len(built) == 1
    path = served / SEGMENT
    status = path.stat()
    path.write_text(_segment(_record(5, "end", "GET /c", span=5, outcome="ok", dur_ms=2)))
    os.utime(path, (status.st_atime, status.st_mtime + 5))
    assert _get(client, "timeline", SEGMENT).status_code == 200
    assert len(built) == 2
