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
        "animation_frames_over_200ms": 0,
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
        "first_row_ms": 300,
        "files": 100,
        "frame_missing_px": 0,
        "interaction_max_ms": 90,
        "interaction_inputs": 1,
        "interactions": 3,
        "index_status_at_probe": "done",
        "harness_version": 4,
        "labels_overflowed": 0,
        "lcp_ms": 900,
        "long_task_max_ms": 80,
        "long_task_max_ms_first_5s": 70,
        "long_tasks_over_200ms": 0,
        "main_thread_blocked_pct": 1.2,
        "measurement_valid": True,
        "performance_profile_schema": "web-performance-profile/v1",
        "reserved_region_shift_px": 0,
        "recorded_at": "2026-08-23T12:00:00+00:00",
        "resource_timing_buffer_full": 0,
        "responsiveness_source": "navigation-profiler",
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
        "no-interactions",
    } <= codes


def test_multisecond_freeze_is_a_blocking_budget_failure() -> None:
    config = load_performance_config(BUDGETS)
    issues = budget_issues(
        _valid_run(
            animation_frame_max_ms=6393,
            animation_frames_over_200ms=3,
            long_task_max_ms=6393,
            long_tasks_over_200ms=3,
            main_thread_blocked_pct=55.3,
        ),
        config,
    )

    blocking_metrics = {issue.metric for issue in blocking_issues(issues)}

    assert {
        "animation_frame_max_ms",
        "animation_frames_over_200ms",
        "long_task_max_ms",
        "long_tasks_over_200ms",
        "main_thread_blocked_pct",
    } <= blocking_metrics


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
