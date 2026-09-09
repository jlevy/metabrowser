"""PythonInventoryStore.rollup: subtree aggregation for the treemap.

Deterministic fixture trees exercise: full-subtree totals with the
gitignore-excluded variants, extension tallies with the remainder row,
dominant extensions, top-N children with the rest bucket, the depth
sentinel (children: null with full totals), pending state, and the
non-directory / unknown-path None result. A synthetic large index
records the query-cost budget (spec: <=150 ms at 100k entries).
"""

from __future__ import annotations

import asyncio
import re
import threading
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from conftest import SyntheticIndexWriter
from watchfiles import Change

from metabrowser.events import FsEntry
from metabrowser.inventory_engine.contract import DiagnosticsQuery, ReadRequest
from metabrowser.inventory_engine.providers.python_inventory import (
    _PythonInventoryStore as PythonInventoryStore,
)
from metabrowser.watch_backends import _emit_for_path
from metabrowser.wire_models import RollupDirNode, RollupResult, validate_rollup_node


def _build_index(root: Path, *, gitignore: str | None = None) -> PythonInventoryStore:
    if gitignore is not None:
        (root / ".gitignore").write_text(gitignore)
        (root / ".git").mkdir()
    index = PythonInventoryStore()

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

    assert node["children"] is not None
    by_name = {child["name"]: child for child in node["children"]}
    assert by_name["build"]["gitignored"] is True
    assert by_name["build"]["unignored_size"] == 0
    assert by_name["src"]["total_files"] == 3
    assert by_name["src"]["dominant_ext"] == ".py"

    tallies = {row[0]: row for row in result["ext_tallies"]}
    assert tallies[".bin"][1:] == (1, 1000, 0, 0)
    assert tallies[".py"][1:] == (2, 150, 2, 150)
    assert tallies[".md"][1:] == (1, 25, 1, 25)


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
    assert node["children"] is not None
    names = [child["name"] for child in node["children"]]
    assert names == ["f0.txt", "f1.txt", "f2.txt"]  # largest bytes first
    rest = node.get("rest")
    assert rest is not None
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
    assert node["children"] is not None
    a_node = node["children"][0]
    assert a_node["name"] == "a"
    assert a_node["children"] is None  # past depth
    assert a_node["total_size"] == 42  # totals remain full-subtree


def test_rollup_none_for_files_and_unknown_paths(tmp_path: Path) -> None:
    (tmp_path / "file.txt").write_text("x")
    index = _build_index(tmp_path)
    assert index.rollup("file.txt", depth=2, top=10, ext_top=4) is None
    assert index.rollup("missing", depth=2, top=10, ext_top=4) is None


def test_rollup_reuses_child_index_until_inventory_changes(tmp_path: Path) -> None:
    (tmp_path / "leaf").mkdir()
    (tmp_path / "leaf" / "one.txt").write_text("one")
    index = _build_index(tmp_path)

    # The child index is maintained on write, so no rollup rebuilds it, and a
    # repeated request reuses the cached subtree aggregate rather than
    # re-walking the subtree.
    first = index.rollup("leaf", depth=1, top=10, ext_top=4)
    cached_aggregate = index._subtree_aggregates.get("leaf")
    assert cached_aggregate is not None
    second = index.rollup("leaf", depth=1, top=10, ext_top=4)
    assert first == second
    assert index._subtree_aggregates.get("leaf") is cached_aggregate

    added = FsEntry.for_observed_file(
        path="leaf/two.md",
        parent="leaf",
        name="two.md",
        size=3,
        mtime_ns=1_700_000_000_000_000_000,
    )
    index.apply_live_entry(added)
    refreshed = index.rollup("leaf", depth=1, top=10, ext_top=4)
    assert refreshed is not None
    assert refreshed["node"]["total_files"] == 2


