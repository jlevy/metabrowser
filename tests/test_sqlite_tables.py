"""The SQLite table source through the table routes, over databases built from the SQL
under ``tests/fixtures/sqlite-tables/``.

Each page walk is checked against the same query run directly with one ``ORDER BY``, so
the keyset paging by region (the sort field's nulls by key, its values by row value) is
held to SQLite's own order in both directions, across types and collations.
"""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import server, table_source
from metabrowser.builtin_plugins.sqlite import reader, source
from metabrowser.builtin_plugins.sqlite.database import segment_name, table_segment
from metabrowser.source import reset_source_session
from metabrowser.table_source import decode_key
from tests.git_pin_harness import fast_import_store, pinned_client
from tests.required_tools import needs_git
from tests.sqlite_fixture import build

FIXTURES = Path(__file__).parent / "fixtures" / "sqlite-tables"


def _stage(root: Path) -> None:
    for name in ("app", "utf16", "snapshot"):
        build(root / f"{name}.db", (FIXTURES / f"{name}.sql").read_text(encoding="utf-8"))
    build(root / "History", "CREATE TABLE visits (id INTEGER PRIMARY KEY, url TEXT);")
    build(root / "x.storedata", "CREATE TABLE t (id INTEGER PRIMARY KEY);")
    (root / "fake.db").write_bytes(b"not a database at all\x00\x01\x02")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    folder = tmp_path / "root"
    folder.mkdir()
    _stage(folder)
    return folder


@pytest.fixture
def client(root: Path) -> Iterator[TestClient]:
    reset_source_session()
    server._set_root_dir(root)  # pyright: ignore[reportPrivateUsage]
    with TestClient(server.app) as test_client:
        yield test_client


def _get(client: TestClient, route: str, **params: Any) -> dict[str, Any]:
    response = client.get(f"/api/plugin/table/{route}", params=params)
    body: dict[str, Any] = response.json()
    body["_status"] = response.status_code
    return body


def _walk(client: TestClient, path: str, **params: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    after: str | None = None
    for _ in range(100):
        query = dict(params)
        if after is not None:
            query["after"] = after
        page = _get(client, "rows", path=path, **query)
        assert page["_status"] == 200, page
        rows.extend(page["rows"])
        after = page["next_after"]
        if after is None:
            return rows
    raise AssertionError("pages did not end")


def _direct(root: Path, sql: str) -> list[Any]:
    connection = sqlite3.connect(root / "app.db")
    try:
        return [row[0] for row in connection.execute(sql)]
    finally:
        connection.close()


# ── Addresses ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("name", "segment"),
    [
        ("users", "users"),
        ("order items", "~6f72646572206974656d73"),
        ("g1-like", "~67312d6c696b65"),
        ("~tilde", "~7e74696c6465"),
        (".", "~2e"),
        ("..", "~2e2e"),
        ("", "~"),
        ("a/b", "~612f62"),
        ("é", "~c3a9"),
    ],
)
def test_every_name_has_exactly_one_segment(name: str, segment: str) -> None:
    assert table_segment(name) == segment
    assert segment_name(segment) == name


def test_a_segment_no_name_encodes_to_names_nothing() -> None:
    assert segment_name("~zz") is None
    assert segment_name("~7573657273") is None  # "users", which is its own segment
    assert segment_name("order items") is None


def test_tables_children_and_kind(client: TestClient) -> None:
    listed = _get(client, "tables", path="app.db")
    groups = {item["label"]: item["group"] for item in listed["tables"]}
    assert groups["users"] == "tables"
    assert groups["shouting"] == "views"
    assert groups["notes"] == "virtual"
    assert groups["notes_data"] == "internal"
    assert groups["sqlite_sequence"] == "internal"
    keyed = {item["label"]: item["keyed"] for item in listed["tables"]}
    assert keyed["users"] and keyed["tags"] and keyed["orders"]
    assert not keyed["shadows"] and not keyed["shouting"]
    paths = {item["label"]: item["path"] for item in listed["tables"]}
    assert paths["order items"] == "app.db/~6f72646572206974656d73"
    children = client.get("/api/plugin/sqlite/children", params={"path": "app.db"}).json()
    rows = {child["name"]: child for child in children["children"]}
    assert rows["users"] == {"name": "users", "path": "app.db/users"}
    assert rows["shouting"]["badge"] == "V"
    assert rows["notes_idx"]["muted"] is True
    assert client.get("/api/plugin/sqlite/children", params={"path": "fake.db"}).json() == {
        "children": []
    }
    child = client.get("/api/file", params={"path": "app.db/users"}).json()
    assert child["kind"] == "sqlite"
    assert child["container"] == "app.db"
    assert child["container_inner"] == "users"
    assert [view["id"] for view in child["views"]] == ["table", "schema", "info"]


