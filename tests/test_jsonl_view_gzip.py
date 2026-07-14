"""Tests for ``.jsonl.gz`` handling in jsonl_view + charts.

The load-bearing concern is logical-size threading: the parser's
large-file caps and the charts cache key must use the *uncompressed*
size. A 1 MB ``.jsonl.gz`` whose decompressed payload is 10 MB is the
"large file" case, not "small file".
"""

from __future__ import annotations

import gzip
from pathlib import Path

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
        def parse_line(self, line: str) -> list[object]:  # noqa: ARG002
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


def test_charts_cache_key_uses_logical_size(tmp_path: Path) -> None:
    """A ``.gz`` and its plain twin (with identical content) get
    *different* cache keys (different paths, different mtime), but each
    key embeds the logical size — verifying the size component is the
    decompressed length, not the disk length, for the .gz."""
    plain, gz = _make_pair(tmp_path, n_events=20)
    plain_key = _cache_key("agent", ArtifactPath(plain))
    gz_key = _cache_key("agent", ArtifactPath(gz))
    assert plain_key is not None
    assert gz_key is not None
    # The size field of the key is the same for both — content-equivalent
    # files should hash on the same logical size, even though disk sizes
    # diverge.
    assert plain_key[3] == gz_key[3]


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
