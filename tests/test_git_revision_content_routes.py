"""What a pinned revision answers that no CLI transcript can show.

The envelopes ``--api`` can reach on one origin are the ``cli-git-pin-*.txt``
transcripts, driven by ``tests/test_cli_git_pin_golden.py``: index status, the tree and
its tallies, the rollup, the catalog, a file envelope per kind, the blob hooks, and the
refusals. What stays here needs something a transcript lacks:

- ``/raw``, ``/view/``, and ``/api/kpress/render``, which ``--api`` does not issue;
- response headers: the raw sandbox and the same-origin proof;
- a store built for one case: a missing object, an LFS pointer with a smudge filter
  configured, symlink shapes, a gitlink-only directory, frontmatter, compound
  extensions, a patch container, a lowered whole-read ceiling;
- an observation from inside: the thread a parse ran on, what KPress was passed.
"""

from __future__ import annotations

import asyncio
import base64
import os
import subprocess
import threading
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from httpx2 import ASGITransport, AsyncClient

from metabrowser import jsonl_view, kpress_adapter
from metabrowser.capabilities import Capabilities, set_capabilities
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
    SYNTAX_HIGHLIGHT_MAX_BYTES,
    TEXT_PREVIEW_CHUNK_BYTES,
    TEXT_PREVIEW_REQUEST_MAX_BYTES,
)
from metabrowser.source import attach_subject, reset_source_session
from metabrowser.wire_models import validate_rollup_node
from tests.git_pin_harness import fast_import_store
from tests.required_tools import needs_git

pytestmark = needs_git

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
    if not loose.is_file():
        raise AssertionError(f"store blob {oid} was not a loose object")
    loose.unlink()


def _wire(*names: bytes) -> str:
    return GitPath.from_segments(*names).to_wire()


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
        store_identity="fixture",
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
        # Not teardown: tests open several pins in turn.
        reset_source_session()


def test_git_directory_with_no_blob_and_rollup_of_a_subtree(tmp_path: Path) -> None:
    """``vendor/`` holds one gitlink and no blob, which the transcripts' origin lacks.

    It is a folder with zero totals, not one whose totals are omitted, and the gitlink
    in it is a file node with no size that is neither a tree nor raw bytes. A rollup
    below the root names its children by their whole wire, which the transcripts' root
    rollup cannot show.
    """

    store, commit = _build_store(tmp_path)
    docs, note = _wire(b"docs"), _wire(b"docs", b"note.txt")
    vendor, dep = _wire(b"vendor"), _wire(b"vendor", b"dep")

    async def _run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            tree = (await client.get("/api/tree")).json()["tree"]
            node = next(node for node in tree if node["name"] == "vendor")
            assert (node["type"], node["total_files"], node["total_size"]) == ("dir", 0, 0)
            assert node["children"] == [{"name": "dep", "path": dep, "type": "file"}]

            folder = (await client.get("/api/file", params={"path": vendor})).json()
            assert folder["dir"] == {"total_files": 0, "total_size": 0}
            assert folder["readme_path"] == ""
            assert [view["id"] for view in folder["views"]] == ["overview", "treemap"]
            assert (await client.get("/raw", params={"path": dep})).status_code == 404
            # The index counts the directories its blobs are in: docs/, and not vendor/.
            assert (await client.get("/api/index/meta")).json()["indexed_dirs"] == 1

            empty = (await client.get("/api/rollup", params={"path": vendor})).json()["node"]
            assert (empty["total_files"], empty["total_size"], empty["children"]) == (0, 0, [])

            nested = await client.get("/api/rollup", params={"path": docs, "depth": "1"})
            assert nested.status_code == 200
            nested_node = nested.json()["node"]
            validate_rollup_node(nested_node)
            assert (nested_node["path"], nested_node["total_files"]) == (docs, 1)
            assert nested_node["total_size"] == 7
            assert [child["path"] for child in nested_node["children"]] == [note]
            assert str(store) not in nested.text

    asyncio.run(_run())


def test_git_rollup_names_use_the_tree_display_escaping(tmp_path: Path) -> None:
    """Rollup names are chrome: C0 bytes and invalid UTF-8 become U+FFFD, as in the tree."""

    store, commit = fast_import_store(
        tmp_path,
        {
            b'"ctl\\001dir/new\\nline.txt"': b"a\n",
            b'"ctl\\001dir/x\\377.txt"': b"bb\n",
        },
    )

    async def _run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            tree = (await client.get("/api/tree", params={"depth": "2"})).json()["tree"]
            rollup = await client.get("/api/rollup", params={"depth": "2"})
            assert rollup.status_code == 200
            node = rollup.json()["node"]
            validate_rollup_node(node)
            (directory,) = node["children"]
            (tree_directory,) = tree
            assert directory["name"] == tree_directory["name"] == "ctl�dir"
            assert directory["path"] == tree_directory["path"]
            names = {child["path"]: child["name"] for child in directory["children"]}
            assert names == {child["path"]: child["name"] for child in tree_directory["children"]}
            assert sorted(names.values()) == ["new�line.txt", "x�.txt"]

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
            typed_tree = typed_body["tree"]
            assert [node["name"] for node in typed_tree] == ["README.md"]
            assert typed_tree[0]["type"] == "file"
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

            # Past the whole-read ceiling a blob is still classified, from a bounded
            # window, the way the filesystem types a large file: /api/file answers.
            windowed = await client.get("/api/file", params={"path": _wire(b"big.bin")})
            assert windowed.status_code == 200
            windowed_body = windowed.json()
            assert windowed_body["type"] == "text"
            assert windowed_body["size"] == 64
            assert windowed_body["content"] == "x" * 32
            assert windowed_body["content_truncated"] is True

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
            assert nxt_body["content_bytes"] == 123
            assert nxt_body["bytes_read"] == SYNTAX_HIGHLIGHT_MAX_BYTES + 123
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


