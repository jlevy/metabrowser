"""Malformed frontmatter must surface a visible error, not silent fallback.

Per docs/general/guidelines/development-rules.md (no-silent-fallback):
parse failures must be either raised or recorded as visible per-file
errors, not silently substituted with defaults. A `.md` file with a
broken YAML frontmatter block must:

1. Have ``ctx.frontmatter_parse_error`` set to the parse-error string;
2. Show up on the /api/file response as ``frontmatter_error``;
3. Fall back to the generic Markdown classification because specialized
   plugin predicates cannot claim a file when the frontmatter dict cannot be
   built.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import Mock

from metabrowser import server
from metabrowser.file_kinds import FileContext


class _FakeQuery:
    def __init__(self, params: dict[str, str]) -> None:
        self._params = params

    def get(self, key: str, default: str = "") -> str:
        return self._params.get(key, default)


def _api_file(path: str) -> dict[str, object]:
    request = Mock(spec=["query_params", "headers"])
    request.query_params = _FakeQuery({"path": path})
    request.headers = {}
    response = asyncio.run(server.api_file(request))
    return json.loads(bytes(response.body))


def test_malformed_frontmatter_sets_parse_error_on_context(tmp_path: Path) -> None:
    f = tmp_path / "bad.md"
    f.write_text("---\nthis: : : not valid yaml :::\n   bad: indent\n---\nbody\n")
    ctx = FileContext(f, ".md")
    # Touch the property; if the YAML parses cleanly we'd get a dict and
    # frontmatter_parse_error would stay None.
    _ = ctx.frontmatter
    assert ctx.frontmatter is None
    assert ctx.frontmatter_parse_error is not None
    assert ctx.frontmatter_parse_error  # non-empty string


def test_clean_frontmatter_no_parse_error(tmp_path: Path) -> None:
    f = tmp_path / "good.md"
    f.write_text("---\ntitle: Hello\n---\nbody\n")
    ctx = FileContext(f, ".md")
    assert ctx.frontmatter == {"title": "Hello"}
    assert ctx.frontmatter_parse_error is None


def test_no_frontmatter_no_parse_error(tmp_path: Path) -> None:
    f = tmp_path / "plain.md"
    f.write_text("# heading\n\nno frontmatter here.\n")
    ctx = FileContext(f, ".md")
    assert ctx.frontmatter is None
    assert ctx.frontmatter_parse_error is None  # absent, not malformed


def test_api_file_surfaces_frontmatter_error_for_md(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    md = tmp_path / "broken.md"
    md.write_text("---\n: : : not valid yaml\nbad indent\n---\n\nbody\n")
    result = _api_file("broken.md")
    assert "frontmatter_error" in result, (
        "/api/file must surface frontmatter parse errors per the "
        "no-silent-fallback rule (got: " + str(list(result.keys())) + ")"
    )
    assert result["frontmatter_error"]
    # No frontmatter dict on the response — the parser couldn't build one.
    assert "frontmatter" not in result
    # Falls back to generic Markdown classification, not a specialized kind.
    assert result["kind"] == "markdown"


def test_api_file_no_frontmatter_error_for_clean_file(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    md = tmp_path / "clean.md"
    md.write_text("---\ntitle: Hello\n---\n\nbody\n")
    result = _api_file("clean.md")
    assert "frontmatter_error" not in result
    assert result["frontmatter"] == {"title": "Hello"}
