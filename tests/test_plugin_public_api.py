"""Public Python helpers used by installed plugin sidekicks."""

from __future__ import annotations

from pathlib import Path

from metabrowser import (
    ArtifactPath,
    detect_adapter,
    extract_agent_charts_cached,
    paths_safe,
    register_root_callback,
    relativize_path,
    resolve_directory,
    resolve_path,
)
from metabrowser.paths_safe import _set_root_dir


def test_sidekick_path_helpers_are_public_and_root_bounded(tmp_path: Path) -> None:
    original_root = paths_safe.ROOT_DIR
    try:
        _set_root_dir(tmp_path)
        folder = tmp_path / "reports"
        folder.mkdir()
        report = folder / "summary.md"
        report.write_text("# Summary\n")

        assert resolve_path("reports/summary.md") == report
        assert resolve_directory("reports") == folder
        assert resolve_path("../outside.txt") is None
        assert resolve_directory("reports/summary.md") is None
        assert relativize_path(str(report)) == "reports/summary.md"
    finally:
        _set_root_dir(original_root)


def test_sidekick_runtime_helpers_are_public() -> None:
    assert ArtifactPath.__name__ == "ArtifactPath"
    assert callable(detect_adapter)
    assert callable(extract_agent_charts_cached)
    assert callable(register_root_callback)
