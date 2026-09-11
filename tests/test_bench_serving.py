"""Build-selection contracts for the serving performance harness."""

from __future__ import annotations

import hashlib
import inspect
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from devtools.bench_serving import (
    MetabBuild,
    Server,
    WheelAttestation,
    _record_inventory_identity,
    _rows,
    _wheel_release_manifest,
    attest_installed_wheel,
    build_corpus,
    phase_settled,
    resolve_metab_build,
)


def test_explicit_benchmark_build_is_resolved_and_versioned(tmp_path: Path) -> None:
    executable = tmp_path / "metab-release"
    executable.write_text("#!/bin/sh\nprintf 'metab 0.6.0\\n'\n", encoding="utf-8")
    executable.chmod(0o755)

    build = resolve_metab_build(str(executable))

    assert build.executable == executable.resolve()
    assert build.version == "metab 0.6.0"


def _write_test_wheel(path: Path, module_source: str = "VALUE = 1\n") -> None:
    metadata = "Metadata-Version: 2.1\nName: metabrowser\nVersion: 0.6.0\n"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("metabrowser/__init__.py", module_source)
        archive.writestr("metabrowser-0.6.0.dist-info/METADATA", metadata)
        archive.writestr(
            "metabrowser-0.6.0.dist-info/entry_points.txt",
            "[console_scripts]\nmetab = metabrowser.cli.entrypoint:main\n",
        )
        archive.writestr("metabrowser-0.6.0.dist-info/RECORD", "")


def _attestation_payload(wheel: Path, *, editable: bool = False) -> dict[str, object]:
    _project, version, _entry_point, files = _wheel_release_manifest(wheel)
    return {
        "distribution_name": "metabrowser",
        "distribution_version": version,
        "editable": editable,
        "files": files,
        "package_files": sorted(name for name in files if name.startswith("metabrowser/")),
        "environment": {
            "python": sys.version,
            "implementation": "CPython",
            "machine": "test",
            "distributions": [["metabrowser", version, "record-hash"]],
        },
    }


def test_installed_build_attestation_binds_wheel_and_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wheel = tmp_path / "metabrowser-0.6.0-py3-none-any.whl"
    _write_test_wheel(wheel)
    executable = tmp_path / "metab"
    executable.write_text(
        f"#!{sys.executable}\n"
        "import sys\n"
        "from metabrowser.cli.entrypoint import main\n"
        'if __name__ == "__main__":\n'
        '    if sys.argv[0].endswith("-script.pyw"):\n'
        "        sys.argv[0] = sys.argv[0][:-11]\n"
        '    elif sys.argv[0].endswith(".exe"):\n'
        "        sys.argv[0] = sys.argv[0][:-4]\n"
        "    sys.exit(main())\n",
        encoding="utf-8",
    )
    build = MetabBuild(executable, "metab 0.6.0")
    payload = _attestation_payload(wheel)
    monkeypatch.setattr(
        "devtools.bench_serving.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout=json.dumps(payload), stderr=""
        ),
    )

    attestation = attest_installed_wheel(build, wheel)

    assert isinstance(attestation, WheelAttestation)
    assert attestation.wheel_sha256 == hashlib.sha256(wheel.read_bytes()).hexdigest()
    assert len(attestation.launcher_sha256) == 64
    assert len(attestation.environment_sha256) == 64


def test_installed_build_attestation_rejects_mismatched_or_editable_install(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wheel = tmp_path / "metabrowser-0.6.0-py3-none-any.whl"
    _write_test_wheel(wheel)
    executable = tmp_path / "metab"
    executable.write_text(
        f"#!{sys.executable}\n"
        "import sys\n"
        "from metabrowser.cli.entrypoint import main\n"
        'if __name__ == "__main__":\n'
        '    if sys.argv[0].endswith("-script.pyw"):\n'
        "        sys.argv[0] = sys.argv[0][:-11]\n"
        '    elif sys.argv[0].endswith(".exe"):\n'
        "        sys.argv[0] = sys.argv[0][:-4]\n"
        "    sys.exit(main())\n",
        encoding="utf-8",
    )
    build = MetabBuild(executable, "metab 0.6.0")
    payload = _attestation_payload(wheel)
    payload["files"] = {"metabrowser/__init__.py": {"sha256": "0" * 64, "size": 10}}
    monkeypatch.setattr(
        "devtools.bench_serving.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout=json.dumps(payload), stderr=""
        ),
    )
    with pytest.raises(SystemExit, match="do not match"):
        attest_installed_wheel(build, wheel)

    payload = _attestation_payload(wheel, editable=True)
    with pytest.raises(SystemExit, match="editable"):
        attest_installed_wheel(build, wheel)


