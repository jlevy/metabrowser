"""File, raw, tree, KPress, patch containers, binary chunks, structured parsed, agent-log, blob kinds, SPA nav tree, folder chrome, Markdown GitPath links, Git folder Overview, listing blob sizes, Git-native rollup, catalog, index status, tree filter tallies, tree summary, filtered tree totals, logical-extension type matching, ignore-noop, tree depth, tree-ext, file-envelope ext, markdown frontmatter, text preview windows, in-tree symlink follow, plugin-sidekick symlink follow, image preview, and odd-name GitPaths honor a pin."""

from __future__ import annotations

import asyncio
import base64
import os
import shutil
import socket
import subprocess
import time
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Any

import pytest
from httpx2 import ASGITransport, AsyncClient

from metabrowser import kpress_adapter
from metabrowser.diff.format import validate_document
from metabrowser.git.content_routes import split_git_container_wire
from metabrowser.git.process import repository_store_target
from metabrowser.git.tree_source import (
    GitPath,
    GitPathError,
    GitRevisionSubject,
    git_revision_subject,
)
from metabrowser.server import app
from metabrowser.settings import (
    INVENTORY_MAX_FILES,
    SYNTAX_HIGHLIGHT_MAX_BYTES,
    TEXT_PREVIEW_CHUNK_BYTES,
    TEXT_PREVIEW_REQUEST_MAX_BYTES,
)
from metabrowser.source import attach_subject, reset_source_session
from metabrowser.wire_models import validate_rollup_node

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git executable is required",
)

_LFS_POINTER = (
    b"version https://git-lfs.github.com/spec/v1\n"
    b"oid sha256:4d7a214614ab2935c943f9e0ff69d22eadbb8f32b1258daaa5e2ca24d17e2393\n"
    b"size 12345\n"
)
# 1x1 transparent PNG. Classification is by extension; bytes pin /raw.
_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\xda\x63\x00"
    b"\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)
_PROMISOR_MISS_BUDGET_S = 1.0


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


def _hash_blob(work: Path, data: bytes) -> str:
    result = subprocess.run(
        ["git", "-C", str(work), "hash-object", "-w", "--stdin"],
        check=True,
        capture_output=True,
        input=data,
        env=_git_env(work),
    )
    return result.stdout.decode().strip()


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
    (work / "config.json").write_text('{"name": "pin", "count": 2}\n', encoding="utf-8")
    (work / "session.jsonl").write_text(
        '{"type":"system","subtype":"init","model":"claude-opus-4-20250514"}\n'
        '{"type":"assistant","message":{"role":"assistant",'
        '"content":[{"type":"text","text":"hello"}]}}\n',
        encoding="utf-8",
    )
    (work / "docs").mkdir()
    (work / "docs" / "note.txt").write_text("nested\n", encoding="utf-8")
    (work / "change.patch").write_text(
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n"
        "+++ b/src/app.py\n"
        "@@ -1,1 +1,1 @@\n"
        "-old\n"
        "+new\n"
        "diff --git a/gone.txt b/gone.txt\n"
        "deleted file mode 100644\n"
        "--- a/gone.txt\n"
        "+++ /dev/null\n"
        "@@ -1,1 +0,0 @@\n"
        "-bye\n",
        encoding="utf-8",
    )
    (work / "100%.html").write_text("<p>ok</p>\n", encoding="utf-8")
    (work / "link").symlink_to("README.md")
    (work / "big.bin").write_bytes(b"x" * 64)
    (work / "nul.bin").write_bytes(b"\x00\x01\x02BINARY")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "one")
    first = _git(work, "rev-parse", "HEAD").decode().strip()
    _index_info(work, f"160000 commit {first}\tvendor/dep\x00".encode())
    _git(work, "commit", "-qm", "gitlink")
    commit = _git(work, "rev-parse", "HEAD").decode().strip()
    _git(tmp_path, "clone", "--bare", "--template=", str(work), str(store), env_root=tmp_path)
    return store, commit


def _delete_store_blob(store: Path, oid: str) -> None:
    loose = store / "objects" / oid[:2] / oid[2:]
    if not loose.is_file():
        pack_dir = store / "objects" / "pack"
        for pack in pack_dir.glob("*.pack"):
            subprocess.run(
                ["git", "-C", str(store), "unpack-objects", "-q"],
                check=True,
                capture_output=True,
                input=pack.read_bytes(),
                env=_git_env(store),
            )
            pack.unlink()
            pack.with_suffix(".idx").unlink(missing_ok=True)
            pack.with_suffix(".promisor").unlink(missing_ok=True)
    if not loose.is_file():
        raise AssertionError(f"store blob {oid} was not a loose object")
    loose.unlink()


@contextmanager
def _unanswered_promisor() -> Generator[str, None, None]:
    with socket.create_server(("127.0.0.1", 0)) as sock:
        port = int(sock.getsockname()[1])
        yield f"http://127.0.0.1:{port}/repo.git"


def _wire(*names: bytes) -> str:
    return GitPath.from_segments(*names).to_wire()


def _assert_listing_entry(entry: dict[str, object]) -> None:
    assert "mtime" not in entry
    assert "mtime_ns" not in entry
    assert "mtime_hash" not in entry
    assert "gitignored" not in entry
    assert "total_files" not in entry
    for key in ("path", "display", "mode", "kind", "symlink", "gitlink", "oid"):
        assert key in entry
    if entry["kind"] == "blob":
        assert isinstance(entry["size"], int)
        assert entry["size"] >= 0
    else:
        assert "size" not in entry


def _assert_nav_tree_node(node: dict[str, object]) -> None:
    assert "mtime" not in node
    assert "mtime_ns" not in node
    assert "gitignored" not in node
    assert node["name"]
    assert node["path"]
    assert node["type"] in {"dir", "file", "symlink"}
    if node["type"] == "dir":
        assert "size" not in node
        children = node["children"]
        assert children is None or isinstance(children, list)
        if children is None:
            assert node["has_children"] is True
        else:
            assert node["has_children"] is bool(children)
            for child in children:
                assert isinstance(child, dict)
                _assert_nav_tree_node(child)
        if "total_files" in node:
            assert isinstance(node["total_files"], int)
            assert node["total_files"] >= 0
        if "total_size" in node:
            assert isinstance(node["total_size"], int)
            assert node["total_size"] >= 0
    else:
        assert "children" not in node
        assert "has_children" not in node
        assert "total_files" not in node
        assert "total_size" not in node
        if "size" in node:
            assert isinstance(node["size"], int)
            assert node["size"] >= 0


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
            assert names >= {
                "README.md",
                "config.json",
                "session.jsonl",
                "docs",
                "100%.html",
                "link",
                "big.bin",
                "vendor",
                "change.patch",
            }
            for entry in body["entries"]:
                _assert_listing_entry(entry)
            readme_entry = next(
                entry for entry in body["entries"] if entry["display"] == "README.md"
            )
            assert readme_entry["kind"] == "blob"
            assert readme_entry["symlink"] is False
            assert readme_entry["size"] == 6
            link_entry = next(entry for entry in body["entries"] if entry["display"] == "link")
            assert link_entry["symlink"] is True
            assert link_entry["kind"] == "blob"
            assert link_entry["size"] == 9
            docs_entry = next(entry for entry in body["entries"] if entry["display"] == "docs")
            assert docs_entry["kind"] == "tree"
            assert "size" not in docs_entry

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
            assert file_body["ext"] == ".md"
            assert "logical_ext" not in file_body
            assert "compressed" not in file_body
            assert "size_uncompressed" not in file_body
            assert "frontmatter" not in file_body
            assert "frontmatter_error" not in file_body
            assert file_body["bytes_read"] == 6
            assert file_body["content_preview_limit"] == SYNTAX_HIGHLIGHT_MAX_BYTES
            assert file_body["content_max_preview_limit"] == TEXT_PREVIEW_REQUEST_MAX_BYTES
            assert file_body["highlight_disabled"] is False
            assert file_body["content_truncated"] is False
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
            note_body = note_file.json()
            assert note_body["content"] == "nested\n"
            assert note_body["ext"] == ".txt"
            assert "logical_ext" not in note_body

            folder = await client.get("/api/file", params={"path": docs_wire})
            assert folder.status_code == 200
            folder_body = folder.json()
            assert folder_body["type"] == "folder"
            assert folder_body["kind"] == "folder"
            assert folder_body["git_kind"] == "tree"
            assert folder_body["name"] == "docs"
            assert folder_body["path"] == docs_wire
            assert [view["id"] for view in folder_body["views"]] == ["overview", "treemap"]
            assert "dir" not in folder_body or "mtime" not in folder_body["dir"]
            assert folder_body["dir"]["total_files"] == 1
            assert folder_body["dir"]["total_size"] == 7
            assert "total_files" not in folder_body
            assert "mtime" not in folder_body
            assert "ext" not in folder_body

            link_wire = _wire(b"link")
            link_file = await client.get("/api/file", params={"path": link_wire})
            assert link_file.status_code == 200
            link_body = link_file.json()
            assert link_body["path"] == link_wire
            assert link_body["display"] == "link"
            assert link_body["type"] == "text"
            assert link_body["kind"] == "markdown"
            assert link_body["ext"] == ".md"
            assert link_body["content"] == "hello\n"
            assert link_body["symlink"] is False
            link_raw = await client.get("/raw", params={"path": link_wire})
            assert link_raw.content == b"hello\n"

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


