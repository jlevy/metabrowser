"""The record-list table source: a JSON or YAML list of mappings through the table routes.

``builtin_plugins/structured/records.py`` builds one table from the structured plugin's
own parse; these tests drive it through ``/api/plugin/table/*`` as the Table view does,
and through the structured plugin's ``parsed`` route where the two share a parse.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.builtin_plugins import structured
from metabrowser.builtin_plugins.structured import parser, records
from metabrowser.builtin_plugins.table import memory
from metabrowser.git.tree_source import GitPath
from metabrowser.plugin_loader.static_assets import build_plugin_routes
from metabrowser.table_source import TABLE_CELL_PREVIEW_CHARS, Budget
from tests.git_pin_harness import fast_import_store, pinned_client


def _clear() -> None:
    records.RECORDS_CACHE.clear()
    parser._PAYLOAD_CACHE.clear()  # pyright: ignore[reportPrivateUsage]


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    server._set_root_dir(tmp_path)
    _clear()
    plugins = [p for p in server._LOADED_PLUGINS if p.name in ("table", "structured")]
    with TestClient(Starlette(routes=build_plugin_routes(plugins))) as test_client:
        yield test_client
    _clear()


Param = str | list[str]


def _get(client: TestClient, route: str, path: str, **params: Param) -> tuple[int, dict[str, Any]]:
    response = client.get(f"/api/plugin/table/{route}", params={"path": path, **params})
    return response.status_code, response.json()


def _ok(client: TestClient, route: str, path: str, **params: Param) -> dict[str, Any]:
    status, body = _get(client, route, path, **params)
    assert status == 200, body
    return body


def _cells(body: dict[str, Any]) -> list[dict[str, Any]]:
    return [row["cells"] for row in body["rows"]]


def _keys(body: dict[str, Any]) -> list[str]:
    return [row["key"] for row in body["rows"]]


def _write(tmp_path: Path, name: str, value: Any) -> str:
    (tmp_path / name).write_text(json.dumps(value))
    return name


def _types(client: TestClient, path: str) -> dict[str, str]:
    return {field["name"]: field["type"] for field in _ok(client, "schema", path)["fields"]}


# ── The table ────────────────────────────────────────────────


def test_a_list_of_mappings_is_one_keyless_table(client: TestClient, tmp_path: Path) -> None:
    path = _write(tmp_path, "a.json", [{"x": 1}, {"x": 2, "y": "b"}])
    assert _ok(client, "tables", path)["tables"] == [
        {
            "id": "",
            "label": "a.json",
            "group": "tables",
            "keyed": False,
            "estimate": None,
            "path": "a.json",
        }
    ]
    schema = _ok(client, "schema", path)
    assert (schema["key"], schema["default_columns"]) == ([], ["x", "y"])
    body = _ok(client, "rows", path)
    assert _keys(body) == ["@1", "@2"]
    # A key a mapping lacks is absent, which the wire shows apart from null.
    assert _cells(body) == [{"x": 1}, {"x": 2, "y": "b"}]
    assert (body["count"], body["count_complete"], body["complete"]) == (2, True, True)
    status, missing = _get(client, "record", "a.json/t", key="@1")
    assert (status, missing["code"]) == (404, "not_found")


def test_fields_are_named_in_the_order_keys_first_appear(
    client: TestClient, tmp_path: Path
) -> None:
    (tmp_path / "a.yaml").write_text(
        "- {b: 1, 1: one}\n- {a: 2, '1': text, '': empty, 2.5: half, null: nothing}\n"
    )
    columns = _ok(client, "rows", "a.yaml")["columns"]
    assert columns == ["b", "1", "a", "1_2", "field_5", "2.5", "null"]
    assert _cells(_ok(client, "rows", "a.yaml", cols=["1", "1_2", "field_5"])) == [
        {"1": "one"},
        {"1_2": "text", "field_5": "empty"},
    ]


def test_types_are_inferred_from_the_values(client: TestClient, tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "a.json",
        [
            {"t": "a", "i": 1, "r": 1, "b": True, "d": "2024-01-02", "dt": "2024-01-02T03:04"},
            {
                "t": "b",
                "i": 2,
                "r": 2.5,
                "b": False,
                "d": "2024-02-03",
                "dt": "2024-01-02 03:04:05Z",
            },
            {"j": [1], "m": {"k": 1}, "u": 1, "n": None},
            {"j": {"x": 1}, "u": "one"},
        ],
    )
    assert _types(client, path) == {
        "t": "text",
        "i": "integer",
        "r": "real",
        "b": "boolean",
        "d": "date",
        "dt": "datetime",
        "j": "json",
        "m": "json",
        "u": "unknown",
        "n": "text",
    }
    fields = {field["name"]: field for field in _ok(client, "schema", path)["fields"]}
    assert fields["i"]["numeric"] and fields["r"]["numeric"] and not fields["u"]["numeric"]
    assert (fields["j"]["sortable"], fields["j"]["filterable"]) == (False, True)
    assert fields["u"]["sort_note"] is not None


def test_a_yaml_date_is_a_date_and_a_value_json_cannot_carry_is_its_text(
    client: TestClient, tmp_path: Path
) -> None:
    (tmp_path / "a.yaml").write_text(
        "- {when: 2024-01-02, at: 2024-01-02T03:04:05Z, x: .nan, big: 123456789012345678901,"
        " nested: {inf: .inf, day: 2024-01-02, bin: !!binary aGk=}}\n"
    )
    assert _types(client, "a.yaml")["when"] == "date"
    (cells,) = _cells(_ok(client, "rows", "a.yaml"))
    assert cells == {
        "when": "2024-01-02",
        "at": "2024-01-02T03:04:05+00:00",
        "x": {"real": "nan"},
        "big": {"int": "123456789012345678901"},
        "nested": {"json": {"inf": "Infinity", "day": "2024-01-02", "bin": "6869"}},
    }


def test_a_later_value_that_contradicts_its_field_is_shown_as_stored(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(records, "RECORDS_TYPE_SAMPLE_ROWS", 2)
    path = _write(tmp_path, "a.json", [{"n": 1}, {"n": 2}, {"n": "three"}, {"n": [4]}])
    assert _types(client, path)["n"] == "integer"
    assert [cells["n"] for cells in _cells(_ok(client, "rows", path))] == [
        1,
        2,
        {"value": "three", "stored": "text"},
        {"value": {"json": [4]}, "stored": "json"},
    ]


def test_a_nested_value_is_its_json_whole_or_its_text_cut(
    client: TestClient, tmp_path: Path
) -> None:
    long = ["x" * 50 for _ in range(20)]
    path = _write(tmp_path, "a.json", [{"j": {"a": 1}}, {"j": long}])
    small, big = (cells["j"] for cells in _cells(_ok(client, "rows", path)))
    assert small == {"json": {"a": 1}}
    text = json.dumps(long, separators=(",", ":"))
    assert big == {"text": text[:TABLE_CELL_PREVIEW_CHARS], "length": len(text)}
    # The record carries it whole, up to its own bound.
    assert _ok(client, "record", path, key="@2")["cells"] == {"j": {"json": long}}


def test_a_nested_value_past_the_record_bound_is_cut_in_the_record(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(records, "TABLE_RECORD_VALUE_BYTES", 10)
    path = _write(tmp_path, "a.json", [{"j": ["é" * 20]}])
    cell = _ok(client, "record", path, key="@1")["cells"]["j"]
    assert cell == {"text": '["éééé', "length": 24}


def test_a_card_is_a_label_and_a_few_fields(client: TestClient, tmp_path: Path) -> None:
    path = _write(tmp_path, "a.json", [{f"f{n}": n for n in range(10)}])
    card = _ok(client, "card", path, key="@1")
    assert card["label"] == 0
    assert list(card["cells"]) == ["f1", "f2", "f3", "f4", "f5", "f6"]


# ── Queries ──────────────────────────────────────────────────


@pytest.fixture
def mixed(tmp_path: Path) -> str:
    return _write(
        tmp_path,
        "m.json",
        [
            {"name": "Ada", "age": 36, "tags": ["x"]},
            {"name": "Bob", "age": "old"},
            {"name": "Cy", "age": None},
            {"name": "Dee", "age": 2.5, "tags": ["y", "z"]},
            {"name": "Eve"},
            {"name": "Fay", "age": True},
        ],
    )


def test_a_sort_orders_by_storage_class_then_value(client: TestClient, mixed: str) -> None:
    ascending = _ok(client, "rows", mixed, sort="age")
    # Nulls and absent values first, then numbers (a boolean among them), then text;
    # ties by position.
    assert _keys(ascending) == ["@3", "@5", "@6", "@4", "@1", "@2"]
    descending = _ok(client, "rows", mixed, sort="age", order="desc")
    assert _keys(descending) == ["@2", "@1", "@4", "@6", "@5", "@3"]
    status, refused = _get(client, "rows", mixed, sort="tags")
    assert (status, refused["code"]) == (400, "bad_query")


def test_a_cursor_pages_through_a_sort(client: TestClient, mixed: str) -> None:
    whole = _keys(_ok(client, "rows", mixed, sort="age", order="desc"))
    seen: list[str] = []
    after: str | None = None
    while True:
        params: dict[str, Param] = {"sort": "age", "order": "desc", "limit": "2"}
        if after:
            params["after"] = after
        body = _ok(client, "rows", mixed, **params)
        seen += _keys(body)
        after = body["next_after"]
        if after is None:
            break
    assert seen == whole


def test_filters_compare_by_type(client: TestClient, mixed: str) -> None:
    def keys(**params: Param) -> list[str]:
        return _keys(_ok(client, "rows", mixed, **params))

    assert keys(**{"f.age": "null"}) == ["@3", "@5"]
    assert keys(**{"f.age": "notnull"}) == ["@1", "@2", "@4", "@6"]
    # An unknown field takes a number as a number and anything else as text.
    assert keys(**{"f.age": "gt:2"}) == ["@1", "@2", "@4"]
    assert keys(**{"f.age": "eq:old"}) == ["@2"]
    assert keys(**{"f.age": "contains:OL"}) == ["@2"]
    assert keys(**{"f.tags": 'contains:"z"'}) == ["@4"]
    assert keys(**{"f.tags": 'eq:["x"]'}) == ["@1"]
    assert keys(**{"f.name": "lt:Bz"}) == ["@1", "@2"]


def test_a_typed_filter_refuses_a_value_of_another_type(client: TestClient, tmp_path: Path) -> None:
    path = _write(tmp_path, "a.json", [{"n": 1}, {"n": 2}])
    status, body = _get(client, "rows", path, **{"f.n": "gt:two"})
    assert (status, body["code"]) == (400, "bad_query")
    assert _keys(_ok(client, "rows", path, **{"f.n": "ge:2"})) == ["@2"]


def test_a_search_reads_text_fields_only(client: TestClient, mixed: str) -> None:
    body = _ok(client, "rows", mixed, q="d")
    assert (body["searched"], _keys(body)) == (["name"], ["@1", "@4"])


def test_a_cursor_with_a_key_the_field_cannot_hold_is_refused(
    client: TestClient, mixed: str
) -> None:
    from metabrowser.table_source import encode_cursor

    bad = encode_cursor(["age", "asc", 2, 5, 1])
    status, body = _get(client, "rows", mixed, sort="age", after=bad or "")
    assert (status, body["code"]) == (400, "bad_query")


def test_an_exhausted_budget_returns_what_it_found(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    total = 3 * memory.BUDGET_CHECK_ROWS
    path = _write(tmp_path, "a.json", [{"n": n} for n in range(total)])
    _ok(client, "rows", path)  # parse first, outside any spent budget

    def spent(cls: type[Budget], seconds: float = 0.0) -> Budget:
        return cls(deadline=0.0)

    monkeypatch.setattr(Budget, "start", classmethod(spent))
    body = _ok(client, "rows", path, limit="2", **{"f.n": "ge:0"})
    assert (body["complete"], body["reason"], body["examined"]) == (
        False,
        "budget",
        memory.BUDGET_CHECK_ROWS,
    )
    refused = _ok(client, "rows", path, sort="n")
    assert (refused["rows"], refused["reason"], refused["sort_refused"]) == ([], "sort_budget", "n")


# ── What is not a list of records ────────────────────────────


@pytest.mark.parametrize(
    ("name", "text", "said"),
    [
        ("a.json", '{"a": 1}', "its top level is a mapping, not a list"),
        ("a.json", '"text"', "its top level is text, not a list"),
        ("a.json", "3", "its top level is a number, not a list"),
        ("a.json", "null", "its top level is null, not a list"),
        ("a.yaml", "- {a: 1}\n- [1]\n", "item 2 of its list is a list, not a mapping"),
        ("a.json", '[{"a": 1}, 2]', "item 2 of its list is a number, not a mapping"),
    ],
)
def test_any_other_document_is_not_a_list_of_records(
    client: TestClient, tmp_path: Path, name: str, text: str, said: str
) -> None:
    (tmp_path / name).write_text(text)
    for route in ("schema", "rows"):
        status, body = _get(client, route, name)
        assert (status, body["code"]) == (422, "source_unreadable")
        assert body["error"] == f"This document is not a list of records: {said}."


def test_an_empty_list_is_an_empty_table(client: TestClient, tmp_path: Path) -> None:
    path = _write(tmp_path, "a.json", [])
    assert _ok(client, "schema", path)["fields"] == []
    body = _ok(client, "rows", path)
    assert (body["rows"], body["count"], body["complete"]) == ([], 0, True)


def test_a_file_that_does_not_parse_or_is_too_large_says_so(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "bad.json").write_text('[{"a": ')
    status, body = _get(client, "schema", "bad.json")
    assert (status, body["code"]) == (422, "source_unreadable")
    assert body["error"].startswith("This file could not be parsed: ")
    monkeypatch.setattr(structured, "STRUCTURED_PARSE_MAX_BYTES", 4)
    _write(tmp_path, "big.json", [{"a": 1}])
    status, body = _get(client, "schema", "big.json")
    assert (status, body["code"]) == (422, "source_unreadable")
    assert "larger than the" in body["error"]


def test_a_yaml_stream_of_mappings_is_a_list_of_records(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text("a: 1\n---\na: 2\nb: x\n")
    assert _cells(_ok(client, "rows", "a.yaml")) == [{"a": 1}, {"a": 2, "b": "x"}]


# ── Bounds ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("bound", "value", "rows", "columns"),
    [
        ("RECORDS_MAX_ROWS", 2, 2, ["a", "b"]),
        ("RECORDS_MAX_CELLS", 3, 2, ["a", "b"]),
        ("RECORDS_MAX_FIELDS", 2, 3, ["a", "b"]),
    ],
)
def test_past_a_bound_the_rest_is_not_read_and_the_page_says_so(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bound: str,
    value: int,
    rows: int,
    columns: list[str],
) -> None:
    monkeypatch.setattr(records, bound, value)
    path = _write(tmp_path, "a.json", [{"a": 1}, {"a": 2, "b": 2}, {"c": 3}])
    body = _ok(client, "rows", path)
    assert (len(body["rows"]), body["columns"]) == (rows, columns)
    assert (body["truncated"], body["complete"], body["reason"]) == (
        True,
        False,
        "source_truncated",
    )
    assert body["count_complete"] == (bound == "RECORDS_MAX_FIELDS")


def test_a_bound_never_hides_a_refusal(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(records, "RECORDS_MAX_ROWS", 1)
    path = _write(tmp_path, "a.json", [{"a": 1}, {"a": 2}, 3])
    assert _get(client, "schema", path)[0] == 422


# ── Generations and the shared parse ─────────────────────────


def test_a_change_moves_the_generation_and_is_read(client: TestClient, tmp_path: Path) -> None:
    path = _write(tmp_path, "a.json", [{"a": 1}])
    first = _ok(client, "rows", path)
    _write(tmp_path, path, [{"a": 1}, {"a": 2}])
    os.utime(tmp_path / path, ns=(1, 1))
    second = _ok(client, "rows", path)
    assert second["generation"] != first["generation"]
    assert second["count"] == 2
    record = _ok(client, "record", path, key="@1", generation=first["generation"])
    assert record["generation_moved"] is True


def test_the_table_reads_the_trees_parse_and_never_writes_its_yaml(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, bool]] = []
    real = structured.parse_structured_bytes

    def counted(data: bytes, ext: str, *, serialize: bool = True) -> parser.StructuredPayload:
        calls.append((ext, serialize))
        return real(data, ext, serialize=serialize)

    monkeypatch.setattr(structured, "parse_structured_bytes", counted)
    path = _write(tmp_path, "a.json", [{"a": 1}])
    tree = client.get("/api/plugin/structured/parsed", params={"path": path})
    assert (tree.status_code, tree.json()["pretty_yaml"]) == (200, "  - a: 1\n")
    for route in ("schema", "rows", "record", "card"):
        _ok(client, route, path, **({"key": "@1"} if route in ("record", "card") else {}))
    assert calls == [(".json", True)]
    # A table read first parses without the canonical YAML, which the Tree view's route
    # writes when it is first shown.
    other = _write(tmp_path, "b.json", [{"a": 1}])
    _ok(client, "rows", other)
    _ok(client, "schema", other)
    tree = client.get("/api/plugin/structured/parsed", params={"path": other})
    assert (tree.status_code, tree.json()["pretty_yaml"]) == (200, "  - a: 1\n")
    assert calls == [(".json", True), (".json", False), (".json", True)]


def test_a_git_pin_reads_a_record_list(tmp_path: Path) -> None:
    store, commit = fast_import_store(
        tmp_path,
        files={
            b"people.json": b'[{"name": "ada", "n": 3}, {"name": "bob", "n": 1}]',
            b"conf.yaml": b"a: 1\n",
        },
    )

    def wire(name: str) -> str:
        return GitPath.from_segments(name.encode()).to_wire()

    async def run() -> dict[str, Any]:
        _clear()
        answers: dict[str, Any] = {}
        async with pinned_client(store, commit) as (pinned, _subject):
            for name, route, params in (
                ("rows", "rows", {"path": wire("people.json"), "sort": "n"}),
                ("record", "record", {"path": wire("people.json"), "key": "@1"}),
                ("mapping", "schema", {"path": wire("conf.yaml")}),
            ):
                response = await pinned.get(f"/api/plugin/table/{route}", params=params)
                answers[name] = (response.status_code, response.json())
        _clear()
        return answers

    answers = asyncio.run(run())
    status, rows = answers["rows"]
    assert status == 200
    assert _cells(rows) == [{"name": "bob", "n": 1}, {"name": "ada", "n": 3}]
    assert answers["record"][1]["cells"] == {"name": "ada", "n": 3}
    assert answers["mapping"][0] == 422