def test_git_symlinks_resolve_component_by_component_like_the_checkout(tmp_path: Path) -> None:
    """A link body is not normalized as text: the checkout on disk is the oracle.

    ``..`` after a directory link climbs from where the link led, a link partway
    through a target is followed, and ``file/..`` or ``missing/..`` does not resolve.
    """

    work = tmp_path / "work"
    store = tmp_path / "store.git"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    (work / "README.md").write_text("root readme\n", encoding="utf-8")
    (work / "docs" / "deep").mkdir(parents=True)
    (work / "docs" / "README.md").write_text("docs readme\n", encoding="utf-8")
    (work / "docs" / "deep" / "note.txt").write_text("deep note\n", encoding="utf-8")
    (work / "deep_link").symlink_to("docs/deep")
    (work / "climb").symlink_to("deep_link/../README.md")
    (work / "through").symlink_to("deep_link/note.txt")
    (work / "file_parent").symlink_to("README.md/../README.md")
    (work / "missing_parent").symlink_to("nope/../README.md")
    (work / "loop_mid").symlink_to("loop/README.md")
    (work / "loop").symlink_to("loop")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "symlinks")
    commit = _git(work, "rev-parse", "HEAD").decode().strip()
    _git(tmp_path, "clone", "--bare", "--template=", str(work), str(store), env_root=tmp_path)

    async def _run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            for name in (b"climb", b"through"):
                served = await client.get("/api/file", params={"path": _wire(name)})
                assert served.status_code == 200, name
                on_disk = (work / name.decode()).read_text(encoding="utf-8")
                assert served.json()["content"] == on_disk, name
                raw = await client.get("/raw", params={"path": _wire(name)})
                assert raw.content.decode() == on_disk, name
            assert (work / "climb").read_text(encoding="utf-8") == "docs readme\n"
            for name in (b"file_parent", b"missing_parent", b"loop_mid"):
                assert not (work / name.decode()).exists(), name
                refused = await client.get("/api/file", params={"path": _wire(name)})
                assert refused.status_code == 404, name

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

            # The container file is a diff too, by its extension.
            container = (await client.get("/api/file", params={"path": patch_wire})).json()
            assert container["kind"] == "diff"
            assert any(view["id"] == "diff" for view in container["views"])

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


