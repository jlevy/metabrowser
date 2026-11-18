"""Front matter is parsed under bounds, off the event loop, and never fails a request.

YAML aliases let a few hundred bytes of front matter stand for millions of values.
:mod:`metabrowser.frontmatter_yaml` measures the composed document before constructing
it, refuses front matter whose written-out size passes ``FRONTMATTER_MAX_EXPANDED_SIZE``,
and answers tags JSON has no type for as JSON-safe values. These tests pin the outcome
on every path a served folder reaches -- the loader, ``/api/file``, and
``/api/kpress/render`` under the untrusted profile -- and bound the work by counting it
rather than timing it: a document past the budget never reaches a YAML constructor.
The pinned-revision path is in ``tests/test_git_revision_content_routes.py``.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import string
import threading
import warnings
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
import yaml as pyyaml
from ruamel.yaml import constructor as ruamel_constructor

from metabrowser import frontmatter_yaml, server
from metabrowser.capabilities import Capabilities, set_capabilities
from metabrowser.file_kinds import FileContext
from metabrowser.frontmatter_yaml import (
    FRONTMATTER_MAX_BYTES,
    FRONTMATTER_MAX_EXPANDED_SIZE,
    YAML_ERROR_MAX_CHARS,
    FrontmatterError,
    json_safe_frontmatter,
    load_frontmatter_yaml,
)
from metabrowser.plugin_loader.classify import (
    CompiledKindRule,
    build_classifier,
    yaml_mapping_from_bytes,
)
from metabrowser.plugin_loader.manifest import KindMatch, KindRule

REFUSED = "without its YAML aliases"

# A comment the shapes past the budget carry, so `constructor_guard` can tell them from
# the front matter a test expects to be built.
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

    ruamel's constructor copies every merged entry into the merging mapping, so the
    last holds width**(levels - 1) entries before any walk of the value.
    """

    names = string.ascii_lowercase
    lines = [f"{names[0]}: &{names[0]} {{k: v}}"]
    for level in range(1, levels):
        refs = ", ".join([f"*{names[level - 1]}"] * width)
        lines.append(f"{names[level]}: &{names[level]} {{<<: [{refs}]}}")
    return OVER_BUDGET + "\n".join(lines) + "\n"


def duplicate_key_bomb(levels: int) -> str:
    """An alias bomb and a key repeated with it as the value (review B, B1).

    ruamel writes both values of a duplicated key into its error message.
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
    """A key of *aliases* aliases to one string, used twice: the message names the key."""

    refs = ", ".join(["*s"] * aliases)
    return OVER_BUDGET + f"s: &s {'y' * length}\nz:\n  ? [{refs}]\n  : 1\n  ? [{refs}]\n  : 2\n"


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

# Front matter ruamel's constructors fail on with an exception that is not a YAMLError.
CONSTRUCTOR_FAILURES = {
    "bool": ("x: !!bool maybe\n", "KeyError"),
    "int": ("x: !!int ''\n", "IndexError"),
    "timestamp": ("when: 9999-12-31T23:59:59.9999999999Z\n", "OverflowError"),
    "omap": ("x: !!omap [a: 1, a: 2]\n", "AssertionError"),
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


def guard_constructors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail at once if a YAML constructor starts on a document marked OVER_BUDGET.

    The bound is that the constructor never runs on such a document, so this checks it
    directly; and where it would run, it stops a merge bomb that would otherwise take
    hours. Both ruamel's and PyYAML's constructors are guarded.
    """

    for base in (ruamel_constructor.BaseConstructor, pyyaml.constructor.BaseConstructor):
        original = base.construct_document

        def guarded(self: Any, node: Any, original: Any = original) -> Any:
            if OVER_BUDGET in getattr(node.start_mark, "buffer", ""):
                raise AssertionError("a YAML constructor ran on a document past the budget")
            return original(self, node)

        monkeypatch.setattr(base, "construct_document", guarded)


