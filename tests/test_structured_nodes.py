"""Ordered structured pages agree across JSON and YAML and retain each source's bytes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from metabrowser.structured_nodes import Format, project_structured, projection_byte_limit


@pytest.mark.parametrize(
    ("fmt", "data", "selected"),
    [
        ("json", b'{"9":null,"0":[{"":{}},{"x":""},{"x":[]}],"u":"\\u00e9"}', b'"\\u00e9"'),
        ("yaml", b'{"9": null, "0": [{"": {}}, {x: ""}, {x: []}], u: "\\u00e9"}', b'"\\u00e9"'),
        (
            "yaml",
            '"9": null\r\n"0":\r\n- "": {}\r\n- x: ""\r\n- x: []\r\nu: é\r\n'.encode(),
            "é".encode(),
        ),
    ],
)
def test_equivalent_documents(fmt: Format, data: bytes, selected: bytes) -> None:
    def visit(*parts: str | int, offset: int = 0, limit: int = 50) -> dict[str, Any]:
        return project_structured(data, fmt, path=parts, offset=offset, limit=limit)

    first = visit(limit=2)
    assert [child["segment"] for child in first["children"]] == ["9", "0"]
    last = visit(offset=first["next_offset"], limit=2)
    assert [child["segment"] for child in last["children"]] == ["u"]
    assert last["next_offset"] is None
    value = last["children"][0]["node"]
    assert value["value"] == "é"
    span = value["source_range"]
    assert data[span["start_byte"] : span["end_byte"]] == selected
    assert visit("9")["node"]["value"] is None
    assert visit("0", 0, "")["node"]["kind"] == "object"
    assert visit("0", 1, "x")["node"]["value"] == ""
    assert visit("0", 2, "x")["node"]["kind"] == "array"
    for path in [(0,), ("0", "0"), ("0", 0, "x")]:
        assert visit(*path)["status"] == "missing"


@pytest.mark.parametrize("fmt", ["json", "yaml"])
def test_number_precision_and_range(fmt: Format) -> None:
    token = b"1.2345678901234567890123456789e1000"
    data = b'["' + "🌊".encode() + b'",\r\n ' + token + b"]"
    node = project_structured(data, fmt, path=[1])["node"]
    assert node["kind"] == "number"
    assert node["value"].encode() == token
    span = node["source_range"]
    assert data[span["start_byte"] : span["end_byte"]] == token


def test_yaml_stream_empty_documents_and_multiline_value_range() -> None:
    data = b"---\r\n---\r\nvalue: |-\r\n  a\r\n  b\r\n---\r\n"
    for document in (0, 2):
        result = project_structured(data, "yaml", document=document)
        assert result["document_count"] == 3
        assert result["node"]["value"] is None
    node = project_structured(data, "yaml", document=1, path=["value"])["node"]
    assert node["value"] == "a\nb"
    span = node["source_range"]
    assert data[span["start_byte"] : span["end_byte"]] == b"|-\r\n  a\r\n  b\r\n"
    assert project_structured(data, "yaml", document=3)["status"] == "missing"


@pytest.mark.parametrize(
    ("fmt", "data"),
    [
        ("json", b'{"":1,"":2}'),
        ("yaml", b"a: 1\na: 2"),
        ("yaml", b"1: null"),
        ("yaml", b"unknown: !unresolved value"),
        ("yaml", b"root: &a [*a]"),
        ("yaml", b"x: [unterminated"),
        ("json", b"[true,,]"),
        ("json", b"NaN"),
        ("json", b'"\\ud800"'),
        ("yaml", b"bad: \xff"),
    ],
)
def test_diagnostics_are_scoped(fmt: Format, data: bytes) -> None:
    response = project_structured(data, fmt)
    assert response["status"] == "invalid"
    assert 0 <= response["error_byte"] <= len(data)


@pytest.mark.parametrize("fmt", ["json", "yaml"])
def test_enforces_byte_and_depth_bounds(fmt: Format) -> None:
    assert project_structured(b" " * (projection_byte_limit(fmt) + 1), fmt)["status"] == "too_large"
    assert project_structured(b"[" * 100 + b"]" * 100, fmt)["status"] == "too_large"


@pytest.mark.parametrize("fmt", ["json", "yaml"])
def test_record_grid_requires_a_complete_list_of_records(fmt: Format) -> None:
    assert project_structured(b"[{}, {}]", fmt)["record_table"]
    mixed = b"[{}, {}, false]"
    assert not project_structured(mixed, fmt, limit=1)["record_table"]
    assert project_structured(mixed, fmt, path=[2])["node"]["value"] is False
    assert not project_structured(b"[]", fmt)["record_table"]


def test_yaml_alias_diagnostic_addresses_the_alias_occurrence() -> None:
    data = b'["anchor", &x null, *x]'
    answer = project_structured(data, "yaml")
    assert answer["status"] == "invalid"
    assert data[answer["error_byte"] :].startswith(b"*x")
    assert project_structured(b'!!int "1.5"', "yaml")["status"] == "invalid"


def test_jsonc_ranges_select_original_bytes_after_non_ascii_comments() -> None:
    raw = rb'"https:\/\/example.org/*literal*/?q=\"//,}"'
    data = '/*🌊*/ {\r\n// clé\r\n "nested": '.encode() + b"[" + raw + b", /* trailing */],\r\n}"
    outer = project_structured(data, "json", path=["nested"])["node"]["source_range"]
    assert data[outer["start_byte"] : outer["end_byte"]] == b"[" + raw + b", /* trailing */]"
    node = project_structured(data, "json", path=["nested", 0])["node"]
    assert node["value"] == 'https://example.org/*literal*/?q="//,}'
    inner = node["source_range"]
    assert data[inner["start_byte"] : inner["end_byte"]] == raw


@pytest.mark.parametrize(
    "data", [b"[,]", b"{,}", b"[1,,]", b'{"a":,}', b"[1/*x*/2]", b"{x:1}", b"['x']"]
)
def test_jsonc_only_accepts_comments_and_trailing_commas(data: bytes) -> None:
    assert project_structured(data, "json")["status"] == "invalid"


def test_jsonc_comment_error_and_retry_budget() -> None:
    from metabrowser.diff.structured_projection import JSONC_MAX_BYTES

    data = '["🌊", /* open'.encode()
    result = project_structured(data, "json")
    assert result["status"] == "invalid"
    assert result["error_byte"] == data.index(b"/*")
    assert (
        project_structured(b"//" + b"x" * JSONC_MAX_BYTES + b"\n1", "json")["status"] == "too_large"
    )
    assert project_structured(b" " * JSONC_MAX_BYTES + b"1", "json")["status"] == "ready"


@pytest.mark.parametrize("fmt", ["json", "yaml"])
def test_inline_node_is_the_same_addressed_node(fmt: Format) -> None:
    data = '{"α": [{"0": [42]}], "empty": []}'.encode()
    assert project_structured(data, fmt) == project_structured(data, fmt, depth=1)
    for depth in range(1, 5):
        page = project_structured(data, fmt, depth=depth)
        row = page["children"][0]
        path: list[str | int] = []
        for level in range(1, depth + 1):
            path.append(row["segment"])
            node = row["node"].copy()
            descendants = node.pop("children", None)
            assert node == project_structured(data, fmt, path=path)["node"]
            if level < depth:
                row = descendants[0]
            else:
                assert descendants is None
    assert project_structured(data, fmt, depth=0)["status"] == "invalid"
    assert project_structured(data, fmt, depth=5)["status"] == "invalid"


def test_inline_budget_is_shared_after_reserving_root_page() -> None:
    import json

    from metabrowser.structured_nodes import PAGE_MAX

    width = PAGE_MAX
    data = json.dumps([list(range(width)) for _ in range(width + 1)]).encode()
    complete = project_structured(data, "json", limit=width, depth=4)
    assert len(complete["children"]) == width
    assert all("children" not in row["node"] for row in complete["children"])
    assert complete["next_offset"] == width
    page = project_structured(data, "json", offset=2, limit=3, depth=4)
    rows = page["children"]
    assert [row["segment"] for row in rows] == [2, 3, 4]
    counts = [len(row["node"]["children"]) for row in rows]
    assert max(counts) - min(counts) <= 1
    assert sum(counts) + len(rows) == PAGE_MAX
    for row, count in zip(rows, counts, strict=True):
        assert row["node"]["child_count"] == width
        assert [child["segment"] for child in row["node"]["children"]] == list(range(count))
        tail = project_structured(data, "json", path=[row["segment"], count])
        assert tail["node"]["value"] == str(count)


def test_copy_jsonc_field_keeps_original_member_and_all_children() -> None:
    raw = rb'"\u0030" /* spelling */: [1.234567890123456789, {"x": 2},]'
    data = b'{"": {' + raw + b'}, "other":null}'
    response = project_structured(data, "json", path=["", "0"], limit=1, copy_row=True)
    assert response["copy_text"] == "{" + raw.decode() + "}"
    assert response["next_offset"] == 1
    item = project_structured(data, "json", path=["", "0", 1], copy_row=True)
    assert item["copy_text"] == '{"x": 2}'
    assert project_structured(b'"hello"', "json", copy_row=True)["copy_text"] == '"hello"'


@pytest.mark.parametrize(
    ("text", "path", "relative", "expected"),
    [
        ("outer:\r\n  text: |2-\r\n    hé\r\n  next: 42", ["outer", "text"], ["text"], "hé"),
        ("lines:\n  - |2+\n    x\n\n  - end\n", ["lines", 0], [], "x\n\n"),
        ("{outer: {'': [x, y], other: 1}}", ["outer", ""], ["", 1], "y"),
        ('? "0"\n: 1.234567890123456789\n', ["0"], ["0"], "1.234567890123456789"),
        ("items:\n-\n- next\n", ["items", 0], [], None),
        ("---\n---\n", [], [], None),
    ],
)
def test_copied_yaml_is_a_reusable_row(
    text: str, path: list[str | int], relative: list[str | int], expected: object
) -> None:
    copied = project_structured(text.encode(), "yaml", path=path, copy_row=True)["copy_text"]
    restored = project_structured(copied.encode(), "yaml", path=relative)
    assert restored["node"]["value"] == expected
    if path and isinstance(path[-1], str):
        root = project_structured(copied.encode(), "yaml")
        assert [row["segment"] for row in root["children"]] == [path[-1]]


@pytest.mark.parametrize("name", ["record.yaml", "record.md"])
def test_copy_route_uses_the_selected_revision_and_keeps_source_independent(
    tmp_path: Path, name: str
) -> None:
    import asyncio
    import json

    from starlette.datastructures import QueryParams

    from metabrowser import server
    from metabrowser.builtin_plugins.structured.nodes_route import read_projection
    from metabrowser.source import FilesystemContentSource

    data = 'outer: {"é": [1, 2], sibling: false}\n'.encode()
    if name.endswith(".md"):
        data = b"---\n" + data + b"---\n# Body\n"
    (tmp_path / name).write_bytes(data)
    server._set_root_dir(tmp_path)
    ref = asyncio.run(FilesystemContentSource(tmp_path).open_ref(name))
    assert ref is not None
    params = {"node": json.dumps(["outer", "é"]), "copy": "row", "mtime_hash": ref.fingerprint}
    response = asyncio.run(read_projection(ref, QueryParams(params)))
    result = json.loads(bytes(response.body))
    assert result["copy_text"] == '{"é": [1, 2]}'
    span = result["node"]["source_range"]
    assert data[span["start_byte"] : span["end_byte"]] == b"[1, 2]"
    stale = asyncio.run(read_projection(ref, QueryParams({**params, "mtime_hash": "stale"})))
    assert stale.status_code == 409
    assert "copy_text" not in json.loads(bytes(stale.body))


@pytest.mark.parametrize(
    ("name", "data", "names"),
    [
        ("records.json", b"[{name:'Ada'}, {name:'Bo'}]", ["Ada", "Bo"]),
        ("records.yaml", b"- &person {name: Ada}\n- *person\n", ["Ada", "Ada"]),
    ],
)
def test_value_only_grid_opens_existing_records_without_claiming_exact_source(
    tmp_path: Path, name: str, data: bytes, names: list[str]
) -> None:
    from starlette.applications import Starlette
    from starlette.testclient import TestClient

    from metabrowser import server
    from metabrowser.plugin_loader.static_assets import build_plugin_routes

    (tmp_path / name).write_bytes(data)
    server._set_root_dir(tmp_path)
    plugins = [p for p in server._LOADED_PLUGINS if p.name in ("structured", "table")]
    with TestClient(Starlette(routes=build_plugin_routes(plugins))) as client:
        url = "/api/plugin/structured/parsed"
        params = {"path": name, "projection": "nodes"}
        page = client.get(url, params=params).json()
        assert page["record_table"] and page["status"] == "invalid"
        assert "node" not in page and "source_range" not in page
        rows = client.get("/api/plugin/table/rows", params={"path": name}).json()["rows"]
        assert [row["cells"]["name"] for row in rows] == names
        for selection in (
            {"node": "[0]"},
            {"document": "1"},
            {"copy": "row"},
            {"tree": "1"},
            {"offset": "1"},
        ):
            other = client.get(url, params={**params, **selection}).json()
            assert not other.get("record_table") and "copy_text" not in other
        assert client.get(url, params={**params, "mtime_hash": "stale"}).status_code == 409
        markdown = tmp_path / "excerpt.md"
        markdown.write_bytes(b"~~~" + name.split(".")[1].encode() + b"\n" + data + b"\n~~~")
        excerpt = client.get(
            url, params={**params, "path": markdown.name, "fence_line": "1"}
        ).json()
        assert excerpt["status"] == "invalid" and not excerpt["record_table"]


@pytest.mark.parametrize(
    ("ext", "data"),
    [
        (".json", b"[{a:1,'a':2}]"),
        (".json", b"[{a:Infinity}]"),
        (".json", b"[{a:'\\ud800'}]"),
        (".json", b"[{a:1}, 7]"),
        (".json", b"[{a:1}"),
        (".yaml", b"- &a {field: *a}"),
        (".yaml", b"- &a {name: Ada}\n- {ref: *a, repeated: 1, repeated: 2}"),
        (".yaml", b"- &a {name: Ada}\n- {ref: *a, 0: number}"),
        (".yaml", b"- &a {name: Ada}\n- {ref: *a, field: !unknown x}"),
    ],
)
def test_value_only_grid_refuses_ambiguous_or_unrepresentable_records(
    ext: str, data: bytes
) -> None:
    from metabrowser.builtin_plugins.structured.nodes_route import _fallback_grid

    fmt: Format = "json" if ext == ".json" else "yaml"
    page = project_structured(data, fmt)
    assert page["status"] == "invalid"
    assert not _fallback_grid(data, ext, page["error_byte"])


def test_value_only_grid_respects_legacy_prefix_and_json5_retry_budget() -> None:
    from metabrowser.builtin_plugins.structured.nodes_route import _fallback_grid
    from metabrowser.diff.structured_projection import JSONC_MAX_BYTES

    data = b"[{name:'Ada'}]"
    assert not _fallback_grid(data, ".csv", 2)
    assert not _fallback_grid(data.ljust(JSONC_MAX_BYTES + 1), ".json", 2)


def test_value_only_grid_caps_alias_expansion_independently_of_input_bytes() -> None:
    from metabrowser.builtin_plugins.structured.nodes_route import _fallback_grid
    from metabrowser.structured_nodes import projection_byte_limit

    # The bounded reader admits the compact input but refuses its repeated value.
    data = b"- &item {name: " + b"a" * (projection_byte_limit("yaml") // 2) + b"}\n"
    data += b"- *item\n" * 10
    assert len(data) < projection_byte_limit("yaml")
    assert not _fallback_grid(data, ".yaml", data.index(b"*"))


@pytest.mark.parametrize("indent", ["", "  "])
def test_yaml_preview_exposes_only_proven_siblings(indent: str) -> None:
    text = (
        "title: Café\r\nitems:\r\n"
        f"{indent}- note: |\r\n{indent}    - text inside a scalar\r\n"
        f"{indent}- name: second\r\n{indent}- name: third\r\n"
        f"{indent}- name: Café\r\n"
    ).encode()
    prefix = text[: text.rindex("é".encode()) + 1]
    root = project_structured(prefix, "yaml", truncated_yaml=True, depth=3)
    assert root["preview"] and "document_count" not in root
    assert root["node"]["partial"] and "source_range" not in root["node"]
    seq = root["children"][1]["node"]
    assert seq["partial"] and "source_range" not in seq
    assert seq["child_count"] == 3
    for index in range(3):
        full = project_structured(text, "yaml", path=["items", index], copy_row=True, tree=True)
        page = project_structured(
            prefix, "yaml", path=["items", index], copy_row=True, tree=True, truncated_yaml=True
        )
        for field in ["node", "copy_text", "tree_value", "children"]:
            assert page[field] == full[field]
    for path in [[], ["items"], ["items", 3]]:
        refused = project_structured(prefix, "yaml", truncated_yaml=True, path=path, copy_row=True)
        assert refused["status"] == "too_large" and "copy_text" not in refused
    corrupt = project_structured(prefix + b"\xff!", "yaml", truncated_yaml=True)
    assert corrupt["status"] == "invalid"


def test_large_yaml_route_previews_complete_mapping_children(tmp_path: Path) -> None:
    from starlette.applications import Starlette
    from starlette.testclient import TestClient

    from metabrowser import server
    from metabrowser.plugin_loader.static_assets import build_plugin_routes

    data = b"summary: ordinary\nitems:\n" + b"- name: " + b"x" * 50 + b"\n"
    data += (b"- name: " + b"y" * 64 + b"\n") * 800
    (tmp_path / "inventory.yaml").write_bytes(data)
    server._set_root_dir(tmp_path)
    plugins = [p for p in server._LOADED_PLUGINS if p.name == "structured"]
    with TestClient(Starlette(routes=build_plugin_routes(plugins))) as client:
        params = {"path": "inventory.yaml", "projection": "nodes", "node": '["items"]'}
        page = client.get("/api/plugin/structured/parsed", params=params).json()
        assert page["status"] == "ready" and page["preview"]
        assert page["node"]["partial"] and 1 < page["node"]["child_count"] < 801
        assert "source_range" not in page["node"] and not page["record_table"]


def test_oversized_yaml_mapping_finishes_prior_sequence_and_excludes_open_scalar() -> None:
    prefix = b"title: collection\nitems:\n- one\n- two\nnotes: |\n  unfinished"
    page = project_structured(prefix, "yaml", truncated_yaml=True)
    assert [row["segment"] for row in page["children"]] == ["title", "items"]
    items = project_structured(prefix, "yaml", truncated_yaml=True, path=["items"], tree=True)
    assert items["tree_value"] == ["one", "two"]
    span = items["node"]["source_range"]
    assert prefix[span["start_byte"] : span["end_byte"]] == b"- one\n- two\n"
    assert project_structured(b"title: only", "yaml", truncated_yaml=True)["status"] == "too_large"


def test_yaml_preview_observes_node_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    from metabrowser import structured_nodes

    monkeypatch.setattr(structured_nodes, "STRUCTURED_YAML_MAX_NODES", 8)
    data = b"title: collection\nitems:\n" + b"- value\n" * 100
    page = project_structured(data, "yaml", truncated_yaml=True, path=["items"])
    assert page["status"] == "ready"
    assert 0 < page["node"]["child_count"] < 8


def test_large_yaml_nested_mapping_keeps_complete_entry_ranges(tmp_path: Path) -> None:
    from starlette.applications import Starlette
    from starlette.testclient import TestClient

    from metabrowser import server
    from metabrowser.plugin_loader.static_assets import build_plugin_routes

    header = "title: Café\r\nentries:\r\n  first:\r\n    note: |\r\n      possible: key\r\n"
    entries = [f"  item-{n}: {'x' * 64}\r\n" for n in range(900)]
    data = (header + "".join(entries) + "later: true\r\n").encode()
    (tmp_path / "catalog.yaml").write_bytes(data)
    server._set_root_dir(tmp_path)
    plugins = [p for p in server._LOADED_PLUGINS if p.name == "structured"]
    url = "/api/plugin/structured/parsed"
    params = {"path": "catalog.yaml", "projection": "nodes"}
    with TestClient(Starlette(routes=build_plugin_routes(plugins))) as client:
        root = client.get(url, params=params).json()
        entries_node = root["children"][1]["node"]
        assert entries_node["partial"] and "source_range" not in entries_node
        page = client.get(url, params={**params, "node": '["entries"]'}).json()
        assert page["preview"] and page["node"] == entries_node
        assert 1 < entries_node["child_count"] < 901
        copied = client.get(url, params={**params, "node": '["entries","first"]', "copy": "row"})
        expected = project_structured(
            (header + entries[0]).encode(), "yaml", path=["entries", "first"], copy_row=True
        )
        for field in ["node", "children", "copy_text"]:
            assert copied.json()[field] == expected[field]
        refused = client.get(url, params={**params, "node": '["entries"]', "copy": "row"}).json()
        assert refused["status"] == "too_large" and "copy_text" not in refused
