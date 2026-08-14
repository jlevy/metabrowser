"""Focused contracts for pure inventory rollup aggregation."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, cast

import pytest

import metabrowser.inventory_rollup as inventory_rollup
from metabrowser.events import FsEntry
from metabrowser.file_type_registry import FileTypeClassification, load_file_type_registry
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
        RollupOptions(depth=0, top=0, ext_top=0, max_nodes=0, remaining_top=-1)
    with pytest.raises(ValueError):
        RollupOptions(depth=0, top=0, ext_top=0, max_nodes=0, remaining_top=21)
    with pytest.raises(ValueError):
        RollupOptions(depth=0, top=0, ext_top=0, max_nodes=0, filename_top=21)
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


def test_breakdown_aggregates_families_before_bounding_the_remaining_tail() -> None:
    files = [
        ("app.js", 10, False),
        ("bundle.min.js", 20, False),
        ("worker.mjs", 30, True),
        ("types.d.ts", 5, False),
        ("large.unknown", 1_000, False),
        ("many.raw", 3, False),
        ("README", 7, False),
    ]
    index = _synthetic_index(files)

    result = index.rollup("", depth=0, top=0, ext_top=1, remaining_top=1, ext_rank="dual")

    assert result is not None
    breakdown = result["file_type_breakdown"]
    families = {
        family["id"]: family for group in breakdown["groups"] for family in group["families"]
    }
    # Compound suffixes fold into the canonical family member before any cap applies,
    # so a low remaining_top never truncates a known family.
    assert families["javascript"]["metrics"] == {
        "all": {"files": 3, "bytes": 60},
        "unignored": {"files": 2, "bytes": 30},
    }
    assert [child["extension"] for child in families["javascript"]["extensions"]] == [
        ".js",
        ".mjs",
    ]
    assert families["typescript"]["extensions"] == [
        {
            "extension": ".ts",
            "metrics": {"all": {"files": 1, "bytes": 5}, "unignored": {"files": 1, "bytes": 5}},
        }
    ]

    assert [row["basename"] for row in breakdown["no_extension"]["filenames"]] == ["README"]
    remaining = breakdown["remaining_types"]
    assert len(remaining["extensions"]) == 1
    assert remaining["others"] is not None
    assert remaining["others"]["omitted_distinct_values"] == 1

    totals = breakdown["metrics"]["all"]
    assert totals["files"] == result["node"]["total_files"]
    assert totals["bytes"] == result["node"]["total_size"]


def test_rollup_classifies_each_distinct_extension_once(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = load_file_type_registry()
    calls: list[str] = []

    class CountingRegistry:
        def __getattr__(self, name: str) -> Any:
            return getattr(registry, name)

        def classify(self, name: str, extension: str) -> FileTypeClassification:
            calls.append(extension)
            return registry.classify(name, extension)

    monkeypatch.setattr(inventory_rollup, "load_file_type_registry", CountingRegistry)
    index = _synthetic_index(
        [
            ("app.js", 1, False),
            ("bundle.min.js", 1, False),
            ("types.d.ts", 1, False),
            ("unknown.zzz", 1, False),
            ("README", 1, False),
        ]
    )

    result = index.rollup("", depth=0, top=0, ext_top=0, remaining_top=20, ext_rank="dual")

    assert result is not None
    assert sorted(calls) == [".d.ts", ".js", ".min.js", ".zzz"]


def test_registry_breakdown_groups_families_and_bounds_fallback_children() -> None:
    files = [
        ("events.jsonl", 20, False),
        ("notes.log", 10, True),
        ("photo.svg", 5, False),
    ]
    files.extend((f"bare-{index}", index, False) for index in range(21))
    files.extend((f"unknown-{index}.x{index}", index, False) for index in range(21))
    index = _synthetic_index(files)

    result = index.rollup("", depth=0, top=0, ext_top=1, remaining_top=20, filename_top=20)

    assert result is not None
    breakdown = result["file_type_breakdown"]
    assert breakdown["schema"] == "file-type-breakdown-v1"
    groups = {group["id"]: group for group in breakdown["groups"]}
    log_files = groups["logs"]["families"][0]
    assert log_files["id"] == "log-files"
    assert {row["extension"] for row in log_files["extensions"]} == {".jsonl", ".log"}
    assert groups["media"]["families"][0]["id"] == "images"

    no_extension = breakdown["no_extension"]
    assert len(no_extension["filenames"]) == 20
    assert no_extension["others"] is not None
    assert no_extension["others"]["omitted_distinct_values"] == 1
    remaining = breakdown["remaining_types"]
    assert len(remaining["extensions"]) == 20
    assert remaining["others"] is not None
    assert remaining["others"]["omitted_distinct_values"] == 1
