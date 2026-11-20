"""The delimited source through the table routes: `.csv` and `.tsv` files as tables.

The rules are in ``builtin_plugins/delimited/source.py``'s docstring; these check each
one through ``/api/plugin/table/*`` as the browser and ``metab --api`` reach them, with
the server's own classifier and source registry. The CLI transcripts are in
``tests/golden/cli-api-table.tryscript.md``.
"""

from __future__ import annotations

import asyncio
import base64
import csv
import json
import os
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from metabrowser import server, table_source
from metabrowser.builtin_plugins.delimited import source as delimited
from metabrowser.cli.plugins import _table_source_problems  # pyright: ignore[reportPrivateUsage]
from metabrowser.git.tree_source import GitPath
from metabrowser.plugin_loader.discovery import LoadedPlugin
from metabrowser.plugin_loader.manifest import PLUGIN_SDK_VERSION, PluginManifest
from metabrowser.plugin_loader.static_assets import build_plugin_routes
from metabrowser.table_source import (
    TABLE_CELL_PREVIEW_CHARS,
    TABLE_PAGE_ROWS_MAX,
    TABLE_TOKEN_MAX_CHARS,
    Budget,
    Filter,
    TableQuery,
    TableQueryError,
    TableSourceDeclaration,
    install_table_sources,
    load_adapter,
)
from tests.git_pin_harness import fast_import_store, pinned_client


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    server._set_root_dir(tmp_path)
    delimited.PARSE_CACHE.clear()
    table = [plugin for plugin in server._LOADED_PLUGINS if plugin.name == "table"]
    with TestClient(Starlette(routes=build_plugin_routes(table))) as test_client:
        yield test_client
    delimited.PARSE_CACHE.clear()


Param = str | list[str]


def _get(client: TestClient, route: str, path: str, **params: Param) -> tuple[int, dict[str, Any]]:
    response = client.get(f"/api/plugin/table/{route}", params={"path": path, **params})
    return response.status_code, response.json()


def _rows(client: TestClient, path: str, **params: Param) -> dict[str, Any]:
    status, body = _get(client, "rows", path, **params)
    assert status == 200, body
    return body


def _cells(body: dict[str, Any]) -> list[dict[str, Any]]:
    return [row["cells"] for row in body["rows"]]


def _keys(body: dict[str, Any]) -> list[str]:
    return [row["key"] for row in body["rows"]]


# ── Parsing ──────────────────────────────────────────────────


def test_a_csv_is_one_untyped_keyless_table(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "a.csv").write_text("x,y\n1,2\n")
    status, body = _get(client, "tables", "a.csv")
    assert status == 200
    assert body["tables"] == [
        {
            "id": "",
            "label": "a.csv",
            "group": "tables",
            "keyed": False,
            "estimate": None,
            "path": "a.csv",
        }
    ]
    status, schema = _get(client, "schema", "a.csv")
    assert status == 200
    assert schema["key"] == []
    assert schema["default_columns"] == ["x", "y"]
    assert [(f["name"], f["type"], f["numeric"]) for f in schema["fields"]] == [
        ("x", "integer", True),
        ("y", "integer", True),
    ]


def test_tab_separated_text_splits_on_tabs(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "a.tsv").write_text("x\ty\na,b\tc\n")
    assert _cells(_rows(client, "a.tsv")) == [{"x": "a,b", "y": "c"}]


def test_quoting_is_rfc_4180s(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "a.csv").write_bytes(b'note,n\r\n"a, ""b""\r\nc",1\r\n')
    assert _cells(_rows(client, "a.csv")) == [{"note": 'a, "b"\r\nc', "n": 1}]


def test_a_byte_order_mark_is_dropped(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "a.csv").write_bytes(b"\xef\xbb\xbfname\nada\n")
    assert _rows(client, "a.csv")["columns"] == ["name"]


def test_invalid_bytes_are_replaced_and_marked(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "a.csv").write_bytes(b"name,n\nab\xff,1\nok\xef\xbf\xbd,2\n")
    assert _cells(_rows(client, "a.csv")) == [
        {"name": {"text": "ab�", "invalid_utf8": True}, "n": 1},
        # A replacement character the file really holds is not invalid.
        {"name": "ok�", "n": 2},
    ]


def test_header_names_are_filled_and_made_unique(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "a.csv").write_text("a,,a,b,a\n1,2,3,4,5\n")
    assert _rows(client, "a.csv")["columns"] == ["a", "column_2", "a_2", "b", "a_3"]


def test_short_rows_are_absent_long_rows_go_to_extra(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "a.csv").write_text("a,b\n1\n\n2,3,4,5\n6,\n")
    body = _rows(client, "a.csv")
    assert body["columns"] == ["a", "b", "extra"]
    # A blank line is not a row, so the long row is the second.
    assert _keys(body) == ["@1", "@2", "@3"]
    assert _cells(body) == [{"a": 1}, {"a": 2, "b": 3, "extra": ["4", "5"]}, {"a": 6, "b": None}]
    _status, schema = _get(client, "schema", "a.csv")
    extra = schema["fields"][-1]
    assert (extra["name"], extra["list"], extra["sortable"], extra["filterable"]) == (
        "extra",
        True,
        False,
        False,
    )


