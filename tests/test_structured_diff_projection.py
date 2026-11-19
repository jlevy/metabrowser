"""The merged YAML and JSON tree a changed structured file's Rendered view draws."""

from __future__ import annotations

import json
import random
import sys
import threading
import time
import warnings
from collections.abc import Callable
from typing import Any

import pytest

from metabrowser.diff import structured_projection
from metabrowser.diff.structured_projection import (
    JSONC_MAX_BYTES,
    SLOW_PARSE_MAX_BYTES,
    STRUCTURED_DIFF_MAX_BYTES,
    StructuredDiffEntry,
    project_structured_diff,
    structured_format,
)

# What a bounded YAML parse may take in these tests: a smoke check only, with room for a
# loaded machine. Whether the merge's work is bounded is asserted by counting it
# (_loop_iterations), which load does not change (mb-8274 review E2).
_CEILING_S = 3.0

# The Python loop iterations one JSON projection may make. Each unit its budgets meter (a
# value, an entry, an alignment or a pairing step) is a pass or two of a loop, so a
# projection that meters all its work stays within a small multiple of their sum. The
# most any shape below makes on Python 3.14 is 0.97 million, the 111 KB pair of review
# E1, against 642,000 budgeted units; with E1's pairing walking the long side it made
# more than 2 million in 0.4 s, and A1's and C3's shapes made 2.4 to more than 8 million
# on the round-1 module (785ff2e94).
_WORK_LIMIT = 3 * (
    structured_projection._MAX_NODES  # pyright: ignore[reportPrivateUsage]
    + structured_projection._MAX_ENTRIES  # pyright: ignore[reportPrivateUsage]
    + structured_projection._MAX_ALIGNMENT_STEPS  # pyright: ignore[reportPrivateUsage]
    + structured_projection._MAX_PAIRING_STEPS  # pyright: ignore[reportPrivateUsage]
)


class _TooMuchWork(BaseException):
    """Stops a projection past its loop limit; a BaseException, so no handler in the
    projection mistakes it for a parse error."""


def _loop_iterations(run: Callable[[], object], limit: int) -> int:
    """The Python loop iterations *run* makes on this thread, stopping it past *limit*.

    Each pass of a ``for`` or ``while`` loop, a comprehension or a generator ends in an
    unconditional jump, which ``sys.monitoring`` reports as a JUMP event, so the count is
    the work pure-Python code does, the same on a loaded machine as on an idle one. Past
    *limit* an exception stops *run*, so a quadratic regression fails in the time the
    limit takes rather than its own.
    """

    monitoring = sys.monitoring
    tool = next(each for each in range(6) if monitoring.get_tool(each) is None)
    thread = threading.get_ident()
    count = 0
    stopped = False

    def jumped(code: object, offset: int, destination: int) -> None:
        nonlocal count, stopped
        if stopped or threading.get_ident() != thread:
            return
        count += 1
        if count > limit:
            stopped = True
            raise _TooMuchWork

    monitoring.use_tool_id(tool, "loop iterations")
    try:
        monitoring.register_callback(tool, monitoring.events.JUMP, jumped)
        monitoring.set_events(tool, monitoring.events.JUMP)
        try:
            run()
        except _TooMuchWork:
            pass
        finally:
            monitoring.set_events(tool, monitoring.events.NO_EVENTS)
    finally:
        monitoring.register_callback(tool, monitoring.events.JUMP, None)
        monitoring.free_tool_id(tool)
    return count


def _compact(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode()


def _projected_within(old: bytes, new: bytes, limit: int) -> tuple[int, str | None]:
    """The loop iterations a JSON projection of *old* and *new* makes, and its status, or
    None when it was stopped past *limit*."""

    statuses: list[str] = []
    work = _loop_iterations(
        lambda: statuses.append(project_structured_diff(old=old, new=new, fmt="json")["status"]),
        limit,
    )
    return work, statuses[0] if statuses else None


def _values(value: object) -> int:
    """The values *value* holds, itself included: what the node budget counts."""

    if isinstance(value, dict):
        return 1 + sum(_values(item) for item in value.values())  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
    if isinstance(value, list):
        return 1 + sum(_values(item) for item in value)  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
    return 1


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
            old=None if old is None else json.dumps(old).encode(),
            new=None if new is None else json.dumps(new).encode(),
            fmt="json",
        )
    )


