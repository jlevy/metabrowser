"""Chart data extraction for the browser — generic agent-log shapes only.

Third-party plugins can supply chart data hooks for their own file kinds.
MetaBrowser core only knows the generic agent-log adapters (Claude, Gemini,
and Pi).

Memoization
-----------

Chart extraction re-parses the entire JSONL log on every call and runs at
~150–220 ms warm on a 38 MB log. The browser hits this every time the user
clicks the Charts tab, including repeats on the same unchanged file. We cache
the result keyed on ``(kind, path, mtime_ns, size)``: the key changes the
moment a single byte is appended. Bounded LRU because chart payloads are
small but a long session could accumulate hundreds.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from cachetools import LRUCache

from metabrowser import jsonl_view
from metabrowser.gz_io import ArtifactPath
from metabrowser.logutil.parsing import LogEvent, create_parser, detect_adapter

# ── Memoization ──────────────────────────────────────────────────

# Bigger than ``_IGNORE_CACHE`` (64) because a long session can touch
# many distinct chart files; smaller than the file content cache (30
# entries × MB-each) because chart payloads are KB-each.
_CHARTS_CACHE_MAX = 128

_CHARTS_CACHE: LRUCache[tuple[str, str, int, int], dict[str, Any]] = LRUCache(
    maxsize=_CHARTS_CACHE_MAX
)


def _cache_key(kind: str, artifact: ArtifactPath) -> tuple[str, str, int, int] | None:
    """Return a (kind, path, mtime_ns, disk_size) tuple, or None if the file vanished.

    Stating once per call is cheap; the key changes on any append so the
    memo invalidates automatically as a live JSONL grows.
    """
    try:
        st = artifact.disk_path.stat()
    except OSError:
        return None
    return (kind, str(artifact.disk_path), st.st_mtime_ns, st.st_size)


def clear_charts_cache() -> None:
    """Drop every memoized chart payload. Wired into the browser's
    ``_clear_browser_caches`` reset for the offline bench harness."""
    _CHARTS_CACHE.clear()


# ── Agent log chart extraction ────────────────────────────────────


def extract_agent_charts(filepath: Path) -> dict[str, Any]:
    """Extract chart data from an agent JSONL log file (Claude/Gemini/Pi).

    Transparently handles compressed JSONL via :class:`ArtifactPath`.
    Returns ``{summary: {counts, metadata}, charts: [...]}``.
    """
    artifact = ArtifactPath(filepath)
    parse_max_bytes = jsonl_view._JSONL_PARSE_MAX_BYTES
    if not artifact.is_compressed and artifact.logical_size > parse_max_bytes:
        raise jsonl_view.JsonlParseLimitError(
            f"JSONL content exceeds {parse_max_bytes} decompressed bytes"
        )
    key = _cache_key("agent", artifact)
    if key is not None:
        hit = _CHARTS_CACHE.get(key)
        if hit is not None:
            return hit

    # Read first lines to detect adapter
    first_lines: list[str] = []
    with artifact.open_text(errors="replace", max_output_bytes=parse_max_bytes) as fh:
        for raw_line in fh:
            stripped = raw_line.strip()
            if stripped:
                first_lines.append(stripped)
            if len(first_lines) >= 20:
                break

    adapter = detect_adapter(first_lines)
    parser = create_parser(adapter)

    # Parse all events
    events: list[LogEvent] = []
    with artifact.open_text(errors="replace", max_output_bytes=parse_max_bytes) as fh:
        for raw_line in fh:
            stripped = raw_line.strip()
            if not stripped or len(stripped) > 256 * 1024:
                continue
            events.extend(parser.parse_line(stripped))
    events.extend(parser.flush())

    if not events:
        result: dict[str, Any] = {"summary": None, "charts": []}
        if key is not None:
            _CHARTS_CACHE[key] = result
        return result

    counts = _agent_taxonomy_counts(events)
    metadata = _agent_metadata(events, adapter)
    charts = _agent_chart_specs(events)

    result = {
        "summary": {"counts": counts, "metadata": metadata},
        "charts": charts,
    }
    if key is not None:
        _CHARTS_CACHE[key] = result
    return result


def _agent_taxonomy_counts(events: list[LogEvent]) -> dict[str, int]:
    """Map each agent log event to a taxonomy path and return aggregated counts."""
    counts: dict[str, int] = {}
    for ev in events:
        path = _agent_taxonomy_path(ev)
        if path:
            counts[path] = counts.get(path, 0) + 1
    return counts


def _agent_taxonomy_path(ev: LogEvent) -> str | None:
    """Map a single agent LogEvent to its taxonomy path."""
    kind = ev.kind
    if kind == "init":
        return "init"
    if kind == "tool_call":
        # Extract tool name from raw event data or summary text
        raw = ev.raw if isinstance(ev.raw, dict) else {}
        tool_name = (
            raw.get("tool_name")
            or raw.get("toolName")
            or raw.get("name")
            or _extract_tool_name(ev.summary)
        )
        return f"tool_call/{tool_name}" if tool_name else "tool_call/unknown"
    if kind == "tool_result":
        return "tool_result/error" if ev.is_error else "tool_result/success"
    if kind == "text":
        return "text"
    if kind == "thinking":
        return "thinking"
    if kind == "result":
        return "result/failed" if ev.is_error else "result/done"
    if kind == "system":
        return "system"
    if kind == "raw":
        return "raw"
    return None


def _extract_tool_name(summary: str) -> str:
    """Extract tool name from a summary string.

    Handles patterns like:
    - ``[tool_call] Read /path``  (Claude)
    - ``[call:Read] path=...``  (Pi)
    - ``-> Read file``  (Gemini)
    """
    # Pi format: [call:ToolName]
    m = re.match(r"\[call:([^\]]+)\]", summary)
    if m:
        return m.group(1)
    # Claude format: [tool_call] ToolName ...
    for prefix in ("[tool_call] ", "\u2192 "):
        if prefix in summary:
            rest = summary.split(prefix, 1)[1]
            parts = rest.split(None, 1)
            if parts:
                return parts[0]
    return "unknown"


def _agent_metadata(events: list[LogEvent], adapter: str) -> dict[str, Any]:
    """Extract metadata from agent log events."""
    metadata: dict[str, Any] = {"adapter": adapter}

    for ev in events:
        if ev.kind == "init":
            raw = ev.raw if isinstance(ev.raw, dict) else {}
            model = raw.get("model")
            if model:
                metadata["model"] = model
        if ev.kind == "result":
            if ev.cost_usd is not None:
                metadata["cost"] = f"${ev.cost_usd:.2f}"
            if ev.duration_s is not None:
                total_s = int(ev.duration_s)
                mins = total_s // 60
                secs = total_s % 60
                metadata["duration"] = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"

    return metadata


def _agent_chart_specs(events: list[LogEvent]) -> list[dict[str, Any]]:
    """Build event activity chart for agent logs as stacked bars."""
    timestamped = [(ev, ev.timestamp) for ev in events if ev.timestamp]
    if len(timestamped) < 2:
        return []

    # Determine time range and bin size
    try:
        times = [datetime.fromisoformat(ts) for _, ts in timestamped]
    except (ValueError, TypeError):
        return []

    t0 = min(times)
    t1 = max(times)
    duration_s = max(1, int((t1 - t0).total_seconds()))
    bin_s = max(10, min(300, duration_s // 40))

    # Group events into bins by kind. Colors are CSS-var sentinels —
    # app.js resolveColor() substitutes computed values before Chart.js
    # consumes the spec (canvas can't resolve var() itself).
    kind_colors = {
        "tool_call": "var(--chart-series-info)",
        "tool_result": "var(--chart-series-info-soft)",
        "text": "var(--chart-series-success)",
        "thinking": "var(--chart-series-thinking)",
        "result": "var(--chart-series-result)",
        "init": "var(--chart-series-init)",
        "system": "var(--chart-series-system)",
    }
    # Collect event kinds present
    kinds_present: list[str] = []
    for ev, _ in timestamped:
        if ev.kind not in kinds_present:
            kinds_present.append(ev.kind)

    # Build bins
    num_bins = max(1, duration_s // bin_s + 1)
    bins_by_kind: dict[str, list[int]] = {k: [0] * num_bins for k in kinds_present}

    for ev, ts_str in timestamped:
        try:
            t = datetime.fromisoformat(ts_str)
            bin_idx = min(int((t - t0).total_seconds()) // bin_s, num_bins - 1)
            if ev.kind in bins_by_kind:
                bins_by_kind[ev.kind][bin_idx] += 1
        except (ValueError, TypeError):
            continue

    # Build bin timestamps
    bin_times = []
    for i in range(num_bins):
        bt = t0.replace(tzinfo=UTC) if t0.tzinfo is None else t0
        bt = bt + timedelta(seconds=i * bin_s)
        bin_times.append(bt.isoformat())

    # Build series
    series = []
    for kind in kinds_present:
        if kind == "raw":
            continue
        color = kind_colors.get(kind, "var(--chart-series-init)")
        data = [{"x": bin_times[j], "y": bins_by_kind[kind][j]} for j in range(num_bins)]
        series.append({"label": kind, "color": color, "data": data})

    if not series:
        return []

    return [
        {
            "id": "event-activity",
            "title": "Event Activity",
            "type": "stacked-bar",
            "x_type": "time",
            "y_label": "events",
            "bin_seconds": bin_s,
            "series": series,
        }
    ]
