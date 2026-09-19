"""Git collection routes honor a pinned GitRevisionSubject without a checkout."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from metabrowser.git import repo as git_repo
from metabrowser.git.history import HISTORY_SESSIONS
from metabrowser.git.process import GitLocation, repository_store_target
from metabrowser.git.repo import repo_info
from metabrowser.git.tree_source import GitRevisionSubject, git_revision_subject
from metabrowser.git.wire import (
    is_full_revision,
    validate_git_commit_detail,
    validate_git_log_page,
    validate_git_repo_info,
)
from metabrowser.server import app
from metabrowser.source import attach_subject, reset_source_session

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git executable is required",
)


def _git_env(root: Path) -> dict[str, str]:
    env = dict(os.environ)
    for name in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_COMMON_DIR",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    ):
        env.pop(name, None)
    env.update(
        {
            "GIT_AUTHOR_NAME": "Revision Routes",
            "GIT_AUTHOR_EMAIL": "routes@example.invalid",
            "GIT_COMMITTER_NAME": "Revision Routes",
            "GIT_COMMITTER_EMAIL": "routes@example.invalid",
            "GIT_AUTHOR_DATE": "2026-01-01T00:00:00 +0000",
            "GIT_COMMITTER_DATE": "2026-01-01T00:00:00 +0000",
            "GIT_CONFIG_GLOBAL": str(root / ".gitconfig-absent"),
            "GIT_CONFIG_SYSTEM": str(root / ".gitconfig-absent"),
        }
    )
    return env


def _git(cwd: Path, *args: str, env_root: Path | None = None) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        env=_git_env(env_root or cwd),
    )
    return result.stdout


def _two_commit_store(tmp_path: Path) -> tuple[Path, str, str]:
    work = tmp_path / "work"
    store = tmp_path / "store.git"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    (work / "README.md").write_text("hello\n", encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "first")
    first = _git(work, "rev-parse", "HEAD").decode().strip()
    (work / "later.txt").write_text("second\n", encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "second")
    second = _git(work, "rev-parse", "HEAD").decode().strip()
    _git(tmp_path, "clone", "--bare", "--template=", str(work), str(store), env_root=tmp_path)
    return store, first, second


@pytest.fixture
def pinned_first(tmp_path: Path) -> Iterator[tuple[Path, str, str]]:
    store, first, second = _two_commit_store(tmp_path)

    async def _pin() -> GitRevisionSubject:
        subject = await git_revision_subject(
            target=repository_store_target(git_dir=store),
            commit_oid=first,
        )
        # Collection routes use GitLocation, not the cat-file pool. Close the
        # actor on this loop so teardown does not cross loop boundaries.
        await subject.aclose()
        return subject

    subject = asyncio.run(_pin())
    attach_subject(subject)
    git_repo.clear_repo_cache()
    try:
        yield store, first, second
    finally:
        asyncio.run(HISTORY_SESSIONS.close_all())
        asyncio.run(subject.aclose())
        reset_source_session()
        git_repo.clear_repo_cache()


def test_git_routes_honor_the_pinned_oid_not_store_head(
    pinned_first: tuple[Path, str, str],
) -> None:
    store, first, second = pinned_first
    with TestClient(app) as client:
        repo = client.get("/api/git/repo")
        assert repo.status_code == 200
        info = repo.json()
        validate_git_repo_info(info)
        assert info["is_repo"] is True
        assert info["root"] == ""
        assert str(store) not in repo.text
        head = info["head"]
        assert head["detached"] is True
        assert head["unborn"] is False
        assert head["ref"] is None
        assert head["revision"] == first
        assert is_full_revision(first)

        refs = client.get("/api/git/refs")
        assert refs.status_code == 200
        payload = refs.json()
        assert payload["is_repo"] is True
        names = {ref["name"] for ref in payload["refs"]}
        assert "main" in names
        assert all("is_head" not in ref for ref in payload["refs"])
        assert str(store) not in refs.text

        summary = client.get("/api/git/summary")
        assert summary.status_code == 200
        summary_body = summary.json()
        assert summary_body["is_repo"] is True
        assert summary_body["commit_count"] == 1
        assert isinstance(summary_body["first_commit_at"], float)

        all_summary = client.get("/api/git/summary", params={"scope": "all"})
        assert all_summary.status_code == 200
        assert all_summary.json()["commit_count"] == 2

        log = client.get("/api/git/log", params={"limit": "10"})
        assert log.status_code == 200
        page = log.json()
        validate_git_log_page(page)
        assert [commit["subject"] for commit in page["commits"]] == ["first"]
        assert page["commits"][0]["id"] == first

        all_log = client.get("/api/git/log", params={"limit": "10", "scope": "all"})
        assert all_log.status_code == 200
        all_page = all_log.json()
        validate_git_log_page(all_page)
        subjects = [commit["subject"] for commit in all_page["commits"]]
        assert "second" in subjects
        assert "first" in subjects
        assert second in {commit["id"] for commit in all_page["commits"]}

        detail = client.get(f"/api/git/commit/{first}")
        assert detail.status_code == 200
        body = detail.json()
        validate_git_commit_detail(body)
        assert body["commit"]["subject"] == "first"
        paths = [change["path"] for change in body["files"]]
        assert "README.md" in paths
        assert all("outside_root" not in change for change in body["files"])
        assert str(store) not in detail.text

        later = client.get("/api/file", params={"path": "README.md"})
        assert later.status_code in {404, 409}
        assert b"hello" not in later.content
        raw = client.get("/raw", params={"path": "README.md"})
        assert raw.status_code in {404, 409}
        assert raw.content != b"hello\n"


def test_repo_info_location_overload_does_not_use_ambient_head(tmp_path: Path) -> None:
    store, first, second = _two_commit_store(tmp_path)
    location = GitLocation.revision(repository_store_target(git_dir=store), first)
    context, info = asyncio.run(repo_info(location))
    assert context is not None
    assert context.git_root is None
    assert context.served_root is None
    validate_git_repo_info(dict(info))
    assert info["root"] == ""
    assert info["head"] is not None
    assert info["head"]["revision"] == first
    assert info["head"]["detached"] is True
    assert info["head"]["revision"] != second
