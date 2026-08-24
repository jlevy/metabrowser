"""Build-selection contracts for the serving performance harness."""

from __future__ import annotations

from pathlib import Path

import pytest

from devtools.bench_serving import _record_inventory_identity, resolve_metab_build


def test_explicit_benchmark_build_is_resolved_and_versioned(tmp_path: Path) -> None:
    executable = tmp_path / "metab-release"
    executable.write_text("#!/bin/sh\nprintf 'metab 0.6.0\\n'\n", encoding="utf-8")
    executable.chmod(0o755)

    build = resolve_metab_build(str(executable))

    assert build.executable == executable.resolve()
    assert build.version == "metab 0.6.0"


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