def test_rollup_reflects_real_fs_mutation_through_fs_change(tmp_path: Path) -> None:
    """Integration leg of the live-refresh chain: a real filesystem
    mutation, driven through the watcher's producer (`_emit_for_path`,
    the code `awatch` feeds), must emit `fs.change` upserts that reach
    root scope AND be visible in the next rollup. The client half —
    `fs.change` on SSE → `metabrowser:inventory-change` → watchRollup
    refetch — is covered by tests/dom/folder-plugin-behavior.js; this
    test pins the server half those events promise.
    """

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x" * 100)

    async def run() -> tuple[RollupResult, set[str], RollupResult, RollupResult]:
        index = PythonInventoryStore()
        index.start(tmp_path)
        await index.wait_until_done(10)

        before = index.rollup("", depth=3, top=40, ext_top=12)
        assert before is not None
        checkpoint = await index.read(
            ReadRequest(queries=(DiagnosticsQuery(query_id="before-add"),))
        )

        target = tmp_path / "src" / "table.csv"
        target.write_bytes(b"c" * 500)
        await _emit_for_path(
            index.refresh,
            tmp_path,
            str(target),
            Change.added,
        )
        change = await asyncio.wait_for(
            anext(index.changes(after=checkpoint.cursor)),
            timeout=1.0,
        )
        upserts = set(change.dirty_paths)

        after_add = index.rollup("", depth=3, top=40, ext_top=12)
        assert after_add is not None

        target.unlink()
        await _emit_for_path(
            index.refresh,
            tmp_path,
            str(target),
            Change.deleted,
        )
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
    assert node["children"] is not None
    src_node = next(child for child in node["children"] if child["name"] == "src")
    assert src_node["total_size"] == 600
    tallies = {row[0]: row for row in after_add["ext_tallies"]}
    assert tallies[".csv"][1:] == (1, 500, 1, 500)

    node = after_delete["node"]
    validate_rollup_node(node)
    assert (node["total_files"], node["total_size"]) == (1, 100)
    assert ".csv" not in {row[0] for row in after_delete["ext_tallies"]}


def _count_nodes(node: RollupDirNode | dict[str, Any]) -> int:
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

    index = PythonInventoryStore()
    entries = SyntheticIndexWriter(index)  # synthetic index setup, test-only
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
    def _has_cut_marker(n: RollupDirNode | dict[str, Any]) -> bool:
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

    index = PythonInventoryStore()
    entries = SyntheticIndexWriter(index)  # synthetic index setup, test-only
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


def _assert_derived_state_matches_entries(index: PythonInventoryStore) -> None:
    """The index keeps derived structures beside ``_entries``; they must agree.

    ``_children_index`` and ``_subtree_aggregates`` are maintained on every
    write rather than rebuilt per request, which is what keeps a rollup
    proportional to what changed. That trade only holds while they stay in
    step with the entries they summarize, and a missed eviction is invisible
    until a folder reports a stale count, so check them against a from-scratch
    derivation.
    """

    expected_children: dict[str, dict[str, FsEntry]] = {}
    for entry in index._entries.values():
        if entry.path == entry.parent:
            continue  # the served root is not its own child
        expected_children.setdefault(entry.parent, {})[entry.path] = entry
    assert index._children_index == expected_children, "child index drifted from entries"

    # Every cached aggregate must equal what a cold rollup would compute.
    for path in list(index._subtree_aggregates):
        cached = index.rollup(path, depth=0, top=0, ext_top=0)
        cold = PythonInventoryStore()
        for entry in index._entries.values():
            cold._replace_index_entry(entry)
        fresh = cold.rollup(path, depth=0, top=0, ext_top=0)
        assert cached == fresh, f"stale aggregate cached for {path!r}"


def _total_files(index: PythonInventoryStore, path: str) -> int:
    result = index.rollup(path, depth=0, top=0, ext_top=0)
    assert result is not None, f"no rollup for {path!r}"
    return result["node"]["total_files"]


