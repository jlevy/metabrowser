"""Transparent bounded compression support for browser artifact reads.

Provides :class:`ArtifactPath`, a thin wrapper that exposes both a
file's on-disk identity (``disk_path``, ``disk_size``) and its logical
identity (``logical_ext``, ``logical_size``, text/binary opens).
Browser endpoints construct one per request and key classification, sizing,
and read behavior off it instead of branching on individual suffixes.

The split lets compressed artifacts produce the same logical API envelopes as
their plain counterparts while preserving their on-disk identity.
"""

from __future__ import annotations

import gzip
import io
import mimetypes
import os
import time
import zlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import IO, Any, cast

# Single source of truth for supported on-disk compression suffixes.
GZIP_SUFFIX: str = ".gz"
GZIP_PARTIAL_SUFFIX: str = GZIP_SUFFIX + ".partial"
ZLIB_SUFFIX: str = ".zlib"
COMPRESSED_SUFFIXES: frozenset[str] = frozenset({GZIP_SUFFIX, ZLIB_SUFFIX})

# Shared resource defaults bound every supported decompressor even when a small
# input expands adversarially.
ARTIFACT_MAX_COMPRESSED_BYTES = 64 * 1024 * 1024
ARTIFACT_MAX_DECOMPRESSED_BYTES = 256 * 1024 * 1024
ARTIFACT_MAX_CPU_SECONDS = 5.0
_ZLIB_INPUT_CHUNK_BYTES = 64 * 1024
_DECOMPRESSED_CHUNK_BYTES = 64 * 1024
_COMPRESSED_SIZE_CACHE_ENTRIES = 256


class ArtifactCompressionError(OSError):
    """A compressed artifact is malformed or violates its stream contract."""


class ArtifactDecompressionLimitError(ArtifactCompressionError):
    """A compressed artifact exceeded a configured resource bound."""


class ArtifactDecompressionTimeoutError(ArtifactDecompressionLimitError):
    """A compressed artifact exceeded its decompression CPU-time budget."""


class _BoundedCompressedReader(io.RawIOBase):
    """Limit physical bytes read from a compressed artifact."""

    def __init__(self, path: Path, max_compressed_bytes: int) -> None:
        super().__init__()
        if max_compressed_bytes <= 0:
            raise ValueError("compressed input bound must be positive")
        self._source = path.open("rb")
        if os.fstat(self._source.fileno()).st_size > max_compressed_bytes:
            self._source.close()
            raise ArtifactDecompressionLimitError(
                f"compressed content exceeds {max_compressed_bytes} bytes"
            )
        self._max_compressed_bytes = max_compressed_bytes
        self._bytes_read = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False

    def readinto(self, buffer: Any) -> int:
        if self.closed:
            raise ValueError("I/O operation on closed compressed input")
        target = memoryview(buffer).cast("B")
        if not target:
            return 0
        remaining = self._max_compressed_bytes - self._bytes_read
        chunk = self._source.read(min(len(target), remaining + 1))
        self._bytes_read += len(chunk)
        if self._bytes_read > self._max_compressed_bytes:
            raise ArtifactDecompressionLimitError(
                f"compressed content exceeds {self._max_compressed_bytes} bytes"
            )
        target[: len(chunk)] = chunk
        return len(chunk)

    def close(self) -> None:
        try:
            self._source.close()
        finally:
            super().close()


