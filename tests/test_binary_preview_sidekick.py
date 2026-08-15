"""Bounded byte-chunk data hook for the built-in binary plugin.

Covers the contract in
``docs/project/specs/done/plan-2026-08-11-binary-byte-preview.md``:

* exact bytes at offset 0, an interior offset, and the final partial chunk,
  for plain, gzip, and zlib artifacts;
* both sides of the preview ceiling and of the reachable window, which
  compressed and plain artifacts share;
* served-root containment and range validation;
* malformed and adversarially expanding compressed input;
* the base64 transport round-tripping all 256 byte values.
"""

from __future__ import annotations

import base64
import gzip
import json
import zlib
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from metabrowser import server
from metabrowser.builtin_plugins.binary import sidekick
from metabrowser.gz_io import ArtifactPath

ALL_BYTES = bytes(range(256))


class _FakeQuery:
    def __init__(self, params: dict[str, str]) -> None:
        self._params = params

    def get(self, key: str, default: str = "") -> str:
        return self._params.get(key, default)


def _chunk(path: str, **params: object) -> tuple[int, dict[str, Any]]:
    """Call the hook the way the data-hook dispatcher does."""
    query = {"path": path, **{k: str(v) for k, v in params.items()}}
    request = Mock(spec=["query_params", "headers"])
    request.query_params = _FakeQuery(query)
    request.headers = {}
    response = sidekick.chunk_handler(request)
    return response.status_code, json.loads(bytes(response.body))


def _payload(body: dict[str, Any]) -> bytes:
    return base64.b64decode(body["content_base64"])


# ── Reads ──────────────────────────────────────────────────────────


def test_reads_exact_bytes_from_offset_zero(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "a.bin").write_bytes(ALL_BYTES)

    status, body = _chunk("a.bin")

    assert status == 200
    assert body["type"] == "binary_chunk"
    assert body["offset"] == 0
    assert body["bytes_read"] == 256
    assert body["next_offset"] == 256
    assert body["logical_size"] == 256
    assert body["has_more"] is False
    assert _payload(body) == ALL_BYTES


def test_reads_exact_bytes_from_an_interior_offset(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "a.bin").write_bytes(ALL_BYTES)

    status, body = _chunk("a.bin", offset=100, limit=50)

    assert status == 200
    assert body["offset"] == 100
    assert body["bytes_read"] == 50
    assert body["next_offset"] == 150
    assert body["has_more"] is True
    assert _payload(body) == ALL_BYTES[100:150]


def test_final_partial_chunk_reports_no_more(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "a.bin").write_bytes(ALL_BYTES)

    status, body = _chunk("a.bin", offset=200, limit=1024)

    assert status == 200
    assert body["bytes_read"] == 56
    assert body["next_offset"] == 256
    assert body["has_more"] is False
    assert _payload(body) == ALL_BYTES[200:]


def test_offset_at_end_of_file_returns_an_empty_chunk(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "a.bin").write_bytes(ALL_BYTES)

    status, body = _chunk("a.bin", offset=256)

    assert status == 200
    assert body["bytes_read"] == 0
    assert body["has_more"] is False
    assert _payload(body) == b""


def test_zero_byte_file_reports_an_empty_complete_chunk(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "empty.bin").write_bytes(b"")

    status, body = _chunk("empty.bin")

    assert status == 200
    assert body["logical_size"] == 0
    assert body["bytes_read"] == 0
    assert body["has_more"] is False


@pytest.mark.parametrize("suffix", [".gz", ".zlib"])
def test_compressed_artifacts_serve_logical_bytes(tmp_path: Path, suffix: str) -> None:
    server._set_root_dir(tmp_path)
    target = tmp_path / f"a.bin{suffix}"
    if suffix == ".gz":
        target.write_bytes(gzip.compress(ALL_BYTES))
    else:
        target.write_bytes(zlib.compress(ALL_BYTES))

    status, body = _chunk(target.name, offset=100, limit=50)

    assert status == 200
    assert body["logical_size"] == 256
    assert _payload(body) == ALL_BYTES[100:150]


