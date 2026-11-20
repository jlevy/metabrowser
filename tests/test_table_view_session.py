"""The table view's session runs production browser code on what the table routes answer.

``tests/dom/table-view-session.js`` drives the table plugin's view (``table-view.js``) and
its state (``table-model.js``) through a scripted page: a small table read and drawn
whole, sorted both ways, filtered from a value and from a header's menu, searched, walked
by the keyboard, a record opened and closed, columns hidden and reset, Back, refusals, a
view disposed before its answers arrive, a table past the whole-table bound drawn as
a window, scrolled, selected, copied, and printed, and the answers a bound shapes: pages
shorter than asked, a search the time budget stopped, a sort it refused, and files read
in part.
``tests/golden/cli-ui-table-view.tryscript.md`` pins its transcript. So that the
conversation is the server's and not envelopes a test wrote by hand, the session plays
the answers in ``tests/fixtures/table-view-responses.json``,
``tests/fixtures/table-view-long-responses.json``,
``tests/fixtures/table-view-bounds-responses.json``, and
``tests/fixtures/table-view-records-responses.json``: what the in-process application
answered for each request the page makes, over the files in ``tests/fixtures/table-view/``
and the files ``BOUNDED`` writes. The record-list recording is a JSON list of mappings,
the structured kind's Table view, and a JSON mapping, which is not a list of records.

A bound meets a file in a test only at a size no recording should hold, so the bounds
recording lowers it, through the same names the server reads, for the one file that
shows it (``BOUNDED``): a page bounded in cells, a delimited file's rows and columns.
The time budget is spent before each rows request on ``numbers.csv``, as
``tests/test_delimited_source.py`` spends it, after its parse.
The first tests here record them again and fail when a recording drifts;
``make golden-update`` rewrites the recordings and then the transcript.

A generation names a file's identity and modification time, which differ between
checkouts, so a recording holds `G` for it: in the answers, and in a record request's
`generation`, which the recorder asks with the file's real generation.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any
from unittest import mock
from urllib.parse import urlencode

import pytest
from starlette.testclient import TestClient

from metabrowser import server, table_source
from metabrowser.builtin_plugins.delimited import source as delimited
from metabrowser.source import reset_source_session
from metabrowser.table_source import Budget
from tests.golden_harness import check_recording, check_recording_text, run_session

TRANSCRIPT = "cli-ui-table-view.tryscript.md"
FIXTURES = Path(__file__).parent / "fixtures" / "table-view"
HOOK = "/api/plugin/table"
GENERATION = "G"
# The cursor the file's previous page of rows ended at, which this request continues from.
AFTER = "<next_after>"

Params = dict[str, str | list[str]]

# Every request the session makes, as the page spells it: a route and its parameters,
# one value each but `cols`, which repeats.
PEOPLE: list[tuple[str, Params]] = [
    ("schema", {}),
    ("rows", {"limit": "200"}),
    ("rows", {"sort": "score", "order": "asc", "limit": "200"}),
    ("rows", {"sort": "score", "order": "desc", "limit": "200"}),
    ("rows", {"f.active": "eq:true", "limit": "200"}),
    ("rows", {"q": "COMMA", "limit": "200"}),
    ("record", {"key": "@2", "generation": GENERATION}),
    ("rows", {"f.age": "contains:9", "limit": "200"}),
    ("rows", {"cols": ["name", "age", "score", "active", "note", "extra"], "limit": "200"}),
    ("rows", {"f.score": "gt:high", "limit": "200"}),
    ("rows", {"f.name": "eq:Zed", "limit": "200"}),
    ("record", {"key": "@4"}),
]
LONG: list[tuple[str, Params]] = [
    ("schema", {}),
    ("rows", {"limit": "200"}),
    ("rows", {"after": AFTER, "limit": "1000"}),
    ("rows", {"sort": "n", "order": "asc", "limit": "200"}),
    ("rows", {"sort": "n", "order": "desc", "limit": "200"}),
]


# A JSON list of mappings, and a mapping, which is not one: the structured kind's Table.
RECORDS: list[tuple[str, Params]] = [
    ("schema", {}),
    ("rows", {"limit": "200"}),
    ("record", {"key": "@1", "generation": GENERATION}),
    ("rows", {"sort": "age", "order": "asc", "limit": "200"}),
]
CONFIG: list[tuple[str, Params]] = [("schema", {})]


# Pages bounded in cells: three fields, a comma in one's name, and a page of nine cells
# carries three rows. The view reads a table it may draw whole until `next_after` ends.
PAGED_CSV = 'name,"city, state",n\n' + "".join(
    f'{name},"{city}, {state}",{n}\n'
    for n, (name, city, state) in enumerate(
        [
            ("Ada", "Austin", "TX"),
            ("Bob", "Boise", "ID"),
            ("Cy", "Chicago", "IL"),
            ("Dee", "Denver", "CO"),
            ("Eve", "Eugene", "OR"),
            ("Flo", "Flint", "MI"),
            ("Gus", "Gary", "IN"),
            ("Hal", "Helena", "MT"),
        ],
        start=1,
    )
)
PAGED: list[tuple[str, Params]] = [
    ("schema", {}),
    ("rows", {"limit": "200"}),
    ("rows", {"after": AFTER, "limit": "1000"}),
    ("rows", {"after": AFTER, "limit": "1000"}),
    ("rows", {"cols": ["name", "city, state"], "limit": "200"}),
    ("rows", {"cols": ["name", "city, state"], "after": AFTER, "limit": "1000"}),
]
# Three budget checks' worth of rows, one in sixteen tagged `match`, so a search the
# spent budget stops has found 256 rows, more than one page.
NUMBERS_CSV = "n,tag\n" + "".join(
    f"{n},{'match' if n % 16 == 0 else 'miss'}\n" for n in range(3 * 4096)
)
NUMBERS: list[tuple[str, Params]] = [
    ("schema", {}),
    ("rows", {"q": "match", "limit": "200"}),
    ("rows", {"q": "match", "after": AFTER, "limit": "1000"}),
    ("rows", {"sort": "n", "order": "asc", "limit": "200"}),
    ("rows", {"limit": "200"}),
]
CUT_CSV = "a,b,c\n1,2,3\n4,5,6\n"
TALL_CSV = "n\n" + "".join(f"{n}\n" for n in range(1, 7))
SHORT: list[tuple[str, Params]] = [("schema", {}), ("rows", {"limit": "200"})]

# Each file the bounds recording writes: its text, its requests, and the bounds lowered
# while it is parsed and paged (module, name, value).
BOUNDED: dict[str, tuple[str, list[tuple[str, Params]], list[tuple[Any, str, int]]]] = {
    "paged.csv": (PAGED_CSV, PAGED, [(table_source, "TABLE_PAGE_CELLS_MAX", 9)]),
    "numbers.csv": (NUMBERS_CSV, NUMBERS, []),
    "cut.csv": (CUT_CSV, SHORT, [(delimited, "DELIMITED_MAX_COLUMNS", 2)]),
    "tall.csv": (TALL_CSV, SHORT, [(delimited, "DELIMITED_MAX_ROWS", 3)]),
}


def _key(route: str, params: Params) -> str:
    return f"{route}?{urlencode(sorted(params.items()), doseq=True)}"


@contextmanager
def _spent_budgets() -> Generator[None]:
    """Every request's time budget spent as it starts."""

    def spent(cls: type[Budget], seconds: float = 0.0) -> Budget:
        return Budget(0)

    with mock.patch.object(Budget, "start", classmethod(spent)):
        yield


