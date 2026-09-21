"""Typed failure envelopes for a pinned Git tree, through the ASGI app."""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

import pytest

from metabrowser.git.process import (
    GitCommandError,
    GitError,
    GitOutputTooLargeError,
    GitTimeoutError,
)
from metabrowser.git.tree_source import (
    GitBatchProtocolError,
    GitPath,
    GitTreeEntry,
    GitTreeSource,
)
from tests.git_pin_harness import fast_import_store, git_env, pinned_client

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git executable is required",
)

_FILES = {
    b"README.md": b"# readme\n",
    b"docs/guide.md": b"guide\n",
    b"docs/deep/note.md": b"note\n",
}
_README = GitPath.from_segments(b"README.md").to_wire()
_PIN_ROUTES = (
    "/api/tree",
    f"/api/file?path={_README}",
    f"/raw?path={_README}",
    "/api/rollup",
    "/api/catalog",
    "/api/index/progress",
    "/api/index/meta",
    "/api/capabilities",
    f"/api/kpress/render?path={_README}&view=document",
)


def _delete_tree_object(store: Path, tmp_path: Path, revision: str) -> str:
    """Explode the packs to loose objects, then remove one tree object."""

    env = git_env(tmp_path)

    def git(*args: str, data: bytes | None = None) -> str:
        done = subprocess.run(
            ["git", "--git-dir", str(store), *args],
            check=True,
            capture_output=True,
            input=data,
            env=env,
        )
        return done.stdout.decode().strip()

    oid = git("rev-parse", revision)
    for pack in list((store / "objects" / "pack").glob("*.pack")):
        moved = tmp_path / pack.name
        pack.rename(moved)
        for sibling in (store / "objects" / "pack").glob(pack.stem + ".*"):
            sibling.unlink()
        git("unpack-objects", "-q", data=moved.read_bytes())
    (store / "objects" / oid[:2] / oid[2:]).unlink()
    return oid


def test_git_timeout_error_has_a_path_free_message() -> None:
    assert str(GitTimeoutError()) == "git command timed out"


def test_missing_tree_object_is_object_unavailable_on_every_index_route(tmp_path: Path) -> None:
    store, commit = fast_import_store(tmp_path, _FILES)
    missing = _delete_tree_object(store, tmp_path, "refs/heads/main:docs")
    docs = GitPath.from_segments(b"docs").to_wire()

    async def run() -> None:
        async with pinned_client(store, commit) as (client, _subject):
            for url in (
                "/api/tree",
                "/api/tree?depth=1",
                f"/api/tree?path={docs}",
                f"/api/file?path={docs}",
                "/api/rollup",
                "/api/catalog",
                "/api/index/progress",
                "/api/index/meta",
                "/api/capabilities",
            ):
                response = await client.get(url)
                assert response.status_code == 404, (url, response.text)
                body = response.json()
                assert body["code"] == "object_unavailable", url
                assert body["oid"] == missing, url
                assert str(store) not in response.text

    asyncio.run(run())


@pytest.mark.parametrize(
    ("failure", "status", "code"),
    [
        (GitTimeoutError(), 504, "git_timeout"),
        (
            GitCommandError(["ls-tree", "/private/store"], 128, "fatal: /private/store"),
            500,
            "git_failed",
        ),
        (GitBatchProtocolError("cat-file actor framing failed"), 500, "git_failed"),
        (GitOutputTooLargeError("git ls-tree produced too much"), 500, "git_failed"),
    ],
)
def test_git_failures_are_typed_json_on_every_pin_route(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: GitError,
    status: int,
    code: str,
) -> None:
    store, commit = fast_import_store(tmp_path, _FILES)

    async def failing(self: GitTreeSource, *_args: object, **_kwargs: object) -> GitTreeEntry:
        raise failure

    async def run() -> None:
        async with pinned_client(store, commit) as (client, _subject):
            monkeypatch.setattr(GitTreeSource, "resolve_path", failing)
            monkeypatch.setattr(GitTreeSource, "blob_index", failing)
            for url in _PIN_ROUTES:
                response = await client.get(url)
                assert response.status_code == status, (url, response.text)
                assert response.headers["content-type"].startswith("application/json"), url
                body = response.json()
                assert body["code"] == code, url
                assert body["error"]
                assert "/private/store" not in response.text

    asyncio.run(run())
