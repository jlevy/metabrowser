"""Tests for the ``/raw`` endpoint's gzip passthrough + identity fallback.

Mirrors the duck-typed handler-call pattern used in ``test_api_resources``
(no httpx dep). Exercises:
  * non-gzip files keep the existing FileResponse shape
  * ``Accept-Encoding: gzip`` → passthrough FileResponse with
    ``Content-Encoding: gzip`` (browser decompresses)
  * ``Accept-Encoding: identity`` → StreamingResponse whose body iterator
    yields the *decompressed* bytes (no Content-Encoding header)
  * The ``_accepts_gzip`` parser handles the RFC 7231 cases we care about
"""

from __future__ import annotations

import asyncio
import gzip
from pathlib import Path
from typing import Any

import pytest
from starlette.responses import FileResponse, StreamingResponse

from metabrowser import server as proc_browser
from metabrowser.server import _accepts_gzip

_SAMPLE_BYTES = b'{"event": "init"}\n{"event": "message", "text": "hello"}\n' * 100


class _Params:
    def __init__(self, data: dict[str, str]) -> None:
        self._data = data

    def get(self, key: str, default: str = "") -> str:
        return self._data.get(key, default)


class _Headers:
    def __init__(self, data: dict[str, str]) -> None:
        # Header lookup in Starlette is case-insensitive; mirror that.
        self._data = {k.lower(): v for k, v in data.items()}

    def get(self, key: str, default: str = "") -> str:
        return self._data.get(key.lower(), default)


class _FakeRequest:
    def __init__(self, path: str, accept_encoding: str = "") -> None:
        self.query_params = _Params({"path": path})
        self.headers = _Headers({"accept-encoding": accept_encoding})


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    """Write events.jsonl + events.jsonl.gz with identical content."""
    plain = tmp_path / "events.jsonl"
    plain.write_bytes(_SAMPLE_BYTES)
    gz = tmp_path / "events.jsonl.gz"
    with gzip.open(gz, "wb") as fh:
        fh.write(_SAMPLE_BYTES)
    proc_browser._set_root_dir(tmp_path)
    return plain, gz


def _call(path: str, accept_encoding: str = "") -> Any:
    fake = _FakeRequest(path, accept_encoding=accept_encoding)
    return asyncio.run(proc_browser.raw_file(fake))  # pyright: ignore[reportArgumentType]


# ── _accepts_gzip parser ──────────────────────────────────────────


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("", False),
        ("gzip", True),
        ("gzip, deflate, br", True),
        ("identity", False),
        ("deflate", False),
        ("*", True),
        ("gzip;q=0", False),
        ("gzip;q=0, *", False),
        ("*;q=0, gzip", True),
        ("gzip;q=0.5", True),
        ("br, gzip;q=0", False),
    ],
)
def test_accepts_gzip_parser(header: str, expected: bool) -> None:
    assert _accepts_gzip(header) is expected


# ── /raw endpoint: non-gzip files unchanged ────────────────────────


def test_raw_plain_file_returns_file_response_without_content_encoding(
    tmp_path: Path,
) -> None:
    plain, _ = _setup(tmp_path)
    response = _call("events.jsonl", accept_encoding="gzip")
    assert isinstance(response, FileResponse)
    assert response.headers.get("content-encoding") is None
    # FileResponse points at the on-disk file, not a temporary copy.
    assert Path(response.path) == plain


# ── /raw endpoint: gzip passthrough ────────────────────────────────


def test_raw_gz_with_accept_gzip_passes_bytes_through(tmp_path: Path) -> None:
    _, gz = _setup(tmp_path)
    response = _call("events.jsonl.gz", accept_encoding="gzip, deflate, br")
    assert isinstance(response, FileResponse)
    assert response.headers["content-encoding"] == "gzip"
    assert response.headers["vary"] == "Accept-Encoding"
    # Crucially, the file streamed IS the .gz on disk — not a decompressed
    # copy. That's the whole point of passthrough.
    assert Path(response.path) == gz


def test_raw_gz_mime_type_uses_logical_extension(tmp_path: Path) -> None:
    _, _ = _setup(tmp_path)
    response = _call("events.jsonl.gz", accept_encoding="gzip")
    # Inner ext drives mime; ``application/octet-stream`` is the fallback
    # so any *non-binary* mime confirms we stripped the .gz before lookup.
    assert response.media_type != "application/x-gzip"
    assert response.media_type != "application/gzip"


# ── /raw endpoint: identity fallback (decompresses on the fly) ─────


def test_raw_gz_with_identity_streams_decompressed_bytes(tmp_path: Path) -> None:
    _, _ = _setup(tmp_path)
    response = _call("events.jsonl.gz", accept_encoding="identity")
    assert isinstance(response, StreamingResponse)
    assert response.headers.get("content-encoding") is None
    assert response.headers["vary"] == "Accept-Encoding"

    # Drain the streaming body and assert it equals the original bytes.
    chunks: list[bytes] = []

    async def _drain() -> None:
        async for chunk in response.body_iterator:
            # The handler yields bytes; this just narrows the type for
            # basedpyright.
            assert isinstance(chunk, (bytes, bytearray, memoryview))
            chunks.append(bytes(chunk))

    asyncio.run(_drain())
    assert b"".join(chunks) == _SAMPLE_BYTES


def test_raw_gz_with_no_accept_encoding_streams_decompressed(tmp_path: Path) -> None:
    """No ``Accept-Encoding`` header at all: be conservative, decompress."""
    _, _ = _setup(tmp_path)
    response = _call("events.jsonl.gz", accept_encoding="")
    assert isinstance(response, StreamingResponse)
    assert response.headers.get("content-encoding") is None


# ── /raw endpoint: 404 path ────────────────────────────────────────


def test_raw_missing_path_returns_404(tmp_path: Path) -> None:
    _setup(tmp_path)
    response = _call("does-not-exist.jsonl")
    assert response.status_code == 404
