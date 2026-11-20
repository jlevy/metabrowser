"""The delimited source through the table routes: `.csv` and `.tsv` files as tables.

The rules are in ``builtin_plugins/delimited/source.py``'s docstring; these check each
one through ``/api/plugin/table/*`` as the browser and ``metab --api`` reach them, with
the server's own classifier and source registry. The CLI transcripts are in
``tests/golden/cli-api-table.tryscript.md``.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.builtin_plugins.delimited import source as delimited
from metabrowser.plugin_loader.static_assets import build_plugin_routes
from metabrowser.table_source import TABLE_CELL_PREVIEW_CHARS, TABLE_TOKEN_MAX_CHARS, Budget


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    server._set_root_dir(tmp_path)
    delimited.PARSE_CACHE.clear()
    table = [plugin for plugin in server._LOADED_PLUGINS if plugin.name == "table"]
    with TestClient(Starlette(routes=build_plugin_routes(table))) as test_client:
        yield test_client
    delimited.PARSE_CACHE.clear()


def _get(client: TestClient, route: str, path: str, **params: str) -> tuple[int, dict[str, Any]]:
    response = client.get(f"/api/plugin/table/{route}", params={"path": path, **params})
    return response.status_code, response.json()


def _rows(client: TestClient, path: str, **params: str) -> dict[str, Any]:
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
    status, schema = _get(client, "schema", "a.csv")
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
    status, schema = _get(client, "schema", "a.csv")
    assert [f["type"] for f in schema["fields"]] == [
        "integer",
        "real",
        "boolean",
        "date",
        "datetime",
        "text",
        "integer",
    ]
    last = _rows(client, "a.csv", after=f"c.{_b64([sample])}")["rows"][0]["cells"]
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
    import base64
    import json

    raw = json.dumps(values, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


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
    status, record = _get(client, "record", "a.csv", key="@1")
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


def test_search_reads_text_fields_and_says_which(client: TestClient, scores: str) -> None:
    body = _rows(client, scores, q="E")
    assert (_keys(body), body["searched"]) == (["@5"], ["name"])


def test_an_exhausted_budget_returns_what_it_found_in_key_order(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = 3 * delimited._BUDGET_CHECK_ROWS
    (tmp_path / "a.csv").write_text("n\n" + "".join(f"{n}\n" for n in range(rows)))
    _rows(client, "a.csv")  # parse first, outside the budget below
    monkeypatch.setattr(delimited.Budget, "start", classmethod(lambda cls, seconds=0: Budget(0)))
    body = _rows(client, "a.csv", sort="n", order="desc", **{"f.n": "ge:0"}, limit="3")
    assert (body["complete"], body["reason"], body["next_after"]) == (False, "budget", None)
    assert body["examined"] == delimited._BUDGET_CHECK_ROWS
    assert _keys(body) == ["@1", "@2", "@3"]
    assert (body["count"], body["count_complete"]) == (delimited._BUDGET_CHECK_ROWS, False)


@pytest.mark.parametrize(
    ("params", "error"),
    [
        ({"sort": "extra"}, "no field named 'extra'"),
        ({"f.n": "gt:five"}, "'five' is not an integer"),
        ({"ref": "other:@1"}, "no field of this table references 'other'"),
        ({"after": "c.WzEsNSwzXQ"}, "after is not a cursor for this sort"),
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
    status, before = _get(client, "record", scores, key="@1")
    target = tmp_path / scores
    target.write_text("name,n\nnew,1\n")
    stamp = time.time() + 5
    os.utime(target, (stamp, stamp))
    status, after = _get(client, "record", scores, key="@1", generation=before["generation"])
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
    held = delimited.PARSE_CACHE._entries  # pyright: ignore[reportPrivateUsage]
    assert len(held) == delimited.DELIMITED_CACHE_MAX_ENTRIES
    assert ("0.csv", ",") not in held