def _serve(tmp_path: Path) -> TestClient:
    root = tmp_path / "root"
    shutil.copytree(FIXTURES, root)
    for name, (text, _requests, _bounds) in BOUNDED.items():
        (root / name).write_text(text, encoding="utf-8")
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
    client: TestClient,
    file: str,
    requests: list[tuple[str, Params]],
    *,
    spent: bool = False,
) -> dict[str, Any]:
    """Each answer, keyed as the page asks; with *spent*, each rows request's time budget
    is spent as it starts, after the file was parsed with a budget of its own."""

    answers: dict[str, Any] = {}
    real = client.get(f"{HOOK}/schema", params={"path": file}).json().get("generation", "")
    after = ""
    for route, params in requests:
        spelled: Params = {"path": file, **params}
        asked = dict(spelled)
        if asked.get("generation") == GENERATION:
            asked["generation"] = real
        if asked.get("after") == AFTER:
            spelled["after"] = asked["after"] = after
        with _spent_budgets() if spent and route == "rows" else ExitStack():
            response = client.get(f"{HOOK}/{route}", params=asked)
        body = response.json()
        if route == "rows":
            after = body.get("next_after") or ""
        answers[_key(route, spelled)] = {"status": response.status_code, "body": _normalize(body)}
    return answers


def _record_lists(tmp_path: Path) -> dict[str, Any]:
    with _serve(tmp_path) as client:
        answers = _record_file(client, "records.json", RECORDS)
        answers.update(_record_file(client, "config.json", CONFIG))
        return {"answers": answers}


