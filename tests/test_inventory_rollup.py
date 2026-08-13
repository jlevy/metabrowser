"""Focused contracts for pure inventory rollup aggregation."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from metabrowser.events import FsEntry
from metabrowser.inventory import InventoryIndex
from metabrowser.inventory_rollup import RollupOptions, RollupRank


def _synthetic_index(files: list[tuple[str, int, bool]]) -> InventoryIndex:
    index = InventoryIndex()
    mtime_ns = 1_700_000_000_000_000_000
    root = FsEntry.for_observed_dir(path="", parent="", name="root")
    index._entries[""] = replace(
        root,
        total_files=len(files),
        total_size=sum(size for _name, size, _ignored in files),
        newest_mtime_ns=mtime_ns,
    )
    for name, size, ignored in files:
        entry = FsEntry.for_observed_file(
            path=name,
            parent="",
            name=name,
            size=size,
            mtime_ns=mtime_ns,
        )
        index._entries[name] = replace(entry, gitignored=ignored)
    return index


def test_rollup_options_reject_invalid_limits_and_rank() -> None:
    with pytest.raises(ValueError):
        RollupOptions(depth=-1, top=0, ext_top=0, max_nodes=0)
    with pytest.raises(ValueError):
        RollupOptions(depth=0, top=-1, ext_top=0, max_nodes=0)
    with pytest.raises(ValueError):
        RollupOptions(depth=0, top=0, ext_top=-1, max_nodes=0)
    with pytest.raises(ValueError):
        RollupOptions(depth=0, top=0, ext_top=0, max_nodes=-1)
    with pytest.raises(ValueError):
        RollupOptions(
            depth=0,
            top=0,
            ext_top=0,
            max_nodes=0,
            ext_rank=cast(RollupRank, "unknown"),
        )


def test_dual_rank_keeps_count_and_byte_heavy_types_with_exact_other() -> None:
    files = [(f"tiny-{index}.txt", 1, False) for index in range(20)]
    files.extend(
        [
            ("large.bin", 10_000, False),
            ("ignored.log", 9_000, True),
            ("empty.cfg", 0, False),
            ("README", 7, False),
        ]
    )
    index = _synthetic_index(files)

    result = index.rollup("", depth=0, top=0, ext_top=2, ext_rank="dual")
    assert result is not None
    assert result["node"]["children"] is None
    rows = result["ext_tallies"]
    assert [row[0] for row in rows] == [".bin", ".txt", ""]
    assert rows[-1][1:] == (3, 9_007, 2, 7)
    assert sum(row[1] for row in rows) == 24
    assert sum(row[2] for row in rows) == 19_027
    assert sum(row[3] for row in rows) == 23
    assert sum(row[4] for row in rows) == 10_027


def test_dual_rank_uses_union_of_all_populations() -> None:
    index = _synthetic_index(
        [
            ("tracked.py", 0, False),
            ("ignored.md", 0, True),
            ("extensionless", 0, False),
        ]
    )

    result = index.rollup("", depth=0, top=0, ext_top=10, ext_rank="dual")
    assert result is not None
    assert {row[0] for row in result["ext_tallies"]} == {".py", ".md", "(none)"}
    assert result["node"]["total_size"] == 0


def test_zero_top_accounts_for_omitted_children_when_depth_allows() -> None:
    index = _synthetic_index([("one.py", 5, False), ("two.md", 7, False)])

    result = index.rollup("", depth=1, top=0, ext_top=10, ext_rank="dual")
    assert result is not None
    assert result["node"]["children"] == []
    assert result["node"].get("rest") == {
        "dirs": 0,
        "files": 2,
        "size": 12,
        "unignored_files": 2,
        "unignored_size": 12,
    }
