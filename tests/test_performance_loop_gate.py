"""Integration checks for performance-loop evidence and candidate gates."""

from __future__ import annotations

import argparse
import importlib.util
import io
import json
from pathlib import Path
from typing import Any, cast

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
        # Nothing observes the tree an external wheel was built from.
        "dirty": None,
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


def test_compare_accepts_an_unverified_dirty_flag_only_for_attested_wheels() -> None:
    module = _runner()
    environment_identity = f"environment:sha256:{'e' * 64}"

    def wheel_rows(label: str, digest: str) -> list[dict[str, Any]]:
        return [
            _run(
                label,
                artifact_sha256=digest * 64,
                build_identity=f"wheel:sha256:{digest * 64}",
                dirty=None,
                environment_identity=environment_identity,
                launcher_sha256="b" * 64,
            )
            for _index in range(3)
        ]

    module._load_runs = lambda: [*wheel_rows("before", "a"), *wheel_rows("after", "d")]
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

    before = [_run("before") for _index in range(3)]
    after = [_run("after", dirty=None) for _index in range(3)]
    with pytest.raises(SystemExit, match="after has no dirty"):
        _compare(module, [*before, *after])


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


SPAWNED_EPOCH_MS = 1_780_000_000_000.0


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
        "server_spawned_epoch_ms": SPAWNED_EPOCH_MS,
        "corpus_launch_marker": module._corpus_launch_marker(corpus),
        "measurement_origin": "http://127.0.0.1:8600",
        "measurement_run_id": "current",
    }
    module.PENDING.write_text(json.dumps(pending), encoding="utf-8")
    stale = _run(
        "after",
        measurement_origin=pending["measurement_origin"],
        measurement_run_id="previous",
        time_origin_epoch_ms=SPAWNED_EPOCH_MS + 2_000,
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


def _recordable_run(
    module: Any, tmp_path: Path, **pending_overrides: object
) -> tuple[Path, dict[str, Any]]:
    """A pending local run, its corpus, and a matching admissible browser payload."""

    module.REPO = tmp_path
    module.HERE = tmp_path
    module.PENDING = tmp_path / "pending.json"
    module.RESULTS = tmp_path / "runs.jsonl"
    module._walk_facts = lambda _port, _declaration=None: {
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
    (corpus / "nested").mkdir(parents=True)
    (corpus / "nested" / "sample.txt").write_text("sample\n", encoding="utf-8")
    pending: dict[str, Any] = {
        "commit": "abc1234",
        "corpus": "test-corpus",
        # What `serve` carries forward from the traversal after the previous run.
        "corpus_fingerprint_baseline": module._corpus_fingerprint(corpus),
        "corpus_launch_marker": module._corpus_launch_marker(corpus),
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
        "server_spawned_at": "2026-05-28T20:26:40.000+00:00",
        "server_spawned_epoch_ms": SPAWNED_EPOCH_MS,
    }
    pending.update(pending_overrides)
    module.PENDING.write_text(json.dumps(pending), encoding="utf-8")
    payload = _run(
        "candidate",
        measurement_origin="http://127.0.0.1:8600",
        measurement_run_id="test-run",
        time_origin_epoch_ms=SPAWNED_EPOCH_MS + 2_500,
    )
    return corpus, payload


def _record(module: Any, payload: dict[str, Any]) -> int:
    return int(
        module.cmd_record(
            argparse.Namespace(
                budgets=str(BUDGETS),
                json=json.dumps(payload),
                json_file=None,
                label=None,
                note="",
            )
        )
    )


def test_record_retains_a_freeze_but_fails_immediately(tmp_path: Path, capsys: Any) -> None:
    module = _runner()
    _corpus, payload = _recordable_run(module, tmp_path)
    payload.update(long_task_max_ms=6393, long_tasks_over_200ms=1)

    assert _record(module, payload) == 1
    recorded = json.loads(module.RESULTS.read_text(encoding="utf-8"))
    assert recorded["files"] == 101
    assert "hard performance gate failed" in capsys.readouterr().out


def test_record_attributes_the_profile_start_to_the_server_spawn(tmp_path: Path) -> None:
    module = _runner()
    _corpus, payload = _recordable_run(module, tmp_path)

    assert _record(module, payload) == 0
    recorded = json.loads(module.RESULTS.read_text(encoding="utf-8"))
    assert recorded["server_spawned_at"] == "2026-05-28T20:26:40.000+00:00"
    assert recorded["spawn_to_profile_start_ms"] == 2_500
    assert recorded["walk_elapsed_ms"] == 1000
    assert {"walk_elapsed_ms", "spawn_to_profile_start_ms"} <= set(module.METRICS)


@pytest.mark.parametrize(
    ("time_origin", "message"),
    [
        (None, "no time origin"),
        (SPAWNED_EPOCH_MS - 1, "started before the pending server was spawned"),
    ],
)
def test_record_refuses_a_profile_without_a_start_after_the_spawn(
    tmp_path: Path, time_origin: float | None, message: str
) -> None:
    module = _runner()
    _corpus, payload = _recordable_run(module, tmp_path)
    payload["time_origin_epoch_ms"] = time_origin

    with pytest.raises(SystemExit, match=message):
        _record(module, payload)
    assert not module.RESULTS.exists()


def test_record_stores_the_fingerprint_after_the_measurement(tmp_path: Path) -> None:
    module = _runner()
    corpus, payload = _recordable_run(module, tmp_path)

    assert _record(module, payload) == 0
    recorded = json.loads(module.RESULTS.read_text(encoding="utf-8"))
    assert recorded["corpus_fingerprint"] == module._corpus_fingerprint(corpus)
    # The traversal is handed to the next launch of this corpus as its baseline.
    pending = json.loads(module.PENDING.read_text(encoding="utf-8"))
    assert pending["corpus_state_after_run"] == {
        "corpus_fingerprint": recorded["corpus_fingerprint"],
        "corpus_launch_marker": module._corpus_launch_marker(corpus),
    }


def test_record_refuses_a_change_below_the_root_since_the_launch_baseline(
    tmp_path: Path,
) -> None:
    module = _runner()
    corpus, payload = _recordable_run(module, tmp_path)
    # Below the root, so the launch marker cannot see it; persisting, so the
    # post-measurement fingerprint alone would match every later row.
    (corpus / "nested" / "sample.txt").write_text("changed during the run\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="corpus changed below the root"):
        _record(module, payload)
    assert not module.RESULTS.exists()
    assert "corpus_state_after_run" not in json.loads(module.PENDING.read_text(encoding="utf-8"))


def test_record_refuses_a_run_launched_without_a_traversal_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _runner()
    _corpus, payload = _recordable_run(module, tmp_path, corpus_fingerprint_baseline=None)

    def traversal(_root: Path) -> str:
        raise AssertionError("refusing a run without a baseline needs no traversal")

    monkeypatch.setattr(module, "_corpus_fingerprint", traversal)

    with pytest.raises(SystemExit, match="without a corpus traversal after the previous run"):
        _record(module, payload)
    assert not module.RESULTS.exists()


def test_record_refuses_a_corpus_root_changed_since_serve(tmp_path: Path) -> None:
    module = _runner()
    corpus, payload = _recordable_run(module, tmp_path)
    (corpus / ".bench-corpus.json").write_text('{"shape": 3}', encoding="utf-8")

    with pytest.raises(SystemExit, match="corpus changed between serve and record"):
        _record(module, payload)


@pytest.mark.parametrize("change", ["remove-top-level-entry", "replace-root", "below-root"])
def test_corpus_launch_marker_sees_the_root_level_only(tmp_path: Path, change: str) -> None:
    module = _runner()
    corpus = tmp_path / "corpus"

    def build(root: Path) -> None:
        (root / "nested").mkdir(parents=True)
        (root / "nested" / "sample.txt").write_text("sample\n", encoding="utf-8")
        (root / "top.txt").write_text("top\n", encoding="utf-8")

    build(corpus)
    before = module._corpus_launch_marker(corpus)
    if change == "remove-top-level-entry":
        (corpus / "top.txt").unlink()
    elif change == "replace-root":
        # Built beside the old root, so the two coexist and cannot share an inode.
        replacement = tmp_path / "replacement"
        build(replacement)
        corpus.rename(tmp_path / "retired")
        replacement.rename(corpus)
    else:
        (corpus / "nested" / "sample.txt").write_text("changed\n", encoding="utf-8")

    after = module._corpus_launch_marker(corpus)
    if change == "below-root":
        # Invisible here by design: the carried full fingerprint is what sees it.
        assert after == before
    else:
        assert after != before


class _JsonResponse(io.BytesIO):
    def __enter__(self) -> _JsonResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def _serve(
    module: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    corpus: Path,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run `_serve_root` with the build, process, and socket mocked; return its pending run."""

    monkeypatch.setattr(module, "HERE", tmp_path)
    monkeypatch.setattr(module, "PENDING", tmp_path / "pending.json")
    monkeypatch.setattr(module, "PORTS_USED", tmp_path / "results" / "ports-used.txt")
    if previous is not None:
        module.PENDING.write_text(json.dumps(previous), encoding="utf-8")
    monkeypatch.setattr(
        module,
        "resolve_metab_build",
        lambda _requested: module.MetabBuild(Path("/installed/metab"), "metab 0.9.2"),
    )
    monkeypatch.setattr(
        module,
        "_build_provenance",
        lambda *_args, **_kwargs: {"build_identity": "git:abc1234", "commit": "abc1234"},
    )
    monkeypatch.setattr(module, "_stop_pending_server", lambda: None)
    monkeypatch.setattr(module, "_next_port", lambda: 8765)

    class Process:
        pid = 4321

    monkeypatch.setattr(module.subprocess, "Popen", lambda *_args, **_kwargs: Process())

    class Socket:
        def __enter__(self) -> Socket:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def settimeout(self, _timeout: float) -> None:
            return None

        def connect_ex(self, _address: tuple[str, int]) -> int:
            return 0

    monkeypatch.setattr(module.socket, "socket", Socket)

    result = module._serve_root(
        argparse.Namespace(
            artifact="",
            build_ref="",
            declare_pre_contract_inventory_identity_missing=False,
            exp="exp-test",
            label="candidate",
            metab="",
            note="",
            provider="python",
        ),
        corpus,
        "test-corpus",
        100,
    )
    assert result == 0
    return cast("dict[str, Any]", json.loads(module.PENDING.read_text(encoding="utf-8")))


def test_serve_does_not_traverse_the_corpus_before_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _runner()
    corpus = tmp_path / "corpus"
    (corpus / "nested").mkdir(parents=True)
    marker = module._corpus_launch_marker(corpus)

    def traversal(_root: Path) -> str:
        raise AssertionError("serve traversed the corpus immediately before the measured walk")

    monkeypatch.setattr(module, "_corpus_fingerprint", traversal)

    pending = _serve(module, tmp_path, monkeypatch, corpus)

    assert "corpus_fingerprint" not in pending
    assert pending["corpus_launch_marker"] == marker
    assert isinstance(pending["server_spawned_epoch_ms"], float)
    assert pending["server_spawned_at"].endswith("+00:00")


@pytest.mark.parametrize("change", ["unchanged", "other-root", "root-marker", "no-traversal"])
def test_serve_carries_the_previous_traversal_only_to_an_unchanged_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    module = _runner()
    corpus = tmp_path / "corpus"
    (corpus / "nested").mkdir(parents=True)
    state = {
        "corpus_fingerprint": module._corpus_fingerprint(corpus),
        "corpus_launch_marker": module._corpus_launch_marker(corpus),
    }
    previous: dict[str, Any] = {"server_root": str(corpus), "corpus_state_after_run": state}
    if change == "other-root":
        previous["server_root"] = str(tmp_path / "elsewhere")
    elif change == "root-marker":
        (corpus / "added").mkdir()
    elif change == "no-traversal":
        del previous["corpus_state_after_run"]

    pending = _serve(module, tmp_path, monkeypatch, corpus, previous)

    expected = state["corpus_fingerprint"] if change == "unchanged" else None
    assert pending["corpus_fingerprint_baseline"] == expected


def _walk_completes_after(
    module: Any, monkeypatch: pytest.MonkeyPatch, polls: int, events: list[str]
) -> None:
    states = iter([False] * polls + [True])

    def read_progress(url: str, *, timeout: float) -> _JsonResponse:
        assert url == "http://127.0.0.1:8600/api/index/progress"
        complete = next(states)
        events.append(f"complete={complete}")
        return _JsonResponse(json.dumps({"complete": complete}).encode())

    monkeypatch.setattr(module.urllib.request, "urlopen", read_progress)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)


def test_fingerprint_traverses_after_the_pending_walk_and_hands_it_forward(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    module = _runner()
    corpus = tmp_path / "corpus"
    (corpus / "nested").mkdir(parents=True)
    monkeypatch.setattr(module, "PENDING", tmp_path / "pending.json")
    module.PENDING.write_text(
        json.dumps({"port": 8600, "server_root": str(corpus), "measurement_run_id": "warm-up"}),
        encoding="utf-8",
    )
    events: list[str] = []
    _walk_completes_after(module, monkeypatch, 2, events)
    real_fingerprint = module._corpus_fingerprint

    def fingerprint(root: Path) -> str:
        events.append("traversal")
        return str(real_fingerprint(root))

    monkeypatch.setattr(module, "_corpus_fingerprint", fingerprint)

    assert module.cmd_fingerprint(argparse.Namespace(timeout=60.0)) == 0

    assert events == ["complete=False", "complete=False", "complete=True", "traversal"]
    pending = json.loads(module.PENDING.read_text(encoding="utf-8"))
    assert pending["measurement_run_id"] == "warm-up"
    assert pending["corpus_state_after_run"] == {
        "corpus_fingerprint": real_fingerprint(corpus),
        "corpus_launch_marker": module._corpus_launch_marker(corpus),
    }
    assert real_fingerprint(corpus) in capsys.readouterr().out


def test_a_traversal_is_not_handed_to_a_launch_it_did_not_precede(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _runner()
    monkeypatch.setattr(module, "PENDING", tmp_path / "pending.json")
    # A newer `serve` replaced the run while its traversal was still running.
    module.PENDING.write_text(json.dumps({"measurement_run_id": "newer"}), encoding="utf-8")

    module._store_corpus_state_after_run(
        "older", {"corpus_fingerprint": "f" * 64, "corpus_launch_marker": "m" * 64}
    )

    assert json.loads(module.PENDING.read_text(encoding="utf-8")) == {"measurement_run_id": "newer"}


def test_fingerprint_refuses_when_the_pending_server_is_not_answering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _runner()
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    monkeypatch.setattr(module, "PENDING", tmp_path / "pending.json")
    module.PENDING.write_text(
        json.dumps({"port": 8600, "server_root": str(corpus), "measurement_run_id": "warm-up"}),
        encoding="utf-8",
    )

    def refused(_url: str, *, timeout: float) -> None:
        raise ConnectionRefusedError("connection refused")

    def traversal(_root: Path) -> str:
        raise AssertionError("a traversal without a completed walk is not the series regime")

    monkeypatch.setattr(module.urllib.request, "urlopen", refused)
    monkeypatch.setattr(module, "_corpus_fingerprint", traversal)

    with pytest.raises(SystemExit, match="not answering"):
        module.cmd_fingerprint(argparse.Namespace(timeout=60.0))
    assert "corpus_state_after_run" not in json.loads(module.PENDING.read_text(encoding="utf-8"))


def test_a_series_refuses_a_change_below_the_root_during_its_first_recorded_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _runner()
    corpus, payload = _recordable_run(module, tmp_path)
    # The unrecorded warm-up cycle: a served run whose walk completed, then `fingerprint`.
    module.PENDING.write_text(
        json.dumps({"port": 8600, "server_root": str(corpus), "measurement_run_id": "warm-up"}),
        encoding="utf-8",
    )
    _walk_completes_after(module, monkeypatch, 0, [])
    assert module.cmd_fingerprint(argparse.Namespace(timeout=60.0)) == 0

    pending = _serve(module, tmp_path, monkeypatch, corpus)
    assert pending["corpus_fingerprint_baseline"] == module._corpus_fingerprint(corpus)
    payload.update(
        measurement_origin=pending["measurement_origin"],
        measurement_run_id=pending["measurement_run_id"],
        time_origin_epoch_ms=pending["server_spawned_epoch_ms"] + 2_500,
    )
    # The first recorded walk meets a change below the root that persists afterwards.
    (corpus / "nested" / "sample.txt").write_text("changed during the run\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="corpus changed below the root"):
        _record(module, payload)
    assert not module.RESULTS.exists()


def test_recorded_capture_refuses_a_run_without_a_traversal_baseline_before_chrome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _runner()
    module.PENDING = tmp_path / "pending.json"
    module.PENDING.write_text(
        json.dumps(
            {
                "corpus_fingerprint_baseline": None,
                "port": 8642,
                "url": "http://127.0.0.1:8642/view/?measurement_run_id=test",
            }
        ),
        encoding="utf-8",
    )

    def launch(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Chrome launched for a run that record would refuse")

    monkeypatch.setattr(module.subprocess, "run", launch)

    with pytest.raises(SystemExit, match="run.py fingerprint"):
        module.cmd_capture(
            argparse.Namespace(
                budgets=str(BUDGETS),
                chrome="",
                headed=True,
                height=900,
                label="",
                note="",
                output=str(tmp_path / "profile.json"),
                record=True,
                timeout_ms=30_000,
                width=1600,
            )
        )


def test_record_owns_the_walk_facts_a_paste_could_supply(tmp_path: Path) -> None:
    module = _runner()
    _corpus, payload = _recordable_run(module, tmp_path)
    # A fast walk logs no completion line, so the harness has no elapsed time to record.
    module._walk_facts = lambda _port, _declaration=None: {
        "inventory_contract": "inventory-provider-v1",
        "inventory_provider": "python",
        "walk_files": 101,
        "walk_status": "done",
    }
    module._inventory_facts = lambda _port: {}
    payload.update(walk_elapsed_ms=1, inventory_work={"pasted": True})

    assert _record(module, payload) == 0
    recorded = json.loads(module.RESULTS.read_text(encoding="utf-8"))
    assert "walk_elapsed_ms" not in recorded
    assert "inventory_work" not in recorded


def test_record_rechecks_the_nonce_under_the_ledger_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _runner()
    _corpus, payload = _recordable_run(module, tmp_path)
    walk_facts = module._walk_facts
    lock_operations: list[int] = []
    real_flock = module.fcntl.flock

    def concurrent_recorder(port: int, declaration: object = None) -> dict[str, Any]:
        # Another recorder of the same pending run appends after the early check.
        module.RESULTS.write_text(
            json.dumps({"measurement_run_id": "test-run"}) + "\n", encoding="utf-8"
        )
        return walk_facts(port, declaration)

    def flock(descriptor: int, operation: int) -> None:
        lock_operations.append(operation)
        real_flock(descriptor, operation)

    module._walk_facts = concurrent_recorder
    monkeypatch.setattr(module.fcntl, "flock", flock)

    with pytest.raises(SystemExit, match="measurement run nonce.*already recorded"):
        _record(module, payload)
    assert module.RESULTS.read_text(encoding="utf-8").count("test-run") == 1
    assert lock_operations[0] == module.fcntl.LOCK_EX


def test_record_requires_the_pending_nonce_on_a_server_route_sample(tmp_path: Path) -> None:
    module = _runner()
    _recordable_run(module, tmp_path)
    sample = {
        "route": "/api/tree?depth=1",
        "measurement_origin": "http://127.0.0.1:8600",
        "srv_settled_ms": 3.0,
    }

    with pytest.raises(SystemExit, match="server route sample belongs to a different pending"):
        _record(module, sample)
    assert not module.RESULTS.exists()

    assert _record(module, {**sample, "measurement_run_id": "test-run"}) == 0
    recorded = json.loads(module.RESULTS.read_text(encoding="utf-8"))
    assert recorded["measurement_run_id"] == "test-run"
    assert recorded["spawn_to_profile_start_ms"] is None


def test_server_route_sample_carries_the_pending_nonce(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    module = _runner()
    module.PENDING = tmp_path / "pending.json"
    module.PENDING.write_text(
        json.dumps(
            {
                "port": 8600,
                "measurement_origin": "http://127.0.0.1:8600",
                "measurement_run_id": "route-run",
            }
        ),
        encoding="utf-8",
    )

    class Progress(io.BytesIO):
        pass

    monkeypatch.setattr(
        module.urllib.request,
        "urlopen",
        lambda _url, *, timeout: Progress(json.dumps({"complete": True}).encode()),
    )
    monkeypatch.setattr(module, "_sample_route", lambda _port, _path: (5.0, 3.0, 100))
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    assert (
        module.cmd_probe_server(
            argparse.Namespace(path="/api/tree?depth=1", every=0.0, settled=1, timeout=30.0)
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["measurement_run_id"] == "route-run"
    assert payload["measurement_origin"] == "http://127.0.0.1:8600"


def test_pre_contract_walk_line_is_read_only_under_its_declaration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _runner()
    monkeypatch.setattr(module, "HERE", tmp_path)
    (tmp_path / "results").mkdir()
    # The v0.9.1 completion line, which names no provider or contract.
    (tmp_path / "results" / "server-8765.log").write_text(
        "INFO inventory walker complete: status=done files=300000 entries=301105 elapsed=12871ms\n",
        encoding="utf-8",
    )

    def unreachable(_url: str, *, timeout: int) -> None:
        raise AssertionError("a logged walk must not fall back to the progress route")

    monkeypatch.setattr(module.urllib.request, "urlopen", unreachable)

    assert module._walk_facts(8765, module.PRE_CONTRACT_INVENTORY_IDENTITY_MISSING) == {
        "walk_status": "done",
        "walk_elapsed_ms": 12_871,
        "walk_files": 300_000,
    }
    with pytest.raises(SystemExit, match="did not declare the pre-contract"):
        module._walk_facts(8765, None)


def test_record_persists_an_attested_pre_contract_identity_gap(tmp_path: Path) -> None:
    module = _runner()
    corpus, _payload = _recordable_run(module, tmp_path)
    attestation = argparse.Namespace(
        wheel_sha256="a" * 64,
        launcher_sha256="b" * 64,
        environment_sha256="c" * 64,
    )
    build = module.MetabBuild(executable=Path("/installed/metab"), version="metab 0.9.1")
    module.resolve_metab_build = lambda _executable: build
    module.attest_installed_wheel = lambda _build, _artifact: attestation
    module._walk_facts = lambda _port, _declaration=None: {"walk_files": 1, "walk_status": "done"}
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
                "corpus_fingerprint_baseline": module._corpus_fingerprint(corpus),
                "corpus_launch_marker": module._corpus_launch_marker(corpus),
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
                "server_spawned_epoch_ms": SPAWNED_EPOCH_MS,
            }
        ),
        encoding="utf-8",
    )
    payload = _run(
        "before",
        measurement_origin="http://127.0.0.1:8600",
        measurement_run_id="test-run",
        time_origin_epoch_ms=SPAWNED_EPOCH_MS + 1_000,
    )

    assert _record(module, payload) == 0
    recorded = json.loads(module.RESULTS.read_text(encoding="utf-8"))
    assert recorded["inventory_identity_declaration"] == (
        module.PRE_CONTRACT_INVENTORY_IDENTITY_MISSING
    )
    assert recorded["inventory_provider"] is None
    assert recorded["inventory_contract"] is None
    assert recorded["artifact_sha256"] == "a" * 64
    # An unverified source tree stays null rather than reading as clean.
    assert recorded["dirty"] is None


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
