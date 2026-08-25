"""Integration checks for performance-loop evidence and candidate gates."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

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
        "index_status_at_probe": "done",
        "harness_version": 15,
        "interaction_input_coverage_pct": 90,
        "interaction_inputs": 6,
        "interaction_max_ms": 90,
        "interactions": 1,
        "inventory_delivery_max_ms": 8,
        "inventory_delivery_attribution_missing": 0,
        "inventory_delivery_work_pct": 0.2,
        "label": label,
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
    result.update(overrides)
    return result


def _compare(module: Any, runs: list[dict[str, Any]]) -> int:
    module._load_runs = lambda: runs
    return int(
        module.cmd_compare(argparse.Namespace(labels=["before", "after"], budgets=str(BUDGETS)))
    )


def test_external_browser_benchmark_requires_an_immutable_build_reference() -> None:
    module = _runner()

    try:
        module._build_provenance("metab 0.6.0", build_ref="", external=True)
    except SystemExit as error:
        assert "--build-ref" in str(error)
    else:
        raise AssertionError("external build was accepted without provenance")

    assert module._build_provenance("metab 0.6.0", build_ref="v0.6.0", external=True) == {
        "build_version": "metab 0.6.0",
        "commit": "v0.6.0",
        "dirty": False,
    }


def test_port_allocation_outlives_the_original_hundred_run_range(
    tmp_path: Path, monkeypatch: Any
) -> None:
    module = _runner()
    module.PORTS_USED = tmp_path / "ports-used"
    module._load_runs = lambda: [{"port": port} for port in range(8600, 8700)]
    checked: list[str] = []

    def unavailable(url: str, *, timeout: float) -> None:
        checked.append(url)
        assert timeout == 0.2
        raise OSError

    monkeypatch.setattr(module.urllib.request, "urlopen", unavailable)

    assert module._next_port() == 8700
    assert checked == ["http://127.0.0.1:8700/"]


def test_browser_harness_stops_only_the_server_it_started() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert 'subprocess.run(["pkill"' not in source
    assert 'subprocess.run(["pgrep"' not in source
    assert '"server_pid": process.pid' in source
    assert "_stop_pending_server()" in source


def test_browser_profile_can_be_loaded_from_a_file(tmp_path: Any) -> None:
    module = _runner()
    profile = tmp_path / "profile.json"
    profile.write_text('{"viewport_w": 1600, "viewport_h": 900}\n', encoding="utf-8")

    assert module._load_probe_payload("", str(profile)) == {
        "viewport_w": 1600,
        "viewport_h": 900,
    }


def test_browser_capture_uses_the_pending_port_and_headed_driver(
    tmp_path: Path, monkeypatch: Any
) -> None:
    module = _runner()
    module.PENDING = tmp_path / "pending.json"
    module.PENDING.write_text('{"port": 8642}\n', encoding="utf-8")
    monkeypatch.setattr(
        module.shutil, "which", lambda name: "/usr/bin/node" if name == "node" else None
    )
    calls: list[list[str]] = []

    class Result:
        returncode = 0

    def run(command: list[str], **_kwargs: object) -> Result:
        calls.append(command)
        return Result()

    monkeypatch.setattr(module.subprocess, "run", run)
    output = tmp_path / "profile.json"

    result = module.cmd_capture(
        argparse.Namespace(
            budgets=str(BUDGETS),
            chrome="",
            headed=True,
            height=900,
            label="",
            note="",
            output=str(output),
            record=False,
            timeout_ms=30_000,
            width=1600,
        )
    )

    assert result == 0
    assert len(calls) == 1
    assert "http://127.0.0.1:8642/view/" in calls[0]
    assert "--headed" in calls[0]
    assert str(output.resolve()) in calls[0]


def test_recorded_browser_capture_requires_headed_chrome(tmp_path: Path) -> None:
    module = _runner()

    with pytest.raises(SystemExit, match="--headed is required"):
        module.cmd_capture(
            argparse.Namespace(
                budgets=str(BUDGETS),
                chrome="",
                headed=False,
                height=900,
                label="",
                note="",
                output=str(tmp_path / "profile.json"),
                record=True,
                timeout_ms=30_000,
                width=1600,
            )
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


def test_compare_fails_on_one_candidate_rendered_error() -> None:
    module = _runner()
    before = [_run("before") for _index in range(3)]
    after = [_run("after") for _index in range(3)]
    after[1]["rendered_preview_errors"] = 1

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
        "walk_files": 101,
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
            json_file=None,
            label=None,
            note="",
        )
    )

    assert result == 1
    recorded = json.loads(module.RESULTS.read_text(encoding="utf-8"))
    assert recorded["files"] == 101
    assert "hard performance gate failed" in capsys.readouterr().out
