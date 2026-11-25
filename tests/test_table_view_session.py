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
import os
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
    ("record", {"key": "@151", "generation": GENERATION}),
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


# The live table: one file at each version the session's steps change it to, with the
# requests the view makes while that version is on disk. None is the file removed. A
# generation is recorded as `G<version>`, the version the file was at, so the page can
# tell one from the next as it would the real ones.
LIVE_FILE = "live.csv"
LIVE: list[tuple[str | None, list[tuple[str, Params]]]] = [
    # The table as first read.
    ("name,qty\na,1\nb,2\nc,3\nd,4\ne,5\n", [("schema", {}), ("rows", {"limit": "200"})]),
    # One cell changed and one row added at the end; the second row opened by position.
    # A refresh reads the rows alone while their columns hold.
    (
        "name,qty\na,1\nb,20\nc,3\nd,4\ne,5\nf,6\n",
        [("rows", {"limit": "200"}), ("record", {"key": "@2", "generation": "G2"})],
    ),
    # A row put first, so every position names the row before it; then sorted by qty.
    (
        "name,qty\nz,9\na,1\nb,20\nc,3\nd,4\ne,5\nf,6\n",
        [
            ("record", {"key": "@2"}),
            ("rows", {"limit": "200"}),
            ("rows", {"sort": "qty", "order": "asc", "limit": "200"}),
            ("rows", {"sort": "qty", "order": "desc", "limit": "200"}),
        ],
    ),
    # Two rows added at the end of the file, one first and one last in the table's order.
    (
        "name,qty\nz,9\na,1\nb,20\nc,3\nd,4\ne,5\nf,6\ng,100\nh,0\n",
        [("rows", {"sort": "qty", "order": "desc", "limit": "200"})],
    ),
    # The same rows, the file touched.
    (
        "name,qty\nz,9\na,1\nb,20\nc,3\nd,4\ne,5\nf,6\ng,100\nh,0\n",
        [("rows", {"sort": "qty", "order": "desc", "limit": "200"})],
    ),
    # One cell changed under the selection, read slowly.
    (
        "name,qty\nz,9\na,1\nb,21\nc,3\nd,4\ne,5\nf,6\ng,100\nh,0\n",
        [("rows", {"sort": "qty", "order": "desc", "limit": "200"})],
    ),
    # Another, read only after twice the last read's time.
    (
        "name,qty\nz,9\na,1\nb,21\nc,30\nd,4\ne,5\nf,6\ng,100\nh,0\n",
        [("rows", {"sort": "qty", "order": "desc", "limit": "200"})],
    ),
    # Another, made while the page is hidden; then the first row's record opened.
    (
        "name,qty\nz,9\na,1\nb,21\nc,30\nd,40\ne,5\nf,6\ng,100\nh,0\n",
        [
            ("rows", {"sort": "qty", "order": "desc", "limit": "200"}),
            ("record", {"key": "@3", "generation": "G8"}),
        ],
    ),
    # Another row changed, the open record not.
    (
        "name,qty\nz,9\na,1\nb,21\nc,30\nd,40\ne,50\nf,6\ng,100\nh,0\n",
        [("record", {"key": "@3"}), ("rows", {"sort": "qty", "order": "desc", "limit": "200"})],
    ),
    # Another, held back while the record pane pauses, and read when it resumes.
    (
        "name,qty\nz,9\na,1\nb,21\nc,30\nd,40\ne,50\nf,60\ng,100\nh,0\n",
        [("record", {"key": "@3"}), ("rows", {"sort": "qty", "order": "desc", "limit": "200"})],
    ),
    # The sorted column gone: the rows refused, so the schema read, and the rows afresh.
    (
        "name\nz\na\nb\nc\nd\ne\nf\ng\nh\n",
        [
            ("rows", {"sort": "qty", "order": "desc", "limit": "200"}),
            ("schema", {}),
            ("rows", {"limit": "200"}),
        ],
    ),
    # The file gone, and a change while it still is: refused each time, said once.
    (None, [("rows", {"limit": "200"}), ("schema", {})]),
    (None, [("rows", {"limit": "200"}), ("schema", {})]),
]


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