def test_distinct_wheel_bytes_have_distinct_artifact_identities(tmp_path: Path) -> None:
    first = tmp_path / "first.whl"
    second = tmp_path / "second.whl"
    _write_test_wheel(first, "VALUE = 1\n")
    _write_test_wheel(second, "VALUE = 2\n")

    assert (
        hashlib.sha256(first.read_bytes()).digest() != hashlib.sha256(second.read_bytes()).digest()
    )


def test_installed_build_attestation_rejects_a_different_python_launcher(
    tmp_path: Path,
) -> None:
    wheel = tmp_path / "metabrowser-0.6.0-py3-none-any.whl"
    _write_test_wheel(wheel)
    executable = tmp_path / "metab"
    executable.write_text(
        f"#!{sys.executable}\nprint('metab 0.6.0')\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="does not invoke"):
        attest_installed_wheel(MetabBuild(executable, "metab 0.6.0"), wheel)


def test_unusable_benchmark_build_fails_with_the_requested_path(tmp_path: Path) -> None:
    missing = tmp_path / "missing-metab"

    try:
        resolve_metab_build(str(missing))
    except SystemExit as error:
        assert str(missing) in str(error)
    else:
        raise AssertionError("missing benchmark executable was accepted")


def test_inventory_identity_validation_allows_an_explicitly_skipped_cold_scan() -> None:
    diagnostics = {
        "provider": "python",
        "contract": "inventory-provider-v1",
    }
    result = {
        "scan_with_client": {"diagnostics": diagnostics},
        "settled": {"diagnostics": diagnostics},
    }

    _record_inventory_identity(result, "python")

    assert result["inventory"] == diagnostics


def test_inventory_identity_validation_rejects_a_present_phase_without_identity() -> None:
    result = {
        "scan_with_client": {"diagnostics": {}},
        "settled": {
            "diagnostics": {
                "provider": "python",
                "contract": "inventory-provider-v1",
            }
        },
    }

    with pytest.raises(SystemExit, match="scan_with_client"):
        _record_inventory_identity(result, "python")


def test_synthetic_corpus_has_an_independent_git_boundary(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"

    result = build_corpus(corpus, 1)

    assert result["shape"] == 2
    assert result["ignored_files"] == 0
    assert (corpus / ".git" / "HEAD").read_text() == "ref: refs/heads/main\n"


def test_settled_benchmark_covers_navigation_and_catalog_cache_paths() -> None:
    source = inspect.getsource(phase_settled)
    assert 'navigation_url = f"{base}/api/tree?depth=0"' in source
    assert 'catalog_url = f"{base}/api/catalog"' in source
    assert 'catalog_payload.get("complete") is not True' in source
    assert "body == catalog_body" in source
    assert "status == 304 and not body" in source

    rows = dict(
        _rows(
            {
                "settled": {
                    "navigation_first_ms": 10.0,
                    "navigation_reused_ms": {"p50": 1.0},
                    "catalog_first_ms": 20.0,
                    "catalog_retained_body_ms": {"p50": 2.0},
                    "catalog_revalidated_304_ms": {"p50": 0.5},
                }
            }
        )
    )
    assert rows["settled navigation, first pass (ms)"] == 10.0
    assert rows["settled navigation, memo p50 (ms)"] == 1.0
    assert rows["settled catalog, first body (ms)"] == 20.0
    assert rows["settled catalog, retained body p50 (ms)"] == 2.0
    assert rows["settled catalog, 304 p50 (ms)"] == 0.5


def test_benchmark_observes_fast_scan_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("METABROWSER_LOG_LEVEL", "WARNING")
    root = tmp_path / "corpus"
    build_corpus(root, 1)
    build = resolve_metab_build("metab")
    with Server(root, tmp_path / "server.log", build, provider="python") as server:
        completed = server.await_walk(timeout_s=10)
        assert completed is not None
        assert completed["files"] == 1
        assert completed["status"] == "done"
