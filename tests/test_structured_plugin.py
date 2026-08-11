"""Tests for the structured (JSON/YAML) plugin's parser + handler.

Covers:
- Parse + YAML re-serialization round-trip for small JSON / YAML
  fixtures.
- Cache key correctness: invalidates when mtime_hash changes.
- Parse-error reporting: malformed input gets a parse_error string,
  parsed=None, no 5xx.
- Size-limit truncation: files past STRUCTURED_PARSE_MAX_BYTES report
  truncated=True with parsed=None.
- node_count / max_depth shape.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

import metabrowser.builtin_plugins.structured.parser as parser_mod
from metabrowser.builtin_plugins.structured.parser import (
    _count_nodes_and_depth,
    parse_structured,
)


def test_parse_small_json(tmp_path: Path) -> None:
    f = tmp_path / "a.json"
    f.write_text('{"a": 1, "b": [true, false, null]}')
    payload = parse_structured(f, ".json", "h1")
    assert payload.parse_error is None
    assert payload.truncated is False
    assert payload.parsed == {"a": 1, "b": [True, False, None]}
    assert payload.pretty_yaml.strip() != ""
    # YAML output preserves insertion order and uses key: value form.
    assert "a:" in payload.pretty_yaml
    assert payload.node_count > 0
    # Root + 2 children + 3 list items = 6 nodes.
    assert payload.node_count == 6


def test_parse_root_json_null_as_valid_data(tmp_path: Path) -> None:
    f = tmp_path / "null.json"
    f.write_text("null")

    payload = parse_structured(f, ".json", "h-null")

    assert payload.parsed is None
    assert payload.parse_error is None
    assert payload.truncated is False
    assert payload.pretty_yaml.strip().startswith("null")
    assert payload.node_count == 1


def test_parse_jsonc_with_comments_and_trailing_commas(tmp_path: Path) -> None:
    # tsconfig.json et al. are JSONC: // + /* */ comments and trailing
    # commas. Strict json.loads rejects these; the parser falls back to
    # json5 so the tree view still renders.
    f = tmp_path / "tsconfig.json"
    f.write_text(
        """{
          // line comment
          "compilerOptions": {
            "strict": true, /* block comment */
            "paths": {
              "@/*": ["./src/*"],
            },
          },
        }"""
    )
    payload = parse_structured(f, ".json", "h-jsonc")
    assert payload.parse_error is None
    assert payload.parsed == {"compilerOptions": {"strict": True, "paths": {"@/*": ["./src/*"]}}}


def test_parse_small_yaml(tmp_path: Path) -> None:
    f = tmp_path / "a.yaml"
    f.write_text("a: 1\nb:\n  - true\n  - false\n  - null\n")
    payload = parse_structured(f, ".yaml", "h1")
    assert payload.parse_error is None
    assert payload.parsed == {"a": 1, "b": [True, False, None]}


def test_parse_multi_document_yaml_with_trailing_empty_doc(tmp_path: Path) -> None:
    # Generated KB files concatenate YAML documents with `---` and often end
    # with a trailing `---` + comment (an empty document). The single-doc
    # loader raised ComposerError on these, dropping the tree view to plain
    # text. A real document followed by an empty one renders as the document.
    f = tmp_path / "kb.yaml"
    f.write_text("---\nretrieval_kb:\n  count: 3\n---\n# trailing comment only\n")
    payload = parse_structured(f, ".yaml", "h-multi")
    assert payload.parse_error is None
    assert payload.parsed == {"retrieval_kb": {"count": 3}}


def test_parse_multi_document_yaml_multiple_real_docs(tmp_path: Path) -> None:
    # A genuine multi-document stream (e.g. k8s manifests) renders as a list.
    f = tmp_path / "multi.yaml"
    f.write_text("a: 1\n---\nb: 2\n---\nc: 3\n")
    payload = parse_structured(f, ".yaml", "h-multi2")
    assert payload.parse_error is None
    assert payload.parsed == [{"a": 1}, {"b": 2}, {"c": 3}]


def test_parse_error_malformed_yaml(tmp_path: Path) -> None:
    f = tmp_path / "bad.yaml"
    f.write_text("a: 1\n  b: 2\nfoo: [unclosed\n")
    payload = parse_structured(f, ".yaml", "h1")
    assert payload.parse_error is not None
    assert payload.parsed is None
    assert payload.truncated is False


def test_parse_error_malformed_json(tmp_path: Path) -> None:
    f = tmp_path / "bad.json"
    f.write_text('{"a": 1, "b":}')
    payload = parse_structured(f, ".json", "h1")
    assert payload.parse_error is not None
    assert payload.parsed is None


def test_truncated_for_oversize(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:

    monkeypatch.setattr(parser_mod, "STRUCTURED_PARSE_MAX_BYTES", 16)
    # Also drop the LRU cache so the patched cap is observed by the
    # next call (parse_structured's wrapper bakes the limit into the
    # cached function body — we re-read at call time).
    parser_mod._parse_structured_cached.cache_clear()
    f = tmp_path / "big.json"
    f.write_text(json.dumps({"x": "y" * 1024}))
    payload = parse_structured(f, ".json", "h-trunc")
    assert payload.truncated is True
    assert payload.parsed is None
    assert payload.parse_error is None


def test_truncated_gzip_does_not_trust_forged_isize(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(parser_mod, "STRUCTURED_PARSE_MAX_BYTES", 64)
    parser_mod._parse_structured_cached.cache_clear()
    encoded = bytearray(gzip.compress(json.dumps({"value": "x" * 256}).encode()))
    encoded[-4:] = (1).to_bytes(4, "little")
    source = tmp_path / "forged.json.gz"
    source.write_bytes(encoded)

    payload = parse_structured(source, ".json", "h-forged-gzip")

    assert payload.truncated is True
    assert payload.parsed is None
    assert payload.parse_error is None


def test_cache_invalidates_on_mtime_change(tmp_path: Path) -> None:
    """Same path + different mtime_hash returns the freshly parsed payload.

    The LRU is keyed on (path, mtime_hash), so a content change
    accompanied by a new mtime_hash key bypasses the stale entry.
    """
    f = tmp_path / "a.json"
    f.write_text('{"v": 1}')
    p1 = parse_structured(f, ".json", "h1")
    assert p1.parsed == {"v": 1}
    f.write_text('{"v": 2}')
    p2 = parse_structured(f, ".json", "h2")
    assert p2.parsed == {"v": 2}
    # And the cache returns the stale value when the same mtime_hash
    # is passed again (the contract is the inventory's responsibility).
    p3 = parse_structured(f, ".json", "h1")
    assert p3.parsed == {"v": 1}


def test_node_count_and_depth_primitive() -> None:
    n, d = _count_nodes_and_depth("hello")
    assert n == 1
    assert d == 0


def test_node_count_and_depth_nested() -> None:
    # {a: [{b: 1}]} = 1 (root dict) + 1 (list) + 1 (inner dict) + 1 (leaf) = 4
    n, d = _count_nodes_and_depth({"a": [{"b": 1}]})
    assert n == 4
    # depths: root=0, list=1, inner dict=2, leaf=3
    assert d == 3


def test_empty_containers() -> None:
    n, d = _count_nodes_and_depth({})
    assert n == 1
    assert d == 0
    n2, d2 = _count_nodes_and_depth([])
    assert n2 == 1
    assert d2 == 0


def test_yaml_serialization_collapses_blank_lines(tmp_path: Path) -> None:
    """Multi-blank-line YAML output collapses to a single blank between
    blocks (matches the YamlViewer reference post-processing)."""
    f = tmp_path / "a.json"
    # Crafted to potentially produce blank padding in the YAML output.
    f.write_text(json.dumps({"a": {"sub": 1}, "b": {"sub2": 2}, "c": {"sub3": 3}}))
    payload = parse_structured(f, ".json", "h1")
    assert "\n\n\n" not in payload.pretty_yaml
