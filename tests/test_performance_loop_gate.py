"""Integration checks for performance-loop evidence and candidate gates."""

from __future__ import annotations

import argparse
import importlib.util
import io
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
    build_identity = "git:baseline" if label == "before" else "git:abc1234"
    result: dict[str, Any] = {
        "animation_frame_max_ms": 80,
        "animation_frame_blocking_ms_max": 30,
        "animation_frames_over_200ms": 0,
        "animation_frames_blocking_over_200ms": 0,
        "cls": 0.01,
        "collapsed_diff_rows_materialized": 0,
        "commit": "baseline" if label == "before" else "abc1234",
        "build_identity": build_identity,
        "build_version": "metab 0.9.2",
        "browser_identity": "TestBrowser/1.0",
        "browser_platform": "TestOS",
        "corpus": "test-corpus",
        "corpus_fingerprint": "f" * 64,
        "corpus_shape": 1,
        "device_scale_factor": 1,
        "dom_nodes": 5000,
        "dirty": False,
        "ever_hidden": False,
        "experiment": "exp-test",
        "fcp_ms": 150,
        "fetch_aborts": 0,
        "fetch_http_4xx": 0,
        "fetch_http_5xx": 0,
        "fetch_network_errors": 0,
        "fetches_in_flight": 0,
        "fetches_in_flight_max": 2,
        "fetches_in_flight_max_by_key": {"/api/tree": 2},
        "fetch_concurrency_keys_overflowed": 0,
        "file_catalog_incomplete": 0,
        "first_row_ms": 300,
        "files": 100,
        "frame_missing_px": 0,
        "index_status_at_probe": "done",
        "harness_version": 18,
        "interaction_input_coverage_pct": 90,
        "interaction_inputs": 6,
        "interaction_max_ms": 90,
        "interactions": 1,
        "inventory_delivery_max_ms": 8,
        "inventory_delivery_attribution_missing": 0,
        "inventory_delivery_work_pct": 0.2,
        "inventory_contract": "inventory-provider-v1",
        "inventory_identity_declaration": None,
        "inventory_provider": "python",
        "inventory_provider_requested": "python",
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
        "startup_style_server_ms_max": 24,
        "tree_region_repaints": 1,
        "unsupported": None,
        "visibility_state": "visible",
        "vitals_source": "navigation-profiler",
        "viewport_h": 900,
        "viewport_w": 1280,
    }
    result.update(overrides)
    return result


def test_report_reader_rejects_duplicate_experiment_ids(tmp_path: Path) -> None:
    module = _runner()
    module.EXPERIMENTS = tmp_path
    frontmatter = "---\nexperiment:\n  id: exp-001\n---\n"
    (tmp_path / "exp-001-first.md").write_text(frontmatter, encoding="utf-8")
    (tmp_path / "exp-001-second.md").write_text(frontmatter, encoding="utf-8")

    with pytest.raises(SystemExit, match=r"duplicate experiment id exp-001.*first.*second"):
        module._experiment_records()


def _compare(module: Any, runs: list[dict[str, Any]]) -> int:
    module._load_runs = lambda: runs
    return int(
        module.cmd_compare(
            argparse.Namespace(
                labels=["before", "after"],
                budgets=str(BUDGETS),
                expect_build=["before=git:baseline", "after=git:abc1234"],
            )
        )
    )


def test_external_browser_benchmark_requires_an_immutable_build_reference() -> None:
    module = _runner()
    build = module.MetabBuild(executable=Path("/installed/metab"), version="metab 0.6.0")
    module.attest_installed_wheel = lambda _build, _artifact: argparse.Namespace(
        wheel_sha256="a" * 64,
        launcher_sha256="b" * 64,
        environment_sha256="c" * 64,
    )

    try:
        module._build_provenance(build, build_ref="", artifact="/release.whl", external=True)
    except SystemExit as error:
        assert "--build-ref" in str(error)
    else:
        raise AssertionError("external build was accepted without provenance")

    assert module._build_provenance(
        build,
        build_ref="d" * 40,
        artifact="/release.whl",
        external=True,
    ) == {
        "build_identity": f"wheel:sha256:{'a' * 64}",
        "build_version": "metab 0.6.0",
        "artifact_sha256": "a" * 64,
        "launcher_sha256": "b" * 64,
        "environment_identity": f"environment:sha256:{'c' * 64}",
        "commit": "d" * 40,
        "dirty": False,
        "inventory_identity_declaration": None,
    }


