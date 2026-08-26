"""CLI contract for the dependency-free Chrome performance driver."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "explorations" / "performance-loop" / "capture-browser.js"
PROBE = ROOT / "explorations" / "performance-loop" / "probe.js"


def test_capture_browser_argument_contract() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available")
    script = f"""
const capture = require({json.dumps(str(CAPTURE))});
const parsed = capture.parseArgs([
  "--url", "http://127.0.0.1:8411/view/",
  "--probe", "probe.js",
  "--output", "profile.json",
  "--headed",
  "--width", "1600",
  "--height", "900"
]);
process.stdout.write(JSON.stringify(parsed));
"""

    result = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    parsed = json.loads(result.stdout)
    assert parsed["headed"] is True
    assert parsed["width"] == 1600
    assert parsed["height"] == 900
    assert parsed["url"] == "http://127.0.0.1:8411/view/"


def test_capture_browser_records_controlled_retained_heap() -> None:
    source = CAPTURE.read_text(encoding="utf-8")

    assert 'session.send("HeapProfiler.collectGarbage")' in source
    assert 'session.send("Runtime.getHeapUsage")' in source
    assert "payload.js_heap_after_gc_mb" in source
    assert source.index("const probe = fs.readFileSync") < source.index(
        'session.send("HeapProfiler.collectGarbage")'
    )


def test_capture_browser_counts_uncaught_page_exceptions_from_navigation() -> None:
    source = CAPTURE.read_text(encoding="utf-8")

    listener = source.index('session.on("Runtime.exceptionThrown"')
    navigation = source.index('session.send("Page.navigate"')
    export = source.index("payload.page_exceptions")

    assert listener < navigation < export
    assert 'await session.send("Runtime.enable")' in source


def test_probe_counts_rendered_preview_errors() -> None:
    source = PROBE.read_text(encoding="utf-8")

    assert 'document.querySelectorAll("#preview-pane .preview-error")' in source
    assert "rendered_preview_errors:" in source


def test_probe_counts_rows_materialized_inside_collapsed_diff_folds() -> None:
    source = PROBE.read_text(encoding="utf-8")

    assert ".diff-fold-group.diff-fold-collapsed .diff-line" in source
    assert ".diff-fold-group.diff-fold-collapsed .diff-split-row" in source
    assert "collapsed_diff_rows_materialized:" in source


def test_capture_browser_pulses_non_product_input_through_loading() -> None:
    source = CAPTURE.read_text(encoding="utf-8")

    assert "startTrustedInputPulse(session)" in source
    assert "await waitForIndex(options.url, options.timeoutMs)" in source
    assert "inputPulseCount = await inputPulse.stop()" in source
    assert "INPUT_PULSE_INTERVAL_MS" in source
    assert "metabrowser-performance-input-sentinel" in source
    stop_start = source.index("async stop()")
    stop_block = source[stop_start : stop_start + 900]
    assert stop_block.index("await dispatchTrustedClickAtPoint(session, point)") < (
        stop_block.index("await removeInputSentinel(session)")
    )
    assert "assertControlledInputCount(payload.interaction_inputs, inputPulseCount)" in source


def test_capture_browser_rejects_input_outside_the_controlled_pulse() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available")
    script = f"""
const capture = require({json.dumps(str(CAPTURE))});
capture.assertControlledInputCount(12, 12);
try {{
  capture.assertControlledInputCount(13, 12);
}} catch (error) {{
  process.stdout.write(String(error.message));
}}
"""

    result = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert "differs from the controlled CDP pulse count" in result.stdout


def test_probe_freezes_product_responsiveness_before_diagnostic_work() -> None:
    source = PROBE.read_text(encoding="utf-8")
    snapshot = source.index("profiler ? profiler.snapshot()")

    assert snapshot < source.index("new PerformanceObserver")
    assert snapshot < source.index('fetch("/api/tree?depth=1"')


def test_probe_does_not_classify_script_preloads_as_stylesheets() -> None:
    source = PROBE.read_text(encoding="utf-8")
    scripts = source[source.index("const scripts =") : source.index("const startupScripts =")]
    styles = source[source.index("const styles =") : source.index("const images =")]

    assert 'pathname.endsWith(".js")' in scripts
    assert 'initiatorType === "script"' not in scripts
    assert 'pathname.endsWith(".css")' in styles
    assert 'initiatorType === "link"' not in styles


def test_probe_attributes_startup_resource_queue_and_server_time() -> None:
    source = PROBE.read_text(encoding="utf-8")
    startup = source[source.index("startup_scripts_slowest:") : source.index("style_transfer_kb:")]

    assert startup.count("response_start_ms:") == 2
    assert startup.count("wait_ms:") == 2
    assert startup.count("download_ms:") == 2
    assert startup.count('entry.name === "srv"') == 2