def test_read_byte_chunk_reports_more_without_returning_it(tmp_path: Path) -> None:
    """The probe byte proving `has_more` must not reach the caller."""
    target = tmp_path / "a.bin"
    target.write_bytes(ALL_BYTES)

    payload, has_more = sidekick.read_byte_chunk(ArtifactPath(target), 0, 10)

    assert payload == ALL_BYTES[:10]
    assert has_more is True


# ── Ceilings and windows ───────────────────────────────────────────


def test_file_exactly_at_the_ceiling_is_eligible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server._set_root_dir(tmp_path)
    monkeypatch.setattr(sidekick, "BINARY_PREVIEW_MAX_BYTES", 1024)
    (tmp_path / "a.bin").write_bytes(b"\x00" * 1024)

    status, body = _chunk("a.bin", limit=16)

    assert status == 200
    assert body["max_preview_bytes"] == 1024


def test_file_above_the_ceiling_serves_a_capped_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ceiling caps loading; it does not refuse the file.

    It used to return 413 for anything larger, so the view existed for binaries
    but declined the large ones with nothing to look at. A bound on browser
    memory is no reason to withhold the first chunk.
    """
    server._set_root_dir(tmp_path)
    monkeypatch.setattr(sidekick, "BINARY_PREVIEW_MAX_BYTES", 1024)
    (tmp_path / "a.bin").write_bytes(b"\x00" * 4096)

    status, body = _chunk("a.bin", limit=16)

    assert status == 200
    assert body["logical_size"] == 4096
    assert body["max_preview_bytes"] == 1024
    assert body["bytes_read"] == 16
    assert body["has_more"] is True
    # The reader is not seeing the whole file, and never will be.
    assert body["preview_limited"] is True


def test_loading_stops_at_the_ceiling(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`has_more` goes false at the cap even though the file continues."""
    server._set_root_dir(tmp_path)
    monkeypatch.setattr(sidekick, "BINARY_PREVIEW_MAX_BYTES", 1024)
    (tmp_path / "a.bin").write_bytes(b"\x00" * 4096)

    status, body = _chunk("a.bin", offset=512, limit=4096)

    assert status == 200
    # Clipped to the ceiling rather than the requested window.
    assert body["bytes_read"] == 512
    assert body["next_offset"] == 1024
    assert body["has_more"] is False
    assert body["preview_limited"] is True

    # And past the cap there is genuinely no window to serve.
    beyond, _ = _chunk("a.bin", offset=1024, limit=16)
    assert beyond == 416


def test_compressed_artifacts_share_the_one_ceiling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Decompression is linear in the offset, so it needs no lower bound.

    A compressed artifact is eligible on exactly the same terms as a plain one;
    only its logical size decides.
    """
    server._set_root_dir(tmp_path)
    monkeypatch.setattr(sidekick, "BINARY_PREVIEW_MAX_BYTES", 4096)
    (tmp_path / "ok.bin.gz").write_bytes(gzip.compress(b"\x00" * 2048))
    (tmp_path / "big.bin.gz").write_bytes(gzip.compress(b"\x00" * 8192))

    eligible, body = _chunk("ok.bin.gz", limit=16)
    oversize, big_body = _chunk("big.bin.gz", limit=16)

    assert eligible == 200
    assert body["max_preview_bytes"] == 4096
    assert body["preview_limited"] is False
    # Larger than the ceiling is capped, not refused — same as a plain file.
    assert oversize == 200
    assert big_body["max_preview_bytes"] == 4096
    assert big_body["preview_limited"] is True


def test_window_past_the_ceiling_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only a window past the *ceiling* is a range error.

    Past the end of a file that fits under the ceiling there is simply nothing
    left, which an empty chunk reports without the caller special-casing a
    status.
    """
    server._set_root_dir(tmp_path)
    monkeypatch.setattr(sidekick, "BINARY_PREVIEW_MAX_BYTES", 1024)
    monkeypatch.setattr(sidekick, "BINARY_PREVIEW_MAX_CHUNK_BYTES", 4096)
    (tmp_path / "a.bin").write_bytes(b"\x00" * 4096)

    refused, _ = _chunk("a.bin", offset=1024, limit=25)
    assert refused == 416

    (tmp_path / "small.bin").write_bytes(b"\x00" * 512)
    past_eof, body = _chunk("small.bin", offset=600, limit=25)
    assert past_eof == 200
    assert body["bytes_read"] == 0
    assert body["has_more"] is False


