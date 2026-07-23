"""InventoryIndex.rollup: subtree aggregation for the treemap.

Deterministic fixture trees exercise: full-subtree totals with the
gitignore-excluded variants, extension tallies with the remainder row,
dominant extensions, top-N children with the rest bucket, the depth
sentinel (children: null with full totals), pending state, and the
non-directory / unknown-path None result. A synthetic large index
records the query-cost budget (spec: <=150 ms at 100k entries).
"""

from __future__ import annotations

import asyncio
import subprocess
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from watchfiles import Change

from metabrowser.events import FsChange, FsEntry, FsUpsert
from metabrowser.inventory import InventoryIndex
from metabrowser.watch_backends import _emit_for_path
from metabrowser.wire_models import validate_rollup_node


def _build_index(root: Path, *, gitignore: str | None = None) -> InventoryIndex:
    if gitignore is not None:
        (root / ".gitignore").write_text(gitignore)
        subprocess.run(
            ["git", "init", "-q", str(root)],
            check=True,
            capture_output=True,
        )
    index = InventoryIndex()

    async def run() -> None:
        index.start(root)
        await index.wait_until_done(10)

    asyncio.run(run())
    return index


def test_rollup_totals_and_gitignore_variants(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x" * 100)
    (tmp_path / "src" / "b.py").write_text("x" * 50)
    (tmp_path / "src" / "notes.md").write_text("x" * 25)
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "out.bin").write_text("x" * 1000)
    index = _build_index(tmp_path, gitignore="build/\n")

    result = index.rollup("", depth=3, top=40, ext_top=12)
    assert result is not None
    node = result["node"]
    validate_rollup_node(node)
    assert node["total_files"] == 4
    assert node["total_size"] == 1175
    # build/ is gitignored: excluded from the unignored variants.
    assert node["unignored_files"] == 3
    assert node["unignored_size"] == 175
    assert node["state"] == "complete"

    by_name = {child["name"]: child for child in node["children"]}
    assert by_name["build"]["gitignored"] is True
    assert by_name["build"]["unignored_size"] == 0
    assert by_name["src"]["total_files"] == 3
    assert by_name["src"]["dominant_ext"] == ".py"

    tallies = {row[0]: row for row in result["ext_tallies"]}
    assert tallies[".bin"][1:] == [1, 1000, 0, 0]
    assert tallies[".py"][1:] == [2, 150, 2, 150]
    assert tallies[".md"][1:] == [1, 25, 1, 25]


def test_rollup_scoped_to_subtree_with_inherited_ignore(tmp_path: Path) -> None:
    ignored_dir = tmp_path / "vendor"
    ignored_dir.mkdir()
    (ignored_dir / "lib.js").write_text("x" * 10)
    nested = ignored_dir / "nested"
    nested.mkdir()
    (nested / "deep.js").write_text("x" * 5)
    index = _build_index(tmp_path, gitignore="vendor/\n")

    result = index.rollup("vendor", depth=2, top=10, ext_top=4)
    assert result is not None
    node = result["node"]
    validate_rollup_node(node)
    # Inside an ignored subtree everything counts as ignored.
    assert node["total_size"] == 15
    assert node["unignored_size"] == 0
    assert node["gitignored"] is True


def test_rollup_top_n_rest_bucket_and_ordering(tmp_path: Path) -> None:
    for i in range(6):
        (tmp_path / f"f{i}.txt").write_text("x" * (100 - i * 10))
    index = _build_index(tmp_path)

    result = index.rollup("", depth=1, top=3, ext_top=4)
    assert result is not None
    node = result["node"]
    validate_rollup_node(node)
    names = [child["name"] for child in node["children"]]
    assert names == ["f0.txt", "f1.txt", "f2.txt"]  # largest bytes first
    rest = node["rest"]
    assert rest["files"] == 3
    assert rest["size"] == 70 + 60 + 50
    assert node["total_files"] == 6


