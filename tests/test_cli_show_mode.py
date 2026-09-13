"""Tests for `metab --show`, the four layers for one selection."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pytest

from metabrowser.cli.show_cli import run_show
from metabrowser.errors import CLIError
from metabrowser.git.process import _REPO_PINNING_GIT_VARS

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
    """A repository whose revisions are identical on every machine and run.

    The repository-pinning variables are scrubbed for the same reason
    `metabrowser.git.process` scrubs them on every spawn, and this fixture is the case
    that comment describes. Run from inside a githook -- which the pre-push gate is --
    git has exported ``GIT_DIR`` and ``GIT_WORK_TREE`` pointing at the real repository,
    and they take precedence over ``cwd``. Inherited here, ``git init`` and the two
    commits below land in *that* repository instead of building the fixture: the
    developer's checkout acquires two stray commits, and ``tmp_path`` never becomes a
    repository at all, so the revision this file pins by hash resolves to a 404.

    It passes standalone and fails only under the hook, from a linked worktree, which is
    the hardest version of that bug to place from the symptom.
    """

    import subprocess

    env = {key: value for key, value in os.environ.items() if key not in _REPO_PINNING_GIT_VARS}
    env.update(_GIT_ENV)

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


@pytest.fixture
def percent_root(tmp_path: Path) -> Path:
    """Names whose native and canonical spellings can be mistaken for each other."""

    (tmp_path / "%41.md").write_text("# First\n")
    (tmp_path / "%2541.md").write_text("# Second sibling\n")
    (tmp_path / "docs%1").mkdir()
    (tmp_path / "docs%1" / "note%.txt").write_text("nested percent\n")
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


def test_show_reports_a_slash_bearing_git_ref_as_one_revision_segment(
    git_root: Path,
    capsys: Any,
) -> None:
    run_show(git_root, path="/commit/refs%2Fheads%2Fmain")

    out = capsys.readouterr().out
    assert "route: /commit/refs%2Fheads%2Fmain" in out
    assert "kind: comparison" in out
    assert "files=2" in out


@pytest.mark.parametrize(
    ("native_path", "view_route", "size"),
    [
        ("%41.md", "/view/%2541.md", 8),
        ("%2541.md", "/view/%252541.md", 17),
        ("docs%1/note%.txt", "/view/docs%251/note%25.txt", 15),
    ],
)
def test_show_keeps_native_and_view_percent_paths_on_one_identity(
    percent_root: Path,
    capsys: Any,
    native_path: str,
    view_route: str,
    size: int,
) -> None:
    """A bare path and its decoded browser route must select the same entry."""

    run_show(percent_root, path=native_path)
    from_native = capsys.readouterr().out

    run_show(percent_root, path=view_route)
    from_route = capsys.readouterr().out

    assert f"route: {view_route}" in from_native
    assert f"size={size}" in from_native
    assert from_route.splitlines()[1:] == from_native.splitlines()[1:]


def test_show_opens_a_literal_percent_directory(percent_root: Path, capsys: Any) -> None:
    run_show(percent_root, path="docs%1")
    from_native = capsys.readouterr().out

    run_show(percent_root, path="/view/docs%251")
    from_route = capsys.readouterr().out

    assert "route: /view/docs%251" in from_native
    assert "kind: folder" in from_native
    assert from_route.splitlines()[1:] == from_native.splitlines()[1:]


@pytest.mark.skipif(os.name == "nt", reason="POSIX filenames retain undecodable bytes")
def test_show_formats_an_undecodable_filename_from_native_and_route_input(
    tmp_path: Path,
    capsys: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lookup and route reporting use the same total path identity codec."""

    import json

    from metabrowser.cli.asgi_client import ApiResponse

    native = os.fsdecode(b"raw\xff.md")

    async def fetch_identity(*_args: Any, **_kwargs: Any) -> ApiResponse:
        return ApiResponse(
            status_code=200,
            body=json.dumps(
                {
                    "path": "raw%FF.md",
                    "type": "text",
                    "kind": "markdown",
                    "views": [
                        {"id": "rendered", "default": True},
                        {"id": "source", "default": False},
                    ],
                    "size": 6,
                    "content_bytes": 6,
                    "content_truncated": False,
                }
            ).encode(),
        )

    monkeypatch.setattr("metabrowser.cli.show_cli._fetch", fetch_identity)

    run_show(tmp_path, path=native)
    from_native = capsys.readouterr().out

    run_show(tmp_path, path="/view/raw%FF.md")
    from_route = capsys.readouterr().out

    assert "route: /view/raw%FF.md" in from_native
    assert "kind: markdown" in from_native
    assert from_route.splitlines()[1:] == from_native.splitlines()[1:]


@pytest.mark.skipif(os.name == "nt", reason="POSIX argv can retain undecodable bytes")
def test_show_reports_an_unencoded_route_byte_without_a_unicode_crash(tmp_path: Path) -> None:
    raw_route = "/view/raw" + os.fsdecode(b"\xff") + ".md"

    with pytest.raises(
        CLIError,
        match=r"/view/raw%FF\.md is not a route this grammar accepts",
    ):
        run_show(tmp_path, path=raw_route)


@pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="the macOS filesystem rejects undecodable byte names",
)
def test_show_reads_an_undecodable_filename_from_a_real_posix_directory(
    tmp_path: Path,
    capsys: Any,
) -> None:
    native = os.fsdecode(b"raw\xff.md")
    (tmp_path / native).write_text("# Raw\n")

    run_show(tmp_path, path="/view/raw%FF.md")

    assert "route: /view/raw%FF.md" in capsys.readouterr().out
