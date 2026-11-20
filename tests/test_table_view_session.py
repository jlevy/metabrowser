"""The table view's session runs production browser code on what the table routes answer.

``tests/dom/table-view-session.js`` drives the table plugin's view (``table-view.js``) and
its state (``table-model.js``) through a scripted page: a small table read and drawn
whole, sorted both ways, filtered from a value and from a header's menu, searched, walked
by the keyboard, a record opened and closed, columns hidden and reset, Back, refusals, a
view disposed before its answers arrive, and a table past the whole-table bound drawn as
a window, scrolled, selected, copied, and printed.
``tests/golden/cli-ui-table-view.tryscript.md`` pins its transcript. So that the
conversation is the server's and not envelopes a test wrote by hand, the session plays
the answers in ``tests/fixtures/table-view-responses.json`` and
``tests/fixtures/table-view-long-responses.json``: what the in-process application
answered for each request the page makes, over the files in ``tests/fixtures/table-view/``.
The first tests here record them again and fail when a recording drifts;
``make golden-update`` rewrites the recordings and then the transcript.

A generation names a file's identity and modification time, which differ between
checkouts, so a recording holds `G` for it: in the answers, and in a record request's
`generation`, which the recorder asks with the file's real generation.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import pytest
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.source import reset_source_session
from tests.golden_harness import check_recording, check_recording_text, run_session

TRANSCRIPT = "cli-ui-table-view.tryscript.md"
FIXTURES = Path(__file__).parent / "fixtures" / "table-view"
HOOK = "/api/plugin/table"
GENERATION = "G"
# The cursor the long table's first page ends at, which its second page continues from.
AFTER = "<next_after>"

# Every request the session makes, as the page spells it: a route and its parameters.
PEOPLE: list[tuple[str, dict[str, str]]] = [
    ("schema", {}),
    ("rows", {"limit": "200"}),
    ("rows", {"sort": "score", "order": "asc", "limit": "200"}),
    ("rows", {"sort": "score", "order": "desc", "limit": "200"}),
    ("rows", {"f.active": "eq:true", "limit": "200"}),
    ("rows", {"q": "COMMA", "limit": "200"}),
    ("record", {"key": "@2", "generation": GENERATION}),
    ("rows", {"f.age": "contains:9", "limit": "200"}),
    ("rows", {"cols": "name,age,score,active,note,extra", "limit": "200"}),
    ("rows", {"f.score": "gt:high", "limit": "200"}),
    ("rows", {"f.name": "eq:Zed", "limit": "200"}),
    ("record", {"key": "@4"}),
]
LONG: list[tuple[str, dict[str, str]]] = [
    ("schema", {}),
    ("rows", {"limit": "200"}),
    ("rows", {"after": AFTER, "limit": "1000"}),
    ("rows", {"sort": "n", "order": "asc", "limit": "200"}),
    ("rows", {"sort": "n", "order": "desc", "limit": "200"}),
]


def _key(route: str, params: dict[str, str]) -> str:
    return f"{route}?{urlencode(sorted(params.items()))}"


def _serve(tmp_path: Path) -> TestClient:
    root = tmp_path / "root"
    shutil.copytree(FIXTURES, root)
    reset_source_session()
    server._set_root_dir(root)  # pyright: ignore[reportPrivateUsage]
    return TestClient(server.app)


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            name: GENERATION if name == "generation" else _normalize(item)
            for name, item in value.items()  # pyright: ignore[reportUnknownVariableType]
        }
    if isinstance(value, list):
        return [_normalize(item) for item in value]  # pyright: ignore[reportUnknownVariableType]
    return value


def _record_file(
    client: TestClient, file: str, requests: list[tuple[str, dict[str, str]]]
) -> dict[str, Any]:
    answers: dict[str, Any] = {}
    real = client.get(f"{HOOK}/schema", params={"path": file}).json()["generation"]
    after = ""
    for route, params in requests:
        spelled = {"path": file, **params}
        asked = dict(spelled)
        if asked.get("generation") == GENERATION:
            asked["generation"] = real
        if asked.get("after") == AFTER:
            spelled["after"] = asked["after"] = after
        response = client.get(f"{HOOK}/{route}", params=asked)
        body = response.json()
        if route == "rows" and "after" not in params and not after:
            after = body.get("next_after") or ""
        answers[_key(route, spelled)] = {"status": response.status_code, "body": _normalize(body)}
    return answers


def _record(tmp_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    with _serve(tmp_path) as client:
        return (
            {"answers": _record_file(client, "people.csv", PEOPLE)},
            {"answers": _record_file(client, "long.csv", LONG)},
        )


def _rows_on_lines(recorded: dict[str, Any]) -> str:
    """The long table's recording with each value of an answer, and each row, on one line,
    so 800 rows stay inside the review budget (``devtools/check_goldens.py``)."""

    answers: list[str] = []
    for key, answer in recorded["answers"].items():
        fields: list[str] = []
        for name, value in answer["body"].items():
            if name == "rows":
                rows = ",\n".join(f"          {json.dumps(row)}" for row in value)
                fields.append(f'        "rows": [\n{rows}\n        ]')
            else:
                fields.append(f"        {json.dumps(name)}: {json.dumps(value)}")
        body = ",\n".join(fields)
        answers.append(
            f'    {json.dumps(key)}: {{\n      "status": {answer["status"]},\n'
            f'      "body": {{\n{body}\n      }}\n    }}'
        )
    joined = ",\n".join(answers)
    return f'{{\n  "answers": {{\n{joined}\n  }}\n}}\n'


def test_the_recorded_answers_are_what_the_routes_answer(tmp_path: Path) -> None:
    people, long = _record(tmp_path)
    check_recording("table-view-responses.json", people, transcript=TRANSCRIPT)
    rendered = _rows_on_lines(long)
    assert json.loads(rendered) == long
    check_recording_text("table-view-long-responses.json", rendered, transcript=TRANSCRIPT)


def test_the_long_table_is_past_the_whole_table_bound(tmp_path: Path) -> None:
    # The session's windowed table must be one the view windows: its count past
    # WHOLE_TABLE_MAX_ROWS (table-view.js) and its first page short of it.
    view = (
        FIXTURES.parent.parent.parent / "src/metabrowser/builtin_plugins/table/table-view.js"
    ).read_text(encoding="utf-8")
    bound = int(view.split("export const WHOLE_TABLE_MAX_ROWS = ")[1].split(";")[0])
    _people, long = _record(tmp_path)
    first = long["answers"][_key("rows", {"path": "long.csv", "limit": "200"})]["body"]
    assert first["count"] > bound
    assert first["count_complete"] is True


def test_the_session_plays_the_recordings_and_asks_for_nothing_else() -> None:
    # The session fails on a request the recordings do not hold, and on an invariant it
    # checks; what it prints is the golden's.
    transcript = run_session("table-view-session.js")
    assert transcript["requests asked of the server"]["unrecorded"] == []


@pytest.mark.parametrize("name", ["table-view-responses.json", "table-view-long-responses.json"])
def test_every_recorded_answer_is_ok_but_the_refusal(name: str) -> None:
    recording = json.loads((FIXTURES.parent / name).read_text(encoding="utf-8"))
    for key, answer in recording["answers"].items():
        expected = 400 if "f.score=gt%3Ahigh" in key else 200
        assert answer["status"] == expected, key
