"""Diff comparison honors a pinned GitRevisionSubject without a checkout."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from metabrowser.diff.format import validate_document
from metabrowser.git import repo as git_repo
from metabrowser.git.process import repository_store_target
from metabrowser.git.tree_source import GitRevisionSubject, git_revision_subject
from metabrowser.server import app
from metabrowser.source import attach_subject, reset_source_session
from tests.diff_fixture_repo import build_diff_fixture

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
            "GIT_AUTHOR_NAME": "Revision Diff",
            "GIT_AUTHOR_EMAIL": "diff@example.invalid",
            "GIT_COMMITTER_NAME": "Revision Diff",
            "GIT_COMMITTER_EMAIL": "diff@example.invalid",
            "GIT_AUTHOR_DATE": "2026-01-01T00:00:00 +0000",
            "GIT_COMMITTER_DATE": "2026-01-01T00:00:00 +0000",
            "GIT_CONFIG_GLOBAL": str(root / ".gitconfig-absent"),
            "GIT_CONFIG_SYSTEM": str(root / ".gitconfig-absent"),
        }
    )
    return env


def _clone_bare(work: Path, store: Path) -> None:
    subprocess.run(
        ["git", "clone", "--bare", "--template=", str(work), str(store)],
        check=True,
        capture_output=True,
        env=_git_env(work.parent),
        cwd=work.parent,
    )


@pytest.fixture
def pinned_base(tmp_path: Path) -> Iterator[tuple[Path, Path, str, str]]:
    work = tmp_path / "work"
    store = tmp_path / "store.git"
    work.mkdir()
    base, target = build_diff_fixture(work)
    _clone_bare(work, store)

    async def _pin() -> GitRevisionSubject:
        subject = await git_revision_subject(
            target=repository_store_target(git_dir=store),
            commit_oid=base,
            store_identity="fixture",
        )
        await subject.aclose()
        return subject

    subject = asyncio.run(_pin())
    attach_subject(subject)
    git_repo.clear_repo_cache()
    try:
        yield work, store, base, target
    finally:
        asyncio.run(subject.aclose())
        reset_source_session()
        git_repo.clear_repo_cache()


def _paths(body: dict[str, object]) -> set[str]:
    manifest = body["manifest"]
    assert isinstance(manifest, dict)
    files = manifest["files"]
    assert isinstance(files, list)
    names: set[str] = set()
    for change in files:
        assert isinstance(change, dict)
        new = change.get("new")
        old = change.get("old")
        if isinstance(new, dict):
            path = new.get("path")
            if isinstance(path, str):
                names.add(path)
        elif isinstance(old, dict):
            path = old.get("path")
            if isinstance(path, str):
                names.add(path)
    return names


def test_comparison_head_is_the_pin_not_store_head(
    pinned_base: tuple[Path, Path, str, str],
) -> None:
    _work, store, base, target = pinned_base
    with TestClient(app) as client:
        head = client.get("/api/plugin/diff/comparison", params={"revision": "HEAD"})
        assert head.status_code == 200
        body = head.json()
        document = validate_document(body)
        assert document.resolved.right.id == base
        assert document.resolved.right.id != target
        assert "new.md" not in _paths(body)
        assert str(store) not in head.text
        assert str(_work) not in head.text

        later = client.get("/api/plugin/diff/comparison", params={"revision": target})
        assert later.status_code == 200
        later_body = later.json()
        validate_document(later_body)
        assert later_body["resolved"]["right"]["id"] == target
        assert "new.md" in _paths(later_body)
        assert str(store) not in later.text
