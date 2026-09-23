"""Algorithmic bounds for a pinned Git tree: counted work, never wall clock."""

from __future__ import annotations

import asyncio
import shutil
from collections.abc import Sequence
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

import pytest

from metabrowser.git import content_routes as routes_module
from metabrowser.git import tree_source as tree_module
from metabrowser.git.process import repository_store_target
from metabrowser.git.tree_source import GitPath, git_revision_subject
from tests.git_pin_harness import fast_import_store, pinned_client

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git executable is required",
)


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


# Growth-rate checks. A single width can only compare against a threshold
# someone chose; two widths compare against the algorithm's own growth. Linear
# work ``a*N + b`` with ``b >= 0`` satisfies ``W(4N) <= 4*W(N)``. Rebuilding or
# scanning every sibling per child makes ``W(4N)`` about ``16*W(N)``. The slack
# absorbs a per-request constant such as ``b < 0`` and nothing more: at these
# widths a quadratic misses the bound by hundreds.
_SCALING_WIDTH = 16
_SCALING_SLACK = 8


@dataclass(frozen=True, slots=True)
class _Work:
    """Counted work for one request or phase. Each field may grow at most linearly."""

    reparents: int
    path_compares: int
    tree_loads: int
    tree_reads: int
    ls_tree_spawns: int
    nav_nodes: int


class _WorkMeter:
    """Counts what a nested listing or lookup does, never how long it takes.

    ``reparents`` counts entries rebuilt under another parent path: the work
    that went quadratic when a cache hit rebuilt every sibling for each child.
    ``path_compares`` counts ``GitPath`` equality checks, so a lookup that scans
    siblings instead of indexing them shows even when it rebuilds nothing.
    ``tree_loads`` counts tree lookups by OID, ``tree_reads`` the actor round
    trips that read a tree object, and ``nav_nodes`` the SPA nodes the route
    builds.
    """

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._counters = _count_tree_work(monkeypatch)
        self._compares = self._loads = self._reads = self._nodes = 0
        real_eq = GitPath.__eq__
        real_load = tree_module.GitTreeSource._load_tree
        real_read = tree_module._BatchObjectReader.read_tree
        real_node = routes_module._nav_tree_node

        def counting_eq(path: GitPath, other: object) -> bool:
            self._compares += 1
            return real_eq(path, other)

        async def counting_load(source: Any, tree_oid: str, *, parent_path: GitPath) -> Any:
            self._loads += 1
            return await real_load(source, tree_oid, parent_path=parent_path)

        async def counting_read(reader: Any, oid: str) -> bytes:
            self._reads += 1
            return await real_read(reader, oid)

        def counting_node(entry: Any, **kwargs: Any) -> dict[str, Any]:
            self._nodes += 1
            return real_node(entry, **kwargs)

        monkeypatch.setattr(GitPath, "__eq__", counting_eq)
        monkeypatch.setattr(tree_module.GitTreeSource, "_load_tree", counting_load)
        monkeypatch.setattr(tree_module._BatchObjectReader, "read_tree", counting_read)
        monkeypatch.setattr(routes_module, "_nav_tree_node", counting_node)

    def reset(self) -> None:
        self._counters.reset()
        self._compares = self._loads = self._reads = self._nodes = 0

    def snapshot(self) -> _Work:
        return _Work(
            reparents=self._counters.reparents,
            path_compares=self._compares,
            tree_loads=self._loads,
            tree_reads=self._reads,
            ls_tree_spawns=self._counters.ls_tree_spawns(),
            nav_nodes=self._nodes,
        )


def _wide_store(tmp_path: Path, width: int) -> tuple[Path, str]:
    """``same/`` holds *width* subtrees sharing one tree OID; ``diff/`` holds *width* distinct ones.

    ``other/`` holds the same one-file tree as every ``same/`` child. Listing it
    first records that shared tree under ``other/``, so every ``same/`` child is
    served from a cache entry recorded under a different path.
    """

    files: dict[bytes, bytes] = {b"other/f.txt": b"shared\n"}
    for index in range(width):
        files[f"same/d{index:04d}/f.txt".encode()] = b"shared\n"
        files[f"diff/d{index:04d}/f.txt".encode()] = f"distinct {index}\n".encode()
    root = tmp_path / f"width-{width}"
    root.mkdir()
    return fast_import_store(root, files)


