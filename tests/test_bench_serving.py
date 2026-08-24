"""Build-selection contracts for the serving performance harness."""

from __future__ import annotations

from pathlib import Path

from devtools.bench_serving import resolve_metab_build


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
