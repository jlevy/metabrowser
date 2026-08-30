"""Tests for `metab --show`, the four layers for one selection."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from metabrowser.cli.show_cli import run_show
from metabrowser.errors import CLIError

GIT_FIXTURE_HEAD = "703de1c4a3360d55e60646f300ceb6c926377221"

_GIT_ENV = {
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
    "GIT_AUTHOR_DATE": "2020-01-01T00:00:00Z",
    "GIT_COMMITTER_DATE": "2020-01-01T00:00:00Z",
}


@pytest.fixture
def git_root(tmp_path: Path) -> Path:
    """A repository whose revisions are identical on every machine and run."""

    import subprocess

    env = {**os.environ, **_GIT_ENV}

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, env=env, check=True, capture_output=True)

    git("init", "-q", "--initial-branch=main", ".")
    (tmp_path / "README.md").write_text("# Repo\n")
    git("add", "README.md")
    git("commit", "-q", "-m", "first commit")
    (tmp_path / "README.md").write_text("# Repo\nmore\n")
    (tmp_path / "other.txt").write_text("x\n")
    git("add", "-A")
    git("commit", "-q", "-m", "second commit")
    return tmp_path


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


@pytest.fixture
def patch_root(tmp_path: Path) -> Path:
    (tmp_path / "change.patch").write_text("--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n")
    return tmp_path


def test_show_resolves_a_view_route_the_same_as_a_bare_path(patch_root: Path, capsys: Any) -> None:
    run_show(patch_root, path="/view/change.patch")
    from_route = capsys.readouterr().out

    run_show(patch_root, path="change.patch")
    from_path = capsys.readouterr().out

    assert from_route.splitlines()[1:] == from_path.splitlines()[1:]


def test_show_resolves_a_container_inner_path(patch_root: Path, capsys: Any) -> None:
    """The container contract, reachable in one command for the first time."""

    run_show(patch_root, path="change.patch/x")

    out = capsys.readouterr().out
    assert "route: /view/change.patch/x" in out
    assert "kind: diff" in out
    assert "container=change.patch" in out
    assert "inner=x" in out


def test_show_rejects_a_malformed_commit_route(patch_root: Path) -> None:
    with pytest.raises(CLIError, match="not a route this grammar accepts"):
        run_show(patch_root, path="/commit/not-a-revision!")


def test_show_reports_a_commit_route_as_a_comparison(git_root: Path, capsys: Any) -> None:
    run_show(git_root, path=f"/commit/{GIT_FIXTURE_HEAD}")

    out = capsys.readouterr().out
    assert f"route: /commit/{GIT_FIXTURE_HEAD}" in out
    assert "kind: comparison" in out
    assert "views: diff (default)" in out
    assert "files=2" in out


def test_show_reports_one_file_inside_a_commit(git_root: Path, capsys: Any) -> None:
    run_show(git_root, path=f"/commit/{GIT_FIXTURE_HEAD}/README.md")

    out = capsys.readouterr().out
    assert "kind: comparison" in out
    assert "file=README.md" in out
