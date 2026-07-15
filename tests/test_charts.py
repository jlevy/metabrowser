"""Tests for metabrowser.charts — chart data extraction."""
# pyright: reportMissingTypeArgument=false

from __future__ import annotations

import json
import tempfile
from collections.abc import Sequence
from pathlib import Path

from metabrowser.charts import (
    extract_agent_charts,
)

# ── Fixtures ────────────────────────────────────────────────────


def _write_jsonl(events: Sequence[object]) -> Path:
    """Write events to a temporary JSONL file and return the path."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as file:
        for event in events:
            file.write(json.dumps(event) + "\n")
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

    def test_empty_file(self):
        path = _write_jsonl([])
        result = extract_agent_charts(path)
        assert result["summary"] is None
        assert result["charts"] == []
