"""Windowed blob reads on a Git pin: classify and page a blob without holding it whole.

``cat-file`` has no byte ranges, so a window streams the blob from its start. These pin
what that costs in held state (only the window), what it leaves behind (an actor that is
reused after a short remainder and replaced after a long one), and what the routes and
the plugin content reader answer for a blob past the pin's whole-read ceiling: the same
thing the filesystem answers for a large file, instead of a 413 before classification.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

import pytest

from metabrowser.git import tree_source as tree_module
from metabrowser.git.process import repository_store_target
from metabrowser.git.tree_source import (
    GitBatchProtocolError,
    GitObjectUnavailableError,
    GitPath,
    GitTreeSource,
    git_revision_subject,
)
from metabrowser.settings import TEXT_PREVIEW_CHUNK_BYTES, TEXT_PREVIEW_REQUEST_MAX_BYTES
from metabrowser.source import read_content_window
from tests.git_pin_harness import fast_import_store
from tests.test_git_revision_content_routes import _pinned_client

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required")

_ZERO_OID = "0" * 40
_LINES = b"".join(b"line %05d of a text blob\n" % index for index in range(400))
_FRONTMATTER = b"---\ntitle: Pinned\n---\n\n# Heading\n\n" + b"body text\n" * 40
_JSONL = (
    b'{"type":"system","subtype":"init","model":"claude-opus-4-20250514"}\n'
    b'{"type":"assistant","message":{"role":"assistant",'
    b'"content":[{"type":"text","text":"hello"}]}}\n'
)
_PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 120
_BINARY = bytes(range(256)) * 4
# Every fixture blob is larger than this, so every route below takes the windowed path.
_CEILING = 64


def _wire(name: bytes) -> str:
    return GitPath.from_segments(name).to_wire()


def _store(tmp_path: Path) -> tuple[Path, str]:
    return fast_import_store(
        tmp_path,
        {
            b"lines.txt": _LINES,
            b"notes": _LINES,
            b"doc.md": _FRONTMATTER,
            b"session.jsonl": _JSONL,
            b"pic.png": _PNG_HEADER,
            b"data.bin": _BINARY,
        },
    )


async def _source(store: Path, commit: str) -> GitTreeSource:
    subject = await git_revision_subject(
        target=repository_store_target(git_dir=store), commit_oid=commit, store_identity="w"
    )
    return subject.tree_source


async def _oid(source: GitTreeSource, name: bytes) -> str:
    entry = await source.resolve_path(GitPath.from_segments(name))
    assert entry is not None
    return entry.oid


async def _actor_pid(source: GitTreeSource) -> int | None:
    async with source._pool.checkout() as reader:  # pyright: ignore[reportPrivateUsage]
        proc = reader._proc  # pyright: ignore[reportPrivateUsage]
        return None if proc is None or proc.returncode is not None else proc.pid


# ── The reader ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("offset", "max_bytes"),
    [(0, 10), (0, len(_LINES)), (100, 250), (len(_LINES) - 5, 50), (len(_LINES) + 9, 10), (7, 0)],
)
def test_a_window_is_the_slice_the_whole_blob_would_give(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, offset: int, max_bytes: int
) -> None:
    # A small chunk makes the skip and the drain each span several reads.
    monkeypatch.setattr(tree_module, "_STREAM_CHUNK_BYTES", 7)
    store, commit = _store(tmp_path)

    async def run() -> None:
        source = await _source(store, commit)
        try:
            window, size = await source.read_blob_window(
                await _oid(source, b"lines.txt"), offset=offset, max_bytes=max_bytes
            )
            assert size == len(_LINES)
            assert window == _LINES[offset : offset + max_bytes]
        finally:
            await source.aclose()

    asyncio.run(run())


def test_a_short_remainder_is_drained_and_the_actor_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tree_module, "BLOB_WINDOW_DRAIN_MAX_BYTES", len(_LINES))
    store, commit = _store(tmp_path)

    async def run() -> None:
        source = await _source(store, commit)
        try:
            oid = await _oid(source, b"lines.txt")
            first, _size = await source.read_blob_window(oid, offset=0, max_bytes=10)
            pid = await _actor_pid(source)
            assert pid is not None
            second, _size = await source.read_blob_window(oid, offset=10, max_bytes=10)
            assert first + second == _LINES[:20]
            assert await _actor_pid(source) == pid
        finally:
            await source.aclose()

    asyncio.run(run())


def test_a_long_remainder_replaces_the_actor_and_the_next_read_still_works(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tree_module, "BLOB_WINDOW_DRAIN_MAX_BYTES", 16)
    store, commit = _store(tmp_path)

    async def run() -> None:
        source = await _source(store, commit)
        try:
            oid = await _oid(source, b"lines.txt")
            window, _size = await source.read_blob_window(oid, offset=0, max_bytes=10)
            assert window == _LINES[:10]
            assert await _actor_pid(source) is None
            assert await source.read_blob(GitPath.from_segments(b"doc.md")) == _FRONTMATTER
            tail, _size = await source.read_blob_window(oid, offset=len(_LINES) - 8, max_bytes=100)
            assert tail == _LINES[-8:]
            assert await _actor_pid(source) is not None
        finally:
            await source.aclose()

    asyncio.run(run())


def test_a_missing_or_non_blob_object_is_refused(tmp_path: Path) -> None:
    store, commit = _store(tmp_path)

    async def run() -> None:
        subject = await git_revision_subject(
            target=repository_store_target(git_dir=store), commit_oid=commit, store_identity="w"
        )
        source = subject.tree_source
        try:
            oid = await _oid(source, b"lines.txt")
            await source.read_blob_window(oid, offset=0, max_bytes=1)
            pid = await _actor_pid(source)
            with pytest.raises(GitObjectUnavailableError):
                await source.read_blob_window(_ZERO_OID, offset=0, max_bytes=1)
            # A missing object is a whole frame, so the actor survives it.
            assert await _actor_pid(source) == pid
            with pytest.raises(GitBatchProtocolError, match="not a blob"):
                await source.read_blob_window(subject.tree_oid, offset=0, max_bytes=1)
            window, _size = await source.read_blob_window(oid, offset=0, max_bytes=4)
            assert window == _LINES[:4]
        finally:
            await subject.aclose()

    asyncio.run(run())


def test_the_content_reader_pages_a_blob_past_the_whole_read_ceiling(tmp_path: Path) -> None:
    """``read_content_window`` used to refuse such a blob with a 413 on a pin."""

    store, commit = _store(tmp_path)

    async def run() -> None:
        subject = await git_revision_subject(
            target=repository_store_target(git_dir=store),
            commit_oid=commit,
            store_identity="w",
            max_blob_bytes=_CEILING,
        )
        try:
            ref = await subject.tree_source.open_ref(_wire(b"data.bin"))
            assert ref is not None
            pages = []
            offset = 0
            while True:
                window = await read_content_window(ref, offset=offset, max_bytes=300)
                pages.append(window.data)
                offset += len(window.data)
                if not window.has_more:
                    break
            assert b"".join(pages) == _BINARY
            assert len(pages) == 4
        finally:
            await subject.aclose()

    asyncio.run(run())


# ── /api/file past the ceiling ─────────────────────────────────────


def test_a_blob_past_the_ceiling_is_classified_like_a_large_file(tmp_path: Path) -> None:
    store, commit = _store(tmp_path)

    async def run() -> None:
        async with _pinned_client(store, commit, max_blob_bytes=_CEILING) as (client, _subject):

            async def file(name: bytes, **params: str) -> dict[str, object]:
                response = await client.get("/api/file", params={"path": _wire(name), **params})
                assert response.status_code == 200, (name, response.text)
                return response.json()

            text = await file(b"lines.txt")
            assert (text["type"], text["size"]) == ("text", len(_LINES))
            assert text["content"] == _LINES[:_CEILING].decode()
            assert text["content_truncated"] is True

            later = await file(b"lines.txt", offset="40", limit="100")
            assert later["content"] == _LINES[40:_CEILING].decode()
            assert later["content_preview_limit"] == _CEILING - 40

            # No extension: a text sniff of the leading bytes, as on the filesystem.
            assert (await file(b"notes"))["type"] == "text"

            binary = await file(b"data.bin")
            assert (binary["type"], binary["size"]) == ("binary", len(_BINARY))
            assert "content" not in binary

            image = await file(b"pic.png")
            assert (image["type"], image["size"]) == ("image", len(_PNG_HEADER))

            markdown = await file(b"doc.md")
            assert markdown["type"] == "text"
            assert markdown["frontmatter"] == {"title": "Pinned"}

            jsonl = await file(b"session.jsonl")
            assert jsonl["type"] == "jsonl"
            assert jsonl["size"] == len(_JSONL)

            past = await client.get(
                "/api/file", params={"path": _wire(b"lines.txt"), "offset": str(_CEILING)}
            )
            assert past.status_code == 416
            assert past.json()["max_offset"] == _CEILING

    asyncio.run(run())


def test_a_blob_past_the_default_ceiling_serves_its_first_window(tmp_path: Path) -> None:
    """The reported case: a text blob over 16 MiB answered 413 before classification."""

    line = b"a line of a large text blob committed to the repository\n"
    body = line * ((TEXT_PREVIEW_REQUEST_MAX_BYTES + 64 * 1024) // len(line) + 1)
    store, commit = fast_import_store(tmp_path, {b"large.log": body})

    async def run() -> None:
        async with _pinned_client(store, commit) as (client, _subject):
            response = await client.get("/api/file", params={"path": _wire(b"large.log")})
            assert response.status_code == 200
            payload = response.json()
            assert payload["type"] == "text"
            assert payload["size"] == len(body)
            assert payload["content_bytes"] == TEXT_PREVIEW_CHUNK_BYTES
            assert payload["content"].encode() == body[:TEXT_PREVIEW_CHUNK_BYTES]
            assert payload["content_truncated"] is True

    asyncio.run(run())


def test_a_jsonl_blob_past_the_parser_ceiling_reports_it_like_the_filesystem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser import jsonl_view

    monkeypatch.setattr(jsonl_view, "_JSONL_PARSE_MAX_BYTES", len(_JSONL) - 1)
    store, commit = _store(tmp_path)

    async def run() -> None:
        async with _pinned_client(store, commit, max_blob_bytes=_CEILING) as (client, _subject):
            response = await client.get("/api/file", params={"path": _wire(b"session.jsonl")})
            assert response.status_code == 200
            payload = json.loads(response.text)
            assert payload["type"] == "error"
            assert "JSONL content exceeds" in payload["error"]

    asyncio.run(run())


def test_the_fixture_blobs_all_exceed_the_ceiling() -> None:
    for body in (_LINES, _FRONTMATTER, _JSONL, _PNG_HEADER, _BINARY):
        assert len(body) > _CEILING