def test_derived_index_state_survives_writes_and_removals(tmp_path: Path) -> None:
    """Adding and removing entries must leave no stale derived state."""

    (tmp_path / "keep").mkdir()
    (tmp_path / "keep" / "a.py").write_text("x" * 10)
    (tmp_path / "drop").mkdir()
    (tmp_path / "drop" / "nested").mkdir()
    (tmp_path / "drop" / "nested" / "b.md").write_text("y" * 20)
    index = _build_index(tmp_path)

    # Populate the aggregate memo, then mutate underneath it.
    index.rollup("", depth=3, top=40, ext_top=12)
    _assert_derived_state_matches_entries(index)

    # Store a file the way the walker does — a leaf write with no accompanying
    # rewrite of its ancestor directory entries. Every directory above it still
    # has to lose its cached aggregate, or the folder keeps reporting the count
    # it had before the file arrived.
    index._replace_index_entry(
        FsEntry.for_observed_file(
            path="keep/c.py",
            parent="keep",
            name="c.py",
            size=30,
            mtime_ns=1_700_000_000_000_000_000,
        )
    )
    assert _total_files(index, "keep") == 2
    assert _total_files(index, "") == 3
    _assert_derived_state_matches_entries(index)

    index.apply_live_entry(
        FsEntry.for_observed_file(
            path="keep/d.py",
            parent="keep",
            name="d.py",
            size=30,
            mtime_ns=1_700_000_000_000_000_000,
        )
    )
    index.rollup("", depth=3, top=40, ext_top=12)
    assert _total_files(index, "keep") == 3
    _assert_derived_state_matches_entries(index)

    # Removing a directory must drop the whole subtree from every structure.
    index.remove("drop")
    index.rollup("", depth=3, top=40, ext_top=12)
    assert index.get("drop/nested/b.md") is None
    assert "drop" not in index._children_index
    assert "drop/nested" not in index._children_index
    # keep/a.py, keep/c.py, keep/d.py survive; the drop/ subtree is gone.
    assert _total_files(index, "") == 3
    _assert_derived_state_matches_entries(index)


def test_eviction_epochs_are_released_once_no_rollup_is_in_flight(tmp_path: Path) -> None:
    """The epoch map is bounded by in-flight passes, not by paths ever seen.

    An epoch only exists so a merge can refuse an aggregate the walker has
    moved past. With no pass in flight there is no merge left to consult it.
    Retaining them instead grows the map with every directory path seen in the
    process lifetime, so a long session over a churning tree never gives any
    of it back.
    """

    (tmp_path / "keep").mkdir()
    (tmp_path / "keep" / "a.py").write_text("x" * 10)
    index = _build_index(tmp_path)

    index.rollup("", depth=3, top=40, ext_top=12)
    assert index._aggregate_evicted_at == {}
    assert index._rollup_passes_in_flight == 0

    # Churn: each write evicts its ancestor chain and records epochs for it.
    for generation in range(25):
        directory = f"churn{generation}"
        index.apply_live_entry(
            FsEntry.for_observed_file(
                path=f"{directory}/f.py",
                parent=directory,
                name="f.py",
                size=8,
                mtime_ns=1_700_000_000_000_000_000,
            )
        )
    assert index._aggregate_evicted_at, "evictions should record epochs while they matter"

    index.rollup("", depth=3, top=40, ext_top=12)
    assert index._aggregate_evicted_at == {}, "epochs outlived the passes that needed them"
    assert index._rollup_passes_in_flight == 0


