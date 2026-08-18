"""Regression tests for browser static assets."""

from __future__ import annotations

from pathlib import Path


def _browser_app_js() -> str:
    repo_root = Path(__file__).resolve().parents[1]
    return (repo_root / "src" / "metabrowser" / "static" / "app.js").read_text()


def _browser_asset(relative_path: str) -> str:
    repo_root = Path(__file__).resolve().parents[1]
    return (repo_root / "src" / "metabrowser" / relative_path).read_text()


def test_tree_subtree_fetches_remain_depth_bounded() -> None:
    js = _browser_app_js()

    assert "TREE_SUBTREE_FETCH_DEPTH" in js
    assert "&depth=${TREE_SUBTREE_FETCH_DEPTH}" in js


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


def test_generated_html_handlers_keep_their_global_names() -> None:
    """Static analysis cannot see function names embedded in generated HTML."""
    app = _browser_app_js()
    sdk = _browser_asset("static/plugin_sdk.js")
    agent_log = _browser_asset("builtin_plugins/agent_log/index.js")

    # The Load more control moved into the SDK's partial-content notice, so the
    # inline handler is emitted there while the global it names still lives in
    # app.js. That split is exactly what this check exists to catch.
    assert 'loadMoreCurrentText()"' in sdk
    assert "async function loadMoreCurrentText()" in app
    # Header copy/navigation buttons carry paths in data-* attributes
    # consumed by a delegated listener (inline onclick would HTML-decode
    # quotes back into the JavaScript string).
    assert "data-copy-path=" in app
    assert "data-nav-dir=" in app
    assert "function copyPath(btn, path)" in app
    assert "content-copy-btn" in sdk
    assert "_copyDelegationInstalled" in sdk
    assert "function copyContent(btn)" in app
    assert 'onclick="toggleEvent(this)"' in agent_log
    assert "function toggleEvent(header)" in app
