"""Tests for the MtimeCache projection facades.

Each façade caches the result of a heavy compute keyed by the
file's mtime fingerprint. Tests verify:

* First call computes; subsequent calls hit the cache.
* When the file's mtime changes, the cached value is dropped
  and a fresh compute happens.
* When the file vanishes, callers get a domain-appropriate
  empty result without re-raising.
* ``invalidate_path`` drops every cache entry for that path.
* Root-swap clears every cache (``invalidate_all_projection_caches``).

Plugin-defined chart projections are intentionally absent here. Metabrowser
core only caches its built-in agent-log projection.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

from metabrowser.projections import (
    _AGENT_CHARTS_CACHE,
    _PARSE_CACHE,
    extract_agent_charts_cached,
    invalidate_all_projection_caches,
    invalidate_path,
    parse_jsonl_file_cached,
)


def _write_agent_jsonl(path: Path) -> None:
    """Minimal Claude Code agent-log shape for the parser."""
    lines = [
        '{"type":"system","subtype":"init","session_id":"x","model":"claude"}',
        '{"type":"user","message":{"role":"user","content":"hi"}}',
        '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"hi"}]}}',
    ]
    path.write_text("\n".join(lines) + "\n")


def _bump_mtime(path: Path) -> None:
    """Force a fresh mtime so the cache fingerprint diverges."""
    new_ts = path.stat().st_mtime + 1.0
    os.utime(path, (new_ts, new_ts))


def setup_function() -> None:
    invalidate_all_projection_caches()


# ── parse_jsonl_file_cached ────────────────────────────────────


def test_parse_jsonl_caches_on_repeat_call(tmp_path: Path) -> None:
    f = tmp_path / "a.jsonl"
    _write_agent_jsonl(f)

    call_count = 0
    real_fn = __import__("metabrowser.jsonl_view", fromlist=["_parse_jsonl_file"])._parse_jsonl_file

    def _spy(p: Path) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        return real_fn(p)

    with patch("metabrowser.jsonl_view._parse_jsonl_file", side_effect=_spy):
        first = parse_jsonl_file_cached(f)
        second = parse_jsonl_file_cached(f)
    assert call_count == 1, "second call should hit the cache"
    assert first == second


def test_parse_jsonl_invalidates_on_mtime_change(tmp_path: Path) -> None:
    f = tmp_path / "a.jsonl"
    _write_agent_jsonl(f)
    parse_jsonl_file_cached(f)
    _bump_mtime(f)
    # Sanity: the underlying compute is invoked again.
    call_count = 0
    real_fn = __import__("metabrowser.jsonl_view", fromlist=["_parse_jsonl_file"])._parse_jsonl_file

    def _spy(p: Path) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        return real_fn(p)

    with patch("metabrowser.jsonl_view._parse_jsonl_file", side_effect=_spy):
        parse_jsonl_file_cached(f)
    assert call_count == 1


def test_parse_jsonl_returns_empty_for_vanished_file(tmp_path: Path) -> None:
    f = tmp_path / "missing.jsonl"
    out = parse_jsonl_file_cached(f)
    # Empty parse shape, NOT a raise.
    assert out["events"] == []
    assert out["summary"]["total_events"] == 0


# ── invalidate_path drops every cache ─────────────────────────


def test_invalidate_path_drops_all_caches(tmp_path: Path) -> None:
    f = tmp_path / "a.jsonl"
    _write_agent_jsonl(f)
    parse_jsonl_file_cached(f)
    # Manually populate the chart cache to exercise invalidation.
    _AGENT_CHARTS_CACHE.update(f, {"charts": [], "summary": None})
    assert _PARSE_CACHE.read(f).hit is True
    assert _AGENT_CHARTS_CACHE.read(f).hit is True

    invalidate_path(f)

    assert _PARSE_CACHE.read(f).hit is False
    assert _AGENT_CHARTS_CACHE.read(f).hit is False


# Broad invalidation


def test_invalidate_all_projection_caches_clears_state(tmp_path: Path) -> None:
    f = tmp_path / "a.jsonl"
    _write_agent_jsonl(f)
    parse_jsonl_file_cached(f)
    _AGENT_CHARTS_CACHE.update(f, {"charts": [], "summary": None})

    invalidate_all_projection_caches()
    assert len(_PARSE_CACHE.cache) == 0
    assert len(_AGENT_CHARTS_CACHE.cache) == 0


# ── chart-cache façades ────────────────────────────────────────


def test_extract_agent_charts_cached_caches_repeat_call(tmp_path: Path) -> None:
    """Synthetic: short-circuit the underlying extractor and
    verify the wrapper caches the return value by mtime."""

    f = tmp_path / "agent.jsonl"
    _write_agent_jsonl(f)
    call_count = 0

    def _stub(p: Path) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        return {"summary": {}, "charts": [{"label": f"call-{call_count}"}]}

    with patch("metabrowser.charts.extract_agent_charts", side_effect=_stub):
        a = extract_agent_charts_cached(f)
        b = extract_agent_charts_cached(f)
    assert call_count == 1
    assert a == b


def test_extract_agent_charts_cached_returns_none_for_missing(tmp_path: Path) -> None:
    f = tmp_path / "missing.jsonl"
    out = extract_agent_charts_cached(f)
    assert out is None


# ── Performance smoke check ───────────────────────────────────


def test_parse_jsonl_cached_second_call_is_fast(tmp_path: Path) -> None:
    """The whole point of the cache: second call is dominated
    by the deepcopy of the cached value, not a re-parse. On a
    small fixture the threshold is generous; the assertion
    catches the case where the cache is silently bypassed."""

    f = tmp_path / "a.jsonl"
    _write_agent_jsonl(f)

    parse_jsonl_file_cached(f)  # warm
    t0 = time.perf_counter()
    for _ in range(50):
        parse_jsonl_file_cached(f)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    # 50 cache hits should comfortably finish under 100 ms.
    assert elapsed_ms < 100, f"50 warm reads took {elapsed_ms:.1f} ms"