def _record(tmp_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    with _serve(tmp_path) as client:
        bounded: dict[str, Any] = {}
        for name, (_text, requests, bounds) in BOUNDED.items():
            with ExitStack() as lowered:
                for module, constant, value in bounds:
                    lowered.enter_context(mock.patch.object(module, constant, value))
                bounded.update(_record_file(client, name, requests, spent=name == "numbers.csv"))
        return (
            {"answers": _record_file(client, "people.csv", PEOPLE)},
            {"answers": _record_file(client, "long.csv", LONG)},
            {"answers": bounded},
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
    people, long, bounded = _record(tmp_path)
    check_recording("table-view-responses.json", people, transcript=TRANSCRIPT)
    for name, recorded in [
        ("table-view-long-responses.json", long),
        ("table-view-bounds-responses.json", bounded),
    ]:
        rendered = _rows_on_lines(recorded)
        assert json.loads(rendered) == recorded
        check_recording_text(name, rendered, transcript=TRANSCRIPT)


def test_the_record_list_recording_is_what_the_routes_answer(tmp_path: Path) -> None:
    recorded = _record_lists(tmp_path)
    check_recording("table-view-records-responses.json", recorded, transcript=TRANSCRIPT)
    answers = recorded["answers"]
    refused = answers[_key("schema", {"path": "config.json"})]
    assert (refused["status"], refused["body"]["code"]) == (422, "source_unreadable")
    record = answers[_key("record", {"path": "records.json", "key": "@1", "generation": "G"})]
    assert record["body"]["cells"]["meta"] == {"json": {"born": 1815, "notes": {"first": True}}}


def test_the_bounds_recording_shows_what_each_bound_answers(tmp_path: Path) -> None:
    # Each lowered bound, and the spent budget, answers what the session's steps say.
    _people, _long, bounded = _record(tmp_path)
    answers = {key: answer["body"] for key, answer in bounded["answers"].items()}
    first = answers[_key("rows", {"path": "paged.csv", "limit": "200"})]
    assert (len(first["rows"]), first["limit"], first["count"]) == (3, 3, 8)
    searched = answers[_key("rows", {"path": "numbers.csv", "q": "match", "limit": "200"})]
    assert (searched["reason"], searched["count_complete"], len(searched["rows"])) == (
        "budget",
        False,
        200,
    )
    assert searched["next_after"]
    refused = answers[
        _key("rows", {"path": "numbers.csv", "sort": "n", "order": "asc", "limit": "200"})
    ]
    assert (refused["rows"], refused["reason"], refused["sort_refused"]) == ([], "sort_budget", "n")
    cut = answers[_key("rows", {"path": "cut.csv", "limit": "200"})]
    assert (cut["truncated"], cut["count_complete"], cut["columns"]) == (True, True, ["a", "b"])
    tall = answers[_key("rows", {"path": "tall.csv", "limit": "200"})]
    assert (tall["truncated"], tall["count_complete"], tall["reason"]) == (
        True,
        False,
        "source_truncated",
    )


def test_the_long_table_is_past_the_whole_table_bound(tmp_path: Path) -> None:
    # The session's windowed table must be one the view windows: its count past
    # WHOLE_TABLE_MAX_ROWS (table-view.js) and its first page short of it.
    view = (
        FIXTURES.parent.parent.parent / "src/metabrowser/builtin_plugins/table/table-view.js"
    ).read_text(encoding="utf-8")
    bound = int(view.split("export const WHOLE_TABLE_MAX_ROWS = ")[1].split(";")[0])
    _people, long, _bounded = _record(tmp_path)
    first = long["answers"][_key("rows", {"path": "long.csv", "limit": "200"})]["body"]
    assert first["count"] > bound
    assert first["count_complete"] is True


def test_the_session_plays_the_recordings_and_asks_for_nothing_else() -> None:
    # The session fails on a request the recordings do not hold, and on an invariant it
    # checks; what it prints is the golden's.
    transcript = run_session("table-view-session.js")
    assert transcript["requests asked of the server"]["unrecorded"] == []


@pytest.mark.parametrize(
    "name",
    [
        "table-view-responses.json",
        "table-view-long-responses.json",
        "table-view-bounds-responses.json",
        "table-view-records-responses.json",
    ],
)
def test_every_recorded_answer_is_ok_but_the_refusals(name: str) -> None:
    recording = json.loads((FIXTURES.parent / name).read_text(encoding="utf-8"))
    for key, answer in recording["answers"].items():
        expected = 400 if "f.score=gt%3Ahigh" in key else 422 if "config.json" in key else 200
        assert answer["status"] == expected, key