def test_external_browser_benchmark_requires_the_exact_wheel() -> None:
    module = _runner()
    build = module.MetabBuild(executable=Path("/installed/metab"), version="metab 0.6.0")

    with pytest.raises(SystemExit, match="--artifact"):
        module._build_provenance(build, build_ref="d" * 40, artifact="", external=True)


def test_pre_contract_inventory_declaration_requires_exact_external_artifact() -> None:
    module = _runner()
    build = module.MetabBuild(executable=Path("/installed/metab"), version="metab 0.9.1")

    with pytest.raises(SystemExit, match="only valid with an external --metab build"):
        module._build_provenance(
            build,
            build_ref="",
            artifact="",
            external=False,
            declare_pre_contract_inventory_identity_missing=True,
        )
    with pytest.raises(SystemExit, match="--build-ref"):
        module._build_provenance(
            build,
            build_ref="short",
            artifact="/release.whl",
            external=True,
            declare_pre_contract_inventory_identity_missing=True,
        )
    with pytest.raises(SystemExit, match="--artifact"):
        module._build_provenance(
            build,
            build_ref="d" * 40,
            artifact="",
            external=True,
            declare_pre_contract_inventory_identity_missing=True,
        )


def test_pre_contract_inventory_declaration_is_bound_to_wheel_provenance() -> None:
    module = _runner()
    build = module.MetabBuild(executable=Path("/installed/metab"), version="metab 0.9.1")
    module.attest_installed_wheel = lambda _build, _artifact: argparse.Namespace(
        wheel_sha256="a" * 64,
        launcher_sha256="b" * 64,
        environment_sha256="c" * 64,
    )

    provenance = module._build_provenance(
        build,
        build_ref="d" * 40,
        artifact="/release.whl",
        external=True,
        declare_pre_contract_inventory_identity_missing=True,
    )

    assert provenance["inventory_identity_declaration"] == (
        module.PRE_CONTRACT_INVENTORY_IDENTITY_MISSING
    )
    assert provenance["build_identity"] == f"wheel:sha256:{'a' * 64}"
    assert provenance["artifact_sha256"] == "a" * 64


def test_pre_contract_inventory_declaration_has_an_explicit_serve_option(capsys: Any) -> None:
    module = _runner()

    with pytest.raises(SystemExit) as error:
        module.main(["serve", "--help"])

    assert error.value.code == 0
    assert "--declare-pre-contract-inventory-identity-missing" in capsys.readouterr().out


@pytest.mark.parametrize(
    "version",
    [
        "metab 0.9.2.dev125+16211ccb",
        "metab 0.9.1 (16211ccb)",
        "metab 0.9.2.dev125+abcdef12 (+125 commits, 16211ccb, dirty)",
    ],
)
def test_external_build_reference_matches_embedded_version_commit(version: str) -> None:
    module = _runner()
    build = module.MetabBuild(executable=Path("/installed/metab"), version=version)
    module.attest_installed_wheel = lambda _build, _artifact: argparse.Namespace(
        wheel_sha256="a" * 64,
        launcher_sha256="b" * 64,
        environment_sha256="c" * 64,
    )

    provenance = module._build_provenance(
        build,
        build_ref="16211ccb6459836c9a0813f0c3b096eef38e17b3",
        artifact="/release.whl",
        external=True,
    )

    assert provenance["commit"] == "16211ccb6459836c9a0813f0c3b096eef38e17b3"