def test_git_tree_projects_spa_nav_nodes(tmp_path: Path) -> None:
    store, commit = _build_store(tmp_path)

    async def _run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            tree = await client.get("/api/tree")
            assert tree.status_code == 200
            body = tree.json()
            assert isinstance(body["tree"], list)
            assert str(store) not in tree.text
            by_name = {node["name"]: node for node in body["tree"]}
            for node in body["tree"]:
                _assert_nav_tree_node(node)
            assert by_name["docs"]["type"] == "dir"
            assert by_name["docs"]["path"] == _wire(b"docs")
            docs_children = {child["name"]: child for child in by_name["docs"]["children"]}
            assert docs_children["note.txt"]["type"] == "file"
            assert docs_children["note.txt"]["path"] == _wire(b"docs", b"note.txt")
            assert by_name["docs"]["has_children"] is True
            assert by_name["docs"]["total_files"] == 1
            assert by_name["docs"]["total_size"] == 7
            assert "mtime" not in by_name["docs"]
            assert by_name["README.md"]["type"] == "file"
            assert by_name["README.md"]["path"] == _wire(b"README.md")
            assert by_name["README.md"]["ext"] == ".md"
            assert "logical_ext" not in by_name["README.md"]
            assert by_name["README.md"]["size"] == 6
            assert by_name["link"]["type"] == "symlink"
            assert by_name["link"]["size"] == 9
            assert "size" not in by_name["docs"]
            assert by_name["vendor"]["type"] == "dir"
            assert by_name["vendor"]["total_files"] == 0
            assert by_name["vendor"]["total_size"] == 0
            vendor_children = {child["name"]: child for child in by_name["vendor"]["children"]}
            assert vendor_children["dep"]["type"] == "file"
            assert vendor_children["dep"]["path"] == _wire(b"vendor", b"dep")
            names = {entry["display"] for entry in body["entries"]}
            assert names >= {"README.md", "docs", "link", "vendor"}

            shallow = await client.get("/api/tree", params={"depth": "1"})
            assert shallow.status_code == 200
            shallow_docs = next(node for node in shallow.json()["tree"] if node["name"] == "docs")
            assert shallow_docs["children"] is None
            assert shallow_docs["has_children"] is True

            summary = await client.get("/api/tree", params={"depth": "0"})
            assert summary.status_code == 200
            summary_body = summary.json()
            assert summary_body["tree"] == []
            assert summary_body["entries"] == []
            assert summary_body["summary"]["files"] == 9

            vendor = await client.get("/api/tree", params={"path": _wire(b"vendor")})
            assert vendor.status_code == 200
            vendor_body = vendor.json()
            dep = next(node for node in vendor_body["tree"] if node["name"] == "dep")
            _assert_nav_tree_node(dep)
            assert dep["type"] == "file"
            assert dep["path"] == _wire(b"vendor", b"dep")
            assert "size" not in dep
            assert str(store) not in vendor.text

    asyncio.run(_run())


def test_git_file_folder_envelope_is_spa_folder_chrome(tmp_path: Path) -> None:
    store, commit = _build_store(tmp_path)

    async def _run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            root = await client.get("/api/file")
            assert root.status_code == 200
            root_body = root.json()
            assert root_body["kind"] == "folder"
            assert root_body["type"] == "folder"
            assert root_body["git_kind"] == "tree"
            assert root_body["path"] == ""
            assert root_body["name"] == ""
            view_ids = [view["id"] for view in root_body["views"]]
            assert view_ids == ["overview", "treemap"]
            assert root_body["readme_path"] == _wire(b"README.md")
            assert root_body["readme_search_truncated"] is False
            assert root_body["dir"]["total_files"] == 9
            assert "mtime" not in root_body["dir"]
            assert "unignored_files" not in root_body["dir"]
            assert "total_files" not in root_body
            assert "ext" not in root_body
            tree = await client.get("/api/tree")
            blob_size = 0
            blob_count = 0
            for node in tree.json()["tree"]:
                if node["type"] == "dir":
                    blob_count += int(node["total_files"])
                    blob_size += int(node["total_size"])
                elif "size" in node:
                    blob_count += 1
                    blob_size += int(node["size"])
            assert root_body["dir"]["total_size"] == blob_size
            assert root_body["dir"]["total_files"] == blob_count
            assert str(store) not in root.text

            vendor = await client.get("/api/file", params={"path": _wire(b"vendor")})
            assert vendor.status_code == 200
            vendor_body = vendor.json()
            assert vendor_body["kind"] == "folder"
            assert vendor_body["git_kind"] == "tree"
            assert vendor_body["name"] == "vendor"
            assert [view["id"] for view in vendor_body["views"]] == ["overview", "treemap"]
            assert vendor_body["readme_path"] == ""
            assert vendor_body["dir"] == {"total_files": 0, "total_size": 0}
            assert "ext" not in vendor_body
            gitlink = await client.get("/api/file", params={"path": _wire(b"vendor", b"dep")})
            assert gitlink.json()["kind"] != "folder"

    asyncio.run(_run())