def test_rollup_depth_sentinel_keeps_full_totals(tmp_path: Path) -> None:
    deep = tmp_path / "a" / "b"
    deep.mkdir(parents=True)
    (deep / "leaf.txt").write_text("x" * 42)
    index = _build_index(tmp_path)

    result = index.rollup("", depth=1, top=10, ext_top=4)
    assert result is not None
    node = result["node"]
    validate_rollup_node(node)
    a_node = node["children"][0]
    assert a_node["name"] == "a"
    assert a_node["children"] is None  # past depth
    assert a_node["total_size"] == 42  # totals remain full-subtree


def test_rollup_none_for_files_and_unknown_paths(tmp_path: Path) -> None:
    (tmp_path / "file.txt").write_text("x")
    index = _build_index(tmp_path)
    assert index.rollup("file.txt", depth=2, top=10, ext_top=4) is None
    assert index.rollup("missing", depth=2, top=10, ext_top=4) is None


def test_rollup_reflects_real_fs_mutation_through_fs_change(tmp_path: Path) -> None:
    """Integration leg of the live-refresh chain: a real filesystem
    mutation, driven through the watcher's producer (`_emit_for_path`,
    the code `awatch` feeds), must emit `fs.change` upserts that reach
    root scope AND be visible in the next rollup. The client half —
    `fs.change` on SSE → `metabrowser:inventory-change` → watchRollup
    refetch — is covered by tests/dom/folder_plugin_behavior.js; this
    test pins the server half those events promise.
    """

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x" * 100)

    async def run() -> tuple[dict[str, Any], set[str], dict[str, Any], dict[str, Any]]:
        index = InventoryIndex()
        index.start(tmp_path)
        await index.wait_until_done(10)

        before = index.rollup("", depth=3, top=40, ext_top=12)
        assert before is not None
        sub_q = index.subscribe(max_queue=1024)

        target = tmp_path / "src" / "table.csv"
        target.write_bytes(b"c" * 500)
        await _emit_for_path(index, tmp_path, str(target), Change.added)

        upserts: set[str] = set()
        while not sub_q.empty():
            evt = sub_q.get_nowait()
            if isinstance(evt, FsChange):
                for op in evt.ops:
                    if isinstance(op, FsUpsert):
                        upserts.add(op.entry.path)

        after_add = index.rollup("", depth=3, top=40, ext_top=12)
        assert after_add is not None

        target.unlink()
        await _emit_for_path(index, tmp_path, str(target), Change.deleted)
        after_delete = index.rollup("", depth=3, top=40, ext_top=12)
        assert after_delete is not None
        return before, upserts, after_add, after_delete

    before, upserts, after_add, after_delete = asyncio.run(run())

    node = before["node"]
    validate_rollup_node(node)
    assert (node["total_files"], node["total_size"]) == (1, 100)

    # The upsert batch covers the file AND its bubbled ancestors: the
    # root upsert is what lands inside the client's root-depth-2 SSE
    # scope no matter how deep the change, so watchRollup always sees
    # a trigger.
    assert "src/table.csv" in upserts
    assert "src" in upserts
    assert "" in upserts

    node = after_add["node"]
    validate_rollup_node(node)
    assert (node["total_files"], node["total_size"]) == (2, 600)
    src_node = next(child for child in node["children"] if child["name"] == "src")
    assert src_node["total_size"] == 600
    tallies = {row[0]: row for row in after_add["ext_tallies"]}
    assert tallies[".csv"][1:] == [1, 500, 1, 500]

    node = after_delete["node"]
    validate_rollup_node(node)
    assert (node["total_files"], node["total_size"]) == (1, 100)
    assert ".csv" not in {row[0] for row in after_delete["ext_tallies"]}


def _count_nodes(node: dict[str, Any]) -> int:
    children = node.get("children") or []
    return 1 + sum(_count_nodes(child) for child in children)


