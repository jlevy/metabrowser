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