def test_git_rollup_uses_blob_index_without_mtime(tmp_path: Path) -> None:
    store, commit = _build_store(tmp_path)
    docs_wire = _wire(b"docs")
    note_wire = _wire(b"docs", b"note.txt")
    vendor_wire = _wire(b"vendor")

    async def _run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            spelling = await client.get("/api/rollup", params={"path": "docs"})
            assert spelling.status_code == 404

            blob = await client.get("/api/rollup", params={"path": _wire(b"README.md")})
            assert blob.status_code == 404

            root = await client.get("/api/rollup", params={"depth": "1"})
            assert root.status_code == 200
            body = root.json()
            assert body["subject"] == "git_revision"
            assert body["root"] == ""
            assert body["path"] == ""
            assert body["index_status"] == "complete"
            assert body["truncated"] is False
            node = body["node"]
            validate_rollup_node(node)
            assert node["type"] == "dir"
            assert node["state"] == "complete"
            assert node["total_files"] == 9
            assert node["unignored_files"] == 9
            assert node["unignored_size"] == node["total_size"]
            assert "mtime" not in node
            names = {child["name"] for child in node["children"]}
            assert "docs" in names
            assert "vendor" in names
            assert "README.md" in names
            docs = next(child for child in node["children"] if child["name"] == "docs")
            assert docs["path"] == docs_wire
            assert docs["total_files"] == 1
            assert docs["total_size"] == 7
            assert "mtime" not in docs
            vendor = next(child for child in node["children"] if child["name"] == "vendor")
            assert vendor["path"] == vendor_wire
            assert vendor["total_files"] == 0
            assert vendor["total_size"] == 0
            readme = next(child for child in node["children"] if child["name"] == "README.md")
            assert "mtime" not in readme
            assert readme["size"] == 6
            assert str(store) not in root.text

            nested = await client.get("/api/rollup", params={"path": docs_wire, "depth": "1"})
            assert nested.status_code == 200
            nested_node = nested.json()["node"]
            validate_rollup_node(nested_node)
            assert nested_node["path"] == docs_wire
            assert nested_node["total_files"] == 1
            assert nested_node["total_size"] == 7
            assert nested_node["children"][0]["path"] == note_wire
            assert "mtime" not in nested_node
            assert str(store) not in nested.text

            empty = await client.get("/api/rollup", params={"path": vendor_wire})
            assert empty.status_code == 200
            empty_node = empty.json()["node"]
            assert empty_node["total_files"] == 0
            assert empty_node["total_size"] == 0
            assert empty_node["children"] == []

    asyncio.run(_run())


def test_git_catalog_lists_blob_wires_with_display_names(tmp_path: Path) -> None:
    store, commit = _build_store(tmp_path)
    readme_wire = _wire(b"README.md")
    note_wire = _wire(b"docs", b"note.txt")
    percent_wire = _wire(b"100%.html")
    gitlink_wire = _wire(b"vendor", b"dep")

    async def _run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            response = await client.get("/api/catalog")
            assert response.status_code == 200
            body = response.json()
            assert body["complete"] is True
            assert body["truncated"] is False
            assert body["revision"] == 1
            files = {file["p"]: file for file in body["files"]}
            assert readme_wire in files
            assert files[readme_wire]["e"] == ".md"
            assert files[readme_wire]["n"] == "README.md"
            assert note_wire in files
            assert files[note_wire]["e"] == ".txt"
            assert files[note_wire]["n"] == "note.txt"
            assert percent_wire in files
            assert files[percent_wire]["n"] == "100%.html"
            assert gitlink_wire not in files
            assert "vendor/dep" not in files
            assert "README.md" not in files
            assert len(files) == 9
            assert str(store) not in response.text

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
            assert ignored.status_code == 200
            ignored_names = {entry["display"] for entry in ignored.json()["entries"]}
            assert "README.md" in ignored_names
            assert "docs" in ignored_names
            assert ignored.json()["summary"]["ignored_files"] == 0

            min_size = await client.get("/api/tree", params={"min_size": "32"})
            assert min_size.status_code == 200
            min_body = min_size.json()
            min_displays = {entry["display"] for entry in min_body["entries"]}
            assert "README.md" not in min_displays
            assert "link" not in min_displays
            assert "docs" not in min_displays
            assert "vendor" not in min_displays
            assert "big.bin" in min_displays
            big = next(entry for entry in min_body["entries"] if entry["display"] == "big.bin")
            assert big["size"] == 64
            min_names = {node["name"] for node in min_body["tree"]}
            assert min_names == min_displays
            assert (
                next(node for node in min_body["tree"] if node["name"] == "big.bin")["size"] == 64
            )
            assert min_body["filtered"]["files"] >= 1
            assert min_body["filtered"]["size"] >= 64
            assert min_body["filtered"]["entries"] == min_body["filtered"]["files"]
            assert all(
                node.get("total_files", 1) > 0 for node in min_body["tree"] if node["type"] == "dir"
            )

            vendor_floor = await client.get(
                "/api/tree", params={"path": _wire(b"vendor"), "min_size": "1"}
            )
            assert vendor_floor.status_code == 200
            assert vendor_floor.json()["entries"] == []
            assert vendor_floor.json()["tree"] == []

            typed = await client.get("/api/tree", params={"types": ".md"})
            assert typed.status_code == 200
            typed_body = typed.json()
            displays = [entry["display"] for entry in typed_body["entries"]]
            assert displays == ["README.md"]
            for entry in typed_body["entries"]:
                _assert_listing_entry(entry)
            typed_tree = typed_body["tree"]
            assert [node["name"] for node in typed_tree] == ["README.md"]
            assert typed_tree[0]["type"] == "file"
            _assert_nav_tree_node(typed_tree[0])
            assert typed_body["filtered"] == {"files": 1, "size": 6, "entries": 1}

            typed_txt = await client.get("/api/tree", params={"types": ".txt"})
            assert typed_txt.status_code == 200
            txt_body = typed_txt.json()
            txt_displays = [entry["display"] for entry in txt_body["entries"]]
            assert txt_displays == ["docs"]
            docs_node = txt_body["tree"][0]
            assert docs_node["name"] == "docs"
            assert docs_node["type"] == "dir"
            assert docs_node["total_files"] == 1
            assert docs_node["total_size"] == 7
            assert [child["name"] for child in docs_node["children"]] == ["note.txt"]
            assert txt_body["filtered"] == {"files": 1, "size": 7, "entries": 1}
            nested = await client.get("/api/tree", params={"path": _wire(b"docs"), "types": ".txt"})
            assert nested.status_code == 200
            nested_body = nested.json()
            assert [entry["display"] for entry in nested_body["entries"]] == ["docs/note.txt"]
            assert nested_body["filtered"] == {"files": 1, "size": 7, "entries": 1}

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


def test_git_tree_matches_logical_extensions_not_name_suffix(tmp_path: Path) -> None:
    work = tmp_path / "work"
    store = tmp_path / "store.git"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    (work / "README.md").write_text("hello\n", encoding="utf-8")
    (work / "notmd").write_text("nope\n", encoding="utf-8")
    (work / "bundle.min.js").write_text("x\n", encoding="utf-8")
    (work / "events.jsonl.gz").write_bytes(b"x\n")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "compound")
    commit = _git(work, "rev-parse", "HEAD").decode().strip()
    _git(tmp_path, "clone", "--bare", "--template=", str(work), str(store), env_root=tmp_path)

    async def _run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            tree = await client.get("/api/tree")
            assert tree.status_code == 200
            body = tree.json()
            by_name = {node["name"]: node for node in body["tree"]}
            assert by_name["bundle.min.js"]["ext"] == ".min.js"
            assert "logical_ext" not in by_name["bundle.min.js"]
            assert "ext" not in by_name["notmd"]
            assert "logical_ext" not in by_name["notmd"]
            gz = by_name["events.jsonl.gz"]
            assert gz["ext"] == ".jsonl.gz"
            assert gz["logical_ext"] == ".jsonl"
            assert gz["compressed"] is True
            assert gz["compression"] == "gzip"
            rows = {row[0]: (row[1], row[2]) for row in body["extensions"]}
            assert rows[".min.js"] == (1, 0)
            assert ".js" not in rows
            catalog = await client.get("/api/catalog")
            files = {file["n"]: file["e"] for file in catalog.json()["files"]}
            assert files["bundle.min.js"] == ".min.js"
            assert files["notmd"] == ""
            assert files["events.jsonl.gz"] == ".jsonl.gz"

            min_js = await client.get(
                "/api/file", params={"path": by_name["bundle.min.js"]["path"]}
            )
            assert min_js.status_code == 200
            min_js_body = min_js.json()
            assert min_js_body["ext"] == ".min.js"
            assert "logical_ext" not in min_js_body
            notmd = await client.get("/api/file", params={"path": by_name["notmd"]["path"]})
            assert notmd.status_code == 200
            assert "ext" not in notmd.json()
            gz_file = await client.get("/api/file", params={"path": gz["path"]})
            assert gz_file.status_code == 200
            gz_body = gz_file.json()
            assert gz_body["ext"] == ".jsonl.gz"
            assert "logical_ext" not in gz_body
            assert "compressed" not in gz_body

            typed_md = await client.get("/api/tree", params={"types": ".md"})
            assert typed_md.status_code == 200
            md_names = [entry["display"] for entry in typed_md.json()["entries"]]
            assert md_names == ["README.md"]
            assert typed_md.json()["filtered"]["files"] == 1

            typed_compound = await client.get("/api/tree", params={"types": ".min.js"})
            assert typed_compound.status_code == 200
            compound_names = [entry["display"] for entry in typed_compound.json()["entries"]]
            assert compound_names == ["bundle.min.js"]
            assert typed_compound.json()["filtered"] == {"files": 1, "size": 2, "entries": 1}

            typed_js = await client.get("/api/tree", params={"types": ".js"})
            assert typed_js.status_code == 200
            js_names = [entry["display"] for entry in typed_js.json()["entries"]]
            assert js_names == ["bundle.min.js"]

    asyncio.run(_run())


