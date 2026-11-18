"""The merged YAML and JSON tree a changed structured file's Rendered view draws."""

from __future__ import annotations

import json
import time
from typing import Any

import pytest

from metabrowser.diff import structured_projection
from metabrowser.diff.structured_projection import (
    SLOW_PARSE_MAX_BYTES,
    STRUCTURED_DIFF_MAX_BYTES,
    StructuredDiffEntry,
    project_structured_diff,
    structured_format,
)


def _yaml(old: str | None, new: str | None) -> dict[str, Any]:
    return dict(
        project_structured_diff(
            old=None if old is None else old.encode(),
            new=None if new is None else new.encode(),
            fmt="yaml",
        )
    )


def _json(old: object, new: object) -> dict[str, Any]:
    return dict(
        project_structured_diff(
            old=json.dumps(old).encode(), new=json.dumps(new).encode(), fmt="json"
        )
    )


def _shape(entries: list[StructuredDiffEntry]) -> list[object]:
    """Each entry as `change key` or `change key value`, nesting a modified entry's."""

    shaped: list[object] = []
    for entry in entries:
        label = f"{entry['change']} {entry.get('key', '-')}"
        if entry["change"] == "modified":
            shaped.append([label, _shape(entry["entries"])])
        else:
            shaped.append(f"{label} {json.dumps(entry['value'])}")
    return shaped


def test_a_changed_scalar_is_its_old_entry_removed_and_its_new_one_added() -> None:
    answer = _yaml("name: demo\nversion: 3\n", "name: demo\nversion: 4\n")
    assert answer["status"] == "ready"
    assert answer["format"] == "yaml"
    assert answer["source_only"] is False
    assert _shape(answer["root"]) == [
        ["modified -", ['context name "demo"', "removed version 3", "added version 4"]]
    ]


def test_mapping_keys_keep_the_new_order_and_a_removed_key_stays_where_it_was() -> None:
    answer = _yaml("a: 1\nb: 2\nc: 3\n", "a: 1\nc: 3\nd: 4\n")
    assert _shape(answer["root"]) == [
        ["modified -", ["context a 1", "removed b 2", "context c 3", "added d 4"]]
    ]


def test_nested_changes_mark_every_mapping_above_them_modified() -> None:
    old = "services:\n  web:\n    image: nginx\n    ports: [80]\n  db:\n    image: pg\n"
    new = "services:\n  web:\n    image: nginx\n    ports: [80, 443]\n  db:\n    image: pg\n"
    assert _shape(_yaml(old, new)["root"]) == [
        [
            "modified -",
            [
                [
                    "modified services",
                    [
                        [
                            "modified web",
                            [
                                'context image "nginx"',
                                ["modified ports", ["context - 80", "added - 443"]],
                            ],
                        ],
                        'context db {"image": "pg"}',
                    ],
                ]
            ],
        ]
    ]


def test_lists_align_by_value_and_pair_replaced_mappings_entry_by_entry() -> None:
    old = [{"id": 1, "v": "a"}, "keep", {"id": 2, "v": "b"}]
    new = ["first", {"id": 1, "v": "a"}, "keep", {"id": 2, "v": "c"}]
    assert _shape(_json(old, new)["root"]) == [
        [
            "modified -",
            [
                'added - "first"',
                'context - {"id": 1, "v": "a"}',
                'context - "keep"',
                ["modified -", ["context id 2", 'removed v "b"', 'added v "c"']],
            ],
        ]
    ]


def test_replaced_scalars_read_as_one_removed_run_and_one_added_run() -> None:
    assert _shape(_json(["a", "b", "x"], ["c", "d", "x"])["root"]) == [
        [
            "modified -",
            ['removed - "a"', 'removed - "b"', 'added - "c"', 'added - "d"', 'context - "x"'],
        ]
    ]


def test_values_of_different_types_differ_as_they_read() -> None:
    answer = _json({"a": 1, "b": True}, {"a": 1.0, "b": 1})
    assert _shape(answer["root"]) == [
        ["modified -", ["removed a 1", "added a 1.0", "removed b true", "added b 1"]]
    ]


def test_a_changed_type_at_the_root_is_removed_then_added() -> None:
    assert _shape(_json([1], {"a": 1})["root"]) == ["removed - [1]", 'added - {"a": 1}']


def test_an_added_and_a_deleted_file_are_one_whole_entry() -> None:
    assert _shape(_yaml(None, "a: 1\n")["root"]) == ['added - {"a": 1}']
    assert _shape(_yaml("a: 1\n", None)["root"]) == ['removed - {"a": 1}']
    assert _yaml(None, "a: 1\n")["source_only"] is False