def _record_live(tmp_path: Path) -> dict[str, Any]:
    """The live file's answers at each version, as the page asks while it is on disk."""

    versions: dict[str, Any] = {}
    with _serve(tmp_path) as client:
        target = tmp_path / "root" / LIVE_FILE
        for number, (text, requests) in enumerate(LIVE, start=1):
            label = f"G{number}"
            if text is None:
                target.unlink(missing_ok=True)
            else:
                target.write_text(text, encoding="utf-8")
                # A second apart, so each version's generation differs from the last's
                # however coarse the filesystem's clock.
                os.utime(target, (1_700_000_000 + number, 1_700_000_000 + number))
            real: dict[str, str] = {}
            answers: dict[str, Any] = {}
            for route, params in requests:
                asked: Params = {"path": LIVE_FILE, **params}
                if isinstance(asked.get("generation"), str):
                    asked["generation"] = real[str(asked["generation"])]
                response = client.get(f"{HOOK}/{route}", params=asked)
                body = response.json()
                if isinstance(body.get("generation"), str):
                    real[label] = body["generation"]
                answers[_key(route, {"path": LIVE_FILE, **params})] = {
                    "status": response.status_code,
                    "body": _relabel(body, label),
                }
            versions[label] = answers
    return {"versions": versions}


def _relabel(value: Any, label: str) -> Any:
    if isinstance(value, dict):
        return {
            name: label if name == "generation" and isinstance(item, str) else _relabel(item, label)
            for name, item in value.items()  # pyright: ignore[reportUnknownVariableType]
        }
    if isinstance(value, list):
        return [_relabel(item, label) for item in value]  # pyright: ignore[reportUnknownVariableType]
    return value


def test_the_live_recording_is_what_the_routes_answer_at_each_version(tmp_path: Path) -> None:
    check_recording("table-view-live-responses.json", _record_live(tmp_path), transcript=TRANSCRIPT)


# A live table drawn as a window, whose rows above the window go stale (review A of #675,
# A4): sixty rows read in part, in pages of ten, so the window can begin pages below the
# first. At each version the recording holds the whole chain of pages, keyed by the cursor
# the page continues from, which names a position that holds across a change.
LIVE_WINDOW_FILE = "live-window.csv"
LIVE_WINDOW_BOUNDS: list[tuple[Any, str, int]] = [
    (delimited, "DELIMITED_MAX_ROWS", 60),
    (table_source, "TABLE_PAGE_CELLS_MAX", 10),
]
LIVE_WINDOW: list[str] = [
    "n\n" + "".join(f"{n}\n" for n in range(1, 81)),
    # A row above the window changed, and one in it.
    "n\n" + "".join(f"{n * 100 if n in (5, 45) else n}\n" for n in range(1, 81)),
]


def _record_live_window(tmp_path: Path) -> dict[str, Any]:
    versions: dict[str, Any] = {}
    with _serve(tmp_path) as client, ExitStack() as lowered:
        for module, constant, value in LIVE_WINDOW_BOUNDS:
            lowered.enter_context(mock.patch.object(module, constant, value))
        target = tmp_path / "root" / LIVE_WINDOW_FILE
        for number, text in enumerate(LIVE_WINDOW, start=1):
            label = f"W{number}"
            target.write_text(text, encoding="utf-8")
            os.utime(target, (1_700_000_000 + number, 1_700_000_000 + number))
            answers: dict[str, Any] = {}
            schema = client.get(f"{HOOK}/schema", params={"path": LIVE_WINDOW_FILE})
            answers[_key("schema", {"path": LIVE_WINDOW_FILE})] = {
                "status": schema.status_code,
                "body": _relabel(schema.json(), label),
            }
            params: Params = {"path": LIVE_WINDOW_FILE, "limit": "200"}
            while True:
                response = client.get(f"{HOOK}/rows", params=params)
                body = response.json()
                answers[_key("rows", params)] = {
                    "status": response.status_code,
                    "body": _relabel(body, label),
                }
                if not body.get("next_after"):
                    break
                params = {"path": LIVE_WINDOW_FILE, "after": body["next_after"], "limit": "1000"}
            versions[label] = {"answers": answers}
    return {"versions": versions}


def _versions_on_lines(recorded: dict[str, Any]) -> str:
    """The windowed live recording with each row of an answer on one line."""

    return "".join(
        [
            '{\n  "versions": {\n',
            ",\n".join(
                f"    {json.dumps(label)}: "
                + _rows_on_lines(answers).replace("\n", "\n    ").rstrip()
                for label, answers in recorded["versions"].items()
            ),
            "\n  }\n}\n",
        ]
    )


