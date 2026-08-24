from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

import pytest

from metabrowser import folder_discovery
from metabrowser.folder_discovery import discover_folder


class _FakeDirEntry:
    def __init__(self, name: str) -> None:
        self.name = name

    def is_file(self, *, follow_symlinks: bool) -> bool:
        assert follow_symlinks is False
        return True


def test_discovers_unusual_readme_casing(tmp_path: Path) -> None:
    (tmp_path / "rEaDmE.mD").write_text("unusual")
    result = discover_folder(tmp_path, max_entries=10)
    assert result.readme_name == "rEaDmE.mD"
    assert result.readme_search_truncated is False


def test_discovers_canonical_readme(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("canonical")
    assert discover_folder(tmp_path, max_entries=10).readme_name == "README.md"


def test_prefers_canonical_readme_when_case_variants_can_coexist(
    tmp_path: Path, monkeypatch: Any
) -> None:
    entries = [_FakeDirEntry("Readme.md"), _FakeDirEntry("README.md")]

    def fake_scandir(_target: object) -> contextlib.AbstractContextManager[list[_FakeDirEntry]]:
        return contextlib.nullcontext(entries)

    monkeypatch.setattr(folder_discovery.os, "scandir", fake_scandir)

    assert discover_folder(tmp_path, max_entries=10).readme_name == "README.md"


def test_ignores_readme_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target.md"
    target.write_text("target")
    (tmp_path / "README.md").symlink_to(target)

    assert discover_folder(tmp_path, max_entries=10).readme_name == ""


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
