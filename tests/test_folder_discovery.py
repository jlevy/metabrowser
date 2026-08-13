from __future__ import annotations

from pathlib import Path

import pytest

from metabrowser.folder_discovery import discover_folder


def test_discovers_preferred_and_unusual_readme_casing(tmp_path: Path) -> None:
    (tmp_path / "rEaDmE.mD").write_text("unusual")
    result = discover_folder(tmp_path, max_entries=10)
    assert result.readme_name == "rEaDmE.mD"
    assert result.readme_search_truncated is False


def test_prefers_canonical_name_and_ignores_symlink(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("canonical")
    target = tmp_path / "target.md"
    target.write_text("target")
    link = tmp_path / "Readme.md"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlinks unavailable")
    assert discover_folder(tmp_path, max_entries=10).readme_name == "README.md"


def test_scan_is_bounded_and_never_recurses(tmp_path: Path) -> None:
    for name in ("a", "b", "c"):
        (tmp_path / name).write_text(name)
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "README.md").write_text("nested")
    result = discover_folder(tmp_path, max_entries=2)
    assert result.readme_name == ""
    assert result.readme_search_truncated is True


def test_rejects_negative_limit(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="nonnegative"):
        discover_folder(tmp_path, max_entries=-1)