def test_external_build_reference_rejects_embedded_version_commit_mismatch() -> None:
    module = _runner()
    build = module.MetabBuild(
        executable=Path("/installed/metab"), version="metab 0.9.2.dev125+16211ccb"
    )
    attested = False

    def attest(_build: Any, _artifact: Any) -> Any:
        nonlocal attested
        attested = True
        raise AssertionError("mismatched source ref reached wheel attestation")

    module.attest_installed_wheel = attest

    with pytest.raises(SystemExit, match="does not match.*16211ccb"):
        module._build_provenance(
            build,
            build_ref="16211ccb00000000000000000000000000000000",
            artifact="/release.whl",
            external=True,
        )
    assert attested is False


def test_local_build_identity_tracks_runtime_bytes_not_recorded_results(tmp_path: Path) -> None:
    module = _runner()
    module.REPO = tmp_path
    (tmp_path / "src").mkdir()
    runtime = tmp_path / "src" / "runtime.py"
    runtime.write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'sample'\n", encoding="utf-8")

    first = module._runtime_tree_fingerprint()
    results = tmp_path / "explorations" / "performance-loop" / "results"
    results.mkdir(parents=True)
    (results / "runs.jsonl").write_text('{"run": 1}\n', encoding="utf-8")
    generated = tmp_path / "src" / "__pycache__"
    generated.mkdir()
    (generated / "runtime.cpython-314.pyc").write_bytes(b"changes every import")
    assert module._runtime_tree_fingerprint() == first

    runtime.write_text("VALUE = 2\n", encoding="utf-8")
    assert module._runtime_tree_fingerprint() != first


def test_real_tree_preserves_the_explicit_inventory_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _runner()
    observed: list[tuple[Path, int | None]] = []

    def record_serve(_args: argparse.Namespace, root: Path, _corpus: str, files: int | None) -> int:
        observed.append((root, files))
        return 0

    monkeypatch.setattr(module, "_serve_root", record_serve)

    assert module.cmd_serve(argparse.Namespace(tree=str(tmp_path), files=60_000)) == 0
    assert observed == [(tmp_path, 60_000)]


def test_synthetic_serve_keeps_its_default_file_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _runner()
    observed: list[int | None] = []
    monkeypatch.setattr(module, "REPO", tmp_path.parent)
    monkeypatch.setattr(module, "_corpus_dir", lambda _files: tmp_path)

    def record_serve(
        _args: argparse.Namespace, _root: Path, _corpus: str, files: int | None
    ) -> int:
        observed.append(files)
        return 0

    monkeypatch.setattr(module, "_serve_root", record_serve)

    assert module.cmd_serve(argparse.Namespace(tree="", files=None)) == 0
    assert observed == [module.DEFAULT_CORPUS_FILES]


def test_fast_walk_uses_the_progress_route_when_no_info_log_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _runner()
    monkeypatch.setattr(module, "HERE", tmp_path)

    class ProgressResponse(io.BytesIO):
        def __enter__(self) -> ProgressResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            self.close()

    def read_progress(url: str, *, timeout: int) -> ProgressResponse:
        assert url == "http://127.0.0.1:8765/api/index/progress"
        assert timeout == 30
        return ProgressResponse(
            json.dumps(
                {
                    "status": "done",
                    "indexed_files": 60_000,
                    "provider": "python",
                    "contract": "inventory-provider-v1",
                }
            ).encode()
        )

    monkeypatch.setattr(module.urllib.request, "urlopen", read_progress)

    assert module._walk_facts(8765) == {
        "walk_status": "done",
        "walk_files": 60_000,
        "inventory_provider": "python",
        "inventory_contract": "inventory-provider-v1",
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
    module.PENDING.write_text(
        '{"port": 8642, "url": "http://127.0.0.1:8642/view/?measurement_run_id=test"}\n',
        encoding="utf-8",
    )
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
    assert "http://127.0.0.1:8642/view/?measurement_run_id=test" in calls[0]
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


def test_compare_fails_when_collapsed_diff_rows_are_in_the_dom() -> None:
    module = _runner()
    before = [_run("before") for _index in range(3)]
    after = [_run("after") for _index in range(3)]
    after[1]["collapsed_diff_rows_materialized"] = 18_191

    assert _compare(module, [*before, *after]) == 1


def test_compare_fails_before_three_runs_per_condition() -> None:
    module = _runner()
    runs = [_run("before"), _run("before"), _run("after"), _run("after")]

    assert _compare(module, runs) == 1


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("build_identity", "worktree:different"),
        ("build_version", "metab 0.9.3"),
        ("commit", "def5678"),
        ("dirty", True),
        ("experiment", "exp-other"),
        ("harness_version", 17),
    ],
)
def test_compare_rejects_a_label_that_mixes_build_or_round_identity(
    field: str,
    replacement: object,
) -> None:
    module = _runner()
    before = [_run("before") for _index in range(3)]
    after = [_run("after") for _index in range(3)]
    after[1][field] = replacement

    with pytest.raises(SystemExit, match=f"after spans multiple {field} values"):
        _compare(module, [*before, *after])


