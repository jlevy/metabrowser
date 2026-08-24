"""Build-selection contracts for the serving performance harness."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from devtools.bench_serving import (
    _record_inventory_identity,
    _rows,
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
