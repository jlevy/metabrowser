"""Front matter is parsed under bounds, off the event loop, and never fails a request.

YAML aliases let a few hundred bytes of front matter stand for millions of values.
:mod:`metabrowser.frontmatter_yaml` composes the document, measures the node graph, and
builds the value itself, leaving ruamel's constructor only the scalars. These tests pin
the outcome on every path a served folder reaches -- the loader, ``/api/file``, and
``/api/kpress/render`` under the untrusted profile -- and bound the work by counting it
rather than timing it: a document past the budget is never built, ruamel never builds a
collection, and ruamel never writes a node into a message. The pinned-revision path is
in ``tests/test_git_revision_content_routes.py``.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import string
import threading
import tracemalloc
import warnings
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
import yaml as pyyaml
from ruamel.yaml import constructor as ruamel_constructor
from ruamel.yaml import nodes as ruamel_nodes

from metabrowser import frontmatter_yaml, server
from metabrowser.capabilities import Capabilities, set_capabilities
from metabrowser.file_kinds import FileContext
from metabrowser.frontmatter_yaml import (
    FRONTMATTER_MAX_BYTES,
    FRONTMATTER_MAX_EXPANDED_SIZE,
    YAML_ERROR_MAX_CHARS,
    YAML_MAX_DEPTH,
    FrontmatterError,
    load_frontmatter_yaml,
)
from metabrowser.plugin_loader.classify import (
    CompiledKindRule,
    build_classifier,
    yaml_mapping_from_bytes,
)
from metabrowser.plugin_loader.manifest import KindMatch, KindRule

REFUSED = "without its YAML aliases"
TOO_DEEP = "nests too deeply"

# A comment the shapes past the budget carry, so a test can find them in an answer.
OVER_BUDGET = "# over budget\n"


def alias_bomb(levels: int, width: int = 9) -> str:
    """*levels* anchors, each a list of *width* aliases to the one before: width**levels values."""

    names = string.ascii_lowercase
    lines = [f"{names[0]}: &{names[0]} [{', '.join(['lol'] * width)}]"]
    for level in range(1, levels):
        refs = ", ".join([f"*{names[level - 1]}"] * width)
        lines.append(f"{names[level]}: &{names[level]} [{refs}]")
    return "\n".join(lines) + "\n"


def merge_bomb(levels: int, width: int = 9) -> str:
    """Each mapping merges *width* aliases of the one before (review A, A1).

    ruamel's constructor copied every merged entry into the merging mapping, so the
    last held width**(levels - 1) entries before any walk of the value.
    """

    names = string.ascii_lowercase
    lines = [f"{names[0]}: &{names[0]} {{k: v}}"]
    for level in range(1, levels):
        refs = ", ".join([f"*{names[level - 1]}"] * width)
        lines.append(f"{names[level]}: &{names[level]} {{<<: [{refs}]}}")
    return OVER_BUDGET + "\n".join(lines) + "\n"


def duplicate_key_bomb(levels: int) -> str:
    """An alias bomb and a key repeated with it as the value (review B, B1).

    ruamel wrote both values of a duplicated key into its error message.
    """

    top = string.ascii_lowercase[levels - 1]
    return OVER_BUDGET + alias_bomb(levels) + f"z:\n  d: *{top}\n  d: *{top}\n"


def merged_into_many(keys: int, mappings: int) -> str:
    """One mapping of *keys* keys merged into *mappings* list items: quadratic in the text."""

    lines = ["b: &b"] + [f"  k{i}: v" for i in range(keys)] + ["items:"]
    lines += ["- <<: *b"] * mappings
    return OVER_BUDGET + "\n".join(lines) + "\n"


def sequence_key_bomb(items: int, uses: int) -> str:
    """A list of *items* used as the key of *uses* mappings; each use copies the list."""

    head = f"k: &k [{', '.join(['x'] * items)}]\n"
    return OVER_BUDGET + head + "".join(f"m{i}: {{? *k : v}}\n" for i in range(uses))


def duplicated_sequence_key(length: int, aliases: int) -> str:
    """A key of *aliases* aliases to one string, used twice: the message named the key."""

    refs = ", ".join(["*s"] * aliases)
    return OVER_BUDGET + f"s: &s {'y' * length}\nz:\n  ? [{refs}]\n  : 1\n  ? [{refs}]\n  : 2\n"


def long_tag_under_a_collection_tag(tag: str, tag_length: int, uses: int, *, mapping: bool) -> str:
    """One scalar with a long tag, aliased *uses* times, in a collection tagged *tag*.

    Review C, C1: `!!timestamp` on a sequence made ruamel write the composed nodes,
    tags and all, into its message, once per use, and the count has no tag in it.
    """

    scalar = f"&a !<{'t' * tag_length}> v"
    if mapping:
        entries = [f"k0: {scalar}"] + [f"k{index}: *a" for index in range(1, uses + 1)]
        return f"z: !<{tag}> {{{', '.join(entries)}}}\n"
    return f"z: !<{tag}> [{scalar}, {', '.join(['*a'] * uses)}]\n"


def nested_inline_merges(depth: int, fan1: int = 100, fan2: int = 3_300) -> str:
    """Review C, C2: one mapping near the budget, wrapped in *depth* inline merges.

    ruamel flattened the merged entries again at each level, and the anchor on each
    level kept every level's two copies alive: 2.5 GB at 480 levels.
    """

    head = "c: &c {'': ''}\n"
    head += "d: &d {<<: [" + ",".join(["*c"] * fan1) + "]}\n"
    inner = "{<<: [" + ",".join(["*d"] * fan2) + "]}"
    opens = "".join(f"{{<<: &n{index} " for index in range(depth))
    return head + "x: " + opens + inner + "}" * depth + "\n"


def flow_sawtooth(depth: int, size: int) -> str:
    """Review C, C3: flow sequences *depth* deep, rising and falling on one line.

    ruamel's scanner walks one pending simple key for each open flow level on every
    token, so the parse cost a factor of the depth.
    """

    unit = "[" * depth + "]" * depth + ","
    return "x: [" + unit * ((size - 6) // len(unit)) + "]\n"


# Every tag the safe loader builds that JSON has no type for, and keys JSON cannot key by.
NON_JSON_SAFE = """\
binary: !!binary aGVsbG8=
set: !!set {b, a}
omap: !!omap [first: 1, second: 2]
pairs: !!pairs [a: 1, a: 2]
nan: .nan
inf: .inf
negative_inf: -.inf
date: 2026-11-17
stamp: 2026-11-17 10:00:00
huge: 0x{huge}
? [a, b]
: tuple key
? 2026-11-17
: date key
1: int key
2.5: float key
null: null key
""".replace("{huge}", "F" * 4_000)

# Front matter the loader does not build, and the reason it gives. A reason names the
# line and the kind of node, never the scalar's text.
CONSTRUCTOR_FAILURES = {
    "bool": ("x: !!bool maybe\n", "line 1: not a valid !!bool"),
    "int": ("x: !!int ''\n", "line 1: not a valid !!int"),
    "timestamp": ("when: 9999-12-31T23:59:59.9999999999Z\n", "line 1: not a valid !!timestamp"),
    "omap": ("x: !!omap [a: 1, a: 2]\n", "line 1: a key appears twice in an ordered map"),
    "timestamp-sequence": (
        "z: !!timestamp [&a v, *a]\n",
        "line 1: a sequence has a tag the loader does not read",
    ),
    "version": ("%YAML 1.31\n--- # x\nkey: v\n", "AssertionError"),
}

# Each escape builds a lone surrogate, which UTF-8 cannot encode; the last two make a pair.
SURROGATES = 'x: "\\ud800"\n"\\udfff": 1\npair: "\\ud83d\\ude00"\n'

OVER_BUDGET_SHAPES = {
    "alias-7": OVER_BUDGET + alias_bomb(7),
    "alias-12": OVER_BUDGET + alias_bomb(12),
    "merge-7": merge_bomb(7),
    "merge-12": merge_bomb(12),
    "duplicate-key-7": duplicate_key_bomb(7),
    "duplicate-key-12": duplicate_key_bomb(12),
    "merged-into-many": merged_into_many(1_000, 1_000),
    "sequence-key": sequence_key_bomb(2_000, 600),
    "duplicated-sequence-key": duplicated_sequence_key(30_000, 2_000),
}

_COLLECTION_TAGS = tuple(
    f"tag:yaml.org,2002:{name}" for name in ("map", "seq", "set", "omap", "pairs")
)


def forbid_ruamel_collections(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail at once if ruamel's constructor builds a collection, or PyYAML builds anything.

    The loader builds every mapping, sequence, and merge key itself (review C, C6), so
    none of these may run. Where they would, they stop a document that would otherwise
    take gigabytes or hours.
    """

    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("a YAML constructor built a collection")

    for cls in (ruamel_constructor.BaseConstructor, ruamel_constructor.SafeConstructor):
        for name in (
            "construct_document",
            "construct_mapping",
            "construct_sequence",
            "construct_pairs",
            "flatten_mapping",
        ):
            if name in vars(cls):
                monkeypatch.setattr(cls, name, refuse)
    for tag in _COLLECTION_TAGS:
        monkeypatch.setitem(ruamel_constructor.SafeConstructor.yaml_constructors, tag, refuse)
    monkeypatch.setattr(pyyaml.constructor.BaseConstructor, "construct_document", refuse)