class _BoundedGzipReader(io.RawIOBase):
    """Limit gzip output and decompression CPU without buffering its payload."""

    def __init__(
        self,
        source: IO[bytes],
        max_output_bytes: int,
        max_cpu_seconds: float,
        *,
        owned_source: io.IOBase | None = None,
    ) -> None:
        super().__init__()
        if max_output_bytes <= 0:
            source.close()
            if owned_source is not None:
                owned_source.close()
            raise ValueError("decompressed output bound must be positive")
        if max_cpu_seconds <= 0:
            source.close()
            if owned_source is not None:
                owned_source.close()
            raise ValueError("decompression CPU bound must be positive")
        self._source = source
        self._owned_source = owned_source
        self._max_output_bytes = max_output_bytes
        self._max_cpu_seconds = max_cpu_seconds
        self._bytes_read = 0
        self._cpu_seconds = 0.0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False

    def _read_decoded(self, size: int) -> bytes:
        started_at = time.thread_time()
        try:
            try:
                return self._source.read(size)
            except (gzip.BadGzipFile, EOFError, zlib.error) as exc:
                raise ArtifactCompressionError(f"invalid gzip stream: {exc}") from exc
        finally:
            self._cpu_seconds += time.thread_time() - started_at
            if self._cpu_seconds > self._max_cpu_seconds:
                raise ArtifactDecompressionTimeoutError(
                    f"gzip decompression exceeded {self._max_cpu_seconds:g} CPU seconds"
                )

    def readinto(self, buffer: Any) -> int:
        if self.closed:
            raise ValueError("I/O operation on closed compressed stream")
        target = memoryview(buffer).cast("B")
        if not target:
            return 0
        remaining = self._max_output_bytes - self._bytes_read
        if remaining <= 0:
            if self._read_decoded(1):
                raise ArtifactDecompressionLimitError(
                    f"decompressed content exceeds {self._max_output_bytes} bytes"
                )
            return 0
        chunk = self._read_decoded(min(len(target), remaining))
        count = len(chunk)
        target[:count] = chunk
        self._bytes_read += count
        return count

    def close(self) -> None:
        try:
            self._source.close()
        finally:
            try:
                if self._owned_source is not None:
                    self._owned_source.close()
            finally:
                super().close()


def _open_gzip_binary(
    path: Path,
    *,
    max_compressed_bytes: int = ARTIFACT_MAX_COMPRESSED_BYTES,
    max_output_bytes: int = ARTIFACT_MAX_DECOMPRESSED_BYTES,
    max_cpu_seconds: float = ARTIFACT_MAX_CPU_SECONDS,
) -> IO[bytes]:
    compressed_source = _BoundedCompressedReader(path, max_compressed_bytes)
    try:
        decoded_source = cast(
            IO[bytes],
            cast(object, gzip.GzipFile(fileobj=compressed_source, mode="rb")),
        )
        return cast(
            IO[bytes],
            _BoundedGzipReader(
                decoded_source,
                max_output_bytes,
                max_cpu_seconds,
                owned_source=compressed_source,
            ),
        )
    except Exception:
        compressed_source.close()
        raise


