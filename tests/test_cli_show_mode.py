"""Tests for `metab --show`, the four layers for one selection."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from metabrowser.cli.show_cli import run_show
from metabrowser.errors import CLIError


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "README.md").write_text("# Sample\n\nHello.\n")
    (tmp_path / "notes.txt").write_text("plain\n")
    (tmp_path / "blob.bin").write_bytes(b"\x00\x01\x02binary")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("a\n")
    return tmp_path


def test_show_reports_the_four_layers_for_a_markdown_file(root: Path, capsys: Any) -> None:
    run_show(root, path="README.md")

    out = capsys.readouterr().out
    assert "show: README.md" in out
    assert "route: /view/README.md" in out
    assert "kind: markdown" in out
    assert "views: rendered (default), source" in out
    assert "model: text envelope;" in out


def test_show_reports_a_folder_as_a_folder_with_its_own_views(root: Path, capsys: Any) -> None:
    run_show(root, path="docs")

    out = capsys.readouterr().out
    assert "kind: folder" in out
    assert "views: overview (default), treemap" in out


def test_show_reports_a_binary_kind(root: Path, capsys: Any) -> None:
    run_show(root, path="blob.bin")

    out = capsys.readouterr().out
    assert "kind: binary" in out
    assert "views: bytes (default)" in out


def test_show_does_not_leak_the_sandbox_path(root: Path, capsys: Any) -> None:
    run_show(root, path="README.md")

    assert str(root) not in capsys.readouterr().out


def test_show_reports_a_missing_path_as_an_error(root: Path) -> None:
    with pytest.raises(CLIError, match="404"):
        run_show(root, path="missing.md")


def test_show_json_format_carries_the_same_four_layers(root: Path, capsys: Any) -> None:
    import json

    run_show(root, path="README.md", fmt="json")

    payload = json.loads(capsys.readouterr().out)
    assert payload["route"] == "/view/README.md"
    assert payload["kind"] == "markdown"
    assert [view["id"] for view in payload["views"]] == ["rendered", "source"]
