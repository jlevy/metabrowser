"""Bounded full-page HTML detection for the html kind's default view.

Classification of ``.html`` / ``.htm`` is by extension. This module only
chooses which of the two views opens first. A miss still offers Preview;
a hit still offers Source.
"""

from __future__ import annotations

from pathlib import Path

from metabrowser.gz_io import ArtifactCompressionError, ArtifactPath

# One 4 KiB read is enough for a doctype, a root tag, or a leading comment
# block, and it stays a single block on a request path. The binary/text
# sniff uses a larger prefix because magic and UTF-8 validity need more
# runway; this question does not.
HTML_SNIFF_PREFIX_BYTES = 4 * 1024

_UTF8_BOM = b"\xef\xbb\xbf"
_ASCII_WS = frozenset(b" \t\n\r\f\v")
_TAG_END = frozenset(b" \t\n\r\f\v/>")
_FULL_PAGE_TAGS = (b"html", b"head", b"body", b"frameset")


def looks_like_full_page_html(prefix: bytes) -> bool:
    """Return whether *prefix* starts like a full HTML document.

    Skips a UTF-8 BOM, leading ASCII whitespace, and complete ``<!-- -->``
    comments, then looks case-insensitively for ``<!doctype html`` or a
    ``<html>``, ``<head>``, ``<body>``, or ``<frameset>`` tag. The first
    remaining token decides; a fragment that begins with other markup is
    not a full page.
    """

    index = 3 if prefix.startswith(_UTF8_BOM) else 0
    length = len(prefix)
    while index < length:
        while index < length and prefix[index] in _ASCII_WS:
            index += 1
        if index >= length:
            return False
        if prefix.startswith(b"<!--", index):
            end = prefix.find(b"-->", index + 4)
            if end < 0:
                return False
            index = end + 3
            continue
        lowered = prefix[index:].lower()
        if lowered.startswith(b"<!doctype"):
            after = lowered[9:]
            if not after or after[0] not in _ASCII_WS:
                return False
            name = after.lstrip()
            return name.startswith(b"html") and _at_name_boundary(name, 4)
        if not lowered.startswith(b"<"):
            return False
        for tag in _FULL_PAGE_TAGS:
            if lowered.startswith(b"<" + tag) and _at_name_boundary(lowered, 1 + len(tag)):
                return True
        return False
    return False


def sniff_full_page_html(path: Path) -> bool:
    """Read a bounded logical prefix and apply :func:`looks_like_full_page_html`.

    Unreadable or undecompressible files are treated as fragments so the
    default tab stays Source.
    """

    try:
        artifact = ArtifactPath(path)
        with artifact.open_binary(max_output_bytes=HTML_SNIFF_PREFIX_BYTES) as stream:
            prefix = stream.read(HTML_SNIFF_PREFIX_BYTES)
    except (ArtifactCompressionError, OSError):
        return False
    return looks_like_full_page_html(prefix)


def _at_name_boundary(data: bytes, end: int) -> bool:
    return end >= len(data) or data[end] in _TAG_END