def test_limit_is_clamped_to_the_per_request_maximum(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server._set_root_dir(tmp_path)
    monkeypatch.setattr(sidekick, "BINARY_PREVIEW_MAX_CHUNK_BYTES", 32)
    (tmp_path / "a.bin").write_bytes(ALL_BYTES)

    status, body = _chunk("a.bin", limit=10_000)

    assert status == 200
    assert body["bytes_read"] == 32
    assert body["has_more"] is True


def test_default_limit_is_the_configured_chunk_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server._set_root_dir(tmp_path)
    monkeypatch.setattr(sidekick, "BINARY_PREVIEW_CHUNK_BYTES", 64)
    (tmp_path / "a.bin").write_bytes(b"\x00" * 512)

    status, body = _chunk("a.bin")

    assert status == 200
    assert body["bytes_read"] == 64


# ── Validation and failures ────────────────────────────────────────


def test_traversal_is_rejected_without_leaking_an_absolute_path(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path.parent / "outside.bin").write_bytes(b"secret")

    status, body = _chunk("../outside.bin")

    assert status == 404
    assert str(tmp_path) not in json.dumps(body)


def test_directory_and_missing_paths_are_rejected(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "sub").mkdir()

    assert _chunk("sub")[0] == 404
    assert _chunk("nope.bin")[0] == 404


@pytest.mark.parametrize(
    ("params", "reason"),
    [
        ({"offset": -1}, "negative offset"),
        ({"offset": "abc"}, "non-integer offset"),
        ({"limit": 0}, "zero limit"),
        ({"limit": -5}, "negative limit"),
        ({"limit": "1e6"}, "non-integer limit"),
    ],
)
def test_invalid_ranges_are_rejected(
    tmp_path: Path, params: dict[str, object], reason: str
) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "a.bin").write_bytes(ALL_BYTES)

    status, _ = _chunk("a.bin", **params)

    assert status == 400, reason


def test_malformed_gzip_reports_a_decompression_failure(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    corrupt = bytearray(gzip.compress(ALL_BYTES))
    corrupt[-4:] = b"\x00\x00\x00\x00"  # break the CRC/ISIZE trailer
    (tmp_path / "a.bin.gz").write_bytes(bytes(corrupt))

    status, body = _chunk("a.bin.gz")

    assert status == 422
    assert "content_base64" not in body


def test_expanding_compressed_input_is_bounded_not_buffered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A small artifact that expands hugely is served bounded, not buffered.

    The output bound is the requested window clipped to the ceiling, so the
    decompressed bytes never accumulate past it however far the input expands.
    """
    server._set_root_dir(tmp_path)
    monkeypatch.setattr(sidekick, "BINARY_PREVIEW_MAX_BYTES", 4096)
    (tmp_path / "bomb.bin.gz").write_bytes(gzip.compress(b"\x00" * (1 << 20)))

    status, body = _chunk("bomb.bin.gz")

    assert status == 200
    assert body["logical_size"] == 1 << 20
    # Never more than the ceiling, whatever the caller asked for.
    assert body["bytes_read"] <= 4096
    assert body["preview_limited"] is True


# ── Envelope ───────────────────────────────────────────────────────


def test_envelope_round_trips_every_byte_value(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "a.bin").write_bytes(ALL_BYTES)

    _, body = _chunk("a.bin")

    assert _payload(body) == ALL_BYTES


def test_envelope_carries_a_fingerprint_that_changes_with_the_file(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    target = tmp_path / "a.bin"
    target.write_bytes(b"first")
    _, first = _chunk("a.bin")

    target.write_bytes(b"second content")
    _, second = _chunk("a.bin")

    assert first["mtime_hash"]
    assert first["mtime_hash"] != second["mtime_hash"]


def test_response_path_is_served_root_relative(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.bin").write_bytes(b"x")

    _, body = _chunk("sub/a.bin")

    assert body["path"] == "sub/a.bin"
