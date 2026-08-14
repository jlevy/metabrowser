"""Tests for logical-extension fields in /api/file and /api/tree responses.

For ``.gz`` files, both endpoints add ``logical_ext`` (inner extension),
``compressed: True``, and ``compression: "gzip"``. ``/api/file`` also
adds ``size_uncompressed`` so the client's "X% read" math works.
Plain files keep the original envelope shape unchanged.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import struct
from pathlib import Path
from typing import Any, cast

from metabrowser import jsonl_view
from metabrowser import server as proc_browser

# Real JSONL events so the parser branch produces a meaningful response,
# not just an empty parse. Adapter-detection wants ~20 lines minimum.
_JSONL_LINES = [
    '{"type":"system","subtype":"init","cwd":"/tmp","tools":["Read"]}',
    '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Hello"}]}}',
    '{"type":"result","subtype":"success","duration_ms":42,"total_cost_usd":0.001,"is_error":false}',
] * 10
_JSONL_BYTES = ("\n".join(_JSONL_LINES) + "\n").encode("utf-8")


class _Params:
    def __init__(self, data: dict[str, str]) -> None:
        self._data = data

    def get(self, key: str, default: str = "") -> str:
        return self._data.get(key, default)


class _Headers:
    def __init__(self, data: dict[str, str]) -> None:
        self._data = {k.lower(): v for k, v in data.items()}

    def get(self, key: str, default: str = "") -> str:
        return self._data.get(key.lower(), default)


class _FakeRequest:
    def __init__(self, **params: str) -> None:
        self.query_params = _Params(params)
        self.headers = _Headers({})


def _setup_pair(tmp_path: Path) -> tuple[Path, Path]:
    """Write events.jsonl + events.jsonl.gz with identical content."""
    plain = tmp_path / "events.jsonl"
    plain.write_bytes(_JSONL_BYTES)
    gz = tmp_path / "events.jsonl.gz"
    with gzip.open(gz, "wb") as fh:
        fh.write(_JSONL_BYTES)
    proc_browser._set_root_dir(tmp_path)
    return plain, gz


def _call_file(path: str, **params: str) -> dict[str, Any]:
    fake = _FakeRequest(path=path, **params)
    response = asyncio.run(proc_browser.api_file(fake))  # pyright: ignore[reportArgumentType]
    return json.loads(bytes(response.body).decode())


def _call_tree(path: str = "") -> dict[str, Any]:
    fake = _FakeRequest(path=path)
    response = asyncio.run(proc_browser.api_tree(fake))  # pyright: ignore[reportArgumentType]
    return json.loads(bytes(response.body).decode())


# ── /api/file ──────────────────────────────────────────────────────


def test_api_file_plain_jsonl_omits_logical_fields(tmp_path: Path) -> None:
    """Existing clients must see the same envelope they always have."""
    _setup_pair(tmp_path)
    body = _call_file("events.jsonl")
    assert body["type"] == "jsonl"
    assert "logical_ext" not in body
    assert "compressed" not in body
    assert "compression" not in body
    assert "size_uncompressed" not in body


def test_api_file_gzipped_jsonl_includes_logical_fields(tmp_path: Path) -> None:
    _setup_pair(tmp_path)
    body = _call_file("events.jsonl.gz")
    assert body["type"] == "jsonl"
    assert body["logical_ext"] == ".jsonl"
    assert body["compressed"] is True
    assert body["compression"] == "gzip"
    # size = on-disk (compressed). size_uncompressed = decompressed.
    assert body["size"] < len(_JSONL_BYTES)
    assert body["size_uncompressed"] == len(_JSONL_BYTES)


def test_api_file_gzipped_text_inlines_full_decompressed_content(tmp_path: Path) -> None:
    """For .gz under the inline cap, content is the full decompressed text."""
    text = "alpha\nbeta\n" * 200
    plain = tmp_path / "notes.txt"
    plain.write_text(text)
    gz = tmp_path / "notes.txt.gz"
    with gzip.open(gz, "wb") as fh:
        fh.write(text.encode("utf-8"))
    proc_browser._set_root_dir(tmp_path)

    body = _call_file("notes.txt.gz")
    assert body["type"] == "text"
    assert body["content"] == text
    assert body["content_truncated"] is False
    assert body["logical_ext"] == ".txt"
    assert body["compressed"] is True
    assert body["size_uncompressed"] == len(text.encode("utf-8"))


def test_api_file_gzipped_text_honors_logical_byte_window(tmp_path: Path) -> None:
    """Gzip previews use the same logical-byte chunk contract as plain text."""
    text = "0123456789abcdef" * (proc_browser._TEXT_PREVIEW_CHUNK_BYTES // 8)
    encoded = text.encode("utf-8")
    gz = tmp_path / "large.txt.gz"
    with gzip.open(gz, "wb") as fh:
        fh.write(encoded)
    proc_browser._set_root_dir(tmp_path)

    offset = 117
    limit = 43
    body = _call_file("large.txt.gz", offset=str(offset), limit=str(limit))

    assert body["type"] == "text_chunk"
    assert body["content"] == encoded[offset : offset + limit].decode()
    assert body["content_offset"] == offset
    assert body["content_bytes"] == limit
    assert body["bytes_read"] == offset + limit
    assert body["content_truncated"] is True


def test_api_file_gzip_preview_does_not_trust_forged_isize(tmp_path: Path) -> None:
    payload = b"x" * (proc_browser._TEXT_PREVIEW_CHUNK_BYTES + 32)
    compressed = bytearray(gzip.compress(payload))
    compressed[-4:] = (1).to_bytes(4, "little")
    (tmp_path / "forged.txt.gz").write_bytes(compressed)
    proc_browser._set_root_dir(tmp_path)

    body = _call_file("forged.txt.gz")
    assert body["type"] == "text"
    assert body["content_bytes"] == proc_browser._TEXT_PREVIEW_CHUNK_BYTES
    assert body["content_truncated"] is True


def test_api_file_jsonl_parse_does_not_trust_forged_gzip_isize(tmp_path: Path, monkeypatch) -> None:
    payload = b'{"type":"result","subtype":"success"}\n' * 4
    compressed = bytearray(gzip.compress(payload))
    compressed[-4:] = (1).to_bytes(4, "little")
    (tmp_path / "forged.jsonl.gz").write_bytes(compressed)
    monkeypatch.setattr(jsonl_view, "_JSONL_PARSE_MAX_BYTES", 64)
    proc_browser._set_root_dir(tmp_path)

    body = _call_file("forged.jsonl.gz")

    assert body["type"] == "error"
    assert "decompressed content exceeds 64 bytes" in body["error"]


def test_api_file_rejects_forged_large_gzip_preview_offset(tmp_path: Path) -> None:
    source = tmp_path / "forged.txt.gz"
    with gzip.open(source, "wb") as fh:
        fh.write(b"small payload\n")
    encoded = source.read_bytes()
    source.write_bytes(encoded[:-4] + struct.pack("<I", 0xF0000000))
    proc_browser._set_root_dir(tmp_path)

    response = asyncio.run(
        proc_browser.api_file(
            cast(Any, _FakeRequest(path=source.name, offset=str(64 * 1024 * 1024), limit="1"))
        )
    )
    body = json.loads(bytes(response.body).decode())

    assert response.status_code == 416
    assert body["max_offset"] == proc_browser._TEXT_PREVIEW_MAX_CHUNK_BYTES


def test_api_file_keeps_random_access_for_large_uncompressed_text(tmp_path: Path) -> None:
    offset = proc_browser._TEXT_PREVIEW_MAX_CHUNK_BYTES + 11
    source = tmp_path / "large.txt"
    source.write_bytes(b"x" * offset + b"tail")
    proc_browser._set_root_dir(tmp_path)

    response = asyncio.run(
        proc_browser.api_file(
            cast(Any, _FakeRequest(path=source.name, offset=str(offset), limit="4"))
        )
    )
    body = json.loads(bytes(response.body).decode())

    assert response.status_code == 200
    assert body["type"] == "text_chunk"
    assert body["content"] == "tail"


def test_api_file_truncated_gzip_degrades_to_binary(tmp_path: Path) -> None:
    (tmp_path / "broken.txt.gz").write_bytes(b"\x1f\x8b")
    proc_browser._set_root_dir(tmp_path)

    body = _call_file("broken.txt.gz")

    assert body["type"] == "binary"
    assert body["kind"] == "binary"
    assert body["size"] == 2
    assert body["logical_ext"] == ".txt"
    assert body["compressed"] is True
    assert body["compression"] == "gzip"
    assert "size_uncompressed" not in body


# ── /api/tree ──────────────────────────────────────────────────────


def test_api_tree_plain_file_omits_logical_fields(tmp_path: Path) -> None:
    plain, _ = _setup_pair(tmp_path)
    body = _call_tree("")
    files = [e for e in body["tree"] if e["type"] == "file"]
    plain_entry = next(e for e in files if e["name"] == plain.name)
    assert "logical_ext" not in plain_entry
    assert "compressed" not in plain_entry


def test_api_tree_gzipped_file_carries_logical_fields(tmp_path: Path) -> None:
    _, gz = _setup_pair(tmp_path)
    body = _call_tree("")
    files = [e for e in body["tree"] if e["type"] == "file"]
    gz_entry = next(e for e in files if e["name"] == gz.name)
    assert gz_entry["logical_ext"] == ".jsonl"
    assert gz_entry["compressed"] is True
    assert gz_entry["compression"] == "gzip"
    # size on the entry stays disk_size (compressed) — that's what's
    # taking up room on the user's machine.
    assert gz_entry["size"] < len(_JSONL_BYTES)