def test_git_kpress_render_honors_gitpath_without_mtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, commit = _build_store(tmp_path)
    seen: dict[str, Any] = {}
    original = kpress_adapter.render_kpress_view

    def _capture(**kwargs: Any) -> Any:
        seen.update(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(kpress_adapter, "render_kpress_view", _capture)

    async def _run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            readme_wire = _wire(b"README.md")
            rendered = await client.get(
                "/api/kpress/render",
                params={"path": readme_wire, "view": "rendered"},
            )
            assert rendered.status_code == 200
            body = rendered.json()
            assert "hello" in body["html"]
            assert "mtime" not in body
            assert str(store) not in rendered.text
            assert seen["source_path"] == readme_wire
            assert "README.md" not in str(seen["source_path"])
            assert seen["frontmatter"] is None
            assert seen["frontmatter_error"] is None

            relative = await client.get(
                "/api/kpress/render",
                params={"path": "README.md", "view": "rendered"},
            )
            assert relative.status_code == 404

            binary = await client.get(
                "/api/kpress/render",
                params={"path": _wire(b"nul.bin"), "view": "rendered"},
            )
            assert binary.status_code == 415
            assert binary.json()["error"] == "KPress render supports text-like files only"

            symlink = await client.get(
                "/api/kpress/render",
                params={"path": _wire(b"link"), "view": "rendered"},
            )
            assert symlink.status_code == 200
            assert "hello" in symlink.json()["html"]
            assert seen["source_path"] == _wire(b"README.md")

    asyncio.run(_run())


def test_git_file_and_kpress_surface_markdown_frontmatter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = tmp_path / "work"
    store = tmp_path / "store.git"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    (work / "note.md").write_text("---\ntitle: Pin\n---\nbody\n", encoding="utf-8")
    (work / "broken.md").write_text(
        "---\n: : : not valid yaml\nbad indent\n---\n\nbody\n",
        encoding="utf-8",
    )
    (work / "plain.md").write_text("# heading\n", encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "frontmatter")
    commit = _git(work, "rev-parse", "HEAD").decode().strip()
    _git(tmp_path, "clone", "--bare", "--template=", str(work), str(store), env_root=tmp_path)
    seen: dict[str, Any] = {}
    original = kpress_adapter.render_kpress_view

    def _capture(**kwargs: Any) -> Any:
        seen.update(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(kpress_adapter, "render_kpress_view", _capture)

    async def _run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            note = await client.get("/api/file", params={"path": _wire(b"note.md")})
            assert note.status_code == 200
            note_body = note.json()
            assert note_body["kind"] == "markdown"
            assert note_body["frontmatter"] == {"title": "Pin"}
            assert "frontmatter_error" not in note_body
            assert str(store) not in note.text

            broken = await client.get("/api/file", params={"path": _wire(b"broken.md")})
            assert broken.status_code == 200
            broken_body = broken.json()
            assert broken_body["kind"] == "markdown"
            assert "frontmatter" not in broken_body
            assert broken_body["frontmatter_error"]

            plain = await client.get("/api/file", params={"path": _wire(b"plain.md")})
            assert plain.status_code == 200
            assert "frontmatter" not in plain.json()
            assert "frontmatter_error" not in plain.json()

            rendered = await client.get(
                "/api/kpress/render",
                params={"path": _wire(b"note.md"), "view": "rendered"},
            )
            assert rendered.status_code == 200
            assert seen["frontmatter"] == {"title": "Pin"}
            assert seen["frontmatter_error"] is None

            seen.clear()
            broken_render = await client.get(
                "/api/kpress/render",
                params={"path": _wire(b"broken.md"), "view": "rendered"},
            )
            assert broken_render.status_code == 200
            assert seen["frontmatter"] is None
            assert seen["frontmatter_error"]

    asyncio.run(_run())


def test_git_text_preview_windows_match_filesystem_highlight_bound(tmp_path: Path) -> None:
    work = tmp_path / "work"
    store = tmp_path / "store.git"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    (work / "big.md").write_text("a" * (SYNTAX_HIGHLIGHT_MAX_BYTES + 123), encoding="utf-8")
    (work / "big.txt").write_text("a" * (TEXT_PREVIEW_CHUNK_BYTES + 123), encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "preview")
    commit = _git(work, "rev-parse", "HEAD").decode().strip()
    _git(tmp_path, "clone", "--bare", "--template=", str(work), str(store), env_root=tmp_path)

    async def _run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            md = await client.get("/api/file", params={"path": _wire(b"big.md")})
            assert md.status_code == 200
            md_body = md.json()
            assert md_body["type"] == "text"
            assert md_body["content_truncated"] is True
            assert md_body["highlight_disabled"] is False
            assert md_body["bytes_read"] == SYNTAX_HIGHLIGHT_MAX_BYTES
            assert len(md_body["content"]) == SYNTAX_HIGHLIGHT_MAX_BYTES
            assert md_body["content_preview_limit"] == SYNTAX_HIGHLIGHT_MAX_BYTES
            assert md_body["content_max_preview_limit"] == TEXT_PREVIEW_REQUEST_MAX_BYTES
            nxt = await client.get(
                "/api/file",
                params={
                    "path": _wire(b"big.md"),
                    "offset": str(md_body["bytes_read"]),
                    "limit": str(TEXT_PREVIEW_CHUNK_BYTES),
                },
            )
            assert nxt.status_code == 200
            nxt_body = nxt.json()
            assert nxt_body["content_offset"] == SYNTAX_HIGHLIGHT_MAX_BYTES
            assert nxt_body["bytes_read"] == 123
            assert nxt_body["content_truncated"] is False

            txt = await client.get("/api/file", params={"path": _wire(b"big.txt")})
            assert txt.status_code == 200
            txt_body = txt.json()
            assert txt_body["content_truncated"] is True
            assert txt_body["highlight_disabled"] is True
            assert txt_body["bytes_read"] == TEXT_PREVIEW_CHUNK_BYTES
            assert txt_body["content_preview_limit"] == TEXT_PREVIEW_CHUNK_BYTES
            assert str(store) not in md.text
            assert str(store) not in txt.text

    asyncio.run(_run())


def test_git_file_raw_kpress_follow_in_tree_symlinks(tmp_path: Path) -> None:
    work = tmp_path / "work"
    store = tmp_path / "store.git"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    (work / "README.md").write_text("hello\n", encoding="utf-8")
    (work / "docs").mkdir()
    (work / "docs" / "note.txt").write_text("nested\n", encoding="utf-8")
    (work / "docs" / "up").symlink_to("../README.md")
    (work / "escape").symlink_to("../README.md")
    (work / "docs" / "escape").symlink_to("../../README.md")
    (work / "to_docs").symlink_to("docs")
    (work / "dangling").symlink_to("missing")
    (work / "abs").symlink_to("/tmp/x")
    (work / "a").symlink_to("b")
    (work / "b").symlink_to("a")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "symlinks")
    commit = _git(work, "rev-parse", "HEAD").decode().strip()
    _git(tmp_path, "clone", "--bare", "--template=", str(work), str(store), env_root=tmp_path)

    async def _run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            nested = await client.get("/api/file", params={"path": _wire(b"docs", b"up")})
            assert nested.status_code == 200
            nested_body = nested.json()
            assert nested_body["path"] == _wire(b"docs", b"up")
            assert nested_body["display"].endswith("up")
            assert nested_body["content"] == "hello\n"
            assert nested_body["ext"] == ".md"
            assert nested_body["symlink"] is False
            nested_raw = await client.get("/raw", params={"path": _wire(b"docs", b"up")})
            assert nested_raw.content == b"hello\n"
            for escaping in (_wire(b"escape"), _wire(b"docs", b"escape")):
                for endpoint in ("/api/file", "/raw", "/api/kpress/render"):
                    refused = await client.get(endpoint, params={"path": escaping})
                    assert refused.status_code == 404

            folder = await client.get("/api/file", params={"path": _wire(b"to_docs")})
            assert folder.status_code == 200
            folder_body = folder.json()
            assert folder_body["type"] == "folder"
            assert folder_body["name"] == "to_docs"
            assert folder_body["path"] == _wire(b"to_docs")
            assert folder_body["git_kind"] == "tree"

            tree = await client.get("/api/tree")
            by_name = {node["name"]: node for node in tree.json()["tree"]}
            assert by_name["to_docs"]["type"] == "symlink"
            assert by_name["dangling"]["type"] == "symlink"

            assert (
                await client.get("/api/file", params={"path": _wire(b"dangling")})
            ).status_code == 404
            assert (
                await client.get("/api/file", params={"path": _wire(b"abs")})
            ).status_code == 404
            assert (await client.get("/api/file", params={"path": _wire(b"a")})).status_code == 404
            assert (await client.get("/raw", params={"path": _wire(b"to_docs")})).status_code == 404
            assert str(store) not in nested.text

    asyncio.run(_run())


def test_git_plugin_sidekicks_follow_in_tree_symlinks(tmp_path: Path) -> None:
    work = tmp_path / "work"
    store = tmp_path / "store.git"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    (work / "README.md").write_text("hello\n", encoding="utf-8")
    (work / "config.json").write_text('{"name": "pin", "count": 2}\n', encoding="utf-8")
    (work / "session.jsonl").write_text(
        '{"type":"system","subtype":"init","model":"claude-opus-4-20250514"}\n'
        '{"type":"assistant","message":{"role":"assistant",'
        '"content":[{"type":"text","text":"hello"}]}}\n',
        encoding="utf-8",
    )
    (work / "change.patch").write_text(
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n"
        "+++ b/src/app.py\n"
        "@@ -1,1 +1,1 @@\n"
        "-old\n"
        "+new\n"
        "diff --git a/gone.txt b/gone.txt\n"
        "deleted file mode 100644\n"
        "--- a/gone.txt\n"
        "+++ /dev/null\n"
        "@@ -1,1 +0,0 @@\n"
        "-bye\n",
        encoding="utf-8",
    )
    (work / "nul.bin").write_bytes(b"\x00\x01\x02BINARY")
    (work / "log").symlink_to("session.jsonl")
    (work / "cfg").symlink_to("config.json")
    (work / "binlink").symlink_to("nul.bin")
    (work / "patchlink").symlink_to("change.patch")
    (work / "dangling").symlink_to("missing")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "sidekick-symlinks")
    commit = _git(work, "rev-parse", "HEAD").decode().strip()
    _git(tmp_path, "clone", "--bare", "--template=", str(work), str(store), env_root=tmp_path)

    async def _run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            charts = await client.get(
                "/api/plugin/agent-log/charts",
                params={"path": _wire(b"log")},
            )
            assert charts.status_code == 200
            assert charts.json()["summary"]["metadata"]["adapter"] == "claude"

            parsed = await client.get(
                "/api/plugin/structured/parsed",
                params={"path": _wire(b"cfg")},
            )
            assert parsed.status_code == 200
            parsed_body = parsed.json()
            assert parsed_body["path"] == _wire(b"cfg")
            assert parsed_body["ext"] == ".json"
            assert parsed_body["parsed"] == {"name": "pin", "count": 2}

            chunk = await client.get(
                "/api/plugin/binary/chunk",
                params={"path": _wire(b"binlink"), "offset": 0, "limit": 16},
            )
            assert chunk.status_code == 200
            chunk_body = chunk.json()
            assert chunk_body["path"] == _wire(b"binlink")
            assert base64.b64decode(chunk_body["content_base64"]) == b"\x00\x01\x02BINARY"

            patch_wire = _wire(b"patchlink")
            children = await client.get("/api/plugin/diff/children", params={"path": patch_wire})
            assert children.status_code == 200
            rows = children.json()["children"]
            assert [row["path"] for row in rows] == [
                f"{patch_wire}/src/app.py",
                f"{patch_wire}/gone.txt",
            ]

            inner = await client.get(
                "/api/file",
                params={"path": f"{patch_wire}/src/app.py"},
            )
            assert inner.status_code == 200
            inner_body = inner.json()
            assert inner_body["kind"] == "diff"
            assert inner_body["container"] == patch_wire
            assert inner_body["container_inner"] == "src/app.py"
            assert inner_body["path"] == f"{patch_wire}/src/app.py"

            document = await client.get(
                "/api/plugin/diff/document",
                params={"path": f"{patch_wire}/src/app.py"},
            )
            assert document.status_code == 200
            parsed_doc = validate_document(document.json())
            assert parsed_doc.manifest.totals.files == 1
            only = parsed_doc.manifest.files[0]
            assert only.new is not None and only.new.path == "src/app.py"

            dangling = _wire(b"dangling")
            assert (
                await client.get("/api/plugin/agent-log/charts", params={"path": dangling})
            ).status_code == 404
            assert (
                await client.get("/api/plugin/structured/parsed", params={"path": dangling})
            ).status_code == 404
            assert (
                await client.get("/api/plugin/binary/chunk", params={"path": dangling})
            ).status_code == 404
            assert (
                await client.get("/api/plugin/diff/children", params={"path": dangling})
            ).status_code == 404
            assert str(store) not in charts.text

    asyncio.run(_run())