def test_the_live_window_recording_is_what_the_routes_answer(tmp_path: Path) -> None:
    recorded = _record_live_window(tmp_path)
    rendered = _versions_on_lines(recorded)
    assert json.loads(rendered) == recorded
    check_recording_text("table-view-live-window-responses.json", rendered, transcript=TRANSCRIPT)


def test_each_live_version_changes_what_the_page_reads(tmp_path: Path) -> None:
    versions = _record_live(tmp_path)["versions"]
    rows = _key("rows", {"path": LIVE_FILE, "limit": "200"})
    assert versions["G2"][rows]["body"]["count"] == versions["G1"][rows]["body"]["count"] + 1
    schema = _key("schema", {"path": LIVE_FILE})
    assert [field["name"] for field in versions["G11"][schema]["body"]["fields"]] == ["name"]
    assert versions["G12"][schema]["status"] == 404


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


@pytest.fixture(scope="module")
def session() -> dict[str, Any]:
    return {**run_session("table-view-session.js"), **run_session("table-view-session.js", "live")}


def test_a_burst_of_changes_is_one_read_once_the_window_ends(session: dict[str, Any]) -> None:
    burst = session[
        "live: three changes in a burst, one read again: a cell changed, a row arrived below"
    ]
    assert burst["requests before the window ends"] == []
    assert burst["requests"] == ["rows?limit=200&path=live.csv"]
    assert burst["flashing"] == ["2", "6"]
    assert burst["menu open, its unsent filter kept"] == "4"


def test_a_row_above_the_reader_is_offered_and_the_focus_follows_its_row(
    session: dict[str, Any],
) -> None:
    paused = session[
        "live: sorted, scrolled two rows down, a row focused, and paused: changes counted, not read"
    ]
    assert (paused["pill"], paused["requests"]) == ("Paused · 2 changes", [])
    resumed = session[
        "live: resumed: the row that sorts above the reader's place offered, the one below "
        "drawn, the focus kept"
    ]
    assert (resumed["offer"], resumed["scrollTop"]) == ("1 new row", 66)
    assert resumed["focus"] == paused["focus"]
    taken = session[
        "live: the offer taken: the new row drawn, the view at it, and the keyboard on it"
    ]
    assert taken["rows"][0].startswith("8 | g")
    # Review A of #675, A8: the button pressed is gone, so the keyboard goes to the row.
    assert taken["focus"]["text"] == "8g100"


def test_a_position_named_record_says_when_another_row_is_there(session: dict[str, Any]) -> None:
    record = session[
        "live: the open record, named by position, read again: another row is there now"
    ]
    assert record["requests"][0] == "record?key=%402&path=live.csv"
    assert any("may be a different one" in notice for notice in record["notices"])


def test_a_gone_column_or_file_keeps_the_page_honest(session: dict[str, Any]) -> None:
    dropped = session["live: the sorted column removed: dropped from the address, with a notice"]
    assert dropped["address"] == ""
    gone = session["live: the file removed: the rows last read kept, and said to be"]
    assert gone["rows"] == dropped["rows"]
    assert "This file is no longer there, so these are the rows last read." in gone["notes"]
    # Two refreshes failed; the live region said so once (review A of #675, A8).
    assert gone["announced, each time"] == [
        "This file is no longer there, so these are the rows last read."
    ]
    assert session["live: disposed: the watch released"]["requests"] == ["unwatch live.csv"]


def test_a_live_row_flashes_in_the_shared_live_row_color() -> None:
    """The flash is the Files tree's arrival animation, in --row-flash-bg, and nearly
    instant under reduced motion; what flashes is the session's."""

    repo = Path(__file__).parent.parent
    table_css = (repo / "src/metabrowser/builtin_plugins/table/styles.css").read_text("utf-8")
    shell_css = (repo / "src/metabrowser/static/styles.css").read_text("utf-8")
    view = (repo / "src/metabrowser/builtin_plugins/table/table-view.js").read_text("utf-8")
    keyframes = shell_css.split("@keyframes tree-row-flash-in {", 1)[1].split("}\n}", 1)[0]
    assert "var(--row-flash-bg)" in keyframes
    flash = table_css.split(".data-grid tr.table-row-flash > * {", 1)[1].split("}", 1)[0]
    assert "animation: tree-row-flash-in" in flash
    duration = int(flash.split("tree-row-flash-in ")[1].split("ms")[0])
    assert f"export const LIVE_FLASH_MS = {duration};" in view
    reduced = table_css.split("@media (prefers-reduced-motion: reduce)", 1)[1]
    assert "table-row-flash" in reduced.split("}\n}", 1)[0]


