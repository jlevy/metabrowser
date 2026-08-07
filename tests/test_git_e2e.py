"""End-to-end checks for ``/api/git/`` through the real route stack.

``test_git_api.py`` calls the handlers directly, which is the right level
for parser and bounds coverage. This file goes through the mounted
Starlette application instead, so route registration, path-parameter
extraction, and the middleware stack are exercised too — the pieces that
a direct handler call silently skips.

The flow mirrors what the browser actually does: gate on ``/api/git/repo``,
load a page of history, then request one commit's detail.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from metabrowser import paths_safe
from metabrowser.git import repo as git_repo
from metabrowser.git.wire import (
    is_full_revision,
    validate_git_commit_detail,
    validate_git_log_page,
    validate_git_repo_info,
)
from metabrowser.server import app

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git executable is required to build the fixture repository",
)


def _git(root: Path, *args: str) -> None:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Fixture Author",
        "GIT_AUTHOR_EMAIL": "author@example.invalid",
        "GIT_COMMITTER_NAME": "Fixture Committer",
        "GIT_COMMITTER_EMAIL": "committer@example.invalid",
        "GIT_CONFIG_GLOBAL": str(root / ".gitconfig-absent"),
        "GIT_CONFIG_SYSTEM": str(root / ".gitconfig-absent"),
    }
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, env=env)


@pytest.fixture
def served_repo(tmp_path: Path) -> Iterator[Path]:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    (root / "one.txt").write_text("one\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "first commit")
    (root / "two.txt").write_text("two\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "second commit\n\nwith a body")
    _git(root, "tag", "v1.0")

    previous = paths_safe.ROOT_DIR
    paths_safe._set_root_dir(root)
    git_repo.clear_repo_cache()
    try:
        yield root
    finally:
        paths_safe._set_root_dir(previous)
        git_repo.clear_repo_cache()


@pytest.fixture
def served_plain(tmp_path: Path) -> Iterator[Path]:
    root = tmp_path / "plain"
    root.mkdir()
    (root / "note.txt").write_text("no repo")

    previous = paths_safe.ROOT_DIR
    paths_safe._set_root_dir(root)
    git_repo.clear_repo_cache()
    try:
        yield root
    finally:
        paths_safe._set_root_dir(previous)
        git_repo.clear_repo_cache()


def test_full_flow_from_gate_to_commit_detail(served_repo: Path) -> None:
    client = TestClient(app)

    info = client.get("/api/git/repo")
    assert info.status_code == 200
    info_payload = info.json()
    validate_git_repo_info(info_payload)
    assert info_payload["is_repo"] is True
    assert info_payload["head"]["ref"] == "refs/heads/main"

    refs = client.get("/api/git/refs").json()
    assert refs["is_repo"] is True
    assert {(r["kind"], r["name"]) for r in refs["refs"]} >= {("branch", "main"), ("tag", "v1.0")}

    log = client.get("/api/git/log", params={"limit": "10"})
    assert log.status_code == 200
    page = log.json()
    validate_git_log_page(page)
    assert [c["subject"] for c in page["commits"]] == ["second commit", "first commit"]

    revision = page["commits"][0]["id"]
    assert is_full_revision(revision)
    detail = client.get(f"/api/git/commit/{revision}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    validate_git_commit_detail(detail_payload)
    assert detail_payload["body"] == "with a body"
    assert [f["path"] for f in detail_payload["files"]] == ["two.txt"]


def test_paging_through_the_route_stack_is_contiguous(served_repo: Path) -> None:
    client = TestClient(app)

    first = client.get("/api/git/log", params={"limit": "1"}).json()
    validate_git_log_page(first)
    assert first["has_more"] is True
    assert first["cursor"]

    second = client.get("/api/git/log", params={"limit": "1", "cursor": first["cursor"]}).json()
    validate_git_log_page(second)
    # No overlap, no gap — the property browser-side lane continuity
    # depends on.
    assert [c["subject"] for c in first["commits"]] == ["second commit"]
    assert [c["subject"] for c in second["commits"]] == ["first commit"]
    assert second["has_more"] is False
    assert second["cursor"] is None


def test_all_routes_answer_with_the_negative_envelope_outside_a_repo(served_plain: Path) -> None:
    client = TestClient(app)
    for path in ("/api/git/repo", "/api/git/refs", "/api/git/log"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.json()["is_repo"] is False, path


def test_commit_route_path_parameter_is_gated(served_repo: Path) -> None:
    client = TestClient(app)
    # Reaches the handler as a path parameter, so the pattern gate is the
    # only thing standing between it and an argument vector.
    assert client.get("/api/git/commit/HEAD").status_code == 400
    assert client.get("/api/git/commit/" + "0" * 40).status_code == 404


def test_index_page_loads_the_git_modules(served_repo: Path) -> None:
    client = TestClient(app)
    html = client.get("/").text
    # Match the script tags, not bare filenames: "app.js" also appears in
    # an HTML comment above the settings menu.
    scripts = re.findall(r'<script src="([^"]+)"', html)
    names = [src.rsplit("/", 1)[-1].split("?", 1)[0] for src in scripts]
    assert "git_graph.js" in names
    assert "git_panel.js" in names
    # Order matters: app.js calls MetabrowserGitPanel.init() from its
    # DOMContentLoaded handler, so both modules must already be parsed.
    assert names.index("git_graph.js") < names.index("git_panel.js") < names.index("app.js")