def test_rollup_global_node_budget_on_adversarial_branching() -> None:
    """`top` bounds one directory, not the response: a balanced
    40x40x40 tree would emit ~65k nodes (~8 MB JSON) without the
    global budget. The budget caps emitted nodes and therefore payload
    bytes regardless of tree shape; cut children fold into rest
    buckets or children:null sentinels, and totals stay full-subtree.
    """

    import json

    from metabrowser.settings import ROLLUP_MAX_NODES

    index = InventoryIndex()
    entries = index._entries  # synthetic index setup, test-only
    mtime_ns = 1_700_000_000_000_000_000

    def _add_dir(path: str, parent: str, name: str) -> None:
        placeholder = FsEntry.for_observed_dir(path=path, parent=parent, name=name)
        entries[path] = replace(placeholder, total_files=1, total_size=1, newest_mtime_ns=mtime_ns)

    _add_dir("", "", "root")
    total_files = 0
    for a in range(40):
        top_dir = f"d{a:02d}"
        _add_dir(top_dir, "", top_dir)
        for b in range(40):
            mid_dir = f"{top_dir}/d{b:02d}"
            _add_dir(mid_dir, top_dir, f"d{b:02d}")
            for c in range(40):
                file_path = f"{mid_dir}/f{c:02d}.py"
                entries[file_path] = FsEntry.for_observed_file(
                    path=file_path,
                    parent=mid_dir,
                    name=f"f{c:02d}.py",
                    size=100 + c,
                    mtime_ns=mtime_ns,
                )
                total_files += 1

    result = index.rollup("", depth=3, top=40, ext_top=12)
    assert result is not None
    node = result["node"]
    validate_rollup_node(node)

    emitted = _count_nodes(node)
    payload_bytes = len(json.dumps(result))
    print(
        f"adversarial rollup: {total_files} files -> {emitted} nodes, "
        f"{payload_bytes:,} bytes (cap {ROLLUP_MAX_NODES} nodes)"
    )
    assert emitted <= ROLLUP_MAX_NODES
    assert payload_bytes < 400_000, f"payload {payload_bytes:,} bytes exceeds the budget"
    # Totals stay full-subtree even where emission was cut.
    assert node["total_files"] == total_files

    # The cut is visible, never silent: budget-exhausted directories
    # carry the children:null lazy sentinel and/or a rest bucket.
    def _has_cut_marker(n: dict[str, Any]) -> bool:
        if n.get("children") is None or "rest" in n:
            return True
        return any(
            _has_cut_marker(child)
            for child in n.get("children") or []
            if child.get("type") == "dir"
        )

    assert _has_cut_marker(node)


def test_rollup_budget_on_synthetic_large_index(tmp_path: Path) -> None:
    """Query-cost budget record: rollup over a synthetic index.

    Builds ~40k entries directly (disk-free) — the spec budget is 150 ms
    at 100k entries; the hard gate here is generous for CI jitter and
    the measured value prints for the budget record.
    """

    index = InventoryIndex()
    entries = index._entries  # synthetic index setup, test-only
    root_placeholder = FsEntry.for_observed_dir(path="", parent="", name="root")
    dir_count = 200
    files_per_dir = 200
    mtime_ns = 1_700_000_000_000_000_000
    entries[""] = replace(
        root_placeholder,
        total_files=dir_count * files_per_dir,
        total_size=dir_count * files_per_dir * 10,
        newest_mtime_ns=mtime_ns,
    )
    for d in range(dir_count):
        dir_path = f"d{d:03d}"
        placeholder = FsEntry.for_observed_dir(path=dir_path, parent="", name=dir_path)
        entries[dir_path] = replace(
            placeholder,
            total_files=files_per_dir,
            total_size=files_per_dir * 10,
            newest_mtime_ns=mtime_ns,
        )
        for f in range(files_per_dir):
            file_path = f"{dir_path}/f{f:03d}.py"
            entries[file_path] = FsEntry.for_observed_file(
                path=file_path,
                parent=dir_path,
                name=f"f{f:03d}.py",
                size=10,
                mtime_ns=mtime_ns,
            )

    start = time.perf_counter()
    result = index.rollup("", depth=3, top=40, ext_top=12)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert result is not None
    total = dir_count * files_per_dir
    assert result["node"]["total_files"] == total
    print(f"rollup budget: {total} files in {elapsed_ms:.1f}ms (spec: 150ms at 100k entries)")
    assert elapsed_ms < 1_000, f"rollup took {elapsed_ms:.1f}ms on {total} synthetic entries"
