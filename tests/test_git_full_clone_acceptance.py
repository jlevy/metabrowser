"""Acceptance: a full clone is acquired cold, reused warm, and read with its origin gone.

Acquisition fetches every object, so a published store is complete and no read ever
needs the origin again. The origin here allows filters, the case in which a partial
clone would have left history's blobs behind. The test acquires it cold, proves the
store lacks no object and records no promisor, reuses it warm without running Git,
and then reads every family of store reads with the origin in place and with it
deleted: the pooled batch reader, file and raw routes, history, commit detail, and
the diff comparison, on the default pin and on its parent. Reads leave every file
under the store's ``objects/`` unchanged.

Nothing is patched: the acquisition floor must admit the Git on ``PATH`` (see
``tests/admitted_git.py``). CI runs this on the lowest admitted release and on the
newest patched one.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pytest
from httpx2 import Response

from metabrowser.cache import acquire as acquire_module
from metabrowser.cache.acquire import PublishedSource, acquire_source
from metabrowser.cache.urls import GitSource, classify_root_argument
from metabrowser.git.process import repository_store_target
from metabrowser.git.tree_source import GitPath, git_revision_subject
from tests.admitted_git import require_admitted_git
from tests.git_pin_harness import pinned_client

pytestmark = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")

# A hang guard, not a performance claim: every read below answers in milliseconds.
_HANG_GUARD_S = 30.0
_NOTE = GitPath.from_segments(b"notes", b"old.txt")
_KEEP = GitPath.from_segments(b"keep.txt")


@dataclass(frozen=True, slots=True)
class _Origin:
    path: Path
    first: str
    second: str
    history_blob: str


def _git_env() -> dict[str, str]:
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env.update(
        {
            "GIT_AUTHOR_NAME": "Full Clone",
            "GIT_AUTHOR_EMAIL": "full@example.invalid",
            "GIT_COMMITTER_NAME": "Full Clone",
            "GIT_COMMITTER_EMAIL": "full@example.invalid",
            "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
            "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
        }
    )
    return env


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, env=_git_env()
    )
    return result.stdout.decode().strip()


def _store_git(store: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "--git-dir", str(store), *args],
        check=True,
        capture_output=True,
        env=_git_env() | {"GIT_NO_LAZY_FETCH": "1"},
        timeout=60,
    )
    return result.stdout.decode()


def _objects(store: Path) -> dict[str, int]:
    """Every file under ``objects/`` with its size: any fetch changes this."""

    root = store / "objects"
    return {
        str(path.relative_to(root)): path.stat().st_size
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _file_source(origin: Path) -> GitSource:
    source = classify_root_argument(f"file://{origin.resolve()}")
    assert isinstance(source, GitSource)
    return source


def _origin(tmp_path: Path) -> _Origin:
    """A bare origin that would serve a blobless clone; one blob lives only in history."""

    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-q", "--initial-branch=topic")
    (work / "notes").mkdir()
    (work / "notes" / "old.txt").write_text("first draft\n", encoding="utf-8")
    (work / "keep.txt").write_text("kept\n", encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "-c", "commit.gpgsign=false", "commit", "-qm", "first")
    first = _git(work, "rev-parse", "HEAD")
    history_blob = _git(work, "rev-parse", f"{first}:notes/old.txt")
    (work / "notes" / "old.txt").write_text("second draft\n", encoding="utf-8")
    _git(work, "-c", "commit.gpgsign=false", "commit", "-qam", "second")
    second = _git(work, "rev-parse", "HEAD")
    origin = tmp_path / "origin.git"
    _git(tmp_path, "clone", "-q", "--bare", "--template=", "--", str(work), str(origin))
    _git(origin, "config", "uploadpack.allowFilter", "true")
    _git(origin, "config", "uploadpack.allowAnySHA1InWant", "true")
    return _Origin(origin, first, second, history_blob)


def _cold_acquire(tmp_path: Path) -> tuple[_Origin, PublishedSource]:
    require_admitted_git()
    origin = _origin(tmp_path)
    published = asyncio.run(acquire_source(_file_source(origin.path), home=tmp_path / "home"))
    assert published.default_revision == origin.second
    store = published.git_dir
    listing = _store_git(store, "rev-list", "--objects", "--missing=print", "--all")
    assert [line for line in listing.splitlines() if line.startswith("?")] == []
    assert origin.history_blob in listing
    assert "promisor" not in (store / "config").read_text(encoding="utf-8")
    assert not list((store / "objects" / "pack").glob("*.promisor"))
    return origin, published


def _ok(response: Response) -> Response:
    assert response.status_code == 200, response.text
    return response


async def _read_every_family(store: Path, origin: _Origin) -> None:
    subject = await git_revision_subject(
        target=repository_store_target(git_dir=store),
        commit_oid=origin.first,
        store_identity="full-clone",
    )
    try:
        assert await subject.tree_source.read_blob(_NOTE) == b"first draft\n"
        tally = await subject.tree_source.tree_tally()
        assert tally is not None
        assert tally.total_files == 2
        assert tally.total_size == len(b"first draft\n") + len(b"kept\n")
    finally:
        await subject.aclose()

    async with pinned_client(store, origin.first) as (client, _subject):
        note = _ok(await client.get("/api/file", params={"path": _NOTE.to_wire()}))
        assert note.json()["content"] == "first draft\n"
        assert _ok(await client.get("/raw", params={"path": _NOTE.to_wire()})).content == (
            b"first draft\n"
        )
        kept = _ok(await client.get("/api/file", params={"path": _KEEP.to_wire()}))
        assert kept.json()["content"] == "kept\n"
        assert origin.first in _ok(await client.get("/api/git/log")).text
        _ok(await client.get(f"/api/git/commit/{origin.first}"))

    async with pinned_client(store, origin.second) as (client, _subject):
        current = _ok(await client.get("/api/file", params={"path": _NOTE.to_wire()}))
        assert current.json()["content"] == "second draft\n"
        detail = _ok(await client.get(f"/api/git/commit/{origin.second}")).json()
        assert detail["stats"]["additions"] == 1
        assert detail["stats"]["deletions"] == 1
        _ok(await client.get("/api/plugin/diff/comparison", params={"revision": origin.second}))


def test_a_warm_open_reuses_the_store_without_running_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, published = _cold_acquire(tmp_path)
    before = _objects(published.git_dir)
    shutil.rmtree(origin.path)

    async def no_git(*_args: object, **_kwargs: object) -> bytes:
        raise AssertionError("a cache hit runs no Git")

    monkeypatch.setattr(acquire_module, "_run", no_git)
    again = asyncio.run(acquire_source(_file_source(origin.path), home=tmp_path / "home"))
    assert again == published
    assert _objects(published.git_dir) == before


@pytest.mark.parametrize("origin_state", ["online", "offline"])
def test_every_read_family_answers_from_the_store_alone(
    tmp_path: Path, origin_state: Literal["online", "offline"]
) -> None:
    origin, published = _cold_acquire(tmp_path)
    if origin_state == "offline":
        shutil.rmtree(origin.path)
    before = _objects(published.git_dir)

    async def run() -> None:
        async with asyncio.timeout(_HANG_GUARD_S):
            await _read_every_family(published.git_dir, origin)

    asyncio.run(run())
    assert _objects(published.git_dir) == before, "a read changed the store's objects"
