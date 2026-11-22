"""The bounded readers and the redaction every event summary passes through."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from metabrowser.builtin_plugins.agents import readers
from metabrowser.builtin_plugins.agents.model import DriftCollector, parse_timestamp
from metabrowser.builtin_plugins.agents.readers import EDGE_BYTES, JsonlReader, clip, edge_records


def _write_lines(path: Path, count: int, width: int) -> None:
    """*count* JSON lines of exactly *width* bytes each, the newline included."""

    lines: list[str] = []
    for n in range(1, count + 1):
        body = json.dumps({"n": n, "p": ""})
        pad = "p" * (width - 1 - len(body))
        lines.append(json.dumps({"n": n, "p": pad}))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _numbers(records: list[dict[str, object]]) -> list[object]:
    return [r["n"] for r in records]


def test_edges_of_a_file_just_over_the_edge_size_cut_mid_line(tmp_path: Path) -> None:
    path = tmp_path / "a.jsonl"
    _write_lines(path, 656, 100)  # 65,600 bytes: the tail starts 64 bytes into line 1
    assert path.stat().st_size == 65600 > EDGE_BYTES
    head, tail = edge_records(path)
    assert _numbers(head)[0] == 1 and _numbers(head)[-1] == 655  # line 656 is cut
    assert _numbers(tail)[0] == 2 and _numbers(tail)[-1] == 656  # line 1 is cut


def test_edges_keep_the_first_tail_line_when_the_cut_is_on_a_boundary(tmp_path: Path) -> None:
    path = tmp_path / "a.jsonl"
    _write_lines(path, 1025, 64)  # 65,600 bytes; the tail starts exactly at line 2
    head, tail = edge_records(path)
    assert _numbers(head)[-1] == 1024
    assert _numbers(tail)[0] == 2 and _numbers(tail)[-1] == 1025


def test_edges_of_a_small_file_are_the_whole_file(tmp_path: Path) -> None:
    path = tmp_path / "a.jsonl"
    _write_lines(path, 3, 50)
    head, tail = edge_records(path)
    assert _numbers(head) == _numbers(tail) == [1, 2, 3]


def test_a_truncated_gzip_is_read_as_far_as_it_goes_and_flagged(tmp_path: Path) -> None:
    path = tmp_path / "a.jsonl.gz"
    path.write_bytes(
        gzip.compress(b"".join(json.dumps({"n": n}).encode() + b"\n" for n in range(2000)))
    )
    path.write_bytes(path.read_bytes()[:-20])
    reader = JsonlReader(path)
    records = [r for _, r in reader if r is not None]
    assert 0 < len(records) < 2000
    assert reader.truncated


def test_garbage_gzip_is_flagged_not_raised(tmp_path: Path) -> None:
    path = tmp_path / "a.jsonl.gz"
    path.write_bytes(b"\x1f\x8b\x08\x00 not really gzip data at all")
    reader = JsonlReader(path)
    assert list(reader) == []
    assert reader.truncated


def test_an_oversize_line_is_skipped_without_being_held(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(readers, "MAX_LINE_BYTES", 100)
    path = tmp_path / "a.jsonl"
    path.write_text(
        '{"n": 1}\n' + json.dumps({"n": 2, "p": "x" * 1000}) + '\n{"n": 3}\n', encoding="utf-8"
    )
    assert list(JsonlReader(path)) == [(1, {"n": 1}), (2, None), (3, {"n": 3})]


def test_a_newline_free_stream_hits_the_budget_not_memory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(readers, "MAX_LINE_BYTES", 100)
    path = tmp_path / "a.jsonl.gz"
    path.write_bytes(gzip.compress(b"x" * 10_000))
    reader = JsonlReader(path, budget=1000)
    assert list(reader) == []
    assert reader.truncated


def test_the_byte_budget_stops_a_read(tmp_path: Path) -> None:
    path = tmp_path / "a.jsonl"
    _write_lines(path, 10, 100)
    reader = JsonlReader(path, budget=450)
    assert len(list(reader)) == 4
    assert reader.truncated


def test_deeply_nested_json_is_an_invalid_line_not_a_crash(tmp_path: Path) -> None:
    path = tmp_path / "a.jsonl"
    path.write_text("[" * 200_000 + "\n" + '{"n": 1}\n', encoding="utf-8")
    assert list(JsonlReader(path)) == [(1, None), (2, {"n": 1})]


def test_timestamps_reject_non_finite_numbers() -> None:
    for value in (float("inf"), float("-inf"), float("nan"), 10**400):
        assert parse_timestamp(value) is None
    assert parse_timestamp(1.5) == 1.5
    assert parse_timestamp(1_800_000_000_000) == 1_800_000_000.0


def test_summaries_are_redacted_before_they_are_clipped() -> None:
    cases = {
        "curl -H 'Authorization: Bearer abc.def-123' https://x": "Authorization: [redacted]",
        "run with api_key=sk-abcdef and go": "api_key=[redacted]",
        "export TOKEN='hello world' now": "TOKEN=[redacted]",
        "mytool --password hunter2 --verbose": "--password [redacted]",
        "id " + "a1" * 20: "id [redacted]",
        "blob " + "Ab1" * 20: "blob [redacted]",
    }
    for text, needle in cases.items():
        out = clip(text)
        assert needle in out, (text, out)
        for secret in ("abc.def-123", "sk-abcdef", "hello world", "hunter2", "a1" * 20, "Ab1" * 20):
            assert secret not in out
    # A token that straddles the clip limit does not survive half-cut.
    out = clip("x " * 55 + "token=" + "s3cr3t" * 5)
    assert "s3cr3t" not in out
    # Ordinary text and paths pass through.
    assert (
        clip("ls -l /usr/local/share/some/long/path/name")
        == "ls -l /usr/local/share/some/long/path/name"
    )


def test_a_failed_pragma_is_a_read_error(tmp_path: Path) -> None:
    path = tmp_path / "bad.sqlite"
    path.write_bytes(b"this is not a database" * 100)
    drift = DriftCollector()
    conn = readers.open_readonly(path, drift)
    assert conn is not None
    assert readers.check_table(conn, "db", "t", frozenset(), frozenset({"a"}), drift) is None
    conn.close()
    assert drift.freeze().read_errors == {"db.t": 1}
    assert drift.truncated
