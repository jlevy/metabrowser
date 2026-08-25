"""Contract tests for the reusable browser-performance gate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from devtools.web_performance import (
    blocking_issues,
    budget_issues,
    load_performance_config,
    validity_issues,
)

ROOT = Path(__file__).resolve().parents[1]
BUDGETS = ROOT / "explorations" / "performance-loop" / "performance-budgets.toml"


def _valid_run(**overrides: object) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "animation_frame_max_ms": 80,
        "animation_frame_blocking_ms_max": 30,
        "animation_frames_over_200ms": 0,
        "animation_frames_blocking_over_200ms": 0,
        "cls": 0.01,
        "commit": "abc1234",
        "corpus": "test-corpus",
        "dom_nodes": 5000,
        "dirty": False,
        "ever_hidden": False,
        "fcp_ms": 150,
        "fetch_aborts": 0,
        "fetch_http_4xx": 0,
        "fetch_http_5xx": 0,
        "fetch_network_errors": 0,
        "fetches_in_flight": 0,
        "file_catalog_incomplete": 0,
        "first_row_ms": 300,
        "files": 100,
        "frame_missing_px": 0,
        "interaction_max_ms": 90,
        "interaction_input_coverage_pct": 90,
        "interaction_inputs": 6,
        "interactions": 3,
        "inventory_delivery_max_ms": 8,
        "inventory_delivery_attribution_missing": 0,
        "inventory_delivery_work_pct": 0.2,
        "index_status_at_probe": "done",
        "harness_version": 12,
        "labels_overflowed": 0,
        "lcp_ms": 900,
        "long_task_max_ms": 80,
        "long_task_max_ms_first_5s": 70,
        "long_tasks_over_200ms": 0,
        "main_thread_blocked_pct": 1.2,
        "measurement_valid": True,
        "performance_profile_schema": "web-performance-profile/v1",
        "page_exceptions": 0,
        "rendered_preview_errors": 0,
        "reserved_region_shift_px": 0,
        "recorded_at": "2026-08-23T12:00:00+00:00",
        "resource_timing_buffer_full": 0,
        "responsiveness_source": "navigation-profiler",
        "shell_tools_missing": 0,
        "startup_script_requests": 22,
        "startup_script_transfer_kb": 154,
        "tree_region_repaints": 1,
        "unsupported": None,
        "visibility_state": "visible",
        "vitals_source": "navigation-profiler",
        "viewport_h": 900,
        "viewport_w": 1280,
    }
    payload.update(overrides)
    return payload


def test_visible_navigation_profile_with_interactions_is_admissible() -> None:
    config = load_performance_config(BUDGETS)

    assert validity_issues(_valid_run(), config) == []
    assert budget_issues(_valid_run(), config) == []


def test_hidden_late_or_interaction_free_records_are_invalid() -> None:
    config = load_performance_config(BUDGETS)
    payload = _valid_run(
        ever_hidden=True,
        interaction_input_coverage_pct=0,
        interaction_inputs=0,
        measurement_valid=False,
        performance_profile_schema=None,
        responsiveness_source="late-buffer",
        vitals_source="late-buffer",
        visibility_state="hidden",
    )

    codes = {issue.code for issue in validity_issues(payload, config)}

    assert {
        "profile-schema",
        "late-profiler",
        "late-vitals",
        "not-visible-throughout",
        "insufficient-interactions",
        "interaction-coverage",
    } <= codes


def test_one_early_click_cannot_claim_whole_load_responsiveness() -> None:
    config = load_performance_config(BUDGETS)

    codes = {
        issue.code
        for issue in validity_issues(
            _valid_run(interaction_input_coverage_pct=0, interaction_inputs=1), config
        )
    }

    assert {"insufficient-interactions", "interaction-coverage"} <= codes


def test_multisecond_freeze_is_a_blocking_budget_failure() -> None:
    config = load_performance_config(BUDGETS)
    issues = budget_issues(
        _valid_run(
            animation_frame_max_ms=6393,
            animation_frame_blocking_ms_max=6200,
            animation_frames_over_200ms=3,
            animation_frames_blocking_over_200ms=3,
            long_task_max_ms=6393,
            long_tasks_over_200ms=3,
            main_thread_blocked_pct=55.3,
        ),
        config,
    )

    blocking_metrics = {issue.metric for issue in blocking_issues(issues)}

    assert {
        "animation_frame_blocking_ms_max",
        "animation_frames_blocking_over_200ms",
        "long_task_max_ms",
        "long_tasks_over_200ms",
        "main_thread_blocked_pct",
    } <= blocking_metrics


def test_event_storm_is_blocking_even_when_no_single_task_crosses_200_ms() -> None:
    config = load_performance_config(BUDGETS)
    issues = budget_issues(
        _valid_run(
            inventory_delivery_max_ms=48,
            inventory_delivery_work_pct=18,
            long_task_max_ms=48,
            long_tasks_over_200ms=0,
            main_thread_blocked_pct=0,
        ),
        config,
    )

    assert {issue.metric for issue in blocking_issues(issues)} == {"inventory_delivery_work_pct"}


def test_missing_inventory_attribution_cannot_report_a_good_zero() -> None:
    config = load_performance_config(BUDGETS)
    issues = budget_issues(_valid_run(inventory_delivery_attribution_missing=1), config)

    assert {issue.metric for issue in blocking_issues(issues)} == {
        "inventory_delivery_attribution_missing"
    }


def test_known_roadmap_debt_is_reported_without_blocking_unrelated_work() -> None:
    config = load_performance_config(BUDGETS)
    issues = budget_issues(
        _valid_run(frame_missing_px=532, reserved_region_shift_px=23, tree_region_repaints=2),
        config,
    )

    assert {issue.metric for issue in issues} >= {
        "frame_missing_px",
        "reserved_region_shift_px",
        "tree_region_repaints",
    }
    assert blocking_issues(issues) == []


def test_missing_required_metric_invalidates_the_record() -> None:
    config = load_performance_config(BUDGETS)
    payload = _valid_run()
    del payload["long_task_max_ms"]

    issues = budget_issues(payload, config)

    assert any(issue.code == "metric-missing" for issue in blocking_issues(issues))


def test_missing_retention_provenance_invalidates_the_record() -> None:
    config = load_performance_config(BUDGETS)
    payload = _valid_run()
    del payload["labels_overflowed"]

    codes = {issue.code for issue in validity_issues(payload, config)}

    assert "attribution-retention-missing" in codes


def test_missing_run_provenance_invalidates_the_record() -> None:
    config = load_performance_config(BUDGETS)
    payload = _valid_run(commit="")

    issues = validity_issues(payload, config)

    assert any(issue.code == "provenance-missing" and "commit" in issue.message for issue in issues)


def test_resource_timing_overflow_invalidates_network_totals() -> None:
    config = load_performance_config(BUDGETS)

    codes = {
        issue.code for issue in validity_issues(_valid_run(resource_timing_buffer_full=1), config)
    }

    assert "resource-retention-overflow" in codes


def test_fetch_failures_gate_while_abort_semantics_stay_visible() -> None:
    config = load_performance_config(BUDGETS)

    failure_issues = budget_issues(_valid_run(fetch_network_errors=1), config)
    abort_issues = budget_issues(_valid_run(fetch_aborts=1), config)

    assert {issue.metric for issue in blocking_issues(failure_issues)} == {"fetch_network_errors"}
    assert {issue.metric for issue in abort_issues} == {"fetch_aborts"}
    assert blocking_issues(abort_issues) == []


def test_rendered_errors_and_page_exceptions_are_blocking_failures() -> None:
    config = load_performance_config(BUDGETS)
    issues = budget_issues(
        _valid_run(page_exceptions=8, rendered_preview_errors=1),
        config,
    )

    assert {issue.metric for issue in blocking_issues(issues)} == {
        "page_exceptions",
        "rendered_preview_errors",
    }


def test_eager_plugin_waterfall_is_a_blocking_budget_failure() -> None:
    config = load_performance_config(BUDGETS)
    issues = budget_issues(
        _valid_run(startup_script_requests=74, startup_script_transfer_kb=337), config
    )

    assert {issue.metric for issue in blocking_issues(issues)} == {
        "startup_script_requests",
        "startup_script_transfer_kb",
    }


def test_eager_shell_tools_or_missing_deferred_tools_fail() -> None:
    config = load_performance_config(BUDGETS)
    issues = budget_issues(
        _valid_run(
            shell_tools_missing=1,
            startup_script_requests=33,
            startup_script_transfer_kb=214,
        ),
        config,
    )

    assert {issue.metric for issue in blocking_issues(issues)} == {
        "shell_tools_missing",
        "startup_script_requests",
        "startup_script_transfer_kb",
    }


def test_incomplete_deferred_file_catalog_fails() -> None:
    config = load_performance_config(BUDGETS)

    issues = budget_issues(_valid_run(file_catalog_incomplete=1), config)

    assert {issue.metric for issue in blocking_issues(issues)} == {"file_catalog_incomplete"}
