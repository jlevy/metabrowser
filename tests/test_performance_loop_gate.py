"""Integration checks for performance-loop evidence and candidate gates."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "explorations" / "performance-loop" / "run.py"
BUDGETS = ROOT / "explorations" / "performance-loop" / "performance-budgets.toml"


def _runner() -> Any:
    spec = importlib.util.spec_from_file_location("metabrowser_performance_loop", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(label: str, **overrides: object) -> dict[str, Any]:
    result: dict[str, Any] = {
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
        "index_status_at_probe": "done",
        "harness_version": 4,
        "interaction_inputs": 1,
        "interaction_max_ms": 90,
        "interactions": 1,
        "label": label,
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
    result.update(overrides)
    return result


def _compare(module: Any, runs: list[dict[str, Any]]) -> int:
    module._load_runs = lambda: runs
    return int(
        module.cmd_compare(argparse.Namespace(labels=["before", "after"], budgets=str(BUDGETS)))
    )


def test_compare_passes_when_candidate_repairs_a_control_freeze() -> None:
    module = _runner()
    before = [
        _run(
            "before",
            long_task_max_ms=6393,
            long_tasks_over_200ms=3,
            main_thread_blocked_pct=55.3,
        )
        for _index in range(3)
    ]
    after = [_run("after") for _index in range(3)]

    assert _compare(module, [*before, *after]) == 0


def test_compare_fails_on_one_candidate_freeze_even_when_other_runs_are_clean() -> None:
    module = _runner()
    before = [_run("before") for _index in range(3)]
    after = [_run("after") for _index in range(3)]
    after[1]["long_task_max_ms"] = 700
    after[1]["long_tasks_over_200ms"] = 1

    assert _compare(module, [*before, *after]) == 1


def test_compare_fails_before_three_runs_per_condition() -> None:
    module = _runner()
    runs = [_run("before"), _run("before"), _run("after"), _run("after")]

    assert _compare(module, runs) == 1


def test_record_retains_a_freeze_but_fails_immediately(tmp_path: Path, capsys: Any) -> None:
    module = _runner()
    module.REPO = tmp_path
    module.PENDING = tmp_path / "pending.json"
    module.RESULTS = tmp_path / "runs.jsonl"
    module._walk_facts = lambda _port: {
        "walk_elapsed_ms": 1000,
        "walk_files": 100,
        "walk_status": "done",
    }
    module.PENDING.write_text(
        json.dumps(
            {
                "commit": "abc1234",
                "corpus": "test-corpus",
                "corpus_shape": 1,
                "dirty": True,
                "experiment": "exp-test",
                "files": 100,
                "label": "candidate",
                "note": "",
                "port": 8600,
            }
        ),
        encoding="utf-8",
    )
    payload = _run(
        "candidate",
        long_task_max_ms=6393,
        long_tasks_over_200ms=1,
        viewport_h=900,
        viewport_w=1280,
    )

    result = module.cmd_record(
        argparse.Namespace(
            budgets=str(BUDGETS),
            json=json.dumps(payload),
            label=None,
            note="",
        )
    )

    assert result == 1
    assert len(module.RESULTS.read_text(encoding="utf-8").splitlines()) == 1
    assert "hard performance gate failed" in capsys.readouterr().out