def test_a_change_the_tree_cannot_show_is_source_only() -> None:
    answer = _yaml("a: 1  # one\nb: 2\n", "b: 2\na: 1  # uno\n")
    assert _shape(answer["root"]) == ['context - {"b": 2, "a": 1}']
    assert answer["source_only"] is True


def test_yaml_values_are_json_values_as_the_tree_route_sends_them() -> None:
    answer = _yaml("1: one\nnull: x\nwhen: 2026-11-18\n", "1: uno\nnull: x\nwhen: 2026-11-18\n")
    assert _shape(answer["root"]) == [
        [
            "modified -",
            ['removed 1 "one"', 'added 1 "uno"', 'context null "x"', 'context when "2026-11-18"'],
        ]
    ]


def test_a_yaml_stream_collapses_as_the_tree_view_collapses_it() -> None:
    answer = _yaml("a: 1\n---\nb: 2\n", "a: 1\n---\nb: 3\n")
    assert _shape(answer["root"]) == [
        [
            "modified -",
            ['context - {"a": 1}', ["modified -", ["removed b 2", "added b 3"]]],
        ]
    ]


def test_jsonc_parses_as_the_tree_view_parses_it() -> None:
    answer = project_structured_diff(
        old=b'{\n  // comment\n  "a": 1,\n}\n', new=b'{\n  "a": 2,\n}\n', fmt="json"
    )
    assert _shape(answer["root"]) == [["modified -", ["removed a 1", "added a 2"]]]


@pytest.mark.parametrize(
    ("old", "new", "fmt"),
    [
        (b"a: [1\n", b"a: 1\n", "yaml"),
        (b"{", b"{}", "json"),
        (b"a: &x 1\nb: *x\n", b"a: 1\n", "yaml"),
    ],
    ids=["malformed-yaml", "malformed-json", "yaml-alias"],
)
def test_a_side_the_tree_view_would_not_draw_is_unsupported(
    old: bytes, new: bytes, fmt: structured_projection.Format
) -> None:
    answer = project_structured_diff(old=old, new=new, fmt=fmt)
    assert answer == {
        "version": "structured-diff-v1",
        "status": "unsupported",
        "root": [],
        "source_only": False,
    }


def test_an_alias_bomb_is_refused_before_it_expands() -> None:
    levels = "".join(f"l{n}: &l{n} [{', '.join([f'*l{n - 1}'] * 9)}]\n" for n in range(1, 10))
    bomb = ("l0: &l0 [x]\n" + levels).encode()
    start = time.perf_counter()
    answer = project_structured_diff(old=None, new=bomb, fmt="yaml")
    assert time.perf_counter() - start < 1.0
    assert answer["status"] == "unsupported"


def test_pairs_past_the_byte_bounds_are_too_large() -> None:
    big = json.dumps({"a": "x" * STRUCTURED_DIFF_MAX_BYTES}).encode()
    assert project_structured_diff(old=None, new=big, fmt="json")["status"] == "too_large"
    yaml = b"a: " + b"x" * SLOW_PARSE_MAX_BYTES + b"\n"
    assert project_structured_diff(old=None, new=yaml, fmt="yaml")["status"] == "too_large"
    # Strict JSON of the same size is inside its own, larger bound.
    strict = json.dumps({"a": "x" * SLOW_PARSE_MAX_BYTES}).encode()
    assert project_structured_diff(old=None, new=strict, fmt="json")["status"] == "ready"
    jsonc = b"// c\n" + strict
    assert project_structured_diff(old=None, new=jsonc, fmt="json")["status"] == "too_large"


def test_trees_past_the_node_and_entry_budgets_are_too_large() -> None:
    many = json.dumps([0] * 50_000).encode()
    assert project_structured_diff(old=None, new=many, fmt="json")["status"] == "too_large"
    old = list(range(5_000))
    new = [*old[:10], -1, *old[11:]]
    assert _json(old, new)["status"] == "too_large"
    assert _json(old[:1_000], new[:1_000])["status"] == "ready"


def test_a_long_run_of_repeated_values_aligns_within_the_work_budget() -> None:
    old = [{"k": index % 10} for index in range(3_000)]
    new = [{"k": (index * 7) % 10} for index in range(3_000)]
    start = time.perf_counter()
    answer = project_structured_diff(
        old=json.dumps(old).encode(), new=json.dumps(new).encode(), fmt="json"
    )
    assert time.perf_counter() - start < 1.0
    assert answer["status"] in {"ready", "too_large"}


def test_structured_format_names_the_plugins_extensions() -> None:
    assert structured_format(".json") == "json"
    assert structured_format(".YML") == "yaml"
    assert structured_format(".yaml") == "yaml"
    assert structured_format(".md") is None
