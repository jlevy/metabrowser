"""Content-based classification for files whose extension does not settle it.

Metabrowser types files by extension almost everywhere, because that is free
and right for the overwhelming majority of what it opens. This module is the
fallback for the remainder: files whose extension is unknown, absent, or not in
the browser's text set, where the only way to know what something is is to look
at it.

Two layers, deliberately separated:

- :func:`classify_prefix` decides from bytes alone. It performs no I/O, so it
  can be applied wherever the bytes already exist — at view time from a bounded
  read, or later by a crawl that has a file's leading bytes in hand and wants to
  record the answer alongside the rest of its inventory.
- :func:`sniff_artifact` is the view-time path: read a bounded prefix, then
  hand it to :func:`classify_prefix`.

The rule is intentionally cheap and conservative, matching what other tools
(git, file(1), grep) settle on:

- A NUL byte means binary. Nothing in the text formats this browser renders
  contains one, and NUL is what almost every real binary format has near the
  front — including UTF-16 text, which this browser does not render as text
  anyway.
- Content that is not valid UTF-8 is binary. A truncated multi-byte sequence at
  the prefix boundary is not a failure; the incremental decoder is used so the
  answer does not depend on where the read happened to stop.

Everything else is text. The bound matters more than the sophistication: the
prefix is a single bounded read, so the check costs the same for a 4 KB file
and a 4 GB one, and it never runs at all when the extension already answered.
"""

from __future__ import annotations

import codecs
from enum import StrEnum
from typing import TYPE_CHECKING

from metabrowser.gz_io import ArtifactCompressionError, ArtifactPath

if TYPE_CHECKING:
    from pathlib import Path

# Bytes examined. Large enough that a text file's first lines and any binary
# format's magic and header land inside it, small enough that the read is one
# block and never worth deferring.
SNIFF_PREFIX_BYTES = 8 * 1024


class ContentClass(StrEnum):
    """What a file's bytes look like.

    ``UNKNOWN`` is a real answer, not an error code: it means the content could
    not be examined — an unreadable file, or a compressed artifact that will not
    decompress — and the caller should fall back to whatever it would have done
    without a content check rather than guess in either direction.
    """

    TEXT = "text"
    BINARY = "binary"
    UNKNOWN = "unknown"


def classify_prefix(prefix: bytes) -> ContentClass:
    """Classify a file from its leading bytes. Pure; performs no I/O.

    ``prefix`` is expected to be the start of the file's *logical* content —
    decompressed, if the artifact is compressed — because that is what the
    browser would render.

    An empty prefix is :attr:`ContentClass.TEXT`: an empty file has nothing
    binary about it, and rendering it as empty text is what a reader expects.
    """
    if not prefix:
        return ContentClass.TEXT
    if b"\x00" in prefix:
        return ContentClass.BINARY
    # `final=False` so a multi-byte character split across the prefix boundary
    # is carried rather than raising. Without it the verdict would depend on
    # SNIFF_PREFIX_BYTES landing mid-character, which is both wrong and
    # maddening to reproduce.
    decoder = codecs.getincrementaldecoder("utf-8")()
    try:
        decoder.decode(prefix, final=False)
    except UnicodeDecodeError:
        return ContentClass.BINARY
    return ContentClass.TEXT


def sniff_artifact(path: Path, *, max_bytes: int = SNIFF_PREFIX_BYTES) -> ContentClass:
    """Classify a file by reading a bounded prefix of its logical bytes.

    Synchronous and bounded, so a request path can run it in a worker thread
    without a second offloading layer. Returns :attr:`ContentClass.UNKNOWN`
    when the bytes cannot be obtained at all.
    """
    try:
        artifact = ArtifactPath(path)
        with artifact.open_binary(max_output_bytes=max_bytes) as stream:
            prefix = stream.read(max_bytes)
    except (ArtifactCompressionError, OSError):
        return ContentClass.UNKNOWN
    return classify_prefix(prefix)
