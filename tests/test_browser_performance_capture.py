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
RUNNER = ROOT / "explorations" / "performance-loop" / "run.py"


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


def test_capture_browser_accepts_the_git_revision_scenario() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available")
    script = f"""
const capture = require({json.dumps(str(CAPTURE))});
const parsed = capture.parseArgs([
  "--url", "http://127.0.0.1:8411/view/",
  "--probe", "probe.js",
  "--output", "profile.json",
  "--scenario", "git-revisions"
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
    assert json.loads(result.stdout)["scenario"] == "git-revisions"


def test_capture_browser_accepts_the_file_view_scenario() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available")
    script = f"""
const capture = require({json.dumps(str(CAPTURE))});
const parsed = capture.parseArgs([
  "--url", "http://127.0.0.1:8411/view/",
  "--probe", "probe.js",
  "--output", "profile.json",
  "--scenario", "file-views"
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
    assert json.loads(result.stdout)["scenario"] == "file-views"


def test_capture_browser_accepts_the_git_history_depth_scenario() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available")
    script = f"""
const capture = require({json.dumps(str(CAPTURE))});
const parsed = capture.parseArgs([
  "--url", "http://127.0.0.1:8411/view/",
  "--probe", "probe.js",
  "--output", "profile.json",
  "--scenario", "git-history-depth",
  "--history-rows", "10000"
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
    assert parsed["scenario"] == "git-history-depth"
    assert parsed["historyRows"] == 10_000


def test_capture_browser_requires_rows_for_the_git_history_depth_scenario() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available")
    script = f"""
const capture = require({json.dumps(str(CAPTURE))});
try {{
  capture.parseArgs([
    "--url", "http://127.0.0.1:8411/view/",
    "--probe", "probe.js",
    "--output", "profile.json",
    "--scenario", "git-history-depth"
  ]);
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
    assert "--history-rows is required" in result.stdout


def test_capture_browser_accepts_the_git_history_rebase_scenario() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available")
    script = f"""
const capture = require({json.dumps(str(CAPTURE))});
const parsed = capture.parseArgs([
  "--url", "http://127.0.0.1:8411/view/",
  "--probe", "probe.js",
  "--output", "profile.json",
  "--scenario", "git-history-rebase"
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
    assert json.loads(result.stdout)["scenario"] == "git-history-rebase"


def test_capture_browser_rejects_an_unknown_scenario() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available")
    script = f"""
const capture = require({json.dumps(str(CAPTURE))});
try {{
  capture.parseArgs([
    "--url", "http://127.0.0.1:8411/view/",
    "--probe", "probe.js",
    "--output", "profile.json",
    "--scenario", "unknown"
  ]);
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
    assert "unknown scenario" in result.stdout


def test_git_revision_scenario_uses_trusted_clicks_and_paint_boundaries() -> None:
    source = CAPTURE.read_text(encoding="utf-8")

    assert "async function runGitFilesRoundTrip" in source
    assert "async function runGitRevisionScenario" in source
    assert "dispatchTrustedClickForSelector" in source
    assert "startGitBlankFrameMonitor" in source
    assert "awaitNextPaint" in source
    assert "assertGitTransitionHealth" in source
    assert 'schema: "git-revision-navigation/v1"' in source
    assert '"gitRevision:selectionFeedback"' in source
    assert '"gitRevision:selectToReady"' in source
    assert 'document.querySelectorAll(".git-commit-diff .diff-root")' in source
    assert "git_files_roundtrip" in source

    capture_flow = source.split("async function capture", 1)[1]
    assert capture_flow.index("runGitFilesRoundTrip") < capture_flow.index("waitForIndex")
    post_preflight = capture_flow.split("gitFilesRoundTrip = await runGitFilesRoundTrip", 1)[1]
    assert post_preflight.index("const preflightTimeOrigin") < post_preflight.index(
        'session.send("Page.navigate"'
    )
    assert "performance.timeOrigin !==" in post_preflight

    runner = RUNNER.read_text(encoding="utf-8")
    assert (
        'choices=["git-revisions", "file-views", "git-history-depth", "git-history-rebase"]'
        in runner
    )
    assert 'command.extend(["--scenario", scenario])' in runner
    assert 'command.extend(["--history-rows", str(args.history_rows)])' in runner


def test_git_files_roundtrip_rejects_frozen_folder_disclosure() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available")
    script = f"""
const capture = require({json.dumps(str(CAPTURE))});
const healthy = {{
  path: "docs",
  return_to_files_ms: 5,
  folder_expand_ms: 8,
  before: {{
    aria_expanded: "false",
    group_collapsed: true,
    group_display: "none",
    group_inline_display: "",
    group_visibility: "hidden",
    row_collapsed: true,
    row_expanded: false
  }},
  after: {{
    aria_expanded: "true",
    group_collapsed: false,
    group_display: "block",
    group_inline_display: "",
    group_visibility: "visible",
    row_collapsed: false,
    row_expanded: true
  }}
}};
capture.assertGitFilesRoundTripHealth(healthy);
for (const [field, mutate] of [
  ["before.row_expanded", (value) => value.before.row_expanded = true],
  ["before.group_collapsed", (value) => value.before.group_collapsed = false],
  ["before.group_inline_display", (value) => value.before.group_inline_display = "none"],
  ["before.group_visibility", (value) => value.before.group_visibility = "visible"],
  ["before.aria_expanded", (value) => value.before.aria_expanded = "true"],
  ["after.row_expanded", (value) => value.after.row_expanded = false],
  ["after.row_collapsed", (value) => value.after.row_collapsed = true],
  ["after.group_collapsed", (value) => value.after.group_collapsed = true],
  ["after.group_display", (value) => value.after.group_display = "none"],
  ["after.group_inline_display", (value) => value.after.group_inline_display = "none"],
  ["after.group_visibility", (value) => value.after.group_visibility = "hidden"],
  ["after.aria_expanded", (value) => value.after.aria_expanded = "false"]
]) {{
  const candidate = structuredClone(healthy);
  mutate(candidate);
  try {{
    capture.assertGitFilesRoundTripHealth(candidate);
  }} catch (error) {{
    process.stdout.write(`${{field}}:${{String(error.message)}}\n`);
  }}
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
    for field in (
        "before.row_expanded",
        "before.group_collapsed",
        "before.group_inline_display",
        "before.group_visibility",
        "before.aria_expanded",
        "after.row_expanded",
        "after.row_collapsed",
        "after.group_collapsed",
        "after.group_display",
        "after.group_inline_display",
        "after.group_visibility",
        "after.aria_expanded",
    ):
        assert f"{field}:" in result.stdout


def test_navigation_scenarios_prepare_click_coordinates_before_timing() -> None:
    source = CAPTURE.read_text(encoding="utf-8")
    file_transition = source.split("async function measureFileTransition", 1)[1].split(
        "async function", 1
    )[0]
    git_transition = source.split("async function measureGitTransition", 1)[1].split(
        "async function", 1
    )[0]

    assert file_transition.index("const point = await pointForFilePath") < file_transition.index(
        "const started = await evaluate"
    )
    assert file_transition.index("startFileBlankFrameMonitor") < file_transition.index(
        "dispatchTrustedClickAtPoint(session, point)"
    )
    assert git_transition.index("const point = await pointForSelector") < git_transition.index(
        "const started = await evaluate"
    )
    assert git_transition.index("startGitBlankFrameMonitor") < git_transition.index(
        "dispatchTrustedClickAtPoint(session, point)"
    )


def test_git_revision_scenario_rejects_stale_or_unmeasured_transitions() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available")
    script = f"""
const capture = require({json.dumps(str(CAPTURE))});
const healthy = {{
  revision: "new",
  selected_revision: "new",
  route_revision: "new",
  rendered_revision: "new",
  mounted_comparisons: 1,
  blank_frames: 0,
  blank_duration_ms: 0,
  pending_seen: true,
  pending_active: false,
  aria_busy: false,
  pending_onset_ms: 5,
  pending_clear_ms: 15,
  phase_labels: [
    "gitRevision:selectionFeedback",
    "gitRevision:selectToReady",
    "gitRevision:rowAnchor"
  ]
}};
capture.assertGitTransitionHealth(healthy);
for (const [field, value] of [
  ["selected_revision", "old"],
  ["route_revision", "old"],
  ["rendered_revision", "old"],
  ["mounted_comparisons", 2],
  ["blank_frames", 1],
  ["pending_seen", false],
  ["pending_active", true],
  ["aria_busy", true],
  ["pending_onset_ms", null],
  ["pending_clear_ms", null],
  ["pending_clear_ms", 4],
  ["phase_labels", ["gitRevision:selectionFeedback", "gitRevision:selectToReady"]]
]) {{
  try {{
    capture.assertGitTransitionHealth({{...healthy, [field]: value}});
  }} catch (error) {{
    process.stdout.write(`${{field}}:${{String(error.message)}}\n`);
  }}
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
    for field in (
        "selected_revision",
        "route_revision",
        "rendered_revision",
        "mounted_comparisons",
        "blank_frames",
        "pending_seen",
        "pending_active",
        "aria_busy",
        "pending_onset_ms",
        "pending_clear_ms",
        "phase_labels",
    ):
        assert f"{field}:" in result.stdout


def test_file_view_scenario_uses_trusted_clicks_and_painted_readiness() -> None:
    source = CAPTURE.read_text(encoding="utf-8")

    assert "async function runFileViewScenario" in source
    assert "dispatchTrustedClickForFilePath" in source
    assert "startFileBlankFrameMonitor" in source
    assert "waitForFileView" in source
    assert "assertFileTransitionHealth" in source
    assert 'schema: "file-view-navigation/v1"' in source
    assert '"fileNavigation:selectToReady"' in source
    assert '"fileNavigation:paintReady"' in source
    assert 'candidates.structured, "cold-structured"' in source
    assert "candidates.structured" in source


def test_file_view_scenario_rejects_blank_stale_or_unmeasured_transitions() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available")
    script = f"""
const capture = require({json.dumps(str(CAPTURE))});
const healthy = {{
  path: "src/app.js",
  selected_path: "src/app.js",
  route_path: "src/app.js",
  rendered_path: "src/app.js",
  rendered_view: "source",
  active_mounts: 1,
  active_view_nonempty: true,
  blank_frames: 0,
  blank_duration_ms: 0,
  pending_seen: true,
  pending_active: false,
  aria_busy: false,
  file_fetches: 1,
  phase_labels: ["fileNavigation:assets", "fileNavigation:activeView",
    "fileNavigation:paintReady", "fileNavigation:selectToReady"]
}};
capture.assertFileTransitionHealth(healthy);
for (const [field, value] of [
  ["selected_path", "old.js"],
  ["route_path", "old.js"],
  ["rendered_path", "old.js"],
  ["rendered_view", ""],
  ["active_mounts", 2],
  ["active_view_nonempty", false],
  ["blank_frames", 1],
  ["pending_seen", false],
  ["pending_active", true],
  ["aria_busy", true],
  ["file_fetches", 2],
  ["phase_labels", ["fileNavigation:assets"]]
]) {{
  try {{
    capture.assertFileTransitionHealth({{...healthy, [field]: value}});
  }} catch (error) {{
    process.stdout.write(`${{field}}:${{String(error.message)}}\n`);
  }}
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
    for field in (
        "selected_path",
        "route_path",
        "rendered_path",
        "rendered_view",
        "active_mounts",
        "active_view_nonempty",
        "blank_frames",
        "pending_seen",
        "pending_active",
        "aria_busy",
        "file_fetches",
        "phase_labels",
    ):
        assert f"{field}:" in result.stdout


def test_probe_exports_fetch_concurrency_provenance() -> None:
    source = PROBE.read_text(encoding="utf-8")

    assert "fetches_in_flight_max: perf.fetches_in_flight_max ?? null" in source
    assert "fetches_in_flight_max_by_key: perf.fetches_in_flight_max_by_key ?? null" in source
    assert (
        "fetch_concurrency_keys_overflowed: perf.fetch_concurrency_keys_overflowed ?? null"
        in source
    )


def test_capture_browser_records_controlled_retained_heap() -> None:
    source = CAPTURE.read_text(encoding="utf-8")

    assert 'session.send("HeapProfiler.collectGarbage")' in source
    assert 'session.send("Runtime.getHeapUsage")' in source
    assert "payload.js_heap_after_gc_mb" in source
    # The default load profile and the Git interaction scenario each collect only
    # after their product snapshot. The default path is the final collection.
    assert source.index("const probe = fs.readFileSync") < source.rindex(
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


def test_git_revision_scenario_rejects_deferred_request_storms() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available")
    script = f"""
const capture = require({json.dumps(str(CAPTURE))});
const healthy = {{
  candidate_revision: "old",
  target_revision: "new",
  pending_files: 3,
  max_deferred_fetches_in_flight: 2,
  fetch_concurrency_keys_overflowed: 0,
  obsolete_successes: 0,
  aborted_requests: 2,
  mounted_comparisons: 1,
  selected_revision: "new",
  route_revision: "new",
  rendered_revision: "new"
}};
capture.assertDeferredHydrationHealth(healthy);
for (const [field, value] of [
  ["candidate_revision", ""],
  ["target_revision", ""],
  ["pending_files", 2],
  ["max_deferred_fetches_in_flight", 3],
  ["fetch_concurrency_keys_overflowed", 1],
  ["obsolete_successes", 1],
  ["aborted_requests", 0],
  ["mounted_comparisons", 2],
  ["route_revision", "old"],
  ["rendered_revision", "old"]
]) {{
  try {{
    capture.assertDeferredHydrationHealth({{...healthy, [field]: value}});
  }} catch (error) {{
    process.stdout.write(`${{field}}:${{String(error.message)}}\n`);
  }}
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
    for field in (
        "candidate_revision",
        "target_revision",
        "pending_files",
        "max_deferred_fetches_in_flight",
        "fetch_concurrency_keys_overflowed",
        "obsolete_successes",
        "aborted_requests",
        "mounted_comparisons",
        "route_revision",
        "rendered_revision",
    ):
        assert f"{field}:" in result.stdout


def test_git_revision_scenario_exercises_deferred_hydration() -> None:
    source = CAPTURE.read_text(encoding="utf-8")

    assert "async function runDeferredHydrationScenario" in source
    assert 'document.querySelectorAll(".diff-file-body")' in source
    assert 'document.querySelectorAll(".diff-progress")' in source
    assert 'fetches_in_flight_max_by_key["/api/plugin/diff/comparison?file"]' in source
    assert "window.metabrowser.perf.reset()" in source
    assert "assertDeferredHydrationHealth(deferredHydration)" in source
    assert "deferred_hydration: deferredHydration" in source


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
