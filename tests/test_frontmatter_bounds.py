"""Front matter is parsed under bounds, off the event loop, and never fails a request.

YAML aliases let a few hundred bytes of front matter stand for millions of values.
:mod:`metabrowser.frontmatter_yaml` refuses front matter whose written-out size passes
``FRONTMATTER_MAX_EXPANDED_SIZE``, and answers tags JSON has no type for as JSON-safe
values. These tests pin the outcome on every path a served folder reaches -- the
loader, ``/api/file``, and ``/api/kpress/render`` under the untrusted profile -- and
bound the work by counting it rather than timing it. The pinned-revision path is in
``tests/test_git_revision_content_routes.py``.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import string
import threading
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from metabrowser import frontmatter_yaml, server
from metabrowser.capabilities import Capabilities, set_capabilities
from metabrowser.file_kinds import FileContext
from metabrowser.frontmatter_yaml import (
    FRONTMATTER_MAX_BYTES,
    FRONTMATTER_MAX_EXPANDED_SIZE,
    FrontmatterError,
    json_safe_frontmatter,
    load_frontmatter_yaml,
)


def alias_bomb(levels: int, width: int = 9) -> str:
    """*levels* anchors, each a list of *width* aliases to the one before: width**levels values."""

    names = string.ascii_lowercase
    lines = [f"{names[0]}: &{names[0]} [{', '.join(['lol'] * width)}]"]
    for level in range(1, levels):
        refs = ", ".join([f"*{names[level - 1]}"] * width)
        lines.append(f"{names[level]}: &{names[level]} [{refs}]")
    return "\n".join(lines) + "\n"


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


def test_the_seven_level_bomb_from_the_report_is_refused() -> None:
    text = alias_bomb(7)
    assert len(text) == 310

    with pytest.raises(FrontmatterError, match="without its YAML aliases") as refused:
        load_frontmatter_yaml(text)

    assert f"{FRONTMATTER_MAX_EXPANDED_SIZE:,} characters" in str(refused.value)


@pytest.mark.parametrize("levels", [7, 12])
def test_an_alias_bomb_is_refused_after_bounded_work(
    levels: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The walk visits at most one node per character of budget, at any depth.

    Twelve levels are 9**12 values written out, 3,600 times the seven the report used;
    the walk stops at the same place for both.
    """

    visits = 0
    visit = frontmatter_yaml._Walk.value

    def counting(walk: Any, value: object) -> object:
        nonlocal visits
        visits += 1
        return visit(walk, value)

    monkeypatch.setattr(frontmatter_yaml._Walk, "value", counting)

    with pytest.raises(FrontmatterError, match="without its YAML aliases"):
        load_frontmatter_yaml(alias_bomb(levels))

    assert 0 < visits <= FRONTMATTER_MAX_EXPANDED_SIZE + 1


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


@pytest.mark.parametrize("text", ["loop: &a [*a]\n", "loop: &a {self: *a}\n"])
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


def test_no_alias_free_front_matter_within_the_byte_bound_passes_the_expansion_bound() -> None:
    """The densest alias-free shape the benchmark found writes out to 3.8x its bytes.

    ``1e15`` is five bytes in a flow list and ``1000000000000000.0`` in JSON. The
    expansion bound is four times the byte bound, so front matter with no aliases is
    never refused by it.
    """

    text = "x: [" + ",".join(["1e15"] * 1_000) + "]\n"
    walk = frontmatter_yaml._Walk(FRONTMATTER_MAX_EXPANDED_SIZE)
    walk.value(load_frontmatter_yaml(text))
    expanded = FRONTMATTER_MAX_EXPANDED_SIZE - walk._remaining

    assert expanded / len(text) < FRONTMATTER_MAX_EXPANDED_SIZE / FRONTMATTER_MAX_BYTES


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


def test_a_value_the_safe_loader_never_builds_is_named_not_stringified() -> None:
    class Opaque:
        def __str__(self) -> str:
            raise AssertionError("str() of an unknown value is unbounded")

    assert json_safe_frontmatter({"x": Opaque()}) == {"x": "<Opaque>"}


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
    parse = frontmatter_yaml.from_yaml_string

    def recording(text: str) -> object:
        threads.append(threading.get_ident())
        return parse(text)

    monkeypatch.setattr(frontmatter_yaml, "from_yaml_string", recording)
    return threads


@pytest.mark.parametrize("levels", [7, 12])
def test_api_file_answers_a_bomb_as_text_with_the_reason_and_keeps_answering(
    levels: int, tmp_path: Path, parse_threads: list[int]
) -> None:
    server._set_root_dir(tmp_path)
    _write_markdown(tmp_path / "bomb.md", alias_bomb(levels))
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
    assert body["content"].startswith("---\na: &a [lol")
    assert "frontmatter" not in body
    assert "without its YAML aliases" in body["frontmatter_error"]
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


def test_a_compressed_bomb_is_refused_like_a_plain_one(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    with gzip.open(tmp_path / "bomb.md.gz", "wt", encoding="utf-8") as fh:
        fh.write(f"---\n{alias_bomb(7)}---\nbody\n")

    body = _body(asyncio.run(server.api_file(_request(path="bomb.md.gz"))))

    assert body["type"] == "text"
    assert "frontmatter" not in body
    assert "without its YAML aliases" in body["frontmatter_error"]


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


def test_invalid_utf8_after_the_front_matter_does_not_hide_it(tmp_path: Path) -> None:
    path = tmp_path / "latin.md"
    head = "---\ntitle: Zürich\n---\n".encode()
    path.write_bytes(head + "body in Latin-1: Zürich\n".encode("latin-1"))

    assert FileContext(path, ".md").frontmatter == {"title": "Zürich"}


def test_untrusted_render_of_a_bomb_reports_the_reason_and_renders_the_body(
    tmp_path: Path, parse_threads: list[int]
) -> None:
    set_capabilities(Capabilities(active_content=False, mutations=False))
    server._set_root_dir(tmp_path)
    _write_markdown(tmp_path / "bomb.md", alias_bomb(12))

    async def _run() -> tuple[int, Any]:
        loop_thread = threading.get_ident()
        response = await server.api_kpress_render(_request(path="bomb.md", view="rendered"))
        return loop_thread, response

    loop_thread, response = asyncio.run(_run())

    assert response.status_code == 200
    body = _body(response)
    assert body["inert"] is True
    assert "Body" in body["html"]
    assert "lol" not in body["html"]
    errors = [item for item in body["diagnostics"] if item["type"] == "frontmatter_error"]
    assert len(errors) == 1
    assert "without its YAML aliases" in errors[0]["message"]
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