def test_aggregate_computed_against_moved_data_is_never_published(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """Invariant 5: a stale aggregate is discarded rather than cached.

    ``/api/rollup`` runs ``build_rollup`` in a worker thread while the walker
    keeps writing on the event loop, so a pass can finish computing a
    directory *after* a write has invalidated it. Publishing that result would
    leave a tally that is wrong and never corrects itself: nothing evicts the
    directory a second time, so the folder keeps reporting the count it had
    before the write until something else happens to write beneath it.

    Reproducing it needs the interleave in one specific place. ``_rollup_view``
    hands out live views rather than copies, so a pass blocked *before* it
    reads a directory's children simply sees the newer data and is correct.
    The window is after the read and before the merge, which is what the stub
    below recreates.
    """

    import metabrowser.inventory_rollup as inventory_rollup

    (tmp_path / "d").mkdir()
    index = _build_index(tmp_path)

    read_children = threading.Event()
    writes_landed = threading.Event()
    original = inventory_rollup._aggregate_subtree

    def aggregate_then_wait(
        directory_path: str,
        parent_ignored: bool,
        children_by_parent: Any,
        aggregates: Any,
    ) -> Any:
        result = original(directory_path, parent_ignored, children_by_parent, aggregates)
        if directory_path == "d":
            # Computed from what the worker could see; now let the walker move
            # past it before this pass merges.
            read_children.set()
            assert writes_landed.wait(5), "writer never ran"
        return result

    monkeypatch.setattr(inventory_rollup, "_aggregate_subtree", aggregate_then_wait)

    async def scenario() -> None:
        pass_done = asyncio.get_running_loop().run_in_executor(
            None, lambda: index.rollup("", depth=2, top=40, ext_top=12)
        )
        assert read_children.wait(5), "rollup pass never reached the directory"
        for number in range(50):
            index._replace_index_entry(
                FsEntry.for_observed_file(
                    path=f"d/f{number}.py",
                    parent="d",
                    name=f"f{number}.py",
                    size=10,
                    mtime_ns=1_700_000_000_000_000_000,
                )
            )
        writes_landed.set()
        await pass_done

    asyncio.run(scenario())

    # What the folder reports once everything has settled must equal what the
    # same entries produce with no cache at all.
    settled = index.rollup("", depth=2, top=40, ext_top=12)
    assert settled is not None
    cold = PythonInventoryStore()
    for entry in index._entries.values():
        cold._replace_index_entry(entry)
    expected = cold.rollup("", depth=2, top=40, ext_top=12)
    assert expected is not None
    assert settled["node"]["total_files"] == expected["node"]["total_files"] == 50
    _assert_derived_state_matches_entries(index)


# Assignments into the index's entry map from outside its two write methods.
# ``_entries[...] = x`` stores an entry without updating ``_children_index``,
# so a later rollup reads the superseded FsEntry out of the child bucket.
_DIRECT_ENTRY_WRITE_RE = re.compile(r"_entries\[[^\]]+\]\s*=(?!=)")

_ENTRY_WRITE_METHODS = ("_replace_index_entry", "_pop_index_entry")


def test_every_index_write_goes_through_the_two_write_methods() -> None:
    """Invariant 2, enforced rather than asserted in prose.

    ``_replace_index_entry`` and ``_pop_index_entry`` are where the derived
    structures are kept in step with ``_entries``. A write that bypasses them
    desynchronizes the index silently, and the shape it leaves behind — a stale
    FsEntry still in its parent's child bucket — surfaces later as a wrong
    tally rather than as an error.
    """

    root = Path(__file__).resolve().parent.parent
    offenders: list[str] = []
    for path in sorted((root / "src").rglob("*.py")) + sorted((root / "tests").rglob("*.py")):
        if path.name == Path(__file__).name:
            continue  # the pattern above lives here
        source = path.read_text(encoding="utf-8")
        in_write_method = False
        for number, line in enumerate(source.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("def "):
                in_write_method = any(name in stripped for name in _ENTRY_WRITE_METHODS)
            if in_write_method:
                continue
            if _DIRECT_ENTRY_WRITE_RE.search(line):
                offenders.append(f"{path.relative_to(root)}:{number}: {stripped}")
    assert not offenders, (
        "write through _replace_index_entry / _pop_index_entry, or "
        "conftest.SyntheticIndexWriter in tests:\n  " + "\n  ".join(offenders)
    )