def test_git_image_file_and_raw_honor_gitpath_without_mtime(tmp_path: Path) -> None:
    work = tmp_path / "work"
    store = tmp_path / "store.git"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    (work / "pic.png").write_bytes(_PNG_1X1)
    (work / "logo").symlink_to("pic.png")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "image")
    commit = _git(work, "rev-parse", "HEAD").decode().strip()
    _git(tmp_path, "clone", "--bare", "--template=", str(work), str(store), env_root=tmp_path)

    async def _run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            png_wire = _wire(b"pic.png")
            envelope = await client.get("/api/file", params={"path": png_wire})
            assert envelope.status_code == 200
            body = envelope.json()
            assert body["subject"] == "git_revision"
            assert body["type"] == "image"
            assert body["kind"] == "image"
            assert body["ext"] == ".png"
            assert body["path"] == png_wire
            assert body["size"] == len(_PNG_1X1)
            assert "content" not in body
            assert "mtime" not in body
            assert "mtime_hash" not in body
            assert any(view["id"] == "preview" for view in body["views"])
            assert str(store) not in envelope.text

            raw = await client.get("/raw", params={"path": png_wire})
            assert raw.status_code == 200
            assert raw.content == _PNG_1X1
            assert raw.headers["content-type"].startswith("image/png")

            logo_wire = _wire(b"logo")
            followed = await client.get("/api/file", params={"path": logo_wire})
            assert followed.status_code == 200
            followed_body = followed.json()
            assert followed_body["path"] == logo_wire
            assert followed_body["type"] == "image"
            assert followed_body["ext"] == ".png"
            followed_raw = await client.get("/raw", params={"path": logo_wire})
            assert followed_raw.content == _PNG_1X1

            relative = await client.get("/api/file", params={"path": "pic.png"})
            assert relative.status_code == 404

    asyncio.run(_run())