def test_types_are_inferred_and_contradictions_shown(client: TestClient, tmp_path: Path) -> None:
    sample = delimited.DELIMITED_TYPE_SAMPLE_ROWS
    lines = ["i,r,b,d,t,z,big"]
    lines += [
        f"{n},{n}.5,true,2020-01-0{n % 9 + 1},2020-01-01T10:00:00Z,007,1" for n in range(sample)
    ]
    lines.append("x,1e999,maybe,2020-02-30,later,8,99999999999999999999")
    (tmp_path / "a.csv").write_text("\n".join(lines) + "\n")
    _status, schema = _get(client, "schema", "a.csv")
    assert [f["type"] for f in schema["fields"]] == [
        "integer",
        "real",
        "boolean",
        "date",
        "datetime",
        "text",
        "integer",
    ]
    last = _rows(client, "a.csv", after=f"c.{_b64([None, 'asc', sample])}")["rows"][0]["cells"]
    assert last == {
        "i": {"value": "x", "stored": "text"},
        "r": {"real": "inf"},
        "b": {"value": "maybe", "stored": "text"},
        "d": {"value": "2020-02-30", "stored": "text"},
        "t": {"value": "later", "stored": "text"},
        "z": "8",
        "big": {"int": "99999999999999999999"},
    }


def _b64(values: list[Any]) -> str:
    return _b64_raw(json.dumps(values, separators=(",", ":")))


def _b64_raw(payload: str) -> str:
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def test_a_datetime_column_says_it_sorts_as_text(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "a.csv").write_text("t,d\n2024-01-01T09:00:00Z,2024-01-01\n")
    _status, schema = _get(client, "schema", "a.csv")
    notes = {f["name"]: f["sort_note"] for f in schema["fields"]}
    assert notes["t"] is not None and notes["t"].startswith("sorted as text")
    assert notes["d"] is None


def test_empty_is_null_in_a_typed_column_and_empty_in_text(
    client: TestClient, tmp_path: Path
) -> None:
    (tmp_path / "a.csv").write_text("n,t\n1,a\n,\n")
    assert _cells(_rows(client, "a.csv")) == [{"n": 1, "t": "a"}, {"n": None, "t": ""}]


def test_long_text_is_previewed_in_rows_and_whole_in_the_record(
    client: TestClient, tmp_path: Path
) -> None:
    long = "é" * (TABLE_CELL_PREVIEW_CHARS + 5)
    (tmp_path / "a.csv").write_text(f"t\n{long}\n")
    assert _cells(_rows(client, "a.csv")) == [
        {"t": {"text": "é" * TABLE_CELL_PREVIEW_CHARS, "length": len(long)}}
    ]
    _status, record = _get(client, "record", "a.csv", key="@1")
    assert record["cells"] == {"t": long}


def test_an_empty_file_is_a_table_with_no_columns(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "a.csv").write_text("")
    body = _rows(client, "a.csv")
    assert (body["columns"], body["rows"], body["count"]) == ([], [], 0)


