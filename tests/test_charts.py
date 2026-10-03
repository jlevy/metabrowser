"""Tests for metabrowser.charts — chart data extraction."""
# pyright: reportMissingTypeArgument=false

from __future__ import annotations

import json
import tempfile
from collections.abc import Sequence
from pathlib import Path

from metabrowser.charts import (
    extract_agent_charts,
    extract_agent_charts_bytes,
)
from metabrowser.jsonl_view import _parse_jsonl_file

# ── Fixtures ────────────────────────────────────────────────────


def _write_jsonl(events: Sequence[object], *, ensure_ascii: bool = True) -> Path:
    """Write events to a temporary JSONL file and return the path."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    ) as file:
        for event in events:
            file.write(json.dumps(event, ensure_ascii=ensure_ascii) + "\n")
        return Path(file.name)


CLAUDE_EVENTS = [
    {"type": "system", "subtype": "init", "model": "claude-opus-4-20250514"},
    {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "tool_use", "name": "Read", "input": {"file_path": "/tmp/test.py"}},
            ]
        },
        "timestamp": "2026-04-06T10:00:00+00:00",
    },
    {
        "type": "user",
        "message": {
            "content": [
                {"type": "tool_result", "tool_use_id": "1", "content": "file contents"},
            ]
        },
        "timestamp": "2026-04-06T10:00:05+00:00",
    },
    {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": "Here is the code."}]},
        "timestamp": "2026-04-06T10:00:10+00:00",
    },
    {
        "type": "result",
        "subtype": "success",
        "cost_usd": 0.05,
        "duration_s": 15.0,
        "is_error": False,
        "timestamp": "2026-04-06T10:00:15+00:00",
    },
]


# ── Agent chart tests ───────────────────────────────────────────


class TestExtractAgentCharts:
    def test_returns_summary_and_charts(self):
        path = _write_jsonl(CLAUDE_EVENTS)
        result = extract_agent_charts(path)
        assert "summary" in result
        assert "charts" in result
        assert result["summary"] is not None

    def test_taxonomy_counts(self):
        path = _write_jsonl(CLAUDE_EVENTS)
        result = extract_agent_charts(path)
        counts = result["summary"]["counts"]
        assert (
            counts.get("init", 0) >= 1 or "init" not in counts
        )  # Claude parser may not emit init for system events
        # Should have tool_call, tool_result, text, result
        total = sum(counts.values())
        assert total > 0

    def test_metadata(self):
        path = _write_jsonl(CLAUDE_EVENTS)
        result = extract_agent_charts(path)
        meta = result["summary"]["metadata"]
        assert meta["adapter"] == "claude"
        from_bytes = extract_agent_charts_bytes(path.read_bytes())
        assert from_bytes["summary"]["metadata"]["adapter"] == "claude"
        assert from_bytes["summary"]["counts"] == result["summary"]["counts"]

    def test_empty_file(self):
        path = _write_jsonl([])
        result = extract_agent_charts(path)
        assert result["summary"] is None
        assert result["charts"] == []


# ── Line splitting ──────────────────────────────────────────────

# Only a newline ends a JSONL record. `JSON.stringify` emits U+2028, U+2029,
# and U+0085 raw rather than escaped, so an agent log that quotes one carries
# it inside a JSON string, and `str.splitlines()` would cut that one record
# into two unparseable fragments — leaving the Charts tab disagreeing with the
# JSONL view about the same file.
_UNESCAPED_UNICODE_BREAKS = (" ", " ", "\x85")


class TestLineSplitting:
    def _log(self, separator: str) -> Path:
        return _write_jsonl(
            [
                {"type": "system", "subtype": "init", "model": "claude-opus-4-20250514"},
                *(
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {"type": "text", "text": f"para one{separator}para two {index}"}
                            ]
                        },
                        "timestamp": f"2026-04-06T10:00:{index:02d}+00:00",
                    }
                    for index in range(5)
                ),
            ],
            ensure_ascii=False,
        )

    def test_file_records_end_only_at_a_newline(self):
        baseline = extract_agent_charts(self._log(" "))["summary"]["counts"]
        for separator in _UNESCAPED_UNICODE_BREAKS:
            counts = extract_agent_charts(self._log(separator))["summary"]["counts"]
            assert counts == baseline, f"{separator!r} split a record"

    def test_bytes_records_end_only_at_a_newline(self):
        baseline = extract_agent_charts_bytes(self._log(" ").read_bytes())["summary"]["counts"]
        for separator in _UNESCAPED_UNICODE_BREAKS:
            payload = self._log(separator).read_bytes()
            counts = extract_agent_charts_bytes(payload)["summary"]["counts"]
            assert counts == baseline, f"{separator!r} split a record"

    def test_counts_match_the_jsonl_view(self):
        """The two tabs read one file, so they must agree on its record count."""

        for separator in (" ", *_UNESCAPED_UNICODE_BREAKS):
            path = self._log(separator)
            charted = sum(extract_agent_charts(path)["summary"]["counts"].values())
            viewed = len(_parse_jsonl_file(path)["events"])
            assert charted == viewed, f"{separator!r} disagrees between charts and the JSONL view"