def test_git_file_raw_tree_honor_newline_and_invalid_utf8_names(tmp_path: Path) -> None:
    work = tmp_path / "work"
    store = tmp_path / "store.git"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    (work / "README.md").write_text("hello\n", encoding="utf-8")
    _git(work, "add", "-A")
    utf8_oid = _hash_blob(work, b"bytes\n")
    newline_oid = _hash_blob(work, b"newline-name\n")
    _index_info(
        work,
        b"100644 blob " + utf8_oid.encode() + b"\tx\xff.txt\x00"
        b"100644 blob " + newline_oid.encode() + b"\tnew\nline.txt\x00",
    )
    _git(work, "commit", "-qm", "odd-names")
    commit = _git(work, "rev-parse", "HEAD").decode().strip()
    _git(tmp_path, "clone", "--bare", "--template=", str(work), str(store), env_root=tmp_path)

    odd_wire = _wire(b"x\xff.txt")
    newline_wire = _wire(b"new\nline.txt")

    async def _run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            tree = await client.get("/api/tree")
            assert tree.status_code == 200
            entries = tree.json()["entries"]
            by_path = {entry["path"]: entry for entry in entries}
            assert odd_wire in by_path
            assert newline_wire in by_path
            assert "\n" not in by_path[newline_wire]["display"]
            assert "\ufffd" in by_path[odd_wire]["display"]
            assert "\ufffd" in by_path[newline_wire]["display"]

            odd_file = await client.get("/api/file", params={"path": odd_wire})
            assert odd_file.status_code == 200
            odd_body = odd_file.json()
            assert odd_body["path"] == odd_wire
            assert odd_body["content"] == "bytes\n"
            assert odd_body["ext"] == ".txt"
            assert "\n" not in odd_body["display"]
            odd_raw = await client.get("/raw", params={"path": odd_wire})
            assert odd_raw.content == b"bytes\n"

            newline_file = await client.get("/api/file", params={"path": newline_wire})
            assert newline_file.status_code == 200
            newline_body = newline_file.json()
            assert newline_body["path"] == newline_wire
            assert newline_body["content"] == "newline-name\n"
            assert newline_body["ext"] == ".txt"
            assert "\n" not in newline_body["display"]
            newline_raw = await client.get("/raw", params={"path": newline_wire})
            assert newline_raw.content == b"newline-name\n"

            catalog = await client.get("/api/catalog")
            names = {row["p"]: row["n"] for row in catalog.json()["files"]}
            assert names[odd_wire] == "x\ufffd.txt"
            assert names[newline_wire] == "new\ufffdline.txt"
            assert "\n" not in names[newline_wire]

            view = await client.get(f"/view/{newline_wire}")
            assert view.status_code == 200
            assert str(store) not in tree.text

    asyncio.run(_run())


def test_split_git_container_wire_keeps_g1_prefix_and_host_inner() -> None:
    patch = GitPath.from_segments(b"docs", b"change.patch")
    path, inner = split_git_container_wire(f"{patch.to_wire()}/src/app.py")
    assert path == patch
    assert inner == "src/app.py"
    root, empty = split_git_container_wire("")
    assert root == GitPath.root() and empty == ""
    only, no_inner = split_git_container_wire(patch.to_wire())
    assert only == patch and no_inner == ""
    with pytest.raises(GitPathError):
        split_git_container_wire("change.patch/src/app.py")


def test_git_patch_container_honors_gitpath_prefix_and_inner(tmp_path: Path) -> None:
    store, commit = _build_store(tmp_path)

    async def _run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            patch_wire = _wire(b"change.patch")
            inner_wire = f"{patch_wire}/src/app.py"
            envelope = await client.get("/api/file", params={"path": inner_wire})
            assert envelope.status_code == 200
            body = envelope.json()
            assert body["subject"] == "git_revision"
            assert body["kind"] == "diff"
            assert body["container"] == patch_wire
            assert body["container_inner"] == "src/app.py"
            assert body["path"] == inner_wire
            assert body["content"] == ""
            assert "mtime" not in body
            assert str(store) not in envelope.text
            assert any(view["id"] == "diff" for view in body["views"])

            relative = await client.get("/api/file", params={"path": "change.patch/src/app.py"})
            assert relative.status_code == 404

            not_patch = await client.get(
                "/api/file", params={"path": f"{_wire(b'README.md')}/src/app.py"}
            )
            assert not_patch.status_code == 404

            children = await client.get("/api/plugin/diff/children", params={"path": patch_wire})
            assert children.status_code == 200
            rows = children.json()["children"]
            assert [row["path"] for row in rows] == [
                f"{patch_wire}/src/app.py",
                f"{patch_wire}/gone.txt",
            ]
            assert rows[0]["badge"] == "M" and rows[1]["badge"] == "D"
            assert str(store) not in children.text

            inner_children = await client.get(
                "/api/plugin/diff/children", params={"path": inner_wire}
            )
            assert inner_children.status_code == 404
            assert inner_children.json()["error"] == "diff_children"

            document = await client.get("/api/plugin/diff/document", params={"path": inner_wire})
            assert document.status_code == 200
            parsed = validate_document(document.json())
            assert parsed.manifest.totals.files == 1
            only = parsed.manifest.files[0]
            assert only.new is not None and only.new.path == "src/app.py"
            assert str(store) not in document.text

            missing_inner = await client.get(
                "/api/plugin/diff/document",
                params={"path": f"{patch_wire}/absent.py"},
            )
            assert missing_inner.status_code == 404
            assert missing_inner.json()["error"] == "diff_document"

            relative_doc = await client.get(
                "/api/plugin/diff/document",
                params={"path": "change.patch/src/app.py"},
            )
            assert relative_doc.status_code == 404

    asyncio.run(_run())


def test_git_binary_chunk_honors_gitpath_without_mtime(tmp_path: Path) -> None:
    store, commit = _build_store(tmp_path)

    async def _run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            nul_wire = _wire(b"nul.bin")
            chunk = await client.get(
                "/api/plugin/binary/chunk",
                params={"path": nul_wire, "offset": 0, "limit": 16},
            )
            assert chunk.status_code == 200
            body = chunk.json()
            assert body["type"] == "binary_chunk"
            assert body["path"] == nul_wire
            assert body["offset"] == 0
            assert body["logical_size"] == 9
            assert body["bytes_read"] == 9
            assert body["has_more"] is False
            assert body["mtime_hash"]
            assert "mtime" not in body
            assert str(store) not in chunk.text
            assert base64.b64decode(body["content_base64"]) == b"\x00\x01\x02BINARY"

            interior = await client.get(
                "/api/plugin/binary/chunk",
                params={"path": nul_wire, "offset": 3, "limit": 4},
            )
            assert interior.status_code == 200
            interior_body = interior.json()
            assert interior_body["mtime_hash"] == body["mtime_hash"]
            assert base64.b64decode(interior_body["content_base64"]) == b"BINA"

            relative = await client.get(
                "/api/plugin/binary/chunk",
                params={"path": "nul.bin"},
            )
            assert relative.status_code == 404

            symlink = await client.get(
                "/api/plugin/binary/chunk",
                params={"path": _wire(b"link")},
            )
            assert symlink.status_code == 200
            symlink_body = symlink.json()
            assert symlink_body["path"] == _wire(b"link")
            assert base64.b64decode(symlink_body["content_base64"]) == b"hello\n"

    asyncio.run(_run())


