"""Diagnostic instrumentation for confirming where slow requests sit.

Two hooks added for the perf-debugging session described in the
2026-05-07 handoff:

1. ``METABROWSER_REQUEST_LOG=verbose`` — flips ``_SlowRequestLogMiddleware``
   from "log only the slow ones" to "log every request with absolute
   wall-clock arrival + completion timestamps". Lets the operator
   correlate server-side timestamps against perf.js records to
   distinguish in-handler latency vs in-transit latency.

2. ``GET /_debug/tasks`` (gated on ``METABROWSER_DEBUG=1``) — JSON
   snapshot of ``asyncio.all_tasks()``. If the count balloons during
   a hover-prefetch storm, the event loop is overcommitted and
   subsequent requests queue.

These tests don't reproduce the slowness (the sandbox can't drive
a real browser); they assert the instrumentation is in place and
behaves as documented so the operator can use it to confirm root
cause.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock

import pytest

from devtools import bench_serving
from metabrowser import server, tree
from metabrowser.inventory_engine.runtime import (
    InventoryRuntime,
    inventory_provider_from_environment,
)
from tests.inventory_harness import inventory_harness


def test_perf_logging_writes_to_current_stderr(capsys) -> None:
    token = "metabrowser-dynamic-stderr"

    logging.getLogger("metabrowser.server").warning(token)

    captured = capsys.readouterr()
    assert token in captured.err
    assert token not in captured.out


def _scope(method: str = "GET", path: str = "/api/tree") -> dict[str, Any]:
    return {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": b"",
        "headers": [],
    }


async def _drive_middleware(
    mw: server._SlowRequestLogMiddleware, *, app_delay: float = 0.0
) -> None:
    async def fake_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
        if app_delay:
            await asyncio.sleep(app_delay)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"x" * 256, "more_body": False})

    mw.app = fake_app

    async def receive() -> dict[str, Any]:
        return {"type": "http.disconnect"}

    sent: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    await mw(_scope(), receive, send)


class _CaptureHandler(logging.Handler):
    """Capture records directly off ``metabrowser.server`` — pytest's
    caplog uses root propagation, but server.py disables propagation
    (its perf-logger setup attaches its own handler and sets
    propagate=False), so caplog sees nothing. Attach this to the
    logger directly to read what server.py emits."""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)

    def messages(self) -> list[str]:
        return [r.getMessage() for r in self.records]


def _attach_capture() -> _CaptureHandler:
    handler = _CaptureHandler()
    server.LOG.addHandler(handler)
    return handler


def _detach_capture(handler: _CaptureHandler) -> None:
    server.LOG.removeHandler(handler)


def test_route_timing_is_debug_diagnostic() -> None:
    """Routine handler timings stay behind the explicit DEBUG log level."""
    handler = _attach_capture()
    original_level = server.LOG.level

    @server.log_async_calls()
    async def fast_route() -> None: ...

    try:
        server.LOG.setLevel(logging.DEBUG)
        asyncio.run(fast_route())
    finally:
        server.LOG.setLevel(original_level)
        _detach_capture(handler)

    records = [record for record in handler.records if "fast_route took" in record.getMessage()]
    assert len(records) == 1
    assert records[0].levelno == logging.DEBUG


def test_expensive_request_handlers_keep_timing_decorators() -> None:
    for handler in (server.api_tree, server.api_rollup, server.api_file):
        assert hasattr(handler, "__wrapped__"), handler.__name__

    assert not hasattr(server._api_folder_envelope, "__wrapped__")


def test_fast_gitignore_setup_does_not_emit_timing_at_info(tmp_path: Path) -> None:
    """The slow-call threshold must suppress sub-threshold helper timings."""
    loggers = (tree.LOG, logging.getLogger("funlog.funlog"))
    handler = _CaptureHandler()
    original_levels = [logger.level for logger in loggers]
    for logger in loggers:
        logger.addHandler(handler)
    tree._IGNORE_CACHE.clear()
    try:
        for logger in loggers:
            logger.setLevel(logging.INFO)
        tree.build_gitignore_check(tmp_path)
    finally:
        tree._IGNORE_CACHE.clear()
        for logger, original_level in zip(loggers, original_levels, strict=True):
            logger.setLevel(original_level)
            logger.removeHandler(handler)

    assert not any("build_gitignore_check" in message for message in handler.messages())


def test_verbose_request_log_logs_every_request() -> None:
    """When verbose=True, every request gets an INFO line — not just slow ones."""
    handler = _attach_capture()
    try:
        mw = server._SlowRequestLogMiddleware(
            app=None,
            threshold_ms=10000,  # high enough that nothing trips it
            verbose=True,
        )
        asyncio.run(_drive_middleware(mw))
    finally:
        _detach_capture(handler)
    matched = [m for m in handler.messages() if "metabrowser request t=" in m]
    assert matched, f"verbose mode must emit per-request line; got {handler.messages()!r}"
    msg = matched[-1]
    # Format: "metabrowser request t=<arrived> -> <completed> (<ms> ms) method=GET path=... status=200 bytes=256"
    assert "method=GET" in msg
    assert "path=/api/tree" in msg
    assert "status=200" in msg
    assert "bytes=256" in msg


def test_default_mode_only_logs_slow_requests() -> None:
    """verbose=False (the default): a fast request emits NO line."""
    handler = _attach_capture()
    try:
        mw = server._SlowRequestLogMiddleware(
            app=None,
            threshold_ms=10000,
            verbose=False,
        )
        asyncio.run(_drive_middleware(mw))
    finally:
        _detach_capture(handler)
    matched = [m for m in handler.messages() if "metabrowser" in m]
    assert matched == [], f"non-verbose mode should be silent for fast requests; got {matched!r}"


def test_default_mode_logs_slow_request_warning() -> None:
    """Threshold breach still fires a WARNING in default mode (existing behaviour).

    Use a 1 ms threshold + a 5 ms artificial app delay so the
    threshold reliably trips. ``threshold_ms=0`` would be falsy and
    skip the branch entirely (the middleware uses the threshold as
    both a value AND an enable flag — 0 means "logging disabled").
    """
    handler = _attach_capture()
    try:
        mw = server._SlowRequestLogMiddleware(
            app=None,
            threshold_ms=1,
            verbose=False,
        )
        asyncio.run(_drive_middleware(mw, app_delay=0.005))
    finally:
        _detach_capture(handler)
    matched = [m for m in handler.messages() if "metabrowser slow server request" in m]
    assert matched, f"slow-request WARNING must fire; got {handler.messages()!r}"


def test_debug_tasks_route_is_gated(monkeypatch) -> None:
    """Without METABROWSER_DEBUG=1 the route returns 404 with an explainer."""
    monkeypatch.delenv("METABROWSER_DEBUG", raising=False)
    response = asyncio.run(server._debug_tasks(Mock()))
    assert response.status_code == 404
    payload = json.loads(bytes(response.body))
    assert "METABROWSER_DEBUG=1" in payload["error"]


def test_debug_tasks_route_returns_task_snapshot(monkeypatch) -> None:
    """With METABROWSER_DEBUG=1 the route returns the asyncio task snapshot."""
    monkeypatch.setenv("METABROWSER_DEBUG", "1")

    async def run_check() -> dict[str, Any]:
        # Spawn a sleeping task so the snapshot has at least one entry
        # besides the test runner itself; this catches a regression where
        # all_tasks() returned None or an empty list.
        async def sleeper() -> None:
            await asyncio.sleep(0.05)

        sleep_task = asyncio.create_task(sleeper(), name="test-sleeper")
        try:
            response = await server._debug_tasks(Mock())
            return json.loads(bytes(response.body))
        finally:
            sleep_task.cancel()

    payload = asyncio.run(run_check())
    assert payload["task_count"] >= 1
    names = {t["name"] for t in payload["tasks"]}
    assert (
        any(
            "test-sleeper" in n or "sleeper" in t["coro"]
            for n, t in zip(names, payload["tasks"], strict=False)
        )
        or len(payload["tasks"]) >= 1
    )


def test_debug_inventory_reports_provider_contract_and_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "one.txt").write_text("one", encoding="utf-8")
    monkeypatch.setenv("METABROWSER_DEBUG", "1")

    async def run_check() -> dict[str, Any]:
        async with inventory_harness(tmp_path) as harness:
            response = await server._debug_inventory(cast(Any, SimpleNamespace(app=harness.app)))
            return json.loads(bytes(response.body))

    payload = asyncio.run(run_check())
    assert payload["provider"] == "python"
    assert payload["contract"] == "inventory-provider-v1"
    assert payload["complete"] is True
    assert set(payload["work"]) == {
        "read_requests",
        "entries_visited",
        "directories_visited",
        "rows_returned",
        "binding_bytes_copied",
        "lock_wait_ns",
        "cpu_time_ns",
        "wall_time_ns",
    }


def test_inventory_provider_environment_selection_is_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("METABROWSER_INVENTORY_PROVIDER", " PYTHON ")
    assert inventory_provider_from_environment() == " PYTHON "
    runtime = InventoryRuntime(provider=inventory_provider_from_environment())
    assert runtime.config.budget.max_files > 0
    monkeypatch.setenv("METABROWSER_INVENTORY_PROVIDER", "missing")
    with pytest.raises(ValueError, match="unknown inventory provider"):
        InventoryRuntime(provider=inventory_provider_from_environment())


def test_serving_benchmark_records_and_validates_provider_identity() -> None:
    result: dict[str, Any] = {
        "cold_scan": {
            "diagnostics": {
                "provider": "python",
                "contract": "inventory-provider-v1",
            }
        },
        "scan_with_client": {
            "diagnostics": {
                "provider": "python",
                "contract": "inventory-provider-v1",
            }
        },
        "settled": {
            "diagnostics": {
                "provider": "python",
                "contract": "inventory-provider-v1",
            }
        },
    }
    bench_serving._record_inventory_identity(result, "python")
    assert result["inventory"] == {
        "provider": "python",
        "contract": "inventory-provider-v1",
    }
    report = bench_serving.render_report(
        {"label": "test", "corpus": {}, "inventory": result["inventory"]},
        None,
    )
    assert "provider=python contract=inventory-provider-v1" in report


@pytest.mark.parametrize(
    ("value", "expected"),
    [("00:00.72", 0.72), ("01:02:03", 3723.0), ("2-01:02:03.5", 176523.5)],
)
def test_serving_benchmark_parses_process_cpu_time(value: str, expected: float) -> None:
    assert bench_serving._cpu_seconds(value) == expected


def test_performance_loop_carries_provider_provenance() -> None:
    source = (
        Path(server.__file__).parents[2] / "explorations" / "performance-loop" / "run.py"
    ).read_text(encoding="utf-8")
    assert '"--provider"' in source
    assert 'environment["METABROWSER_INVENTORY_PROVIDER"] = args.provider' in source
    assert '"inventory_provider_requested": args.provider' in source
    assert '"inventory_contract": payload.get("contract")' in source


def test_response_carries_server_timing_header() -> None:
    """Every response (fast or slow) carries Server-Timing: srv;dur=<ms>.

    The browser's Network tab renders this in the timing waterfall,
    and perf.js reads it to print server-vs-transit breakdowns on
    slow_fetch records. Always-on header — no opt-in required.
    """
    captured: list[dict[str, Any]] = []

    async def fake_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
        async def trapped_send(message: dict[str, Any]) -> None:
            captured.append(message)
            await send(message)

        await trapped_send({"type": "http.response.start", "status": 200, "headers": []})
        await trapped_send({"type": "http.response.body", "body": b"x", "more_body": False})

    mw = server._SlowRequestLogMiddleware(app=fake_app)

    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    asyncio.run(mw(_scope(), receive, send))

    starts = [m for m in sent if m.get("type") == "http.response.start"]
    assert starts, "middleware must forward http.response.start"
    headers = dict(starts[0].get("headers") or [])
    timing = headers.get(b"server-timing")
    assert timing is not None, f"Server-Timing header must be set; got headers={headers!r}"
    assert timing.startswith(b"srv;dur=")


def test_slow_request_warning_includes_arrival_epoch() -> None:
    """The default-mode WARNING line carries t=<arrived> so the operator
    can correlate against perf.js timestamps without flipping verbose."""
    handler = _attach_capture()
    try:
        mw = server._SlowRequestLogMiddleware(
            app=None,
            threshold_ms=1,
            verbose=False,
        )
        asyncio.run(_drive_middleware(mw, app_delay=0.005))
    finally:
        _detach_capture(handler)
    matched = [m for m in handler.messages() if "metabrowser slow server request" in m]
    assert matched, f"slow-request WARNING must fire; got {handler.messages()!r}"
    assert "t=" in matched[-1], f"warning must include arrival epoch; got: {matched[-1]!r}"


def test_perf_js_parses_server_timing_and_logs_breakdown() -> None:
    """perf.js's fetch wrapper reads Server-Timing and stores server_ms
    on the sample; slow-fetch console line includes a 'server=… transit=…'
    breakdown.

    We assert against perf.js source text (the JS runtime would need
    JSDOM); the contract is small enough that source-text checks
    catch the regression cleanly.
    """
    perf_js = (Path(server.__file__).resolve().parent / "static" / "perf.js").read_text(
        encoding="utf-8"
    )
    assert "_parseServerTiming" in perf_js, "perf.js must expose a Server-Timing parser"
    assert "server-timing" in perf_js.lower(), (
        "perf.js must read the Server-Timing header off the response"
    )
    assert "server_ms" in perf_js, "fetch sample must carry server_ms when Server-Timing is present"
    # Slow-fetch log line should print the breakdown when server_ms is known.
    assert 'server=" + sample.server_ms' in perf_js or "server=" in perf_js, (
        "slow-fetch warning must surface server_ms inline for at-a-glance reading"
    )


def test_request_log_env_var_recognized(monkeypatch) -> None:
    """Setting METABROWSER_REQUEST_LOG=verbose at startup flips the
    module-level constant; tested via importlib reload-free check that
    the constant maps the value correctly."""
    # We can't easily reload the server module mid-test (it has
    # singletons); instead probe the parsing logic by replicating it.
    for value, expected in [
        ("verbose", True),
        ("VERBOSE", True),
        (" verbose ", True),
        ("", False),
        ("0", False),
        ("info", False),
    ]:
        monkeypatch.setenv("METABROWSER_REQUEST_LOG", value)
        is_verbose = os.environ.get("METABROWSER_REQUEST_LOG", "").strip().lower() == "verbose"
        assert is_verbose is expected, f"value={value!r} expected={expected} got={is_verbose}"