@pytest.fixture
def no_ruamel_collections(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    forbid_ruamel_collections(monkeypatch)
    yield


def test_the_seven_level_bomb_from_the_report_is_refused() -> None:
    text = alias_bomb(7)
    assert len(text) == 310

    with pytest.raises(FrontmatterError, match=REFUSED) as refused:
        load_frontmatter_yaml(text)

    assert f"{FRONTMATTER_MAX_EXPANDED_SIZE:,} characters" in str(refused.value)


@pytest.mark.parametrize("shape", OVER_BUDGET_SHAPES)
@pytest.mark.usefixtures("no_ruamel_collections")
def test_a_document_past_the_budget_is_refused_before_it_is_built(
    shape: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Aliases, merge keys, sequence keys, and duplicated keys are measured, not built.

    The measure visits each composed node once, whatever shares it: at most two child
    lists for each node, and so at most two for each byte. Nothing is built, so no
    expansion happens and none reaches the reason.
    """

    text = OVER_BUDGET_SHAPES[shape]
    child_lists = 0
    children = frontmatter_yaml._children

    def counting(node: Any) -> Any:
        nonlocal child_lists
        child_lists += 1
        return children(node)

    monkeypatch.setattr(frontmatter_yaml, "_children", counting)
    builds = Mock(side_effect=AssertionError("the builder ran on a document past the budget"))
    monkeypatch.setattr(frontmatter_yaml._Builder, "value", builds)

    with pytest.raises(FrontmatterError, match=REFUSED) as refused:
        load_frontmatter_yaml(text)

    assert 0 < child_lists <= 2 * len(text)
    assert len(str(refused.value)) <= YAML_ERROR_MAX_CHARS


@pytest.mark.parametrize("mapping", [False, True], ids=["sequence", "mapping"])
@pytest.mark.parametrize(
    "tag",
    [
        *sorted(str(tag) for tag in ruamel_constructor.SafeConstructor.yaml_constructors if tag),
        "!x",
    ],
)
@pytest.mark.usefixtures("no_ruamel_collections")
def test_ruamel_never_writes_a_node_into_a_message(
    tag: str, mapping: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every tag the safe constructor knows, on a collection of one long-tagged alias.

    Review C, C1: ruamel's timestamp reader wrote the composed nodes, tags and all, into
    its message. A node is never written out here, whichever tag a collection carries,
    and the reason stays within its bound.
    """

    writes = 0
    node_repr = ruamel_nodes.Node.__repr__

    def counting(node: Any) -> str:
        nonlocal writes
        writes += 1
        return node_repr(node)

    monkeypatch.setattr(ruamel_nodes.Node, "__repr__", counting)
    text = long_tag_under_a_collection_tag(tag, 1_000, 1_000, mapping=mapping)

    try:
        load_frontmatter_yaml(text)
    except FrontmatterError as refused:
        assert len(str(refused)) <= YAML_ERROR_MAX_CHARS
        assert "ttttt" not in str(refused)

    assert writes == 0


@pytest.mark.usefixtures("no_ruamel_collections")
def test_nested_inline_merges_are_built_once_whatever_their_depth() -> None:
    """Review C, C2: 60 inline merge levels, each anchored, around 330,000 merged entries.

    A mapping reached twice through merges adds nothing the second time, so the value
    is one entry and the load holds a few megabytes, where ruamel's copies at each
    level held hundreds. Past YAML_MAX_DEPTH the nesting is refused before it is built.
    """

    text = nested_inline_merges(60)
    tracemalloc.start()
    try:
        parsed = load_frontmatter_yaml(text)
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert parsed == {"c": {"": ""}, "d": {"": ""}, "x": {"": ""}}
    assert peak < 32 * 1024 * 1024

    with pytest.raises(FrontmatterError, match=TOO_DEEP):
        load_frontmatter_yaml(nested_inline_merges(400))


@pytest.mark.usefixtures("no_ruamel_collections")
def test_merge_keys_take_ruamels_values_and_order() -> None:
    """A mapping's own keys win; an earlier merged mapping wins over a later one, and a
    merged mapping's own keys over those it merges. The keys come in ruamel's order: the
    merged ones first, the last named first, then the mapping's own (ruamel 0.19.1
    answers each of these the same, keys in the same order).
    """

    parsed = load_frontmatter_yaml(
        "a: &a {x: a, y: a}\n"
        "b: &b {y: b, z: b, w: b}\n"
        "c: &c {<<: *a, x: c}\n"
        "m: {<<: [*c, *b, *a], z: own}\n"
        "n: {<<: [*a, *b, *a]}\n"
    )

    assert isinstance(parsed, dict)
    assert list(parsed["c"].items()) == [("x", "c"), ("y", "a")]
    assert list(parsed["m"].items()) == [("x", "c"), ("y", "a"), ("z", "own"), ("w", "b")]
    assert list(parsed["n"].items()) == [("x", "a"), ("y", "a"), ("z", "b"), ("w", "b")]


@pytest.mark.usefixtures("no_ruamel_collections")
def test_nesting_is_refused_past_its_bound_before_the_scanner_pays_for_it() -> None:
    """Review C, C3: 400 flow levels on one line cost ruamel's scanner 53 us a byte.

    The composer stops at YAML_MAX_DEPTH, so the deepest shape is refused at once, and
    nesting up to the bound still loads.
    """

    with pytest.raises(FrontmatterError, match=TOO_DEEP):
        load_frontmatter_yaml(flow_sawtooth(400, 8_192))

    # The mapping is one level, and the scalar inside the sequences is one more.
    sequences = YAML_MAX_DEPTH - 2
    expected: object = "a"
    for _level in range(sequences):
        expected = [expected]
    assert load_frontmatter_yaml("x: " + "[" * sequences + "a" + "]" * sequences) == {"x": expected}
    with pytest.raises(FrontmatterError, match=TOO_DEEP):
        load_frontmatter_yaml("x: " + "[" * (sequences + 1) + "a" + "]" * (sequences + 1))


def test_a_shared_anchor_within_the_bound_is_written_out_as_a_plain_tree() -> None:
    parsed = load_frontmatter_yaml(
        "author: &me {name: Ada, tags: [math, engines]}\n"
        "reviewer: *me\n"
        "defaults: &d {draft: false}\n"
        "page:\n  <<: *d\n  title: Notes\n"
    )

    assert parsed == {
        "author": {"name": "Ada", "tags": ["math", "engines"]},
        "reviewer": {"name": "Ada", "tags": ["math", "engines"]},
        "defaults": {"draft": False},
        "page": {"draft": False, "title": "Notes"},
    }
    assert isinstance(parsed, dict)
    # Written out: no reference is shared, so no later walk can multiply.
    assert parsed["author"] is not parsed["reviewer"]
    assert parsed["author"]["tags"] is not parsed["reviewer"]["tags"]


def test_merge_keys_within_the_bound_still_merge() -> None:
    parsed = load_frontmatter_yaml(merged_into_many(20, 30).removeprefix(OVER_BUDGET))

    assert isinstance(parsed, dict)
    assert len(parsed["items"]) == 30
    assert all(item == parsed["b"] for item in parsed["items"])
    assert len(parsed["b"]) == 20


@pytest.mark.parametrize(
    "text", ["loop: &a [*a]\n", "loop: &a {self: *a}\n", "loop: &a {<<: *a}\n"]
)
def test_an_alias_inside_its_own_anchor_is_refused(text: str) -> None:
    with pytest.raises(FrontmatterError, match="refers to a value that contains it"):
        load_frontmatter_yaml(text)


def test_nesting_too_deep_for_the_parser_is_refused_not_raised() -> None:
    assert load_frontmatter_yaml("x: " + "[" * 50 + "]" * 50 + "\n") is not None

    with pytest.raises(FrontmatterError, match=TOO_DEEP):
        load_frontmatter_yaml("x: " + "[" * 5_000 + "]" * 5_000 + "\n")


def test_text_past_the_byte_bound_is_refused_before_parsing() -> None:
    with pytest.raises(FrontmatterError, match="longer than 256 KiB"):
        load_frontmatter_yaml("x: " + "y" * FRONTMATTER_MAX_BYTES + "\n")


def _built_size(text: str) -> int:
    yaml = frontmatter_yaml._new_yaml(FRONTMATTER_MAX_EXPANDED_SIZE, keep_last=False)
    node = yaml.compose(text)
    builder = frontmatter_yaml._Builder(
        yaml.constructor, FRONTMATTER_MAX_EXPANDED_SIZE, keep_last=False
    )
    builder.value(node)
    return FRONTMATTER_MAX_EXPANDED_SIZE - builder.remaining


def test_the_densest_alias_free_front_matter_at_the_byte_bound_is_accepted() -> None:
    """The densest alias-free shape found writes out to 3.8 times its bytes.

    Each ``1e15`` is five bytes of a flow list and ``1000000000000000.0`` once built,
    with one for the node. The expansion bound is four times the byte bound, so front
    matter with no aliases is not refused by it even at the byte bound.
    """

    count = (FRONTMATTER_MAX_BYTES - len("x: []\n")) // len("1e15,")
    text = "x: [" + ",".join(["1e15"] * count) + "]\n"
    assert FRONTMATTER_MAX_BYTES - len(text) < len("1e15,")

    assert load_frontmatter_yaml(text) == {"x": [1e15] * count}
    expanded = _built_size(text)
    assert expanded / len(text) > 3.79
    assert expanded <= FRONTMATTER_MAX_EXPANDED_SIZE


def test_tags_json_has_no_type_for_are_answered_as_json_safe_values() -> None:
    parsed = load_frontmatter_yaml(NON_JSON_SAFE)

    assert isinstance(parsed, dict)
    huge = parsed.pop("huge")
    assert parsed == {
        "binary": "aGVsbG8=",
        "set": ["a", "b"],
        "omap": {"first": 1, "second": 2},
        "pairs": [["a", 1], ["a", 2]],
        "nan": ".nan",
        "inf": ".inf",
        "negative_inf": "-.inf",
        "date": "2026-11-17",
        "stamp": "2026-11-17T10:00:00",
        '["a", "b"]': "tuple key",
        "2026-11-17": "date key",
        "1": "int key",
        "2.5": "float key",
        "null": "null key",
    }
    # Past Python's decimal digit limit, which the JSON encoder would refuse.
    assert huge == "0x" + "f" * 4_000
    # What every consumer does with it: the response encoder, and a sorted cache key.
    json.dumps(parsed, allow_nan=False, sort_keys=True)


def test_keys_are_compared_by_their_json_text() -> None:
    """``1`` and ``"1"`` are one key, as JSON sees them; ``1`` and ``true`` are two.

    Comparing text also keeps a mapping's build linear in integer keys chosen to share
    one hash (review C, C4): a string's hash is seeded.
    """

    assert load_frontmatter_yaml("1: one\ntrue: yes\n") == {"1": "one", "true": "yes"}
    with pytest.raises(FrontmatterError, match="line 2: a key appears twice in one mapping"):
        load_frontmatter_yaml("1: one\n'1': quoted\n")


def test_an_integer_within_the_decimal_digit_limit_stays_a_number() -> None:
    parsed = load_frontmatter_yaml("x: " + "9" * 4_000 + "\n")

    assert parsed == {"x": int("9" * 4_000)}
    assert json.dumps(parsed) == '{"x": ' + "9" * 4_000 + "}"


def test_lone_surrogates_from_escapes_are_replaced_so_the_answer_encodes() -> None:
    parsed = load_frontmatter_yaml(SURROGATES)

    assert parsed == {"x": "\ufffd", "\ufffd": 1, "pair": "\U0001f600"}
    json.dumps(parsed, ensure_ascii=False).encode()


@pytest.mark.parametrize("case", CONSTRUCTOR_FAILURES)
def test_a_scalar_or_tag_the_loader_does_not_read_is_a_front_matter_error(case: str) -> None:
    text, reason = CONSTRUCTOR_FAILURES[case]

    with pytest.raises(FrontmatterError) as refused:
        load_frontmatter_yaml(text)

    assert str(refused.value).startswith(f"Error parsing YAML metadata: {reason}")


def test_a_duplicated_key_names_its_line_and_never_its_values() -> None:
    big = "y" * 10_000
    text = f"s: &s {big}\nd: *s\nd: *s\n"

    with pytest.raises(FrontmatterError, match="line 3: a key appears twice") as refused:
        load_frontmatter_yaml(text)

    assert big[:100] not in str(refused.value)
    assert len(str(refused.value)) <= YAML_ERROR_MAX_CHARS


def test_a_reason_that_quotes_the_document_is_cut_to_its_bound() -> None:
    with pytest.raises(FrontmatterError, match="found undefined alias") as refused:
        load_frontmatter_yaml("a: *" + "t" * 200_000 + "\n")

    assert len(str(refused.value)) == YAML_ERROR_MAX_CHARS
    assert str(refused.value).endswith("\u2026")


def test_only_yaml_1_2_is_read() -> None:
    """A `%YAML 1.1` directive would bring back 1.1's booleans, octals, and sexagesimals
    (review C, C5), and with them a parse superlinear in its text."""

    with pytest.raises(FrontmatterError, match="declares YAML 1.1, and only YAML 1.2"):
        load_frontmatter_yaml("%YAML 1.1\n--- # x\non: 1\nmode: 0755\n")
    assert load_frontmatter_yaml("%YAML 1.2\n--- # x\non: 1\nmode: 0755\n") == {
        "on": 1,
        "mode": 755,
    }


def test_untrusted_front_matter_writes_no_warning(capsys: pytest.CaptureFixture[str]) -> None:
    """ruamel warns on each reused anchor, and under YAML 1.1 on an exponent without a dot.

    Each message quotes the author's text, and Python keeps every distinct one for the
    life of the process, so the loader must not raise them at all.
    """

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        for index in range(20):
            assert load_frontmatter_yaml(f"k{index}: &a 1\nv{index}: &a 2\n") is not None
        with pytest.raises(FrontmatterError, match="declares YAML 1.1"):
            load_frontmatter_yaml("%YAML 1.1\n--- # x\na: 1e3\n")

    assert caught == []
    assert capsys.readouterr().err == ""


def test_a_scalar_the_safe_loader_never_builds_is_named_not_stringified() -> None:
    class Opaque:
        def __str__(self) -> str:
            raise AssertionError("str() of an unknown value is unbounded")

    assert frontmatter_yaml._json_scalar(Opaque()) == ("<Opaque>", len("<Opaque>"))


@pytest.mark.usefixtures("no_ruamel_collections")
def test_the_yaml_prefix_predicate_refuses_a_merge_bomb_before_building_it() -> None:
    """The classifier's `.yaml` prefix parses through the same bound (review A, A2)."""

    assert yaml_mapping_from_bytes(merge_bomb(12).encode()) is None
    assert yaml_mapping_from_bytes(OVER_BUDGET_SHAPES["alias-12"].encode()) is None
    assert yaml_mapping_from_bytes(b"x: !!bool maybe\n") is None
    assert yaml_mapping_from_bytes(("x: " + "[" * 5_000).encode()) is None
    assert yaml_mapping_from_bytes(b"spec: Bundle/0.1\n1: one\non: yes\n") == {
        "spec": "Bundle/0.1",
        "1": "one",
        "on": "yes",
    }


@pytest.mark.usefixtures("no_ruamel_collections")
def test_the_yaml_prefix_keeps_a_duplicated_keys_last_value_and_reads_only_1_2() -> None:
    """Review C, C5: most YAML tools keep a repeated key's last value, so a file can carry
    one unnoticed; the predicate does too, where front matter refuses it."""

    assert yaml_mapping_from_bytes(b"a: 1\nb: 2\na: 3\n") == {"a": 3, "b": 2}
    assert yaml_mapping_from_bytes(b"%YAML 1.1\n--- # x\non: 1\n") is None


def _rule(match: KindMatch) -> CompiledKindRule:
    return CompiledKindRule(
        rule=KindRule(id="keyed", match=match), plugin_name="keyed", discovery_index=0
    )


def test_a_key_predicate_matches_a_non_string_key_by_its_json_text(tmp_path: Path) -> None:
    markdown = tmp_path / "note.md"
    markdown.write_text("---\n1: one\n---\nbody\n", encoding="utf-8")
    listing = tmp_path / "list.yaml"
    listing.write_text("2: two\ntrue: yes\n", encoding="utf-8")

    by_frontmatter = build_classifier([_rule(KindMatch(ext=".md", frontmatter_has_key="1"))])
    by_yaml = build_classifier([_rule(KindMatch(ext=".yaml", yaml_has_key="true"))])

    assert by_frontmatter(FileContext(markdown, ".md")) == "keyed"
    assert by_yaml(FileContext(listing, ".yaml")) == "keyed"


class _FakeQuery:
    def __init__(self, params: dict[str, str]) -> None:
        self._params = params

    def get(self, key: str, default: str = "") -> str:
        return self._params.get(key, default)


def _request(**params: str) -> Any:
    request = Mock(spec=["query_params", "headers", "method", "path_params"])
    request.query_params = _FakeQuery(params)
    request.headers = {}
    request.method = "GET"
    request.path_params = {}
    return request


def _body(response: Any) -> dict[str, Any]:
    return json.loads(bytes(response.body))


def _write_markdown(path: Path, frontmatter: str) -> None:
    path.write_text(f"---\n{frontmatter}---\n\n# Body\n\ntext\n", encoding="utf-8")


@pytest.fixture
def parse_threads(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """The thread each front-matter parse ran on."""

    threads: list[int] = []
    load = frontmatter_yaml._load

    def recording(*args: Any, **kwargs: Any) -> object:
        threads.append(threading.get_ident())
        return load(*args, **kwargs)

    monkeypatch.setattr(frontmatter_yaml, "_load", recording)
    return threads


@pytest.mark.parametrize("shape", ["alias-7", "alias-12", "merge-12", "duplicate-key-12"])
@pytest.mark.usefixtures("no_ruamel_collections")
def test_api_file_answers_a_bomb_as_text_with_the_reason_and_keeps_answering(
    shape: str, tmp_path: Path, parse_threads: list[int]
) -> None:
    server._set_root_dir(tmp_path)
    _write_markdown(tmp_path / "bomb.md", OVER_BUDGET_SHAPES[shape])
    _write_markdown(tmp_path / "plain.md", "title: Plain\n")

    async def _run() -> tuple[int, Any, Any]:
        loop_thread = threading.get_ident()
        bomb, plain = await asyncio.gather(
            server.api_file(_request(path="bomb.md")),
            server.api_file(_request(path="plain.md")),
        )
        return loop_thread, bomb, plain

    loop_thread, bomb, plain = asyncio.run(_run())

    assert bomb.status_code == 200
    body = _body(bomb)
    assert (body["type"], body["kind"]) == ("text", "markdown")
    assert body["content"].startswith("---\n" + OVER_BUDGET)
    assert "frontmatter" not in body
    assert REFUSED in body["frontmatter_error"]
    assert len(bomb.body) < 4_096
    assert _body(plain)["frontmatter"] == {"title": "Plain"}
    assert parse_threads and loop_thread not in parse_threads


def test_api_file_answers_tags_json_has_no_type_for(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    _write_markdown(tmp_path / "odd.md", NON_JSON_SAFE)

    body = _body(asyncio.run(server.api_file(_request(path="odd.md"))))

    assert body["type"] == "text"
    assert "frontmatter_error" not in body
    assert body["frontmatter"]["set"] == ["a", "b"]
    assert body["frontmatter"]["nan"] == ".nan"
    assert body["frontmatter"]['["a", "b"]'] == "tuple key"


@pytest.mark.parametrize("case", ["bool", "int", "timestamp", "omap", "timestamp-sequence"])
def test_api_file_and_render_answer_a_scalar_or_tag_the_loader_does_not_read(
    case: str, tmp_path: Path
) -> None:
    text, reason = CONSTRUCTOR_FAILURES[case]
    set_capabilities(Capabilities(active_content=False, mutations=False))
    server._set_root_dir(tmp_path)
    _write_markdown(tmp_path / "odd.md", text)

    async def _run() -> tuple[Any, Any]:
        return (
            await server.api_file(_request(path="odd.md")),
            await server.api_kpress_render(_request(path="odd.md", view="rendered")),
        )

    answered, rendered = asyncio.run(_run())

    body = _body(answered)
    assert (answered.status_code, body["type"]) == (200, "text")
    assert body["frontmatter_error"].startswith(f"Error parsing YAML metadata: {reason}")
    assert rendered.status_code == 200
    reasons = [
        item["message"]
        for item in _body(rendered)["diagnostics"]
        if item["type"] == "frontmatter_error"
    ]
    assert reasons == [body["frontmatter_error"]]


def test_api_file_answers_front_matter_with_lone_surrogates(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    _write_markdown(tmp_path / "escaped.md", SURROGATES)

    response = asyncio.run(server.api_file(_request(path="escaped.md")))

    assert response.status_code == 200
    assert _body(response)["frontmatter"] == {"x": "\ufffd", "\ufffd": 1, "pair": "\U0001f600"}


def test_a_compressed_bomb_is_refused_like_a_plain_one(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    with gzip.open(tmp_path / "bomb.md.gz", "wt", encoding="utf-8") as fh:
        fh.write(f"---\n{alias_bomb(7)}---\nbody\n")

    body = _body(asyncio.run(server.api_file(_request(path="bomb.md.gz"))))

    assert body["type"] == "text"
    assert "frontmatter" not in body
    assert REFUSED in body["frontmatter_error"]


@pytest.mark.parametrize("name", ["long.md", "long.md.gz"])
def test_an_unclosed_fence_past_the_byte_bound_names_the_bound(tmp_path: Path, name: str) -> None:
    text = "---\n" + "key: value\n" * (FRONTMATTER_MAX_BYTES // 8)
    path = tmp_path / name
    if name.endswith(".gz"):
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            fh.write(text)
    else:
        path.write_text(text, encoding="utf-8")

    ctx = FileContext(path, ".md")

    assert ctx.frontmatter is None
    assert ctx.frontmatter_parse_error == (
        "Front matter not parsed: its closing delimiter is not within the first 256 KiB"
    )


@pytest.mark.parametrize("name", ["wide.md", "wide.md.gz"])
def test_a_first_line_past_the_byte_bound_is_no_front_matter(tmp_path: Path, name: str) -> None:
    text = "x" * (FRONTMATTER_MAX_BYTES + 50_000)
    path = tmp_path / name
    if name.endswith(".gz"):
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            fh.write(text)
    else:
        path.write_text(text, encoding="utf-8")

    ctx = FileContext(path, ".md")

    assert ctx.frontmatter is None
    assert ctx.frontmatter_parse_error is None


def test_an_unclosed_compressed_fence_within_the_bound_names_no_path(tmp_path: Path) -> None:
    path = tmp_path / "short.md.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write("---\ntitle: never closed\n")

    ctx = FileContext(path, ".md")

    assert ctx.frontmatter is None
    assert ctx.frontmatter_parse_error == "Delimiter `---` for end of frontmatter not found"


def test_invalid_utf8_after_the_front_matter_does_not_hide_it(tmp_path: Path) -> None:
    path = tmp_path / "latin.md"
    head = "---\ntitle: Zürich\n---\n".encode()
    path.write_bytes(head + "body in Latin-1: Zürich\n".encode("latin-1"))

    assert FileContext(path, ".md").frontmatter == {"title": "Zürich"}


@pytest.mark.parametrize("shape", ["alias-12", "merge-12", "duplicate-key-12"])
@pytest.mark.usefixtures("no_ruamel_collections")
def test_untrusted_render_of_a_bomb_reports_the_reason_and_renders_the_body(
    shape: str, tmp_path: Path, parse_threads: list[int]
) -> None:
    set_capabilities(Capabilities(active_content=False, mutations=False))
    server._set_root_dir(tmp_path)
    _write_markdown(tmp_path / "bomb.md", OVER_BUDGET_SHAPES[shape])

    async def _run() -> tuple[int, Any]:
        loop_thread = threading.get_ident()
        response = await server.api_kpress_render(_request(path="bomb.md", view="rendered"))
        return loop_thread, response

    loop_thread, response = asyncio.run(_run())

    assert response.status_code == 200
    # The rendered page is about 13 KB; an expansion would be megabytes.
    assert len(response.body) < 65_536
    body = _body(response)
    assert body["inert"] is True
    assert "Body" in body["html"]
    assert "lol" not in body["html"]
    errors = [item for item in body["diagnostics"] if item["type"] == "frontmatter_error"]
    assert len(errors) == 1
    assert REFUSED in errors[0]["message"]
    assert parse_threads and loop_thread not in parse_threads


def test_a_git_blob_prefix_that_never_closes_its_fence_names_the_bound() -> None:
    from metabrowser.plugin_loader.classify import parse_frontmatter_bytes

    unclosed = b"---\n" + b"key: value\n" * (FRONTMATTER_MAX_BYTES // 8)

    assert parse_frontmatter_bytes(unclosed) == (
        None,
        "Front matter not parsed: its closing delimiter is not within the first 256 KiB",
    )
    assert parse_frontmatter_bytes(b"---\nkey: value\n") == (
        None,
        "Delimiter `---` for end of frontmatter not found",
    )
