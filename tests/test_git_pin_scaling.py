"""Algorithmic bounds for a pinned Git tree: counted work, never wall clock."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from collections.abc import AsyncGenerator, Mapping, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from httpx2 import ASGITransport, AsyncClient

from metabrowser.git import tree_source as tree_module
from metabrowser.git.process import repository_store_target
from metabrowser.git.tree_source import GitPath, GitRevisionSubject, git_revision_subject
from metabrowser.server import app
from metabrowser.source import attach_subject, reset_source_session

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git executable is required",
)


def _git_env(root: Path) -> dict[str, str]:
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env.update(
        {
            "GIT_CONFIG_GLOBAL": str(root / ".gitconfig-absent"),
            "GIT_CONFIG_SYSTEM": str(root / ".gitconfig-absent"),
        }
    )
    return env


def fast_import_store(tmp_path: Path, files: Mapping[bytes, bytes]) -> tuple[Path, str]:
    """A bare store with one commit. Names are plain ASCII, so no quoting."""

    store = tmp_path / "store.git"
    env = _git_env(tmp_path)
    subprocess.run(
        ["git", "init", "-q", "--bare", "--template=", "-b", "main", str(store)],
        check=True,
        capture_output=True,
        env=env,
    )
    stream = bytearray(
        b"commit refs/heads/main\n"
        b"committer Scale <scale@example.invalid> 1767225600 +0000\n"
        b"data 6\nscale\n\n"
    )
    for name, body in files.items():
        stream += b"M 100644 inline " + name + b"\ndata " + str(len(body)).encode() + b"\n"
        stream += body + b"\n"
    stream += b"\ndone\n"
    subprocess.run(
        ["git", "--git-dir", str(store), "fast-import", "--quiet", "--done"],
        check=True,
        capture_output=True,
        input=bytes(stream),
        env=env,
    )
    commit = subprocess.run(
        ["git", "--git-dir", str(store), "rev-parse", "refs/heads/main"],
        check=True,
        capture_output=True,
        env=env,
    ).stdout
    return store, commit.decode().strip()


@asynccontextmanager
async def pinned_client(
    store: Path, commit: str
) -> AsyncGenerator[tuple[AsyncClient, GitRevisionSubject], None]:
    subject = await git_revision_subject(
        target=repository_store_target(git_dir=store),
        commit_oid=commit,
        store_identity="scaling-fixture",
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


class _Counters:
    def __init__(self) -> None:
        self.reparents = 0
        self.spawns: list[tuple[str, ...]] = []

    def reset(self) -> None:
        self.reparents = 0
        self.spawns.clear()

    def ls_tree_spawns(self) -> int:
        return sum(1 for args in self.spawns if "ls-tree" in args)


def _count_tree_work(monkeypatch: pytest.MonkeyPatch) -> _Counters:
    counters = _Counters()
    real_replace = tree_module.replace
    real_run_git = tree_module.run_git

    def counting_replace(obj: Any, /, **changes: Any) -> Any:
        if "path" in changes:
            counters.reparents += 1
        return real_replace(obj, **changes)

    async def counting_run_git(args: Sequence[str], **kwargs: Any) -> bytes:
        counters.spawns.append(tuple(args))
        return await real_run_git(args, **kwargs)

    monkeypatch.setattr(tree_module, "replace", counting_replace)
    monkeypatch.setattr(tree_module, "run_git", counting_run_git)
    return counters


def test_wide_nested_listing_is_linear_in_directory_width(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A nested listing of D subdirectories must not do D*D work or D spawns.

    ``same/`` holds D subdirectories sharing ONE tree OID, so every child
    listing is served from a cache entry recorded under a sibling's path and
    has to be reparented. ``diff/`` holds D distinct trees, so a cold listing
    has D trees to read.
    """

    width = 48
    files: dict[bytes, bytes] = {}
    for index in range(width):
        files[f"same/d{index:03d}/f.txt".encode()] = b"shared\n"
        files[f"diff/d{index:03d}/f.txt".encode()] = f"distinct {index}\n".encode()
    store, commit = fast_import_store(tmp_path, files)
    counters = _count_tree_work(monkeypatch)

    async def run() -> None:
        async with pinned_client(store, commit) as (client, _subject):
            for name in (b"same", b"diff"):
                wire = GitPath.from_segments(name).to_wire()
                counters.reset()
                cold = await client.get(f"/api/tree?path={wire}&depth=2")
                assert cold.status_code == 200
                # One recursive index walk, not one spawn per child tree.
                assert counters.ls_tree_spawns() <= 2, counters.spawns
                assert counters.reparents <= 4 * width

                counters.reset()
                warm = await client.get(f"/api/tree?path={wire}&depth=2")
                assert warm.status_code == 200
                assert warm.json() == cold.json()
                assert counters.ls_tree_spawns() == 0
                # Unfixed: every child re-listed and rebuilt all D siblings.
                assert counters.reparents <= 4 * width, counters.reparents

                nodes = warm.json()["tree"]
                assert len(nodes) == width
                for index, node in enumerate(nodes):
                    child = GitPath.from_segments(name, f"d{index:03d}".encode())
                    assert node["path"] == child.to_wire()
                    # A shared tree OID still lists under EACH parent path.
                    assert [leaf["path"] for leaf in node["children"]] == [
                        child.child(b"f.txt").to_wire()
                    ]

    asyncio.run(run())


def test_warm_path_resolution_reparents_only_the_hit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    width = 64
    files = {f"wide/d{index:03d}/f.txt".encode(): b"shared\n" for index in range(width)}
    files[b"other/f.txt"] = b"shared\n"
    store, commit = fast_import_store(tmp_path, files)
    counters = _count_tree_work(monkeypatch)

    async def run() -> None:
        subject = await git_revision_subject(
            target=repository_store_target(git_dir=store),
            commit_oid=commit,
            store_identity="scaling-fixture",
        )
        try:
            source = subject.tree_source
            await source.list_tree(GitPath.from_segments(b"wide"))
            await source.list_tree(GitPath.from_segments(b"other"))
            counters.reset()
            for index in range(width):
                path = GitPath.from_segments(b"wide", f"d{index:03d}".encode(), b"f.txt")
                entry = await source.resolve_path(path)
                assert entry is not None and entry.path == path and entry.is_blob
            assert counters.ls_tree_spawns() == 0
            # The shared ``{f.txt}`` tree was cached under ``other/``: one
            # reparented hit per lookup, never one per sibling.
            assert counters.reparents <= width
        finally:
            await subject.aclose()

    asyncio.run(run())


def test_raw_tree_object_parser_refuses_malformed_records() -> None:
    oid = "ab" * 20
    raw_oid = bytes.fromhex(oid)
    good = b"100644 b.txt\x00" + raw_oid + b"40000 a\x00" + raw_oid + b"160000 dep\x00" + raw_oid
    entries = tree_module._parse_tree_object(good, parent=GitPath.from_segments(b"p"), oid=oid)
    assert [(entry.path.segments, entry.mode, entry.kind, entry.oid) for entry in entries] == [
        ((b"p", b"a"), "040000", "tree", oid),
        ((b"p", b"b.txt"), "100644", "blob", oid),
        ((b"p", b"dep"), "160000", "commit", oid),
    ]
    for bad in (
        good[:-1],
        b"100644 no-terminator",
        b"10x644 b.txt\x00" + raw_oid,
        b"100644 a/b\x00" + raw_oid,
    ):
        with pytest.raises(tree_module.GitBatchProtocolError):
            tree_module._parse_tree_object(bad, parent=GitPath.root(), oid=oid)
