"""Exact byte spans of closed, column-zero structured code fences in a KPress document."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from kpress.format.markdown import _markdown_it
from kpress.runtime import _strip_leading_frontmatter
from markdown_it.token import Token

from metabrowser.builtin_plugins.structured.parser import STRUCTURED_CACHE_SIZE
from metabrowser.markdown_limits import (
    _CONTAINER_LINE,
    _MAX_CONTAINER_LINES,
    _MAX_NESTING,
    MARKDOWN_DIFF_MAX_BYTES,
)

_EOL = re.compile(rb"\r\n|\r|\n")


@dataclass(frozen=True, slots=True)
class StructuredFence:
    opening_line: int
    format: Literal["json", "yaml"]
    start_byte: int
    end_byte: int


def structured_fences(data: bytes) -> tuple[StructuredFence, ...]:
    """Recognized fences, omitting unclosed and nested blocks whose text is transformed."""
    if len(data) > MARKDOWN_DIFF_MAX_BYTES:
        return ()
    return _fences(data)


@lru_cache(maxsize=STRUCTURED_CACHE_SIZE)
def _fences(data: bytes) -> tuple[StructuredFence, ...]:
    # Cache only bounded host bytes and ranges. A revision with changed bytes cannot
    # reuse stale line numbers. No inline parsing, highlighting or YAML parsing here.
    text = _EOL.sub(b"\n", data).decode("utf-8", "replace")
    body = _strip_leading_frontmatter(text)
    if body and not body.startswith(("`", "~")) and "\n`" not in body and "\n~" not in body:
        return ()
    if len(_CONTAINER_LINE.findall(body.encode())) > _MAX_CONTAINER_LINES:
        return ()
    body_line = text.count("\n", 0, len(text) - len(body))
    line_starts = [0, *(match.end() for match in _EOL.finditer(data)), len(data)]
    md = _markdown_it(trust_mode="sanitized", diagrams="mermaid", math="auto")
    md.options["maxNesting"] = _MAX_NESTING
    tokens: list[Token] = []
    md.block.parse(body.replace("\x00", "\ufffd"), md, {}, tokens)
    found: list[StructuredFence] = []
    for token in tokens:
        if token.type != "fence" or token.level or not token.map:
            continue
        language = token.info.strip().split(maxsplit=1)
        if not language or language[0].lower() not in {"json", "yaml", "yml"}:
            continue
        opening, after = (index + body_line for index in token.map)
        if after <= opening + 1:
            continue
        marker = token.markup.encode("ascii")
        first = data[line_starts[opening] : line_starts[opening + 1]]
        last = data[line_starts[after - 1] : line_starts[after]].rstrip(b"\r\n")
        closing = last.lstrip(b" ")
        run = closing.rstrip(b" \t")
        if (
            not first.startswith(marker)
            or len(last) - len(closing) > 3
            or not run.startswith(marker)
            or run.strip(marker[:1])
        ):
            continue
        found.append(
            StructuredFence(
                opening + 1,
                "json" if language[0].lower() == "json" else "yaml",
                line_starts[opening + 1],
                line_starts[after - 1],
            )
        )
    return tuple(found)
