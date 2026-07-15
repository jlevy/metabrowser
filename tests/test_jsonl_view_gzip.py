"""Tests for ``.jsonl.gz`` handling in jsonl_view + charts.

The load-bearing concern is logical-size threading: the parser's
large-file caps and the charts cache key must use the *uncompressed*
size. A 1 MB ``.jsonl.gz`` whose decompressed payload is 10 MB is the
"large file" case, not "small file".
"""

from __future__ import annotations

import asyncio
import gzip
import json
import zlib
from pathlib import Path

import pytest

from metabrowser import jsonl_view, server
from metabrowser.builtin_plugins.agent_log.sidekick import charts_handler
from metabrowser.charts import _cache_key, extract_agent_charts
from metabrowser.gz_io import ArtifactPath
from metabrowser.jsonl_view import _LARGE_FILE_BYTES, _parse_jsonl_file

# Repetitive Claude-format events: compresses to ~3% so we can comfortably
# cross the 2 MiB large-file threshold while keeping the on-disk file
# small enough for fast tests.
_CLAUDE_EVENT = (
    '{"type":"assistant","message":{"role":"assistant","content":'
    '[{"type":"text","text":"' + ("xx " * 3000) + '"}]}}'
)


def _make_pair(tmp_path: Path, n_events: int) -> tuple[Path, Path]:
    """Write events.jsonl + events.jsonl.gz with `n_events` events."""
    body = ("\n".join([_CLAUDE_EVENT] * n_events) + "\n").encode("utf-8")
    plain = tmp_path / "events.jsonl"
    plain.write_bytes(body)
    gz = tmp_path / "events.jsonl.gz"
    with gzip.open(gz, "wb") as fh:
        fh.write(body)
    return plain, gz


def test_parse_jsonl_file_handles_gzip_transparently(tmp_path: Path) -> None:
    """Same content, two on-disk encodings → same parsed event count."""
    plain, gz = _make_pair(tmp_path, n_events=30)
    plain_result = _parse_jsonl_file(plain)
    gz_result = _parse_jsonl_file(gz)
    assert plain_result["summary"]["total_events"] == gz_result["summary"]["total_events"]
    assert plain_result["events"] == gz_result["events"]


def test_parse_jsonl_file_degrades_line_parser_exceptions(tmp_path: Path, monkeypatch) -> None:
    """A parser bug in one line should become a warning event, not abort the file."""

    class BrokenParser:
        def parse_line(self, line: str) -> list[object]:
            raise RuntimeError("bad parser")

        def flush(self) -> list[object]:
            return []

    monkeypatch.setattr("metabrowser.jsonl_view.create_parser", lambda adapter: BrokenParser())
    log = tmp_path / "events.jsonl"
    log.write_text('{"type":"thread.started","thread_id":"abc"}\n')

    result = _parse_jsonl_file(log)

    assert result["summary"]["parse_errors"] == 1
    assert "kept rendering" in result["summary"]["warning"]
    assert result["events"][0]["summary"].startswith("[parse_error] line 1:")


def test_parse_jsonl_file_uses_logical_size_for_large_file_gate(tmp_path: Path) -> None:
    """A small .gz on disk whose decompressed payload exceeds the
    large-file threshold should engage the per-event raw cap.

    Without logical-size threading the parser would use the compressed
    on-disk size, miss the threshold, and ship full per-event raw
    payloads — the very behavior the cap exists to prevent.
    """
    # ~9 KB per event * ~250 = ~2.2 MB uncompressed (over the 2 MiB cap)
    # Real on-disk size after gzip is ~50-100 KB.
    n_events = 250
    _, gz = _make_pair(tmp_path, n_events)
    artifact = ArtifactPath(gz)
    assert artifact.disk_size < _LARGE_FILE_BYTES, "fixture should be small on disk"
    assert artifact.logical_size > _LARGE_FILE_BYTES, "fixture should be large logically"

    result = _parse_jsonl_file(gz)
    # bytes_read reflects the logical size, not the compressed disk size.
    assert result["bytes_read"] == artifact.logical_size


def test_charts_cache_key_uses_safe_disk_fingerprint(tmp_path: Path) -> None:
    plain, gz = _make_pair(tmp_path, n_events=20)
    plain_key = _cache_key("agent", ArtifactPath(plain))
    gz_key = _cache_key("agent", ArtifactPath(gz))
    assert plain_key is not None
    assert gz_key is not None
    assert plain_key[3] == plain.stat().st_size
    assert gz_key[3] == gz.stat().st_size


def test_extract_agent_charts_handles_gzip(tmp_path: Path) -> None:
    """End-to-end: chart extraction works on a ``.jsonl.gz``."""
    _, gz = _make_pair(tmp_path, n_events=20)
    result = extract_agent_charts(gz)
    # The fixture has assistant events but no init/result; charts
    # extractor should still return a structured envelope without
    # raising. The exact chart shape depends on the analyzer; we just
    # assert the contract holds.
    assert "summary" in result
    assert "charts" in result


class _Params:
    def __init__(self, path: str) -> None:
        self._path = path

    def get(self, key: str, default: str = "") -> str:
        return self._path if key == "path" else default


class _Request:
    def __init__(self, path: str) -> None:
        self.query_params = _Params(path)


def test_charts_endpoint_rejects_gzip_and_zlib_over_actual_decoded_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = (json.dumps({"type": "result", "subtype": "success"}) + "\n").encode() * 4
    gzip_bytes = bytearray(gzip.compress(payload))
    gzip_bytes[-4:] = (1).to_bytes(4, "little")
    (tmp_path / "forged.jsonl.gz").write_bytes(gzip_bytes)
    (tmp_path / "large.jsonl.zlib").write_bytes(zlib.compress(payload))
    monkeypatch.setattr(jsonl_view, "_JSONL_PARSE_MAX_BYTES", 64)
    server._set_root_dir(tmp_path)

    for name in ("forged.jsonl.gz", "large.jsonl.zlib"):
        response = asyncio.run(
            charts_handler(_Request(name))  # pyright: ignore[reportArgumentType]
        )
        assert response.status_code == 413
        body = json.loads(bytes(response.body))
        assert "64" in body["error"]