def test_a_database_with_any_name_has_tables(client: TestClient) -> None:
    for path in ("History", "x.storedata"):
        listed = _get(client, "tables", path=path)
        assert listed["_status"] == 200
        table = listed["tables"][0]["id"]
        page = _get(client, "rows", path=f"{path}/{table}")
        assert page["_status"] == 200
        assert page["path"] == f"{path}/{table}"


def test_fsqlite_reserved_tables_are_internal(client: TestClient) -> None:
    listed = _get(client, "tables", path="snapshot.db")
    groups = {item["label"]: item["group"] for item in listed["tables"]}
    assert groups == {"applied_tx": "internal", "fsqlite_meta": "internal", "items": "tables"}


def test_refusals(client: TestClient) -> None:
    assert _get(client, "schema", path="app.db")["code"] == "table_not_found"
    assert _get(client, "schema", path="app.db/nothing")["code"] == "table_not_found"
    assert _get(client, "schema", path="app.db/~7573657273")["code"] == "table_not_found"
    assert _get(client, "rows", path="app.db/users/more")["_status"] == 404
    assert _get(client, "rows", path="fake.db/users")["_status"] == 404


# ── Schema ─────────────────────────────────────────────────────


def _fields(client: TestClient, path: str) -> dict[str, dict[str, Any]]:
    schema = _get(client, "schema", path=path)
    assert schema["_status"] == 200, schema
    return {item["name"]: item for item in schema["fields"]}


def test_keys_types_and_references(client: TestClient) -> None:
    schema = _get(client, "schema", path="app.db/users")
    assert schema["table"] == "users"
    assert schema["key"] == ["id"]
    fields = {item["name"]: item for item in schema["fields"]}
    assert {name: item["type"] for name, item in fields.items()} == {
        "id": "integer",
        "name": "text",
        "email": "text",
        "age": "integer",
        "active": "boolean",
        "joined": "date",
        "prefs": "json",
        "avatar": "blob",
        "bio": "text",
    }
    assert fields["avatar"]["filterable"] is False
    assert schema["referenced_by"] == [{"table": "orders", "fields": ["user_id"], "to": ["id"]}]
    orders = _get(client, "schema", path="app.db/orders")
    assert orders["key"] == ["rowid"]
    rowid = orders["fields"][0]
    assert (rowid["name"], rowid["key"], rowid["hidden"]) == ("rowid", True, True)
    assert "rowid" not in orders["default_columns"]
    assert orders["references"] == [{"table": "users", "fields": ["user_id"], "to": ["id"]}]
    grants = _get(client, "schema", path="app.db/grants")
    ref = {"table": "tags", "fields": ["owner", "tag"], "to": ["owner", "tag"]}
    assert grants["references"] == [ref]
    assert {item["name"]: item["ref"] for item in grants["fields"]}["tag"] == ref
    assert _get(client, "schema", path="app.db/tags")["key"] == ["owner", "tag"]
    assert _get(client, "schema", path="app.db/shadows")["key"] == []
    assert _get(client, "schema", path="app.db/shouting")["key"] == []
    prices = _fields(client, "app.db/prices")
    assert prices["dollars"]["generated"] is True
    assert prices["label"]["generated"] is True


