"""Acceptance: reading a not-yet-converged blob, with the origin online and offline.

The open-repository plan decided ("Blobless acquisition and the offline
guarantee") that every store read runs with ``GIT_NO_LAZY_FETCH=1``. A
blob the store does not hold yet is then a typed ``object_unavailable`` in
bounded time, never a request that waits on a promisor remote, and the outcome
is the same whether that remote is reachable or not.

The store here is built the way production builds one: a blobless acquisition
of a ``file://`` origin that honors filters, published as ``converging`` with
only the default revision's blobs prefetched. The blob read is one the prefetch
skipped, the older revision of a changed file. It is read through each family of
store reads: the pooled batch reader, file and raw routes, history, commit
detail, and the diff comparison.

*Online* keeps the origin in place, and a control on a copy of the store proves
that Git without the policy fetches that blob from it. *Offline* deletes the
origin, and the same control proves no fetch can succeed. Both must answer with
the same typed result and leave every file under the store's ``objects/``
unchanged.

Nothing is patched: the acquisition floor must admit the Git on ``PATH`` (see
``tests/admitted_git.py``). CI runs these on the lowest admitted release and on
the newest patched one, so the reading of Git's source behind that floor is
checked at runtime.
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

from metabrowser.cache.acquire import acquire_file_source
from metabrowser.cache.atomic import read_record
from metabrowser.cache.paths import store_record
from metabrowser.cache.records import REPOSITORY_STORE_STATE_CONTRACT_ID, RepositoryStoreState
from metabrowser.cache.urls import GitSource, classify_root_argument
from metabrowser.git.process import repository_store_target
from metabrowser.git.tree_source import GitObjectUnavailableError, GitPath, git_revision_subject
from tests.admitted_git import require_admitted_git
from tests.git_pin_harness import pinned_client

pytestmark = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")

# A hang guard, not a performance claim. Every read below answers in tens of
# milliseconds; a lazy fetch that stalled would run into the 15 s request deadline.
_HANG_GUARD_S = 10.0
_OLD_PATH = GitPath.from_segments(b"notes", b"old.txt")
_KEEP_PATH = GitPath.from_segments(b"keep.txt")


@dataclass(frozen=True, slots=True)
class _ConvergingStore:
    origin: Path
    store: Path
    first: str
    second: str
    missing_oid: str


def _git_env() -> dict[str, str]:
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env.update(
        {
            "GIT_AUTHOR_NAME": "Lazy Fetch",
            "GIT_AUTHOR_EMAIL": "lazy@example.invalid",
            "GIT_COMMITTER_NAME": "Lazy Fetch",
            "GIT_COMMITTER_EMAIL": "lazy@example.invalid",
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


def _store_git(
    store: Path, *args: str, lazy_fetch: bool = False
) -> subprocess.CompletedProcess[bytes]:
    """Run Git on *store*; lazy fetch stays off unless a control asks for it."""

    env = _git_env()
    if not lazy_fetch:
        env["GIT_NO_LAZY_FETCH"] = "1"
    return subprocess.run(
        ["git", "--git-dir", str(store), *args],
        check=False,
        capture_output=True,
        env=env,
        timeout=60,
    )


def _present(store: Path, oid: str) -> bool:
    return _store_git(store, "cat-file", "-e", oid).returncode == 0


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


def _converging_store(tmp_path: Path) -> _ConvergingStore:
    """A published blobless store whose older revision's blob was never fetched."""

    require_admitted_git()
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-q", "--initial-branch=topic")
    (work / "notes").mkdir()
    (work / "notes" / "old.txt").write_text("first draft\n", encoding="utf-8")
    (work / "keep.txt").write_text("kept\n", encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "-c", "commit.gpgsign=false", "commit", "-qm", "first")
    first = _git(work, "rev-parse", "HEAD")
    (work / "notes" / "old.txt").write_text("second draft\n", encoding="utf-8")
    _git(work, "-c", "commit.gpgsign=false", "commit", "-qam", "second")
    second = _git(work, "rev-parse", "HEAD")
    missing_oid = _git(work, "rev-parse", f"{first}:notes/old.txt")
    current_oid = _git(work, "rev-parse", f"{second}:notes/old.txt")

    origin = tmp_path / "origin.git"
    _git(tmp_path, "clone", "-q", "--bare", "--template=", "--", str(work), str(origin))
    _git(origin, "config", "uploadpack.allowFilter", "true")
    _git(origin, "config", "uploadpack.allowAnySHA1InWant", "true")

    home = tmp_path / "home"
    published = asyncio.run(acquire_file_source(_file_source(origin), home=home))
    assert published.strategy == "blobless"
    assert published.default_revision == second
    state = read_record(
        home, store_record(published.store_key, "state.yml"), REPOSITORY_STORE_STATE_CONTRACT_ID
    )
    assert isinstance(state, RepositoryStoreState)
    assert state.object_state == "converging"
    store = published.git_dir
    assert _present(store, current_oid), "the default revision's blobs are prefetched"
    assert not _present(store, missing_oid), "an older revision's blob is not"
    return _ConvergingStore(
        origin=origin, store=store, first=first, second=second, missing_oid=missing_oid
    )