def _sendable(answer: object) -> bytes:
    """*answer* encoded as the route's `JSONResponse` encodes it."""

    return json.dumps(
        answer, ensure_ascii=False, allow_nan=False, indent=None, separators=(",", ":")
    ).encode("utf-8")


def _shape(entries: list[StructuredDiffEntry]) -> list[object]:
    """Each entry as `change key` or `change key value`, nesting a modified entry's."""

    shaped: list[object] = []
    for entry in entries:
        label = f"{entry['change']} {entry.get('key', '-')}"
        if entry["change"] == "modified":
            shaped.append([label, _shape(entry.get("entries", []))])
        else:
            shaped.append(f"{label} {json.dumps(entry.get('value'))}")
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


def test_yaml_values_the_tree_route_cannot_send_are_coerced_to_json() -> None:
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
        (b"a: 1\na: 2\n", b"a: 1\n", "yaml"),
        (b'{"admin": false}', b'{"admin": true, "admin": false}', "json"),
        (b'{"a": 1,}', b'{"a": 1, "a": 2,}', "json"),
        (b"a: 1\n", b"a: 1\n", "yaml"),
    ],
    ids=[
        "malformed-yaml",
        "malformed-json",
        "yaml-duplicate-key",
        "json-duplicate-key",
        "jsonc-duplicate-key",
        "same-bytes",
    ],
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


def test_aliases_and_merge_keys_read_as_their_values() -> None:
    old = "base: &b {x: 1}\nc:\n  <<: *b\n  y: 2\nd: *b\n"
    new = "base: &b {x: 1}\nc:\n  <<: *b\n  y: 3\nd: *b\n"
    assert _shape(_yaml(old, new)["root"]) == [
        [
            "modified -",
            [
                'context base {"x": 1}',
                ["modified c", ["context x 1", "removed y 2", "added y 3"]],
                'context d {"x": 1}',
            ],
        ]
    ]


def test_an_alias_bomb_is_refused_before_it_expands(monkeypatch: pytest.MonkeyPatch) -> None:
    # mb-8274 review A2: ruamel's C parser, when installed, is never what reads it.
    import ruamel.yaml.main

    class Refused:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise AssertionError("the C parser was used")

    monkeypatch.setattr(ruamel.yaml.main, "CParser", Refused, raising=False)
    levels = "".join(f"l{n}: &l{n} [{', '.join([f'*l{n - 1}'] * 9)}]\n" for n in range(1, 10))
    bomb = ("l0: &l0 [x]\n" + levels).encode()
    start = time.perf_counter()
    answer = project_structured_diff(old=None, new=bomb, fmt="yaml")
    assert time.perf_counter() - start < _CEILING_S
    assert answer["status"] == "too_large"


def test_reused_anchor_names_write_no_warning() -> None:
    # mb-8274 review B5: ruamel warns once per reused anchor, quoting the file.
    text = "".join(f"- &a {index}\n" for index in range(500)).encode()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        answer = project_structured_diff(old=None, new=text, fmt="yaml")
    assert answer["status"] == "ready"
    assert [str(each.message) for each in caught if "anchor" in str(each.message).lower()] == []