class _BoundedZlibReader(io.RawIOBase):
    """Incrementally decode one zlib stream under input, output, and time bounds."""

    def __init__(
        self,
        path: Path,
        *,
        max_compressed_bytes: int,
        max_output_bytes: int,
        max_cpu_seconds: float,
    ) -> None:
        super().__init__()
        if max_compressed_bytes <= 0 or max_output_bytes <= 0 or max_cpu_seconds <= 0:
            raise ValueError("zlib resource bounds must be positive")
        self._source = path.open("rb")
        disk_size = os.fstat(self._source.fileno()).st_size
        if disk_size > max_compressed_bytes:
            self._source.close()
            raise ArtifactDecompressionLimitError(
                f"compressed content exceeds {max_compressed_bytes} bytes"
            )
        self._decompressor = zlib.decompressobj()
        self._buffer = bytearray()
        self._compressed_read = 0
        self._decompressed_read = 0
        self._max_compressed_bytes = max_compressed_bytes
        self._max_output_bytes = max_output_bytes
        self._max_cpu_seconds = max_cpu_seconds
        self._cpu_seconds = 0.0
        self._finished = False

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False

    def _check_time_budget(self) -> None:
        if self._cpu_seconds > self._max_cpu_seconds:
            raise ArtifactDecompressionTimeoutError(
                f"zlib decompression exceeded {self._max_cpu_seconds:g} CPU seconds"
            )

    def _read_compressed_chunk(self) -> bytes:
        unconsumed = self._decompressor.unconsumed_tail
        if unconsumed:
            return unconsumed
        remaining = self._max_compressed_bytes - self._compressed_read
        chunk = self._source.read(min(_ZLIB_INPUT_CHUNK_BYTES, remaining + 1))
        self._compressed_read += len(chunk)
        if self._compressed_read > self._max_compressed_bytes:
            raise ArtifactDecompressionLimitError(
                f"compressed content exceeds {self._max_compressed_bytes} bytes"
            )
        return chunk

    def _finish_stream(self) -> None:
        if not self._decompressor.eof:
            raise ArtifactCompressionError("truncated zlib stream")
        if self._decompressor.unused_data:
            raise ArtifactCompressionError("zlib artifact contains trailing data")
        trailing = self._source.read(1)
        self._compressed_read += len(trailing)
        if self._compressed_read > self._max_compressed_bytes:
            raise ArtifactDecompressionLimitError(
                f"compressed content exceeds {self._max_compressed_bytes} bytes"
            )
        if trailing:
            raise ArtifactCompressionError("zlib artifact contains trailing data")
        self._finished = True

    def _pump(self) -> None:
        chunk = self._read_compressed_chunk()
        if not chunk:
            self._finish_stream()
            return

        remaining = self._max_output_bytes - self._decompressed_read
        if remaining <= 0:
            raise ArtifactDecompressionLimitError(
                f"decompressed content exceeds {self._max_output_bytes} bytes"
            )
        output_limit = min(_DECOMPRESSED_CHUNK_BYTES, remaining)
        started_at = time.thread_time()
        try:
            output = self._decompressor.decompress(chunk, max_length=output_limit)
        except zlib.error as exc:
            raise ArtifactCompressionError(f"invalid zlib stream: {exc}") from exc
        self._cpu_seconds += time.thread_time() - started_at
        self._check_time_budget()

        self._decompressed_read += len(output)
        self._buffer.extend(output)
        if self._decompressor.eof:
            self._finish_stream()

    def readinto(self, buffer: Any) -> int:
        if self.closed:
            raise ValueError("I/O operation on closed zlib stream")
        target = memoryview(buffer).cast("B")
        while len(self._buffer) < len(target) and not self._finished:
            self._pump()
        count = min(len(target), len(self._buffer))
        target[:count] = self._buffer[:count]
        del self._buffer[:count]
        return count

    def close(self) -> None:
        try:
            self._source.close()
        finally:
            super().close()


def _open_zlib_binary(
    path: Path,
    *,
    max_compressed_bytes: int = ARTIFACT_MAX_COMPRESSED_BYTES,
    max_output_bytes: int = ARTIFACT_MAX_DECOMPRESSED_BYTES,
    max_cpu_seconds: float = ARTIFACT_MAX_CPU_SECONDS,
) -> IO[bytes]:
    raw = _BoundedZlibReader(
        path,
        max_compressed_bytes=max_compressed_bytes,
        max_output_bytes=max_output_bytes,
        max_cpu_seconds=max_cpu_seconds,
    )
    return cast(IO[bytes], raw)


@lru_cache(maxsize=_COMPRESSED_SIZE_CACHE_ENTRIES)
def _gzip_uncompressed_size_cached(path_str: str, mtime_ns: int, disk_size: int) -> int:
    del mtime_ns, disk_size
    total = 0
    with _open_gzip_binary(Path(path_str)) as source:
        while chunk := source.read(_DECOMPRESSED_CHUNK_BYTES):
            total += len(chunk)
    return total


def _gzip_uncompressed_size(path: Path) -> int:
    """Validate and count every gzip member under the global resource bounds."""
    stat_result = path.stat()
    return _gzip_uncompressed_size_cached(str(path), stat_result.st_mtime_ns, stat_result.st_size)


@lru_cache(maxsize=_COMPRESSED_SIZE_CACHE_ENTRIES)
def _zlib_uncompressed_size_cached(path_str: str, mtime_ns: int, disk_size: int) -> int:
    del mtime_ns, disk_size
    total = 0
    with _open_zlib_binary(Path(path_str)) as source:
        while chunk := source.read(_DECOMPRESSED_CHUNK_BYTES):
            total += len(chunk)
    return total