def test_compare_rejects_stale_candidate_rows_even_when_the_label_is_consistent() -> None:
    module = _runner()
    before = [_run("before") for _index in range(3)]
    after = [
        _run("after", build_identity="git:old", build_version="metab 0.9.1", commit="old")
        for _index in range(3)
    ]

    with pytest.raises(SystemExit, match="not expected build git:abc1234"):
        _compare(module, [*before, *after])


def test_compare_requires_distinct_conditions_and_builds() -> None:
    module = _runner()
    with pytest.raises(SystemExit, match="at least two distinct"):
        module.cmd_compare(
            argparse.Namespace(
                labels=["after"],
                budgets=str(BUDGETS),
                expect_build=["after=git:abc1234"],
            )
        )

    before = [_run("before", build_identity="git:same") for _index in range(3)]
    after = [_run("after", build_identity="git:same") for _index in range(3)]
    module._load_runs = lambda: [*before, *after]
    with pytest.raises(SystemExit, match="distinct build artifacts"):
        module.cmd_compare(
            argparse.Namespace(
                labels=["before", "after"],
                budgets=str(BUDGETS),
                expect_build=["before=git:same", "after=git:same"],
            )
        )


def test_compare_accepts_an_attested_pre_contract_identity_gap() -> None:
    module = _runner()
    environment_identity = f"environment:sha256:{'e' * 64}"
    before = [
        _run(
            "before",
            artifact_sha256="a" * 64,
            build_identity=f"wheel:sha256:{'a' * 64}",
            environment_identity=environment_identity,
            inventory_contract=None,
            inventory_identity_declaration=module.PRE_CONTRACT_INVENTORY_IDENTITY_MISSING,
            inventory_provider=None,
            launcher_sha256="b" * 64,
        )
        for _index in range(3)
    ]
    after = [
        _run(
            "after",
            artifact_sha256="d" * 64,
            build_identity=f"wheel:sha256:{'d' * 64}",
            environment_identity=environment_identity,
            launcher_sha256="f" * 64,
        )
        for _index in range(3)
    ]
    module._load_runs = lambda: [*before, *after]

    assert (
        module.cmd_compare(
            argparse.Namespace(
                labels=["before", "after"],
                budgets=str(BUDGETS),
                expect_build=[
                    f"before=wheel:sha256:{'a' * 64}",
                    f"after=wheel:sha256:{'d' * 64}",
                ],
            )
        )
        == 0
    )


def test_compare_rejects_a_label_that_mixes_pre_contract_declarations() -> None:
    module = _runner()
    before = [_run("before") for _index in range(3)]
    after = [_run("after") for _index in range(3)]
    before[1]["inventory_identity_declaration"] = module.PRE_CONTRACT_INVENTORY_IDENTITY_MISSING

    with pytest.raises(SystemExit, match="before spans multiple inventory_identity_declaration"):
        _compare(module, [*before, *after])


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("viewport_w", 1600),
        ("viewport_h", 1000),
        ("device_scale_factor", 2),
        ("browser_identity", "OtherBrowser/2.0"),
        ("browser_platform", "OtherOS"),
        ("corpus_fingerprint", "0" * 64),
    ],
)
def test_compare_rejects_incomparable_conditions(field: str, replacement: object) -> None:
    module = _runner()
    before = [_run("before") for _index in range(3)]
    after = [_run("after", **{field: replacement}) for _index in range(3)]

    with pytest.raises(SystemExit, match=f"conditions do not share one {field}"):
        _compare(module, [*before, *after])


