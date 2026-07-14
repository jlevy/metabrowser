"""Regression tests for the v2 browser scalability work.

Locks in the browser scalability contract:

* charts memo invalidates on mtime/size change;
* ``/api/file`` emits a strong ETag and honours ``If-None-Match`` with
  a 304-no-body response;
* the SSE tail emits an ``append`` event for newly-written lines.

Tests drive the handlers via duck-typed Request objects to avoid
pulling httpx in. This matches the broader pattern in this test suite.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, cast

from metabrowser import server as proc_browser
from metabrowser import sse
from metabrowser.charts import _CHARTS_CACHE, extract_agent_charts
from metabrowser.sse import _tail_jsonl


class _FakeHeaders:
    def __init__(self, data: dict[str, str]) -> None:
        self._data = {k.lower(): v for k, v in data.items()}

    def get(self, key: str, default: str = "") -> str:
        return self._data.get(key.lower(), default)


class _FakeRequest:
    def __init__(self, query: dict[str, str], headers: dict[str, str] | None = None) -> None:
        self.query_params = _FakeQuery(query)
        self.headers = _FakeHeaders(headers or {})


class _FakeQuery:
    def __init__(self, data: dict[str, str]) -> None:
        self._data = data

    def get(self, key: str, default: str = "") -> str:
        return self._data.get(key, default)


# ── Charts memoization ──────────────────────────────────────────


_CLAUDE_SAMPLE = (
    json.dumps(
        {
            "type": "system",
            "subtype": "init",
            "model": "claude-opus-4-7",
            "session_id": "abc",
            "timestamp": "2026-04-24T12:00:00Z",
        }
    )
    + "\n"
    + json.dumps(
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "total_cost_usd": 0.5,
            "duration_ms": 1000,
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "timestamp": "2026-04-24T12:00:01Z",
        }
    )
    + "\n"
)


def test_charts_cache_returns_same_payload_on_repeat(tmp_path: Path) -> None:
    """Second call against an unmodified file is a cache hit — same dict
    object identity confirms we did not re-parse."""
    _CHARTS_CACHE.clear()
    log = tmp_path / "log.jsonl"
    log.write_text(_CLAUDE_SAMPLE)

    first = extract_agent_charts(log)
    second = extract_agent_charts(log)
    assert first is second, "expected charts cache hit on repeat call"


def test_charts_cache_invalidates_when_file_grows(tmp_path: Path) -> None:
    """Appending to the file changes its (mtime_ns, size) key; the next
    call must re-parse and produce a payload reflecting the new content."""
    _CHARTS_CACHE.clear()
    log = tmp_path / "log.jsonl"
    log.write_text(_CLAUDE_SAMPLE)
    first = extract_agent_charts(log)
    first_count = first["summary"]["counts"].get("init", 0)

    # Append another init event. Sleep slightly so mtime_ns is guaranteed
    # to advance on filesystems with coarser-than-nanosecond mtime
    # granularity (most modern Linux is fine, but the guard is cheap).
    time.sleep(0.01)
    extra = json.dumps(
        {
            "type": "system",
            "subtype": "init",
            "model": "claude-opus-4-7",
            "session_id": "def",
            "timestamp": "2026-04-24T12:00:02Z",
        }
    )
    with log.open("a") as fh:
        fh.write(extra + "\n")

    second = extract_agent_charts(log)
    assert second is not first, "expected cache miss after file changed"
    assert second["summary"]["counts"].get("init", 0) == first_count + 1


# ── ETag / 304 on /api/file ─────────────────────────────────────


def test_etag_is_stable_for_unchanged_file_hash() -> None:
    """Browser-server restarts should not change ETags for unchanged files."""
    assert proc_browser._etag_for("abc123") == '"abc123"'


def test_api_file_emits_etag_header_and_304s_on_match(tmp_path: Path) -> None:
    """Round-trip: first GET returns ETag; second GET with that ETag in
    If-None-Match must return 304 with no body."""
    fixture = tmp_path / "doc.md"
    fixture.write_text("# hello\n")
    proc_browser._set_root_dir(tmp_path)
    try:
        # First call: no If-None-Match → 200 + body + ETag header.
        first = asyncio.run(proc_browser.api_file(cast(Any, _FakeRequest({"path": "doc.md"}))))
        etag = first.headers.get("etag")
        assert first.status_code == 200
        assert etag, "api_file must emit an ETag header"
        assert bytes(first.body), "200 must have a body"

        # Second call: matching If-None-Match → 304 + empty body.
        second = asyncio.run(
            proc_browser.api_file(
                cast(Any, _FakeRequest({"path": "doc.md"}, {"If-None-Match": etag}))
            )
        )
        assert second.status_code == 304
        assert bytes(second.body) == b"", "304 must have an empty body"

        # Third call: stale ETag → 200 with fresh body (server doesn't
        # short-circuit on a non-matching token).
        third = asyncio.run(
            proc_browser.api_file(
                cast(Any, _FakeRequest({"path": "doc.md"}, {"If-None-Match": '"stale"'}))
            )
        )
        assert third.status_code == 200
        assert bytes(third.body)
    finally:
        proc_browser._set_root_dir(Path())


def test_api_file_etag_changes_when_file_changes(tmp_path: Path) -> None:
    """A modification must invalidate the ETag — otherwise the client
    keeps the stale cached payload forever."""
    fixture = tmp_path / "doc.md"
    fixture.write_text("# v1\n")
    proc_browser._set_root_dir(tmp_path)
    try:
        first = asyncio.run(proc_browser.api_file(cast(Any, _FakeRequest({"path": "doc.md"}))))
        first_etag = first.headers.get("etag")
        time.sleep(0.01)
        fixture.write_text("# v2 with more content\n")
        second = asyncio.run(proc_browser.api_file(cast(Any, _FakeRequest({"path": "doc.md"}))))
        second_etag = second.headers.get("etag")
        assert first_etag != second_etag, "ETag must change when file content changes"

        third = asyncio.run(
            proc_browser.api_file(
                cast(Any, _FakeRequest({"path": "doc.md"}, {"If-None-Match": first_etag or ""}))
            )
        )
        assert third.status_code == 200
        assert bytes(third.body)
    finally:
        proc_browser._set_root_dir(Path())


def test_api_file_windows_large_text_initial_payload(tmp_path: Path) -> None:
    """Large text files should not be sent wholesale on first preview."""
    content = "a" * (proc_browser._TEXT_PREVIEW_CHUNK_BYTES + 123)
    fixture = tmp_path / "big.yaml"
    fixture.write_text(content)
    proc_browser._set_root_dir(tmp_path)
    try:
        resp = asyncio.run(proc_browser.api_file(cast(Any, _FakeRequest({"path": "big.yaml"}))))
        payload = json.loads(bytes(resp.body))
        assert payload["type"] == "text"
        assert payload["content_truncated"] is True
        assert payload["highlight_disabled"] is True
        assert payload["bytes_read"] == proc_browser._TEXT_PREVIEW_CHUNK_BYTES
        assert len(payload["content"]) == proc_browser._TEXT_PREVIEW_CHUNK_BYTES
    finally:
        proc_browser._set_root_dir(Path())


def test_api_file_codex_turn_completed_without_usage_helper_crash(tmp_path: Path) -> None:
    """Standalone metabrowser parses Codex terminal events without optional plugins."""
    fixture = tmp_path / "codex.jsonl"
    fixture.write_text(
        '{"type":"thread.started","thread_id":"019e2507-3953"}\n'
        "Reading additional input from stdin...\n"
        '{"type":"turn.completed","usage":{"input_tokens":1686052,'
        '"cached_input_tokens":1465472,"output_tokens":10890}}\n'
    )
    proc_browser._set_root_dir(tmp_path)
    try:
        resp = asyncio.run(proc_browser.api_file(cast(Any, _FakeRequest({"path": "codex.jsonl"}))))
        body = json.loads(resp.body)
        assert resp.status_code == 200
        assert body["type"] == "jsonl"
        assert body["summary"]["adapter"] == "codex"
        assert any(
            event["summary"] == "[result] DONE input=1686052 output=10890 cached=1465472"
            for event in body["events"]
        )
    finally:
        proc_browser._set_root_dir(Path())


def test_api_file_internal_error_degrades_to_error_view(tmp_path: Path, monkeypatch) -> None:
    """Unexpected /api/file exceptions should render an error payload, not HTTP 500."""
    fixture = tmp_path / "broken.jsonl"
    fixture.write_text('{"type":"thread.started","thread_id":"abc"}\n')

    def _raise(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("boom")

    monkeypatch.setattr("metabrowser.projections.parse_jsonl_file_cached", _raise)
    proc_browser._set_root_dir(tmp_path)
    try:
        resp = asyncio.run(proc_browser.api_file(cast(Any, _FakeRequest({"path": "broken.jsonl"}))))
        body = json.loads(resp.body)
        assert resp.status_code == 200
        assert body["type"] == "error"
        assert "Internal error while rendering this file" in body["error"]
        assert "RuntimeError: boom" in body["error"]
        assert "server 500" in body["warning"]
    finally:
        proc_browser._set_root_dir(Path())


def test_api_file_large_text_chunk_ignores_matching_etag(tmp_path: Path) -> None:
    """Load-more chunk requests need a body even when the file ETag matches."""
    content = "a" * proc_browser._TEXT_PREVIEW_CHUNK_BYTES + "tail"
    fixture = tmp_path / "big.yaml"
    fixture.write_text(content)
    proc_browser._set_root_dir(tmp_path)
    try:
        first = asyncio.run(proc_browser.api_file(cast(Any, _FakeRequest({"path": "big.yaml"}))))
        etag = first.headers.get("etag")
        assert etag is not None
        resp = asyncio.run(
            proc_browser.api_file(
                cast(
                    Any,
                    _FakeRequest(
                        {
                            "path": "big.yaml",
                            "offset": str(proc_browser._TEXT_PREVIEW_CHUNK_BYTES),
                            "limit": "16",
                        },
                        {"If-None-Match": etag},
                    ),
                )
            )
        )
        payload = json.loads(bytes(resp.body))
        assert resp.status_code == 200
        assert payload["type"] == "text_chunk"
        assert payload["content"] == "tail"
        assert payload["content_truncated"] is False
    finally:
        proc_browser._set_root_dir(Path())


# ── SSE tail (sse.py) ──────────────────────────────────────────


def test_sse_tail_emits_append_for_appended_lines(tmp_path: Path) -> None:
    """Drive the async generator directly; write 20 lines so the
    detection threshold trips, then assert an ``append`` frame fires."""

    log = tmp_path / "live.jsonl"
    # Pre-write 20 init lines — enough to trip detection and emit the
    # initial batch on the first cycle.
    lines = [
        json.dumps(
            {
                "type": "system",
                "subtype": "init",
                "model": "claude-opus-4-7",
                "session_id": f"s{i}",
                "timestamp": f"2026-04-24T12:00:{i:02d}Z",
            }
        )
        for i in range(20)
    ]
    log.write_text("\n".join(lines) + "\n")

    async def collect_first_batch() -> bytes:
        gen = _tail_jsonl(log, 0)
        # First non-comment frame should be the append batch. Cap how
        # long we wait so a regression that fails to emit doesn't hang
        # the test.
        async with asyncio.timeout(2.0):
            async for frame in gen:
                if frame.startswith(b"event: append"):
                    return frame
        return b""

    frame = asyncio.run(collect_first_batch())
    assert frame.startswith(b"event: append"), "expected an append frame on first cycle"
    # Frame format: "event: append\ndata: {...}\n\n"
    data_line = frame.split(b"\n", 2)[1]
    assert data_line.startswith(b"data: ")
    payload: dict[str, Any] = json.loads(data_line[len(b"data: ") :])
    assert payload["adapter"] == "claude"
    assert payload["cursor"] > 0
    assert payload["events"], "append frame must carry parsed events"


def test_sse_tail_streams_single_append_after_initial_cursor(tmp_path: Path) -> None:
    """When the browser opens SSE after the initial /api/file parse, the
    cursor is already at EOF. One newly-appended line must still stream
    immediately rather than waiting for 20 additional lines."""

    log = tmp_path / "live-after-open.jsonl"
    lines = [
        json.dumps(
            {
                "type": "system",
                "subtype": "init",
                "model": "claude-opus-4-7",
                "session_id": f"s{i}",
                "timestamp": f"2026-04-24T12:01:{i:02d}Z",
            }
        )
        for i in range(20)
    ]
    log.write_text("\n".join(lines) + "\n")
    cursor = log.stat().st_size

    async def collect_single_append() -> bytes:
        gen = _tail_jsonl(log, cursor)

        async def append_one_line() -> None:
            await asyncio.sleep(0.1)
            with log.open("a") as fh:
                fh.write(
                    json.dumps(
                        {
                            "type": "result",
                            "subtype": "success",
                            "is_error": False,
                            "timestamp": "2026-04-24T12:01:21Z",
                        }
                    )
                    + "\n"
                )

        append_task = asyncio.create_task(append_one_line())
        try:
            async with asyncio.timeout(2.0):
                async for frame in gen:
                    if frame.startswith(b"event: append"):
                        return frame
        finally:
            await append_task
        return b""

    frame = asyncio.run(collect_single_append())
    assert frame.startswith(b"event: append"), "single appended line should stream"
    payload: dict[str, Any] = json.loads(frame.split(b"\n", 2)[1][len(b"data: ") :])
    assert payload["adapter"] == "claude"
    assert len(payload["events"]) == 1
    assert payload["events"][0]["kind"] == "result"


def test_sse_tail_detects_short_paused_file_after_grace(tmp_path: Path, monkeypatch: Any) -> None:
    """Short logs should emit after a grace period instead of waiting forever for 20 lines."""

    monkeypatch.setattr(sse, "_ADAPTER_DETECTION_GRACE_S", 0.05)
    monkeypatch.setattr(sse, "_TAIL_POLL_INTERVAL_S", 0.02)
    log = tmp_path / "short-live.jsonl"
    log.write_text(_CLAUDE_SAMPLE)

    async def collect_short_file_batch() -> bytes:
        gen = sse._tail_jsonl(log, 0)
        async with asyncio.timeout(1.0):
            async for frame in gen:
                if frame.startswith(b"event: append"):
                    return frame
        return b""

    frame = asyncio.run(collect_short_file_batch())
    assert frame.startswith(b"event: append"), "short paused file should stream"
    payload: dict[str, Any] = json.loads(frame.split(b"\n", 2)[1][len(b"data: ") :])
    assert payload["adapter"] == "claude"
    assert payload["events"], "short-file fallback must replay buffered events"


def test_sse_tail_closes_on_file_disappearance(tmp_path: Path) -> None:
    """If the file disappears mid-stream, the generator emits a
    ``closed`` frame and returns rather than spinning forever on
    OSError."""

    log = tmp_path / "ghost.jsonl"
    log.write_text("{}\n")

    async def collect_until_close() -> bytes:
        gen = _tail_jsonl(log, 0)
        # Delete the file before the second poll cycle.
        log.unlink()
        async with asyncio.timeout(3.0):
            async for frame in gen:
                if frame.startswith(b"event: closed"):
                    return frame
        return b""

    frame = asyncio.run(collect_until_close())
    assert frame.startswith(b"event: closed"), "expected closed frame after file vanished"


# ── Client-side markdown safety ─────────────────────────────────


def test_markdown_plugin_has_no_duplicate_client_renderer() -> None:
    plugin_js = (
        proc_browser.STATIC_DIR.parent / "builtin_plugins" / "markdown" / "index.js"
    ).read_text()
    assert "DOMPurify" not in plugin_js
    assert "marked.parse(" not in plugin_js
    assert "fetchKpressRender" in plugin_js


def test_index_omits_duplicate_markdown_runtime() -> None:
    html = bytes(asyncio.run(proc_browser.index(cast(Any, _FakeRequest({})))).body).decode()
    assert "dompurify" not in html.lower()
    assert "marked.min.js" not in html


def test_live_stream_append_code_appends_at_log_tail() -> None:
    """Live rows should appear after existing log rows, not after the filter bar."""
    app_js = proc_browser.STATIC_DIR.joinpath("app.js").read_text()
    assert "logPane.insertAdjacentHTML('beforeend', tail)" in app_js
    assert "insertAdjacentHTML('afterend', tail)" not in app_js
    assert 'logPane && logPane.style.display !== "none"' in app_js


def test_client_file_cache_eviction_cleans_file_metadata() -> None:
    """fileETags and fileNeedsRevalidate must be bounded with fileCache."""
    app_js = proc_browser.STATIC_DIR.joinpath("app.js").read_text()
    assert "function evictFileCacheMetadata(path)" in app_js
    assert "fileETags.delete(path)" in app_js
    assert "fileNeedsRevalidate.delete(path)" in app_js
    assert "cachePut(fileCache, path, data, CACHE_MAX, evictFileCacheMetadata)" in app_js


def test_client_tree_pagination_state_clears_on_root_render() -> None:
    """Root tree reloads should drop stale deferred pagination batches."""
    app_js = proc_browser.STATIC_DIR.joinpath("app.js").read_text()
    # Anchor on the measure call and inspect the immediate function body.
    # 500 chars covers the small reset-and-render block without crossing
    # into unrelated callers — independent of where in loadTree() the
    # measure call sits relative to other statements.
    start = app_js.index('measure("renderTreeNodes:root"')
    root_block = app_js[start : start + 500]
    assert "pendingTreePages.clear()" in root_block
    assert "pendingTreePageId = 0" in root_block


def test_active_to_inactive_does_not_close_open_stream() -> None:
    """When a file flips from active to inactive, the
    re-render path (now in _mirrorActiveFromFsEntry) must not
    call selectFile while an EventSource owns the visible log
    tab — selectFile closes the stream. The post-pollActivity
    architecture preserves this rule via the
    ``if (!currentLiveStream)`` guard around the selectFile
    re-fetch."""
    app_js = proc_browser.STATIC_DIR.joinpath("app.js").read_text()
    fn_start = app_js.index("function _mirrorActiveFromFsEntry(entry)")
    fn_block = app_js[fn_start : fn_start + 3000]
    assert "if (!currentLiveStream)" in fn_block
    assert fn_block.index("if (!currentLiveStream)") < fn_block.index("selectFile(currentPath)")


def test_browser_perf_reports_large_file_render_phases() -> None:
    """Large-file diagnosis needs separate client timings for body parse,
    HTML generation/mounting, and syntax highlighting. The renderer-side
    perf labels migrated with the renderers into per-plugin index.js
    files (Phase 3c-3f); the shell-level timings still live in app.js.
    """
    app_js = proc_browser.STATIC_DIR.joinpath("app.js").read_text()
    perf_js = proc_browser.STATIC_DIR.joinpath("perf.js").read_text()
    text_plugin = (
        proc_browser.STATIC_DIR.parent / "builtin_plugins" / "text" / "index.js"
    ).read_text()

    assert "apiFile:json" in app_js
    # renderSourceTab → renderText:source via the text built-in plugin.
    assert "renderText:source" in text_plugin
    assert "renderFile:mount" in app_js
    assert "renderFile:nextPaint" in app_js
    assert "highlightCode" in app_js
    assert "no-highlight" in app_js
    assert "loadMoreCurrentText" in app_js
    assert "TEXT_PREVIEW_CHUNK_BYTES" in app_js
    assert "filePerfMeta" in app_js
    assert "MetabrowserDebug" in app_js
    assert "slow_measure" in perf_js
    assert "setSlowThreshold" in perf_js
    assert "console.warn" in perf_js


def test_server_installs_slow_request_logging_middleware() -> None:
    """Slow server-side browser requests should be visible in server logs."""
    assert any(
        getattr(middleware.cls, "__name__", "") == "_SlowRequestLogMiddleware"
        for middleware in proc_browser.app.user_middleware
    )


def test_slow_request_middleware_skips_long_lived_paths() -> None:
    """``/api/events`` is an SSE stream held open ~indefinitely.
    The slow-request threshold is ~3 s; without an explicit skip,
    every connected browser tab triggers a slow-request warning at
    every heartbeat."""

    middleware_class = proc_browser._SlowRequestLogMiddleware
    skipped = middleware_class._LONG_LIVED_PATHS
    assert "/api/events" in skipped, (
        "/api/events must be in the skip list — it's the SSE inventory "
        "stream and intentionally held open"
    )
    # Cover the other long-lived endpoints too so adding /api/tail or
    # /api/stream here doesn't silently emit slow-request false alarms.
    assert "/api/tail" in skipped
    assert "/api/stream" in skipped


def test_browser_open_handles_os_errors() -> None:
    """Headless launchers often raise OSError rather than webbrowser.Error."""
    proc_source = Path(proc_browser.__file__).read_text()
    serve_source = Path(proc_browser.__file__).parent.joinpath("cli", "serve.py").read_text()
    assert "except (webbrowser.Error, OSError)" in proc_source
    assert "except (webbrowser.Error, OSError)" in serve_source