def _lazy_fetch_would_succeed(fixture: _ConvergingStore, scratch: Path) -> bool:
    """Whether Git with its default policy fetches the blob into a copy of the store."""

    copy = scratch / "control.git"
    shutil.copytree(fixture.store, copy, symlinks=True)
    result = _store_git(
        copy,
        "-c",
        "protocol.file.allow=always",
        "cat-file",
        "blob",
        fixture.missing_oid,
        lazy_fetch=True,
    )
    if result.returncode != 0:
        return False
    assert result.stdout == b"first draft\n"
    assert _objects(copy) != _objects(fixture.store), "the control fetch wrote no object"
    return True


def _assert_unavailable(response: Response, oid: str, *, error_key: str = "code") -> None:
    assert response.status_code == 404, response.text
    body = response.json()
    assert body[error_key] == "object_unavailable", body
    assert body["oid"] == oid, body
    assert response.headers.get("cache-control") == "no-store"


async def _read_every_family(fixture: _ConvergingStore) -> None:
    missing = fixture.missing_oid
    wire = _OLD_PATH.to_wire()

    # The older pin names the blob the prefetch skipped.
    subject = await git_revision_subject(
        target=repository_store_target(git_dir=fixture.store),
        commit_oid=fixture.first,
        store_identity="lazy-fetch",
    )
    try:
        with pytest.raises(GitObjectUnavailableError) as caught:
            await subject.tree_source.read_blob(_OLD_PATH)
        assert caught.value.oid == missing
        tally = await subject.tree_source.tree_tally()
        assert tally is not None
        assert tally.total_files == 2
        assert tally.total_size is None
    finally:
        await subject.aclose()

    async with pinned_client(fixture.store, fixture.first) as (client, _subject):
        _assert_unavailable(await client.get("/api/file", params={"path": wire}), missing)
        raw = await client.get("/raw", params={"path": wire})
        assert raw.status_code == 404
        kept = await client.get("/api/file", params={"path": _KEEP_PATH.to_wire()})
        assert kept.status_code == 200, kept.text
        assert kept.json()["content"] == "kept\n"
        history = await client.get("/api/git/log")
        assert history.status_code == 200, history.text
        assert fixture.first in history.text
        _assert_unavailable(await client.get(f"/api/git/commit/{fixture.first}"), missing)

    # The default pin is fully present, yet its own commit and diff read the old blob.
    async with pinned_client(fixture.store, fixture.second) as (client, _subject):
        current = await client.get("/api/file", params={"path": wire})
        assert current.status_code == 200, current.text
        assert current.json()["content"] == "second draft\n"
        _assert_unavailable(await client.get(f"/api/git/commit/{fixture.second}"), missing)
        comparison = await client.get(
            "/api/plugin/diff/comparison", params={"revision": fixture.second}
        )
        _assert_unavailable(comparison, missing, error_key="error")


@pytest.mark.parametrize("origin_state", ["online", "offline"])
def test_a_not_yet_converged_blob_is_unavailable_and_never_fetched(
    tmp_path: Path, origin_state: Literal["online", "offline"]
) -> None:
    fixture = _converging_store(tmp_path)
    if origin_state == "offline":
        shutil.rmtree(fixture.origin)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    assert _lazy_fetch_would_succeed(fixture, scratch) is (origin_state == "online")
    before = _objects(fixture.store)

    async def run() -> None:
        async with asyncio.timeout(_HANG_GUARD_S):
            await _read_every_family(fixture)

    asyncio.run(run())

    assert _objects(fixture.store) == before, "a read added objects to the store"
    assert not _present(fixture.store, fixture.missing_oid)