def test_unindexed_fields_do_not_sort_past_the_bound(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(reader, "SORT_UNINDEXED_MAX_ROWS", 3)
    fields = _fields(client, "app.db/users")
    assert fields["id"]["sortable"] and fields["email"]["sortable"]
    assert not fields["name"]["sortable"]
    assert "more than 3 rows" in fields["name"]["sort_note"]
    refused = _get(client, "rows", path="app.db/users", sort="name")
    assert refused["code"] == "bad_query"


# ── Paging ─────────────────────────────────────────────────────


@pytest.mark.parametrize("order", ["asc", "desc"])
@pytest.mark.parametrize("sort", [None, "email", "age", "name", "joined", "bio"])
@pytest.mark.parametrize("limit", [1, 2, 4])
def test_pages_follow_one_order_by(
    client: TestClient, root: Path, sort: str | None, order: str, limit: int
) -> None:
    params: dict[str, Any] = {"order": order, "limit": limit}
    if sort is not None:
        params["sort"] = sort
    keys = [decode_key(row["key"])[0] for row in _walk(client, "app.db/users", **params)]
    direction = " DESC" if order == "desc" else ""
    by = f"{sort}{direction}, id{direction}" if sort else f"id{direction}"
    assert keys == _direct(root, f"SELECT id FROM users ORDER BY {by}")


@pytest.mark.parametrize("order", ["asc", "desc"])
def test_a_collated_composite_key_pages_in_order(client: TestClient, order: str) -> None:
    rows = _walk(client, "app.db/tags", order=order, limit=1, sort="tag")
    keys = [decode_key(row["key"]) for row in rows]
    expected = [[1, "admin"], [1, "beta"], [3, "beta"]]
    if order == "desc":
        expected = [[3, "beta"], [1, "beta"], [1, "admin"]]
    assert keys == expected


@pytest.mark.parametrize("order", ["asc", "desc"])
def test_a_view_pages_by_position(client: TestClient, order: str) -> None:
    rows = _walk(client, "app.db/shouting", order=order, limit=2)
    keys = [row["key"] for row in rows]
    expected = [f"@{n}" for n in range(1, 7)]
    assert keys == (expected if order == "asc" else expected[::-1])
    names = [row["cells"]["name"] for row in rows]
    assert names[0] == ("ADA" if order == "asc" else "FAY")
    sorted_rows = _walk(client, "app.db/shouting", sort="letters", limit=4)
    assert [row["cells"]["letters"] for row in sorted_rows] == [2, 3, 3, 3, 3, 3]
    record = _get(client, "record", path="app.db/shouting", key="@6")
    assert record["cells"]["name"] == "FAY"
    assert record["positional"] is True


def test_a_table_whose_rowid_is_shadowed_pages_by_position(client: TestClient) -> None:
    rows = _walk(client, "app.db/shadows", limit=1)
    assert [row["key"] for row in rows] == ["@1", "@2"]
    assert rows[1]["cells"] == {"rowid": "d", "_rowid_": "e", "oid": "f"}


def test_blob_keys_round_trip(client: TestClient) -> None:
    rows = _walk(client, "app.db/blobs", limit=1, order="desc")
    assert [row["cells"]["k"]["hex"] for row in rows] == ["04", "0203", "01"]
    record = _get(client, "record", path="app.db/blobs", key=rows[1]["key"])
    assert record["cells"]["v"] == "two"


def test_a_cursor_for_another_sort_is_refused(client: TestClient) -> None:
    page = _get(client, "rows", path="app.db/users", sort="email", limit=2)
    refused = _get(client, "rows", path="app.db/users", sort="age", after=page["next_after"])
    assert refused["code"] == "bad_query"
    assert "made for" in refused["error"]


# ── Values ─────────────────────────────────────────────────────


def test_values_are_encoded_totally(client: TestClient) -> None:
    page = _get(client, "rows", path="app.db/users")
    cells = {decode_key(row["key"])[0]: row["cells"] for row in page["rows"]}
    assert cells[1]["prefs"] == {"json": {"theme": "dark"}, "preview": '{"theme":"dark"}'}
    assert cells[1]["avatar"] == {"blob": True, "length": 3, "hex": "00ff10"}
    assert cells[1]["active"] is True
    assert cells[2]["age"] == {"value": "unknown", "stored": "text"}
    assert cells[2]["prefs"] == "not json"
    assert cells[2]["email"] is None
    assert cells[2]["bio"] == ""
    assert cells[3]["age"] == {"int": "9007199254740993"}
    # Past the inline bound, previewed from its stored bytes, with its size in bytes.
    assert cells[3]["bio"] == {"text": "0" * 400, "bytes": 5200}
    assert cells[4]["age"] == {"int": "-9223372036854775808"}
    assert cells[4]["active"] == {"value": 2, "stored": "integer"} or cells[4]["active"] == 2
    assert cells[4]["avatar"]["length"] == 300 and len(cells[4]["avatar"]["hex"]) == 400
    assert cells[5]["bio"] == {"text": "�A", "invalid_utf8": True}
    assert cells[5]["joined"] == 20230101
    orders = _get(client, "rows", path="app.db/orders")["rows"]
    totals = [row["cells"]["total"] for row in orders]
    assert totals == [9.5, {"real": "inf"}, {"real": "-inf"}, 0.5, None]


def test_long_values_are_previewed_past_the_inline_bound(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    huge = _get(client, "rows", path="app.db/huge")["rows"]
    assert huge[0]["cells"]["body"] == "small"
    body = huge[1]["cells"]["body"]
    assert body["bytes"] == 1_200_000 and body["text"] == "0" * 400
    record = _get(client, "record", path="app.db/huge", key=huge[1]["key"])
    assert record["cells"]["body"]["bytes"] == 1_200_000
    assert len(record["cells"]["body"]["text"]) == 64 * 1024
    refused = _get(client, "rows", path="app.db/huge", sort="body")
    assert refused["code"] == "bad_query" and "longer than" in refused["error"]
    # In a WITHOUT ROWID table a value past the inline bound has its size alone.
    blobs = _get(client, "rows", path="app.db/blobs")["rows"]
    assert blobs[2]["cells"]["v"] == {"length": 6000, "preview": False}
    # A UTF-16 database's preview is decoded from its stored bytes.
    words = _get(client, "rows", path="utf16.db/words")["rows"]
    assert words[0]["cells"]["word"] == "héllo wörld"
    assert words[1]["cells"]["word"]["text"] == "é" + "0" * 399
    assert words[1]["cells"]["word"]["bytes"] == 2 * 5201
    # A search skips what it cannot examine, and says so.
    found = _get(client, "rows", path="app.db/huge", q="small")
    assert [row["cells"]["body"] for row in found["rows"]] == ["small"]
    assert found["skipped"] == 1


# ── Filters, search, references, counts ────────────────────────


def test_filters_search_and_ref(client: TestClient) -> None:
    def ids(**params: Any) -> list[int]:
        page = _get(client, "rows", path="app.db/users", **params)
        assert page["_status"] == 200, page
        return [decode_key(row["key"])[0] for row in page["rows"]]

    assert ids(**{"f.age": "gt:35"}) == [1, 3, 5]
    assert ids(**{"f.email": "null"}) == [2, 4]
    assert ids(**{"f.active": "eq:true"}) == [1, 3, 5]
    assert ids(**{"f.name": "contains:e"}) == [4, 5]
    assert ids(q="EXAMPLE") == [1, 3, 5]
    page = _get(client, "rows", path="app.db/users", q="ada")
    assert "email" in page["searched"] and "age" not in page["searched"]
    user = _get(client, "rows", path="app.db/users", limit=1)["rows"][0]["key"]
    orders = _get(client, "rows", path="app.db/orders", ref=f"users:{user}")
    assert [row["cells"]["note"] for row in orders["rows"]] == ["first", None]
    assert orders["count"] == 2 and orders["count_complete"] is True


def test_references_resolve_by_the_target_columns_collation(client: TestClient) -> None:
    rows = _get(client, "rows", path="app.db/grants")["rows"]
    tags = [row["cells"]["tag"] for row in rows]
    assert tags[0]["ref"]["table"] == "tags" and tags[0]["ref"]["label"] == "ADMIN"
    assert decode_key(tags[0]["ref"]["key"]) == [1, "admin"]
    assert tags[2]["ref"] == {"table": "tags", "key": None, "label": "gamma", "missing": True}
    orders = _get(client, "rows", path="app.db/orders")["rows"]
    dangling = orders[3]["cells"]["user_id"]
    assert dangling == {"ref": {"table": "users", "key": None, "label": 99, "missing": True}}
    assert orders[4]["cells"]["user_id"] is None


def test_counts_are_capped(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(source, "COUNT_CAP", 4)
    page = _get(client, "rows", path="app.db/users", limit=2)
    assert (page["count"], page["count_complete"]) == (4, False)
    assert page["estimate"] == 6
    filtered = _get(client, "rows", path="app.db/users", **{"f.age": "gt:0"})
    assert filtered["count_complete"] is False


def test_record_and_card(client: TestClient) -> None:
    user = _get(client, "rows", path="app.db/users", limit=1)["rows"][0]["key"]
    record = _get(client, "record", path="app.db/users", key=user)
    assert record["cells"]["name"] == "Ada"
    assert record["referenced_by"] == [
        {"table": "orders", "fields": ["user_id"], "to": ["id"], "count": 2, "count_complete": True}
    ]
    card = _get(client, "card", path="app.db/users", key=user)
    assert card["label"] == "Ada"
    assert "name" not in card["cells"] and len(card["cells"]) <= 6
    missing = _get(client, "record", path="app.db/users", key="k.Wzk5OV0")
    assert missing["code"] == "record_not_found"
    order = _get(client, "rows", path="app.db/orders", limit=1)["rows"][0]
    assert decode_key(order["key"]) == [1]
    assert _get(client, "record", path="app.db/orders", key=order["key"])["cells"]["rowid"] == 1


def test_schema_route(client: TestClient) -> None:
    whole = client.get("/api/plugin/sqlite/schema", params={"path": "app.db"}).json()
    names = {(entry["type"], entry["name"]) for entry in whole["objects"]}
    assert ("index", "users_email") in names and ("view", "shouting") in names
    one = client.get("/api/plugin/sqlite/schema", params={"path": "app.db/grants"}).json()
    assert one["table"] == "grants"
    assert [entry["name"] for entry in one["objects"]] == ["grants"]
    assert one["foreign_keys"] == [
        {
            "table": "grants",
            "fields": ["owner", "tag"],
            "references": "tags",
            "to": ["owner", "tag"],
        }
    ]
    info = client.get("/api/plugin/sqlite/info", params={"path": "app.db/users"}).json()
    assert info["access"]["state"] == "current"


def test_virtual_tables_are_read_only_where_trusted(client: TestClient) -> None:
    page = _get(client, "rows", path="app.db/notes")
    assert page["_status"] == 200
    assert page["rows"][0]["cells"]["body"] == "remember the milk"


# ── A Git pin ──────────────────────────────────────────────────


@needs_git
def test_a_pinned_database_lists_and_reads_its_tables(tmp_path: Path) -> None:
    built = build(tmp_path / "app.db", (FIXTURES / "snapshot.sql").read_text(encoding="utf-8"))
    store, commit = fast_import_store(
        tmp_path, {b"app.db": built.read_bytes(), b"History": built.read_bytes()}
    )

    async def run() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        async with pinned_client(store, commit) as (pinned, _subject):
            # A table's address is a container child on a pin too, whatever the name.
            for wire in ("g1-YXBwLmRi/items", "g1-SGlzdG9yeQ/items"):
                child = (await pinned.get("/api/file", params={"path": wire})).json()
                assert (child["kind"], child["container_inner"]) == ("sqlite", "items")
            listed = (
                await pinned.get("/api/plugin/table/tables", params={"path": "g1-YXBwLmRi"})
            ).json()
            address = listed["tables"][2]["path"]
            rows = (await pinned.get("/api/plugin/table/rows", params={"path": address})).json()
            children = (
                await pinned.get("/api/plugin/sqlite/children", params={"path": "g1-YXBwLmRi"})
            ).json()
            return listed, rows, children

    listed, rows, children = asyncio.run(run())
    assert listed["tables"][2]["path"] == "g1-YXBwLmRi/items"
    assert rows["rows"][0]["cells"] == {"id": 1, "name": "kept"}
    assert children["children"][2]["path"] == "g1-YXBwLmRi/items"


@pytest.mark.parametrize("order", ["asc", "desc"])
def test_tokens_past_the_bound_are_positions(
    client: TestClient, root: Path, monkeypatch: pytest.MonkeyPatch, order: str
) -> None:
    """With no key or cursor short enough for a token, rows are named by their position in
    key order and pages continue from the rows served, under one generation."""
    monkeypatch.setattr(table_source, "TABLE_TOKEN_MAX_CHARS", 4)
    rows = _walk(client, "app.db/users", sort="email", order=order, limit=2, cols="email")
    direction = " DESC" if order == "desc" else ""
    expected = _direct(root, f"SELECT id FROM users ORDER BY email{direction}, id{direction}")
    assert [row["key"] for row in rows] == [f"@{key}" for key in expected]
    record = _get(client, "record", path="app.db/users", key="@3")
    assert record["cells"]["name"] == "Cy" and record["positional"] is True
    view = _walk(client, "app.db/shouting", order=order, limit=4)
    positions = [f"@{n}" for n in range(1, 7)]
    assert [row["key"] for row in view] == (positions if order == "asc" else positions[::-1])
    page = _get(client, "rows", path="app.db/users", limit=2)
    stale = _get(client, "rows", path="app.db/users", limit=2, after="@2.stale")
    assert page["next_after"].startswith("@2.")
    assert (stale["reason"], stale["rows"]) == ("cursor_expired", [])
