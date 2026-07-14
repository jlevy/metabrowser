"""Transparent on-disk gzip support for browser artifact reads.

Provides :class:`ArtifactPath`, a thin wrapper that exposes both a
file's on-disk identity (``disk_path``, ``disk_size``) and its logical
identity (``logical_ext``, ``logical_size``, text/binary opens).
Browser endpoints construct one per request and key all classification,
sizing, and read behavior off it instead of sprinkling
``path.suffix == ".gz"`` checks across the codebase.

The split lets a ``foo.jsonl.gz`` produce byte-identical API envelopes
to ``foo.jsonl`` while the on-disk size and bytes-on-the-wire still
reflect the compressed reality.

Future archive formats (``.zst``, ``.br``, ``.xz``) plug in here, not at
every callsite.
"""

from __future__ import annotations

import gzip
import mimetypes
import os
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import IO, cast

# Single source of truth for the gzip on-disk suffix. Every callsite that
# detects, appends, or strips the gzip extension imports from here so a
# future archive format swap is a one-line change.
GZIP_SUFFIX: str = ".gz"
GZIP_PARTIAL_SUFFIX: str = GZIP_SUFFIX + ".partial"


def _gz_uncompressed_size(path: Path) -> int:
    """Read the gzip ISIZE trailer (last four bytes) in O(1).

    ISIZE stores uncompressed size mod 2**32. We never produce or read
    files >= 2 GB (run artifacts cap well below that), so the modulo
    never bites in practice. Raises ``OSError`` on read failure;
    caller decides how to surface a malformed-trailer case.
    """
    with path.open("rb") as fh:
        fh.seek(-4, os.SEEK_END)
        return struct.unpack("<I", fh.read(4))[0]


@dataclass(frozen=True)
class ArtifactPath:
    """A path the browser may open as either gzip-compressed or plain.

    Frozen: equality and hashing key off ``disk_path`` only. All derived
    properties are O(1) on top of cheap stat/suffix operations, so we
    don't bother caching them.
    """

    disk_path: Path

    @property
    def is_gzip(self) -> bool:
        return self.disk_path.suffix.lower() == GZIP_SUFFIX

    @property
    def logical_ext(self) -> str:
        """Inner extension: ``foo.jsonl.gz`` -> ``.jsonl``; ``foo.jsonl`` -> ``.jsonl``."""
        if self.is_gzip:
            return self.disk_path.with_suffix("").suffix.lower()
        return self.disk_path.suffix.lower()

    @property
    def logical_name(self) -> str:
        """Display filename with the ``.gz`` stripped when present."""
        if self.is_gzip:
            return self.disk_path.with_suffix("").name
        return self.disk_path.name

    @property
    def disk_size(self) -> int:
        return self.disk_path.stat().st_size

    @property
    def logical_size(self) -> int:
        """Uncompressed size. For ``.gz`` reads the ISIZE trailer."""
        if self.is_gzip:
            return _gz_uncompressed_size(self.disk_path)
        return self.disk_size

    @property
    def compression(self) -> str | None:
        """Compression scheme tag (e.g. ``"gzip"``). ``None`` for uncompressed."""
        return "gzip" if self.is_gzip else None

    @property
    def mime_type(self) -> str:
        """Best-guess MIME type derived from the *logical* filename."""
        mime, _ = mimetypes.guess_type(self.logical_name)
        return mime or "application/octet-stream"

    def open_text(self, errors: str = "replace") -> IO[str]:
        """Open as text. Always text mode; never returns a binary handle."""
        if self.is_gzip:
            return gzip.open(self.disk_path, "rt", errors=errors)
        return open(self.disk_path, errors=errors)

    def open_binary(self) -> IO[bytes]:
        """Open as binary, decompressing transparently when gzipped."""
        if self.is_gzip:
            # ``gzip.open(..., "rb")`` is typed as ``GzipFile`` rather than
            # the IO[bytes] protocol it actually implements at runtime.
            # Round-trip through ``object`` so basedpyright accepts the
            # cast; callers see the unified IO[bytes] type.
            return cast(IO[bytes], cast(object, gzip.open(self.disk_path, "rb")))
        return self.disk_path.open("rb")

    def passthrough_headers(self) -> dict[str, str]:
        """Headers for serving the on-disk gzip bytes verbatim to the client.

        Returns ``Content-Encoding: gzip`` + ``Vary: Accept-Encoding``
        when ``is_gzip``; empty dict otherwise. The caller is responsible
        for setting ``Content-Type`` (typically from :attr:`mime_type`).
        Pair with :meth:`open_binary` for the stream-decompress fallback
        when the client doesn't accept gzip.
        """
        if self.is_gzip:
            return {"Content-Encoding": "gzip", "Vary": "Accept-Encoding"}
        return {}
