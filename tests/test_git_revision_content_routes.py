"""File, raw, tree, KPress, patch containers, binary chunks, structured parsed, and agent-log honor GitPath on a pin."""

from __future__ import annotations

import asyncio
import base64
import os
import shutil
import subprocess
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from httpx2 import ASGITransport, AsyncClient

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


def test_git_kpress_render_honors_gitpath_without_mtime(tmp_path: Path) -> None:
    store, commit = _build_store(tmp_path)

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
            assert symlink.status_code == 404

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
            assert symlink.status_code == 404

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