def test_record_rejects_a_stale_profile_and_changed_corpus(tmp_path: Path) -> None:
    module = _runner()
    module.PENDING = tmp_path / "pending.json"
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    source = corpus / "sample.txt"
    source.write_text("before\n", encoding="utf-8")
    pending = {
        "port": 8600,
        "server_root": str(corpus),
        "corpus_fingerprint": module._corpus_fingerprint(corpus),
        "measurement_origin": "http://127.0.0.1:8600",
        "measurement_run_id": "current",
    }
    module.PENDING.write_text(json.dumps(pending), encoding="utf-8")
    stale = _run(
        "after",
        measurement_origin=pending["measurement_origin"],
        measurement_run_id="previous",
    )
    with pytest.raises(SystemExit, match="different pending measurement"):
        module.cmd_record(
            argparse.Namespace(
                budgets=str(BUDGETS), json=json.dumps(stale), json_file=None, label="", note=""
            )
        )

    source.write_text("after!\n", encoding="utf-8")
    current = {**stale, "measurement_run_id": "current"}
    with pytest.raises(SystemExit, match="corpus changed"):
        module.cmd_record(
            argparse.Namespace(
                budgets=str(BUDGETS),
                json=json.dumps(current),
                json_file=None,
                label="",
                note="",
            )
        )


def test_record_refuses_a_measurement_nonce_already_in_the_ledger(tmp_path: Path) -> None:
    module = _runner()
    module.PENDING = tmp_path / "pending.json"
    module.RESULTS = tmp_path / "runs.jsonl"
    module.PENDING.write_text(
        json.dumps({"measurement_run_id": "duplicate-run"}),
        encoding="utf-8",
    )
    module.RESULTS.write_text(
        json.dumps({"measurement_run_id": "duplicate-run"}) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="measurement run nonce.*already recorded"):
        module.cmd_record(
            argparse.Namespace(
                budgets=str(BUDGETS),
                json=json.dumps(_run("after")),
                json_file=None,
                label="",
                note="",
            )
        )