def test_a_refresh_that_changes_nothing_draws_nothing_and_keeps_the_selection(
    session: dict[str, Any],
) -> None:
    """Review A of #675, A9: the selection follows its rows by key, and a refresh whose
    rows read the same leaves the grid as drawn."""

    touched = session[
        "live: the file touched, its rows as they were: nothing drawn again, the selection kept"
    ]
    assert touched["selected"] == ["8", "3"]
    assert touched["first row element kept"] is True
    changed = session[
        "live: a cell changed under the selection, read slowly: the selection stays on its rows"
    ]
    assert changed["selected"] == ["8", "3"]
    assert changed["flashing"] == ["3"]


def test_the_next_refresh_is_spaced_by_what_the_last_cost(session: dict[str, Any]) -> None:
    """Review A of #675, A2: after a read of 400 ms, the next waits 800 ms, not the window."""

    spaced = session[
        "live: after a read that took 400 ms, the next waits twice that, not the window"
    ]
    assert spaced["requests once the window ends"] == []
    assert spaced["requests at twice the last read"] == [
        "rows?limit=200&order=desc&path=live.csv&sort=qty"
    ]


def test_a_hidden_page_reads_nothing_and_reads_once_when_shown(session: dict[str, Any]) -> None:
    hidden = session[
        "live: a change while the page is hidden: nothing read until it is shown, then once"
    ]
    assert hidden["requests while hidden"] == []
    assert hidden["requests"] == ["rows?limit=200&order=desc&path=live.csv&sort=qty"]


def test_a_refresh_reads_the_rows_alone_while_their_columns_hold(session: dict[str, Any]) -> None:
    """Review A of #675, A2: after the first read, the schema is read again only when the
    rows say the question may have moved: a column gone, or the file."""

    asked = [
        name
        for name, step in session.items()
        if name.startswith("live: ") and "schema?path=live.csv" in step.get("requests", [])
    ]
    assert asked == [
        "live: a table read, its file watched with the generation it read",
        "live: the sorted column removed: dropped from the address, with a notice",
        "live: the file removed: the rows last read kept, and said to be",
    ]


def test_a_refused_watch_says_the_table_is_not_following(session: dict[str, Any]) -> None:
    refused = session[
        "live: a watch refused says the table is not following its file, until it is live again"
    ]
    assert refused["notes while refused"] == [
        "This table is not following changes to its file now."
    ]
    assert refused["notes once live"] == []


def test_a_record_read_again_unchanged_is_left_as_drawn_and_can_pause(
    session: dict[str, Any],
) -> None:
    """Review A of #675, A7: no redraw, the keyboard where it was, and a Live control in
    the record pane that pauses the table."""

    again = session[
        "live: a record read again unchanged: not drawn again, the keyboard on its Live control"
    ]
    assert again["record pane drawn again"] is False
    assert again["focus"] == "the record's Live control"
    paused = session["live: the record's Live control pressed: paused there, a change held back"]
    assert (paused["requests"], paused["record pill"]) == ([], "Paused · 1 change")


def test_a_windowed_refresh_leaves_no_rows_above_the_window_as_last_read(
    session: dict[str, Any],
) -> None:
    """Review A of #675, A4: a live refresh asks the question again as refresh() does, from
    the first page as far as the reader reached, so rows above the window are read too and
    none stays as last read under a Live pill."""

    first = session[
        "live window: rows 5 and 45 changed: read again from the start as far as the reader reached"
    ]
    assert first["requests"][0] == "rows?limit=200&path=live-window.csv"
    assert first["rows changed"] == ["45 | 4500"]
    top = session[
        "live window: back at the top: row 5 as read with the rest, nothing stale to read again"
    ]
    assert top["rows changed as it arrives"] == ["5 | 500"]
    assert top["requests"] == []