def test_a_file_past_the_parse_cap_shows_its_leading_rows(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(delimited, "DELIMITED_PARSE_MAX_BYTES", 20)
    (tmp_path / "a.csv").write_text("n\n1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n")
    body = _rows(client, "a.csv")
    # 20 bytes end with the ninth row, which the read cannot know is whole, so it goes.
    assert _cells(body) == [{"n": n} for n in range(1, 9)]
    assert (body["complete"], body["truncated"], body["reason"]) == (
        False,
        True,
        "source_truncated",
    )
    assert (body["count"], body["count_complete"]) == (8, False)


def test_a_compressed_file_reads_through_its_stream(client: TestClient, tmp_path: Path) -> None:
    import gzip

    (tmp_path / "a.csv.gz").write_bytes(gzip.compress(b"n\n1\n"))
    assert _cells(_rows(client, "a.csv.gz")) == [{"n": 1}]


# ── Sorting, paging, filtering, search ───────────────────────


@pytest.fixture
def scores(tmp_path: Path) -> str:
    (tmp_path / "s.csv").write_text("name,n\nc,10\na,\nb,5\nd,7\ne,5\n")
    return "s.csv"


def test_sort_puts_nulls_first_ascending_and_last_descending(
    client: TestClient, scores: str
) -> None:
    assert _keys(_rows(client, scores, sort="n")) == ["@2", "@3", "@5", "@4", "@1"]
    assert _keys(_rows(client, scores, sort="n", order="desc")) == ["@1", "@4", "@5", "@3", "@2"]


@pytest.mark.parametrize("order", ["asc", "desc"])
@pytest.mark.parametrize("sort", [None, "n", "name"])
def test_cursor_paging_visits_every_row_once(
    client: TestClient, scores: str, order: str, sort: str | None
) -> None:
    params = {"order": order, **({"sort": sort} if sort else {})}
    whole = _keys(_rows(client, scores, **params))
    seen: list[str] = []
    after: str | None = None
    while True:
        body = _rows(client, scores, limit="2", **params, **({"after": after} if after else {}))
        seen += _keys(body)
        after = body["next_after"]
        if after is None:
            break
    assert seen == whole


def test_a_cursor_stays_a_sort_position_across_generations(
    client: TestClient, scores: str, tmp_path: Path
) -> None:
    first = _rows(client, scores, sort="n", limit="2")
    assert _keys(first) == ["@2", "@3"]
    # A row added that sorts before the cursor's position does not shift the next page,
    # as an offset would. A keyless row's tie-breaker is its position, so a row inserted
    # above it in the file would move it.
    (tmp_path / scores).write_text("name,n\nc,10\na,\nb,5\nd,7\ne,5\nz,1\n")
    after = _rows(client, scores, sort="n", limit="2", after=first["next_after"])
    assert [cells["name"] for cells in _cells(after)] == ["e", "d"]
    assert after["generation"] != first["generation"]


def test_a_sort_value_past_the_token_bound_pages_by_position(
    client: TestClient, tmp_path: Path
) -> None:
    long = "x" * TABLE_TOKEN_MAX_CHARS
    (tmp_path / "a.csv").write_text(f"t\n{long}a\n{long}b\n{long}c\n")
    first = _rows(client, "a.csv", sort="t", limit="1")
    assert first["next_after"] == f"@1.{first['generation']}"
    second = _rows(client, "a.csv", sort="t", limit="1", after=first["next_after"])
    assert _keys(second) == ["@2"]
    stale = _rows(client, "a.csv", sort="t", after="@1.0000")
    assert (stale["rows"], stale["complete"], stale["reason"]) == ([], False, "cursor_expired")


def test_filters_compare_typed_values_and_skip_nulls(client: TestClient, scores: str) -> None:
    assert _keys(_rows(client, scores, **{"f.n": "ge:7"})) == ["@1", "@4"]
    assert _keys(_rows(client, scores, **{"f.n": "ne:5"})) == ["@1", "@4"]
    assert _keys(_rows(client, scores, **{"f.n": "null"})) == ["@2"]
    assert _keys(_rows(client, scores, **{"f.n": "notnull", "f.name": "lt:d"})) == ["@1", "@3"]
    assert _keys(_rows(client, scores, **{"f.name": "contains:B"})) == ["@3"]
    assert _rows(client, scores, **{"f.n": "eq:5"})["count"] == 2


def test_search_reads_text_fields_and_names_them(client: TestClient, scores: str) -> None:
    body = _rows(client, scores, q="E")
    assert (_keys(body), body["searched"]) == (["@5"], ["name"])


def _spend_every_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    def spent(cls: type[Budget], seconds: float = 0.0) -> Budget:
        return Budget(0)

    monkeypatch.setattr(Budget, "start", classmethod(spent))


@pytest.fixture
def numbers(client: TestClient, tmp_path: Path) -> str:
    rows = 3 * delimited._BUDGET_CHECK_ROWS
    (tmp_path / "a.csv").write_text("n\n" + "".join(f"{n}\n" for n in range(rows)))
    _rows(client, "a.csv")  # parse first, outside any spent budget
    return "a.csv"


@pytest.mark.parametrize(
    ("order", "first"),
    [("asc", ["@1", "@2", "@3"]), ("desc", [f"@{3 * 4096 - n}" for n in range(3)])],
)
def test_an_exhausted_budget_returns_what_it_found_in_the_querys_order(
    client: TestClient,
    numbers: str,
    monkeypatch: pytest.MonkeyPatch,
    order: str,
    first: list[str],
) -> None:
    assert delimited._BUDGET_CHECK_ROWS == 4096
    _spend_every_budget(monkeypatch)
    body = _rows(client, numbers, order=order, **{"f.n": "ge:0"}, limit="3")
    assert (body["complete"], body["reason"], body["sort_refused"]) == (False, "budget", None)
    assert body["examined"] == delimited._BUDGET_CHECK_ROWS
    assert _keys(body) == first
    assert (body["count"], body["count_complete"]) == (delimited._BUDGET_CHECK_ROWS, False)
    # The cursor continues among the rows found, in the same order.
    after = _rows(
        client, numbers, order=order, **{"f.n": "ge:0"}, limit="3", after=body["next_after"]
    )
    whole = _rows(client, numbers, order=order, **{"f.n": "ge:0"}, limit="6")
    assert _keys(body) + _keys(after) == _keys(whole)


def test_a_sort_the_budget_cannot_finish_is_refused_by_name(
    client: TestClient, numbers: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _spend_every_budget(monkeypatch)
    # The scan before the sort runs out.
    scanned = _rows(client, numbers, sort="n", order="desc", **{"f.n": "ge:0"}, limit="3")
    assert (scanned["rows"], scanned["complete"], scanned["next_after"]) == ([], False, None)
    assert (scanned["reason"], scanned["sort_refused"]) == ("sort_budget", "n")
    assert (scanned["examined"], scanned["count_complete"]) == (delimited._BUDGET_CHECK_ROWS, False)
    # No scan, but the sort's index is not built and the budget is spent before it.
    unbuilt = _rows(client, numbers, sort="n", limit="3")
    assert (unbuilt["rows"], unbuilt["reason"], unbuilt["sort_refused"]) == ([], "sort_budget", "n")
    assert (unbuilt["count"], unbuilt["count_complete"], unbuilt["examined"]) == (
        3 * delimited._BUDGET_CHECK_ROWS,
        True,
        None,
    )
    monkeypatch.undo()
    _rows(client, numbers, sort="n", limit="1")  # builds the index within a fresh budget
    _spend_every_budget(monkeypatch)
    built = _rows(client, numbers, sort="n", order="desc", limit="2")
    assert (_keys(built), built["reason"], built["sort_refused"]) == (
        [f"@{3 * 4096}", f"@{3 * 4096 - 1}"],
        None,
        None,
    )


@pytest.mark.parametrize(
    ("params", "error"),
    [
        ({"sort": "extra"}, "no field named 'extra'"),
        ({"f.n": "gt:five"}, "'five' is not an integer"),
        ({"ref": "other:@1"}, "no field of this table references 'other'"),
        (
            {"after": "c.WzEsNSwzXQ"},
            "after is not a cursor for this query: it was made for sort=1 order=5",
        ),
    ],
)
def test_a_query_the_table_cannot_serve_is_refused(
    client: TestClient, scores: str, params: dict[str, str], error: str
) -> None:
    status, body = _get(client, "rows", scores, **params)
    assert (status, body["code"], body["error"]) == (400, "bad_query", error)


# ── Records, cards, and generations ──────────────────────────


def test_a_record_is_named_by_position(client: TestClient, scores: str) -> None:
    status, record = _get(client, "record", scores, key="@3")
    assert status == 200
    assert (record["key"], record["positional"], record["cells"]) == (
        "@3",
        True,
        {"name": "b", "n": 5},
    )
    assert record["generation_moved"] is None
    status, moved = _get(client, "record", scores, key="@3", generation=record["generation"])
    assert moved["generation_moved"] is False


def test_a_record_reports_a_moved_generation(
    client: TestClient, scores: str, tmp_path: Path
) -> None:
    _status, before = _get(client, "record", scores, key="@1")
    target = tmp_path / scores
    target.write_text("name,n\nnew,1\n")
    stamp = time.time() + 5
    os.utime(target, (stamp, stamp))
    _status, after = _get(client, "record", scores, key="@1", generation=before["generation"])
    assert (after["generation_moved"], after["cells"]) == (True, {"name": "new", "n": 1})


def test_a_card_is_a_label_and_a_few_fields(client: TestClient, tmp_path: Path) -> None:
    header = ",".join(f"c{n}" for n in range(10))
    (tmp_path / "a.csv").write_text(f"{header}\n" + ",".join(f"v{n}" for n in range(10)) + "\n")
    status, card = _get(client, "card", "a.csv", key="@1")
    assert status == 200
    assert card["label"] == "v0"
    assert list(card["cells"]) == ["c1", "c2", "c3", "c4", "c5", "c6"]


@pytest.mark.parametrize(
    ("route", "params", "status", "code"),
    [
        ("record", {"key": "@9"}, 404, "record_not_found"),
        ("record", {"key": "k.WzFd"}, 404, "record_not_found"),
        ("record", {"key": "@0"}, 404, "record_not_found"),
        ("card", {}, 400, "bad_query"),
    ],
)
def test_a_record_the_file_does_not_hold_is_refused(
    client: TestClient, scores: str, route: str, params: dict[str, str], status: int, code: str
) -> None:
    found, body = _get(client, route, scores, **params)
    assert (found, body["code"]) == (status, code)


def test_paths_that_are_not_tables_are_refused(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("x\n")
    (tmp_path / "dir").mkdir()
    assert _get(client, "schema", "missing.csv")[1]["code"] == "not_found"
    assert _get(client, "schema", "dir")[1]["code"] == "not_found"
    assert _get(client, "schema", "../escape.csv")[1]["code"] == "not_found"
    status, body = _get(client, "schema", "a.txt")
    assert (status, body["code"], body["kind"]) == (404, "not_a_table_source", "text")


def test_a_parse_is_cached_per_generation(client: TestClient, scores: str, tmp_path: Path) -> None:
    first = _rows(client, scores)
    cached = delimited.PARSE_CACHE.get((scores, ","), first["generation"])
    assert cached is not None
    assert _rows(client, scores)["generation"] == first["generation"]
    assert delimited.PARSE_CACHE.get((scores, ","), first["generation"]) is cached


def test_the_cache_is_bounded_in_entries(client: TestClient, tmp_path: Path) -> None:
    for number in range(delimited.DELIMITED_CACHE_MAX_ENTRIES + 2):
        (tmp_path / f"{number}.csv").write_text("n\n1\n")
        _rows(client, f"{number}.csv")
    held = delimited.PARSE_CACHE._held  # pyright: ignore[reportPrivateUsage]
    assert len(held) == delimited.DELIMITED_CACHE_MAX_ENTRIES
    assert ("0.csv", ",") not in held


# ── Tokens the server did not mint ───────────────────────────


@pytest.fixture
def typed(tmp_path: Path) -> str:
    (tmp_path / "t.csv").write_text(
        "n,d,r,b,s\n3,2024-01-03,1.5,true,x\n1,2024-01-01,,false,y\n2,,2.5,,z\n"
    )
    return "t.csv"


def test_a_cursor_from_another_sort_is_refused_by_name(client: TestClient, typed: str) -> None:
    by_date = _rows(client, typed, sort="d", limit="1")
    status, body = _get(client, "rows", typed, sort="n", after=by_date["next_after"])
    assert (status, body["code"], body["param"]) == (400, "bad_query", "after")
    assert 'made for sort="d" order="asc"' in body["error"]
    status, body = _get(client, "rows", typed, sort="d", order="desc", after=by_date["next_after"])
    assert (status, body["code"]) == (400, "bad_query")


@pytest.mark.parametrize(
    ("params", "status", "code"),
    [
        # Values of the wrong type for the sort column, in the cursor's own format.
        ({"sort": "n", "after": f"c.{_b64(['n', 'asc', 1, 'x', 5])}"}, 400, "bad_query"),
        ({"sort": "n", "after": f"c.{_b64(['n', 'asc', 1, [1], 5])}"}, 400, "bad_query"),
        ({"sort": "n", "after": f"c.{_b64(['n', 'asc', 1, None, 5])}"}, 400, "bad_query"),
        ({"sort": "n", "after": f"c.{_b64(['n', 'asc', 1, True, 5])}"}, 400, "bad_query"),
        ({"sort": "b", "after": f"c.{_b64(['b', 'asc', 1, 1, 5])}"}, 400, "bad_query"),
        ({"sort": "d", "after": f"c.{_b64(['d', 'asc', 1, 7, 5])}"}, 400, "bad_query"),
        ({"sort": "s", "after": f"c.{_b64(['s', 'asc', 1, 'x', 5])}"}, 400, "bad_query"),
        ({"sort": "s", "after": f"c.{_b64(['s', 'asc', 2, 3, 5])}"}, 400, "bad_query"),
        ({"sort": "n", "after": f"c.{_b64(['n', 'asc', '1', 3, 5])}"}, 400, "bad_query"),
        # The review's tokens, in the format this layer first minted.
        ({"sort": "n", "after": f"c.{_b64([1, 'x', 5])}"}, 400, "bad_query"),
        ({"sort": "n", "after": f"c.{_b64([1, [1], 5])}"}, 400, "bad_query"),
        ({"sort": "n", "after": f"c.{_b64([1, None, 5])}"}, 400, "bad_query"),
        # Positions that are not positive integers, an infinity among them.
        ({"after": f"c.{_b64_raw('[1e999]')}"}, 400, "bad_query"),
        ({"after": f"c.{_b64_raw('[null,"asc",1e999]')}"}, 400, "bad_query"),
        ({"sort": "n", "after": f"c.{_b64_raw('[1,5,1e999]')}"}, 400, "bad_query"),
        ({"sort": "n", "after": f"c.{_b64_raw('["n","asc",1,5,1e999]')}"}, 400, "bad_query"),
        ({"after": f"c.{_b64([None, 'asc', 0])}"}, 400, "bad_query"),
        ({"after": f"c.{_b64([None, 'asc', True])}"}, 400, "bad_query"),
        ({"after": "@" + "1" * 5000 + ".abc"}, 400, "bad_query"),
    ],
)
def test_a_token_the_server_did_not_mint_is_a_bad_query(
    client: TestClient, typed: str, params: dict[str, str], status: int, code: str
) -> None:
    found, body = _get(client, "rows", typed, **params)
    assert (found, body["code"]) == (status, code), body


def test_a_real_cursor_carries_infinities(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "r.csv").write_text("r\n1e999\n1.5\n-1e999\n")
    seen: list[str] = []
    after: str | None = None
    while True:
        body = _rows(client, "r.csv", sort="r", limit="1", **({"after": after} if after else {}))
        seen += _keys(body)
        after = body["next_after"]
        if after is None:
            break
    assert seen == ["@3", "@2", "@1"]


def test_a_long_key_names_no_row_and_a_long_limit_is_the_maximum(
    client: TestClient, typed: str
) -> None:
    for route in ("record", "card"):
        status, body = _get(client, route, typed, key="@" + "1" * 5000)
        assert (status, body["code"]) == (404, "record_not_found")
    assert _rows(client, typed, limit="1" * 5000)["limit"] == TABLE_PAGE_ROWS_MAX


# ── Bounds on what a file costs ──────────────────────────────


def test_naming_a_repeated_header_is_linear() -> None:
    started = time.perf_counter()
    names = delimited._column_names(["a"] * 20_000)
    # A name scan per retry made this cubic: 3,000 of one name took 28 s.
    assert time.perf_counter() - started < 1.0
    assert names[:3] == ["a", "a_2", "a_3"] and names[-1] == "a_20000"
    assert len(set(names)) == len(names)
    assert delimited._column_names(["a", "a_2", "a", "a", "a_2"]) == [
        "a",
        "a_2",
        "a_3",
        "a_4",
        "a_2_2",
    ]
    assert delimited._column_names(["", "column_1", ""]) == ["column_1", "column_1_2", "column_3"]


def test_cells_past_the_column_bound_are_not_read(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(delimited, "DELIMITED_MAX_COLUMNS", 3)
    (tmp_path / "wide.csv").write_text("a,b,c,d,e\n1,2,3,4,5\n6,7\n")
    body = _rows(client, "wide.csv")
    assert body["columns"] == ["a", "b", "c"]
    assert _cells(body) == [{"a": 1, "b": 2, "c": 3}, {"a": 6, "b": 7}]
    assert (body["complete"], body["truncated"], body["reason"]) == (
        False,
        True,
        "source_truncated",
    )
    # Every row was read, so the count is exact.
    assert (body["count"], body["count_complete"]) == (2, True)
    (tmp_path / "long.csv").write_text("a,b\n1,2,3,4,5\n")
    long = _rows(client, "long.csv")
    assert _cells(long) == [{"a": 1, "b": 2, "extra": ["3"]}]
    assert long["truncated"] is True


@pytest.mark.parametrize(
    ("bound", "value"), [("DELIMITED_MAX_ROWS", 3), ("DELIMITED_MAX_CELLS", 8)]
)
def test_a_file_past_its_row_or_cell_bound_shows_its_leading_rows(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bound: str, value: int
) -> None:
    monkeypatch.setattr(delimited, bound, value)
    (tmp_path / "a.csv").write_text("n,m\n1,1\n2,2\n3,3\n4,4\n5,5\n")
    body = _rows(client, "a.csv", sort="n", order="desc")
    # Three rows, or the header and three rows of two cells within eight cells.
    assert [cells["n"] for cells in _cells(body)] == [3, 2, 1]
    assert (body["complete"], body["truncated"], body["reason"]) == (
        False,
        True,
        "source_truncated",
    )
    assert (body["count"], body["count_complete"]) == (3, False)


def test_a_page_of_wide_rows_carries_fewer_and_says_so(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(table_source, "TABLE_PAGE_CELLS_MAX", 6)
    (tmp_path / "a.csv").write_text("a,b,c\n1,2,3\n4,5,6\n7,8,9,10,11\n")
    # Two named columns and the extra list, which holds up to two cells: four a row.
    body = _rows(client, "a.csv", limit="100")
    assert (body["limit"], _keys(body)) == (1, ["@1"])
    assert body["next_after"] is not None
    narrow = _rows(client, "a.csv", cols=["a", "b"], limit="100")
    assert (narrow["limit"], _keys(narrow)) == (3, ["@1", "@2", "@3"])


def test_held_bytes_follow_the_files_shape_and_its_sort_indexes() -> None:
    narrow = delimited.parse_delimited(
        b"n\n" + b"7\n" * 1000, has_more=False, delimiter=",", generation="g"
    )
    wide = delimited.parse_delimited(
        b"a,b,c,d\n" + b"x,y,z,w\n" * 250, has_more=False, delimiter=",", generation="g"
    )
    # Bytes alone would call these alike; their rows and cells differ.
    assert narrow.parsed_bytes == 1001 * 96 + 1001 * 56 + 2002
    assert wide.parsed_bytes == 251 * 96 + 1004 * 56 + 2008
    accented = delimited.parse_delimited(
        "t\né\n".encode(), has_more=False, delimiter=",", generation="g"
    )
    assert accented.parsed_bytes == 2 * 96 + 2 * 56 + 4 * len("t\né\n".encode())
    before = narrow.held_bytes
    index = narrow.sort_index(0, Budget.start())
    assert index is not None
    assert narrow.held_bytes == before + len(index) * index.itemsize


def test_the_cache_counts_a_sort_index_and_evicts_for_it(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("a.csv", "b.csv"):
        (tmp_path / name).write_text("n\n" + "".join(f"{n}\n" for n in range(1000)))
    one = delimited.parse_delimited(
        (tmp_path / "a.csv").read_bytes(), has_more=False, delimiter=",", generation="g"
    )
    # Room for both files, but not for both and a sort index.
    monkeypatch.setattr(delimited, "DELIMITED_CACHE_MAX_BYTES", 2 * one.parsed_bytes + 100)
    _rows(client, "a.csv")
    _rows(client, "b.csv")
    held = delimited.PARSE_CACHE._held  # pyright: ignore[reportPrivateUsage]
    assert [key[0] for key in held] == ["a.csv", "b.csv"]
    _rows(client, "b.csv", sort="n")
    assert [key[0] for key in held] == ["b.csv"]


def test_a_parse_restores_the_csv_field_limit(tmp_path: Path) -> None:
    before = csv.field_size_limit()
    long = "x" * (before + 10)
    parsed = delimited.parse_delimited(
        f"t\n{long}\n".encode(), has_more=False, delimiter=",", generation="g"
    )
    assert parsed.rows == [[long]]
    assert csv.field_size_limit() == before


def test_concurrent_first_requests_parse_a_file_once(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "a.csv").write_text("n\n1\n2\n")
    parses: list[int] = []
    real = delimited.parse_delimited
    entered = threading.Event()

    def slow(data: bytes, **kwargs: Any) -> Any:
        parses.append(1)
        entered.set()
        time.sleep(0.3)
        return real(data, **kwargs)

    monkeypatch.setattr(delimited, "parse_delimited", slow)
    answers: list[int] = []

    def ask(route: str) -> None:
        answers.append(_get(client, route, "a.csv")[0])

    first = threading.Thread(target=ask, args=("schema",))
    first.start()
    assert entered.wait(5)
    others = [threading.Thread(target=ask, args=(route,)) for route in ("rows", "rows", "card")]
    for thread in others:
        thread.start()
    for thread in (first, *others):
        thread.join(10)
    assert sorted(answers) == [200, 200, 200, 400]  # the card names no key
    assert len(parses) == 1


def test_a_failed_parse_lets_the_next_request_parse_again() -> None:
    cache = delimited._ParseCache()
    calls: list[int] = []

    def fail() -> Any:
        calls.append(1)
        raise delimited.SourceUnreadableError("no")

    for _ in range(2):
        with pytest.raises(delimited.SourceUnreadableError):
            cache.load(("a.csv", ","), "g", fail)
    assert len(calls) == 2


def test_the_source_refuses_a_field_it_does_not_have() -> None:
    # The route checks the query against one parse and reads another; if the file lost
    # the column in between, the source refuses rather than failing.
    parsed = delimited.parse_delimited(b"n\n1\n", has_more=False, delimiter=",", generation="g")
    for query in (TableQuery(sort="gone"), TableQuery(filters=(Filter("gone", "eq", "1"),))):
        with pytest.raises(TableQueryError, match="no field named 'gone'"):
            delimited._page(parsed, query, Budget.start())


def test_a_page_with_no_tests_lists_no_row_indexes() -> None:
    parsed = delimited.parse_delimited(
        b"n\n1\n2\n3\n", has_more=False, delimiter=",", generation="g"
    )
    scan = delimited._scan(parsed, [], Budget.start(), descending=True)
    assert scan.matches == range(2, -1, -1)


def test_a_header_name_may_hold_a_comma(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "a.csv").write_text('"Last, First",b\n"Lovelace, Ada",1\n')
    body = _rows(client, "a.csv", cols="Last, First")
    assert _cells(body) == [{"Last, First": "Lovelace, Ada"}]
    both = _rows(client, "a.csv", cols=["b", "Last, First"])
    assert both["columns"] == ["b", "Last, First"]


# ── A Git pin ────────────────────────────────────────────────


def test_the_routes_read_a_table_on_a_pin(tmp_path: Path) -> None:
    store, commit = fast_import_store(
        tmp_path,
        {
            b"people.csv": b"name,n\nada,3\nbob,1\ncy,2\n",
            b"cities.tsv": b"city\tpop\nLima\t10\n",
            b"notes.txt": b"x\n",
        },
        symlinks={b"alias.csv": b"people.csv", b"out.csv": b"../outside.csv"},
    )

    def wire(name: str) -> str:
        return GitPath.from_segments(name.encode()).to_wire()

    async def run() -> dict[str, Any]:
        delimited.PARSE_CACHE.clear()
        answers: dict[str, Any] = {}
        async with pinned_client(store, commit) as (client, _subject):
            for name, route, params in (
                ("tables", "tables", {"path": wire("people.csv")}),
                ("rows", "rows", {"path": wire("people.csv"), "sort": "n", "order": "desc"}),
                ("record", "record", {"path": wire("people.csv"), "key": "@2"}),
                ("tsv", "rows", {"path": wire("cities.tsv")}),
                ("alias", "rows", {"path": wire("alias.csv"), "sort": "name"}),
                ("missing", "schema", {"path": wire("gone.csv")}),
                ("escape", "schema", {"path": wire("out.csv")}),
                ("text", "schema", {"path": wire("notes.txt")}),
            ):
                response = await client.get(f"/api/plugin/table/{route}", params=params)
                answers[name] = (response.status_code, response.json())
        delimited.PARSE_CACHE.clear()
        return answers

    answers = asyncio.run(run())
    status, tables = answers["tables"]
    assert status == 200
    assert [(t["id"], t["label"], t["keyed"]) for t in tables["tables"]] == [
        ("", "people.csv", False)
    ]
    status, rows = answers["rows"]
    assert (status, _keys(rows), rows["complete"]) == (200, ["@1", "@3", "@2"], True)
    # A pin's content cannot change, so its generation is the blob's object id.
    assert len(rows["generation"]) == 40 and rows["generation"] == tables["generation"]
    status, record = answers["record"]
    assert (status, record["cells"], record["positional"]) == (200, {"name": "bob", "n": 1}, True)
    assert _cells(answers["tsv"][1]) == [{"city": "Lima", "pop": 10}]
    assert [cells["name"] for cells in _cells(answers["alias"][1])] == ["ada", "bob", "cy"]
    assert answers["missing"][1]["code"] == "not_found"
    assert answers["escape"][1]["code"] == "not_found"
    assert (answers["text"][0], answers["text"][1]["code"]) == (404, "not_a_table_source")


def test_every_table_source_kind_classifies_on_a_pin_by_name_alone() -> None:
    # On a pin a table route classifies by the Git-blob subset of the rules (extension
    # and basename) and, for bytes that sniff as binary, a kind's magic number from the
    # blob's first bytes; a table source whose kind needed more would not be served there.
    pin_rules = {"ext", "exts", "basename", "magic"}
    # An fsqlite store is read on a served folder only: its files are found beside its
    # marker by path, which a pin's identities do not offer, so on a pin its marker is
    # the JSON file it is, and its routes answer `unsupported_for_subject`.
    served_folder_only = {"sqlite-store"}
    served = {
        declaration.kind
        for declaration in server._table_source_declarations()  # pyright: ignore[reportPrivateUsage]
    }
    assert "delimited" in served
    assert served_folder_only <= served
    for plugin in server._LOADED_PLUGINS:  # pyright: ignore[reportPrivateUsage]
        for kind in plugin.manifest.kind:
            if kind.id in served - served_folder_only:
                used = set(kind.match.model_dump(exclude_none=True))
                assert used <= pin_rules, (plugin.name, kind.id, used)


# ── Registration and the doctor ──────────────────────────────


def adapter_for_tests(handle: Any) -> Any:
    return handle


not_callable = 7


@pytest.fixture
def registry() -> Iterator[None]:
    saved = table_source._REGISTRY  # pyright: ignore[reportPrivateUsage]
    table_source._REGISTRY = table_source._Registry()  # pyright: ignore[reportPrivateUsage]
    yield
    table_source._REGISTRY = saved  # pyright: ignore[reportPrivateUsage]


async def _no_kind(_ref: Any) -> str | None:
    return None


def test_a_later_declaration_for_a_kind_replaces_an_earlier_one(registry: None) -> None:
    module = __name__
    install_table_sources(
        [
            TableSourceDeclaration(plugin="first", kind="k", adapter=f"{module}:not_callable"),
            TableSourceDeclaration(
                plugin="second", kind="k", adapter=f"{module}:adapter_for_tests"
            ),
        ],
        _no_kind,
    )
    declaration = table_source._REGISTRY.declarations["k"]  # pyright: ignore[reportPrivateUsage]
    assert declaration.plugin == "second"
    loaded = load_adapter(declaration)
    assert loaded is adapter_for_tests
    # Imported once, then reused.
    assert table_source._REGISTRY.adapters == {"k": adapter_for_tests}  # pyright: ignore[reportPrivateUsage]


def test_an_adapter_that_does_not_import_or_call_is_refused(registry: None) -> None:
    with pytest.raises(TypeError, match="is not callable"):
        load_adapter(
            TableSourceDeclaration(plugin="p", kind="a", adapter=f"{__name__}:not_callable")
        )
    with pytest.raises(ImportError):
        load_adapter(
            TableSourceDeclaration(plugin="p", kind="b", adapter="no_such_module_x:adapter")
        )
    assert table_source._REGISTRY.adapters == {}  # pyright: ignore[reportPrivateUsage]


def _plugin(source: str, adapter: str) -> LoadedPlugin:
    manifest = PluginManifest.model_validate(
        {
            "plugin": {"name": "tabular", "sdk_version": PLUGIN_SDK_VERSION, "requires": ["table"]},
            "kind": [{"id": "tabular", "match": {"ext": ".tabular"}}],
            "table_source": [{"kind": "tabular", "adapter": adapter}],
        }
    )
    return LoadedPlugin(
        name="tabular", static_root=Path("/nonexistent"), manifest=manifest, source=source
    )


def test_an_operator_directory_plugins_table_sources_are_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    local = _plugin("local:/plugins/tabular", f"{__name__}:adapter_for_tests")
    installed = _plugin("entry-point:tabular", f"{__name__}:adapter_for_tests")
    monkeypatch.setattr(server, "_LOADED_PLUGINS", [local])
    assert server._table_source_declarations() == []  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(server, "_LOADED_PLUGINS", [installed])
    assert server._table_source_declarations() == [  # pyright: ignore[reportPrivateUsage]
        TableSourceDeclaration(
            plugin="tabular", kind="tabular", adapter=f"{__name__}:adapter_for_tests"
        )
    ]


@pytest.mark.parametrize(
    ("source", "adapter", "problem"),
    [
        ("entry-point:tabular", f"{__name__}:adapter_for_tests", None),
        (
            "local:/plugins/tabular",
            f"{__name__}:adapter_for_tests",
            "operator-directory plugins are JavaScript-only",
        ),
        ("entry-point:tabular", "no_such_module_x:adapter", "cannot import 'no_such_module_x'"),
        ("entry-point:tabular", f"{__name__}:not_callable", "is not a callable"),
    ],
)
def test_the_doctor_reports_a_table_source_that_cannot_serve(
    source: str, adapter: str, problem: str | None
) -> None:
    problems = _table_source_problems(_plugin(source, adapter))
    if problem is None:
        assert problems == []
    else:
        assert len(problems) == 1 and problem in problems[0], problems