def test_record_retains_a_freeze_but_fails_immediately(tmp_path: Path, capsys: Any) -> None:
    module = _runner()
    module.REPO = tmp_path
    module.PENDING = tmp_path / "pending.json"
    module.RESULTS = tmp_path / "runs.jsonl"
    module._walk_facts = lambda _port: {
        "inventory_contract": "inventory-provider-v1",
        "inventory_provider": "python",
        "walk_elapsed_ms": 1000,
        "walk_files": 101,
        "walk_status": "done",
    }
    module._inventory_facts = lambda _port: {
        "inventory_contract": "inventory-provider-v1",
        "inventory_provider": "python",
        "inventory_work": {},
    }
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "sample.txt").write_text("sample\n", encoding="utf-8")
    corpus_fingerprint = module._corpus_fingerprint(corpus)
    module.PENDING.write_text(
        json.dumps(
            {
                "commit": "abc1234",
                "corpus": "test-corpus",
                "corpus_fingerprint": corpus_fingerprint,
                "corpus_shape": 1,
                "dirty": True,
                "experiment": "exp-test",
                "files": 100,
                "label": "candidate",
                "note": "",
                "port": 8600,
                "inventory_provider_requested": "python",
                "measurement_origin": "http://127.0.0.1:8600",
                "measurement_run_id": "test-run",
                "server_root": str(corpus),
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
        measurement_origin="http://127.0.0.1:8600",
        measurement_run_id="test-run",
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


def test_record_persists_an_attested_pre_contract_identity_gap(tmp_path: Path) -> None:
    module = _runner()
    module.REPO = tmp_path
    module.PENDING = tmp_path / "pending.json"
    module.RESULTS = tmp_path / "runs.jsonl"
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "sample.txt").write_text("sample\n", encoding="utf-8")
    attestation = argparse.Namespace(
        wheel_sha256="a" * 64,
        launcher_sha256="b" * 64,
        environment_sha256="c" * 64,
    )
    build = module.MetabBuild(executable=Path("/installed/metab"), version="metab 0.9.1")
    module.resolve_metab_build = lambda _executable: build
    module.attest_installed_wheel = lambda _build, _artifact: attestation
    module._walk_facts = lambda _port: {"walk_files": 1, "walk_status": "done"}
    module._inventory_facts = lambda _port: {}
    provenance = module._build_provenance(
        build,
        build_ref="16211ccb6459836c9a0813f0c3b096eef38e17b3",
        artifact="/release.whl",
        external=True,
        declare_pre_contract_inventory_identity_missing=True,
    )
    module.PENDING.write_text(
        json.dumps(
            {
                **provenance,
                "artifact_path": "/release.whl",
                "corpus": "test-corpus",
                "corpus_fingerprint": module._corpus_fingerprint(corpus),
                "corpus_shape": 1,
                "experiment": "exp-test",
                "files": 1,
                "inventory_provider_requested": "python",
                "label": "before",
                "measurement_origin": "http://127.0.0.1:8600",
                "measurement_run_id": "test-run",
                "note": "",
                "port": 8600,
                "server_executable": str(build.executable),
                "server_root": str(corpus),
            }
        ),
        encoding="utf-8",
    )
    payload = _run(
        "before",
        measurement_origin="http://127.0.0.1:8600",
        measurement_run_id="test-run",
    )

    assert (
        module.cmd_record(
            argparse.Namespace(
                budgets=str(BUDGETS),
                json=json.dumps(payload),
                json_file=None,
                label="",
                note="",
            )
        )
        == 0
    )
    recorded = json.loads(module.RESULTS.read_text(encoding="utf-8"))
    assert recorded["inventory_identity_declaration"] == (
        module.PRE_CONTRACT_INVENTORY_IDENTITY_MISSING
    )
    assert recorded["inventory_provider"] is None
    assert recorded["inventory_contract"] is None
    assert recorded["artifact_sha256"] == "a" * 64


def test_record_identity_rejects_missing_and_conflicting_server_facts() -> None:
    module = _runner()

    with pytest.raises(SystemExit, match="did not report an inventory provider and contract"):
        module._require_inventory_identity({}, {}, "python", None)

    assert module._require_inventory_identity(
        {},
        {},
        "python",
        module.PRE_CONTRACT_INVENTORY_IDENTITY_MISSING,
    ) == (None, None)

    with pytest.raises(SystemExit, match="pre-contract declaration conflicts"):
        module._require_inventory_identity(
            {
                "inventory_provider": "python",
                "inventory_contract": "inventory-provider-v1",
            },
            {},
            "python",
            module.PRE_CONTRACT_INVENTORY_IDENTITY_MISSING,
        )

    with pytest.raises(SystemExit, match="conflicting inventory identities"):
        module._require_inventory_identity(
            {
                "inventory_provider": "python",
                "inventory_contract": "inventory-provider-v1",
            },
            {
                "inventory_provider": "fdu",
                "inventory_contract": "inventory-provider-v1",
            },
            "python",
            None,
        )


def test_compare_rejects_a_duplicate_measurement_nonce() -> None:
    module = _runner()
    before = [_run("before", measurement_run_id=f"before-{index}") for index in range(3)]
    after = [_run("after", measurement_run_id=f"after-{index}") for index in range(3)]
    after[2]["measurement_run_id"] = after[0]["measurement_run_id"]

    with pytest.raises(SystemExit, match="duplicate measurement_run_id.*after-0"):
        _compare(module, [*before, *after])


def test_compare_requires_a_nonce_for_current_harness_evidence() -> None:
    module = _runner()
    before = [
        _run(
            "before",
            harness_version=module.HARNESS_VERSION,
            measurement_run_id=f"before-{index}",
        )
        for index in range(3)
    ]
    after = [
        _run(
            "after",
            harness_version=module.HARNESS_VERSION,
            measurement_run_id=f"after-{index}",
        )
        for index in range(3)
    ]
    del after[1]["measurement_run_id"]

    with pytest.raises(SystemExit, match="after row 2 has no measurement_run_id"):
        _compare(module, [*before, *after])