def test_git_structured_parsed_and_plugin_kind_by_extension(tmp_path: Path) -> None:
    store, commit = _build_store(tmp_path)

    async def _run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            json_wire = _wire(b"config.json")
            envelope = await client.get("/api/file", params={"path": json_wire})
            assert envelope.status_code == 200
            body = envelope.json()
            assert body["subject"] == "git_revision"
            assert body["kind"] == "structured"
            assert body["type"] == "text"
            assert body["content"] == '{"name": "pin", "count": 2}\n'
            assert "mtime" not in body
            assert "mtime_hash" not in body
            assert str(store) not in envelope.text
            assert any(view["id"] == "tree" for view in body["views"])

            parsed = await client.get(
                "/api/plugin/structured/parsed",
                params={"path": json_wire},
            )
            assert parsed.status_code == 200
            parsed_body = parsed.json()
            assert parsed_body["type"] == "structured"
            assert parsed_body["path"] == json_wire
            assert parsed_body["ext"] == ".json"
            assert parsed_body["parsed"] == {"name": "pin", "count": 2}
            assert parsed_body["truncated"] is False
            assert parsed_body["parse_error"] is None
            assert parsed_body["mtime_hash"]
            assert "mtime" not in parsed_body
            assert str(store) not in parsed.text

            relative = await client.get(
                "/api/plugin/structured/parsed",
                params={"path": "config.json"},
            )
            assert relative.status_code == 404

            unsupported = await client.get(
                "/api/plugin/structured/parsed",
                params={"path": _wire(b"README.md")},
            )
            assert unsupported.status_code == 400
            assert unsupported.json()["error"] == "Unsupported extension"

            patch_wire = _wire(b"change.patch")
            patch_file = await client.get("/api/file", params={"path": patch_wire})
            assert patch_file.status_code == 200
            patch_body = patch_file.json()
            assert patch_body["kind"] == "diff"
            assert any(view["id"] == "diff" for view in patch_body["views"])
            assert "mtime" not in patch_body
            assert str(store) not in patch_file.text

    asyncio.run(_run())


def test_git_agent_log_charts_and_adapter_kind(tmp_path: Path) -> None:
    store, commit = _build_store(tmp_path)

    async def _run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            log_wire = _wire(b"session.jsonl")
            envelope = await client.get("/api/file", params={"path": log_wire})
            assert envelope.status_code == 200
            body = envelope.json()
            assert body["subject"] == "git_revision"
            assert body["type"] == "jsonl"
            assert body["kind"] == "agent-log"
            assert body["summary"]["adapter"] == "claude"
            assert body["events"]
            assert "mtime" not in body
            assert "mtime_hash" not in body
            assert str(store) not in envelope.text
            assert any(view["id"] == "charts" for view in body["views"])

            charts = await client.get(
                "/api/plugin/agent-log/charts",
                params={"path": log_wire},
            )
            assert charts.status_code == 200
            charts_body = charts.json()
            assert charts_body["summary"]["metadata"]["adapter"] == "claude"
            assert str(store) not in charts.text

            relative = await client.get(
                "/api/plugin/agent-log/charts",
                params={"path": "session.jsonl"},
            )
            assert relative.status_code == 404

            unsupported = await client.get(
                "/api/plugin/agent-log/charts",
                params={"path": _wire(b"README.md")},
            )
            assert unsupported.status_code == 400
            assert unsupported.json()["error"] == "Not a JSONL file"

            missing = await client.get(
                "/api/plugin/agent-log/charts",
                params={"path": _wire(b"absent.jsonl")},
            )
            assert missing.status_code == 404

    asyncio.run(_run())


def test_git_file_classifies_json_content_key(tmp_path: Path) -> None:
    from metabrowser.plugin_loader.classify import CompiledKindRule
    from metabrowser.plugin_loader.manifest import KindMatch, KindRule
    from metabrowser.server import _PLUGIN_KIND_RULES

    rule = CompiledKindRule(
        rule=KindRule(
            id="pin-config",
            match=KindMatch(ext=".json", json_has_key="name"),
            priority=100,
        ),
        plugin_name="test-pin",
        discovery_index=10_000,
    )
    _PLUGIN_KIND_RULES.append(rule)
    store, commit = _build_store(tmp_path)

    async def _run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            envelope = await client.get("/api/file", params={"path": _wire(b"config.json")})
            assert envelope.status_code == 200
            body = envelope.json()
            assert body["kind"] == "pin-config"
            assert body["type"] == "text"
            assert str(store) not in envelope.text

    try:
        asyncio.run(_run())
    finally:
        _PLUGIN_KIND_RULES.remove(rule)


def test_git_pin_refuses_inventory_backed_routes(tmp_path: Path) -> None:
    store, commit = _build_store(tmp_path)

    async def _run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            stream = await client.get("/api/stream")
            assert stream.status_code == 409
            stream_body = stream.json()
            assert stream_body["code"] == "unsupported_for_subject"
            assert stream_body["capability"] == "filesystem"
            assert str(store) not in stream.text
            diagnostic = await client.post("/api/diagnostics/pending-tallies", json={"pending": {}})
            assert diagnostic.status_code == 409
            assert diagnostic.json()["capability"] == "filesystem"

    asyncio.run(_run())


def test_git_index_status_is_complete_without_mtime_or_watcher(tmp_path: Path) -> None:
    store, commit = _build_store(tmp_path)

    async def _run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            progress = await client.get("/api/index/progress")
            assert progress.status_code == 200
            progress_body = progress.json()
            assert progress_body["status"] == "done"
            assert progress_body["complete"] is True
            assert progress_body["truncated"] is False
            assert progress_body["active"] is False
            assert progress_body["indexed_files"] == 9
            assert progress_body["provider"] == "git"
            assert progress_body["contract"] == "git-revision"
            assert "mtime" not in progress_body
            assert str(store) not in progress.text

            meta = await client.get("/api/index/meta")
            assert meta.status_code == 200
            meta_body = meta.json()
            assert meta_body["status"] == "done"
            assert meta_body["indexed_files"] == 9
            assert meta_body["indexed_dirs"] == 1
            assert meta_body["complete"] is True
            assert "oldest_mtime_ns" not in meta_body
            assert "newest_mtime_ns" not in meta_body
            assert "watch_mode" not in meta_body
            suffixes = {row["ext"]: row["count"] for row in meta_body["suffixes"]}
            assert suffixes[".bin"] == 2
            assert suffixes[".md"] == 1
            assert suffixes[".txt"] == 1
            assert "" not in suffixes
            assert str(store) not in meta.text

            caps = await client.get("/api/capabilities")
            assert caps.status_code == 200
            caps_body = caps.json()
            assert caps_body["index"]["complete"] is True
            assert caps_body["index"]["indexed_files"] == 9
            assert caps_body["index"]["truncated"] is False
            assert caps_body["index"]["provider"] == "git"
            assert caps_body["backends"][0]["mode"] == "none"
            assert caps_body["backends"][0]["reason"] == "git-revision-immutable"
            assert caps_body["events"]["stream"] == "off"
            assert caps_body["events"]["reason"] == "git-revision-no-watcher"
            assert str(store) not in caps.text

    asyncio.run(_run())


