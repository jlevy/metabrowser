"""File, raw, and tree honor GitPath on a pinned GitRevisionSubject."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from httpx2 import ASGITransport, AsyncClient

from metabrowser.git.process import repository_store_target
from metabrowser.git.tree_source import GitPath, GitRevisionSubject, git_revision_subject
from metabrowser.server import app
from metabrowser.settings import TEXT_PREVIEW_REQUEST_MAX_BYTES
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
            "GIT_AUTHOR_NAME": "GitPath Routes",
            "GIT_AUTHOR_EMAIL": "gitpath@example.invalid",
            "GIT_COMMITTER_NAME": "GitPath Routes",
            "GIT_COMMITTER_EMAIL": "gitpath@example.invalid",
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


def _index_info(work: Path, records: bytes) -> None:
    subprocess.run(
        ["git", "-C", str(work), "update-index", "-z", "--index-info"],
        check=True,
        capture_output=True,
        input=records,
        env=_git_env(work),
    )


def _build_store(tmp_path: Path) -> tuple[Path, str]:
    work = tmp_path / "work"
    store = tmp_path / "store.git"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    (work / "README.md").write_text("hello\n", encoding="utf-8")
    (work / "docs").mkdir()
    (work / "docs" / "note.txt").write_text("nested\n", encoding="utf-8")
    (work / "100%.html").write_text("<p>ok</p>\n", encoding="utf-8")
    (work / "link").symlink_to("README.md")
    (work / "big.bin").write_bytes(b"x" * 64)
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "one")
    first = _git(work, "rev-parse", "HEAD").decode().strip()
    _index_info(work, f"160000 commit {first}\tvendor/dep\x00".encode())
    _git(work, "commit", "-qm", "gitlink")
    commit = _git(work, "rev-parse", "HEAD").decode().strip()
    _git(tmp_path, "clone", "--bare", "--template=", str(work), str(store), env_root=tmp_path)
    return store, commit


def _wire(*names: bytes) -> str:
    return GitPath.from_segments(*names).to_wire()


def _assert_listing_entry(entry: dict[str, object]) -> None:
    assert "mtime" not in entry
    assert "mtime_ns" not in entry
    assert "mtime_hash" not in entry
    assert "gitignored" not in entry
    assert "size" not in entry
    assert "total_files" not in entry
    for key in ("path", "display", "mode", "kind", "symlink", "gitlink", "oid"):
        assert key in entry


@asynccontextmanager
async def _pinned_client(
    store: Path,
    commit: str,
    *,
    max_blob_bytes: int | None = None,
) -> AsyncGenerator[tuple[AsyncClient, GitRevisionSubject], None]:
    subject = await git_revision_subject(
        target=repository_store_target(git_dir=store),
        commit_oid=commit,
        max_blob_bytes=(
            TEXT_PREVIEW_REQUEST_MAX_BYTES if max_blob_bytes is None else max_blob_bytes
        ),
    )
    attach_subject(subject)
    try:
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                yield client, subject
    finally:
        await subject.aclose()
        reset_source_session()


def test_git_file_raw_tree_honor_gitpath_without_filesystem_facts(tmp_path: Path) -> None:
    store, commit = _build_store(tmp_path)

    async def _run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            tree = await client.get("/api/tree")
            assert tree.status_code == 200
            body = tree.json()
            assert body["subject"] == "git_revision"
            assert body["path"] == ""
            assert body["kind"] == "tree"
            assert "root" not in body
            assert str(store) not in tree.text
            names = {entry["display"] for entry in body["entries"]}
            assert names >= {"README.md", "docs", "100%.html", "link", "big.bin", "vendor"}
            for entry in body["entries"]:
                _assert_listing_entry(entry)
            readme_entry = next(
                entry for entry in body["entries"] if entry["display"] == "README.md"
            )
            assert readme_entry["kind"] == "blob"
            assert readme_entry["symlink"] is False
            link_entry = next(entry for entry in body["entries"] if entry["display"] == "link")
            assert link_entry["symlink"] is True
            assert link_entry["kind"] == "blob"

            readme_wire = _wire(b"README.md")
            assert readme_entry["path"] == readme_wire
            file_resp = await client.get("/api/file", params={"path": readme_wire})
            assert file_resp.status_code == 200
            file_body = file_resp.json()
            assert file_body["subject"] == "git_revision"
            assert file_body["type"] == "text"
            assert file_body["kind"] == "markdown"
            assert file_body["git_kind"] == "blob"
            assert file_body["content"] == "hello\n"
            assert file_body["size"] == 6
            assert "mtime" not in file_body
            assert "mtime_hash" not in file_body
            assert str(store) not in file_resp.text

            raw = await client.get("/raw", params={"path": readme_wire})
            assert raw.status_code == 200
            assert raw.content == b"hello\n"

            relative = await client.get("/api/file", params={"path": "README.md"})
            assert relative.status_code == 404
            assert b"hello" not in relative.content
            relative_raw = await client.get("/raw", params={"path": "README.md"})
            assert relative_raw.status_code == 404
            assert relative_raw.content != b"hello\n"

            docs_wire = _wire(b"docs")
            docs_tree = await client.get("/api/tree", params={"path": docs_wire})
            assert docs_tree.status_code == 200
            docs_body = docs_tree.json()
            note = next(
                entry for entry in docs_body["entries"] if entry["display"].endswith("note.txt")
            )
            _assert_listing_entry(note)
            note_file = await client.get("/api/file", params={"path": note["path"]})
            assert note_file.status_code == 200
            assert note_file.json()["content"] == "nested\n"

            folder = await client.get("/api/file", params={"path": docs_wire})
            assert folder.status_code == 200
            folder_body = folder.json()
            assert folder_body["type"] == "tree"
            assert folder_body["git_kind"] == "tree"
            assert "dir" not in folder_body
            assert "total_files" not in folder_body

            link_wire = _wire(b"link")
            link_file = await client.get("/api/file", params={"path": link_wire})
            assert link_file.status_code == 200
            link_body = link_file.json()
            assert link_body["symlink"] is True
            assert link_body["content"] == "README.md"
            link_raw = await client.get("/raw", params={"path": link_wire})
            assert link_raw.content == b"README.md"

            gitlink_wire = _wire(b"vendor", b"dep")
            gitlink_file = await client.get("/api/file", params={"path": gitlink_wire})
            assert gitlink_file.status_code == 200
            gitlink_body = gitlink_file.json()
            assert gitlink_body["gitlink"] is True
            assert gitlink_body["type"] == "gitlink"
            assert gitlink_body["git_kind"] == "commit"
            assert "content" not in gitlink_body
            gitlink_tree = await client.get("/api/tree", params={"path": gitlink_wire})
            assert gitlink_tree.status_code == 404
            gitlink_raw = await client.get("/raw", params={"path": gitlink_wire})
            assert gitlink_raw.status_code == 404

    asyncio.run(_run())


def test_git_tree_filters_and_blob_size_gate(tmp_path: Path) -> None:
    store, commit = _build_store(tmp_path)

    async def _run() -> None:
        async with _pinned_client(store, commit, max_blob_bytes=32) as (client, _subject):
            recency = await client.get("/api/tree", params={"recency": "24h"})
            assert recency.status_code == 409
            recency_body = recency.json()
            assert recency_body["code"] == "unsupported_for_subject"
            assert recency_body["capability"] == "recency"

            ignored = await client.get("/api/tree", params={"include_ignored": "0"})
            assert ignored.status_code == 409
            ignored_body = ignored.json()
            assert ignored_body["code"] == "unsupported_for_subject"
            assert ignored_body["capability"] == "ignore"

            min_size = await client.get("/api/tree", params={"min_size": "1"})
            assert min_size.status_code == 409
            min_size_body = min_size.json()
            assert min_size_body["code"] == "unsupported_for_subject"
            assert min_size_body["capability"] == "min_size"
            assert min_size_body.get("entries") is None

            typed = await client.get("/api/tree", params={"types": ".md"})
            assert typed.status_code == 200
            displays = [entry["display"] for entry in typed.json()["entries"]]
            assert displays == ["README.md"]
            for entry in typed.json()["entries"]:
                _assert_listing_entry(entry)

            too_big = await client.get("/api/file", params={"path": _wire(b"big.bin")})
            assert too_big.status_code == 413
            too_big_body = too_big.json()
            assert too_big_body["code"] == "blob_too_large"
            assert too_big_body["max_bytes"] == 32
            assert too_big_body["size"] == 64

            raw_too_big = await client.get("/raw", params={"path": _wire(b"big.bin")})
            assert raw_too_big.status_code == 413
            assert raw_too_big.json()["code"] == "blob_too_large"

            still_ok = await client.get("/api/file", params={"path": _wire(b"README.md")})
            assert still_ok.status_code == 200
            assert still_ok.json()["content"] == "hello\n"

    asyncio.run(_run())
