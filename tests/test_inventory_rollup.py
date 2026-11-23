"""Focused contracts for pure inventory rollup aggregation."""

from __future__ import annotations

import random
from collections.abc import Iterator
from dataclasses import dataclass, replace
from typing import Any, cast

import pytest
from conftest import SyntheticIndexWriter

from metabrowser.events import FsEntry
from metabrowser.file_type_registry import FileTypeClassification, load_file_type_registry
from metabrowser.inventory_engine.providers.python_inventory import (
    _PythonInventoryStore as PythonInventoryStore,
)
from metabrowser.inventory_rollup import (
    RollupOptions,
    RollupRank,
    build_rollup,
    group_rollup_children,
)


def _synthetic_index(files: list[tuple[str, int, bool]]) -> PythonInventoryStore:
    index = PythonInventoryStore()
    entries = SyntheticIndexWriter(index)
    mtime_ns = 1_700_000_000_000_000_000
    root = FsEntry.for_observed_dir(path="", parent="", name="root")
    entries[""] = replace(
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
        entries[name] = replace(entry, gitignored=ignored)
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

    index = _synthetic_index(
        [
            ("app.js", 1, False),
            ("bundle.min.js", 1, False),
            ("types.d.ts", 1, False),
            ("unknown.zzz", 1, False),
            ("README", 1, False),
        ]
    )
    monkeypatch.setattr(index, "_registry", CountingRegistry())

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
    log_files = next(
        family for family in groups["other"]["families"] if family["id"] == "log-files"
    )
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


@dataclass(frozen=True, slots=True)
class _RollupProbe:
    path: str
    parent: str
    name: str
    type: str
    ext: str
    size: int
    mtime_ns: int
    gitignored: bool
    total_files: int | None


def test_omit_mtime_drops_mtime_from_emitted_nodes() -> None:
    entries = {
        "": _RollupProbe("", "", "root", "dir", "", 0, 1, False, 1),
        "a.txt": _RollupProbe("a.txt", "", "a.txt", "file", ".txt", 4, 1, False, None),
    }
    result = build_rollup(
        entries,
        group_rollup_children(entries),
        "",
        RollupOptions(depth=1, top=10, ext_top=10, max_nodes=10, omit_mtime=True),
        False,
    )
    assert result is not None
    assert "mtime" not in result["node"]
    children = result["node"]["children"]
    assert children is not None
    assert "mtime" not in children[0]


def test_rollup_mtime_stays_in_the_filesystem_key_order() -> None:
    entries = {
        "": _RollupProbe("", "", "root", "dir", "", 0, 1, False, 1),
        "a.txt": _RollupProbe("a.txt", "", "a.txt", "file", ".txt", 4, 1, False, None),
    }
    result = build_rollup(
        entries,
        group_rollup_children(entries),
        "",
        RollupOptions(depth=1, top=10, ext_top=10, max_nodes=10),
        False,
    )
    assert result is not None
    dir_keys = list(result["node"].keys())
    assert dir_keys.index("mtime") == dir_keys.index("unignored_size") + 1
    children = result["node"]["children"]
    assert children is not None
    file_keys = list(children[0].keys())
    assert file_keys[file_keys.index("size") : file_keys.index("ext") + 1] == [
        "size",
        "mtime",
        "ext",
    ]


def test_node_budget_expands_the_heaviest_directory_first() -> None:
    """A wide, light folder must not spend the budget a deep, heavy one needs.

    Level by level, the budget went to ``wide``'s thirty one-file folders and ``zdeep/a``
    came back unexpanded, though it holds most of the files. Heaviest first, the chain
    down to ``zdeep/a/b`` expands and its files are emitted. The heavy branch sorts after
    the light one, so expanding in path order fails here too.
    """

    entries = _probes(
        _dir(""),
        _dir("wide"),
        _dir("zdeep"),
        _dir("zdeep/a"),
        _dir("zdeep/a/b"),
        *(_dir(f"wide/s{i:02d}") for i in range(30)),
        *(_file(f"wide/s{i:02d}/x.py", 10) for i in range(30)),
        *(_file(f"zdeep/a/b/f{i:03d}.py", 10) for i in range(100)),
    )

    root = _rollup_root(entries, depth=6, top=50, max_nodes=40)
    nodes = _nodes_by_path(root)
    assert nodes["zdeep/a"]["children"] is not None
    assert nodes["zdeep/a/b"]["children"], "the heaviest chain was not expanded"
    assert len(nodes) <= 40


def test_node_budget_weighs_unignored_files_beside_all_files() -> None:
    """One response serves both Show ignored settings.

    ``build`` is ignored and holds most of all files; ``src`` holds most of the unignored
    ones. Both expand before ``docs``, which is light by either measure. Weighing all
    files alone leaves ``src`` unexpanded; weighing unignored files alone leaves ``build``.
    """

    entries = _probes(
        _dir(""),
        _dir("build", ignored=True),
        _dir("build/a"),
        _dir("build/b"),
        _dir("src"),
        _dir("src/lib"),
        _dir("docs"),
        _dir("docs/guide"),
        *(_file(f"build/a/f{i:02d}.py") for i in range(50)),
        *(_file(f"build/b/f{i:02d}.py") for i in range(40)),
        *(_file(f"src/lib/f{i}.py") for i in range(8)),
        *(_file(f"docs/guide/f{i}.md") for i in range(2)),
    )

    nodes = _nodes_by_path(_rollup_root(entries, depth=12, top=50, max_nodes=15))
    assert [child["name"] for child in nodes["build"]["children"] or []] == ["a", "b"]
    assert len(nodes.get("src/lib", {}).get("children") or []) == 8
    assert nodes["build/a"]["children"] is None
    assert nodes["docs"]["children"] is None


def test_node_budget_weighs_bytes_beside_files() -> None:
    """A folder heavy by bytes and one heavy by files both expand before a light one.

    ``assets`` holds one large file, ``tests`` many small ones, and ``misc`` is light by
    either measure, though it outweighs ``tests`` by bytes and ``assets`` by files.
    """

    entries = _probes(
        _dir(""),
        _dir("assets"),
        _dir("assets/img"),
        _dir("tests"),
        _dir("tests/unit"),
        _dir("misc"),
        _dir("misc/x"),
        _file("assets/img/hero.png", 9_000),
        *(_file(f"tests/unit/t{i}.py", 1) for i in range(8)),
        *(_file(f"misc/x/m{i}.bin", 500) for i in range(2)),
    )

    nodes = _nodes_by_path(_rollup_root(entries, depth=12, top=50, max_nodes=15))
    assert len(nodes["assets/img"]["children"] or []) == 1
    assert len(nodes.get("tests/unit", {}).get("children") or []) == 8
    assert nodes["misc"]["children"] is None


def test_node_budget_breaks_an_exact_weight_tie_by_path() -> None:
    """Equal weights at one level expand in path order, whatever order they were found.

    ``q`` outweighs ``p``, so ``q/aa`` is found before ``p/zz``; the two weigh exactly the
    same and the budget expands one, so path order picks ``p/zz``. The emitted tree is the
    same whatever order the entries arrive in.
    """

    probes = (
        _dir(""),
        _dir("p"),
        _dir("p/zz"),
        _dir("q"),
        _dir("q/aa"),
        _file("q/f1.py"),
        _file("q/f2.py"),
        *(_file(f"p/zz/f{i}.py") for i in range(5)),
        *(_file(f"q/aa/f{i}.py") for i in range(5)),
    )

    root = _rollup_root(_probes(*probes), depth=12, top=50, max_nodes=12)
    nodes = _nodes_by_path(root)
    assert len(nodes["p/zz"]["children"] or []) == 5
    assert nodes["q/aa"]["children"] is None
    assert _rollup_root(_probes(*reversed(probes)), depth=12, top=50, max_nodes=12) == root


def test_zero_weight_tree_expands_level_by_level() -> None:
    """With no files counted yet every weight is zero, and expansion falls back to levels.

    Path order would expand ``a/x`` before ``b``; level order, which keeps truncation
    honest (``inventory_engine/contract.py``), expands every top-level folder it can first.
    """

    entries = _probes(
        _dir(""),
        *(_dir(name) for name in ("a", "b", "c")),
        *(_dir(f"{name}/x") for name in ("a", "b", "c")),
        *(_dir(f"{name}/x/y") for name in ("a", "b", "c")),
    )

    nodes = _nodes_by_path(_rollup_root(entries, depth=12, top=10, max_nodes=6))
    assert [child["path"] for child in nodes["a"]["children"] or []] == ["a/x"]
    assert [child["path"] for child in nodes["b"]["children"] or []] == ["b/x"]
    assert nodes["c"]["children"] is None
    assert nodes["a/x"]["children"] is None


@pytest.mark.parametrize(
    ("top", "max_nodes"),
    [(0, 1_200), (1, 1_200), (7, 1_200), (200, 1_200), (200, 90), (6_000, 100_000)],
)
def test_selected_children_and_rest_match_a_full_sort(top: int, max_nodes: int) -> None:
    """Selecting the leading children equals sorting every child, on a large directory.

    The reference below sorts both rankings in full, interleaves them, emits up to the
    limit, and sums every omitted child into ``rest``, as emission did before it selected.
    Sizes repeat so that path breaks ties; heavy symlinks lead both rankings, so the
    selection has to reach past them; some folders outweigh every file, so folders are
    emitted beside a ``rest``; and some files and folders are ignored.
    """

    rng = random.Random(20261122)
    probes: list[_RollupProbe] = [_dir("")]
    for i in range(3_000):
        probes.append(_file(f"f{i:04d}.py", rng.choice((0, 1, 2, 3, 5, 8, 13)), ignored=i % 7 == 0))
    for i in range(400):
        folder = f"d{i:03d}"
        probes.append(_dir(folder, ignored=i % 5 == 0))
        probes.extend(
            _file(f"{folder}/g{j}.md", rng.choice((1, 2, 3, 40)), ignored=j == 0 and i % 3 == 0)
            for j in range(rng.randint(0, 4))
        )
    for i in range(40):
        probes.append(_file(f"s{i:02d}", 1_000_000, kind="symlink", ignored=i % 2 == 0))
    entries = _probes(*probes)

    root = _rollup_root(entries, depth=1, top=top, max_nodes=max_nodes)

    children = [probe for probe in entries.values() if probe.parent == "" and probe.path]
    expected_paths, expected_rest = _full_sort_reference(entries, children, min(top, max_nodes - 1))
    assert [child["path"] for child in root["children"]] == expected_paths
    assert root.get("rest") == expected_rest
    # The fixture reaches the case it is for: folders emitted beside a rest.
    if top == 200 and max_nodes == 1_200:
        assert any(child["type"] == "dir" for child in root["children"]) and expected_rest
        assert 0 < expected_rest["dirs"] < 400


def _full_sort_reference(
    entries: dict[str, _RollupProbe],
    children: list[_RollupProbe],
    emit_limit: int,
) -> tuple[list[str], dict[str, int] | None]:
    # Totals of each folder's files: (files, bytes, unignored files, unignored bytes).
    subtree: dict[str, list[int]] = {
        child.path: [0, 0, 0, 0] for child in children if child.type == "dir"
    }
    for probe in entries.values():
        totals = subtree.get(probe.parent)
        if totals is None or probe.type != "file":
            continue
        totals[0] += 1
        totals[1] += probe.size
        if not (entries[probe.parent].gitignored or probe.gitignored):
            totals[2] += 1
            totals[3] += probe.size

    def all_weight(child: _RollupProbe) -> int:
        return subtree[child.path][1] if child.type == "dir" else child.size

    def visible_weight(child: _RollupProbe) -> int:
        if child.type == "dir":
            return subtree[child.path][3]
        return 0 if child.gitignored else child.size

    all_ranked = sorted(children, key=lambda child: (-all_weight(child), child.path))
    visible_ranked = sorted(children, key=lambda child: (-visible_weight(child), child.path))
    ordered: list[_RollupProbe] = []
    seen: set[str] = set()
    for pair in zip(all_ranked, visible_ranked, strict=True):
        for child in pair:
            if child.path not in seen:
                seen.add(child.path)
                ordered.append(child)
    emitted: list[str] = []
    omitted: list[_RollupProbe] = []
    for child in ordered:
        if len(emitted) >= emit_limit:
            omitted.append(child)
        elif child.type in ("dir", "file"):
            emitted.append(child.path)
    if not omitted:
        return emitted, None
    rest = {"dirs": 0, "files": 0, "size": 0, "unignored_files": 0, "unignored_size": 0}
    for child in omitted:
        if child.type == "dir":
            files, size, visible_files, visible_size = subtree[child.path]
            rest["dirs"] += 1
        elif child.type == "file":
            files, size = 1, child.size
            visible_files, visible_size = (0, 0) if child.gitignored else (1, child.size)
        else:
            continue
        rest["files"] += files
        rest["size"] += size
        rest["unignored_files"] += visible_files
        rest["unignored_size"] += visible_size
    return emitted, rest


def _dir(path: str, *, ignored: bool = False) -> _RollupProbe:
    parent, _, name = path.rpartition("/")
    return _RollupProbe(path, parent, name or "root", "dir", "", 0, 1, ignored, 1)


def _file(path: str, size: int = 1, *, ignored: bool = False, kind: str = "file") -> _RollupProbe:
    parent, _, name = path.rpartition("/")
    dot = name.rfind(".")
    ext = name[dot:] if dot > 0 else ""
    return _RollupProbe(path, parent, name, kind, ext, size, 1, ignored, None)


def _probes(*probes: _RollupProbe) -> dict[str, _RollupProbe]:
    return {probe.path: probe for probe in probes}


def _rollup_root(
    entries: dict[str, _RollupProbe], *, depth: int, top: int, max_nodes: int
) -> dict[str, Any]:
    result = build_rollup(
        entries,
        group_rollup_children(entries),
        "",
        RollupOptions(depth=depth, top=top, ext_top=0, max_nodes=max_nodes),
        False,
    )
    assert result is not None
    return cast(dict[str, Any], result["node"])


def _nodes_by_path(root: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {node["path"]: node for node in _walk(root)}


def _walk(node: dict[str, Any]) -> Iterator[dict[str, Any]]:
    yield node
    for child in node.get("children") or []:
        yield from _walk(child)
