"""Regression tests for browser static assets."""

from __future__ import annotations

from pathlib import Path


def _browser_app_js() -> str:
    repo_root = Path(__file__).resolve().parents[1]
    return (repo_root / "src" / "metabrowser" / "static" / "app.js").read_text()


def test_tree_subtree_fetches_remain_depth_bounded() -> None:
    js = _browser_app_js()

    assert "TREE_SUBTREE_FETCH_DEPTH" in js
    assert '"&depth=" + TREE_SUBTREE_FETCH_DEPTH' in js


def test_hover_prefetch_skips_expensive_file_types() -> None:
    js = _browser_app_js()

    assert "FILE_PREFETCH_HOVER_DELAY_MS" in js
    assert "FILE_PREFETCH_MAX_CONCURRENT" in js
    # Logical-ext-aware JSONL skip (covers both `.jsonl` and `.jsonl.gz`
    # once the server attaches `data-logical-ext`).
    assert "item.dataset.logicalExt || getExt(path)" in js
    assert 'ext !== ".jsonl"' in js
    assert "AbortController" in js


def test_activity_polling_retired_no_longer_referenced() -> None:
    """Sanity: the SPA no longer schedules /api/activity polls.
    Active-file detection moved to the inventory's background
    ActiveFileTracker (server side) → fs.change ops on
    /api/events → _mirrorActiveFromFsEntry on the client. The
    legacy poll loop and its tunables are gone."""

    js = _browser_app_js()
    assert "setInterval(pollActivity" not in js
    assert "data.poll_interval_ms !== activityPollDelayMs" not in js