def test_git_jsonl_blob_is_parsed_off_the_event_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A JSONL blob can be 16 MiB. Its parse must not run on the loop thread."""

    store, commit = _build_store(tmp_path)
    parse_threads: list[int] = []
    real_parse = jsonl_view.parse_jsonl_bytes

    def recording_parse(body: bytes) -> dict[str, Any]:
        parse_threads.append(threading.get_ident())
        return real_parse(body)

    monkeypatch.setattr(jsonl_view, "parse_jsonl_bytes", recording_parse)

    async def _run() -> None:
        loop_thread = threading.get_ident()
        async with _pinned_client(store, commit) as (client, _subject):
            response = await client.get("/api/file", params={"path": _wire(b"session.jsonl")})
            assert response.status_code == 200
            assert response.json()["type"] == "jsonl"
        assert parse_threads and loop_thread not in parse_threads

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


def test_git_file_raw_missing_blob_is_object_unavailable(tmp_path: Path) -> None:
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

    async def _run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            tree = await client.get("/api/tree")
            assert tree.status_code == 200
            tree_body = tree.json()
            sizes = {entry["display"]: entry.get("size") for entry in tree_body["entries"]}
            # The missing blob is listed, without a size, and the totals are omitted.
            assert sizes == {"README.md": None, "keep.txt": 5}
            assert "summary" not in tree_body
            missing = await client.get("/api/file", params={"path": _wire(b"README.md")})
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


def _assert_git_raw_sandbox(response: Any, *, active_content: bool) -> None:
    """The raw trust headers, whichever layer produced the response.

    ``_RawTrustHeaderMiddleware`` owns these for the whole ``/raw`` path, so a
    pinned Git subject must carry them exactly as a filesystem subject does --
    on a hit, on a miss, and with active content on or off.
    """

    csp = response.headers["content-security-policy"]
    assert csp.startswith("sandbox ")
    assert "allow-same-origin" not in csp
    assert "frame-ancestors" not in csp
    assert ("allow-scripts" in csp) is active_content
    assert response.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize("active_content", [True, False])
def test_git_raw_blobs_are_sandboxed_like_filesystem_raw(
    tmp_path: Path, active_content: bool
) -> None:
    """An HTML or SVG blob under a pin is opaque-origin sandboxed on the wire.

    ``raw_file`` dispatches a pinned subject to ``git_revision_raw`` before it
    reaches the filesystem branch, so trust-header evidence taken on that branch
    is evidence for the filesystem only. SECURITY.md promises the sandbox on
    every raw response; this asserts it against the Git bytes themselves.
    """

    store, commit = fast_import_store(
        tmp_path,
        {
            b"page.html": b"<!doctype html><script>parent.postMessage(1)</script>\n",
            b"pic.svg": b"<svg xmlns='http://www.w3.org/2000/svg'><script/></svg>\n",
        },
    )
    set_capabilities(Capabilities(active_content=active_content, mutations=False))

    async def _run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            for name in (b"page.html", b"pic.svg"):
                hit = await client.get("/raw", params={"path": _wire(name)})
                assert hit.status_code == 200, name
                _assert_git_raw_sandbox(hit, active_content=active_content)
                assert str(store) not in hit.text
            miss = await client.get("/raw", params={"path": _wire(b"absent.html")})
            assert miss.status_code == 404
            _assert_git_raw_sandbox(miss, active_content=active_content)
            # A filesystem spelling is not a wire identity, so it is a miss
            # too -- and a miss is still sandboxed.
            spelled = await client.get("/raw", params={"path": "page.html"})
            assert spelled.status_code == 404
            _assert_git_raw_sandbox(spelled, active_content=active_content)

    asyncio.run(_run())


def test_git_raw_path_form_is_a_sandboxed_capability_refusal(tmp_path: Path) -> None:
    """``/raw/{path}`` under a pin answers ``unsupported_for_subject``, sandboxed.

    The path form exists so relative references in a previewed document resolve,
    and a pin never offers that preview (mb-g5je). The refusal is typed rather than a
    404 that would misreport a present file, and it still carries the sandbox, so an
    answer on this branch cannot leave the application origin unprotected.
    """

    store, commit = fast_import_store(tmp_path, {b"page.html": b"<!doctype html><p>pin</p>\n"})

    async def _run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            for address in ("/raw/page.html", f"/raw/{_wire(b'page.html')}"):
                answered = await client.get(address)
                assert answered.status_code == 409, (address, answered.status_code)
                assert answered.json()["capability"] == "raw_document_path"
                _assert_git_raw_sandbox(answered, active_content=True)
                assert str(store) not in answered.text

    asyncio.run(_run())


def test_api_same_origin_proof_covers_the_git_content_routes(tmp_path: Path) -> None:
    """The ``/api/*`` proof is path-scoped, so a pin is behind it too."""

    store, commit = fast_import_store(tmp_path, {b"README.md": b"pin\n"})
    readme = {"path": _wire(b"README.md")}

    async def _run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            for route in ("/api/tree", "/api/file", "/api/capabilities"):
                params = readme if route == "/api/file" else None
                refused = await client.get(
                    route,
                    params=params,
                    headers={"origin": "https://evil.example", "sec-fetch-site": "cross-site"},
                )
                assert refused.status_code == 403, route
                accepted = await client.get(
                    route,
                    params=params,
                    headers={"sec-fetch-site": "same-origin"},
                )
                assert accepted.status_code == 200, route

    asyncio.run(_run())


def test_git_symlink_bodies_past_path_max_are_refused(tmp_path: Path) -> None:
    """A body longer than a checkout could hold is unresolvable, and costs nothing.

    Each component walks the tree from the root, so an unbounded crafted body kept
    the event loop busy for over a minute in review. The long body here would
    otherwise resolve to the README, so a 404 proves the bound, not a bad path.
    """

    work = tmp_path / "work"
    store = tmp_path / "store.git"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    (work / "README.md").write_text("root readme\n", encoding="utf-8")
    (work / "d").mkdir()
    (work / "d" / "keep").write_text("keep\n", encoding="utf-8")
    _git(work, "add", "-A")
    bodies = {"long": "d/../" * 820 + "README.md", "short": "d/../" * 800 + "README.md"}
    assert len(bodies["long"]) > 4096 >= len(bodies["short"])
    for name, body in bodies.items():
        target = work / f".{name}.body"
        target.write_text(body, encoding="utf-8")
        oid = _git(work, "hash-object", "-w", str(target)).decode().strip()
        target.unlink()
        _git(work, "update-index", "--add", "--cacheinfo", f"120000,{oid},{name}")
    _git(work, "commit", "-qm", "long links")
    commit = _git(work, "rev-parse", "HEAD").decode().strip()
    _git(tmp_path, "clone", "--bare", "--template=", str(work), str(store), env_root=tmp_path)

    async def _run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            short = await client.get("/api/file", params={"path": _wire(b"short")})
            assert short.status_code == 200, short.text
            assert short.json()["content"] == "root readme\n"
            long = await client.get("/api/file", params={"path": _wire(b"long")})
            assert long.status_code == 404, long.text

    asyncio.run(_run())
