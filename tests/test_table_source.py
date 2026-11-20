"""The table source protocol in core: cells, tokens, the query grammar, and the wire.

``metabrowser.table_source`` is SDK surface that every source and the table routes share,
so these pin its rules apart from any source: the delimited source's behavior is in
``tests/test_delimited_source.py`` and the routes' transcripts in
``tests/golden/cli-api-table.tryscript.md``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from metabrowser import plugin_api, table_source
from metabrowser.plugin_loader.manifest import PLUGIN_SDK_VERSION, PluginManifest
from metabrowser.table_source import (
    MAX_SAFE_INTEGER,
    TABLE_PAGE_ROWS_DEFAULT,
    TABLE_PAGE_ROWS_MAX,
    TABLE_TOKEN_MAX_CHARS,
    FieldRef,
    Filter,
    RecordNotFoundError,
    RefFilter,
    TableField,
    TableQuery,
    TableQueryError,
    TableSchema,
    check_table_query,
    coerce_filter_value,
    cut_utf8,
    decode_cursor,
    decode_key,
    encode_cursor,
    encode_key,
    integer_cell,
    parse_position_key,
    parse_positional_cursor,
    parse_table_query,
    position_key,
    positional_cursor,
    real_cell,
    stat_generation,
    stored_cell,
    text_cell,
)

# ── Cells ────────────────────────────────────────────────────


def test_integers_past_a_browser_number_keep_their_digits() -> None:
    assert integer_cell(MAX_SAFE_INTEGER) == MAX_SAFE_INTEGER
    assert integer_cell(-MAX_SAFE_INTEGER) == -MAX_SAFE_INTEGER
    assert integer_cell(MAX_SAFE_INTEGER + 1) == {"int": "9007199254740992"}
    assert integer_cell(-(10**30)) == {"int": "-" + "1" + "0" * 30}


def test_reals_json_cannot_carry_are_named() -> None:
    assert real_cell(1.5) == 1.5
    assert real_cell(float("inf")) == {"real": "inf"}
    assert real_cell(float("-inf")) == {"real": "-inf"}
    assert real_cell(float("nan")) == {"real": "nan"}


def test_text_is_plain_until_cut_or_invalid() -> None:
    assert text_cell("short", max_chars=10) == "short"
    assert text_cell("abcdef", max_chars=3) == {"text": "abc", "length": 6}
    assert text_cell("ab�", invalid_utf8=True) == {"text": "ab�", "invalid_utf8": True}
    assert text_cell("", max_chars=0) == ""


def test_a_byte_cut_never_splits_a_character() -> None:
    assert cut_utf8("aé", 2) == "a"
    assert cut_utf8("aé", 3) == "aé"
    assert cut_utf8("€€", 4) == "€"
    assert text_cell("€€", max_bytes=4) == {"text": "€", "length": 2}


def test_a_stored_type_is_shown_rather_than_coerced() -> None:
    assert stored_cell("abc", "text") == {"value": "abc", "stored": "text"}


# ── Tokens ───────────────────────────────────────────────────


def test_keys_and_cursors_are_deterministic_round_trips() -> None:
    key = encode_key([7, "é"])
    assert key == encode_key([7, "é"])
    assert key is not None and key.startswith("k.")
    assert decode_key(key) == [7, "é"]
    cursor = encode_cursor([1, 2.5, 3])
    assert cursor is not None and cursor.startswith("c.")
    assert decode_cursor(cursor) == [1, 2.5, 3]


def test_a_token_past_the_bound_is_not_minted() -> None:
    assert encode_key(["x" * TABLE_TOKEN_MAX_CHARS]) is None
    assert encode_cursor(["x" * TABLE_TOKEN_MAX_CHARS]) is None


@pytest.mark.parametrize("token", ["k.", "c.!!", "x.e30", "c.e30", "c." + "A" * 2000])
def test_a_forged_cursor_is_a_bad_query(token: str) -> None:
    with pytest.raises(TableQueryError):
        decode_cursor(token)


def test_positions_and_positional_cursors() -> None:
    assert position_key(3) == "@3"
    assert parse_position_key("@3") == 3
    assert parse_position_key("k.abc") is None
    for bad in ("@0", "@03", "@x", "@", "@٣"):
        with pytest.raises(RecordNotFoundError):
            parse_position_key(bad)
    assert positional_cursor(200, "ab12") == "@200.ab12"
    assert parse_positional_cursor("@200.ab12") == (200, "ab12")
    assert parse_positional_cursor("c.abc") is None
    for bad in ("@200", "@x.ab", "@1.a.b"):
        with pytest.raises(TableQueryError):
            parse_positional_cursor(bad)


def test_stat_generation_follows_identity_size_and_time(tmp_path: Path) -> None:
    target = tmp_path / "a.csv"
    target.write_text("a\n1\n")
    first = stat_generation(target)
    assert first == stat_generation(target)
    target.write_text("a\n12\n")
    assert stat_generation(target) != first


# ── The query grammar ────────────────────────────────────────


def test_an_empty_query_is_the_first_default_page() -> None:
    assert parse_table_query([("path", "a.csv")]) == TableQuery()
    assert TableQuery().limit == TABLE_PAGE_ROWS_DEFAULT


def test_every_parameter_parses() -> None:
    query = parse_table_query(
        [
            ("sort", "n"),
            ("order", "desc"),
            ("q", "ada"),
            ("f.n", "gt:5"),
            ("f.n", "le:9"),
            ("f.x", "null"),
            ("f.y", "eq:"),
            ("ref", "users:k.WzFd"),
            ("cols", "a,b"),
            ("after", "c.WzJd"),
            ("limit", "5000"),
        ]
    )
    assert query == TableQuery(
        sort="n",
        order="desc",
        q="ada",
        filters=(
            Filter("n", "gt", "5"),
            Filter("n", "le", "9"),
            Filter("x", "null", None),
            Filter("y", "eq", ""),
        ),
        ref=RefFilter(table="users", key="k.WzFd"),
        cols=("a", "b"),
        after="c.WzJd",
        limit=TABLE_PAGE_ROWS_MAX,
    )


@pytest.mark.parametrize(
    ("items", "param"),
    [
        ([("bogus", "1")], "bogus"),
        ([("sort", "a"), ("sort", "b")], "sort"),
        ([("order", "up")], "order"),
        ([("limit", "0")], "limit"),
        ([("limit", "-3")], "limit"),
        ([("limit", "x")], "limit"),
        ([("f.n", "between:1")], "f.n"),
        ([("f.n", "gt")], "f.n"),
        ([("f.n", "null:x")], "f.n"),
        ([("f.", "eq:1")], "f."),
        ([("ref", "users")], "ref"),
        ([("cols", ",")], "cols"),
    ],
)
def test_a_malformed_parameter_is_refused_by_name(items: list[tuple[str, str]], param: str) -> None:
    with pytest.raises(TableQueryError) as caught:
        parse_table_query(items)
    assert caught.value.details["param"] == param


def _schema() -> TableSchema:
    return TableSchema(
        table="",
        fields=(
            TableField(name="n", type="integer", sortable=True, filterable=True),
            TableField(name="blob", type="blob", sort_note="blobs do not sort"),
            TableField(
                name="owner",
                type="integer",
                filterable=True,
                ref=FieldRef(table="users", fields=("owner",), to=("id",)),
            ),
        ),
        key=(),
        default_columns=("n", "owner"),
        references=(FieldRef(table="users", fields=("owner",), to=("id",)),),
    )


@pytest.mark.parametrize(
    ("query", "message"),
    [
        (TableQuery(sort="nope"), "no field named 'nope'"),
        (TableQuery(sort="blob"), "'blob' is not sortable: blobs do not sort"),
        (TableQuery(filters=(Filter("blob", "eq", "x"),)), "'blob' is not filterable"),
        (TableQuery(cols=("n", "gone")), "no field named 'gone'"),
        (TableQuery(ref=RefFilter("teams", "@1")), "no field of this table references 'teams'"),
    ],
)
def test_the_schema_refuses_what_it_cannot_serve(query: TableQuery, message: str) -> None:
    with pytest.raises(TableQueryError, match=message):
        check_table_query(query, _schema())


def test_the_schema_admits_what_it_states() -> None:
    check_table_query(
        TableQuery(sort="n", filters=(Filter("owner", "eq", "1"),), ref=RefFilter("users", "@1")),
        _schema(),
    )


def test_filter_values_are_typed_by_their_field() -> None:
    integer = TableField(name="n", type="integer")
    assert coerce_filter_value(integer, "-4") == -4
    assert coerce_filter_value(TableField(name="r", type="real"), "2.5") == 2.5
    assert coerce_filter_value(TableField(name="b", type="boolean"), "TRUE") is True
    assert coerce_filter_value(TableField(name="t", type="text"), "9") == "9"
    with pytest.raises(TableQueryError, match="not an integer"):
        coerce_filter_value(integer, "nine")


# ── SDK surface ──────────────────────────────────────────────


def test_the_plugin_api_exports_what_a_source_implements_and_no_host_wiring() -> None:
    exported = set(plugin_api.__all__)
    assert {"TableSource", "TableHandle", "text_cell", "encode_cursor"} <= exported
    assert all(hasattr(table_source, name) for name in exported if name.startswith("Table"))
    # The registry and the routes' own wiring are the host's, not a plugin's.
    for host_only in ("install_table_sources", "open_table_source", "page_wire"):
        assert host_only not in exported


def _manifest(**fields: object) -> PluginManifest:
    data: dict[str, object] = {
        "plugin": {"name": "csvish", "sdk_version": PLUGIN_SDK_VERSION, "requires": ["table"]},
        "kind": [{"id": "csvish", "match": {"ext": ".csvish"}}],
        "table_source": [{"kind": "csvish", "adapter": "csvish.source:adapter"}],
    }
    data.update(fields)
    return PluginManifest.model_validate(data)


def test_a_table_source_declaration_validates() -> None:
    assert _manifest().validate_consistency() == []


@pytest.mark.parametrize(
    ("fields", "problem"),
    [
        (
            {"plugin": {"name": "csvish", "sdk_version": PLUGIN_SDK_VERSION}},
            "plugin 'csvish' declares a [[table_source]] but does not require 'table'",
        ),
        (
            {"table_source": [{"kind": "other", "adapter": "m:a"}]},
            "table_source kind 'other' is not a [[kind]] this plugin declares",
        ),
        (
            {"table_source": [{"kind": "csvish", "adapter": "m:a"}] * 2},
            "table_source kind 'csvish' is declared more than once",
        ),
        (
            {"table_source": [{"kind": "csvish", "adapter": "no_colon"}]},
            "table_source 'csvish' has malformed adapter 'no_colon'",
        ),
    ],
)
def test_a_table_source_declaration_is_checked(fields: dict[str, object], problem: str) -> None:
    problems = _manifest(**fields).validate_consistency()
    assert any(found.startswith(problem) for found in problems), problems