def _measure_wide_tree(tmp_path: Path, meter: _WorkMeter, width: int) -> dict[str, _Work]:
    store, commit = _wide_store(tmp_path, width)
    same = GitPath.from_segments(b"same")
    diff = GitPath.from_segments(b"diff")
    other = GitPath.from_segments(b"other")
    requests = (
        ("same cold", f"/api/tree?path={same.to_wire()}&depth=2"),
        ("same warm", f"/api/tree?path={same.to_wire()}&depth=2"),
        ("diff cold", f"/api/tree?path={diff.to_wire()}&depth=2"),
        ("diff warm", f"/api/tree?path={diff.to_wire()}&depth=2"),
        ("root", "/api/tree?depth=3"),
    )

    async def run() -> dict[str, _Work]:
        work: dict[str, _Work] = {}
        async with pinned_client(store, commit) as (client, subject):
            seeded = await client.get(f"/api/tree?path={other.to_wire()}&depth=1")
            assert seeded.status_code == 200
            for label, url in requests:
                meter.reset()
                response = await client.get(url)
                work[label] = meter.snapshot()
                assert response.status_code == 200, (label, response.text)
                if label.startswith(("same", "diff")):
                    nodes = response.json()["tree"]
                    assert len(nodes) == width, label
                    assert all(len(node["children"]) == 1 for node in nodes), label
            meter.reset()
            for index in range(width):
                path = same.child(f"d{index:04d}".encode()).child(b"f.txt")
                entry = await subject.tree_source.resolve_path(path)
                assert entry is not None and entry.path == path and entry.is_blob
            work["lookup warm"] = meter.snapshot()
        return work

    return asyncio.run(run())


def _growth_violations(
    small: dict[str, _Work], large: dict[str, _Work], *, width: int
) -> list[str]:
    violations: list[str] = []
    for phase, narrow in small.items():
        wide = large[phase]
        for metric in fields(_Work):
            at_n = getattr(narrow, metric.name)
            at_4n = getattr(wide, metric.name)
            if at_4n > 4 * at_n + _SCALING_SLACK:
                violations.append(
                    f"{phase}: {metric.name} grew from {at_n} at width {width} "
                    f"to {at_4n} at width {4 * width}"
                )
    return violations