def _zlib_uncompressed_size(path: Path) -> int:
    """Validate and count a zlib stream under the global resource bounds."""
    stat_result = path.stat()
    return _zlib_uncompressed_size_cached(str(path), stat_result.st_mtime_ns, stat_result.st_size)


@dataclass(frozen=True)
class ArtifactPath:
    """A path the browser may open as compressed or plain.

    Frozen: equality and hashing key off ``disk_path`` only. Zlib logical size
    requires a bounded validation scan and is cached by path fingerprint.
    """

    disk_path: Path

    @property
    def is_gzip(self) -> bool:
        return self.disk_path.suffix.lower() == GZIP_SUFFIX

    @property
    def is_zlib(self) -> bool:
        return self.disk_path.suffix.lower() == ZLIB_SUFFIX

    @property
    def is_compressed(self) -> bool:
        return self.disk_path.suffix.lower() in COMPRESSED_SUFFIXES

    @property
    def logical_ext(self) -> str:
        """Return the inner extension after a supported compression suffix."""
        if self.is_compressed:
            return self.disk_path.with_suffix("").suffix.lower()
        return self.disk_path.suffix.lower()

    @property
    def logical_name(self) -> str:
        """Display filename with the compression suffix stripped when present."""
        if self.is_compressed:
            return self.disk_path.with_suffix("").name
        return self.disk_path.name

    @property
    def disk_size(self) -> int:
        return self.disk_path.stat().st_size

    @property
    def logical_size(self) -> int:
        """Validated uncompressed size for compressed artifacts."""
        if self.is_gzip:
            return _gzip_uncompressed_size(self.disk_path)
        if self.is_zlib:
            return _zlib_uncompressed_size(self.disk_path)
        return self.disk_size

    @property
    def compression(self) -> str | None:
        """Compression scheme tag (e.g. ``"gzip"``). ``None`` for uncompressed."""
        if self.is_gzip:
            return "gzip"
        if self.is_zlib:
            return "zlib"
        return None

    @property
    def mime_type(self) -> str:
        """Best-guess MIME type derived from the *logical* filename."""
        mime, _ = mimetypes.guess_type(self.logical_name)
        return mime or "application/octet-stream"

    def open_text(
        self,
        errors: str = "replace",
        *,
        max_compressed_bytes: int = ARTIFACT_MAX_COMPRESSED_BYTES,
        max_output_bytes: int = ARTIFACT_MAX_DECOMPRESSED_BYTES,
        max_cpu_seconds: float = ARTIFACT_MAX_CPU_SECONDS,
    ) -> IO[str]:
        """Open as text. Always text mode; never returns a binary handle."""
        if self.is_compressed:
            binary = self.open_binary(
                max_compressed_bytes=max_compressed_bytes,
                max_output_bytes=max_output_bytes,
                max_cpu_seconds=max_cpu_seconds,
            )
            return io.TextIOWrapper(binary, errors=errors)
        return open(self.disk_path, errors=errors)

    def open_binary(
        self,
        *,
        max_compressed_bytes: int = ARTIFACT_MAX_COMPRESSED_BYTES,
        max_output_bytes: int = ARTIFACT_MAX_DECOMPRESSED_BYTES,
        max_cpu_seconds: float = ARTIFACT_MAX_CPU_SECONDS,
    ) -> IO[bytes]:
        """Open as binary, transparently decompressing supported formats."""
        if self.is_gzip:
            return _open_gzip_binary(
                self.disk_path,
                max_compressed_bytes=max_compressed_bytes,
                max_output_bytes=max_output_bytes,
                max_cpu_seconds=max_cpu_seconds,
            )
        if self.is_zlib:
            return _open_zlib_binary(
                self.disk_path,
                max_compressed_bytes=max_compressed_bytes,
                max_output_bytes=max_output_bytes,
                max_cpu_seconds=max_cpu_seconds,
            )
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