def test_pairs_past_the_byte_bounds_are_too_large() -> None:
    big = json.dumps({"a": "x" * STRUCTURED_DIFF_MAX_BYTES}).encode()
    assert project_structured_diff(old=None, new=big, fmt="json")["status"] == "too_large"
    yaml = b"a: " + b"x" * SLOW_PARSE_MAX_BYTES + b"\n"
    assert project_structured_diff(old=None, new=yaml, fmt="yaml")["status"] == "too_large"
    # Strict JSON of the same size is inside its own, larger bound.
    strict = json.dumps({"a": "x" * SLOW_PARSE_MAX_BYTES}).encode()
    assert project_structured_diff(old=None, new=strict, fmt="json")["status"] == "ready"
    jsonc = b"// c\n" + json.dumps({"a": "x" * JSONC_MAX_BYTES}).encode()
    assert project_structured_diff(old=None, new=jsonc, fmt="json")["status"] == "too_large"
    small = b"// c\n" + json.dumps({"a": "x" * (JSONC_MAX_BYTES // 2)}).encode()
    assert project_structured_diff(old=None, new=small, fmt="json")["status"] == "ready"


def test_yaml_is_bounded_by_the_nodes_it_composes() -> None:
    # mb-8274 review A4: a flow list of one-digit integers is a node every three bytes.
    def flow(count: int, last: int) -> bytes:
        return ("[" + ", ".join(["1"] * (count - 1) + [str(last)]) + "]\n").encode()

    over = structured_projection._MAX_YAML_NODES  # pyright: ignore[reportPrivateUsage]
    start = time.perf_counter()
    answer = project_structured_diff(old=flow(over, 1), new=flow(over, 2), fmt="yaml")
    assert time.perf_counter() - start < _CEILING_S
    assert answer["status"] == "too_large"
    inside = project_structured_diff(old=flow(1_000, 1), new=flow(1_000, 2), fmt="yaml")
    assert inside["status"] == "ready"


def test_nesting_past_the_bound_is_too_large_in_yaml_and_json() -> None:
    # mb-8274 review B8: YAML's composer refuses it as it reads, at once.
    deep = 70
    yaml = ("[" * deep + "1" + "]" * deep + "\n").encode()
    start = time.perf_counter()
    assert project_structured_diff(old=None, new=yaml, fmt="yaml")["status"] == "too_large"
    assert time.perf_counter() - start < _CEILING_S
    nested: object = 1
    for _ in range(deep):
        nested = [nested]
    assert _json(None, nested)["status"] == "too_large"
    shallow: object = 1
    for _ in range(30):
        shallow = [shallow]
    assert _json(None, shallow)["status"] == "ready"


def test_trees_past_the_node_and_entry_budgets_are_too_large() -> None:
    many = json.dumps([0] * 50_000).encode()
    assert project_structured_diff(old=None, new=many, fmt="json")["status"] == "too_large"
    old = list(range(5_000))
    new = [*old[:10], -1, *old[11:]]
    assert _json(old, new)["status"] == "too_large"
    assert _json(old[:1_000], new[:1_000])["status"] == "ready"


def test_a_long_run_of_repeated_mappings_aligns_within_the_work_budget() -> None:
    old = _compact([{"k": index % 10} for index in range(3_000)])
    new = _compact([{"k": (index * 7) % 10} for index in range(3_000)])
    work, _ = _projected_within(old, new, _WORK_LIMIT)
    assert work <= _WORK_LIMIT, work


def test_structured_format_names_the_plugins_extensions() -> None:
    assert structured_format(".json") == "json"
    assert structured_format(".YML") == "yaml"
    assert structured_format(".yaml") == "yaml"
    assert structured_format(".md") is None


def test_a_long_run_of_repeated_values_aligns_within_the_work_budget() -> None:
    # mb-8274 review A1: difflib's matcher is cubic in repeated values; this pair made
    # more than 8 million loop iterations on the round-1 module, and makes 0.65 million.
    old = _compact([index % 10 for index in range(1_000)])
    new = _compact([(index * 7) % 10 for index in range(1_000)])
    work, status = _projected_within(old, new, _WORK_LIMIT)
    assert work <= _WORK_LIMIT, work
    assert status == "ready"


def test_nesting_does_not_multiply_the_work() -> None:
    # mb-8274 review C3: comparing each level walked everything under it. A list of
    # 19,000 fits the node budget at both depths, so each pair reaches the merge; at
    # depth 15 the round-1 module made 2.4 million loop iterations, and this makes about
    # three for each value.
    inner = [index % 10 for index in range(19_000)]

    def nest(last: int, depth: int) -> object:
        value: object = [inner, last]
        for _ in range(depth):
            value = [value, 0]
        return value

    for depth in (15, 60):
        old, new = nest(1, depth), nest(2, depth)
        limit = 8 * (_values(old) + _values(new))
        work, status = _projected_within(_compact(old), _compact(new), limit)
        assert work <= limit, (depth, work)
        assert status == "ready", depth


@pytest.mark.parametrize(("long", "short"), [(5_000, 2_000), (15_000, 8_000)])
def test_a_long_list_against_many_short_ones_pairs_within_the_work_budget(
    long: int, short: int
) -> None:
    # mb-8274 review E1: pairing charged one step for each pair of lists but walked the
    # long removed list for each, so a 111 KB pair took 10-11 s; it made more than
    # 2 million loop iterations in 0.4 s, and makes under 1 million.
    old, new = _compact([list(range(long))]), _compact([[0]] * short)
    assert len(old) + len(new) <= STRUCTURED_DIFF_MAX_BYTES
    work, _ = _projected_within(old, new, _WORK_LIMIT)
    assert work <= _WORK_LIMIT, work


def test_past_the_alignment_budget_equal_items_stay_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # mb-8274 review A6: the replaced run pairs in order, and an equal pair is context.
    monkeypatch.setattr(structured_projection, "_MAX_ALIGNMENT_STEPS", 0)
    assert _shape(_json([0, 1, 2, 3, 0], [0, 5, 2, 6, 0])["root"]) == [
        [
            "modified -",
            [
                "context - 0",
                "removed - 1",
                "added - 5",
                "context - 2",
                "removed - 3",
                "added - 6",
                "context - 0",
            ],
        ]
    ]


def test_an_insertion_beside_an_edit_pairs_the_edited_item() -> None:
    # mb-8274 review D1: in order, the inserted job was compared with the edited one.
    old = {"jobs": [{"name": "build", "run": "make", "os": "linux"}, {"name": "test"}]}
    new = {
        "jobs": [
            {"name": "lint", "run": "ruff", "os": "mac"},
            {"name": "build", "run": "make all", "os": "linux"},
            {"name": "test"},
        ]
    }
    assert _shape(_json(old, new)["root"]) == [
        [
            "modified -",
            [
                [
                    "modified jobs",
                    [
                        'added - {"name": "lint", "run": "ruff", "os": "mac"}',
                        [
                            "modified -",
                            [
                                'context name "build"',
                                'removed run "make"',
                                'added run "make all"',
                                'context os "linux"',
                            ],
                        ],
                        'context - {"name": "test"}',
                    ],
                ]
            ],
        ]
    ]


def test_a_removed_key_is_drawn_before_a_key_added_after_it() -> None:
    assert _shape(_json({"a": 1, "b": 2}, {"a": 1, "c": 3})["root"]) == [
        ["modified -", ["context a 1", "removed b 2", "added c 3"]]
    ]


def test_signed_zero_is_one_value() -> None:
    # mb-8274 review D3: the merge and the alignment agree, as == does.
    answer = _json([0.0, 1], [-0.0, 1])
    assert answer["source_only"] is True
    assert [entry["change"] for entry in answer["root"]] == ["context"]


def test_numbers_a_browser_cannot_tell_apart_carry_their_text() -> None:
    # mb-8274 review A7: 2**60 and 2**60 + 1 are one JavaScript number, as are 1 and 1.0.
    answer = _json([2**60, 1], [2**60 + 1, 1.0])
    removed = [entry for entry in answer["root"][0]["entries"] if entry["change"] == "removed"]
    added = [entry for entry in answer["root"][0]["entries"] if entry["change"] == "added"]
    assert [entry.get("text") for entry in removed] == [str(2**60), None]
    assert [entry.get("text") for entry in added] == [str(2**60 + 1), "1.0"]


@pytest.mark.parametrize(
    ("old", "new", "fmt"),
    [
        (b'{"a": 0x' + b"f" * 4_000 + b",}", b'{"a": 1,}', "json"),
        (b"a: 0x" + b"f" * 4_000 + b"\n", b"a: 1\n", "yaml"),
        (b'{"a": "\\ud800"}', b'{"a": "x"}', "json"),
        (b'a: "\\uD800"\n', b"a: x\n", "yaml"),
        (b'{"\\ud800": 1}', b'{"x": 1}', "json"),
    ],
    ids=["jsonc-hex", "yaml-hex", "json-surrogate", "yaml-surrogate", "json-surrogate-key"],
)
def test_every_ready_answer_can_be_sent(old: bytes, new: bytes, fmt: str) -> None:
    # mb-8274 review A9 and B4: such values made a ready answer the encoder refused.
    answer = project_structured_diff(old=old, new=new, fmt=fmt)  # pyright: ignore[reportArgumentType]
    assert answer["status"] == "ready"
    assert _sendable(answer)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ('enabled: "no"\n', "enabled: no\n"),
        ("1: a\n", '"1": a\n'),
        ("true: a\n", '"true": a\n'),
        ("d: 2024-01-01\n", 'd: "2024-01-01"\n'),
        ("b: !!binary aGk=\n", 'b: "aGk="\n'),
        ("s: !!set {a, b}\n", "s: [a, b]\n"),
        ("[a, b]\n", "a\n---\nb\n"),
    ],
    ids=["yaml-1.1-word", "int-key", "bool-key", "date", "binary", "set", "stream"],
)
def test_a_change_the_tree_draws_alike_is_source_only(old: str, new: str) -> None:
    # mb-8274 review B2: the tree draws both sides' rows alike, so Source shows it.
    answer = _yaml(old, new)
    assert answer["status"] == "ready"
    assert [entry["change"] for entry in answer["root"]] == ["context"]
    assert answer["source_only"] is True


def test_a_hidden_change_beside_a_drawn_one_is_still_source_only() -> None:
    answer = _yaml("d: 2024-01-01\nx: 1\n", 'd: "2024-01-01"\nx: 2\n')
    assert _shape(answer["root"]) == [
        ["modified -", ['context d "2024-01-01"', "removed x 1", "added x 2"]]
    ]
    assert answer["source_only"] is True


def test_non_finite_numbers_and_dates_are_their_text() -> None:
    answer = _yaml(None, "a: .inf\nb: 2026-11-18T10:00:00\nc: !!binary aGk=\nd: !!set {b, a}\n")
    assert answer["root"][0]["value"] == {
        "a": ".inf",
        "b": "2026-11-18T10:00:00",
        "c": "aGk=",
        "d": ["a", "b"],
    }


def _sides(entries: list[StructuredDiffEntry], kind: str | None) -> tuple[object, object]:
    """Both sides a merged list or mapping reads back as: (old, new)."""

    old: list[tuple[str | None, object]] = []
    new: list[tuple[str | None, object]] = []
    for entry in entries:
        key = entry.get("key")
        change = entry["change"]
        if change == "modified":
            before, after = _sides(entry.get("entries", []), entry.get("type"))
            old.append((key, before))
            new.append((key, after))
        else:
            if change in {"context", "removed"}:
                old.append((key, entry.get("value")))
            if change in {"context", "added"}:
                new.append((key, entry.get("value")))
    if kind == "map":
        return dict(old), dict(new)  # pyright: ignore[reportArgumentType]
    return [value for _, value in old], [value for _, value in new]


def _random_value(rng: random.Random, depth: int) -> object:
    roll = rng.random()
    if depth > 2 or roll < 0.5:
        return rng.choice([0, 1, 2, "a", "b", True, None])
    if roll < 0.75:
        return [_random_value(rng, depth + 1) for _ in range(rng.randint(0, 6))]
    return {rng.choice("pqrstu"): _random_value(rng, depth + 1) for _ in range(rng.randint(0, 5))}


def _mutated(rng: random.Random, value: object) -> object:
    if isinstance(value, list):
        items = [_mutated(rng, item) if rng.random() < 0.3 else item for item in value]
        for _ in range(rng.randint(0, 2)):
            if items and rng.random() < 0.5:
                items.pop(rng.randrange(len(items)))
            else:
                items.insert(rng.randint(0, len(items)), _random_value(rng, 2))
        return items
    if isinstance(value, dict):
        mapping = {
            key: _mutated(rng, item) if rng.random() < 0.3 else item for key, item in value.items()
        }
        if mapping and rng.random() < 0.3:
            mapping.pop(rng.choice(list(mapping)))
        if rng.random() < 0.3:
            mapping[rng.choice("pqrstuvw")] = _random_value(rng, 2)
        return mapping
    return _random_value(rng, 2) if rng.random() < 0.5 else value


def _common(old: list[str], new: list[str]) -> int:
    """The longest common subsequence of two lists of value texts."""

    best = [[0] * (len(new) + 1) for _ in range(len(old) + 1)]
    for i, before in enumerate(old):
        for j, after in enumerate(new):
            best[i + 1][j + 1] = (
                best[i][j] + 1 if before == after else max(best[i][j + 1], best[i + 1][j])
            )
    return best[-1][-1]


def _minimal(entries: list[StructuredDiffEntry], kind: str | None) -> None:
    """Each modified list keeps as many items unchanged as both sides have in common, and
    each modified mapping marks unchanged every key whose value did not change."""

    old, new = _sides(entries, kind)
    unchanged = [entry for entry in entries if entry["change"] == "context"]
    if kind == "map":
        assert isinstance(old, dict) and isinstance(new, dict)
        same = [key for key in old if key in new and _text(old[key]) == _text(new[key])]
        assert sorted(entry.get("key", "") for entry in unchanged) == sorted(same)
    elif kind == "list":
        assert isinstance(old, list) and isinstance(new, list)
        assert len(unchanged) == _common(
            [_text(item) for item in old], [_text(item) for item in new]
        )
    for entry in entries:
        if entry["change"] == "modified":
            _minimal(entry.get("entries", []), entry.get("type"))


def _text(value: object) -> str:
    return json.dumps(value, sort_keys=True)


@pytest.mark.parametrize("lowered", [False, True], ids=["default", "lowered-bound"])
def test_both_sides_read_back_from_every_merge(
    lowered: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    # mb-8274 review D5: a seeded property of the merge, at the default alignment bound
    # (where the marks are also minimal) and at one so low every list falls back.
    if lowered:
        monkeypatch.setattr(structured_projection, "_MAX_ALIGNMENT_STEPS", 0)
    rng = random.Random(557)
    for _ in range(400):
        old = _random_value(rng, 0)
        if not isinstance(old, dict | list):
            old = [old]
        new = _mutated(rng, old)
        answer = _json(old, new)
        if old == new and _text(old) == _text(new):
            continue
        assert answer["status"] == "ready"
        root = answer["root"]
        if len(root) == 1 and root[0]["change"] == "modified":
            before, after = _sides(root[0].get("entries", []), root[0].get("type"))
        else:
            before, after = _sides(root, None)
            before, after = before[0] if before else None, after[0] if after else None  # pyright: ignore[reportIndexIssue]
        assert _text(before) == _text(old)
        assert json.dumps(after) == json.dumps(new)
        if not lowered:
            _minimal(root, None)


def test_past_the_pairing_budget_a_replaced_run_pairs_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old = [{"name": "build", "run": "make"}, "x"]
    new = [{"name": "lint", "run": "ruff"}, {"name": "build", "run": "make all"}, "x"]
    paired = _shape(_json(old, new)["root"])
    assert paired[0][1][0] == 'added - {"name": "lint", "run": "ruff"}'  # pyright: ignore[reportIndexIssue]
    monkeypatch.setattr(structured_projection, "_MAX_PAIRING_CELLS", 0)
    in_order = _shape(_json(old, new)["root"])
    assert in_order[0][1][0][0] == "modified -"  # pyright: ignore[reportIndexIssue]