@pytest.fixture
def constructor_guard(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    guard_constructors(monkeypatch)
    yield


def test_the_seven_level_bomb_from_the_report_is_refused() -> None:
    text = alias_bomb(7)
    assert len(text) == 310

    with pytest.raises(FrontmatterError, match=REFUSED) as refused:
        load_frontmatter_yaml(text)

    assert f"{FRONTMATTER_MAX_EXPANDED_SIZE:,} characters" in str(refused.value)


@pytest.mark.parametrize("shape", OVER_BUDGET_SHAPES)
@pytest.mark.usefixtures("constructor_guard")
def test_a_document_past_the_budget_is_refused_before_it_is_constructed(
    shape: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Aliases, merge keys, sequence keys, and duplicated keys are measured, not built.

    The measure visits each composed node once, whatever shares it: at most two child
    lists for each node, and so at most two for each byte. No constructor and no copy
    runs, so no expansion happens and none reaches the reason.
    """

    text = OVER_BUDGET_SHAPES[shape]
    child_lists = 0
    children = frontmatter_yaml._children

    def counting(node: Any) -> Any:
        nonlocal child_lists
        child_lists += 1
        return children(node)

    monkeypatch.setattr(frontmatter_yaml, "_children", counting)
    copies = Mock(side_effect=AssertionError("the copy ran on a document past the budget"))
    monkeypatch.setattr(frontmatter_yaml._Walk, "value", copies)

    with pytest.raises(FrontmatterError, match=REFUSED) as refused:
        load_frontmatter_yaml(text)

    assert 0 < child_lists <= 2 * len(text)
    assert len(str(refused.value)) <= YAML_ERROR_MAX_CHARS


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
    assert load_frontmatter_yaml("x: " + "[" * 100 + "]" * 100 + "\n") is not None

    with pytest.raises(FrontmatterError, match="nests too deeply"):
        load_frontmatter_yaml("x: " + "[" * 5_000 + "]" * 5_000 + "\n")


def test_text_past_the_byte_bound_is_refused_before_parsing() -> None:
    with pytest.raises(FrontmatterError, match="longer than 256 KiB"):
        load_frontmatter_yaml("x: " + "y" * FRONTMATTER_MAX_BYTES + "\n")


def test_the_densest_alias_free_front_matter_at_the_byte_bound_is_accepted() -> None:
    """The densest alias-free shape found writes out to 3.85 times its bytes.

    Each flow mapping holds the keys ``1e15`` to ``9e15`` with no values: five bytes of
    YAML a key, and twenty in the copy (``1000000000000000.0`` and a null). The family's
    limit is four, and the expansion bound is four times the byte bound, so front
    matter with no aliases is not refused by it even at the byte bound.
    """

    item = "{" + ",".join(f"{digit}e15" for digit in range(1, 10)) + "}"
    count = (FRONTMATTER_MAX_BYTES - len("x: []\n")) // (len(item) + 1)
    text = "x: [" + ",".join([item] * count) + "]\n"
    assert FRONTMATTER_MAX_BYTES - len(text) < len(item) + 1

    parsed = load_frontmatter_yaml(text)

    walk = frontmatter_yaml._Walk(FRONTMATTER_MAX_EXPANDED_SIZE)
    walk.value(parsed)
    expanded = FRONTMATTER_MAX_EXPANDED_SIZE - walk._remaining
    assert expanded / len(text) > 3.8
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


def test_an_integer_within_the_decimal_digit_limit_stays_a_number() -> None:
    parsed = load_frontmatter_yaml("x: " + "9" * 4_000 + "\n")

    assert parsed == {"x": int("9" * 4_000)}
    assert json.dumps(parsed) == '{"x": ' + "9" * 4_000 + "}"


def test_lone_surrogates_from_escapes_are_replaced_so_the_answer_encodes() -> None:
    parsed = load_frontmatter_yaml(SURROGATES)

    assert parsed == {"x": "\ufffd", "\ufffd": 1, "pair": "\U0001f600"}
    json.dumps(parsed, ensure_ascii=False).encode()


@pytest.mark.parametrize("case", CONSTRUCTOR_FAILURES)
def test_a_constructor_failure_of_any_type_is_a_front_matter_error(case: str) -> None:
    text, raised = CONSTRUCTOR_FAILURES[case]

    with pytest.raises(FrontmatterError, match=f"^Error parsing YAML metadata: {raised}"):
        load_frontmatter_yaml(text)


def test_a_duplicated_key_names_the_key_and_never_its_values() -> None:
    big = "y" * 10_000
    text = f"s: &s {big}\nd: *s\nd: *s\n"

    with pytest.raises(FrontmatterError, match='found duplicate key "d"') as refused:
        load_frontmatter_yaml(text)

    assert big[:100] not in str(refused.value)
    assert len(str(refused.value)) <= YAML_ERROR_MAX_CHARS


def test_a_reason_that_quotes_the_document_is_cut_to_its_bound() -> None:
    with pytest.raises(FrontmatterError, match="could not determine a constructor") as refused:
        load_frontmatter_yaml("a: !" + "t" * 200_000 + " 1\n")

    assert len(str(refused.value)) == YAML_ERROR_MAX_CHARS
    assert str(refused.value).endswith("\u2026")


def test_untrusted_front_matter_writes_no_warning(capsys: pytest.CaptureFixture[str]) -> None:
    """ruamel warns on each reused anchor and on a YAML 1.1 exponent without a dot.

    Each message quotes the author's text, and Python keeps every distinct one for the
    life of the process, so the loader must not raise them at all.
    """

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        for index in range(20):
            assert load_frontmatter_yaml(f"k{index}: &a 1\nv{index}: &a 2\n") is not None
        parsed = load_frontmatter_yaml("%YAML 1.1\n--- # x\na: 1e3\nb: -2E2\n")

    assert parsed == {"a": 1000.0, "b": -200.0}
    assert caught == []
    assert capsys.readouterr().err == ""


def test_a_value_the_safe_loader_never_builds_is_named_not_stringified() -> None:
    class Opaque:
        def __str__(self) -> str:
            raise AssertionError("str() of an unknown value is unbounded")

    assert json_safe_frontmatter({"x": Opaque()}) == {"x": "<Opaque>"}


@pytest.mark.usefixtures("constructor_guard")
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

    def recording(*args: Any) -> object:
        threads.append(threading.get_ident())
        return load(*args)

    monkeypatch.setattr(frontmatter_yaml, "_load", recording)
    return threads


@pytest.mark.parametrize("shape", ["alias-7", "alias-12", "merge-12", "duplicate-key-12"])
@pytest.mark.usefixtures("constructor_guard")
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


@pytest.mark.parametrize("case", ["bool", "int", "timestamp", "omap"])
def test_api_file_and_render_answer_a_constructor_failure_with_its_reason(
    case: str, tmp_path: Path
) -> None:
    text, raised = CONSTRUCTOR_FAILURES[case]
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
    assert body["frontmatter_error"].startswith(f"Error parsing YAML metadata: {raised}")
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
@pytest.mark.usefixtures("constructor_guard")
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
