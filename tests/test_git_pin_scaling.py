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

from metabrowser.git import content_routes as routes_module
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


def _count_per_blob_work(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every whole-index scan derives one extension per blob, so count those."""

    seen: list[str] = []
    real_derive_ext = routes_module.derive_ext

    def counting_derive_ext(name: str) -> str:
        seen.append(name)
        return real_derive_ext(name)

    monkeypatch.setattr(routes_module, "derive_ext", counting_derive_ext)
    return seen


def test_whole_index_facts_are_derived_once_per_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    blobs = 400
    files = {
        f"pkg{index % 8}/sub{index % 3}/mod_{index:04d}.{'py' if index % 2 else 'md'}".encode(): (
            b"x" * (index % 7 + 1)
        )
        for index in range(blobs)
    }
    store, commit = fast_import_store(tmp_path, files)
    seen = _count_per_blob_work(monkeypatch)
    urls = (
        "/api/tree?depth=1",
        "/api/tree?depth=2&types=.py",
        "/api/tree?depth=2&min_size=4",
        "/api/index/progress",
        "/api/index/meta",
        "/api/capabilities",
        "/api/rollup",
        "/api/catalog",
    )

    async def run() -> None:
        async with pinned_client(store, commit) as (client, _subject):
            first: dict[str, Any] = {}
            for url in urls:
                response = await client.get(url)
                assert response.status_code == 200, url
                first[url] = response.json()
            assert first["/api/tree?depth=2&types=.py"]["filtered"]["files"] == blobs // 2
            assert first["/api/index/meta"]["indexed_files"] == blobs
            assert len(first["/api/catalog"]["files"]) == blobs
            for url in urls:
                seen.clear()
                response = await client.get(url)
                assert response.json() == first[url], url
                # A pin is immutable: a repeat may touch the nodes it lists,
                # never every blob of the index again.
                assert len(seen) < blobs // 4, (url, len(seen))

    asyncio.run(run())


def test_nav_tree_stops_nesting_at_its_node_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = {
        f"d{outer}/e{inner}/f{leaf}.txt".encode(): b"x"
        for outer in range(6)
        for inner in range(6)
        for leaf in range(6)
    }
    store, commit = fast_import_store(tmp_path, files)
    budget = 40
    monkeypatch.setattr(routes_module, "GIT_NAV_TREE_MAX_NODES", budget)

    def walk(nodes: list[dict[str, Any]]) -> tuple[int, int]:
        total = lazy = 0
        for node in nodes:
            total += 1
            children = node.get("children")
            if node["type"] == "dir" and children is None:
                assert node["has_children"] is True
                lazy += 1
            elif children:
                nested_total, nested_lazy = walk(children)
                total += nested_total
                lazy += nested_lazy
        return total, lazy

    async def run() -> None:
        async with pinned_client(store, commit) as (client, _subject):
            response = await client.get("/api/tree?depth=20")
            assert response.status_code == 200
            tree = response.json()["tree"]
            # Every direct child is present; nesting stops once the budget is spent.
            assert [node["name"] for node in tree] == [f"d{outer}" for outer in range(6)]
            total, lazy = walk(tree)
            assert total <= budget
            assert lazy > 0
            # Totals come from the index, so a lazy directory is not dimmed as empty.
            assert all(node["total_files"] == 36 for node in tree)

    asyncio.run(run())


def test_derived_facts_build_once_per_key_and_stay_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, commit = fast_import_store(tmp_path, {b"a.txt": b"a\n"})
    monkeypatch.setattr(tree_module, "MAX_DERIVED_FACTS", 3)
    builds: list[int] = []

    def build(key: int) -> int:
        builds.append(key)
        return key * 10

    async def run() -> None:
        subject = await git_revision_subject(
            target=repository_store_target(git_dir=store),
            commit_oid=commit,
            store_identity="scaling-fixture",
        )
        try:
            source = subject.tree_source
            racing = await asyncio.gather(*(source.derived(1, lambda: build(1)) for _ in range(5)))
            assert racing == [10] * 5
            assert builds == [1]
            for key in (2, 3, 4):
                assert await source.derived(key, lambda key=key: build(key)) == key * 10
            # Key 1 was the least recently used of four, so only it is rebuilt.
            assert await source.derived(4, lambda: build(4)) == 40
            assert await source.derived(1, lambda: build(1)) == 10
            assert builds == [1, 2, 3, 4, 1]

            def fail() -> int:
                raise RuntimeError("not remembered")

            with pytest.raises(RuntimeError):
                await source.derived("bad", fail)
            assert await source.derived("bad", lambda: 7) == 7
        finally:
            await subject.aclose()

    asyncio.run(run())
