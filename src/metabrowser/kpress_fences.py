"""Bind a rendered Markdown fence to its original file, across wiki rewrites and inert HTML."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import TypedDict

from metabrowser.gz_io import ArtifactCompressionError
from metabrowser.inert_html import ANCHOR_PREFIX
from metabrowser.markdown_limits import MARKDOWN_DIFF_MAX_BYTES
from metabrowser.source import ContentReadError, read_content_window, resolve_content


class FencePlacement(TypedDict):
    id: str
    opening_line: int
    format: str


@dataclass(frozen=True, slots=True)
class MarkedMarkdown:
    source: str
    placements: tuple[FencePlacement, ...]


_EOL = re.compile(rb"\r\n?|\n")
_STRUCTURED_OPENING = re.compile(
    r"(?:\A|(?<=[\r\n]))(?:`{3,}|~{3,})[^\S\r\n]*(?:json|yaml|yml)(?=\s|$)",
    re.IGNORECASE,
)


async def read_fence_origin(
    path: str,
    revision: str,
    source: str,
    ext: str,
    view: str,
    profile: str | None,
    *,
    blob: bytes | None = None,
) -> bytes | None:
    """Read the bounded, revision-checked input that the node route would address."""
    if (
        ext != ".md"
        or len(source) > MARKDOWN_DIFF_MAX_BYTES
        or (profile or view or "document").strip().lower()
        not in {"document", "rendered", "markdown", "doc"}
        or not _STRUCTURED_OPENING.search(source)
    ):
        return None
    if blob is not None:
        return blob if len(blob) <= MARKDOWN_DIFF_MAX_BYTES else None
    try:
        ref = await resolve_content(path)
        if ref is None or ref.fingerprint != revision:
            return None
        window = await read_content_window(ref, max_bytes=MARKDOWN_DIFF_MAX_BYTES)
        after = await resolve_content(path)
    except (ContentReadError, ArtifactCompressionError):
        return None
    if window.has_more or after is None or after.fingerprint != revision:
        return None
    return window.data


def mark_fences(source: str, origin: bytes, revision: str) -> MarkedMarkdown:
    # The same KPress block parser and budgets define the structured projection route.
    # Token maps address the full source here; KPress later strips frontmatter itself.
    from metabrowser.markdown_fences import structured_fences

    original = {f.opening_line: f for f in structured_fences(origin)}
    if not original:
        return MarkedMarkdown(source, ())
    rendered = source.encode("utf-8")
    # The namespace covers the complete input, including authored raw HTML and POST
    # overrides. A marker copied from another render changes this hash if pasted into
    # the input. Lookalike classes and identical code contents convey no authority.
    namespace = hashlib.sha256(revision.encode() + b"\0" + rendered).hexdigest()[:32]
    placements: list[FencePlacement] = []
    pieces: list[bytes] = []
    copied = 0
    for fence in structured_fences(rendered):
        authored = original.get(fence.opening_line)
        if authored is None or authored.format != fence.format:
            continue
        payload = rendered[fence.start_byte : fence.end_byte]
        original_payload = origin[authored.start_byte : authored.end_byte]
        if _EOL.sub(b"\n", payload) != _EOL.sub(b"\n", original_payload):
            continue
        marker = f"{ANCHOR_PREFIX}mb-fence-{namespace}-{fence.opening_line}"
        # Extend the info string without changing its language, payload or line map.
        end = fence.start_byte - (
            2 if rendered[fence.start_byte - 2 : fence.start_byte] == b"\r\n" else 1
        )
        pieces.extend((rendered[copied:end], b" ", marker.encode()))
        copied = end
        placements.append(
            {"id": marker, "opening_line": fence.opening_line, "format": fence.format}
        )
    pieces.append(rendered[copied:])
    return MarkedMarkdown(b"".join(pieces).decode(), tuple(placements))