def test_nested_listing_and_lookup_work_grow_linearly_with_width(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Counted work at width 4N stays within 4x the work at N; a quadratic is 16x."""

    width = _SCALING_WIDTH
    meter = _WorkMeter(monkeypatch)
    small = _measure_wide_tree(tmp_path, meter, width)
    large = _measure_wide_tree(tmp_path, meter, 4 * width)

    violations = _growth_violations(small, large, width=width)
    assert not violations, "\n".join(violations)
    # Non-vacuous: each counter saw the work it exists to bound, once per child.
    for measured, scale in ((small, width), (large, 4 * width)):
        assert measured["same warm"].reparents >= scale
        assert measured["lookup warm"].reparents >= scale
        assert measured["lookup warm"].path_compares >= scale
        assert measured["diff cold"].tree_reads >= scale
        assert measured["diff warm"].nav_nodes >= 2 * scale
        # A child listing reads one tree object; it never spawns ls-tree.
        assert all(work.ls_tree_spawns <= 1 for work in measured.values())
        assert measured["same warm"].tree_reads == measured["diff warm"].tree_reads == 0


def _index_store(tmp_path: Path, blobs: int) -> tuple[Path, str]:
    """*blobs* files spread over eight fixed top-level directories."""

    files = {
        f"pkg{index % 8}/sub{index % 3}/mod_{index:05d}.{'py' if index % 2 else 'md'}".encode(): (
            b"x" * (index % 7 + 1)
        )
        for index in range(blobs)
    }
    root = tmp_path / f"blobs-{blobs}"
    root.mkdir()
    return fast_import_store(root, files)


def _per_blob_work(tmp_path: Path, seen: list[str], blobs: int) -> tuple[int, int]:
    """(cold, warm) extension derivations over the chrome and listing routes."""

    store, commit = _index_store(tmp_path, blobs)
    urls = (
        "/api/tree?depth=1",
        "/api/tree?depth=1&types=.py",
        "/api/index/meta",
        "/api/rollup",
        "/api/catalog",
    )

    async def run() -> tuple[int, int]:
        async with pinned_client(store, commit) as (client, _subject):
            seen.clear()
            for url in urls:
                assert (await client.get(url)).status_code == 200, url
            cold = len(seen)
            seen.clear()
            for url in urls:
                assert (await client.get(url)).status_code == 200, url
            return cold, len(seen)

    return asyncio.run(run())


def test_repeated_requests_do_not_grow_with_the_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A warm repeat costs what it lists, not what the pin holds.

    The first pass derives whole-index facts, which is linear in blobs. The
    repeat answers from the memo, so its per-blob work is the same for a tree
    four times larger whose listing is the same eight directories.
    """

    seen = _count_per_blob_work(monkeypatch)
    blobs = 200
    cold_small, warm_small = _per_blob_work(tmp_path, seen, blobs)
    cold_large, warm_large = _per_blob_work(tmp_path, seen, 4 * blobs)

    assert cold_small >= blobs
    assert cold_large <= 4 * cold_small + _SCALING_SLACK
    assert warm_large <= warm_small + _SCALING_SLACK, (warm_small, warm_large)
    assert warm_large < blobs // 4


def _deep_store(tmp_path: Path, fanout: int) -> tuple[Path, str]:
    """A three-level tree of *fanout* entries per level, every tree object distinct.

    Distinct leaf bodies keep identical subtrees from sharing one OID, so the
    tree cache cannot be what bounds the work; only the node budget can.
    """

    files = {
        f"d{outer:02d}/e{inner:02d}/f{leaf:02d}.txt".encode(): f"{outer} {inner} {leaf}\n".encode()
        for outer in range(fanout)
        for inner in range(fanout)
        for leaf in range(fanout)
    }
    root = tmp_path / f"fanout-{fanout}"
    root.mkdir()
    return fast_import_store(root, files)


def _budgeted_listing(tmp_path: Path, meter: _WorkMeter, fanout: int) -> tuple[_Work, int]:
    store, commit = _deep_store(tmp_path, fanout)

    async def run() -> tuple[_Work, int]:
        async with pinned_client(store, commit) as (client, _subject):
            meter.reset()
            response = await client.get("/api/tree?depth=20")
            assert response.status_code == 200
            return meter.snapshot(), len(response.json()["tree"])

    return asyncio.run(run())


def test_deep_listing_work_is_bounded_by_the_node_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Past the budget, a deeper or wider tree adds no nested listing work.

    Growing the fanout from 4 to 8 multiplies the tree by eight. The nodes the
    route builds and the trees it lists must stay under the budget, with only
    the top level, which is always listed whole, growing with the fanout.
    """

    budget = 40
    monkeypatch.setattr(routes_module, "GIT_NAV_TREE_MAX_NODES", budget)
    meter = _WorkMeter(monkeypatch)
    small, small_top = _budgeted_listing(tmp_path, meter, 4)
    large, large_top = _budgeted_listing(tmp_path, meter, 8)

    assert (small_top, large_top) == (4, 8)
    for work, top in ((small, small_top), (large, large_top)):
        assert work.nav_nodes <= budget + top, work
        assert work.tree_loads <= budget + top + 1, work
        assert work.tree_reads <= budget + top + 1, work
    # The larger tree hit the budget; without it, nesting would visit all 8**3 leaves.
    assert large.nav_nodes < 8**3