def test_git_tree_exposes_filter_tallies_without_ignored_or_mtime(tmp_path: Path) -> None:
    store, commit = _build_store(tmp_path)

    async def _run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            tree = await client.get("/api/tree")
            assert tree.status_code == 200
            body = tree.json()
            assert body["tally_cache_status"] == "done"
            assert body["tally_cache_max_files"] == INVENTORY_MAX_FILES
            assert "recency_tallies" not in body
            assert "oldest_mtime_ns" not in body
            rows = {row[0]: (row[1], row[2]) for row in body["extensions"]}
            assert rows[".bin"] == (2, 0)
            assert rows[".md"] == (1, 0)
            assert rows[".json"] == (1, 0)
            assert rows[".txt"] == (1, 0)
            assert "" not in rows
            canonical = {row[0]: (row[1], row[2]) for row in body["canonical_extensions"]}
            assert canonical[".md"] == (1, 0)
            assert canonical[".bin"] == (2, 0)
            families = {row[0]: (row[1], row[2]) for row in body["type_families"]}
            assert families["markdown"] == (1, 0)
            assert families["json"] == (1, 0)
            assert families["html"] == (1, 0)
            presets = {row[0]: (row[1], row[2]) for row in body["type_presets"]}
            assert presets["code"] == (1, 0)
            assert presets["docs"] == (2, 0)
            assert presets["data"] == (1, 0)
            assert presets["archives"] == (0, 0)
            assert presets["media"] == (0, 0)
            files = 0
            size = 0
            for node in body["tree"]:
                if node["type"] == "dir":
                    files += int(node["total_files"])
                    size += int(node["total_size"])
                elif "size" in node:
                    files += 1
                    size += int(node["size"])
            assert body["summary"] == {
                "files": 9,
                "size": size,
                "ignored_files": 0,
                "ignored_size": 0,
            }
            assert files == 9
            assert "filtered" not in body
            assert str(store) not in tree.text

            docs = await client.get("/api/tree", params={"path": _wire(b"docs")})
            assert docs.status_code == 200
            docs_body = docs.json()
            assert docs_body["tally_cache_status"] == "done"
            assert {row[0]: (row[1], row[2]) for row in docs_body["extensions"]} == rows
            assert {row[0]: (row[1], row[2]) for row in docs_body["type_presets"]} == presets
            assert docs_body["summary"] == body["summary"]
            assert str(store) not in docs.text

    asyncio.run(_run())


def test_git_file_raw_return_lfs_pointer_bytes_without_smudge(tmp_path: Path) -> None:
    work = tmp_path / "work"
    store = tmp_path / "store.git"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    (work / ".gitattributes").write_text(
        "*.bin filter=lfs diff=lfs merge=lfs -text\n", encoding="utf-8"
    )
    (work / "media.bin").write_bytes(_LFS_POINTER)
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "lfs pointer")
    commit = _git(work, "rev-parse", "HEAD").decode().strip()
    _git(tmp_path, "clone", "--bare", "--template=", str(work), str(store), env_root=tmp_path)
    marker = tmp_path / "smudge-ran"
    smudge = tmp_path / "smudge.sh"
    smudge.write_text(
        f"#!/bin/sh\necho SMUDGED > '{marker}'\necho SMUDGED\n",
        encoding="utf-8",
    )
    smudge.chmod(0o755)
    _git(store, "config", "filter.lfs.smudge", str(smudge))
    _git(store, "config", "filter.lfs.required", "true")

    async def _run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            raw = await client.get("/raw", params={"path": _wire(b"media.bin")})
            assert raw.status_code == 200
            assert raw.content == _LFS_POINTER
            envelope = await client.get("/api/file", params={"path": _wire(b"media.bin")})
            assert envelope.status_code == 200
            body = envelope.json()
            assert body["size"] == len(_LFS_POINTER)
            assert body["oid"] == _git(store, "rev-parse", f"{commit}:media.bin").decode().strip()
            assert "git-lfs" in body["content"]
            assert str(store) not in envelope.text

    asyncio.run(_run())
    assert marker.exists() is False


def test_git_file_raw_promisor_miss_is_object_unavailable(tmp_path: Path) -> None:
    work = tmp_path / "work"
    store = tmp_path / "store.git"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    (work / "README.md").write_text("hello\n", encoding="utf-8")
    (work / "keep.txt").write_text("kept\n", encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "two blobs")
    commit = _git(work, "rev-parse", "HEAD").decode().strip()
    missing_oid = _git(work, "rev-parse", "HEAD:README.md").decode().strip()
    _git(tmp_path, "clone", "--bare", "--template=", str(work), str(store), env_root=tmp_path)
    _delete_store_blob(store, missing_oid)
    with _unanswered_promisor() as url:
        _git(store, "config", "extensions.partialClone", "origin")
        _git(store, "config", "remote.origin.promisor", "true")
        _git(store, "config", "remote.origin.url", url)

        async def _run() -> None:
            async with _pinned_client(store, commit) as (client, _subject):
                tree = await client.get("/api/tree")
                assert tree.status_code == 200
                tree_body = tree.json()
                names = {entry["display"] for entry in tree_body["entries"]}
                assert names == {"README.md", "keep.txt"}
                assert "summary" not in tree_body
                started = time.monotonic()
                async with asyncio.timeout(2):
                    missing = await client.get("/api/file", params={"path": _wire(b"README.md")})
                assert time.monotonic() - started < _PROMISOR_MISS_BUDGET_S
                assert missing.status_code == 404
                body = missing.json()
                assert body["code"] == "object_unavailable"
                assert body["oid"] == missing_oid
                assert str(store) not in missing.text
                raw = await client.get("/raw", params={"path": _wire(b"README.md")})
                assert raw.status_code == 404
                kept = await client.get("/api/file", params={"path": _wire(b"keep.txt")})
                assert kept.status_code == 200
                assert kept.json()["content"] == "kept\n"
                rollup = await client.get("/api/rollup")
                assert rollup.status_code == 404
                assert rollup.json()["code"] == "object_unavailable"
                assert rollup.json()["oid"] == missing_oid
                catalog = await client.get("/api/catalog")
                assert catalog.status_code == 200
                catalog_body = catalog.json()
                assert catalog_body["complete"] is True
                paths = {file["p"] for file in catalog_body["files"]}
                assert _wire(b"README.md") in paths
                assert _wire(b"keep.txt") in paths
                assert str(store) not in catalog.text

        asyncio.run(_run())


def test_git_view_shell_honors_gitpath_and_refuses_filesystem_spelling(tmp_path: Path) -> None:
    store, commit = _build_store(tmp_path)
    readme = _wire(b"README.md")
    missing = _wire(b"nope.txt")
    patch_inner = f"{_wire(b'change.patch')}/src/app.py"

    async def _run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            root = await client.get("/view/")
            assert root.status_code == 200
            assert "text/html" in root.headers.get("content-type", "")
            assert str(store) not in root.text
            assert commit[:12] in root.text
            assert "METABROWSER_REPOSITORY_CONTEXT=null" in root.text
            assert 'METABROWSER_SOURCE_KIND="git_revision"' in root.text
            blob = await client.get(f"/view/{readme}")
            assert blob.status_code == 200
            assert "text/html" in blob.headers.get("content-type", "")
            absent = await client.get(f"/view/{missing}")
            assert absent.status_code == 200
            inner = await client.get(f"/view/{patch_inner}")
            assert inner.status_code == 200
            filesystem = await client.get("/view/README.md")
            assert filesystem.status_code == 400
            assert filesystem.text == "Invalid view path."
            assert str(store) not in filesystem.text

    asyncio.run(_run())
