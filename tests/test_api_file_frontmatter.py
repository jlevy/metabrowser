"""api/file emits a `frontmatter` field for markdown files with frontmatter.

Plugins fetch the parsed dict via `ctx.frontmatter` in their JS renderers
without re-parsing the YAML block client-side.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import Mock

from metabrowser import server


class _FakeQuery:
    def __init__(self, params: dict[str, str]) -> None:
        self._params = params

    def get(self, key: str, default: str = "") -> str:
        return self._params.get(key, default)


class _FakeRequest:
    def __init__(self, query: dict[str, str]) -> None:
        self.query_params = _FakeQuery(query)
        self.headers = {}


def _api_file(path: str) -> dict[str, Any]:
    request = Mock(spec=["query_params", "headers"])
    request.query_params = _FakeQuery({"path": path})
    request.headers = {}
    response = asyncio.run(server.api_file(request))
    return (response.body and __import__("json").loads(response.body)) or {}


def test_api_file_emits_frontmatter_for_md_with_yaml(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    md = tmp_path / "doc.md"
    md.write_text("---\ntitle: Hello\ntags:\n  - a\n  - b\n---\n\nbody text\n")
    result = _api_file("doc.md")
    assert result.get("frontmatter") == {"title": "Hello", "tags": ["a", "b"]}


def test_api_file_omits_frontmatter_when_md_has_none(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    md = tmp_path / "plain.md"
    md.write_text("# heading\n\nbody only, no frontmatter.\n")
    result = _api_file("plain.md")
    # Field is omitted (rather than an empty dict) so the JS check
    # `data.frontmatter` is falsy when there's nothing to parse.
    assert "frontmatter" not in result


def test_api_file_omits_frontmatter_for_non_md(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    txt = tmp_path / "notes.txt"
    txt.write_text("plain text\n")
    result = _api_file("notes.txt")
    assert "frontmatter" not in result
